#!/usr/bin/env python3
"""Validate Manzanita donor custody without converting partial evidence into closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT_SCHEMA = "axm-tools/manzanita-donor-custody-contract@2"
REGISTER_SCHEMA = "axm-tools/manzanita-donor-register@2"
MANIFEST_SCHEMA = "axm-tools/manzanita-custody-manifest@2"
ALLOWED_DONOR_STATES = {"archived_repo", "archived_external", "located_not_archived", "missing", "rejected"}


class CustodyValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CustodyValidationError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def git_value(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    require(result.returncode == 0, f"Git object lookup failed for {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CustodyValidationError(f"Invalid JSON in {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain an object")
    return value, raw


def clean_relative(value: str) -> str:
    path = PurePosixPath(value)
    require(value not in {"", "."} and not path.is_absolute() and ".." not in path.parts, f"Unsafe path: {value!r}")
    return path.as_posix()


def resolve_regular_repo_file(repo_root: Path, relative: str, label: str) -> Path:
    clean = clean_relative(relative)
    unresolved = repo_root / clean
    require(
        unresolved.exists() or unresolved.is_symlink(),
        f"{label} is missing: {relative}",
    )
    require(
        not unresolved.is_symlink(),
        f"{label} may not be a symbolic link: {relative}",
    )
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise CustodyValidationError(f"{label} escapes repo: {relative}") from exc
    require(resolved.is_file(), f"{label} is not a regular file: {relative}")
    return resolved


def unique_ids(rows: list[dict[str, Any]], label: str) -> set[str]:
    values = [row.get("id") for row in rows]
    require(all(isinstance(value, str) and value for value in values), f"{label} id is missing")
    require(len(values) == len(set(values)), f"Duplicate {label} ids")
    return set(values)


def validate_contract(contract: dict[str, Any]) -> set[str]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected contract schema")
    require(contract.get("state") in {"in_progress", "closed"}, "Invalid contract state")
    required_classes = contract.get("required_classes")
    require(isinstance(required_classes, list) and required_classes, "Required classes are missing")
    require(len(required_classes) == len(set(required_classes)), "Required classes are duplicated")
    scopes = contract.get("archive_scopes")
    require(isinstance(scopes, list) and scopes, "Archive scopes are missing")
    unique_ids(scopes, "archive scope")
    for scope in scopes:
        clean_relative(str(scope.get("path", "")))
        require(scope.get("class") in required_classes, f"Unknown scope class: {scope.get('class')}")
    guard = contract.get("public_route_guard")
    require(isinstance(guard, dict), "Public route guard is missing")
    files = guard.get("files")
    require(isinstance(files, dict) and files, "Public route guard has no files")
    for path, expected in files.items():
        clean_relative(path)
        require(len(str(expected.get("git_blob_sha1", ""))) == 40, f"Guard lacks Git blob id: {path}")
    historical = contract.get("historical_public_route_guards", [])
    require(isinstance(historical, list), "Historical public route guards must be a list")
    releases = []
    for row in historical:
        require(isinstance(row, dict), "Historical public route guard must be an object")
        releases.append(str(row.get("release", "")))
        clean_relative(str(row.get("path", "")))
        require(len(str(row.get("commit", ""))) == 40, "Historical public route guard lacks commit")
        require(len(str(row.get("tree", ""))) == 40, "Historical public route guard lacks tree")
        historical_files = row.get("files")
        require(isinstance(historical_files, dict) and historical_files, "Historical public route guard has no files")
        for historical_path, expected in historical_files.items():
            clean_relative(historical_path)
            require(len(str(expected.get("git_blob_sha1", ""))) == 40, f"Historical guard lacks Git blob id: {historical_path}")
    require(len(releases) == len(set(releases)), "Historical public releases are duplicated")
    if historical:
        law = contract.get("release_transition_law", {})
        require(law.get("superseded_release_bytes_remain_exact") is True, "Release transition law does not preserve superseded bytes")
    require(contract.get("qualification_boundary"), "Qualification boundary is missing")
    require(contract.get("close_law", {}).get("canonical_task_count_effect") == "none_without_exact_row_source", "Close law weakens canonical task-count boundary")
    return set(required_classes)


def validate_register(register: dict[str, Any], contract: dict[str, Any], required_classes: set[str]) -> list[str]:
    require(register.get("schema") == REGISTER_SCHEMA, "Unexpected register schema")
    require(register.get("contract_id") == contract.get("contract_id"), "Contract id drifted")
    donors = register.get("donors")
    gaps = register.get("gaps")
    require(isinstance(donors, list) and donors, "Donors are missing")
    require(isinstance(gaps, list), "Gaps must be a list")
    unique_ids(donors, "donor")
    unique_ids(gaps, "gap")
    scope_ids = {row["id"] for row in contract["archive_scopes"]}
    represented_classes = set()
    for donor in donors:
        require(donor.get("class") in required_classes, f"Unknown donor class: {donor.get('class')}")
        require(donor.get("custody_state") in ALLOWED_DONOR_STATES, f"Invalid donor state: {donor.get('id')}")
        require(set(donor.get("archive_scope_ids", [])).issubset(scope_ids), f"Donor references unknown scope: {donor.get('id')}")
        require(donor.get("claim_boundary"), f"Donor lacks claim boundary: {donor.get('id')}")
        represented_classes.add(donor["class"])
    open_required = []
    for gap in gaps:
        require(gap.get("class") in required_classes, f"Unknown gap class: {gap.get('class')}")
        require(gap.get("state") in {"open", "closed"}, f"Invalid gap state: {gap.get('id')}")
        for field in ("target", "admission", "failure_mode"):
            require(gap.get(field), f"Gap lacks {field}: {gap.get('id')}")
        represented_classes.add(gap["class"])
        if gap.get("required_for_close") and gap.get("state") != "closed":
            open_required.append(gap["id"])
    missing_classes = sorted(required_classes - represented_classes)
    require(not missing_classes, f"Custody classes lack donor or gap coverage: {missing_classes}")
    require(register.get("canonical_task_count_effect") == "none", "Register mutates canonical task count")
    if register.get("state") == "closed":
        require(not open_required, "Custody cannot close with required gaps open")
        not_archived = [row["id"] for row in donors if row.get("custody_state") not in {"archived_repo", "archived_external"}]
        require(not not_archived, f"Custody cannot close with unarchived donors: {not_archived}")
    else:
        require(open_required, "In-progress custody must name open close gates")
    return sorted(open_required)


def validate_observed(observed: dict[str, Any]) -> None:
    require(observed.get("schema") == "axm-tools/manzanita-observed-execution-ledger@1", "Unexpected observed ledger schema")
    require(observed.get("constitutional_source_state") == "original_row_level_register_unavailable", "Observed ledger hides constitutional source failure")
    records = observed.get("records")
    require(isinstance(records, list) and records, "Observed records are missing")
    prs = [row.get("pull_request") for row in records]
    require(len(prs) == len(set(prs)), "Observed pull requests are duplicated")
    require(all(row.get("state") == "merged_observed" for row in records), "Observed ledger includes a non-merged object as merged")
    require(all(row.get("canonical_task_count_effect") == "none" for row in records), "Observed record mutates task count")
    external = observed.get("external_campaign_state", {})
    require(external.get("release_state") == "HOLD", "Observed ledger weakens release hold")
    require(external.get("passed_campaigns") == [], "Observed ledger invents a passed external campaign")
    require(len(external.get("not_performed_campaigns", [])) == 10, "Observed ledger must retain ten unperformed campaigns")
    require(external.get("public_release_authorized") is False, "Observed ledger authorizes public release")
    require(observed.get("canonical_task_count_effect") == "none", "Observed ledger mutates canonical task count")


def validate_historical_public_guards(repo_root: Path, contract: dict[str, Any]) -> None:
    for guard in contract.get("historical_public_route_guards", []):
        commit = guard["commit"]
        route_path = clean_relative(guard["path"])
        observed_tree = git_value(repo_root, "rev-parse", f"{commit}:{route_path}")
        require(observed_tree == guard["tree"], f"Historical public release tree changed: {guard['release']}")
        for relative, expected in guard["files"].items():
            observed_blob = git_value(repo_root, "rev-parse", f"{commit}:{clean_relative(relative)}")
            require(
                observed_blob == expected["git_blob_sha1"],
                f"Historical public release changed: {guard['release']} {relative}",
            )


def validate_public_guard(repo_root: Path, contract: dict[str, Any]) -> None:
    for relative, expected in contract["public_route_guard"]["files"].items():
        path = resolve_regular_repo_file(repo_root, relative, "Guarded file")
        require(git_blob_sha1(path.read_bytes()) == expected["git_blob_sha1"], f"Historical public route changed: {relative}")


def validate_manifest(repo_root: Path, contract: dict[str, Any], contract_raw: bytes, register: dict[str, Any], register_raw: bytes, observed_raw: bytes, manifest: dict[str, Any], require_complete: bool) -> None:
    require(manifest.get("schema") == MANIFEST_SCHEMA, "Unexpected manifest schema")
    require(manifest.get("contract_id") == contract.get("contract_id"), "Manifest contract id drifted")
    generated = manifest.get("generated_from", {})
    require(generated.get("contract_sha256") == sha256_bytes(contract_raw), "Manifest was built from another contract")
    require(generated.get("register_sha256") == sha256_bytes(register_raw), "Manifest was built from another register")
    require(generated.get("observed_ledger_sha256") == sha256_bytes(observed_raw), "Manifest was built from another observed ledger")
    payload = dict(manifest)
    supplied = payload.pop("payload_sha256", None)
    require(supplied == sha256_bytes(canonical_bytes(payload)), "Manifest payload checksum is invalid")
    validate_historical_public_guards(repo_root, contract)
    validate_public_guard(repo_root, contract)
    files = manifest.get("files")
    require(isinstance(files, list) and files, "Manifest files are missing")
    paths = [row.get("path") for row in files]
    require(paths == sorted(paths), "Manifest files are not sorted")
    require(len(paths) == len(set(paths)), "Manifest paths are duplicated")
    require(manifest.get("source_file_count") == len(files), "Manifest file count drifted")
    require(manifest.get("source_bytes") == sum(row.get("bytes", -1) for row in files), "Manifest byte count drifted")
    for row in files:
        relative = clean_relative(str(row.get("path", "")))
        path = resolve_regular_repo_file(repo_root, relative, "Manifest source")
        payload_bytes = path.read_bytes()
        require(len(payload_bytes) == row.get("bytes"), f"Byte count changed: {relative}")
        require(sha256_bytes(payload_bytes) == row.get("sha256"), f"SHA-256 changed: {relative}")
        require(git_blob_sha1(payload_bytes) == row.get("git_blob_sha1"), f"Git blob changed: {relative}")
        require(row.get("scopes"), f"Manifest file has no scope: {relative}")
    expected_open = sorted(row["id"] for row in register["gaps"] if row.get("required_for_close") and row.get("state") != "closed")
    require(manifest.get("open_required_gaps") == expected_open, "Manifest open-gap set drifted")
    expected_status = "COMPLETE" if not expected_open else "PARTIAL"
    require(manifest.get("status") == expected_status, "Manifest status is false")
    require(manifest.get("canonical_task_count_effect") == "none", "Manifest mutates canonical task count")
    if require_complete:
        require(expected_status == "COMPLETE", "Custody remains partial")


def main() -> None:
    directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path, default=directory / "CUSTODY_CONTRACT.json")
    parser.add_argument("--register", type=Path, default=directory / "DONOR_REGISTER.json")
    parser.add_argument("--observed-ledger", type=Path, default=directory / "OBSERVED_EXECUTION_LEDGER.json")
    parser.add_argument("--manifest", type=Path, default=directory / "CUSTODY_MANIFEST.json")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    contract, contract_raw = load_json(args.contract)
    register, register_raw = load_json(args.register)
    observed, observed_raw = load_json(args.observed_ledger)
    manifest, _ = load_json(args.manifest)
    required = validate_contract(contract)
    open_gaps = validate_register(register, contract, required)
    validate_observed(observed)
    validate_manifest(repo_root, contract, contract_raw, register, register_raw, observed_raw, manifest, args.require_complete)
    print(json.dumps({
        "result": "PASS",
        "custody_status": manifest["status"],
        "repo_resident_files": manifest["source_file_count"],
        "repo_resident_bytes": manifest["source_bytes"],
        "open_required_gaps": len(open_gaps),
        "qualification": "custody consistency only",
        "canonical_task_count_effect": "none",
        "manifest_sha256": manifest["payload_sha256"],
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except CustodyValidationError as exc:
        raise SystemExit(str(exc)) from exc
