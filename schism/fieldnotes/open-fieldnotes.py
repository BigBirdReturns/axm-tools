#!/usr/bin/env python3
"""Install or open Fieldnotes through the unmodified SCHISM public command line."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
APP = "fieldnotes"


def controller(path, state, runtime, wheelhouse):
    path = path.expanduser().resolve()
    if path.is_dir() and (path / "schism.py").is_file():
        if (path / "SOURCE-MANIFEST.json").is_file():
            subprocess.run([sys.executable, str(path / "scripts" / "verify_source.py")], cwd=path, check=True)
        command = [sys.executable, str(path / "scripts" / "launch.py"), "--environment", str(runtime), "--state", str(state), "--install-only"]
        if wheelhouse:
            command.extend(["--wheelhouse", str(wheelhouse.expanduser().resolve())])
        print("Preparing SCHISM's hash-locked source runtime.", flush=True)
        subprocess.run(command, cwd=path, check=True)
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        return [str(python), str(path / "schism.py"), "--state", str(state)]
    if path.is_dir():
        path = path / ("schism.exe" if os.name == "nt" else "schism")
    if not path.is_file() or path.suffix == ".py":
        raise ValueError("Pass the complete extracted SCHISM source folder, native distribution folder, or native executable.")
    print("Using the native SCHISM controller. Fieldnotes requires Python 3.11+ on PATH.", flush=True)
    return [str(path), "--state", str(state)]


def call(prefix, *args):
    print("SCHISM " + " ".join(str(part) for part in args), flush=True)
    result = subprocess.run([*prefix, *(str(part) for part in args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "SCHISM command failed")
    value = json.loads(result.stdout)
    if "status" in value and value["status"] != "succeeded" and "operation" in value:
        raise RuntimeError(value.get("error") or "The operation did not succeed.")
    return value


def selected(prefix):
    return next((app for app in call(prefix, "status")["applications"] if app["id"] == APP), None)


def private_url(state, app):
    run_id = app.get("run_id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise RuntimeError("The selected application has no current run.")
    connection = json.loads((state / "work" / APP / run_id / "fieldnotes-open.json").read_text(encoding="utf-8"))
    token = connection.get("token", "")
    if connection.get("application") != APP or connection.get("port") != 8787 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise RuntimeError("The current Fieldnotes private link has an unexpected format.")
    request = urllib.request.Request("http://127.0.0.1:8787/api/notebook", headers={"Authorization": "Bearer " + token})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        notebook = json.load(response)
    if notebook.get("application") != APP or notebook.get("version") != app["version"]:
        raise RuntimeError("The live notebook differs from the selected application.")
    return "http://127.0.0.1:8787/#token=" + token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schism", type=Path, required=True, help="Complete extracted SCHISM 0.1.1 source/native folder, or native executable")
    parser.add_argument("--state", type=Path, default=Path.home() / ".schism", help="Existing or new private operator state")
    cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "axm-fieldnotes" / "schism-0.1.1" / "venv"
    parser.add_argument("--runtime", type=Path, default=cache, help="Private runtime used only with the source controller")
    parser.add_argument("--wheelhouse", type=Path, help="Optional compatible offline SCHISM dependency directory")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--app-version", choices=("1.0.0", "1.1.0"), help="Explicitly package and select this app version; first install defaults to 1.1.0")
    choice.add_argument("--rollback", action="store_true", help="Restore the prior code version while retaining current notes")
    choice.add_argument("--stop", action="store_true", help="Stop Fieldnotes without deleting notes")
    parser.add_argument("--no-browser", action="store_true", help="Print the private link without opening a browser")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Fieldnotes requires Python 3.11 or newer.")
    state = args.state.expanduser().resolve()
    runtime = args.runtime.expanduser().resolve()
    prefix = controller(args.schism, state, runtime, args.wheelhouse)
    probe = subprocess.run([*prefix, "--version"], capture_output=True, text=True, encoding="utf-8", check=True)
    if probe.stdout.strip() != "0.1.1":
        raise ValueError("This Fieldnotes release is qualified with SCHISM 0.1.1; select that controller.")
    if os.name == "nt":
        print("PowerShell command prefix: & " + " ".join("'" + part.replace("'", "''") + "'" for part in prefix), flush=True)
    else:
        print("Shell command prefix: " + shlex.join(prefix), flush=True)
    identity = call(prefix, "identity")
    print("Operator: " + identity["key_id"], flush=True)
    app = selected(prefix)
    if args.stop:
        if app:
            call(prefix, "stop", APP, "--expect", app["generation"])
        print("Fieldnotes is stopped. Its notes remain in " + str(state / "data" / APP), flush=True)
        return 0
    if args.rollback:
        if not app:
            raise ValueError("Install Fieldnotes before restoring a prior version.")
        call(prefix, "rollback", APP, "--expect", app["generation"])
    elif not app or args.app_version:
        version = args.app_version or "1.1.0"
        source = ROOT / "versions" / version
        print("Packing the included Fieldnotes " + version + " source with YOUR operator identity. No publisher trust grants are added.", flush=True)
        with tempfile.TemporaryDirectory(prefix="fieldnotes-package-") as temp:
            package = Path(temp) / "fieldnotes.schism"
            call(prefix, "pack", source, "--output", package)
            imported = call(prefix, "import", package)
            call(prefix, "deploy", imported["release_id"], "--expect", app["generation"] if app else 0)
    elif app["status"] != "running":
        call(prefix, "start", APP, "--expect", app["generation"])
    app = selected(prefix)
    url = private_url(state, app)
    print("\nFieldnotes " + app["version"] + " is running.\nNotes: " + app["data_path"] + "\nPrivate link: " + url, flush=True)
    print("Keep this link private. After an update or restart, run this launcher again. Closing the browser leaves the service running.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print("Fieldnotes: " + str(error), file=sys.stderr)
        raise SystemExit(1)
