"""Small portable filesystem and process boundaries used by the controller."""
from __future__ import annotations

import contextlib
import errno
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

import psutil

ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}\Z")


class Refusal(ValueError):
    """A requested transition did not satisfy its preconditions."""


class Cancelled(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def private_root(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for p in (path, *path.parents):
        try:
            attributes = p.lstat()
        except FileNotFoundError:
            continue
        if p.is_symlink() or getattr(attributes, "st_file_attributes", 0) & 0x400:
            raise Refusal("Managed paths cannot traverse a symbolic link or junction: " + str(p))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def atomic_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise Refusal("Refusing a symlink state file")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextlib.contextmanager
def file_lock(path, cancelled=lambda: False):
    """An OS-owned lock; process death releases it without expiry guessing."""
    path = Path(path)
    if path.is_symlink():
        raise Refusal("Refusing a symlink lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    handle = os.fdopen(fd, "r+b")
    try:
        if os.fstat(fd).st_size == 0:
            handle.write(b"0")
            handle.flush()
        while True:
            if cancelled():
                raise Cancelled("Operation cancelled while waiting for application ownership")
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                time.sleep(0.1)
        yield
    finally:
        handle.close()


def process_alive(pid, created):
    if not pid or not created:
        return False
    try:
        p = psutil.Process(int(pid))
        return abs(p.create_time() - float(created)) < 0.01 and p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.Error, ValueError, TypeError):
        return False


def process_identity(pid):
    return {"pid": pid, "created": psutil.Process(pid).create_time()}


def stop_owned(pid, created, timeout=5):
    """Stop only a recorded process identity and its observed descendants."""
    if not process_alive(pid, created):
        return False
    try:
        parent = psutil.Process(int(pid))
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return False
    processes = list(reversed(children)) + [parent]
    for p in processes:
        try:
            p.terminate()
        except psutil.Error:
            pass
    _, remaining = psutil.wait_procs(processes, timeout=timeout)
    for p in remaining:
        try:
            p.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(remaining, timeout=2)
    return True


def controller_command(*args):
    if getattr(sys, "frozen", False):
        return [sys.executable, *map(str, args)]
    return [sys.executable, "-m", "schism_stack", *map(str, args)]


def detached(command, stdout=None):
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": stdout or subprocess.DEVNULL,
              "stderr": subprocess.STDOUT, "cwd": str(Path(__file__).resolve().parents[1]), "close_fds": True}
    if getattr(sys, "frozen", False):
        # Independent frozen workers must own their extracted runtime after the
        # original console exits; they cannot borrow its temporary bundle.
        kwargs["env"] = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        kwargs["cwd"] = str(Path(sys.executable).resolve().parent)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    # Retain and reap the child while this controller lives. The daemon does not
    # couple a detached job's lifetime to a departing caller.
    threading.Thread(target=process.wait, daemon=True).start()
    return process


def validate_id(value, label="Application id"):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise Refusal(label + " must contain lowercase letters, digits, dots, underscores or hyphens")
    return value
