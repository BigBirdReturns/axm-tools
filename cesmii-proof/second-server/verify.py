#!/usr/bin/env python3
"""Reproduce the local official-server check and retain fresh, source-bound evidence."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
from urllib.parse import urlsplit

PIN = "9ffc352470b9807a0143cd5c43f9680cb5779550"
HERE = Path(__file__).resolve().parent
APP = HERE.parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--server-source", required=True, help="The pinned i3X checkout created by setup.py.")
    p.add_argument("--base-url", default="http://127.0.0.1:8381/v1")
    p.add_argument("--out", required=True, help="A NEW directory for fresh observations.")
    a = p.parse_args()
    if urlsplit(a.base_url).hostname not in ("127.0.0.1", "localhost", "::1"):
        p.error("This upstream conformance exercise is for your explicitly selected local demo server.")
    source = Path(a.server_source).resolve()
    manifest = json.loads((HERE / "upstream-source.json").read_text(encoding="utf-8"))
    head = manifest.get("source_commit")
    if head != PIN:
        p.error("The bundled source revision differs from the release pin.")
    if (source / ".git").exists():
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        if git_head != PIN:
            p.error("The server checkout differs from the release pin.")
    config = json.loads((source / "demo/server/config.json").read_text(encoding="utf-8"))
    if config.get("data_source", {}).get("type") != "mock":
        p.error("This reproduction requires the official simulated mock data source.")
    tracked = [f for f in manifest["files"] if f.startswith(("demo/server/", "conformance-tests/"))]
    mismatches = [f for f in tracked if not (source / f).is_file() or sha(source / f) != manifest["files"][f]]
    if mismatches:
        p.error("Runtime source differs from pinned Git bytes: " + ", ".join(mismatches[:8]))
    out = Path(a.out).expanduser().resolve()
    if out.exists():
        p.error("The evidence directory already exists. Select a new path to preserve earlier runs.")
    out.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location("axm_capture", APP / "capture.py")
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    label = "CESMII official simulated data on a separate local server instance"
    pump = collector.capture(a.base_url, evidence_label=label, production_data=False)
    tank = collector.capture(a.base_url, "tank-201", ["sensor-001"], None,
                             evidence_label=label, production_data=False)
    missing = collector.capture(a.base_url, "axm-missing-object", ["axm-missing-value"], None,
                                evidence_label=label, production_data=False)
    no_data = collector.capture(a.base_url, "tank-201", ["tank-201"], None,
                                evidence_label=label, production_data=False)
    save(out / "capture-no-value.json", no_data)
    save(out / "capture-local-pump.json", pump)
    save(out / "capture-local-tank.json", tank)
    save(out / "capture-missing-object.json", missing)
    command = ["node", str(source / "conformance-tests/bin/i3x-test.js"), "run",
               a.base_url, "--no-writes", "--timeout", "15000", "--json", str(out / "conformance-report.json")]
    suite = subprocess.run(command, cwd=source / "conformance-tests", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    (out / "conformance-output.txt").write_text((suite.stdout + suite.stderr).replace(str(out), ".").replace(str(source), "[upstream-source]"), encoding="utf-8")
    report = json.loads((out / "conformance-report.json").read_text(encoding="utf-8"))
    app_run = subprocess.run(
        ["node", str(HERE / "verify.cjs"), str(out)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90,
    )
    (out / "application-output.txt").write_text((app_run.stdout + app_run.stderr).replace(str(out), ".").replace(str(APP), "[application-source]"), encoding="utf-8")
    app_report = json.loads((out / "application-report.json").read_text(encoding="utf-8")) if (out / "application-report.json").exists() else {"status": "FAIL", "error": app_run.stderr or app_run.stdout}
    provenance = {
        "schema": "axm-i3x-second-server-provenance/1",
        "source_repository": "https://github.com/cesmii/i3X", "source_ref": "1.0", "source_commit": head,
        "tracked_server_and_suite_files_exact_git_blobs": True,
        "tracked_files_verified": len(tracked),
        "local_configuration_file": "demo/server/config.json", "config": config,
        "base_url": a.base_url,
        "launch": "python -m uvicorn app:app --host 127.0.0.1 --port " + str(config.get("port", 8381)),
        "launch_cwd": "i3X/demo/server", "data_classification": label,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "file_sha256": {f: sha(source / f) for f in tracked if (source / f).is_file()},
        "config_sha256": sha(source / "demo/server/config.json"),
    }
    save(out / "server-provenance.json", provenance)
    summary = report.get("summary", report)
    passed = suite.returncode == 0 and app_run.returncode == 0 and app_report.get("status") == "PASS"
    evidence = {
        "schema": "axm-i3x-second-server-evidence/1",
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "source_commit": head, "base_url": a.base_url,
        "official_suite": {"exit_code": suite.returncode, "summary": summary,
                           "current_value_writes_disabled": True,
                           "scope": "The pinned official suite exercised this local server; it creates/deletes test subscriptions and probes unsupported historical writes for HTTP 501."},
        "application": app_report,
        "files": {f.name: sha(f) for f in sorted(out.iterdir()) if f.is_file()},
        "limits": [
            "Separate deployment of CESMII's official implementation; not an independently authored vendor server.",
            "Official simulated manufacturing data; no member operational data or plant-control connection.",
            "A local self-run conformance result describes this server and configuration; CESMII has not certified AXM.",
        ],
    }
    save(out / "evidence.json", evidence)
    print(json.dumps({"status": evidence["status"], "official_suite": summary.get("counts"),
                      "application": app_report.get("checks"), "out": str(out)}))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
