#!/usr/bin/env python3
"""Supervise one explicitly selected SCHISM service under an OS service manager.

An explicit unit start (including boot) starts the selected service. An operator
stop ends that supervision session. Tasks are never run. Shutdown is bound to
the adopted release, generation and run, including replacements within a release.

Controller contract: SCHISM 0.1.1. Atomic shutdown uses that version's Engine
submit/execute, _generation and app-lock semantics. Its normal durable stop job,
events and process bookkeeping remain authoritative; no database rows are edited
here. The worker-dispatch adapter supplies the additional run-identity guard
that the 0.1.1 CLI's generation-only stop option cannot express. Other controller
versions fail closed pending qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

CONTROLLER_VERSION = "0.1.1"
GUARDED_STOP_CONTRACT = "research-studio-owned-service-stop@1"
REPLACED = "Supervisor ownership changed; selected replacement left untouched"
ACTIVE_TRANSITIONS = {"start", "stop", "deploy", "rollback", "recover"}
TERMINAL_JOBS = {"succeeded", "failed", "cancelled", "interrupted"}


def selected(snapshot, app_id):
    if snapshot.get("version") != CONTROLLER_VERSION:
        raise RuntimeError(f"Qualified controller version required: {CONTROLLER_VERSION}")
    app = next((item for item in snapshot["applications"] if item["id"] == app_id), None)
    if app is None or app.get("kind") != "service":
        raise RuntimeError("Supervisor requires an already deployed service application")
    return app


def ownership(app):
    return {key: app.get(key) for key in ("release_id", "generation", "run_id")}


class LifecycleMonitor:
    """Interpret snapshots without mistaking process exit for operator intent."""

    def __init__(self, snapshot, app_id):
        self.app_id = app_id
        app = selected(snapshot, app_id)
        self.adopted = ownership(app)
        if not self.adopted["run_id"]:
            raise RuntimeError("Running service lacks a selected run identity")
        self.run_started = datetime.fromisoformat(app["process"]["started_at"].replace("Z", "+00:00"))
        # Snapshot reads app/process before jobs. A stop may complete between
        # those reads, so exclude only stop jobs older than this selected run.
        self.old_stops = {
            job["id"] for job in snapshot.get("jobs", [])
            if job.get("app_id") == app_id and job.get("operation") == "stop"
            and job.get("status") == "succeeded"
            and (not job.get("ended_at") or datetime.fromisoformat(
                job["ended_at"].replace("Z", "+00:00")) < self.run_started)
        }
        self.completed_stops = set()
        self.transition_since = None

    def observe(self, snapshot, transition_timeout=120):
        app = selected(snapshot, self.app_id)
        if ownership(app) != self.adopted:
            return "replacement-selected", app
        jobs = [job for job in snapshot.get("jobs", []) if job.get("app_id") == self.app_id]
        for job in jobs:
            result = job.get("result") or {}
            if (job.get("operation") == "stop" and job.get("status") == "succeeded"
                    and job["id"] not in self.old_stops
                    and job.get("ended_at") and datetime.fromisoformat(
                        job["ended_at"].replace("Z", "+00:00")) >= self.run_started
                    and result.get("app_id") == self.app_id and result.get("status") == "stopped"):
                self.completed_stops.add(job["id"])
        if app["status"] == "running":
            self.transition_since = None
            return "running", app
        active = [job for job in jobs if job.get("operation") in ACTIVE_TRANSITIONS
                  and job.get("status") in {"queued", "running"}]
        if active:
            # Deploy/rollback stop the old run before accepting a new one. The
            # app snapshot can also lead the stop job's final success commit.
            self.transition_since = self.transition_since or time.monotonic()
            if time.monotonic() - self.transition_since > transition_timeout:
                raise RuntimeError("Application lifecycle transition did not settle")
            return "lifecycle-transition", app
        if app["status"] == "stopped" and self.completed_stops:
            return "operator-stopped", app
        raise RuntimeError(f"Service left running state without a completed operator stop: {app['status']}")


def load_engine(controller):
    controller = Path(controller).resolve(strict=True)
    sys.path.insert(0, str(controller.parent))
    package = importlib.import_module("schism_stack")
    module = importlib.import_module("schism_stack.engine")
    if (package.__version__ != CONTROLLER_VERSION
            or Path(module.__file__).resolve().parent.parent != controller.parent):
        raise RuntimeError("Qualified SCHISM controller version and source path required")
    return module


def guarded_engine_class(base):
    class GuardedStopEngine(base):
        def __init__(self, state, expected):
            super().__init__(state)
            self.expected = expected

        def _generation(self, app_id, expected_generation):
            # Engine.execute invokes this inside its ordinary app-scoped lock.
            # Start/stop do not advance generation, so run_id is mandatory.
            app = self.store.app(app_id, required=False)
            if app is None or ownership(app) != self.expected:
                raise RuntimeError(REPLACED)
            checked = super()._generation(app_id, expected_generation)
            release = self.store.release(checked["release_id"])
            if release["application"]["kind"] != "service":
                raise RuntimeError("Guarded shutdown refuses task applications")
            return checked
    return GuardedStopEngine


def guarded_worker(args):
    module = load_engine(args.controller)
    initial = module.Engine(args.state)
    job = initial.store.job(args.guarded_stop_worker)
    request = json.loads(job["request"])
    if (request.get("operation") != "stop" or request.get("app_id") != args.app
            or request.get("supervisor_contract") != GUARDED_STOP_CONTRACT):
        raise RuntimeError("Guarded worker requires its exact service-stop request")
    expected = request["expected_ownership"]
    if set(expected) != {"release_id", "generation", "run_id"} or not expected["run_id"]:
        raise RuntimeError("Guarded worker requires complete adopted identity")
    engine = guarded_engine_class(module.Engine)(args.state, expected)
    engine.execute(args.guarded_stop_worker)
    return 0


def guarded_stop(args, expected):
    module = load_engine(args.controller)
    engine = module.Engine(args.state)
    ordinary_command = module.controller_command

    def worker_command(*arguments):
        # Only this stop's normal detached lifecycle worker is redirected.
        if len(arguments) == 4 and arguments[0] == "--state" and arguments[2] == "_worker":
            return [sys.executable, str(Path(__file__).resolve()),
                    "--controller", str(Path(args.controller).resolve()),
                    "--state", str(Path(args.state).resolve()), "--app", args.app,
                    "--guarded-stop-worker", str(arguments[3])]
        raise RuntimeError("Unexpected controller worker-dispatch contract")

    try:
        module.controller_command = worker_command
        receipt = engine.submit({"operation": "stop", "app_id": args.app,
            "expected_generation": expected["generation"], "expected_ownership": expected,
            "supervisor_contract": GUARDED_STOP_CONTRACT})
    finally:
        module.controller_command = ordinary_command
    deadline = time.monotonic() + 28
    while time.monotonic() < deadline:
        job = engine.job(receipt["job_id"])
        if job["status"] in TERMINAL_JOBS:
            if job["status"] == "succeeded":
                return {"event": "supervision-stopped", "app": args.app, "job_id": job["id"]}
            if job.get("error") == REPLACED:
                return {"event": "replacement-left-running", "app": args.app, "job_id": job["id"]}
            raise RuntimeError(f"Guarded stop {job['id']} {job['status']}: {job.get('error')}")
        time.sleep(0.1)
    raise RuntimeError(f"Guarded stop remains unresolved; inspect retained job {receipt['job_id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--guarded-stop-worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.guarded_stop_worker:
        return guarded_worker(args)
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())

    def call(*arguments, timeout=8):
        command = [sys.executable, str(args.controller), "--state", str(args.state), *map(str, arguments)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout or f"Controller exit {result.returncode}")
        return json.loads(result.stdout)

    try:
        snapshot = call("status")
        app = selected(snapshot, args.app)
        if app["status"] != "running":
            # Explicit service-manager activation authorizes this service start.
            call("recover", args.app, timeout=10)
            app = selected(call("status"), args.app)
            call("start", args.app, "--expect", app["generation"], timeout=35)
            snapshot = call("status")
            app = selected(snapshot, args.app)
        if app["status"] != "running":
            raise RuntimeError("Service did not reach running state")
        monitor = LifecycleMonitor(snapshot, args.app)
        print(json.dumps({"event": "supervision-started", "app": args.app,
                          "state": str(args.state), **monitor.adopted,
                          "process": app.get("process")}), flush=True)
        while not stopped.wait(3):
            outcome, app = monitor.observe(call("status"))
            if outcome in {"operator-stopped", "replacement-selected"}:
                print(json.dumps({"event": outcome, "app": args.app,
                                  "adopted": monitor.adopted, "selected": ownership(app)}), flush=True)
                return 0
        print(json.dumps(guarded_stop(args, monitor.adopted)), flush=True)
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"event": "supervision-failed", "app": args.app, "error": str(error)}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
