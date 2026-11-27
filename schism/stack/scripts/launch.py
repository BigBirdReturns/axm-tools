#!/usr/bin/env python3
"""Create a private pinned runtime, then run the actual local console."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shlex
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", type=Path, help="Private runtime directory; defaults to a versioned user cache")
    parser.add_argument("--state", type=Path, default=Path.home() / ".schism")
    parser.add_argument("--port", type=int, default=8371)
    parser.add_argument("--wheelhouse", type=Path, help="Use a compatible downloaded offline wheelhouse")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--install-only", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("SCHISM requires Python 3.11 or newer")
    cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "axm-schism" / "0.1.1"
    environment = (args.environment or cache / "venv").expanduser().absolute()
    if environment.is_symlink():
        raise SystemExit("Refusing a symbolic-link runtime")
    marker = environment / "schism-runtime.json"
    if environment.exists() and not marker.exists() and any(environment.iterdir()):
        raise SystemExit("Select a new empty runtime directory or an existing SCHISM runtime")
    if not environment.exists() or not (environment / "pyvenv.cfg").exists():
        environment.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(environment)
        marker.write_text('{}\n', encoding="utf-8")
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lock = ROOT / "requirements.lock"
    if not lock.is_file():
        raise SystemExit("Release is missing its required dependency lockfile")
    fingerprint = hashlib.sha256(lock.read_bytes()).hexdigest()
    current = json.loads(marker.read_text(encoding="utf-8"))
    if current.get("lock_sha256") != fingerprint:
        command = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:", "--require-hashes", "-r", str(lock)]
        if args.wheelhouse:
            command += ["--no-index", "--find-links", str(args.wheelhouse.expanduser().absolute())]
        subprocess.run(command, check=True)
        marker.write_text(json.dumps({"version": "0.1.1", "lock_sha256": fingerprint}) + "\n", encoding="utf-8")
    print("Runtime ready: " + str(python), flush=True)
    state = args.state.expanduser().absolute()
    prefix = [str(python), str(ROOT / "schism.py"), "--state", str(state)]
    print(("Command line (cmd.exe): " + subprocess.list2cmdline(prefix)) if os.name == "nt" else ("Command line: " + shlex.join(prefix)), flush=True)
    if args.install_only:
        return 0
    command = [*prefix, "serve", "--port", str(args.port)]
    if not args.no_browser:
        command.append("--open")
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
