"""Signed, closed application packages. Inspection never executes payload code.

Packages are deliberately selected source directories, not automatic repository
or home-directory exports. Only Python bytecode/cache products are omitted;
private paths, secret-looking names, links and special files cause refusal.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import unicodedata
from urllib.parse import urlsplit
import zipfile

from . import identity
from .common import Refusal, now, validate_id

SCHEMA = "schism.application/v1"
RELEASE_SCHEMA = "schism.release/v1"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_FILES = 10000
APP_FIELDS = {"schema", "id", "name", "version", "kind", "command", "environment",
              "secret_env", "data_schema", "health", "stop_timeout", "task_timeout", "cwd"}
APP_REQUIRED = {"schema", "id", "name", "version", "kind", "command"}
RELEASE_FIELDS = {"schema", "release_id", "application", "files", "publisher", "created_at"}
FILE_FIELDS = {"path", "sha256", "size", "executable"}
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", "conin$", "conout$", *["com" + str(i) for i in range(1, 10)],
                    *["lpt" + str(i) for i in range(1, 10)], "com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"}
SECRET_EXTENSIONS = {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore", ".kdbx"}
SECRET_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "authorized_keys", "known_hosts",
                "schism-state.json", "state.sqlite", "state.sqlite-wal", "state.sqlite-shm",
                "credentials", "secrets", "password", "passwords", "access_token", "refresh_token"}
CODE_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".cs", ".c", ".h", ".cpp"}


def _need(condition, message):
    if not condition:
        raise Refusal(message)


def _loads(raw, limit=MAX_METADATA_BYTES):
    _need(isinstance(raw, bytes) and len(raw) <= limit, "JSON document exceeds its byte limit")
    def pairs(items):
        out = {}
        for key, value in items:
            _need(key not in out, "Duplicate JSON member: " + key)
            out[key] = value
        return out
    def constant(value):
        raise Refusal("Non-finite JSON value: " + value)
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs, parse_constant=constant)
        identity.canonical(value)
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        if isinstance(exc, Refusal):
            raise
        raise Refusal("Invalid UTF-8 JSON: " + str(exc)) from exc


def _text(value, label, maximum=200, empty=False):
    _need(isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= maximum and
          "\x00" not in value, label + " must be a bounded text value")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise Refusal(label + " contains invalid Unicode") from exc
    return value


def _path(value, *, source=False):
    _text(value, "Package path", 1024)
    _need(not value.startswith("/") and "\\" not in value and ":" not in value,
          "Package paths must be relative forward-slash paths")
    parts = value.split("/")
    _need(len(parts) <= 32 and all(part not in {"", ".", ".."} for part in parts), "Traversal or empty package path component")
    for part in parts:
        _need(len(part.encode("utf-8")) <= 240 and not part.endswith((".", " ")) and
              not any(ord(c) < 32 or ord(c) == 127 or c in '<>"|?*' for c in part),
              "Package path is not portable across recipients")
        _need(part.split(".", 1)[0].casefold() not in WINDOWS_RESERVED, "Reserved device name in package path")
        if source:
            _need(not part.startswith("."), "Private dot files and trees are excluded from application packages")
            lower = part.casefold()
            suffix = PurePosixPath(lower).suffix
            secret_word = re.search(r"(?:^|[._-])(?:secrets?|credentials?|passwords?|access[_-]?token|refresh[_-]?token)(?:[._-]|$)", lower)
            _need(lower not in SECRET_NAMES and suffix not in SECRET_EXTENSIONS and
                  not (secret_word and suffix not in CODE_EXTENSIONS),
                  "Secret-looking or operator-state path cannot enter an application package: " + value)
    return value


def _fold(value):
    return unicodedata.normalize("NFC", value).casefold()


def _paths_unique(names):
    seen, nodes = set(), {}
    for name in names:
        folded = _fold(name)
        _need(folded not in seen, "Duplicate or case-colliding package paths")
        seen.add(folded)
        parts = name.split("/")
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = _fold(prefix)
            if key in nodes:
                _need(nodes[key] == prefix, "Case-colliding package directories")
            nodes[key] = prefix
    for name in names:
        parts = name.split("/")
        for index in range(1, len(parts)):
            _need(_fold("/".join(parts[:index])) not in seen, "A package file is also used as a directory")


def _number(value, label, minimum, maximum):
    _need(isinstance(value, (int, float)) and not isinstance(value, bool) and
          math.isfinite(value) and minimum <= value <= maximum, label + " is outside its supported range")
    return value


def _env_name(value):
    _need(isinstance(value, str) and ENV_NAME.fullmatch(value) and not value.upper().startswith("SCHISM_"),
          "Invalid or reserved environment variable name")
    return value


def normalize_application(document):
    _need(isinstance(document, dict) and APP_REQUIRED <= set(document) <= APP_FIELDS,
          "Unknown application fields or missing required fields")
    _need(document["schema"] == SCHEMA, "Unsupported application schema")
    app_id = validate_id(document["id"])
    _path(app_id)
    name = _text(document["name"], "Application name")
    version = _text(document["version"], "Application version", 100)
    _need(isinstance(document["kind"], str) and document["kind"] in {"task", "service"}, "Application kind must be task or service")
    command = document["command"]
    _need(isinstance(command, list) and 1 <= len(command) <= 256, "Application command must be an argv array")
    for index, item in enumerate(command):
        _text(item, "Command argument", 32768, empty=index > 0)
    _need(sum(len(item.encode("utf-8")) for item in command) <= 131072, "Application argv exceeds its byte bound")
    environment = document.get("environment", {})
    _need(isinstance(environment, dict) and len(environment) <= 128, "Application environment must be a bounded object")
    _need(len({_fold(key) for key in environment if isinstance(key, str)}) == len(environment), "Environment keys collide across recipients")
    for key, value in environment.items():
        _env_name(key)
        _text(value, "Environment value", 32768, empty=True)
        _need(not re.search(r"(?:^|_)(?:SECRET|PASSWORD|PASSWD|TOKEN|PRIVATE_KEY|API_KEY|ACCESS_KEY)(?:_|$)", key.upper()),
              "Declare sensitive environment names in secret_env and configure values on the recipient")
    _need(sum(len(v.encode("utf-8")) for v in environment.values()) <= 262144, "Application environment exceeds its byte bound")
    secret_env = document.get("secret_env", [])
    _need(isinstance(secret_env, list) and len(secret_env) <= 128, "secret_env must be a bounded list of names")
    for key in secret_env:
        _env_name(key)
    _need(len({_fold(key) for key in secret_env}) == len(secret_env), "Duplicate secret environment names")
    _need(not ({_fold(key) for key in secret_env} & {_fold(key) for key in environment}), "Secret values cannot be supplied by release environment")
    data_schema = _text(document.get("data_schema", "1"), "Data schema", 100)
    cwd = document.get("cwd", ".")
    if cwd != ".":
        _path(cwd, source=True)
    stop_timeout = _number(document.get("stop_timeout", 5), "Stop timeout", 0.1, 300)
    task_timeout = _number(document.get("task_timeout", 300), "Task timeout", 0.1, 604800)
    health = document.get("health", {"type": "process"})
    _need(isinstance(health, dict) and isinstance(health.get("type"), str) and health.get("type") in {"process", "http"}, "Unsupported health contract")
    if health["type"] == "process":
        _need(set(health) <= {"type", "grace", "timeout"}, "Unknown process-health fields")
        timeout = _number(health.get("timeout", 10), "Health timeout", 0.1, 300)
        grace = _number(health.get("grace", 1), "Process health grace", 0, timeout)
        health = {"type": "process", "grace": grace, "timeout": timeout}
    else:
        _need({"type", "url"} <= set(health) <= {"type", "url", "timeout", "status"}, "Unknown or missing HTTP-health fields")
        url = _text(health["url"], "Health URL", 2048)
        try:
            parsed = urlsplit(url)
            address = ipaddress.ip_address(parsed.hostname or "")
            port = parsed.port
            valid = parsed.scheme == "http" and address.is_loopback and "%" not in (parsed.hostname or "") and not parsed.username and not parsed.password and not parsed.fragment and (port is None or 1 <= port <= 65535)
        except ValueError:
            valid = False
        _need(valid, "HTTP health must use an explicit numeric loopback address without credentials or fragments")
        status = health.get("status", 200)
        _need(isinstance(status, int) and not isinstance(status, bool) and 200 <= status <= 299, "Health status must be an HTTP success code")
        health = {"type": "http", "url": url, "timeout": _number(health.get("timeout", 10), "Health timeout", 0.1, 300), "status": status}
    output = {"schema": SCHEMA, "id": app_id, "name": name, "version": version, "kind": document["kind"],
              "command": list(command), "environment": dict(environment), "secret_env": list(secret_env),
              "data_schema": data_schema, "health": health, "stop_timeout": stop_timeout,
              "task_timeout": task_timeout, "cwd": cwd}
    identity.canonical(output)
    return output


def _no_links(path):
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Refusal("Managed source, output and extraction paths cannot traverse links or junctions")


def _regular_bytes(path, limit=MAX_FILE_BYTES):
    _no_links(path)
    before = path.lstat()
    _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "Payload must contain regular files without hard links")
    _need(before.st_size <= limit, "Application file exceeds its byte bound")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        start = os.fstat(handle.fileno())
        _need((start.st_dev, start.st_ino) == (before.st_dev, before.st_ino), "Source identity changed during packaging")
        raw = handle.read(limit + 1)
        end = os.fstat(handle.fileno())
    _need(len(raw) <= limit and len(raw) == start.st_size and
          (start.st_size, start.st_mtime_ns) == (end.st_size, end.st_mtime_ns), "Source changed or exceeded its bound while read")
    return raw, bool(start.st_mode & 0o111)


def _collect(source):
    payload = {}
    total = 0
    def walk(directory):
        nonlocal total
        for path in sorted(directory.iterdir(), key=lambda p: p.name):
            relative = path.relative_to(source).as_posix()
            info = path.lstat()
            _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                  "Source contains a symlink or junction: " + relative)
            if path.name == "__pycache__" and stat.S_ISDIR(info.st_mode):
                continue
            if path.suffix.casefold() in {".pyc", ".pyo"} and stat.S_ISREG(info.st_mode):
                continue
            _path(relative, source=True)
            if stat.S_ISDIR(info.st_mode):
                walk(path)
            elif stat.S_ISREG(info.st_mode):
                raw, executable = _regular_bytes(path)
                total += len(raw)
                _need(total <= MAX_TOTAL_BYTES and len(payload) < MAX_FILES, "Application inventory exceeds its supported bound")
                payload[relative] = (raw, executable)
            else:
                raise Refusal("Source contains a special file: " + relative)
    walk(source)
    _paths_unique(payload)
    _need("schism.json" in payload, "Source root must contain schism.json")
    return payload


def _timestamp(value):
    _need(isinstance(value, str) and value.endswith("Z"), "Release creation time must be UTC")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise Refusal("Invalid release creation time") from exc


def _metadata(release, envelope):
    _need(isinstance(release, dict) and set(release) == RELEASE_FIELDS and release.get("schema") == RELEASE_SCHEMA,
          "Unknown release fields or schema")
    signed = identity.verify(envelope, RELEASE_SCHEMA)
    _need(identity.canonical(signed) == identity.canonical(release), "Signature does not bind the release document")
    identity.validate_descriptor(release["publisher"])
    _need(release["publisher"]["key_id"] == envelope["key_id"] and
          release["publisher"]["public_key"] == envelope["public_key"], "Release publisher differs from its signer")
    body = {key: value for key, value in release.items() if key != "release_id"}
    _need(release["release_id"] == hashlib.sha256(identity.canonical(body)).hexdigest(), "Release content identity mismatch")
    _timestamp(release["created_at"])
    application = normalize_application(release["application"])
    _need(identity.canonical(application) == identity.canonical(release["application"]), "Release application must contain normalized defaults")
    files = release["files"]
    _need(isinstance(files, list) and 1 <= len(files) <= MAX_FILES, "Invalid release inventory")
    names, total = [], 0
    for item in files:
        _need(isinstance(item, dict) and set(item) == FILE_FIELDS, "Unknown file inventory fields")
        _path(item["path"], source=True)
        _need(isinstance(item["sha256"], str) and HEX.fullmatch(item["sha256"]), "Invalid file digest")
        _need(isinstance(item["size"], int) and not isinstance(item["size"], bool) and 0 <= item["size"] <= MAX_FILE_BYTES,
              "Invalid file size")
        _need(isinstance(item["executable"], bool), "Executable flag must be boolean")
        names.append(item["path"])
        total += item["size"]
    _need(total <= MAX_TOTAL_BYTES and names == sorted(names), "Release inventory must be sorted and bounded")
    _paths_unique(names)
    _need("schism.json" in names, "Release inventory omits its original application document")
    cwd = application["cwd"]
    _need(cwd == "." or any(name.startswith(cwd + "/") for name in names), "Declared working directory is absent from payload")
    return release


def _verify_payload(release, payload):
    expected = {row["path"]: row for row in release["files"]}
    _need(set(payload) == set(expected), "Application payload inventory is not closed")
    for name, (raw, executable) in payload.items():
        row = expected[name]
        _need(len(raw) == row["size"] and hashlib.sha256(raw).hexdigest() == row["sha256"], "Application content differs from signed inventory: " + name)
        _need(executable == row["executable"], "Executable mode differs from signed inventory: " + name)
    manifest = normalize_application(_loads(payload["schism.json"][0], 1024 * 1024))
    _need(identity.canonical(manifest) == identity.canonical(release["application"]), "Original application document differs from normalized release application")


def _read_bundle(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    _no_links(path)
    _need(path.is_file() and path.stat().st_size <= MAX_ARCHIVE_BYTES, "Application archive exceeds its supported bound")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            _need(3 <= len(infos) <= MAX_FILES + 2, "Invalid archive entry count")
            names = []
            total = 0
            for info in infos:
                _path(info.filename)
                _need(info.filename == info.orig_filename and not info.is_dir(), "Directory or altered ZIP member name refused")
                mode = info.external_attr >> 16
                _need(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not info.external_attr & 0x10,
                      "Archive contains a link or special file")
                _need(not info.flag_bits & 1 and info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED},
                      "Encrypted or unsupported compressed entry")
                limit = MAX_METADATA_BYTES if info.filename in {"release.json", "signature.json"} else MAX_FILE_BYTES
                _need(0 <= info.file_size <= limit, "Archive member exceeds its expanded byte bound")
                total += info.file_size
                names.append(info.filename)
            _need(total <= MAX_TOTAL_BYTES + 2 * MAX_METADATA_BYTES, "Expanded application archive exceeds its bound")
            _paths_unique(names)
            _need("release.json" in names and "signature.json" in names, "Release metadata or signature is missing")
            release = _loads(archive.read("release.json"))
            envelope = _loads(archive.read("signature.json"))
            _metadata(release, envelope)
            expected = {"release.json", "signature.json", *["payload/" + row["path"] for row in release["files"]]}
            _need(set(names) == expected, "Archive inventory is not closed")
            payload = {}
            for row in release["files"]:
                info = archive.getinfo("payload/" + row["path"])
                raw = archive.read(info)
                payload[row["path"]] = (raw, bool((info.external_attr >> 16) & 0o111))
            _verify_payload(release, payload)
            return release, envelope, payload
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, EOFError, OSError) as exc:
        if isinstance(exc, Refusal):
            raise
        raise Refusal("Application archive cannot be verified: " + str(exc)) from exc


def inspect(path: Path) -> dict:
    return _read_bundle(path)[0]


def _zip_write(archive, name, raw, executable=False):
    item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    item.create_system = 3
    item.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    item.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(item, raw)


def build(source: Path, output: Path, state: Path) -> dict:
    source, output, state = (Path(os.path.abspath(Path(value).expanduser())) for value in (source, output, state))
    _no_links(source)
    _no_links(output)
    _need(source.is_dir(), "Application source must be a directory")
    _need(not output.is_relative_to(source) and not state.is_relative_to(source), "Package output and operator state must stay outside application source")
    _need(not output.exists(), "Package output already exists; choose a new output path")
    payload = _collect(source)
    app = normalize_application(_loads(payload["schism.json"][0], 1024 * 1024))
    files = [{"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "executable": executable}
             for name, (raw, executable) in sorted(payload.items())]
    body = {"schema": RELEASE_SCHEMA, "application": app, "files": files,
            "publisher": identity.ensure_identity(state), "created_at": now()}
    release = {**body, "release_id": hashlib.sha256(identity.canonical(body)).hexdigest()}
    envelope = identity.sign(state, release, RELEASE_SCHEMA)
    _metadata(release, envelope)
    _verify_payload(release, payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    _no_links(output.parent)
    fd, temporary = tempfile.mkstemp(prefix=".schism-build-", dir=output.parent)
    os.close(fd)
    temp = Path(temporary)
    try:
        with zipfile.ZipFile(temp, "w") as archive:
            _zip_write(archive, "release.json", identity.canonical(release) + b"\n")
            _zip_write(archive, "signature.json", identity.canonical(envelope) + b"\n")
            for name, (raw, executable) in sorted(payload.items()):
                _zip_write(archive, "payload/" + name, raw, executable)
        _need(temp.stat().st_size <= MAX_ARCHIVE_BYTES, "Built application archive exceeds its byte bound")
        inspect(temp)
        # Exclusive final creation preserves earlier releases even under a race.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as handle, temp.open("rb") as incoming:
            while chunk := incoming.read(1024 * 1024):
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        temp.unlink(missing_ok=True)
    return release


def extract(path: Path, destination: Path) -> dict:
    release, envelope, payload = _read_bundle(path)
    destination = Path(os.path.abspath(Path(destination).expanduser()))
    _no_links(destination)
    _need(not destination.exists() or (destination.is_dir() and not any(destination.iterdir())), "Extraction destination must be new or empty")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = [("release.json", identity.canonical(release) + b"\n", False),
               ("signature.json", identity.canonical(envelope) + b"\n", False)]
    records += [("payload/" + name, raw, executable) for name, (raw, executable) in payload.items()]
    for name, raw, executable in records:
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        _no_links(target)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o755 if executable else 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        if os.name != "nt":
            target.chmod(0o755 if executable else 0o644)
    return verify_directory(destination)


def verify_directory(destination: Path) -> dict:
    destination = Path(os.path.abspath(Path(destination).expanduser()))
    _no_links(destination)
    _need(destination.is_dir(), "Release directory is absent")
    release = _loads(_regular_bytes(destination / "release.json", MAX_METADATA_BYTES)[0])
    envelope = _loads(_regular_bytes(destination / "signature.json", MAX_METADATA_BYTES)[0])
    _metadata(release, envelope)
    files = {"release.json", "signature.json", *["payload/" + row["path"] for row in release["files"]]}
    directories = {"payload"}
    for name in files:
        parts = name.split("/")
        directories.update("/".join(parts[:i]) for i in range(1, len(parts)))
    seen_files, seen_dirs = set(), set()
    for path in destination.rglob("*"):
        relative = path.relative_to(destination).as_posix()
        _path(relative)
        _no_links(path)
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            seen_dirs.add(relative)
        else:
            _need(stat.S_ISREG(info.st_mode), "Extracted release contains a special file")
            seen_files.add(relative)
    _paths_unique(seen_files)
    _need(seen_files == files and seen_dirs == directories, "Extracted release inventory is not closed")
    payload = {}
    for row in release["files"]:
        raw, executable = _regular_bytes(destination / "payload" / row["path"])
        # Windows exposes no portable POSIX executable bit; its signed value is
        # retained while bytes and closed inventory remain independently checked.
        payload[row["path"]] = (raw, executable if os.name != "nt" else row["executable"])
    _verify_payload(release, payload)
    return release
