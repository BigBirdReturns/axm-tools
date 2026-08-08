#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
from typing import Any

ARCHIVE_NAME = "AXM-Aperture-G3-Platform-Observation-Kit-v2.tar.gz"
ENVELOPE_NAME = ARCHIVE_NAME + ".b64"
ENVELOPE_SHA256 = "237b9d98dafed780c35fbfa5b1d8a0b20e3c724556f2473bc14dc9d60c59a313"
ENVELOPE_BYTES = 120040
ARCHIVE_SHA256 = "71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74"
ARCHIVE_BYTES = 90028
SOURCE_EVIDENCE_COMMIT = "54a13c6212e18b3a191448ff28452d0f9cf1b6c0"
KIT_ID = "g3observationkit2_6a0784236b71e0c78d22a6087aa837764eadddee17cc58e9522e909358eda9a1"
QUALIFICATION_ID = "g3observationqualification2_14f759a2212a9119e6d9f0ae81e0e7f9a5937ceddcbe1e2b00864e51380bd4ec"
PROGRESS_ID = "uiprogress2_6073d7e2855ec35fece231f86e0cc0aa94ed9499d1b7a44d7fdbd5d1f2837cf2"
SOURCE_MATRIX_SHA256 = "aef281d81fae08bf350e700948405f98d49a770442a323189b16c9b9f005f657"
SOURCE_MANIFEST_SHA256 = "014a5d9f0dc8803484333c7deb7dadc89f38f96667c69d8fc72699923f3ae6ca"
PACKAGE_MANIFEST_SHA256 = "87218d601ff0d4f7d577d6c5bf476b2dbd073a7176d192cba24f3745c28030b7"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def verify_node() -> None:
    version = subprocess.check_output(["node", "--version"], text=True).strip()
    if version != "v22.16.0":
        raise SystemExit(f"Node version mismatch: {version}")


def safe_extract(archive: pathlib.Path, destination: pathlib.Path) -> pathlib.Path:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination.resolve()
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            if member.issym() or member.islnk() or member.isdev():
                raise SystemExit(f"unsafe tar member: {member.name}")
            resolved = (destination / member.name).resolve()
            if resolved != target and target not in resolved.parents:
                raise SystemExit(f"archive path escape: {member.name}")
        bundle.extractall(destination, filter="data")
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1 or roots[0].name != "AXM-Aperture-G3-Platform-Observation-Kit-v2":
        raise SystemExit(f"unexpected source roots: {[path.name for path in roots]}")
    return roots[0]


