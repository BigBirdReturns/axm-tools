#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import lzma
import os
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "manzanita/v31-continuation-payload-independent-verification@1"
ROOT_SUFFIX = PurePosixPath("manzanita-next/review/mw-habitat-live-photo-030-continuation")
EXPECTED = {
    "base64": {"bytes": 65868, "sha256": "80cd3ebdde0157c32efd0d4359ea70070a5aec975cd96f4654314ce9cf87b4ec"},
    "xz": {"bytes": 49400, "sha256": "853c65f996fb666745e6835b20944436e28a665fa5be63b0730e0afd151a318e"},
    "tar": {"bytes": 348160, "sha256": "911ee957181292cf33c1e3816245d2236dde6eff716dbc64818bbed3bfa1bae2"},
    "tar_members": 39,
    "source_manifest": {"bytes": 6984, "sha256": "14d8eaf0809b76fd7019b3d334c03e2bf671d1ec2724b54962c62aeabaa87e0c"},
    "source_files": 38,
    "source_bytes": 305245,
    "harness_checks": 202,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_posix(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and "\\" not in name and all(part not in ("", ".", "..") for part in p.parts)


def add(checks: list[dict[str, Any]], name: str, passed: bool, actual: Any, expected: Any) -> None:
    checks.append({"name": name, "pass": bool(passed), "actual": actual, "expected": expected})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    recovery = args.recovery_dir.resolve()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    receipt_path = recovery / "V31_CONTINUATION_PAYLOAD_RECOVERY_RECEIPT.json"
    add(checks, "recovery receipt present", receipt_path.is_file(), str(receipt_path), "regular file")
    receipt: dict[str, Any] = {}
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            add(checks, "recovery receipt classification", receipt.get("classification") == "EXACT_CONTINUATION_SOURCE_PAYLOAD_RECOVERED", receipt.get("classification"), "EXACT_CONTINUATION_SOURCE_PAYLOAD_RECOVERED")
            add(checks, "recovery receipt result", receipt.get("result") == "PASS", receipt.get("result"), "PASS")
        except Exception as exc:
            errors.append(f"receipt parse failed: {exc}")

    b64_path = recovery / "SOURCE_PAYLOAD.recovered.b64"
    b64_raw = b64_path.read_bytes() if b64_path.is_file() else b""
    b64_payload = b64_raw.rstrip(b"\r\n")
    add(checks, "recovered Base64 file present", b64_path.is_file(), str(b64_path), "regular file")
    add(checks, "Base64 bytes", len(b64_payload) == EXPECTED["base64"]["bytes"], len(b64_payload), EXPECTED["base64"]["bytes"])
    add(checks, "Base64 SHA-256", sha256(b64_payload) == EXPECTED["base64"]["sha256"], sha256(b64_payload), EXPECTED["base64"]["sha256"])

    xz_bytes = b""
    tar_bytes = b""
    try:
        xz_bytes = base64.b64decode(b64_payload, validate=True)
        add(checks, "Base64 strict decode", True, "valid", "valid RFC 4648 Base64")
    except Exception as exc:
        errors.append(f"Base64 decode failed: {exc}")
        add(checks, "Base64 strict decode", False, str(exc), "valid RFC 4648 Base64")

    add(checks, "XZ bytes", len(xz_bytes) == EXPECTED["xz"]["bytes"], len(xz_bytes), EXPECTED["xz"]["bytes"])
    add(checks, "XZ SHA-256", sha256(xz_bytes) == EXPECTED["xz"]["sha256"], sha256(xz_bytes), EXPECTED["xz"]["sha256"])
    try:
        tar_bytes = lzma.decompress(xz_bytes)
        add(checks, "XZ decompression", True, "valid", "valid XZ stream")
    except Exception as exc:
        errors.append(f"XZ decompression failed: {exc}")
        add(checks, "XZ decompression", False, str(exc), "valid XZ stream")

    add(checks, "tar bytes", len(tar_bytes) == EXPECTED["tar"]["bytes"], len(tar_bytes), EXPECTED["tar"]["bytes"])
    add(checks, "tar SHA-256", sha256(tar_bytes) == EXPECTED["tar"]["sha256"], sha256(tar_bytes), EXPECTED["tar"]["sha256"])

    extracted = recovery / "independent_verifier_extraction"
    if extracted.exists():
        import shutil
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True, exist_ok=True)
    tar_members: list[dict[str, Any]] = []
    source_root: Path | None = None
    if tar_bytes:
        try:
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
                members = tf.getmembers()
                add(checks, "tar member count", len(members) == EXPECTED["tar_members"], len(members), EXPECTED["tar_members"])
                unsafe = []
                for m in members:
                    safe = safe_posix(m.name) and (m.isfile() or m.isdir()) and not m.issym() and not m.islnk()
                    tar_members.append({"path": m.name, "bytes": m.size, "regular_or_directory": m.isfile() or m.isdir(), "safe": safe})
                    if not safe:
                        unsafe.append(m.name)
                add(checks, "tar paths and member types safe", not unsafe, unsafe, [])
                if not unsafe:
                    for m in members:
                        target = extracted / m.name
                        if m.isdir():
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        handle = tf.extractfile(m)
                        target.write_bytes(handle.read() if handle else b"")
                        target.chmod(0o755 if m.mode & 0o111 else 0o644)
        except Exception as exc:
            errors.append(f"tar audit/extraction failed: {exc}")
            add(checks, "tar audit and extraction", False, str(exc), "successful")
        else:
            add(checks, "tar audit and extraction", True, "successful", "successful")

    roots = [p.parent for p in extracted.rglob("SOURCE_MANIFEST.json") if PurePosixPath(p.parent.as_posix()).parts[-len(ROOT_SUFFIX.parts):] == ROOT_SUFFIX.parts]
    add(checks, "unique nested source root", len(roots) == 1, [str(p) for p in roots], 1)
    if len(roots) == 1:
        source_root = roots[0]

    manifest_checks: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    if source_root is not None:
        manifest_path = source_root / "SOURCE_MANIFEST.json"
        raw_manifest = manifest_path.read_bytes()
        add(checks, "SOURCE_MANIFEST bytes", len(raw_manifest) == EXPECTED["source_manifest"]["bytes"], len(raw_manifest), EXPECTED["source_manifest"]["bytes"])
        add(checks, "SOURCE_MANIFEST SHA-256", sha256(raw_manifest) == EXPECTED["source_manifest"]["sha256"], sha256(raw_manifest), EXPECTED["source_manifest"]["sha256"])
        try:
            manifest = json.loads(raw_manifest.decode("utf-8"))
        except Exception as exc:
            errors.append(f"SOURCE_MANIFEST parse failed: {exc}")
        entries = manifest.get("entries") if isinstance(manifest, dict) else None
        add(checks, "SOURCE_MANIFEST schema", manifest.get("schema") == "manzanita/useful-plant-v30-source-manifest@1", manifest.get("schema"), "manzanita/useful-plant-v30-source-manifest@1")
        add(checks, "SOURCE_MANIFEST file_count", manifest.get("file_count") == EXPECTED["source_files"], manifest.get("file_count"), EXPECTED["source_files"])
        add(checks, "SOURCE_MANIFEST total_bytes", manifest.get("total_bytes") == EXPECTED["source_bytes"], manifest.get("total_bytes"), EXPECTED["source_bytes"])
        add(checks, "SOURCE_MANIFEST entries list", isinstance(entries, list), type(entries).__name__, "list")
        if isinstance(entries, list):
            add(checks, "SOURCE_MANIFEST entry count", len(entries) == EXPECTED["source_files"], len(entries), EXPECTED["source_files"])
            seen: set[str] = set()
            total = 0
            for entry in entries:
                rel = entry.get("path") if isinstance(entry, dict) else None
                expected_bytes = entry.get("bytes") if isinstance(entry, dict) else None
                expected_hash = entry.get("sha256") if isinstance(entry, dict) else None
                valid_path = isinstance(rel, str) and safe_posix(rel) and rel not in seen
                seen.add(rel or "")
                target = source_root / rel if valid_path else source_root
                raw = target.read_bytes() if valid_path and target.is_file() else b""
                passed = valid_path and target.is_file() and len(raw) == expected_bytes and sha256(raw) == expected_hash
                manifest_checks.append({"path": rel, "pass": passed, "actual_bytes": len(raw) if target.is_file() else None, "expected_bytes": expected_bytes, "actual_sha256": sha256(raw) if target.is_file() else None, "expected_sha256": expected_hash})
                if target.is_file():
                    total += len(raw)
            add(checks, "all SOURCE_MANIFEST entries exact", all(c["pass"] for c in manifest_checks), sum(1 for c in manifest_checks if c["pass"]), len(manifest_checks))
            add(checks, "manifest-covered bytes recomputed", total == EXPECTED["source_bytes"], total, EXPECTED["source_bytes"])

    harness_record: dict[str, Any] = {"result": "NOT_RUN"}
    if source_root is not None:
        harness = source_root / "harness" / "verify_source_carrier.py"
        add(checks, "source harness present", harness.is_file(), str(harness), "regular file")
        if harness.is_file():
            cp = subprocess.run([os.environ.get("PYTHON", "python3"), str(harness)], cwd=str(source_root), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                harness_record = json.loads(cp.stdout)
            except Exception as exc:
                harness_record = {"result": "PARSE_FAIL", "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr, "error": str(exc)}
            add(checks, "source harness exit code", cp.returncode == 0, cp.returncode, 0)
            add(checks, "source harness result", harness_record.get("result") == "PASS", harness_record.get("result"), "PASS")
            add(checks, "source harness checks passed", harness_record.get("checks_passed") == EXPECTED["harness_checks"], harness_record.get("checks_passed"), EXPECTED["harness_checks"])
            add(checks, "source harness checks total", harness_record.get("checks_total") == EXPECTED["harness_checks"], harness_record.get("checks_total"), EXPECTED["harness_checks"])

    result = "PASS" if checks and all(c["pass"] for c in checks) and not errors else "FAIL"
    output = {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": result,
        "classification": "INDEPENDENT_EXACT_CONTINUATION_SOURCE_PAYLOAD_VERIFICATION" if result == "PASS" else "CONTINUATION_SOURCE_PAYLOAD_VERIFICATION_FAILED",
        "checks_passed": sum(1 for c in checks if c["pass"]),
        "checks_total": len(checks),
        "checks": checks,
        "errors": errors,
        "tar_members": tar_members,
        "manifest_entry_checks": manifest_checks,
        "source_harness_receipt": harness_record,
        "authority": {"production_input_admitted": False, "accepted_v30_parent_established": False, "merge_authorized": False, "release_authorized": False, "public_route_effect": "none", "pages_effect": "none", "external_effect": "none", "queue_advanced": False},
        "claim_boundary": "This validation independently verifies only the bounded continuation source replay carrier recovered from repository history. It does not establish the accepted v30 r1 parent, exact retained Neighborhood media, raw PUBLIC_CONVERGENCE provenance, operator acceptance, merge authority, release authority, or public-route effect.",
    }
    write_json(args.output, output)
    print(json.dumps({"result": result, "checks_passed": output["checks_passed"], "checks_total": output["checks_total"]}, indent=2))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
