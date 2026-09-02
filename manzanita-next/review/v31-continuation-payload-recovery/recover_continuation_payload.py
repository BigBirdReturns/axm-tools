#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import lzma
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

BASE64_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
SCHEMA = "manzanita/v31-continuation-payload-recovery@1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def safe_member_name(name: str) -> tuple[bool, str]:
    p = PurePosixPath(name)
    if not name or p.is_absolute():
        return False, "empty-or-absolute"
    if any(part in ("", ".", "..") for part in p.parts):
        return False, "unsafe-component"
    if "\\" in name:
        return False, "backslash"
    return True, "ok"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, indent=2, sort_keys=False, ensure_ascii=False).encode("utf-8") + b"\n")


def scan_git_objects(repo: Path, target_hashes: dict[str, dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "result": "PASS",
        "objects_seen": 0,
        "blobs_seen": 0,
        "blob_bytes_seen": 0,
        "candidate_blobs_hashed": 0,
        "candidate_blob_bytes_hashed": 0,
        "exact_matches": [],
        "errors": [],
    }
    interesting_sizes = {int(spec["bytes"]) for spec in target_hashes.values()}
    try:
        cp = run(
            [
                "git",
                "cat-file",
                "--batch-all-objects",
                "--batch-check=%(objectname) %(objecttype) %(objectsize)",
            ],
            cwd=repo,
        )
    except Exception as exc:
        result["result"] = "FAIL"
        result["errors"].append(f"object enumeration failed: {exc}")
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result

    by_size: dict[int, list[tuple[str, str, str]]] = {}
    for label, spec in target_hashes.items():
        by_size.setdefault(int(spec["bytes"]), []).append((label, str(spec["sha256"]), str(spec.get("kind", "blob"))))

    exact_dir = output_dir / "exact_git_object_matches"
    exact_dir.mkdir(parents=True, exist_ok=True)
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            result["errors"].append(f"unparsed object row: {line!r}")
            continue
        oid, obj_type, size_text = parts
        result["objects_seen"] += 1
        try:
            size = int(size_text)
        except ValueError:
            result["errors"].append(f"invalid object size: {line!r}")
            continue
        if obj_type != "blob":
            continue
        result["blobs_seen"] += 1
        result["blob_bytes_seen"] += size
        if size not in interesting_sizes:
            continue
        try:
            raw = subprocess.run(
                ["git", "cat-file", "blob", oid],
                cwd=str(repo),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
        except Exception as exc:
            result["errors"].append(f"cat-file {oid} failed: {exc}")
            continue
        result["candidate_blobs_hashed"] += 1
        result["candidate_blob_bytes_hashed"] += len(raw)
        digest = sha256_bytes(raw)
        for label, expected, kind in by_size[size]:
            if digest != expected:
                continue
            name = f"{label}__git-{oid}.bin"
            path = exact_dir / name
            path.write_bytes(raw)
            result["exact_matches"].append(
                {
                    "label": label,
                    "kind": kind,
                    "git_oid": oid,
                    "bytes": len(raw),
                    "sha256": digest,
                    "artifact_path": str(path.relative_to(output_dir)),
                }
            )
    if result["errors"]:
        result["result"] = "PASS_WITH_WARNINGS"
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result


def candidate_variants(raw: bytes) -> Iterable[tuple[str, bytes, dict[str, Any]]]:
    yield "as-is", raw, {}
    stripped = raw.rstrip(b"\r\n")
    yield "canonical-lf", stripped + b"\n", {"removed_line_end_bytes": len(raw) - len(stripped)}
    yield "payload-only", stripped, {"removed_line_end_bytes": len(raw) - len(stripped)}
    yield "canonical-crlf", stripped + b"\r\n", {"removed_line_end_bytes": len(raw) - len(stripped)}
    if b"-" in stripped or b"_" in stripped:
        translated = stripped.translate(bytes.maketrans(b"-_", b"+/")) + b"\n"
        yield "urlsafe-to-standard", translated, {}
    if b" " in stripped:
        yield "space-to-plus", stripped.replace(b" ", b"+") + b"\n", {}


def recover_single_substitution(raw: bytes, expected_sha256: str) -> tuple[bytes | None, dict[str, Any]]:
    started = time.monotonic()
    buf = bytearray(raw)
    attempts = 0
    for pos in range(len(buf)):
        old = buf[pos]
        alphabet = b"\n\r" if pos >= len(buf) - 2 and old in b"\r\n" else BASE64_ALPHABET
        for new in alphabet:
            if new == old:
                continue
            buf[pos] = new
            attempts += 1
            if hashlib.sha256(buf).hexdigest() == expected_sha256:
                return bytes(buf), {
                    "method": "single-byte-substitution",
                    "position": pos,
                    "old_byte": old,
                    "old_char": chr(old) if 32 <= old < 127 else None,
                    "new_byte": new,
                    "new_char": chr(new) if 32 <= new < 127 else None,
                    "attempts": attempts,
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                }
        buf[pos] = old
    return None, {
        "method": "single-byte-substitution",
        "attempts": attempts,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "result": "not-found",
    }


def recover_adjacent_swap(raw: bytes, expected_sha256: str) -> tuple[bytes | None, dict[str, Any]]:
    started = time.monotonic()
    buf = bytearray(raw)
    attempts = 0
    for pos in range(len(buf) - 1):
        if buf[pos] == buf[pos + 1]:
            continue
        buf[pos], buf[pos + 1] = buf[pos + 1], buf[pos]
        attempts += 1
        if hashlib.sha256(buf).hexdigest() == expected_sha256:
            return bytes(buf), {
                "method": "adjacent-byte-swap",
                "position": pos,
                "attempts": attempts,
                "elapsed_seconds": round(time.monotonic() - started, 6),
            }
        buf[pos], buf[pos + 1] = buf[pos + 1], buf[pos]
    return None, {
        "method": "adjacent-byte-swap",
        "attempts": attempts,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "result": "not-found",
    }


def recover_part(raw: bytes, expected_sha256: str, exact_object_candidates: list[bytes]) -> tuple[bytes | None, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for index, candidate in enumerate(exact_object_candidates):
        digest = sha256_bytes(candidate)
        attempts.append({"method": "exact-git-object", "index": index, "bytes": len(candidate), "sha256": digest})
        if digest == expected_sha256:
            return candidate, {"result": "RECOVERED", "selected": attempts[-1], "attempts": attempts}

    seen: set[bytes] = set()
    for name, candidate, detail in candidate_variants(raw):
        if candidate in seen:
            continue
        seen.add(candidate)
        digest = sha256_bytes(candidate)
        entry = {"method": name, "bytes": len(candidate), "sha256": digest, **detail}
        attempts.append(entry)
        if digest == expected_sha256:
            return candidate, {"result": "RECOVERED", "selected": entry, "attempts": attempts}

    recovered, detail = recover_single_substitution(raw, expected_sha256)
    attempts.append(detail)
    if recovered is not None:
        return recovered, {"result": "RECOVERED", "selected": detail, "attempts": attempts}

    recovered, detail = recover_adjacent_swap(raw, expected_sha256)
    attempts.append(detail)
    if recovered is not None:
        return recovered, {"result": "RECOVERED", "selected": detail, "attempts": attempts}

    return None, {"result": "NOT_RECOVERED", "attempts": attempts}


def deterministic_zip(source_dir: Path, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(source_dir).as_posix()
            raw = path.read_bytes()
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            zf.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            members.append({"path": rel, "bytes": len(raw), "sha256": sha256_bytes(raw)})
    raw_zip = output_path.read_bytes()
    return {
        "path": str(output_path),
        "member_count": len(members),
        "bytes": len(raw_zip),
        "sha256": sha256_bytes(raw_zip),
        "members": members,
    }


def validate_source_manifest(extracted: Path) -> dict[str, Any]:
    manifest_path = extracted / "SOURCE_MANIFEST.json"
    result: dict[str, Any] = {"present": manifest_path.is_file(), "result": "NOT_PRESENT", "checks": []}
    if not manifest_path.is_file():
        return result
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["result"] = "FAIL"
        result["error"] = f"manifest parse failed: {exc}"
        return result
    entries = manifest.get("entries") or manifest.get("files") or manifest.get("members") or []
    if not isinstance(entries, list):
        result["result"] = "FAIL"
        result["error"] = "manifest entries are not a list"
        return result
    checks: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            checks.append({"path": None, "pass": False, "detail": "entry-not-object"})
            continue
        rel = entry.get("path") or entry.get("name")
        if not isinstance(rel, str):
            checks.append({"path": None, "pass": False, "detail": "missing-path"})
            continue
        ok, reason = safe_member_name(rel)
        target = extracted / rel
        if not ok:
            checks.append({"path": rel, "pass": False, "detail": reason})
            continue
        if not target.is_file():
            checks.append({"path": rel, "pass": False, "detail": "missing"})
            continue
        raw = target.read_bytes()
        expected_bytes = entry.get("bytes")
        expected_sha = entry.get("sha256")
        passed = (expected_bytes is None or len(raw) == int(expected_bytes)) and (expected_sha is None or sha256_bytes(raw) == str(expected_sha))
        checks.append(
            {
                "path": rel,
                "pass": passed,
                "actual_bytes": len(raw),
                "expected_bytes": expected_bytes,
                "actual_sha256": sha256_bytes(raw),
                "expected_sha256": expected_sha,
            }
        )
    result["manifest_schema"] = manifest.get("schema")
    result["entry_count"] = len(entries)
    result["checks"] = checks
    result["checks_passed"] = sum(1 for c in checks if c.get("pass"))
    result["checks_total"] = len(checks)
    result["result"] = "PASS" if checks and all(c.get("pass") for c in checks) else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--carrier", type=Path, default=Path("manzanita-next/review/mw-habitat-live-photo-030-continuation"))
    parser.add_argument("--output", type=Path, default=Path("_temp/v31-continuation-payload-recovery"))
    args = parser.parse_args()

    repo = args.repo.resolve()
    carrier = args.carrier if args.carrier.is_absolute() else repo / args.carrier
    output = args.output if args.output.is_absolute() else repo / args.output
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    receipt = json.loads((carrier / "PAYLOAD_RECEIPT.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((carrier / "BOOTSTRAP_MANIFEST.json").read_text(encoding="utf-8"))

    expected_parts = {entry["path"]: entry for entry in receipt["carrier_parts"]}
    bootstrap_parts = {
        PurePosixPath(entry["path"]).name: entry
        for entry in bootstrap["entries"]
        if "SOURCE_PAYLOAD.tar.xz.b64.part" in entry["path"]
    }

    part_records: list[dict[str, Any]] = []
    target_hashes: dict[str, dict[str, Any]] = {}
    for name, spec in expected_parts.items():
        raw = (carrier / name).read_bytes()
        actual = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
        bootstrap_spec = bootstrap_parts.get(name)
        record = {
            "path": name,
            "expected": {"bytes": int(spec["bytes"]), "sha256": spec["sha256"]},
            "bootstrap_expected": bootstrap_spec,
            "actual": actual,
            "exact": actual["bytes"] == int(spec["bytes"]) and actual["sha256"] == spec["sha256"],
        }
        part_records.append(record)
        target_hashes[f"part-{name[-2:]}"] = {"bytes": int(spec["bytes"]), "sha256": spec["sha256"], "kind": "carrier-part"}
    target_hashes.update(
        {
            "payload-xz": {"bytes": int(receipt["xz_bytes"]), "sha256": receipt["xz_sha256"], "kind": "xz"},
            "payload-base64": {"bytes": int(receipt["base64_bytes"]), "sha256": receipt["base64_sha256"], "kind": "base64-payload"},
        }
    )

    object_scan = scan_git_objects(repo, target_hashes, output)
    object_match_bytes: dict[str, list[bytes]] = {}
    for match in object_scan.get("exact_matches", []):
        path = output / match["artifact_path"]
        object_match_bytes.setdefault(match["label"], []).append(path.read_bytes())

    current_dir = output / "current_parts"
    recovered_dir = output / "recovered_parts"
    current_dir.mkdir(parents=True, exist_ok=True)
    recovered_dir.mkdir(parents=True, exist_ok=True)

    recovered_parts: list[bytes] = []
    recovery_records: list[dict[str, Any]] = []
    all_parts_recovered = True
    for record in part_records:
        name = record["path"]
        raw = (carrier / name).read_bytes()
        (current_dir / name).write_bytes(raw)
        if record["exact"]:
            recovered = raw
            detail = {"result": "ALREADY_EXACT", "selected": {"method": "as-is"}, "attempts": []}
        else:
            label = f"part-{name[-2:]}"
            recovered, detail = recover_part(raw, record["expected"]["sha256"], object_match_bytes.get(label, []))
        out_record = {**record, "recovery": detail}
        if recovered is None:
            all_parts_recovered = False
            recovered_parts.append(raw)
            out_record["selected_bytes"] = len(raw)
            out_record["selected_sha256"] = sha256_bytes(raw)
            out_record["selected_is_expected"] = False
        else:
            recovered_parts.append(recovered)
            (recovered_dir / name).write_bytes(recovered)
            out_record["selected_bytes"] = len(recovered)
            out_record["selected_sha256"] = sha256_bytes(recovered)
            out_record["selected_is_expected"] = sha256_bytes(recovered) == record["expected"]["sha256"]
            if not out_record["selected_is_expected"]:
                all_parts_recovered = False
        recovery_records.append(out_record)

    payload_b64 = b"".join(part.rstrip(b"\r\n") for part in recovered_parts)
    payload_checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, actual: Any, expected: Any) -> None:
        payload_checks.append({"name": name, "pass": bool(passed), "actual": actual, "expected": expected})

    add_check("part-count", len(recovered_parts) == int(receipt["carrier_part_count"]), len(recovered_parts), receipt["carrier_part_count"])
    add_check("base64-bytes", len(payload_b64) == int(receipt["base64_bytes"]), len(payload_b64), receipt["base64_bytes"])
    add_check("base64-sha256", sha256_bytes(payload_b64) == receipt["base64_sha256"], sha256_bytes(payload_b64), receipt["base64_sha256"])
    (output / "SOURCE_PAYLOAD.recovered.b64").write_bytes(payload_b64 + b"\n")

    xz_bytes = b""
    tar_bytes = b""
    base64_error: str | None = None
    xz_error: str | None = None
    try:
        xz_bytes = base64.b64decode(payload_b64, validate=True)
    except Exception as exc:
        base64_error = str(exc)
        add_check("base64-decode", False, base64_error, "valid RFC 4648 Base64")
    else:
        add_check("base64-decode", True, "valid", "valid RFC 4648 Base64")
        add_check("xz-bytes", len(xz_bytes) == int(receipt["xz_bytes"]), len(xz_bytes), receipt["xz_bytes"])
        add_check("xz-sha256", sha256_bytes(xz_bytes) == receipt["xz_sha256"], sha256_bytes(xz_bytes), receipt["xz_sha256"])
        (output / "SOURCE_PAYLOAD.recovered.tar.xz").write_bytes(xz_bytes)
        try:
            tar_bytes = lzma.decompress(xz_bytes)
        except Exception as exc:
            xz_error = str(exc)
            add_check("xz-decompress", False, xz_error, "valid XZ stream")
        else:
            add_check("xz-decompress", True, "valid", "valid XZ stream")
            add_check("tar-bytes", len(tar_bytes) == int(receipt["tar_bytes"]), len(tar_bytes), receipt["tar_bytes"])
            add_check("tar-sha256", sha256_bytes(tar_bytes) == receipt["tar_sha256"], sha256_bytes(tar_bytes), receipt["tar_sha256"])
            (output / "SOURCE_PAYLOAD.recovered.tar").write_bytes(tar_bytes)

    tar_audit: dict[str, Any] = {"result": "NOT_RUN", "members": [], "errors": []}
    extracted_dir = output / "recovered_source"
    source_manifest_validation: dict[str, Any] = {"result": "NOT_RUN"}
    archive_record: dict[str, Any] | None = None
    if tar_bytes:
        extracted_dir.mkdir(parents=True, exist_ok=True)
        try:
            import io
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
                members = tf.getmembers()
                tar_audit["member_count"] = len(members)
                for member in members:
                    ok, reason = safe_member_name(member.name)
                    rec = {
                        "path": member.name,
                        "type": member.type.decode("ascii", "replace") if isinstance(member.type, bytes) else str(member.type),
                        "size": member.size,
                        "safe_path": ok,
                        "path_reason": reason,
                        "regular_or_directory": member.isfile() or member.isdir(),
                    }
                    tar_audit["members"].append(rec)
                    if not ok or not (member.isfile() or member.isdir()):
                        tar_audit["errors"].append(rec)
                if len(members) != int(receipt["member_count"]):
                    tar_audit["errors"].append({"member_count_mismatch": {"actual": len(members), "expected": receipt["member_count"]}})
                if not tar_audit["errors"]:
                    for member in members:
                        if member.isdir():
                            (extracted_dir / member.name).mkdir(parents=True, exist_ok=True)
                            continue
                        target = extracted_dir / member.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source = tf.extractfile(member)
                        target.write_bytes(source.read() if source else b"")
                        target.chmod(0o755 if member.mode & 0o111 else 0o644)
                    tar_audit["result"] = "PASS"
                else:
                    tar_audit["result"] = "FAIL"
        except Exception as exc:
            tar_audit["result"] = "FAIL"
            tar_audit["errors"].append({"tar_open_error": str(exc)})

        if tar_audit["result"] == "PASS":
            source_manifest_validation = validate_source_manifest(extracted_dir)
            archive_record = deterministic_zip(extracted_dir, output / "V31_CONTINUATION_SOURCE_PAYLOAD_RECOVERED.zip")

    exact_payload = all_parts_recovered and all(check["pass"] for check in payload_checks)
    if exact_payload and tar_audit.get("result") == "PASS":
        classification = "EXACT_CONTINUATION_SOURCE_PAYLOAD_RECOVERED"
    elif all_parts_recovered:
        classification = "PART_HASHES_RECOVERED_BUT_COMPOSITE_PAYLOAD_FAILED"
    else:
        classification = "HOLD_CONTINUATION_CARRIER_PARTS_NOT_RECOVERED"

    final = {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "started_at": started_at,
        "repository": {
            "root": str(repo),
            "head": run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip(),
            "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip(),
        },
        "carrier": {
            "path": str(carrier.relative_to(repo)),
            "payload_receipt_schema": receipt.get("schema"),
            "bootstrap_manifest_schema": bootstrap.get("schema"),
        },
        "classification": classification,
        "result": "PASS" if classification == "EXACT_CONTINUATION_SOURCE_PAYLOAD_RECOVERED" else "HOLD",
        "all_parts_recovered": all_parts_recovered,
        "exact_payload_recovered": exact_payload,
        "part_records": recovery_records,
        "git_object_scan": object_scan,
        "payload_checks": payload_checks,
        "base64_error": base64_error,
        "xz_error": xz_error,
        "tar_audit": tar_audit,
        "source_manifest_validation": source_manifest_validation,
        "recovered_source_archive": archive_record,
        "authority": {
            "product_files_modified": 0,
            "merge_authorized": False,
            "release_authorized": False,
            "public_route_effect": "none",
            "pages_effect": "none",
            "external_effect": "none",
            "queue_advanced": False,
        },
        "claim_boundary": "This receipt governs recovery of the bounded continuation source replay carrier only. Even an exact recovery does not establish the accepted v30 r1 parent, the exact retained Neighborhood media, raw PUBLIC_CONVERGENCE provenance, operator acceptance, merge authority, release authority, or public-route effect.",
    }
    write_json(output / "V31_CONTINUATION_PAYLOAD_RECOVERY_RECEIPT.json", final)

    summary_lines = [
        "# Manzanita V31 continuation payload recovery",
        "",
        f"Classification: `{classification}`",
        "",
        f"Exact carrier parts recovered: `{all_parts_recovered}`",
        f"Exact composite payload recovered: `{exact_payload}`",
        f"Git objects observed: `{object_scan.get('objects_seen', 0)}`",
        f"Candidate blobs hashed: `{object_scan.get('candidate_blobs_hashed', 0)}`",
        f"Exact Git-object matches: `{len(object_scan.get('exact_matches', []))}`",
        "",
        "The recovery is bounded to the source replay carrier. It does not admit or reconstruct the accepted v30 r1 parent or any held production input.",
    ]
    (output / "V31_CONTINUATION_PAYLOAD_RECOVERY_SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(json.dumps({"classification": classification, "exact_payload_recovered": exact_payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
