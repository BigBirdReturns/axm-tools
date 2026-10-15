#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SUCCESS = "PASS_WINDOWS_NATIVE_RUNTIME_RESOLVER_AND_SHIMS_QUALIFIED"
ALIASES = {"py", "python", "python3"}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("receipt root must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, observed: Any) -> None:
        checks.append({"name": name, "passed": bool(condition), "observed": observed})
        if not condition:
            raise AssertionError(name)

    receipt = load(args.receipt)
    check("schema", receipt.get("schema") == "manzanita/v31-windows-native-runtime-qualification-receipt@1", receipt.get("schema"))
    check("terminal result", receipt.get("result") == SUCCESS, receipt.get("result"))
    runtime = receipt.get("runtime") or {}
    selected = runtime.get("selected") or {}
    version = selected.get("version") or []
    check("runtime resolution result", runtime.get("result") == "PASS_SUPPORTED_PYTHON_RUNTIME_RESOLVED", runtime.get("result"))
    check("version floor", len(version) >= 2 and tuple(version[:2]) >= (3, 10), version)
    check("selected executable", isinstance(selected.get("executable"), str) and bool(selected.get("executable")), selected.get("executable"))
    broken = receipt.get("broken_candidate_probe") or {}
    check("broken candidate refused", broken.get("probe_passed") is False, broken)
    aliases = receipt.get("alias_observations") or []
    names = {row.get("alias") for row in aliases if isinstance(row, dict)}
    check("all aliases observed", names == ALIASES, sorted(names))
    check("all aliases passed", all(row.get("exit_code") == 0 and isinstance(row.get("parsed"), dict) for row in aliases), aliases)
    authority = receipt.get("authority") or {}
    check("no product mutation", authority.get("product_files_modified") == 0, authority)
    check("operator host not implied", authority.get("operator_host_execution_proved") is False, authority)
    check("no materialized production inputs", authority.get("production_inputs_materialized") == 0, authority)
    check("admission held", authority.get("admission_invoked") is False, authority)
    check("v31 absent", authority.get("v31_created") is False, authority)
    check("merge held", authority.get("merge_authorized") is False, authority)
    check("release held", authority.get("release_authorized") is False, authority)
    check("public effects absent", authority.get("public_route_effect") == authority.get("pages_effect") == authority.get("external_effect") == "none", authority)
    check("PowerShell edition recorded", bool((receipt.get("environment") or {}).get("powershell_edition")), receipt.get("environment"))
    check("internal checks all pass", all(row.get("passed") is True for row in receipt.get("checks", [])), receipt.get("checks"))

    output = {
        "schema": "manzanita/v31-windows-native-runtime-qualification-validation@1",
        "result": "PASS_WINDOWS_NATIVE_RUNTIME_RECEIPT_VALIDATED",
        "source_receipt": str(args.receipt),
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "checks": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
