"""Command-line and detached worker entrypoints for SCHISM."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import time

from . import __version__, bundle
from .common import Refusal, canonical
from .engine import Engine, TERMINAL
from .evidence import backup_application, export_evidence, restore_application, verify_evidence
from .server import serve
from .transport import MAX_TRANSFER, add_peer, peer_request, remote_response, remove_peer


def output(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), flush=True)


def wait_job(engine, job_id, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = engine.job(job_id)
        if job["status"] in TERMINAL:
            return job
        time.sleep(0.15)
    return {"id": job_id, "status": "running", "wait_expired": True, "message": "The durable job continues; inspect it with job <id>"}


def parser():
    root = argparse.ArgumentParser(prog="schism", description="Operator-owned application deployment, execution and recovery")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--state", type=Path, default=Path(os.environ.get("SCHISM_STATE", str(Path.home() / ".schism"))))
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create or inspect a recipient's private state and signing identity")
    init.add_argument("--name", default="Local operator")
    console = commands.add_parser("serve", help="Open the local application console")
    console.add_argument("--port", type=int, default=8371)
    console.add_argument("--open", action="store_true")
    commands.add_parser("status", help="Inspect applications, releases, jobs and trust")
    commands.add_parser("identity", help="Print the public operator identity")
    pack = commands.add_parser("pack", help="Build a signed application from an explicit source folder")
    pack.add_argument("source", type=Path)
    pack.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect", help="Verify a package without execution or import")
    inspect.add_argument("package", type=Path)
    import_ = commands.add_parser("import", help="Verify and retain a package without execution")
    import_.add_argument("package", type=Path)
    trust = commands.add_parser("trust", help="Authorize a publisher for explicit application scopes")
    trust.add_argument("publisher", type=Path, help="A .schism package or public identity JSON")
    trust.add_argument("--app", action="append", required=True)
    trust.add_argument("--label")
    revoke = commands.add_parser("revoke", help="Refuse future executions from a publisher")
    revoke.add_argument("key_id")
    deploy = commands.add_parser("deploy", help="Activate an imported release after its acceptance check")
    deploy.add_argument("release_id")
    deploy.add_argument("--expect", type=int, required=True, help="Observed application generation; 0 for first deployment")
    deploy.add_argument("--detach", action="store_true")
    for name in ("start", "stop", "run", "rollback"):
        command = commands.add_parser(name)
        command.add_argument("app_id")
        command.add_argument("--expect", type=int, required=True)
        command.add_argument("--detach", action="store_true")
    recover = commands.add_parser("recover", help="Reconcile observed process state without replaying effects")
    recover.add_argument("app_id")
    cancel = commands.add_parser("cancel", help="Request cancellation of a durable job")
    cancel.add_argument("job_id")
    config = commands.add_parser("configure", help="Set private runtime environment values from a local JSON object")
    config.add_argument("app_id")
    config.add_argument("--environment", type=Path, required=True)
    job = commands.add_parser("job", help="Read retained status and output")
    job.add_argument("job_id")
    job.add_argument("--wait", action="store_true")
    job.add_argument("--timeout", type=float, default=600)
    export = commands.add_parser("export-evidence")
    export.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify-evidence")
    verify.add_argument("file", type=Path)
    verify.add_argument("--key-id")
    backup = commands.add_parser("backup", help="Export a stopped application's releases and persistent data")
    backup.add_argument("app_id")
    backup.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore", help="Import a pinned backup into an unused application id; execution remains stopped")
    restore.add_argument("file", type=Path)
    restore.add_argument("--key-id", required=True)
    node = commands.add_parser("node", help="Manage recipients through existing pinned SSH")
    node_commands = node.add_subparsers(dest="node_command", required=True)
    add = node_commands.add_parser("add")
    add.add_argument("name")
    add.add_argument("--host", required=True)
    add.add_argument("--python", required=True)
    add.add_argument("--root", required=True)
    add.add_argument("--remote-state", required=True)
    add.add_argument("--port", type=int, default=22)
    add.add_argument("--ssh-config", help="Optional existing local OpenSSH configuration")
    remove = node_commands.add_parser("remove")
    remove.add_argument("name")
    node_status = node_commands.add_parser("status")
    node_status.add_argument("name")
    node_import = node_commands.add_parser("import")
    node_import.add_argument("name")
    node_import.add_argument("package", type=Path)
    action = node_commands.add_parser("action")
    action.add_argument("name")
    action.add_argument("request", type=Path, help="Lifecycle request JSON; same contract as local API")
    node_job = node_commands.add_parser("job")
    node_job.add_argument("name")
    node_job.add_argument("job_id")
    # Internal process modes are explicit and remain usable in frozen executables.
    worker = commands.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("job_id")
    runner = commands.add_parser("_runner", help=argparse.SUPPRESS)
    runner.add_argument("run_id")
    commands.add_parser("_remote", help=argparse.SUPPRESS)
    return root


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    try:
        command = args.command
        if command == "inspect":
            output(bundle.inspect(args.package))
            return 0
        if command == "verify-evidence":
            output(verify_evidence(args.file, args.key_id))
            return 0
        engine = Engine(args.state, getattr(args, "name", "Local operator") if command == "init" else "Local operator")
        if command == "_worker":
            engine.execute(args.job_id)
            return 0
        if command == "_runner":
            from .runner import run
            return run(args.state, args.run_id)
        if command == "_remote":
            raw = sys.stdin.buffer.read(MAX_TRANSFER + 1)
            if len(raw) > MAX_TRANSFER:
                raise Refusal("Remote request exceeds supported size")
            output(remote_response(engine, json.loads(raw)))
            return 0
        if command in {"init", "identity"}:
            output(engine.store.identity)
        elif command == "serve":
            return serve(engine, args.port, args.open)
        elif command == "status":
            output(engine.snapshot())
        elif command == "pack":
            output(bundle.build(args.source, args.output, engine.root))
        elif command == "import":
            output(engine.import_package(args.package))
        elif command == "job":
            job = wait_job(engine, args.job_id, args.timeout) if args.wait else engine.job(args.job_id)
            output(job)
            return 0 if job["status"] in {"queued", "running", "succeeded"} else 1
        elif command == "export-evidence":
            output(export_evidence(engine, args.output))
        elif command == "backup":
            output(backup_application(engine, args.app_id, args.output))
        elif command == "restore":
            output(restore_application(engine, args.file, args.key_id))
        elif command == "node":
            if args.node_command == "add":
                specification = {"name": args.name, "host": args.host, "python": args.python, "root": args.root, "state": args.remote_state, "port": args.port}
                if args.ssh_config:
                    specification["ssh_config"] = args.ssh_config
                result = add_peer(engine, specification)
            elif args.node_command == "remove":
                result = remove_peer(engine, args.name)
            elif args.node_command == "status":
                result = peer_request(engine, args.name, {"operation": "state"})
            elif args.node_command == "job":
                result = peer_request(engine, args.name, {"operation": "job", "job_id": args.job_id})
            elif args.node_command == "import":
                bundle.inspect(args.package)
                result = peer_request(engine, args.name, {"operation": "import", "package": base64.b64encode(args.package.read_bytes()).decode("ascii")})
            else:
                result = peer_request(engine, args.name, {"operation": "action", "request": json.loads(args.request.read_text(encoding="utf-8"))})
            output(result)
        else:
            request = {"operation": command}
            if command == "trust":
                publisher = bundle.inspect(args.publisher)["publisher"] if args.publisher.suffix == ".schism" else json.loads(args.publisher.read_text(encoding="utf-8"))
                request.update(publisher=publisher, apps=args.app)
                if args.label:
                    request["label"] = args.label
            elif command == "revoke":
                request["key_id"] = args.key_id
            elif command == "deploy":
                request.update(release_id=args.release_id, expected_generation=args.expect)
            elif command in {"start", "stop", "run", "rollback"}:
                request.update(app_id=args.app_id, expected_generation=args.expect)
            elif command == "recover":
                request["app_id"] = args.app_id
            elif command == "cancel":
                request["job_id"] = args.job_id
            elif command == "configure":
                request.update(app_id=args.app_id, environment=json.loads(args.environment.read_text(encoding="utf-8")))
            receipt = engine.submit(request)
            if getattr(args, "detach", False):
                output(receipt)
            else:
                job = wait_job(engine, receipt["job_id"])
                output(job)
                return 0 if job["status"] == "succeeded" else 1
        return 0
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