def decode_envelope(envelope: pathlib.Path, output: pathlib.Path) -> pathlib.Path:
    encoded = envelope.read_bytes()
    if len(encoded) != ENVELOPE_BYTES or sha256_bytes(encoded) != ENVELOPE_SHA256:
        raise SystemExit("source envelope identity mismatch")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"source envelope decode failure: {exc}") from exc
    if len(raw) != ARCHIVE_BYTES or sha256_bytes(raw) != ARCHIVE_SHA256:
        raise SystemExit("decoded source archive identity mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    with tarfile.open(output, "r:gz") as bundle:
        bundle.getmembers()
    return output


def verify_manifest(root: pathlib.Path, manifest_name: str) -> None:
    manifest = root / manifest_name
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise SystemExit(f"invalid manifest row {manifest_name}:{line_number}") from exc
        if not HEX64.fullmatch(digest.lower()):
            raise SystemExit(f"invalid manifest digest {manifest_name}:{line_number}")
        relative = relative.removeprefix("./")
        path = (root / relative).resolve()
        resolved_root = root.resolve()
        if path != resolved_root and resolved_root not in path.parents:
            raise SystemExit(f"manifest path escape: {relative}")
        if not path.is_file() or sha256_file(path) != digest.lower():
            raise SystemExit(f"manifest mismatch: {manifest_name}:{relative}")


def tree_digest(root: pathlib.Path) -> str:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n")
    return sha256_bytes("".join(rows).encode("utf-8"))


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def execute_source(root: pathlib.Path) -> dict[str, Any]:
    verify_node()
    if any(path.name.lower() == "runtime_binding.json" for path in root.rglob("*")):
        raise SystemExit("clean source unexpectedly contains RUNTIME_BINDING.json")

    verify_manifest(root, "SOURCE_MANIFEST.sha256")
    verify_manifest(root, "PACKAGE_MANIFEST.sha256")
    if sha256_file(root / "SOURCE_MANIFEST.sha256") != SOURCE_MANIFEST_SHA256:
        raise SystemExit("source manifest identity mismatch")
    if sha256_file(root / "PACKAGE_MANIFEST.sha256") != PACKAGE_MANIFEST_SHA256:
        raise SystemExit("package manifest identity mismatch")

    tests = sorted((root / "tests").glob("*.test.mjs"))
    if not tests:
        raise SystemExit("no Kit tests found")
    test_result = run(["node", "--test", *[str(path) for path in tests]], root)
    transcript = test_result.stdout + test_result.stderr
    if not re.search(r"(?:#\s*)?tests\s+49\b", transcript):
        raise SystemExit("49-test denominator absent")
    if not re.search(r"(?:#\s*)?pass\s+49\b", transcript):
        raise SystemExit("49-pass denominator absent")
    if not re.search(r"(?:#\s*)?fail\s+0\b", transcript):
        raise SystemExit("zero-failure denominator absent")

    run(["node", "scripts/verify-package.mjs"], root)
    run(["node", "scripts/compile-progress.mjs"], root)

    kit = load(root / "receipts/KIT.json")
    qualification = load(root / "qualification/RESULT.json")
    progress = load(root / "qualification/PROGRESS.json")
    checks = {
        "kit_id": (kit.get("kitId"), KIT_ID),
        "qualification_id": (qualification.get("qualificationId"), QUALIFICATION_ID),
        "progress_id": (progress.get("progressId"), PROGRESS_ID),
        "progress_status": (progress.get("status"), "BLOCKED"),
        "reason_codes": (progress.get("reasonCodes"), ["runtime_binding_missing"]),
        "runtime_binding_verified": (progress.get("runtimeBindingVerified"), False),
        "observed_interactions": (progress.get("observedInteractions"), 0),
        "observed_visuals": (progress.get("observedVisuals"), 0),
        "observed_reader_groups": (progress.get("observedReaderGroups"), 0),
        "canonical_ap410": (progress.get("canonicalAp410Accepted"), False),
        "canonical_g3": (progress.get("canonicalG3Accepted"), False),
        "source_matrix": (kit.get("sourceMatrixSha256"), SOURCE_MATRIX_SHA256),
        "tests": (qualification.get("tests"), 49),
        "passed": (qualification.get("passed"), 49),
        "failed": (qualification.get("failed"), 0),
    }
    failures = {
        name: {"observed": observed, "expected": expected}
        for name, (observed, expected) in checks.items()
        if observed != expected
    }
    if failures:
        raise SystemExit(json.dumps({"identity_failures": failures}, indent=2))
    return {
        "kit_id": KIT_ID,
        "qualification_id": QUALIFICATION_ID,
        "progress_id": PROGRESS_ID,
        "progress_status": "BLOCKED",
        "reason_codes": ["runtime_binding_missing"],
        "tests": 49,
        "passed": 49,
        "failed": 0,
        "source_tree_sha256": tree_digest(root),
        "runtime_binding_present": False,
        "observed_interactions": 0,
        "observed_visuals": 0,
        "observed_reader_groups": 0,
        "accepted_gates": [],
        "canonical_ap410_accepted": False,
        "canonical_g3_accepted": False,
        "hosted_repository_accepted": False,
    }


def from_envelope(envelope: pathlib.Path, work: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    archive = decode_envelope(envelope, work / ARCHIVE_NAME)
    root = safe_extract(archive, work / "source")
    return archive, root


def from_archive(archive: pathlib.Path, work: pathlib.Path) -> pathlib.Path:
    if archive.stat().st_size != ARCHIVE_BYTES or sha256_file(archive) != ARCHIVE_SHA256:
        raise SystemExit("artifact source archive identity mismatch")
    return safe_extract(archive, work / "source")


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--source-envelope", required=True)
    matrix.add_argument("--work", required=True)
    matrix.add_argument("--result", required=True)
    cold = sub.add_parser("cold")
    cold.add_argument("--source-envelope", required=True)
    cold.add_argument("--work", required=True)
    cold.add_argument("--artifact", required=True)
    replay = sub.add_parser("replay")
    replay.add_argument("--archive", required=True)
    replay.add_argument("--work", required=True)
    replay.add_argument("--result", required=True)
    args = parser.parse_args()

    work = pathlib.Path(args.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    if args.mode == "matrix":
        archive, root = from_envelope(pathlib.Path(args.source_envelope).resolve(), work)
        result = execute_source(root)
        result.update({
            "runner_os": os.environ.get("RUNNER_OS", sys.platform),
            "source_evidence_commit": SOURCE_EVIDENCE_COMMIT,
            "source_envelope_sha256": ENVELOPE_SHA256,
            "source_archive_sha256": sha256_file(archive),
        })
        write_json(pathlib.Path(args.result).resolve(), result)
        print(json.dumps(result, sort_keys=True))
        return

    if args.mode == "replay":
        root = from_archive(pathlib.Path(args.archive).resolve(), work)
        result = execute_source(root)
        result.update({
            "runner_os": os.environ.get("RUNNER_OS", sys.platform),
            "source_evidence_commit": SOURCE_EVIDENCE_COMMIT,
            "source_archive_sha256": ARCHIVE_SHA256,
            "artifact_replay": True,
        })
        write_json(pathlib.Path(args.result).resolve(), result)
        print(json.dumps(result, sort_keys=True))
        return

    artifact = pathlib.Path(args.artifact).resolve()
    artifact.mkdir(parents=True, exist_ok=True)
    envelope = pathlib.Path(args.source_envelope).resolve()
    archive_a, root_a = from_envelope(envelope, work / "a")
    archive_b, root_b = from_envelope(envelope, work / "b")
    result_a = execute_source(root_a)
    result_b = execute_source(root_b)
    if archive_a.read_bytes() != archive_b.read_bytes():
        raise SystemExit("cold archive bytes differ")
    if result_a != result_b:
        raise SystemExit("cold source results differ")

    shutil.copy2(archive_a, artifact / ARCHIVE_NAME)
    shutil.copy2(envelope, artifact / ENVELOPE_NAME)
    write_json(artifact / "COLD_A.json", result_a)
    write_json(artifact / "COLD_B.json", result_b)
    core = {
        "format": "axm-aperture-observation-kit-v2-hosted-source-receipt/1",
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "candidate_head": os.environ.get("GITHUB_SHA", ""),
        "source_evidence_commit": SOURCE_EVIDENCE_COMMIT,
        "source_custody_receipt": "ap410kitsourcecustody2_f1dd528c5b6c3858157ea629d96174b6f7ca612eb4feb1e084a21d7e1dbd26a6",
        "source_envelope_sha256": ENVELOPE_SHA256,
        "source_envelope_bytes": ENVELOPE_BYTES,
        "source_archive_sha256": ARCHIVE_SHA256,
        "source_archive_bytes": ARCHIVE_BYTES,
        "source_tree_sha256": result_a["source_tree_sha256"],
        "kit_id": KIT_ID,
        "qualification_id": QUALIFICATION_ID,
        "progress_id": PROGRESS_ID,
        "contract_runs": 2,
        "contracts_per_run": 49,
        "runtime_binding_present": False,
        "observed_interactions": 0,
        "observed_visuals": 0,
        "observed_reader_groups": 0,
        "accepted_gates": [],
        "canonical_ap410_accepted": False,
        "canonical_g3_accepted": False,
        "hosted_repository_accepted": False,
        "authority": "hosted_source_portability_only",
        "waivers": [],
    }
    receipt = {"receipt_id": content_id("ap410kithostedsource1_", core), **core}
    write_json(artifact / "HOSTED_SOURCE_RECEIPT.json", receipt)
    files = sorted(path for path in artifact.iterdir() if path.is_file())
    (artifact / "SHA256SUMS").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in files),
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
