#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OBSERVATION = "WINDOWS_NATIVE_QUALIFICATION_OBSERVATION_V1.json"
REQUIRED = [
    "RUNTIME_RESOLVER_CONTRACT.json",
    "resolve_v31_python.ps1",
    "run_windows_runtime_qualification.ps1",
    "RUN_WINDOWS_RUNTIME_QUALIFICATION.cmd",
    "validate_runtime_receipt.py",
    "verify_source.py",
    OBSERVATION,
    "README.md",
]
FORBIDDEN_PY_IMPORTS = {"requests", "urllib.request", "http.client", "socket", "ftplib"}
EXPECTED_AUTHORITY = {
    "product_files_modified": 0,
    "operator_host_execution_proved": False,
    "production_inputs_materialized": 0,
    "admission_invoked": False,
    "v31_created": False,
    "merge_authorized": False,
    "release_authorized": False,
    "public_route_effect": "none",
    "pages_effect": "none",
    "external_effect": "none",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_python(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for name in imported:
        if name in FORBIDDEN_PY_IMPORTS or any(name.startswith(p + ".") for p in FORBIDDEN_PY_IMPORTS):
            raise AssertionError(f"forbidden network import in {path.name}: {name}")


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, observed: Any) -> None:
        checks.append({"name": name, "passed": bool(condition), "observed": observed})
        if not condition:
            raise AssertionError(name)

    for rel in REQUIRED:
        path = ROOT / rel
        check(f"required file: {rel}", path.is_file(), str(path))

    contract = json.loads((ROOT / "RUNTIME_RESOLVER_CONTRACT.json").read_text(encoding="utf-8"))
    check("contract schema", contract.get("schema") == "manzanita/v31-windows-native-runtime-qualification-contract@1", contract.get("schema"))
    check("success result", contract.get("success_result") == "PASS_WINDOWS_NATIVE_RUNTIME_RESOLVER_AND_SHIMS_QUALIFIED", contract.get("success_result"))
    check("candidate order", contract["runtime_contract"]["candidate_order"] == ["PATH_PY3_LAUNCHER", "PATH_PYTHON3", "PATH_PYTHON", "CODEX_DEPENDENCY_RUNTIME", "CODEX_RUNTIME", "USER_LOCAL_PYTHON", "PROGRAM_FILES_PYTHON"], contract["runtime_contract"]["candidate_order"])
    check("minimum Python", contract["runtime_contract"]["minimum_python"] == [3, 10], contract["runtime_contract"]["minimum_python"])
    check("contract authority held", contract["authority"] == EXPECTED_AUTHORITY, contract["authority"])

    observation = json.loads((ROOT / OBSERVATION).read_text(encoding="utf-8"))
    check("observation schema", observation.get("schema") == "manzanita/v31-windows-native-runtime-qualification-observation@1", observation.get("schema"))
    check("observation disposition", observation.get("disposition") == "PASS_WITH_PRODUCTION_AND_OPERATOR_HOST_AUTHORITIES_HELD", observation.get("disposition"))
    check("observation venue", observation.get("repository") == "BigBirdReturns/axm-tools" and observation.get("pull_request") == 142, {"repository": observation.get("repository"), "pull_request": observation.get("pull_request")})
    workflow = observation.get("workflow") or {}
    artifact = workflow.get("artifact") or {}
    check("observed run identity", workflow.get("run_id") == 33531386064 and workflow.get("run_number") == 4 and workflow.get("job_id") == 99935133215 and workflow.get("conclusion") == "success", workflow)
    check("observed artifact identity", artifact.get("id") == 9809864919 and artifact.get("bytes") == 5235 and artifact.get("sha256") == "62363baedaafa25c65cd4681e7003b207d49ffd9f2ae96061ca12ba5f3f5af1f", artifact)
    runtime = observation.get("runtime") or {}
    check("observed resolver result", runtime.get("resolver_result") == "PASS_SUPPORTED_PYTHON_RUNTIME_RESOLVED", runtime.get("resolver_result"))
    version = runtime.get("version") or []
    check("observed runtime floor", len(version) >= 2 and tuple(version[:2]) >= (3, 10), version)
    check("observed alias coverage", runtime.get("compatibility_aliases") == ["py", "python", "python3"] and runtime.get("alias_exit_codes") == {"py": 0, "python": 0, "python3": 0} and runtime.get("executable_continuity") == "PASS", runtime)
    qualification = observation.get("qualification") or {}
    check("observed qualification counts", qualification.get("source_verification") == {"passed": 25, "total": 25} and qualification.get("runtime_campaign") == {"passed": 12, "total": 12} and qualification.get("receipt_validation") == {"passed": 18, "total": 18}, qualification)
    check("observed terminal results", qualification.get("terminal_result") == "PASS_WINDOWS_NATIVE_RUNTIME_RESOLVER_AND_SHIMS_QUALIFIED" and qualification.get("validation_result") == "PASS_WINDOWS_NATIVE_RUNTIME_RECEIPT_VALIDATED", qualification)
    lineage = observation.get("failure_and_repair_lineage") or []
    check("four-run falsification lineage", len(lineage) == 4 and [row.get("run_number") for row in lineage] == [1, 2, 3, 4] and all(row.get("result") == "FAIL_WINDOWS_NATIVE_RUNTIME_QUALIFICATION_NOT_COMPLETED" for row in lineage[:3]) and lineage[3].get("result") == "PASS_WINDOWS_NATIVE_RUNTIME_RESOLVER_AND_SHIMS_QUALIFIED", lineage)
    observed_authority = observation.get("authority") or {}
    check("operator workstation remains unobserved", observed_authority.get("github_hosted_windows_runtime_qualified") is True and observed_authority.get("operator_workstation_execution_observed") is False and observed_authority.get("operator_storage_search_observed") is False, observed_authority)
    check("production and release authority held", observed_authority.get("production_inputs_materialized") == 0 and observed_authority.get("required_production_inputs") == 5 and observed_authority.get("provenance_aware_intake_invoked") is False and observed_authority.get("provenance_wrapper_invoked") is False and observed_authority.get("underlying_v1_admission_invoked") is False and observed_authority.get("accepted_parent_extracted") is False and observed_authority.get("v31_created") is False and observed_authority.get("product_files_modified") == 0 and observed_authority.get("operator_visual_acceptance") == "ABSENT" and observed_authority.get("merge_authorized") is False and observed_authority.get("release_authorized") is False and observed_authority.get("public_route_effect") == observed_authority.get("pages_effect") == observed_authority.get("external_effect") == "none", observed_authority)

    for path in [ROOT / "validate_runtime_receipt.py", ROOT / "verify_source.py"]:
        check_python(path)
        check(f"Python parses: {path.name}", True, sha256(path))
    ps = (ROOT / "resolve_v31_python.ps1").read_text(encoding="utf-8")
    runner = (ROOT / "run_windows_runtime_qualification.ps1").read_text(encoding="utf-8")
    cmd = (ROOT / "RUN_WINDOWS_RUNTIME_QUALIFICATION.cmd").read_bytes()
    check("resolver exposes required functions", all(token in ps for token in ["function Invoke-V31PythonProbe", "function Resolve-V31Python", "function Install-V31PythonShims"]), sha256(ROOT / "resolve_v31_python.ps1"))
    check("resolver uses argument-preserving Python driver", "Invoke-ResolvedPython.py" in ps and "subprocess.run([executable, *prefix, *arguments]" in ps and "--strip-py3" in ps, sha256(ROOT / "resolve_v31_python.ps1"))
    check("runner refuses broken executable candidate", "broken executable candidate is refused" in runner and "System32\\cmd.exe" in runner, sha256(ROOT / "run_windows_runtime_qualification.ps1"))
    check("runner exercises all aliases", all(token in runner for token in ["name='py'", "name='python'", "name='python3'"]), sha256(ROOT / "run_windows_runtime_qualification.ps1"))
    check("cmd pins working directory", b'cd /d "%~dp0"' in cmd, sha256(ROOT / "RUN_WINDOWS_RUNTIME_QUALIFICATION.cmd"))
    check("cmd uses Windows PowerShell", b"powershell.exe" in cmd, sha256(ROOT / "RUN_WINDOWS_RUNTIME_QUALIFICATION.cmd"))
    check("cmd uses CRLF", b"\r\n" in cmd and cmd.replace(b"\r\n", b"").find(b"\n") == -1, len(cmd))
    operational = ["resolve_v31_python.ps1", "run_windows_runtime_qualification.ps1", "RUN_WINDOWS_RUNTIME_QUALIFICATION.cmd", "validate_runtime_receipt.py"]
    combined = "\n".join((ROOT / name).read_text(encoding="utf-8", errors="ignore") for name in operational)
    for token in ["Invoke-WebRequest", "Start-BitsTransfer", "System.Net.WebClient", "requests.get", "urllib.request.urlopen"]:
        check(f"network actuator absent: {token}", token not in combined, token)
    result = {
        "schema": "manzanita/v31-windows-native-runtime-source-verification@1",
        "result": "PASS_WINDOWS_NATIVE_RUNTIME_QUALIFICATION_SOURCE_VERIFIED",
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "checks": checks,
        "files": [{"path": rel, "bytes": (ROOT / rel).stat().st_size, "sha256": sha256(ROOT / rel)} for rel in sorted(REQUIRED)],
    }
    out = ROOT / "SOURCE_VERIFICATION_RECEIPT.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
