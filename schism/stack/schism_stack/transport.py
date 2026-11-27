"""Optional remote recipients over the operator's existing pinned OpenSSH."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

from . import identity
from .common import Refusal, canonical, digest, now, validate_id

MAX_TRANSFER = 96 * 1024 * 1024


def _exchange(specification, request):
    host = specification.get("host")
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:%-]{0,250}", host):
        raise Refusal("Use a configured SSH alias or user@host")
    port = specification.get("port", 22)
    if type(port) is not int or not 1 <= port <= 65535:
        raise Refusal("SSH port must be 1..65535")
    python = specification.get("python", "python3")
    root, state = specification.get("root"), specification.get("state")
    if not all(isinstance(x, str) and x and "\0" not in x for x in (python, root, state)):
        raise Refusal("A remote interpreter, installed source root and state root are required")
    bootstrap = "import sys;sys.path.insert(0," + repr(root) + ");from schism_stack.cli import main;raise SystemExit(main(" + repr(["--state", state, "_remote"]) + "))"
    remote_command = shlex.join([python, "-c", bootstrap])
    command = ["ssh"]
    if specification.get("ssh_config"):
        configuration = Path(specification["ssh_config"]).expanduser().absolute()
        if not configuration.is_file():
            raise Refusal("Declared local SSH configuration does not exist")
        command.extend(["-F", str(configuration)])
    command.extend(["-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", "-p", str(port), host, remote_command])
    environment = dict(os.environ)
    if os.name == "nt":
        # Windows sshd's inherited descriptor map describes its original pipes.
        # Passing it to a new ssh process after replacing stdin can strand input.
        inherited = {"shell", "c28fc6f98a2c44abbbd89d6a3037d0d9_posix_fd_state"}
        environment = {key: value for key, value in environment.items() if key.casefold() not in inherited}
    encoded = canonical(request)
    if len(encoded) > MAX_TRANSFER:
        raise Refusal("SSH request exceeds the transfer bound")
    completed = subprocess.run(command, input=encoded, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=environment)
    if completed.returncode != 0:
        raise Refusal("SSH recipient refused the request: " + completed.stderr.decode("utf-8", errors="replace")[-4000:])
    if len(completed.stdout) > MAX_TRANSFER:
        raise Refusal("SSH reply exceeds the supported size")
    try:
        envelope = json.loads(completed.stdout)
        payload = identity.verify(envelope, "schism.remote/v1", specification.get("key_id"))
    except Exception as exc:
        raise Refusal("Remote response failed identity verification: " + str(exc)) from exc
    if payload.get("request_sha256") != digest(request):
        raise Refusal("Remote response belongs to a different request")
    if payload.get("error"):
        raise Refusal("Recipient: " + str(payload["error"]))
    return envelope, payload["reply"]


def add_peer(engine, specification):
    name = validate_id(specification.get("name"), "Node name")
    if engine.store.one("SELECT name FROM peers WHERE name=?", (name,)):
        raise Refusal("Node name already exists; remove it explicitly before enrolling a replacement")
    specification = {key: specification[key] for key in ("name", "host", "python", "root", "state", "port", "ssh_config") if key in specification}
    envelope, reply = _exchange(specification, {"operation": "identity", "nonce": os.urandom(16).hex()})
    if envelope["key_id"] != reply["identity"]["key_id"]:
        raise Refusal("Remote identity and response signer disagree")
    specification.update({"key_id": envelope["key_id"], "identity": reply["identity"], "enrolled_at": now(), "transport": "ssh-posix"})
    with engine.store.db() as con:
        con.execute("INSERT INTO peers VALUES(?,?)", (name, canonical(specification).decode()))
    engine.store.event("node.enrolled", {"name": name, "key_id": envelope["key_id"], "host": specification["host"], "authority": "existing pinned SSH account"})
    return specification


def remove_peer(engine, name):
    with engine.store.db() as con:
        if not con.execute("DELETE FROM peers WHERE name=?", (name,)).rowcount:
            raise Refusal("Unknown node")
    engine.store.event("node.removed", {"name": name})
    return {"name": name, "removed": True}


def peer_request(engine, name, request):
    row = engine.store.one("SELECT specification FROM peers WHERE name=?", (name,))
    if not row:
        raise Refusal("Node has not been enrolled")
    specification = json.loads(row["specification"])
    request = dict(request, nonce=os.urandom(16).hex(), recipient_key_id=specification["key_id"])
    _, reply = _exchange(specification, request)
    engine.store.event("node.requested", {"name": name, "operation": request.get("operation"), "request_sha256": digest(request)})
    return reply


def remote_response(engine, request):
    try:
        operation = request.get("operation")
        if operation != "identity" and request.get("recipient_key_id") != engine.store.identity["key_id"]:
            raise Refusal("Recipient identity does not match the enrolled operator key")
        if operation == "identity":
            reply = {"identity": engine.store.identity}
        elif operation == "state":
            reply = engine.snapshot()
        elif operation == "action":
            reply = engine.submit(request["request"])
        elif operation == "job":
            reply = engine.job(request["job_id"])
        elif operation == "import":
            raw = base64.b64decode(request["package"], validate=True)
            if len(raw) > 64 * 1024 * 1024:
                raise Refusal("Remote package exceeds the 64 MiB transfer bound")
            fd, name = tempfile.mkstemp(suffix=".schism", dir=engine.root / "incoming")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
                reply = engine.import_package(name)
            finally:
                Path(name).unlink(missing_ok=True)
        else:
            raise Refusal("Unsupported remote operation")
        payload = {"request_sha256": digest(request), "reply": reply, "error": None}
    except Exception as exc:
        payload = {"request_sha256": digest(request), "reply": None, "error": str(exc)}
    return identity.sign(engine.root, payload, "schism.remote/v1")
