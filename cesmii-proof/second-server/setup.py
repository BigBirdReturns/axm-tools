#!/usr/bin/env python3
"""Install a pinned, unmodified CESMII demo server into an explicitly selected directory."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile

PIN = "9ffc352470b9807a0143cd5c43f9680cb5779550"
REPOSITORY = "https://github.com/cesmii/i3X.git"
HERE = Path(__file__).resolve().parent

def run(args, cwd):
    print(" ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", required=True, help="A NEW directory outside the downloaded source package.")
    p.add_argument("--port", type=int, default=8381)
    p.add_argument("--run", action="store_true", help="Start the server in this terminal after setup.")
    p.add_argument("--fetch-upstream", action="store_true", help="Fetch the pinned commit using Git instead of the bundled source archive.")
    args = p.parse_args()
    if not 1024 <= args.port <= 65535:
        p.error("Choose an unprivileged port from 1024 through 65535.")
    root = Path(args.work_dir).expanduser().resolve()
    if root.exists():
        p.error("The work directory already exists. Select a new directory to preserve earlier runs.")
    root.mkdir(parents=True)
    source = root / "i3X"
    manifest = json.loads((HERE / "upstream-source.json").read_text(encoding="utf-8"))
    if manifest.get("source_commit") != PIN:
        raise RuntimeError("Bundled source manifest differs from the published revision.")
    if args.fetch_upstream:
        run(["git", "init", str(source)], root)
        run(["git", "config", "core.autocrlf", "false"], source)
        run(["git", "remote", "add", "origin", REPOSITORY], source)
        run(["git", "fetch", "--depth", "1", "origin", PIN], source)
        run(["git", "checkout", "--detach", "FETCH_HEAD"], source)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        if head != PIN:
            raise RuntimeError("Upstream source revision differs from the published pin.")
    else:
        archive = HERE / "upstream-source.zip"
        if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
            raise RuntimeError("Bundled upstream source archive failed its integrity check.")
        source.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name, expected in manifest["files"].items():
                target = (source / name).resolve()
                if not target.is_relative_to(source):
                    raise RuntimeError("Unsafe bundled source path.")
                raw = z.read("i3X/" + name)
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise RuntimeError("Bundled upstream source bytes changed: " + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        head = PIN
    for name, expected in manifest["files"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Installed upstream source differs from its pinned bytes: " + name)
    env = root / "venv"
    run([sys.executable, "-m", "venv", str(env)], root)
    py = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    server = source / "demo/server"
    run([py, "-m", "pip", "install", "-r", server / "requirements.txt"], root)
    config = {
        "host": "127.0.0.1", "port": args.port, "debug": False,
        "app": {"title": "CESMII official demo server, AXM local verification",
                "description": "Unmodified upstream i3X 1.0 implementation; official simulated manufacturing data",
                "version": "1.0.0", "root_path": "/v1"},
        "data_source": {"type": "mock", "config": {}},
    }
    (server / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    files = {}
    for f in sorted(server.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            files[f.relative_to(source).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    command = [str(py), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(args.port)]
    provenance = {
        "schema": "axm-i3x-second-server-provenance/1",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_repository": REPOSITORY, "source_commit": head,
        "source_tree": "demo/server", "upstream_source_unmodified": True,
        "local_configuration_file": "demo/server/config.json", "config": config,
        "python_version": subprocess.check_output([str(py), "--version"], text=True).strip(),
        "file_sha256": files,
        "launch": "python -m uvicorn app:app --host 127.0.0.1 --port " + str(args.port),
        "launch_cwd": "i3X/demo/server",
        "base_url": "http://127.0.0.1:" + str(args.port) + "/v1",
        "data_classification": "CESMII upstream simulated demo data; no manufacturer data",
    }
    (root / "server-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (root / "requirements-resolved.txt").write_text(
        subprocess.check_output([str(py), "-m", "pip", "freeze"], text=True), encoding="utf-8"
    )
    print(json.dumps({"ready": True, "cwd": str(server), "command": command, "base_url": provenance["base_url"]}), flush=True)
    if args.run:
        run(command, server)
    else:
        print("Start from " + str(server))
        print(subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command))

if __name__ == "__main__":
    main()
