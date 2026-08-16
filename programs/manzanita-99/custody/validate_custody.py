#!/usr/bin/env python3
"""Validate Manzanita donor custody without confusing partial custody for closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

REGISTER_SCHEMA = "axm-tools/manzanita-99-donor-register@1"
MANIFEST_SCHEMA = "axm-tools/manzanita-99-custody-manifest@1"
DEFAULT_REGISTER = Path(__file__).with_name("DONOR_REGISTER.json")
DEFAULT_MANIFEST = Path(__file__).with_name("CUSTODY_MANIFEST.json")


class CustodyError(ValueError):
    """Raised when custody evidence violates the program contract."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CustodyError(message)


def clean_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    require(
        bool(value) and value != "." and not path.is_absolute() and ".." not in path.parts,
        f"Unsafe repository-relative path: {value!r}",
    )
    return path.as_posix()


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CustodyError(f"Invalid JSON in {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value, raw


def unique_ids(rows: list[dict[str, Any]], label: str) -> set[str]:
    ids: list[str] = []
    for row in rows:
        value = row.get("id")
        require(isinstance(value, str) and value, f"{label} row lacks an id")
        ids.append(value)
    require(len(ids) == len(set(ids)), f"Duplicate {label} ids")
    return set(ids)


def validate_register(register: dict[str, Any]) -> dict[str, Any]:
    require(register.get("schema") == REGISTER_SCHEMA, "Unexpected donor register schema")
    require(register.get("task") == "JDB99-001", "Register must govern JDB99-001")
    require(register.get("state") in {"in_progress", "closed"}, "Invalid task state")
    require(bool(register.get("qualification_boundary")), "Qualification boundary is required")

    scopes = register.get("archive_scopes")
    donors = register.get("donors")
    gaps = register.get("gaps")
    required_classes = register.get("required_classes")

    require(isinstance(scopes, list) and scopes, "At least one archive scope is required")
    require(isinstance(donors, list) and donors, "At least one donor is required")
    require(isinstance(gaps, list), "Gaps must be a list")
    require(isinstance(required_classes, list) and required_classes, "Required classes are missing")
    require(len(required_classes) == len(set(required_classes)), "Duplicate required classes")

    scope_ids = unique_ids(scopes, "archive scope")
    donor_ids = unique_ids(donors, "donor")
    gap_ids = unique_ids(gaps, "gap")
    require(donor_ids.isdisjoint(gap_ids), "Donor and gap ids must not collide")

    for scope in scopes:
        clean_relative_path(scope.get("path", ""))
        for excluded in scope.get("exclude", []):
            clean_relative_path(excluded)

    archived_classes: set[str] = set()
    for donor in donors:
        donor_class = donor.get("class")
        require(donor_class in required_classes, f"Unknown donor class: {donor_class!r}")
        require(
            donor.get("custody_state") in {
                "archived",
                "archived_private_external",
                "located_not_archived",
                "missing",
                "rejected",
            },
            f"Invalid custody state for {donor['id']}",
        )
        donor_scopes = donor.get("archive_scope_ids", [])
        require(
            set(donor_scopes).issubset(scope_ids),
            f"{donor['id']} references an unknown archive scope",
        )
        require(bool(donor.get("claim_boundary")), f"{donor['id']} lacks a claim boundary")
        if donor.get("custody_state") == "archived":
            archived_classes.add(donor_class)

    open_required = []
    gap_classes: set[str] = set()
    for gap in gaps:
        gap_class = gap.get("class")
        require(gap_class in required_classes, f"Unknown gap class: {gap_class!r}")
        require(gap.get("state") in {"open", "closed"}, f"Invalid gap state: {gap['id']}")
        require(bool(gap.get("target")), f"{gap['id']} lacks a target")
        require(bool(gap.get("admission")), f"{gap['id']} lacks admission criteria")
        require(bool(gap.get("failure_mode")), f"{gap['id']} lacks a failure mode")
        gap_classes.add(gap_class)
        if gap.get("required_for_close") and gap.get("state") != "closed":
            open_required.append(gap["id"])

    uncovered = sorted(set(required_classes) - archived_classes - gap_classes)
    require(not uncovered, f"Required custody classes lack an archive or gap: {uncovered}")

    guard = register.get("public_route_guard")
    require(isinstance(guard, dict), "Public route guard is required")
    clean_relative_path(guard.get("path", ""))
    guard_files = guard.get("files")
    require(isinstance(guard_files, dict) and guard_files, "Public route guard has no files")
    for path, expected in guard_files.items():
        clean_relative_path(path)
        require(
            isinstance(expected, dict) and len(expected.get("git_blob_sha1", "")) == 40,
            f"Public route guard lacks a Git blob identity for {path}",
        )
        if "sha256" in expected:
            require(len(expected["sha256"]) == 64, f"Invalid SHA-256 guard for {path}")

    if register["state"] == "closed":
        require(not open_required, "JDB99-001 cannot close while required gaps remain")
        not_archived = sorted(
            donor["id"] for donor in donors if donor.get("custody_state") != "archived"
        )
        require(not not_archived, f"JDB99-001 cannot close with unarchived donors: {not_archived}")
    else:
        require(open_required, "An in-progress custody task must identify its open close gates")

    return {
        "scope_ids": scope_ids,
        "open_required": sorted(open_required),
        "archived_classes": archived_classes,
    }


def validate_public_guard(repo_root: Path, register: dict[str, Any]) -> None:
    for relative, expected in register["public_route_guard"]["files"].items():
        clean = clean_relative_path(relative)
        path = (repo_root / clean).resolve()
        try:
            path.relative_to(repo_root)
        except ValueError as exc:
            raise CustodyError(f"Guard path escapes repository: {relative}") from exc
        require(path.is_file(), f"Guarded public-route file is missing: {relative}")
        payload = path.read_bytes()
        require(
            git_blob_sha1(payload) == expected["git_blob_sha1"],
            f"Historical public route changed: {relative}",
        )
        if "sha256" in expected:
            require(
                sha256_bytes(payload) == expected["sha256"],
                f"Historical public route SHA-256 changed: {relative}",
            )


def validate_manifest(
    repo_root: Path,
    register: dict[str, Any],
    register_raw: bytes,
    manifest: dict[str, Any],
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    require(manifest.get("schema") == MANIFEST_SCHEMA, "Unexpected custody manifest schema")
    require(manifest.get("task") == "JDB99-001", "Manifest must govern JDB99-001")
    require(manifest.get("task_state") == register.get("state"), "Task state drifted")
    require(
        manifest.get("generated_from", {}).get("register_sha256") == sha256_bytes(register_raw),
        "Manifest was built from a different donor register",
    )

    payload = dict(manifest)
    supplied_payload_hash = payload.pop("payload_sha256", None)
    require(
        supplied_payload_hash == sha256_bytes(canonical_bytes(payload)),
        "Custody manifest payload checksum is invalid",
    )

    validate_public_guard(repo_root, register)

    files = manifest.get("files")
    require(isinstance(files, list) and files, "Custody manifest has no files")
    paths = [row.get("path") for row in files]
    require(paths == sorted(paths), "Custody manifest files are not path-sorted")
    require(len(paths) == len(set(paths)), "Custody manifest contains duplicate paths")
    require(manifest.get("source_file_count") == len(files), "File count drifted")
    require(
        manifest.get("source_bytes") == sum(row.get("bytes", -1) for row in files),
        "Source byte count drifted",
    )

    for row in files:
        relative = clean_relative_path(row.get("path", ""))
        path = (repo_root / relative).resolve()
        try:
            path.relative_to(repo_root)
        except ValueError as exc:
            raise CustodyError(f"Manifest path escapes repository: {relative}") from exc
        require(path.is_file(), f"Manifest source file is missing: {relative}")
        payload_bytes = path.read_bytes()
        require(len(payload_bytes) == row.get("bytes"), f"Byte count changed: {relative}")
        require(sha256_bytes(payload_bytes) == row.get("sha256"), f"SHA-256 changed: {relative}")
        require(
            git_blob_sha1(payload_bytes) == row.get("git_blob_sha1"),
            f"Git blob identity changed: {relative}",
        )
        require(row.get("scopes"), f"Manifest file has no archive scope: {relative}")

    expected_open = sorted(
        gap["id"]
        for gap in register.get("gaps", [])
        if gap.get("required_for_close") and gap.get("state") != "closed"
    )
    require(
        manifest.get("open_required_gaps") == expected_open,
        "Manifest open-gap set drifted from donor register",
    )
    expected_status = "COMPLETE" if not expected_open else "PARTIAL"
    require(manifest.get("status") == expected_status, "Manifest custody status is false")
    require(
        manifest.get("qualification_boundary") == register.get("qualification_boundary"),
        "Qualification boundary drifted",
    )
    if require_complete:
        require(expected_status == "COMPLETE", "Custody remains partial")

    return {
        "status": expected_status,
        "files": len(files),
        "bytes": manifest.get("source_bytes"),
        "open_required": expected_open,
        "payload_sha256": supplied_payload_hash,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--require-complete", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    register, register_raw = load_json(args.register)
    manifest, _ = load_json(args.manifest)
    register_result = validate_register(register)
    manifest_result = validate_manifest(
        repo_root,
        register,
        register_raw,
        manifest,
        require_complete=args.require_complete,
    )
    print(
        json.dumps(
            {
                "result": "PASS",
                "task": "JDB99-001",
                "task_state": register.get("state"),
                "custody_status": manifest_result["status"],
                "repo_resident_files": manifest_result["files"],
                "repo_resident_bytes": manifest_result["bytes"],
                "open_required_gaps": len(register_result["open_required"]),
                "qualification": "custody consistency only",
                "manifest_sha256": manifest_result["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except CustodyError as exc:
        raise SystemExit(str(exc)) from exc
