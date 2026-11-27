"""Detached process observer. Application exits remain recorded after UI closure."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import psutil

from . import bundle
from .common import Refusal, now, read_json
from .store import Store


def run(state, run_id):
    store = Store(state)
    row = store.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not row or row["status"] != "starting":
        return 2
    with store.db() as con:
        updated = con.execute("UPDATE runs SET runner_pid=?,runner_created=? WHERE id=? AND status='starting' AND runner_pid IS NULL", (os.getpid(), psutil.Process().create_time(), run_id)).rowcount
    if not updated:
        return 2
    root = store.root
    release = root / "releases" / row["release_id"]
    child = None
    code, error = None, None
    try:
        metadata = bundle.verify_directory(release)
        if metadata != store.release(row["release_id"]):
            raise Refusal("Verified release differs from selected metadata")
        store.check_trust(metadata)
        app = metadata["application"]
        data = root / "data" / row["app_id"]
        data.mkdir(parents=True, exist_ok=True)
        work = root / "work" / row["app_id"] / run_id
        work.mkdir(parents=True, exist_ok=True)
        python = sys.executable
        if getattr(sys, "frozen", False):
            import shutil
            names = ("python", "python3") if os.name == "nt" else ("python3", "python")
            python = next((found for name in names if (found := shutil.which(name))), None)
            uses_python = any("{python}" in value for value in [*app["command"], *app.get("environment", {}).values()])
            if not python and uses_python:
                raise Refusal("This application requires external Python on PATH or an explicit interpreter in its command")
            python = python or "python"
        tokens = {"{python}": python, "{release}": str(release / "payload"), "{data}": str(data), "{work}": str(work)}
        def expand(text):
            for key, value in tokens.items():
                text = text.replace(key, value)
            return text
        command = [expand(value) for value in app["command"]]
        environment = {key: value for key, value in os.environ.items() if key in {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL", "PATHEXT", "APPDATA", "LOCALAPPDATA"}}
        environment.update({key: expand(value) for key, value in app.get("environment", {}).items()})
        config = root / "config" / (row["app_id"] + ".json")
        if config.exists():
            environment.update(read_json(config).get("environment", {}))
        environment.setdefault("PYTHONIOENCODING", "utf-8")
        environment.setdefault("PYTHONUTF8", "1")
        missing = [key for key in app.get("secret_env", []) if key not in environment]
        if missing:
            raise Refusal("Configure required environment names before starting: " + ", ".join(missing))
        environment.update({"SCHISM_DATA": str(data), "SCHISM_WORK": str(work), "SCHISM_RELEASE": str(release / "payload"), "SCHISM_APP_ID": row["app_id"], "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
        cwd = release / "payload" / app.get("cwd", ".")
        kwargs = {"cwd": cwd, "env": environment, "stdin": subprocess.DEVNULL, "close_fds": True}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        with (root / "logs" / (run_id + ".log")).open("ab", buffering=0) as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, **kwargs)
            created = psutil.Process(child.pid).create_time()
            with store.db() as con:
                con.execute("UPDATE runs SET status='running',pid=?,process_created=? WHERE id=?", (child.pid, created, run_id))
            code = child.wait()
    except BaseException as exc:
        error = str(exc)
        if child is not None and child.poll() is None:
            from .common import stop_owned
            stop_owned(child.pid, psutil.Process(child.pid).create_time())
            code = child.poll()
    with store.db() as con:
        con.execute("UPDATE runs SET status=?,exit_code=?,error=?,ended_at=? WHERE id=?", ("failed" if error else "exited", code, error, now(), run_id))
    store.event("process.exited", {"run_id": run_id, "app_id": row["app_id"], "release_id": row["release_id"], "exit_code": code, "error": error})
    return 0 if code == 0 and not error else 1
