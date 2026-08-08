#!/usr/bin/env python3
"""Execute the exact AP-410 Kit v2 source qualification denominator."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
from typing import Any

EXPECTED_SOURCE_SHA = "71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74"
EXPECTED_SOURCE_BYTES = 90028
EXPECTED_NODE = "v22.16.0"
EXPECTED_PROGRESS_ID = "uiprogress2_6073d7e2855ec35fece231f86e0cc0aa94ed9499d1b7a44d7fdbd5d1f2837cf2"
EXPECTED_KIT_ID = "g3observationkit2_6a0784236b71e0c78d22a6087aa837764eadddee17cc58e9522e909358eda9a1"
EXPECTED_QUALIFICATION_ID = "g3observationqualification2_14f759a2212a9119e6d9f0ae81e0e7f9a5937ceddcbe1e2b00864e51380bd4ec"

def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def refuse(message: str) -> None:
    raise SystemExit(f"REFUSED: {message}")

def run(command: list[str], cwd: pathlib.Path, log: pathlib.Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        refuse(f"command failed ({result.returncode}): {' '.join(command)}")
    return result.stdout

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--work-root", type=pathlib.Path, required=True)
    parser.add_argument("--runner-label", default=os.environ.get("RUNNER_OS", "local"))
    args = parser.parse_args()

    data_root = args.data_root.resolve()
    work = args.work_root.resolve()
    if work.exists():
        shutil.rmtree(work)
    (work / "extract").mkdir(parents=True)
    (work / "logs").mkdir(parents=True)
    archive = work / "AXM-Aperture-G3-Platform-Observation-Kit-v2.tar.gz"
    verification = work / "dispatch-verification.json"

    run(
        [sys.executable, str(data_root / "scripts" / "verify_dispatch_data.py"),
         "--data-root", str(data_root), "--output", str(archive), "--receipt", str(verification)],
        data_root,
        work / "logs" / "dispatch-verification.log",
    )
    if archive.stat().st_size != EXPECTED_SOURCE_BYTES or digest(archive) != EXPECTED_SOURCE_SHA:
        refuse("reconstructed source identity drift")

    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(work / "extract", filter="data")
    roots = [path for path in (work / "extract").iterdir() if path.is_dir()]
    if len(roots) != 1:
        refuse("expected one extracted source root")
    source_root = roots[0]
    (work / "source-root.txt").write_text(str(source_root) + "\n", encoding="utf-8")

    node_version = run(["node", "--version"], source_root, work / "logs" / "node-version.log").strip()
    if node_version != EXPECTED_NODE:
        refuse(f"node version mismatch: {node_version}")
    (work / "node-version.txt").write_text(node_version + "\n", encoding="utf-8")

    inventory = []
    for path in sorted(p for p in source_root.rglob("*") if p.is_file()):
        inventory.append(f"{digest(path)}  {path.relative_to(source_root).as_posix()}")
    (work / "source-inventory.sha256").write_text("\n".join(inventory) + "\n", encoding="utf-8")

    tests = sorted(str(path.relative_to(source_root)) for path in (source_root / "tests").glob("*.test.mjs"))
    contract_output = run(["node", "--test", *tests], source_root, work / "logs" / "contracts.log")
    if "# tests 49" not in contract_output or "# pass 49" not in contract_output or "# fail 0" not in contract_output:
        refuse("49-contract denominator not reproduced")

    verify_output = run(["node", "scripts/verify-package.mjs"], source_root, work / "logs" / "verify-package.log")
    if "PACKAGE_VERIFIED" not in verify_output:
        refuse("package verification marker absent")

    progress_output = run(["node", "scripts/compile-progress.mjs"], source_root, work / "logs" / "compile-progress.log").strip()
    try:
        progress = json.loads(progress_output.splitlines()[-1])
    except Exception as exc:
        refuse(f"compile-progress output is not JSON: {exc}")
    required = {
        "progressId": EXPECTED_PROGRESS_ID,
        "runtimeBindingVerified": False,
        "observedInteractions": 0,
        "observedVisuals": 0,
        "observedReaderGroups": 0,
        "status": "BLOCKED",
        "sourceCompilerAccepted": False,
        "canonicalAp410Accepted": False,
        "canonicalG3Accepted": False,
        "hostedRepositoryAccepted": False,
        "waivers": [],
    }
    for key, expected in required.items():
        if progress.get(key) != expected:
            refuse(f"progress field drift at {key}: {progress.get(key)!r}")
    if progress.get("reasonCodes") != ["runtime_binding_missing"]:
        refuse("runtime_binding_missing is not the sole reason code")

    blocked_text = json.dumps(progress, sort_keys=True, separators=(",", ":")) + "\n"
    (work / "blocked-progress.json").write_text(blocked_text, encoding="utf-8")
    qualification = {
        "format": "axm-aperture-g3-observation-kit-v2-hosted-qualification/1",
        "runner_label": args.runner_label,
        "source_archive": {"bytes": archive.stat().st_size, "sha256": digest(archive)},
        "kit_id": EXPECTED_KIT_ID,
        "qualification_id": EXPECTED_QUALIFICATION_ID,
        "blocked_progress_id": EXPECTED_PROGRESS_ID,
        "node_version": node_version,
        "contracts": {"passed": 49, "failed": 0},
        "package_verified": True,
        "runtime_binding_present": False,
        "observed_platform_interactions": 0,
        "observed_platform_visuals": 0,
        "manual_reader_groups_passed": 0,
        "canonical_ap410_accepted": False,
        "canonical_g3_accepted": False,
        "hosted_repository_accepted": False,
        "accepted_gates": [],
        "status": "PASS",
    }
    core = json.dumps(qualification, sort_keys=True, separators=(",", ":")).encode()
    qualification["qualification_receipt_sha256"] = hashlib.sha256(core).hexdigest()
    (work / "qualification.json").write_text(json.dumps(qualification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (work / "qualification.env").write_text(
        "\n".join([
            f"archive_sha256={digest(archive)}",
            f"archive_bytes={archive.stat().st_size}",
            f"kit={EXPECTED_KIT_ID}",
            f"qualification={EXPECTED_QUALIFICATION_ID}",
            f"blocked_progress={EXPECTED_PROGRESS_ID}",
            "contracts=49",
            "status=PASS",
            f"runner_label={args.runner_label}",
        ]) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(qualification, sort_keys=True))

if __name__ == "__main__":
    main()
