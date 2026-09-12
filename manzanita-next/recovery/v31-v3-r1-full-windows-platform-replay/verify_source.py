#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "WINDOWS_PLATFORM_REPLAY_CONTRACT.json",
    "fetch_exact_v3_r1_package.py",
    "validate_windows_platform_replay.py",
    "verify_source.py",
    "README.md",
]
EXPECTED_PACKAGE = {
    "filename": "MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip",
    "bytes": 553_074,
    "sha256": "2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738",
}
FORBIDDEN_IMPORTS = {"requests", "http.client", "socket", "ftplib"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_python(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, observed: Any) -> None:
        checks.append({"name": name, "passed": bool(condition), "observed": observed})
        if not condition:
            raise AssertionError(name)

    for relative in REQUIRED:
        path = ROOT / relative
        check(f"required file: {relative}", path.is_file(), str(path))

    contract = json.loads((ROOT / "WINDOWS_PLATFORM_REPLAY_CONTRACT.json").read_text(encoding="utf-8"))
    check("contract schema", contract.get("schema") == "manzanita/v31-v3-r1-full-windows-platform-replay-contract@1", contract.get("schema"))
    check("object class bounded", contract.get("object_class") == "bounded exact-package Windows platform replay", contract.get("object_class"))
    check("exact package binding", contract.get("source_package", {}).get("filename") == EXPECTED_PACKAGE["filename"] and contract.get("source_package", {}).get("bytes") == EXPECTED_PACKAGE["bytes"] and contract.get("source_package", {}).get("sha256") == EXPECTED_PACKAGE["sha256"], contract.get("source_package"))
    check("exact terminal result", contract.get("execution", {}).get("expected_terminal_result") == "PASS_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY", contract.get("execution"))
    check("operator storage held", contract.get("execution", {}).get("operator_storage_read") is False, contract.get("execution"))
    check("production admission held", contract.get("execution", {}).get("production_admission") is False, contract.get("execution"))
    authority = contract.get("authority") or {}
    check("production inputs zero", authority.get("production_inputs_materialized") == 0, authority)
    check("operator workstation unobserved", authority.get("operator_workstation_execution_observed") is False, authority)
    check("product authority held", authority.get("product_files_modified") == 0 and authority.get("v31_created") is False and authority.get("operator_visual_acceptance") == "ABSENT", authority)
    check("release authority held", authority.get("merge_authorized") is False and authority.get("release_authorized") is False and authority.get("public_route_effect") == authority.get("pages_effect") == authority.get("external_effect") == "none", authority)

    for relative in ["fetch_exact_v3_r1_package.py", "validate_windows_platform_replay.py", "verify_source.py"]:
        path = ROOT / relative
        imports = parse_python(path)
        check(f"Python parses: {relative}", True, sha256(path))
        prohibited = sorted(name for name in imports if name in FORBIDDEN_IMPORTS or any(name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORTS))
        check(f"no prohibited network/control imports: {relative}", not prohibited, prohibited)

    fetch_source = (ROOT / "fetch_exact_v3_r1_package.py").read_text(encoding="utf-8")
    validation_source = (ROOT / "validate_windows_platform_replay.py").read_text(encoding="utf-8")
    check("fetch gate enforces exact byte count", "received != EXPECTED_BYTES" in fetch_source and "received > EXPECTED_BYTES" in fetch_source, None)
    check("fetch gate enforces exact SHA-256", "observed_sha != EXPECTED_SHA256" in fetch_source, None)
    check("fetch gate validates ZIP CRC", "archive.testzip()" in fetch_source, None)
    check("fetch gate refuses traversal", "PurePosixPath" in fetch_source and 'part in {"", ".", ".."}' in fetch_source, None)
    check("fetch gate refuses symlinks", "is_symlink" in fetch_source and "symlink ZIP member refused" in fetch_source, None)
    check("replay validator binds exact terminal result", "EXPECTED_RESULT" in validation_source and "PASS_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY" in validation_source, None)
    check("replay validator holds operator storage", 'authority.get("operator_storage_read") is False' in validation_source, None)
    check("replay validator holds product mutation", 'authority.get("product_mutation") is False' in validation_source, None)

    receipt = {
        "schema": "manzanita/v31-v3-r1-full-windows-platform-replay-source-verification@1",
        "result": "PASS_V31_V3_R1_FULL_WINDOWS_PLATFORM_REPLAY_SOURCE_VERIFIED",
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "checks": checks,
        "files": [
            {
                "path": relative,
                "bytes": (ROOT / relative).stat().st_size,
                "sha256": sha256(ROOT / relative),
            }
            for relative in sorted(REQUIRED)
        ],
        "authority": authority,
    }
    output = ROOT / "SOURCE_VERIFICATION_RECEIPT.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
