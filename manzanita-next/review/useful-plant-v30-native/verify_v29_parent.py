#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACT = HERE / "V29_PARENT_ADMISSION_CONTRACT.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any = None,
    expected: Any = None,
) -> None:
    checks.append(
        {
            "name": name,
            "pass": bool(passed),
            "observed": observed,
            "expected": expected,
        }
    )


def safe_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    parts = Path(normalized).parts
    return (
        bool(name)
        and "\\" not in name
        and not normalized.startswith("/")
        and not any(part in {"..", ""} for part in parts)
        and not (parts and ":" in parts[0])
    )


def json_member(zf: zipfile.ZipFile, path: str) -> dict[str, Any]:
    payload = zf.read(path)
    return json.loads(payload.decode("utf-8"))


def required_fields(
    checks: list[dict[str, Any]],
    label: str,
    document: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    for key, value in expected.items():
        observed = document.get(key, object())
        add_check(checks, f"{label}: {key}", observed == value, observed, value)


def hold_receipt(archive: Path, contract: dict[str, Any]) -> dict[str, Any]:
    required = contract["required_archive"]
    return {
        "schema": "manzanita/v29-parent-admission-receipt@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_id": contract["gate_id"],
        "parent_release_id": contract["parent_release_id"],
        "archive_path": str(archive),
        "result": "HOLD_PARENT_ARCHIVE_UNMOUNTED",
        "admission_state": "HOLD",
        "archive_admitted": False,
        "checks_passed": 1,
        "checks_total": 1,
        "checks": [
            {
                "name": "missing archive fails closed",
                "pass": True,
                "observed": "absent",
                "expected": required["filename"],
            }
        ],
        "blocking_holds": [
            "exact v29 archive not mounted",
            "exact Plant donor admission not performed",
            "inherited Household, Street, and Property rendered locks not executed",
            "operator visual acceptance absent",
        ],
        **contract["authority"],
    }


def evaluate_archive(archive: Path, contract: dict[str, Any]) -> dict[str, Any]:
    if not archive.is_file():
        return hold_receipt(archive, contract)

    checks: list[dict[str, Any]] = []
    expected_archive = contract["required_archive"]
    observed_bytes = archive.stat().st_size
    observed_sha256 = sha256_path(archive)
    add_check(checks, "archive filename", archive.name == expected_archive["filename"], archive.name, expected_archive["filename"])
    add_check(checks, "archive bytes", observed_bytes == expected_archive["bytes"], observed_bytes, expected_archive["bytes"])
    add_check(checks, "archive sha256", observed_sha256 == expected_archive["sha256"], observed_sha256, expected_archive["sha256"])

    if not all(item["pass"] for item in checks):
        return finish_receipt(archive, contract, checks, "FAIL_PARENT_ARCHIVE_IDENTITY")

    try:
        with zipfile.ZipFile(archive) as zf:
            bad_member = zf.testzip()
            add_check(checks, "ZIP CRC integrity", bad_member is None, bad_member, None)

            infos = zf.infolist()
            names = [item.filename for item in infos if not item.is_dir()]
            unsafe = [name for name in names if not safe_member_name(name)]
            add_check(checks, "ZIP paths safe", not unsafe, unsafe, [])

            casefolded: dict[str, list[str]] = {}
            for name in names:
                casefolded.setdefault(name.casefold(), []).append(name)
            collisions = [items for items in casefolded.values() if len(items) > 1]
            add_check(checks, "ZIP paths case-unique", not collisions, collisions, [])

            symlinks: list[str] = []
            for info in infos:
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_IFMT(mode) == stat.S_IFLNK:
                    symlinks.append(info.filename)
            add_check(checks, "ZIP contains no symlinks", not symlinks, symlinks, [])

            name_set = set(names)
            for required in contract["required_members"]:
                path = required["path"]
                present = path in name_set
                add_check(checks, f"required member present: {path}", present, present, True)
                if not present:
                    continue
                payload = zf.read(path)
                observed = {"bytes": len(payload), "sha256": sha256_bytes(payload)}
                if "bytes" in required:
                    add_check(checks, f"required member bytes: {path}", observed["bytes"] == required["bytes"], observed["bytes"], required["bytes"])
                if "sha256" in required:
                    add_check(checks, f"required member sha256: {path}", observed["sha256"] == required["sha256"], observed["sha256"], required["sha256"])

            if "index.html" in name_set and "mw-habitat-live-photo-029.STANDALONE.html" in name_set:
                index_payload = zf.read("index.html")
                standalone_payload = zf.read("mw-habitat-live-photo-029.STANDALONE.html")
                add_check(
                    checks,
                    "Household entry and standalone exact-byte agreement",
                    index_payload == standalone_payload,
                    sha256_bytes(index_payload),
                    sha256_bytes(standalone_payload),
                )

            semantic_documents: dict[str, dict[str, Any]] = {}
            for label, rule in contract["semantic_receipts"].items():
                path = rule["path"]
                if path not in name_set:
                    continue
                try:
                    document = json_member(zf, path)
                    semantic_documents[label] = document
                    add_check(checks, f"{label}: JSON parse", True, "valid", "valid")
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    add_check(checks, f"{label}: JSON parse", False, str(exc), "valid")
                    continue
                required_fields(checks, label, document, rule["required"])

            seal_rule = contract["semantic_receipts"]["seal"]
            seal = semantic_documents.get("seal")
            if seal is not None:
                ledger_rows = seal.get(seal_rule.get("member_ledger_field", "files"), [])
                ledger = {
                    row.get("path"): {"bytes": row.get("bytes"), "sha256": row.get("sha256")}
                    for row in ledger_rows
                    if isinstance(row, dict) and isinstance(row.get("path"), str)
                }
                for required in contract["required_members"]:
                    path = required["path"]
                    if path == seal_rule["path"]:
                        continue
                    if "bytes" not in required or "sha256" not in required:
                        continue
                    observed = ledger.get(path)
                    expected = {"bytes": required["bytes"], "sha256": required["sha256"]}
                    add_check(checks, f"seal ledger exact member: {path}", observed == expected, observed, expected)

    except zipfile.BadZipFile as exc:
        add_check(checks, "ZIP opens", False, str(exc), "valid ZIP")

    return finish_receipt(archive, contract, checks, "PASS_EXACT_V29_PARENT_ADMITTED")


def finish_receipt(
    archive: Path,
    contract: dict[str, Any],
    checks: list[dict[str, Any]],
    pass_result: str,
) -> dict[str, Any]:
    passed = sum(1 for item in checks if item["pass"])
    all_pass = bool(checks) and passed == len(checks)
    return {
        "schema": "manzanita/v29-parent-admission-receipt@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_id": contract["gate_id"],
        "parent_release_id": contract["parent_release_id"],
        "archive_path": str(archive),
        "archive_measurement": {
            "bytes": archive.stat().st_size if archive.is_file() else None,
            "sha256": sha256_path(archive) if archive.is_file() else None,
        },
        "result": pass_result if all_pass else "FAIL_PARENT_ADMISSION",
        "admission_state": "ADMITTED" if all_pass else "FAIL",
        "archive_admitted": all_pass,
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "next_gate": contract["next_gate_after_pass"] if all_pass else None,
        "blocking_holds": [] if all_pass else ["parent admission checks failed"],
        **contract["authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed exact v29 parent admission gate.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expect-missing",
        action="store_true",
        help="Treat an absent exact archive as an expected, successfully enforced HOLD.",
    )
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    receipt = evaluate_archive(args.archive, contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))

    if receipt["result"] == "PASS_EXACT_V29_PARENT_ADMITTED":
        return 0
    if receipt["result"] == "HOLD_PARENT_ARCHIVE_UNMOUNTED" and args.expect_missing:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
