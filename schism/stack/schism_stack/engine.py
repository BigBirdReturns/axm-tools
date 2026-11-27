"""General application admission, durable execution and recovery transitions."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import uuid

import psutil

from . import __version__, bundle, identity
from .common import (Cancelled, Refusal, atomic_json, canonical, controller_command,
                     detached, digest, now, private_root, process_alive,
                     process_identity, read_json, stop_owned, validate_id)
from .store import Store

OPERATIONS = {"trust", "revoke", "deploy", "start", "stop", "run", "rollback", "recover", "cancel", "configure"}
TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}


class Engine:
    def __init__(self, state, name="Local operator"):
        self.store = Store(state, name)
        self.root = self.store.root

    def import_package(self, path):
        metadata = bundle.inspect(Path(path))
        release_id = metadata["release_id"]
        with self.store.lock("package-import"):
            destination = self.root / "releases" / release_id
            if destination.exists():
                verified = bundle.verify_directory(destination)
                if verified != metadata:
                    raise Refusal("Existing content identity disagrees with imported package")
            else:
                staging = self.root / "incoming" / ("stage-" + uuid.uuid4().hex)
                try:
                    bundle.extract(Path(path), staging)
                    os.replace(staging, destination)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            package_path = self.root / "packages" / (release_id + ".schism")
            if not package_path.exists():
                temp = self.root / "incoming" / (uuid.uuid4().hex + ".schism")
                shutil.copyfile(path, temp)
                # Bind the retained package, rather than trusting a mutable caller path.
                if bundle.inspect(temp) != metadata:
                    temp.unlink()
                    raise Refusal("Package changed while importing")
                os.replace(temp, package_path)
            with self.store.db() as con:
                con.execute("INSERT OR IGNORE INTO releases VALUES(?,?,?,?)", (release_id, canonical(metadata).decode(), str(destination), now()))
            self.store.event("release.imported", {"release_id": release_id, "app_id": metadata["application"]["id"], "publisher": metadata["publisher"]["key_id"]})
        return dict(metadata, trusted=self.store.trusted(metadata))

    def submit(self, request):
        if not isinstance(request, dict) or request.get("operation") not in OPERATIONS:
            raise Refusal("Unknown lifecycle operation")
        request = dict(request)
        request_id = request.pop("request_id", None) or uuid.uuid4().hex
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,100}", request_id):
            raise Refusal("Request id must contain 8 to 100 portable identifier characters")
        fingerprint = digest(request)
        job_id = uuid.uuid4().hex
        app_id = request.get("app_id")
        if app_id is not None:
            validate_id(app_id)
        if request["operation"] == "deploy":
            app_id = self.store.release(request.get("release_id"))["application"]["id"]
        with self.store.db() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT id,fingerprint FROM jobs WHERE request_id=?", (request_id,)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise Refusal("Request id already belongs to different input")
                return {"job_id": old["id"], "reused": True}
            con.execute("INSERT INTO jobs(id,request_id,fingerprint,request,operation,app_id,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        (job_id, request_id, fingerprint, canonical(request).decode(), request["operation"], app_id, "queued", now()))
        self.store.event("operation.requested", {"job_id": job_id, "request_id": request_id, "operation": request["operation"], "app_id": app_id, "request_sha256": fingerprint})
        log_path = self.root / "logs" / ("worker-" + job_id + ".log")
        try:
            with log_path.open("ab") as log:
                child = detached(controller_command("--state", self.root, "_worker", job_id), log)
            created = process_identity(child.pid)["created"]
            with self.store.db() as con:
                con.execute("UPDATE jobs SET worker_pid=?,worker_created=? WHERE id=? AND worker_pid IS NULL", (child.pid, created, job_id))
        except BaseException as error:
            with self.store.db() as con:
                con.execute("UPDATE jobs SET status='interrupted',error=?,ended_at=? WHERE id=? AND status='queued'", (str(error), now(), job_id))
            raise
        return {"job_id": job_id, "reused": False}

    def cancelled(self, job_id):
        return bool(self.store.job(job_id)["cancel"])

    def checkpoint(self, job_id):
        if self.cancelled(job_id):
            raise Cancelled("Operation cancelled")

    def execute(self, job_id):
        with self.store.db() as con:
            updated = con.execute("UPDATE jobs SET status='running',worker_pid=?,worker_created=?,started_at=? WHERE id=? AND status='queued'", (os.getpid(), psutil.Process().create_time(), now(), job_id)).rowcount
        if not updated:
            return
        job = self.store.job(job_id)
        request = json.loads(job["request"])
        operation = request["operation"]
        status, result, error = "succeeded", None, None
        try:
            self.checkpoint(job_id)
            if operation in {"trust", "revoke", "cancel", "configure"}:
                result = self._administrative(request)
            else:
                app_id = job["app_id"]
                if not app_id:
                    raise Refusal("Application id is required")
                with self.store.lock("app:" + app_id, lambda: self.cancelled(job_id)):
                    self.checkpoint(job_id)
                    if operation == "deploy":
                        result = self._deploy(app_id, request["release_id"], request.get("expected_generation"), job_id)
                    elif operation == "rollback":
                        app = self.store.app(app_id)
                        if not app["previous_release_id"]:
                            raise Refusal("Application has no retained prior release")
                        result = self._deploy(app_id, app["previous_release_id"], request.get("expected_generation"), job_id, rollback=True)
                    elif operation == "start":
                        result = self._start(app_id, request.get("expected_generation"), job_id)
                    elif operation == "stop":
                        app = self._generation(app_id, request.get("expected_generation"))
                        self._stop_app(app)
                        self.store.event("application.stopped", {"app_id": app_id, "generation": app["generation"]})
                        result = {"app_id": app_id, "status": "stopped"}
                    elif operation == "run":
                        result = self._task(app_id, request.get("expected_generation"), job_id)
                    elif operation == "recover":
                        result = self._recover(app_id)
        except Cancelled as exc:
            status, error = "cancelled", str(exc)
        except BaseException as exc:
            status, error = "failed", str(exc)
        with self.store.db() as con:
            con.execute("UPDATE jobs SET status=?,result=?,error=?,ended_at=? WHERE id=?", (status, canonical(result).decode() if result is not None else None, error, now(), job_id))
        self.store.event("operation." + status, {"job_id": job_id, "operation": operation, "app_id": job["app_id"], "result": result, "error": error})

    def _administrative(self, request):
        operation = request["operation"]
        if operation == "trust":
            publisher = request.get("publisher", {})
            raw = identity.validate_descriptor(publisher)
            key_id = identity.key_id(raw)
            if len(raw) != 32 or publisher.get("key_id") != key_id:
                raise Refusal("Publisher fingerprint does not match its Ed25519 public key")
            apps = request.get("apps")
            if not isinstance(apps, list) or not apps or len(apps) > 100:
                raise Refusal("Select explicit application scopes")
            for app_id in apps:
                if app_id != "*":
                    validate_id(app_id)
            label = str(request.get("label") or publisher.get("name") or key_id)[:180]
            with self.store.db() as con:
                con.execute("INSERT OR REPLACE INTO trust VALUES(?,?,?,?,0)", (key_id, canonical(publisher).decode(), canonical(sorted(set(apps))).decode(), label))
            self.store.event("publisher.authorized", {"key_id": key_id, "apps": apps, "label": label})
            return {"key_id": key_id, "apps": apps}
        if operation == "revoke":
            key_id = request.get("key_id")
            with self.store.db() as con:
                if not con.execute("UPDATE trust SET revoked=1 WHERE key_id=?", (key_id,)).rowcount:
                    raise Refusal("Publisher is not registered")
            self.store.event("publisher.revoked", {"key_id": key_id})
            return {"key_id": key_id, "revoked": True, "running_processes_unchanged": True}
        if operation == "cancel":
            target = self.store.job(request.get("job_id"))
            with self.store.db() as con:
                con.execute("UPDATE jobs SET cancel=1 WHERE id=? AND status IN ('queued','running')", (target["id"],))
            return {"job_id": target["id"], "cancel_requested": target["status"] not in TERMINAL}
        if operation == "configure":
            app_id = validate_id(request.get("app_id"))
            environment = request.get("environment")
            if not isinstance(environment, dict) or len(environment) > 100:
                raise Refusal("Environment must be an object with at most 100 values")
            if any(not isinstance(key, str) for key in environment) or len({key.casefold() for key in environment}) != len(environment):
                raise Refusal("Environment names must be unique across case-insensitive recipients")
            for key, value in environment.items():
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", key) or key.upper().startswith("SCHISM_") or not isinstance(value, str) or "\0" in value or len(value) > 32768:
                    raise Refusal("Environment names and values must be valid process strings")
            atomic_json(self.root / "config" / (app_id + ".json"), {"environment": environment})
            self.store.event("application.configured", {"app_id": app_id, "environment_names": sorted(environment)})
            return {"app_id": app_id, "environment_names": sorted(environment), "applies_on_next_start": True}
        raise Refusal("Unsupported administrative operation")

    def _generation(self, app_id, expected):
        app = self.store.app(app_id, required=False)
        actual = app["generation"] if app else 0
        if type(expected) is not int or expected != actual:
            raise Refusal(f"Application generation changed: expected {expected!r}, observed {actual}; refresh before applying")
        return app

    def _verified(self, release_id):
        metadata = self.store.release(release_id)
        self.store.check_trust(metadata)
        observed = bundle.verify_directory(self.root / "releases" / release_id)
        if observed != metadata:
            raise Refusal("Retained release metadata differs from verified package")
        return metadata

    def _deploy(self, app_id, release_id, expected, job_id, rollback=False):
        old = self._generation(app_id, expected)
        metadata = self._verified(release_id)
        application = metadata["application"]
        if application["id"] != app_id:
            raise Refusal("Release belongs to another application")
        if old and old["release_id"] == release_id:
            return {"app_id": app_id, "release_id": release_id, "generation": old["generation"], "unchanged": True}
        if old and old["data_schema"] != application.get("data_schema", "1"):
            raise Refusal("Persistent data schema differs; export data and perform an explicit migration before changing schema")
        data_root = self.root / "data" / app_id
        bundle._no_links(data_root)
        contract = self.store.one("SELECT data_schema FROM data_contracts WHERE app_id=?", (app_id,))
        data_schema = application.get("data_schema", "1")
        if contract and contract["data_schema"] != data_schema:
            raise Refusal("Retained application data has a different schema, including data from an unselected candidate")
        if not contract:
            if data_root.exists() and any(data_root.iterdir()):
                raise Refusal("Existing application data has no recorded schema; migrate it into an explicitly staged recipient")
            with self.store.db() as con:
                con.execute("BEGIN IMMEDIATE")
                con.execute("INSERT INTO data_contracts VALUES(?,?)", (app_id, data_schema))
                self.store.event("data.contract-bound", {"app_id": app_id, "data_schema": data_schema}, connection=con)
        old_running = bool(old and self._running(old))
        private_root(data_root)
        self.store.event("activation.prepared", {"app_id": app_id, "candidate": release_id, "previous": old["release_id"] if old else None, "expected_generation": expected, "rollback": rollback})
        if old:
            self._stop_app(old)
        run_id = None
        try:
            self.checkpoint(job_id)
            if application["kind"] == "service":
                run_id = self._spawn(app_id, release_id, "service", job_id)
                self._health(run_id, application, job_id)
            self.checkpoint(job_id)
            # Re-check revocation and bytes immediately before the activation commit.
            self._verified(release_id)
            with self.store.db() as con:
                con.execute("BEGIN IMMEDIATE")
                current = con.execute("SELECT generation FROM apps WHERE id=?", (app_id,)).fetchone()
                if (current["generation"] if current else 0) != expected:
                    raise Refusal("Concurrent activation changed the expected generation")
                con.execute("INSERT OR REPLACE INTO apps VALUES(?,?,?,?,?,?,?,?)", (app_id, release_id, old["release_id"] if old else None, expected + 1, "running" if run_id else "ready", run_id, application.get("data_schema", "1"), None))
                self.store.event("release.activated", {"app_id": app_id, "release_id": release_id, "generation": expected + 1, "previous_release_id": old["release_id"] if old else None, "rollback": rollback}, connection=con)
            return {"app_id": app_id, "release_id": release_id, "generation": expected + 1, "status": "running" if run_id else "ready"}
        except BaseException as error:
            if run_id:
                self._stop_run(run_id)
            recovery = "previous release remains selected"
            if old and old_running:
                previous_run = None
                try:
                    prior = self._verified(old["release_id"])
                    previous_run = self._spawn(app_id, old["release_id"], "service", job_id)
                    self._health(previous_run, prior["application"], None)
                    with self.store.db() as con:
                        con.execute("UPDATE apps SET status='running',run_id=?,last_error=? WHERE id=?", (previous_run, str(error), app_id))
                    recovery = "previous release restarted"
                except BaseException as recovery_error:
                    if previous_run:
                        self._stop_run(previous_run)
                    with self.store.db() as con:
                        con.execute("UPDATE apps SET status='interrupted',last_error=? WHERE id=?", (f"Candidate: {error}; recovery: {recovery_error}", app_id))
                    recovery = "previous release restart failed: " + str(recovery_error)
            elif old:
                with self.store.db() as con:
                    con.execute("UPDATE apps SET status=?,last_error=? WHERE id=?", ("ready" if self.store.release(old["release_id"])["application"]["kind"] == "task" else "stopped", str(error), app_id))
            self.store.event("activation.refused", {"app_id": app_id, "candidate": release_id, "error": str(error), "recovery": recovery, "data_restored": False})
            raise type(error)(str(error) + "; " + recovery) from error

    def _spawn(self, app_id, release_id, kind, job_id):
        run_id = uuid.uuid4().hex
        private_root(self.root / "work" / app_id / run_id)
        with self.store.db() as con:
            con.execute("INSERT INTO runs(id,app_id,release_id,kind,job_id,status,created_at) VALUES(?,?,?,?,?,'starting',?)", (run_id, app_id, release_id, kind, job_id, now()))
        with (self.root / "logs" / ("runner-" + run_id + ".log")).open("ab") as log:
            process = detached(controller_command("--state", self.root, "_runner", run_id), log)
        with self.store.db() as con:
            con.execute("UPDATE runs SET launcher_pid=?,launcher_created=? WHERE id=? AND launcher_pid IS NULL", (process.pid, process_identity(process.pid)["created"], run_id))
        return run_id

    def _running(self, app):
        if not app or not app["run_id"]:
            return False
        row = self.store.one("SELECT * FROM runs WHERE id=?", (app["run_id"],))
        return bool(row and process_alive(row["pid"], row["process_created"]))

    def _health(self, run_id, application, job_id):
        health = application.get("health") or {"type": "process", "grace": 1, "timeout": 10}
        timeout = float(health.get("timeout", 10))
        deadline = time.monotonic() + timeout
        live_since = None
        last = "Process has not started"
        while time.monotonic() < deadline:
            if job_id:
                self.checkpoint(job_id)
            row = self.store.one("SELECT * FROM runs WHERE id=?", (run_id,))
            if row["status"] in {"exited", "failed", "stopped"}:
                raise Refusal("Candidate exited before acceptance: " + str(row["error"] or row["exit_code"]))
            if process_alive(row["pid"], row["process_created"]):
                if live_since is None:
                    live_since = time.monotonic()
                if health["type"] == "process":
                    if time.monotonic() - live_since >= float(health.get("grace", 1)):
                        return
                elif health["type"] == "http":
                    try:
                        # No proxy use and no redirects: health stays on the declared loopback endpoint.
                        class NoRedirect(urllib.request.HTTPRedirectHandler):
                            def redirect_request(self, *args, **kwargs):
                                return None
                        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
                        with opener.open(health["url"], timeout=min(1, max(0.1, deadline - time.monotonic()))) as response:
                            if response.status == int(health.get("status", 200)):
                                # Bind endpoint acceptance to the candidate's process tree.
                                # Another process answering the same port cannot admit it.
                                target = urlsplit(health["url"])
                                port = target.port or 80
                                target_address = ipaddress.ip_address(target.hostname)
                                candidate = psutil.Process(row["pid"])
                                owned = [candidate, *candidate.children(recursive=True)]
                                def matches(connection):
                                    if connection.status != psutil.CONN_LISTEN or connection.laddr.port != port:
                                        return False
                                    address = ipaddress.ip_address(connection.laddr.ip.split("%", 1)[0])
                                    return address.version == target_address.version and (address == target_address or address.is_unspecified)
                                listening = any(matches(connection) for process in owned for connection in process.net_connections(kind="inet"))
                                if listening and process_alive(row["pid"], row["process_created"]):
                                    return
                                last = "Declared endpoint is not owned by the candidate process tree"
                                time.sleep(0.1)
                                continue
                            last = "HTTP status " + str(response.status)
                    except Exception as exc:
                        last = str(exc)
            else:
                live_since = None
            time.sleep(0.1)
        raise Refusal("Candidate health did not pass within its declared timeout: " + last)

    def _stop_run(self, run_id):
        row = self.store.one("SELECT * FROM runs WHERE id=?", (run_id,))
        if not row:
            return
        metadata = self.store.release(row["release_id"])
        timeout = float(metadata["application"].get("stop_timeout", 5))
        stop_owned(row["pid"], row["process_created"], timeout)
        # A runner observing a known child gets a bounded opportunity to retain
        # its exit and close SQLite before forced wrapper termination.
        runner_finished = False
        if row["pid"] and process_alive(row["runner_pid"], row["runner_created"]):
            try:
                observer = psutil.Process(row["runner_pid"])
                if abs(observer.create_time() - float(row["runner_created"])) < 0.01:
                    observer.wait(timeout=1)
                runner_finished = True
            except psutil.NoSuchProcess:
                runner_finished = True
            except psutil.TimeoutExpired:
                pass
        # Handle cancellation while the wrapper is still preparing the child.
        if not runner_finished:
            stop_owned(row["runner_pid"], row["runner_created"], 1)
        stop_owned(row.get("launcher_pid"), row.get("launcher_created"), 1)
        with self.store.db() as con:
            con.execute("UPDATE runs SET status='stopped',ended_at=COALESCE(ended_at,?) WHERE id=? AND status IN ('starting','running')", (now(), run_id))

    def _stop_app(self, app):
        if app["run_id"]:
            self._stop_run(app["run_id"])
        with self.store.db() as con:
            con.execute("UPDATE apps SET status='stopped' WHERE id=?", (app["id"],))

    def _start(self, app_id, expected, job_id):
        app = self._generation(app_id, expected)
        if not app:
            raise Refusal("Application must be deployed before starting")
        metadata = self._verified(app["release_id"])
        if metadata["application"]["kind"] != "service":
            raise Refusal("Task applications use Run")
        if self._running(app):
            return {"app_id": app_id, "status": "running", "unchanged": True}
        run_id = self._spawn(app_id, app["release_id"], "service", job_id)
        try:
            self._health(run_id, metadata["application"], job_id)
            with self.store.db() as con:
                con.execute("UPDATE apps SET status='running',run_id=?,last_error=NULL WHERE id=?", (run_id, app_id))
            self.store.event("application.started", {"app_id": app_id, "release_id": app["release_id"], "run_id": run_id})
            return {"app_id": app_id, "status": "running", "run_id": run_id}
        except BaseException:
            self._stop_run(run_id)
            raise

    def _task(self, app_id, expected, job_id):
        app = self._generation(app_id, expected)
        if not app:
            raise Refusal("Application must be deployed before running")
        metadata = self._verified(app["release_id"])
        if metadata["application"]["kind"] != "task":
            raise Refusal("Service applications use Start")
        if self._running(app):
            raise Refusal("A run already owns this application's data")
        run_id = self._spawn(app_id, app["release_id"], "task", job_id)
        with self.store.db() as con:
            con.execute("UPDATE apps SET status='running',run_id=?,last_error=NULL WHERE id=?", (run_id, app_id))
        deadline = time.monotonic() + float(metadata["application"].get("task_timeout", 300))
        try:
            while True:
                self.checkpoint(job_id)
                run = self.store.one("SELECT * FROM runs WHERE id=?", (run_id,))
                if run["status"] in {"exited", "failed", "stopped"}:
                    if run["exit_code"] != 0:
                        raise Refusal("Task failed: " + str(run["error"] or ("exit " + str(run["exit_code"]))))
                    return {"app_id": app_id, "run_id": run_id, "exit_code": 0, "data_path": str(self.root / "data" / app_id)}
                if time.monotonic() >= deadline:
                    raise Refusal("Task exceeded its declared timeout")
                if run["runner_pid"] and not process_alive(run["runner_pid"], run["runner_created"]):
                    raise Refusal("Task wrapper disappeared; outcome requires recovery and will not be replayed")
                if not run["runner_pid"] and run.get("launcher_pid") and not process_alive(run["launcher_pid"], run["launcher_created"]):
                    raise Refusal("Task launcher exited before the wrapper claimed execution; inspect its retained log")
                time.sleep(0.1)
        finally:
            run = self.store.one("SELECT * FROM runs WHERE id=?", (run_id,))
            if run["status"] in {"starting", "running"}:
                self._stop_run(run_id)
            with self.store.db() as con:
                con.execute("UPDATE apps SET status='ready' WHERE id=?", (app_id,))

    def _recover(self, app_id):
        app = self.store.app(app_id, required=False)
        if not app:
            held = []
            for row in self.store.all("SELECT * FROM runs WHERE app_id=? AND status IN ('starting','running')", (app_id,)):
                self._stop_run(row["id"])
                held.append(row["id"])
            result = {"app_id": app_id, "status": "unselected", "generation": 0, "uncommitted_runs_stopped": held, "automatic_replay": False}
            self.store.event("application.recovered", result)
            return result
        metadata = bundle.verify_directory(self.root / "releases" / app["release_id"])
        if metadata != self.store.release(app["release_id"]):
            raise Refusal("Selected release failed integrity verification")
        selected_run = app["run_id"]
        held = []
        for row in self.store.all("SELECT * FROM runs WHERE app_id=? AND status IN ('starting','running')", (app_id,)):
            if row["id"] != selected_run:
                # An uncommitted candidate is never promoted during recovery.
                self._stop_run(row["id"])
                held.append(row["id"])
        status = "running" if self._running(app) else ("ready" if metadata["application"]["kind"] == "task" else "stopped")
        with self.store.db() as con:
            con.execute("UPDATE apps SET status=? WHERE id=?", (status, app_id))
        result = {"app_id": app_id, "status": status, "generation": app["generation"], "uncommitted_runs_stopped": held, "automatic_replay": False}
        self.store.event("application.recovered", result)
        return result

    def reconcile(self):
        from datetime import datetime, timezone
        for row in self.store.all("SELECT * FROM jobs WHERE status IN ('queued','running')"):
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))).total_seconds()
            if age < 5 or process_alive(row["worker_pid"], row["worker_created"]):
                continue
            if not row["worker_pid"] and age < 30:
                continue
            with self.store.db() as con:
                changed = con.execute("UPDATE jobs SET status='interrupted',error=?,ended_at=? WHERE id=? AND status IN ('queued','running')", ("Worker disappeared; inspect application state before any new request. Automatic replay is disabled.", now(), row["id"])).rowcount
            if changed:
                self.store.event("operation.interrupted", {"job_id": row["id"], "app_id": row["app_id"], "automatic_replay": False})

    def job(self, job_id):
        self.reconcile()
        row = self.store.job(job_id)
        row.pop("request", None)
        runs = self.store.all("SELECT * FROM runs WHERE job_id=? ORDER BY created_at", (job_id,))
        pieces = []
        for run in runs:
            for name in (run["id"] + ".log", "runner-" + run["id"] + ".log"):
                path = self.root / "logs" / name
                if path.exists():
                    with path.open("rb") as handle:
                        handle.seek(max(0, path.stat().st_size - 65536))
                        pieces.append(handle.read(65536).decode("utf-8", errors="replace"))
        row["log"] = "\n".join(pieces)[-131072:]
        row["runs"] = runs
        return row

    def snapshot(self):
        self.reconcile()
        apps = []
        for app in self.store.all("SELECT * FROM apps ORDER BY id"):
            metadata = self.store.release(app["release_id"])
            document = metadata["application"]
            run = self.store.one("SELECT * FROM runs WHERE id=?", (app["run_id"],)) if app["run_id"] else None
            alive = bool(run and process_alive(run["pid"], run["process_created"]))
            status = app["status"]
            if status == "running" and not alive:
                status = "interrupted" if run and run["status"] in {"starting", "running"} else ("ready" if document["kind"] == "task" else "stopped")
            config_path = self.root / "config" / (app["id"] + ".json")
            configured = sorted(read_json(config_path).get("environment", {})) if config_path.exists() else []
            apps.append(dict(app, name=document.get("name", app["id"]), kind=document["kind"], version=document["version"], status=status,
                             process={"pid": run["pid"], "started_at": run["created_at"]} if alive else None,
                             data_path=str(self.root / "data" / app["id"]), configured_environment=configured,
                             trusted=self.store.trusted(metadata)))
        releases = [dict(json.loads(row["metadata"]), trusted=self.store.trusted(json.loads(row["metadata"]))) for row in self.store.all("SELECT metadata FROM releases ORDER BY imported_at DESC")]
        jobs = self.store.all("SELECT id,operation,app_id,status,created_at,ended_at,result,error FROM jobs ORDER BY created_at DESC LIMIT 100")
        for job in jobs:
            job["result"] = json.loads(job["result"]) if job["result"] else None
        events = [identity.verify(json.loads(row["envelope"]), "schism.event/v1", self.store.identity["key_id"]) for row in self.store.all("SELECT envelope FROM events ORDER BY sequence DESC LIMIT 100")]
        trust = [{"key_id": row["key_id"], "publisher": json.loads(row["publisher"]), "apps": json.loads(row["apps"]), "label": row["label"], "revoked": bool(row["revoked"])} for row in self.store.all("SELECT * FROM trust ORDER BY label")]
        peers = [json.loads(row["specification"]) for row in self.store.all("SELECT specification FROM peers ORDER BY name")]
        return {"version": __version__, "identity": self.store.identity, "platform": platform.system(), "state_root": str(self.root), "applications": apps, "releases": releases, "jobs": jobs, "events": events, "trust": trust, "peers": peers}
