#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_RESULT = "PASS_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY"
EXPECTED_PACKAGE = {
    "name": "MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip",
    "bytes": 553_074,
    "sha256": "2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738",
}
EXPECTED_DEPENDENCY = {
    "bytes": 500_961,
    "sha256": "9821a140c507991e19e0f53d2d576e31b75ec4f11ff6ff8b7ab67677d95151a4",
}
ALIASES = {"py.cmd", "python.cmd", "python3.cmd", "py", "python", "python3"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} root must be an object")
    return value


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recursive_find(value: Any, key: str) -> list[Any]:
    matches: list[Any] = []
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                matches.append(current_value)
            matches.extend(recursive_find(current_value, key))
    elif isinstance(value, list):
        for item in value:
            matches.extend(recursive_find(item, key))
    return matches


def contains_value(value: Any, expected: Any) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(contains_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(contains_value(item, expected) for item in value)
    return False


def all_internal_checks_pass(receipt: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    rows = receipt.get("checks")
    if not isinstance(rows, list) or not rows:
        return False, []
    normalized = [row for row in rows if isinstance(row, dict)]
    return len(normalized) == len(rows) and all(row.get("passed") is True for row in normalized), normalized


def alias_rows(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for key in ("alias_observations", "aliases", "shim_observations"):
        value = receipt.get(key)
        if isinstance(value, list):
            candidates.extend(row for row in value if isinstance(row, dict))
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-receipt", type=Path, required=True)
    parser.add_argument("--acquisition-receipt", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    replay = load(args.replay_receipt)
    acquisition = load(args.acquisition_receipt)
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, observed: Any) -> None:
        checks.append({"name": name, "passed": bool(condition), "observed": observed})
        if not condition:
            raise AssertionError(name)

    check("replay receipt schema", replay.get("schema") == "manzanita/v31-operator-execution-bootstrap-windows-platform-replay@3-r1", replay.get("schema"))
    check("replay terminal result", replay.get("result") == EXPECTED_RESULT, replay.get("result"))
    check("Windows host observed", replay.get("windows_host") is True, replay.get("windows_host"))

    package = replay.get("package") or {}
    check("replay package filename", package.get("name") == EXPECTED_PACKAGE["name"], package)
    check("replay package byte count", package.get("bytes") == EXPECTED_PACKAGE["bytes"], package)
    check("replay package SHA-256", package.get("sha256") == EXPECTED_PACKAGE["sha256"], package)
    check("mounted package byte count", args.package.stat().st_size == EXPECTED_PACKAGE["bytes"], args.package.stat().st_size)
    check("mounted package SHA-256", sha256(args.package) == EXPECTED_PACKAGE["sha256"], sha256(args.package))

    check("acquisition result", acquisition.get("result") == "PASS_V31_V3_R1_EXACT_PACKAGE_ACQUIRED_VERIFIED_AND_ISOLATED", acquisition.get("result"))
    acquired_expected = acquisition.get("expected") or {}
    check("acquisition exact identity", acquired_expected.get("bytes") == EXPECTED_PACKAGE["bytes"] and acquired_expected.get("sha256") == EXPECTED_PACKAGE["sha256"], acquired_expected)
    check("acquisition ZIP controls", all((acquisition.get("zip") or {}).get(key) is True for key in ("paths_safe", "paths_unique", "casefold_unique", "symlinks_absent")) and (acquisition.get("zip") or {}).get("crc") == "PASS", acquisition.get("zip"))

    runtime = replay.get("runtime") or {}
    version = runtime.get("version") or runtime.get("version_info") or []
    check("runtime minimum version", isinstance(version, list) and len(version) >= 2 and tuple(int(item) for item in version[:2]) >= (3, 10), version)
    check("runtime executable recorded", isinstance(runtime.get("executable"), str) and bool(runtime.get("executable")), runtime)

    passed, internal = all_internal_checks_pass(replay)
    check("all package-owned replay checks pass", passed, {"passed": sum(row.get("passed") is True for row in internal), "total": len(internal)})

    dependency_evidence = [
        value
        for key in ("dependency", "preparation", "nested_dependency")
        for value in recursive_find(replay, key)
        if isinstance(value, dict)
    ]
    dependency_bound = contains_value(replay, EXPECTED_DEPENDENCY["sha256"]) and contains_value(replay, EXPECTED_DEPENDENCY["bytes"])
    check("exact nested dependency bound", dependency_bound, dependency_evidence[:5])

    aliases = alias_rows(replay)
    observed_aliases = {
        str(row.get("alias") or row.get("name") or "").casefold()
        for row in aliases
    }
    expected_alias_names = {"py", "python", "python3"}
    normalized_aliases = {name.removesuffix(".cmd") for name in observed_aliases}
    check("py, python, and python3 aliases observed", expected_alias_names.issubset(normalized_aliases), sorted(observed_aliases))
    check("all alias executions succeeded", all((row.get("exit_code") == 0 or row.get("returncode") == 0) for row in aliases), aliases)
    check("alias argument continuity", all((row.get("parsed") or {}).get("argv") == ["--alpha", "value with spaces", "-x"] for row in aliases), aliases)

    collection_sha_values = []
    for key in ("first_collection", "second_collection", "collection_first", "collection_second"):
        for value in recursive_find(replay, key):
            if isinstance(value, dict) and isinstance(value.get("sha256"), str):
                collection_sha_values.append(value["sha256"])
    if len(collection_sha_values) < 2:
        collection_sha_values = [
            value
            for value in recursive_find(replay, "sha256")
            if isinstance(value, str) and value not in {EXPECTED_PACKAGE["sha256"], EXPECTED_DEPENDENCY["sha256"]}
        ]
    duplicate_sha = any(collection_sha_values.count(value) >= 2 for value in set(collection_sha_values))
    check("two-pass deterministic collection", duplicate_sha, collection_sha_values)
    check("collection manifest omits variable built_at", not contains_value(replay, "built_at"), None)

    authority = replay.get("authority") or {}
    check("replay-only authority", authority.get("replay_only") is True, authority)
    check("operator storage not read", authority.get("operator_storage_read") is False, authority)
    check("production inputs remain zero", authority.get("production_inputs_materialized") == 0, authority)
    check("admission not invoked", authority.get("admission_invoked") is False, authority)
    check("product mutation absent", authority.get("product_mutation") is False, authority)
    check("merge and release held", authority.get("merge_authorized") is False and authority.get("release_authorized") is False, authority)
    check("public effects absent", authority.get("public_route_effect") == authority.get("pages_effect") == authority.get("external_effect") == "none", authority)

    acquisition_authority = acquisition.get("authority") or {}
    check("acquisition authority held", acquisition_authority.get("operator_storage_read") is False and acquisition_authority.get("production_inputs_materialized") == 0 and acquisition_authority.get("production_admission_invoked") is False and acquisition_authority.get("accepted_parent_extracted") is False and acquisition_authority.get("product_mutation") is False, acquisition_authority)

    output = {
        "schema": "manzanita/v31-v3-r1-full-windows-platform-replay-validation@1",
        "result": "PASS_V31_V3_R1_FULL_WINDOWS_PLATFORM_REPLAY_VALIDATED",
        "observed_at": now_iso(),
        "source_receipts": {
            "acquisition": str(args.acquisition_receipt),
            "platform_replay": str(args.replay_receipt),
        },
        "package": {
            "path": str(args.package),
            "bytes": args.package.stat().st_size,
            "sha256": sha256(args.package),
        },
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "checks": checks,
        "standing": {
            "exact_full_package_windows_replay": "PASS",
            "operator_workstation_execution": "NOT_OBSERVED",
            "operator_storage_search": "NOT_PERFORMED",
            "production_inputs_materialized": 0,
            "production_admission": "NOT_INVOKED",
            "accepted_parent_extracted": False,
            "v31_created": False,
            "product_files_modified": 0,
            "operator_visual_acceptance": "ABSENT",
            "merge_authorized": False,
            "release_authorized": False,
            "public_route_effect": "none",
            "pages_effect": "none",
            "external_effect": "none",
        },
    }
    atomic_json(args.output, output)
    print(f"PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
