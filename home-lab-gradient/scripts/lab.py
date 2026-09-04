#!/usr/bin/env python3
"""Authoritative runner for the Home Lab Capability Gradient.

The runner keeps mutable evidence and receipts outside the source tree by
default. Source JSON defines the capability graph and experiment catalog;
operator state records only what the estate has actually observed or qualified.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from evidence import (
    EVIDENCE_SCHEMA,
    canonical_receipt_id,
    ingest_receipts,
    load_json,
    make_receipt,
    sha256_file,
    write_json,
)
from planner import PlannerError, build_plan, parse_inputs, read_json, sha256_json, canonical_bytes
from render import (
    AUTHORITATIVE_COMPRESSOR_SHA256,
    RenderError,
    canonical_gzip,
    compressor_fingerprint,
    write_page,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

WINDOWS_HOST_SCHEMA = "axm-community-lab/windows-host-observation@1"
LINUX_HOST_SCHEMA = "axm-community-lab/host-observation@2"
COLLECTOR_SCHEMA = "axm-community-lab/host-observation-collector@1"
HOST_OBSERVATION_RECEIPT_SCHEMA = "axm-community-lab/host-observation-receipt@1"
HOST_OBSERVATION_RECEIPT_SUFFIX = ".receipt.json"
HOST_OBSERVATION_RECEIPT_REQUIRED = (
    "schema",
    "observation_schema",
    "collector_schema",
    "platform",
    "host_id",
    "observed_at",
    "observation_sha256",
    "observation_file_name",
    "observation_file_sha256",
    "observation_file_bytes",
    "host_fingerprint_sha256",
    "accelerator_identity_sha256",
    "accelerator_identity_count",
    "collector_source_sha256",
    "python_executable_sha256",
    "seed_id",
    "seed_manifest_sha256",
    "carries_observation_body",
    "claim_boundary",
    "receipt_sha256",
)
HOST_OBSERVATION_RECEIPT_JOIN_COORDINATES = (
    "schema",
    "platform",
    "host_id",
    "observed_at",
    "observation_sha256",
)
REQUIRED_RUNTIME_NAMES = ("python", "git", "ollama", "docker", "wsl", "nvidia-smi")
PROHIBITED_FIELD_MARKERS = (
    "serial",
    "machine_guid",
    "machine-id",
    "mac_address",
    "ip_address",
    "credential",
    "private_key",
    "tailscale",
    "token",
)
MAC_RE = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
IPV4_RE = re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b")
# Textual IPv6 always has either all eight groups or a "::" compression.
# Requiring one of those avoids false refusals on PCI bus ids (0000:01:00.0)
# and wall-clock timestamps (01:00:00), which share the shorter hex:hex shape.
# The boundary guards matter as much as the shape: without them a "::" after
# any hex-ish letter matches, so ordinary prose ("Usage::") reads as an address
# and would refuse a clean observation.
IPV6_RE = re.compile(
    r"(?<![0-9A-Za-z:])"
    r"(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|::(?:[0-9A-Fa-f]{1,4}:){0,6}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){2,7}:(?![0-9A-Za-z])"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,4}"
    r")"
    r"(?![0-9A-Za-z:])"
)

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def observation_digest(observation: Mapping[str, Any]) -> str:
    normalized = {k: v for k, v in observation.items() if k != "observation_sha256"}
    return hashlib.sha256(canonical_bytes(normalized)).hexdigest()


def retains_value(value: Any) -> bool:
    """True when a prohibited-marker field actually carries an identifier.

    A collector declares its refusals explicitly (``"serial_numbers_collected":
    false``, ``"machine_guid": null``), so an empty or negative declaration is
    compliance, not retention. Membership in a set literal cannot express this:
    ``[]`` and ``{}`` are unhashable.
    """
    if value is None or value is False:
        return False
    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        return bool(value)
    return True


def collect_private_identifier_failures(payload: Any, host_id: str, *, path: str = "observation") -> list[str]:
    failures: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            label = f"{path}.{key}"
            lower = str(key).lower()
            if any(marker in lower for marker in PROHIBITED_FIELD_MARKERS) and retains_value(value):
                failures.append(f"{host_id}: prohibited private field retained at {label}")
            failures.extend(collect_private_identifier_failures(value, host_id, path=label))
        return failures
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            failures.extend(collect_private_identifier_failures(item, host_id, path=f"{path}[{index}]"))
        return failures
    if isinstance(payload, str):
        if MAC_RE.search(payload):
            failures.append(f"{host_id}: prohibited MAC pattern retained")
        if IPV4_RE.search(payload):
            failures.append(f"{host_id}: prohibited IP pattern retained")
        if IPV6_RE.search(payload):
            failures.append(f"{host_id}: prohibited IPv6 pattern retained")
    return failures


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("T", "-").replace("Z", "Z")


def default_state_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "AXM" / "home-lab-gradient"
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "axm" / "home-lab-gradient"


def state_paths(state_dir: Path) -> dict[str, Path]:
    return {
        "root": state_dir,
        "estate": state_dir / "estate.json",
        "evidence": state_dir / "evidence.json",
        "plan": state_dir / "plan.json",
        "runs": state_dir / "runs",
        "functions": state_dir / "functions",
    }


def init_state(state_dir: Path, *, overwrite: bool = False) -> dict[str, Path]:
    paths = state_paths(state_dir)
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["runs"].mkdir(parents=True, exist_ok=True)
    paths["functions"].mkdir(parents=True, exist_ok=True)
    for key, source in (("estate", DATA / "estate.json"), ("evidence", DATA / "evidence.json")):
        target = paths[key]
        if overwrite or not target.exists():
            shutil.copy2(source, target)
    marker = paths["root"] / "STATE_BOUNDARY.txt"
    if overwrite or not marker.exists():
        marker.write_text(
            "This directory contains operator-owned Home Lab Capability Gradient state.\n"
            "Receipts and observations here are not source files and are not committed automatically.\n",
            encoding="utf-8",
        )
    return paths


def source_docs() -> tuple[dict[str, Any], dict[str, Any]]:
    return read_json(DATA / "goals.json"), read_json(DATA / "experiments.json")


def build_state_plan(state_dir: Path, *, generated_at: str, output: Path | None = None) -> dict[str, Any]:
    paths = init_state(state_dir)
    goals_doc, experiments_doc = source_docs()
    plan = build_plan(
        read_json(paths["estate"]),
        goals_doc,
        experiments_doc,
        read_json(paths["evidence"]),
        generated_at=generated_at,
    )
    destination = output or paths["plan"]
    write_json(destination, plan)
    return plan


def find_experiment(experiment_id: str, experiments_doc: Mapping[str, Any]) -> dict[str, Any]:
    for raw in experiments_doc.get("experiments", []):
        if isinstance(raw, Mapping) and raw.get("id") == experiment_id:
            return dict(raw)
    raise PlannerError(f"unknown experiment: {experiment_id}")


def type_matches(value: Any, expected: str) -> bool:
    table = {
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "null": lambda item: item is None,
    }
    if expected not in table:
        raise PlannerError(f"unsupported contract type: {expected}")
    return table[expected](value)


def dotted_get(value: Mapping[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def validate_output_contract(output: Mapping[str, Any], contract: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    output_contract = contract.get("output_contract")
    if not isinstance(output_contract, Mapping):
        return ["output_contract missing"]
    required_fields = output_contract.get("required_fields", {})
    if not isinstance(required_fields, Mapping):
        return ["output_contract.required_fields must be an object"]
    for field, expected in required_fields.items():
        try:
            observed = dotted_get(output, str(field))
        except KeyError:
            failures.append(f"missing output field {field}")
            continue
        if not type_matches(observed, str(expected)):
            failures.append(f"output field {field} is not {expected}")
    for field in output_contract.get("nonempty_fields", []):
        try:
            observed = dotted_get(output, str(field))
        except KeyError:
            failures.append(f"missing nonempty output field {field}")
            continue
        if observed is None or (isinstance(observed, (str, list, dict)) and len(observed) == 0):
            failures.append(f"output field {field} is empty")
    for field, expected in output_contract.get("expected_values", {}).items():
        try:
            observed = dotted_get(output, str(field))
        except KeyError:
            failures.append(f"missing expected output field {field}")
            continue
        if observed != expected:
            failures.append(f"output field {field} expected {expected!r}, got {observed!r}")
    return failures


def scaffold_function(function_id: str, destination: Path, *, model: str, host: str) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    adapter = ROOT / "scripts" / "ollama_function.py"
    implementation = {
        "provider": "ollama-local",
        "model": model,
        "endpoint": host,
        "adapter": "scripts/ollama_function.py",
        "adapter_sha256": sha256_file(adapter),
        "argv": [
            "{python}",
            "{tool_root}/scripts/ollama_function.py",
            "--model",
            model,
            "--host",
            host,
            "--input",
            "{input_path}",
            "--output",
            "{output_path}",
        ],
        "working_directory": "{tool_root}",
        "environment": {},
    }
    contract = {
        "schema": "axm-community-lab/function-contract@1",
        "id": function_id,
        "version": "0.1.0-draft",
        "purpose": "Bounded local inference through the already observed RTX 4060 Ollama route.",
        "authority": "draft until qualification receipt passes",
        "implementation": implementation,
        "implementation_sha256": sha256_json(implementation),
        "input_contract": {
            "required_fields": {"prompt": "string"},
            "max_prompt_chars": 4096,
        },
        "output_contract": {
            "required_fields": {
                "schema": "string",
                "status": "string",
                "model": "string",
                "model_digest": "string",
                "prompt_sha256": "string",
                "response": "string",
                "provider": "object",
            },
            "nonempty_fields": ["model", "model_digest", "prompt_sha256", "response"],
            "expected_values": {
                "schema": "axm-community-lab/bounded-local-inference-output@1",
                "status": "PASS",
                "model": model,
            },
            "stable_fields": ["schema", "status", "model", "model_digest", "prompt_sha256"],
        },
        "execution": {
            "timeout_seconds": 150,
            "qualification_attempts": 2,
            "shell": False,
            "concurrency": 1,
            "cleanup": "invocation temp files retained only inside the receipt run directory",
        },
        "failure_semantics": {
            "2": "invalid fixture or input contract",
            "3": "provider unavailable or timed out",
            "4": "provider returned no response text",
            "other_nonzero": "bounded execution failure",
        },
        "claim_boundary": "Qualification proves this exact adapter, model digest, interface, and fixture replay on one observed worker. It does not prove semantic quality, universal determinism, alternate-worker eligibility, or production scheduling gain.",
    }
    fixture = {
        "schema": "axm-community-lab/function-fixture@1",
        "function_id": function_id,
        "input": {
            "prompt": "Return only the integer result of 12 * 13 + 5.",
            "keep_alive": "5m",
        },
        "purpose": "Small replay fixture for interface, model identity, timeout, and cleanup qualification.",
    }
    contract_path = destination / "function-contract.json"
    fixture_path = destination / "function-fixture.json"
    write_json(contract_path, contract)
    write_json(fixture_path, fixture)
    return contract_path, fixture_path


def qualify_function(
    *,
    contract_path: Path,
    fixture_path: Path,
    state_dir: Path,
    generated_at: str,
    ingest: bool,
) -> tuple[Path, dict[str, Any]]:
    paths = init_state(state_dir)
    contract = load_json(contract_path)
    fixture = load_json(fixture_path)
    if contract.get("schema") != "axm-community-lab/function-contract@1":
        raise PlannerError("unsupported function contract schema")
    if fixture.get("schema") != "axm-community-lab/function-fixture@1":
        raise PlannerError("unsupported function fixture schema")
    if fixture.get("function_id") != contract.get("id"):
        raise PlannerError("fixture function_id does not match contract")
    implementation = contract.get("implementation")
    execution = contract.get("execution")
    if not isinstance(implementation, Mapping) or not isinstance(execution, Mapping):
        raise PlannerError("contract requires implementation and execution objects")
    argv_template = implementation.get("argv")
    if not isinstance(argv_template, list) or not argv_template or not all(isinstance(x, str) for x in argv_template):
        raise PlannerError("contract implementation.argv must be a non-empty string array")
    attempts = int(execution.get("qualification_attempts", 2))
    timeout = float(execution.get("timeout_seconds", 120))
    if attempts < 2 or attempts > 5:
        raise PlannerError("qualification_attempts must be between 2 and 5")

    run_dir = paths["runs"] / f"{stamp(generated_at)}-freeze-one-function"
    if run_dir.exists():
        raise PlannerError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    copied_contract = run_dir / "function-contract.json"
    copied_fixture = run_dir / "function-fixture.json"
    shutil.copy2(contract_path, copied_contract)
    shutil.copy2(fixture_path, copied_fixture)

    outputs: list[dict[str, Any]] = []
    artifacts: list[Path] = [copied_contract, copied_fixture]
    execution_failures: list[str] = []
    fixture_input = fixture.get("input")
    if not isinstance(fixture_input, Mapping):
        raise PlannerError("fixture input must be an object")
    required_input = contract.get("input_contract", {}).get("required_fields", {})
    for field, expected in required_input.items():
        if field not in fixture_input or not type_matches(fixture_input[field], expected):
            execution_failures.append(f"fixture field {field} missing or not {expected}")
    max_chars = int(contract.get("input_contract", {}).get("max_prompt_chars", 0) or 0)
    if max_chars and len(str(fixture_input.get("prompt", ""))) > max_chars:
        execution_failures.append("fixture prompt exceeds max_prompt_chars")

    if not execution_failures:
        for index in range(1, attempts + 1):
            attempt_dir = run_dir / f"attempt-{index}"
            attempt_dir.mkdir()
            input_path = attempt_dir / "input.json"
            output_path = attempt_dir / "output.json"
            stdout_path = attempt_dir / "stdout.txt"
            stderr_path = attempt_dir / "stderr.txt"
            write_json(input_path, dict(fixture_input))
            substitutions = {
                "{python}": sys.executable,
                "{tool_root}": str(ROOT),
                "{input_path}": str(input_path),
                "{output_path}": str(output_path),
                "{run_dir}": str(run_dir),
            }
            argv = []
            for raw in argv_template:
                value = raw
                for key, replacement in substitutions.items():
                    value = value.replace(key, replacement)
                argv.append(value)
            working_raw = str(implementation.get("working_directory", "{tool_root}"))
            for key, replacement in substitutions.items():
                working_raw = working_raw.replace(key, replacement)
            environment = os.environ.copy()
            for key, value in implementation.get("environment", {}).items():
                environment[str(key)] = str(value)
            try:
                completed = subprocess.run(
                    argv,
                    cwd=working_raw,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    shell=False,
                )
                stdout_path.write_text(completed.stdout, encoding="utf-8")
                stderr_path.write_text(completed.stderr, encoding="utf-8")
                if completed.returncode != 0:
                    execution_failures.append(f"attempt {index} exited {completed.returncode}")
                elif not output_path.is_file():
                    execution_failures.append(f"attempt {index} produced no output file")
                else:
                    output = load_json(output_path)
                    output_failures = validate_output_contract(output, contract)
                    execution_failures.extend(f"attempt {index}: {message}" for message in output_failures)
                    outputs.append(output)
            except subprocess.TimeoutExpired:
                stdout_path.write_text("", encoding="utf-8")
                stderr_path.write_text(f"timeout after {timeout} seconds\n", encoding="utf-8")
                execution_failures.append(f"attempt {index} timed out")
            artifacts.extend([input_path, stdout_path, stderr_path])
            if output_path.exists():
                artifacts.append(output_path)

    stable_failures: list[str] = []
    stable_fields = contract.get("output_contract", {}).get("stable_fields", [])
    if len(outputs) == attempts:
        baseline = outputs[0]
        for field in stable_fields:
            try:
                expected = dotted_get(baseline, field)
            except KeyError:
                stable_failures.append(f"stable field missing: {field}")
                continue
            for index, output in enumerate(outputs[1:], start=2):
                try:
                    observed = dotted_get(output, field)
                except KeyError:
                    stable_failures.append(f"attempt {index} stable field missing: {field}")
                    continue
                if observed != expected:
                    stable_failures.append(f"attempt {index} stable field drift: {field}")
    else:
        stable_failures.append(f"only {len(outputs)} of {attempts} attempts produced contract-valid output")

    implementation_digest_ok = contract.get("implementation_sha256") == sha256_json(implementation)
    explicit_runtime_ok = all(
        key in execution for key in ("timeout_seconds", "qualification_attempts", "shell", "cleanup")
    ) and execution.get("shell") is False
    checks = [
        {
            "id": "stable-function-and-implementation-identity",
            "pass": bool(contract.get("id")) and implementation_digest_ok,
            "detail": "function id present and implementation digest recomputes",
        },
        {
            "id": "input-and-output-contracts",
            "pass": not execution_failures,
            "detail": execution_failures or "all attempts satisfied the declared interface",
        },
        {
            "id": "runtime-timeout-cleanup-failure-semantics",
            "pass": explicit_runtime_ok and bool(contract.get("failure_semantics")),
            "detail": "shell-free bounded runtime and failure meanings are explicit",
        },
        {
            "id": "contract-level-replay",
            "pass": not stable_failures,
            "detail": stable_failures or f"{attempts} attempts retained all declared stable fields",
        },
    ]
    passed = all(check["pass"] for check in checks)
    supports = [{"capability": "function_contract", "tier": "qualified"}] if passed else []
    receipt = make_receipt(
        experiment_id="freeze-one-function",
        status="PASS" if passed else "FAIL",
        generated_at=generated_at,
        checks=checks,
        artifact_paths=artifacts,
        receipt_dir=run_dir,
        supports=supports,
        claim_boundary=str(contract.get("claim_boundary")),
        metadata={
            "function_id": contract.get("id"),
            "contract_sha256": sha256_file(copied_contract),
            "fixture_sha256": sha256_file(copied_fixture),
            "attempts": attempts,
        },
    )
    receipt_path = run_dir / "experiment.receipt.json"
    write_json(receipt_path, receipt)
    if passed and ingest:
        goals_doc, experiments_doc = source_docs()
        tier_order, _, _, _ = parse_inputs(goals_doc, experiments_doc)
        ledger, _ = ingest_receipts(
            read_json(paths["evidence"]),
            [receipt_path],
            experiments_doc,
            tier_order,
            as_of=generated_at,
        )
        write_json(paths["evidence"], ledger)
        build_state_plan(state_dir, generated_at=generated_at)
    return receipt_path, receipt


def classify_adapter(adapter: Mapping[str, Any]) -> str:
    vendor = str(adapter.get("vendor_guess") or "").lower()
    role = str(adapter.get("role_candidate") or "").lower()
    if role in {"igpu", "dgpu"}:
        return role
    if vendor == "nvidia":
        return "dgpu"
    if vendor in {"intel", "amd"}:
        return "igpu-candidate"
    return "unclassified"



def disabled_with_reason_failures(
    observation: Mapping[str, Any],
    host_id: str,
    *,
    required_rows: tuple[str, ...] = REQUIRED_RUNTIME_NAMES,
    platform: str = "unknown",
) -> list[str]:
    runtime = observation.get("runtime")
    if not isinstance(runtime, list):
        return [f"{host_id}: runtime inventory missing"]
    failures: list[str] = []
    seen: list[str] = []
    row_by_name: dict[str, Mapping[str, Any]] = {}
    required = {str(item).lower() for item in required_rows}
    for index, raw in enumerate(runtime):
        if not isinstance(raw, Mapping):
            failures.append(f"{host_id}: runtime[{index}] is not an object")
            continue
        name = str(raw.get("name") or "").strip().lower()
        label = name or f"runtime[{index}]"
        if not name:
            failures.append(f"{host_id}: runtime[{index}] name missing")
        else:
            row_by_name[name] = raw
            seen.append(name)
            if name in seen[:-1]:
                failures.append(f"{host_id}: duplicate runtime identity: {name}")
        present = raw.get("present")
        disabled = raw.get("disabled")
        reason = raw.get("disabled_reason")
        executable = raw.get("path")
        if present is True:
            if disabled is not False:
                failures.append(f"{host_id}: {label} is present but not explicitly enabled")
            if not isinstance(executable, str) or not executable.strip():
                failures.append(f"{host_id}: {label} is present without an executable path")
            if reason is not None and reason != "":
                failures.append(f"{host_id}: {label} is present but carries a disabled reason")
        elif present is False:
            if disabled is not True:
                failures.append(f"{host_id}: {label} is absent but not explicitly disabled")
            if not isinstance(reason, str) or not reason.strip():
                failures.append(f"{host_id}: {label} is disabled without a reason")
            if executable is not None:
                failures.append(f"{host_id}: {label} is disabled but still declares a path")
        else:
            failures.append(f"{host_id}: {label} present must be boolean")
    if platform == "linux":
        wsl = row_by_name.get("wsl")
        if wsl is None:
            failures.append(f"{host_id}: wsl runtime row missing")
        else:
            disabled_reason = wsl.get("disabled_reason")
            if wsl.get("present") is not False:
                failures.append(f"{host_id}: wsl must be explicitly absent on native Linux hosts")
            if wsl.get("disabled") is not True:
                failures.append(f"{host_id}: wsl must be explicitly disabled on native Linux hosts")
            if not isinstance(disabled_reason, str) or disabled_reason.strip() != "not applicable on a native Linux host":
                failures.append(f"{host_id}: wsl disabled_reason must be \"not applicable on a native Linux host\"")
    seen_set = set(seen)
    extra = sorted(seen_set - required)
    if extra:
        failures.append(f"{host_id}: unexpected runtime identities: {', '.join(extra)}")
    missing = sorted(required - seen_set)
    if missing:
        failures.append(f"{host_id}: runtime identities missing: {', '.join(missing)}")
    if len(seen_set) != len(required):
        failures.append(f"{host_id}: runtime denominator incomplete or duplicate: {len(seen)} of {len(required)} required identities")
    return failures


def observe_platform(host_observation: Mapping[str, Any]) -> str:
    """Resolve the platform an observation was taken on, never inferring it.

    The retained Windows ``@1`` schema predates the platform field, so its
    platform comes from the schema itself: that is the backward-compatibility
    seam, and it is why those bytes stay admissible unchanged. ``@2`` carries an
    explicit ``platform`` and gets no such courtesy — an absent field resolves
    to nothing and refuses, because a platform-neutral schema that guesses its
    own platform is not platform-neutral.
    """
    schema = str(host_observation.get("schema") or "")
    if schema == WINDOWS_HOST_SCHEMA:
        return "windows"
    if schema == LINUX_HOST_SCHEMA:
        return str(host_observation.get("platform") or "").lower()
    return ""


def classify_observation_discovery(host_observation: Mapping[str, Any], expected: Mapping[str, Any], *, host_id: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    discovery_failures: list[str] = []
    if not host_observation.get("host_id"):
        failures.append(f"{host_id}: host_id missing")
    platform = observe_platform(host_observation)
    if not platform:
        failures.append(f"{host_id}: unsupported observation schema")
    elif platform != "windows" and platform != "linux":
        failures.append(f"{host_id}: unsupported platform {platform}")

    system = host_observation.get("system", {})
    memory = host_observation.get("memory", {})
    storage = host_observation.get("storage", {})
    cpu = host_observation.get("cpu", [])
    if not isinstance(system, Mapping):
        failures.append(f"{host_id}: system missing")
    if not isinstance(memory, Mapping):
        failures.append(f"{host_id}: memory missing")
    else:
        if not memory.get("total_bytes"):
            failures.append(f"{host_id}: memory.total_bytes missing")
    if not isinstance(storage, Mapping):
        failures.append(f"{host_id}: storage missing")
    else:
        if not storage.get("physical_disks"):
            discovery_failures.append(f"{host_id}: physical disk inventory incomplete")
    if not isinstance(cpu, list):
        failures.append(f"{host_id}: cpu missing")
    if platform == "windows":
        if not system.get("computer_name"):
            failures.append(f"{host_id}: windows computer_name missing")
        if not system.get("os_caption") and not system.get("os_version"):
            failures.append(f"{host_id}: windows OS identity incomplete")
    elif platform == "linux":
        if not system.get("hostname"):
            failures.append(f"{host_id}: linux hostname missing")
        if not system.get("kernel") and not system.get("os_release"):
            failures.append(f"{host_id}: linux OS/kernel identity incomplete")
        if not system.get("architecture"):
            failures.append(f"{host_id}: linux architecture missing")

    return failures, discovery_failures


SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def admitted_linux_collector_sha256() -> str | None:
    source = ROOT / "scripts" / "collect-linux.py"
    try:
        return sha256_file(source)
    except OSError:
        return None


def validate_linux_observation_identity(host_observation: Mapping[str, Any], *, host_id: str) -> list[str]:
    failures: list[str] = []
    collector = host_observation.get("collector")
    if not isinstance(collector, Mapping):
        return [f"{host_id}: collector identity missing"]
    if str(collector.get("schema") or "") != COLLECTOR_SCHEMA:
        failures.append(f"{host_id}: collector schema missing or invalid")
    if str(collector.get("platform") or "").lower() != "linux":
        failures.append(f"{host_id}: collector platform not linux")
    source_sha256 = str(collector.get("source_sha256") or "").lower()
    if not SHA256_HEX_RE.match(source_sha256):
        failures.append(f"{host_id}: collector source_identity digest missing")
    elif not collector.get("source_path"):
        failures.append(f"{host_id}: collector source_identity path missing")
    else:
        admitted = admitted_linux_collector_sha256()
        if admitted is None:
            failures.append(f"{host_id}: admitted collector source_identity unreadable")
        elif source_sha256 != admitted:
            failures.append(f"{host_id}: collector source_identity digest mismatch")
    python_identity = collector.get("python_executable")
    if not isinstance(python_identity, Mapping):
        failures.append(f"{host_id}: collector python identity missing")
    else:
        if not python_identity.get("path"):
            failures.append(f"{host_id}: collector python executable path missing")
        if not SHA256_HEX_RE.match(str(python_identity.get("sha256") or "").lower()):
            failures.append(f"{host_id}: collector python executable digest missing")
    return failures


HOST_FINGERPRINT_SCHEMA = "axm-community-lab/observed-host-fingerprint@1"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _component(value: Any) -> str:
    """Normalize one permitted field into a comparable component string."""
    if value is None or value is True or value is False:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value if item is not None)
    return " ".join(str(value).split()).strip().lower()


def _joined(*values: Any) -> str:
    return "|".join(_component(value) for value in values)


def accelerator_identities(host_observation: Mapping[str, Any]) -> list[str]:
    """Every globally unique accelerator identifier the observation carries.

    An NVIDIA UUID is unique to one physical board by construction, so it is
    the identity that must never appear under two host ids. PCI bus ids are
    deliberately excluded: they are unique per machine, not per estate, and
    requiring them to differ would refuse an honest three-host census.
    """
    graphics = _mapping(host_observation.get("graphics"))
    identities: list[str] = []
    for row in _rows(graphics.get("nvidia")) + _rows(graphics.get("adapters")):
        if not isinstance(row, Mapping):
            continue
        identity = _component(row.get("uuid"))
        if identity:
            identities.append(identity)
    return sorted(set(identities))


def host_fingerprint_components(host_observation: Mapping[str, Any]) -> dict[str, Any]:
    """The body-safe physical identity of the observed machine.

    Built only from fields the privacy law already admits into an observation
    body, so it introduces no new identifier and retains no prohibited one. It
    deliberately excludes host_id, the estate role labels, observed_at, the
    clock samples, and the collector and runtime rows: those are exactly what
    an operator edits when relabelling one machine as three, and a fingerprint
    that moved with them would prove only that the labels differ.
    """
    system = _mapping(host_observation.get("system"))
    firmware = _mapping(system.get("firmware"))
    memory = _mapping(host_observation.get("memory"))
    storage = _mapping(host_observation.get("storage"))
    graphics = _mapping(host_observation.get("graphics"))
    return {
        "schema": HOST_FINGERPRINT_SCHEMA,
        "computer_name": _component(system.get("computer_name") or system.get("hostname")),
        "system_manufacturer": _component(system.get("manufacturer") or firmware.get("system_manufacturer")),
        "system_model": _component(system.get("model") or firmware.get("system_product_name")),
        "os_identity": _component(system.get("os_caption") or system.get("os_release")),
        "architecture": _component(system.get("architecture")),
        "firmware": [
            _component(system.get("bios_manufacturer") or firmware.get("bios_manufacturer")),
            _component(system.get("bios_version") or firmware.get("bios_version")),
            _component(firmware.get("bios_date")),
            _component(firmware.get("board_name")),
        ],
        "cpu": sorted(
            _joined(
                row.get("name"),
                row.get("manufacturer") or row.get("vendor"),
                row.get("processor_id") or row.get("package_id"),
                row.get("cores"),
                row.get("logical_processors"),
            )
            for row in _rows(host_observation.get("cpu"))
            if isinstance(row, Mapping)
        ),
        "memory_total_bytes": memory.get("total_bytes"),
        "physical_disks": sorted(
            _joined(row.get("model"), row.get("size_bytes"))
            for row in _rows(storage.get("physical_disks"))
            if isinstance(row, Mapping)
        ),
        "display_adapters": sorted(
            _joined(row.get("name"), row.get("pnp_device_id") or row.get("bus_id"))
            for row in _rows(graphics.get("adapters"))
            if isinstance(row, Mapping)
        ),
        "accelerator_identities": accelerator_identities(host_observation),
    }


def observed_host_fingerprint(host_observation: Mapping[str, Any]) -> str:
    """One digest addressing the observed machine, never its declared role."""
    return hashlib.sha256(canonical_bytes(host_fingerprint_components(host_observation))).hexdigest()


def host_observation_receipt_path(observation_path: Path, host_id: str) -> Path:
    """The one admitted commit marker: an exact sibling named from host_id."""
    return observation_path.with_name(f"{host_id}{HOST_OBSERVATION_RECEIPT_SUFFIX}")


def admitted_seed_identity() -> tuple[str, str]:
    """Return (seed id, manifest digest) from the exact admitted seed bytes."""
    sums = ROOT / "seed" / "sha256sums.txt"
    manifest = ROOT / "seed" / "seed-manifest.json"
    return sha256_file(sums), sha256_file(manifest)


def _receipt_body_strings(payload: Any, found: set[str]) -> None:
    if isinstance(payload, Mapping):
        for value in payload.values():
            _receipt_body_strings(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _receipt_body_strings(value, found)
    elif isinstance(payload, str) and len(payload) >= 3:
        found.add(payload)


def _receipt_scalar_strings(payload: Any, found: list[str]) -> None:
    if isinstance(payload, Mapping):
        for value in payload.values():
            _receipt_scalar_strings(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _receipt_scalar_strings(value, found)
    elif isinstance(payload, str):
        found.append(payload)


def host_receipt_body_leak_failures(
    receipt: Mapping[str, Any], observation: Mapping[str, Any], host_id: str
) -> list[str]:
    """Refuse any host-descriptive observation value carried by the receipt."""
    collector = _mapping(observation.get("collector"))
    python_identity = _mapping(collector.get("python_executable"))
    allowed = {str(observation.get(name)) for name in HOST_OBSERVATION_RECEIPT_JOIN_COORDINATES}
    allowed.update(
        {
            str(collector.get("schema")),
            str(collector.get("source_sha256")),
            str(python_identity.get("sha256")),
        }
    )
    body: set[str] = set()
    _receipt_body_strings(observation, body)
    receipt_values: list[str] = []
    _receipt_scalar_strings(receipt, receipt_values)
    failures: list[str] = []
    for candidate in sorted(body - allowed):
        if any(candidate == value or (len(candidate) >= 8 and candidate in value) for value in receipt_values):
            failures.append(f"{host_id}: receipt carries an observation body value: {candidate!r}")
    return failures


def validate_host_observation_receipt(
    receipt: Mapping[str, Any], observation: Mapping[str, Any], observation_path: Path
) -> list[str]:
    """Verify the body-free physical commit marker against exact observation bytes."""
    host_id = str(observation.get("host_id") or observation_path.stem)
    failures: list[str] = []
    for field in HOST_OBSERVATION_RECEIPT_REQUIRED:
        if field not in receipt:
            failures.append(f"{host_id}: receipt field missing: {field}")
    extras = sorted(set(receipt) - set(HOST_OBSERVATION_RECEIPT_REQUIRED))
    if extras:
        failures.append(f"{host_id}: receipt carries unrecognized fields: {', '.join(extras)}")
    if receipt.get("schema") != HOST_OBSERVATION_RECEIPT_SCHEMA:
        failures.append(f"{host_id}: receipt schema mismatch")
    if receipt.get("observation_schema") != observation.get("schema"):
        failures.append(f"{host_id}: receipt observation_schema does not bind the observation schema")
    collector = _mapping(observation.get("collector"))
    if receipt.get("collector_schema") != collector.get("schema"):
        failures.append(f"{host_id}: receipt collector_schema does not bind the observation collector")
    for field in ("platform", "host_id", "observed_at", "observation_sha256"):
        if receipt.get(field) != observation.get(field):
            failures.append(f"{host_id}: receipt {field} does not bind the observation")
    expected_name = f"{host_id}.json"
    if observation_path.name != expected_name:
        failures.append(
            f"{host_id}: Linux observation file name must be the declared lexical name {expected_name}"
        )
    if receipt.get("observation_file_name") != observation_path.name:
        failures.append(f"{host_id}: receipt observation_file_name does not name the declared observation")
    try:
        exact_digest = sha256_file(observation_path)
        exact_bytes = observation_path.stat().st_size
    except OSError as exc:
        failures.append(f"{host_id}: observation file cannot be bound by receipt: {exc}")
    else:
        if receipt.get("observation_file_sha256") != exact_digest:
            failures.append(f"{host_id}: receipt observation_file_sha256 does not bind the exact file bytes")
        if receipt.get("observation_file_bytes") != exact_bytes:
            failures.append(f"{host_id}: receipt observation_file_bytes does not bind the exact file size")
    if receipt.get("host_fingerprint_sha256") != observed_host_fingerprint(observation):
        failures.append(f"{host_id}: receipt host_fingerprint_sha256 does not recompute")
    identities = accelerator_identities(observation)
    identity_digests = sorted(
        hashlib.sha256(identity.encode("utf-8")).hexdigest() for identity in identities
    )
    if receipt.get("accelerator_identity_sha256") != identity_digests:
        failures.append(f"{host_id}: receipt accelerator_identity_sha256 does not recompute")
    if receipt.get("accelerator_identity_count") != len(identities):
        failures.append(f"{host_id}: receipt accelerator_identity_count does not match")
    python_identity = _mapping(collector.get("python_executable"))
    if receipt.get("collector_source_sha256") != collector.get("source_sha256"):
        failures.append(f"{host_id}: receipt collector_source_sha256 does not bind the collector")
    if receipt.get("python_executable_sha256") != python_identity.get("sha256"):
        failures.append(f"{host_id}: receipt python_executable_sha256 does not bind the collector runtime")
    try:
        seed_id, manifest_sha256 = admitted_seed_identity()
    except OSError as exc:
        failures.append(f"{host_id}: admitted seed identity is unreadable: {exc}")
    else:
        if receipt.get("seed_id") != seed_id:
            failures.append(f"{host_id}: receipt seed_id does not bind the admitted seed")
        if receipt.get("seed_manifest_sha256") != manifest_sha256:
            failures.append(f"{host_id}: receipt seed_manifest_sha256 does not bind the admitted manifest")
    if receipt.get("carries_observation_body") is not False:
        failures.append(f"{host_id}: receipt must declare carries_observation_body false")
    if not isinstance(receipt.get("claim_boundary"), str) or not receipt.get("claim_boundary"):
        failures.append(f"{host_id}: receipt claim_boundary missing")
    expected_receipt_digest = hashlib.sha256(
        canonical_bytes({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    ).hexdigest()
    if receipt.get("receipt_sha256") != expected_receipt_digest:
        failures.append(f"{host_id}: receipt digest mismatch")
    failures.extend(host_receipt_body_leak_failures(receipt, observation, host_id))
    return failures


def physical_identity_failures(
    fingerprints: Mapping[str, str],
    accelerators: Mapping[str, Sequence[str]],
) -> list[str]:
    """Refuse a denominator that one machine could satisfy by relabelling.

    Three declared host_id strings prove three labels. Three distinct observed
    fingerprints, with accelerator identities appearing under exactly one of
    them, are what prove three machines.
    """
    failures: list[str] = []
    seen_fingerprint: dict[str, str] = {}
    for host_id in sorted(fingerprints):
        fingerprint = fingerprints[host_id]
        owner = seen_fingerprint.get(fingerprint)
        if owner is None:
            seen_fingerprint[fingerprint] = host_id
            continue
        failures.append(
            f"{host_id}: observed host fingerprint {fingerprint} is the same physical host as {owner}"
        )
    seen_accelerator: dict[str, str] = {}
    for host_id in sorted(accelerators):
        for identity in accelerators[host_id]:
            owner = seen_accelerator.get(identity)
            if owner is None:
                seen_accelerator[identity] = host_id
                continue
            failures.append(
                f"{host_id}: accelerator identity {identity} is already observed on {owner}"
            )
    return failures


def normalize_host_observation_for_aggregate(
    host_observation: Mapping[str, Any],
    host_id: str,
    *,
    source_file: Path,
    igpu_candidates: Sequence[Mapping[str, Any]],
    dgpu_identities: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """One aggregate row: the predecessor contract, plus explicit successors.

    source_sha256 keeps its predecessor meaning -- the SHA-256 of the exact
    retained input file -- and igpu_candidates, dgpu_identities,
    physical_disks, and network_adapters are carried unchanged, so a consumer
    written against the earlier estate-observation@1 reads the same fields with
    the same semantics. The two digests are then named separately, because the
    single phrase "the digest of this row" was the one thing that could mean
    either the exact file bytes or the semantic observation body.
    """
    system = _mapping(host_observation.get("system"))
    storage = _mapping(host_observation.get("storage"))
    network = _mapping(host_observation.get("network"))
    source_file_sha256 = sha256_file(source_file)
    return {
        "host_id": host_id,
        "source_sha256": source_file_sha256,
        "source_file_sha256": source_file_sha256,
        "observation_sha256": host_observation.get("observation_sha256"),
        "schema": host_observation.get("schema"),
        "platform": observe_platform(host_observation),
        "computer_name": system.get("computer_name") or system.get("hostname"),
        "host_fingerprint_sha256": observed_host_fingerprint(host_observation),
        "cpu": host_observation.get("cpu", []),
        "memory": host_observation.get("memory", {}),
        "physical_disks": storage.get("physical_disks", []),
        "storage": host_observation.get("storage", {}),
        "network_adapters": network.get("adapters", []),
        "network": host_observation.get("network", {}),
        "igpu_candidates": list(igpu_candidates),
        "dgpu_identities": list(dgpu_identities),
        "clock": host_observation.get("clock"),
        "observed_at": host_observation.get("observed_at"),
    }


def qualify_estate(
    *,
    observations: Sequence[Path],
    state_dir: Path,
    generated_at: str,
    ingest: bool,
) -> tuple[Path, dict[str, Any]]:
    paths = init_state(state_dir)
    estate = read_json(paths["estate"])
    expected_hosts = {str(host["id"]): host for host in estate.get("hosts", [])}
    if not expected_hosts:
        raise PlannerError("estate descriptor contains no hosts")
    run_dir = paths["runs"] / f"{stamp(generated_at)}-capture-estate-snapshot"
    if run_dir.exists():
        raise PlannerError(f"run directory already exists: {run_dir}")
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True)

    loaded: dict[str, dict[str, Any]] = {}
    retained: dict[str, Path] = {}
    copied: list[Path] = []
    failures: list[str] = []
    private_failures: list[str] = []
    digest_failures: list[str] = []
    source_failures: list[str] = []
    receipt_failures: list[str] = []
    inventory_failures: list[str] = []
    device_failures: list[str] = []
    disabled_reason_failures: list[str] = []
    fingerprints: dict[str, str] = {}
    accelerators: dict[str, list[str]] = {}
    receipt_digests: dict[str, str] = {}
    for source in observations:
        item = load_json(source)
        schema = str(item.get("schema") or "")
        platform = observe_platform(item)
        if schema == WINDOWS_HOST_SCHEMA:
            pass
        elif schema == LINUX_HOST_SCHEMA:
            if platform != "linux":
                failures.append(
                    f"{source.name}: platform must be explicit: observed {platform or 'no platform field'}"
                )
                continue
        else:
            failures.append(f"{source.name}: unsupported schema")
            continue
        host_id = str(item.get("host_id") or "")
        if not host_id:
            failures.append(f"{source.name}: host_id missing")
            continue
        if host_id in loaded:
            failures.append(f"duplicate host_id: {host_id}")
            continue
        if platform == "linux":
            source_failures.extend(validate_linux_observation_identity(item, host_id=host_id))
            receipt_source = host_observation_receipt_path(source, host_id)
            receipt_target = inputs_dir / receipt_source.name
            try:
                receipt_raw = receipt_source.read_bytes()
            except FileNotFoundError:
                receipt_failures.append(
                    f"{host_id}: required Linux observation receipt missing: {receipt_source.name}"
                )
            except OSError as exc:
                receipt_failures.append(
                    f"{host_id}: required Linux observation receipt unreadable: {receipt_source.name}: {exc}"
                )
            else:
                shutil.copy2(receipt_source, receipt_target)
                copied.append(receipt_target)
                receipt_digests[host_id] = sha256_file(receipt_target)
                try:
                    receipt_item = json.loads(receipt_raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    receipt_failures.append(
                        f"{host_id}: malformed Linux observation receipt {receipt_source.name}: {exc}"
                    )
                else:
                    if not isinstance(receipt_item, Mapping):
                        receipt_failures.append(
                            f"{host_id}: malformed Linux observation receipt {receipt_source.name}: root must be an object"
                        )
                    else:
                        receipt_failures.extend(
                            validate_host_observation_receipt(receipt_item, item, source)
                        )
        disabled_reason_failures.extend(
            disabled_with_reason_failures(
                item,
                host_id,
                required_rows=REQUIRED_RUNTIME_NAMES,
                platform=platform,
            )
        )

        target = inputs_dir / f"{host_id}.json"
        copied_digest = observation_digest(item)
        if str(item.get("observation_sha256") or "").lower() != copied_digest:
            digest_failures.append(f"{host_id}: observation_sha256 mismatch")
        if not item.get("observation_sha256"):
            digest_failures.append(f"{host_id}: observation_sha256 missing")
        private_failures.extend(collect_private_identifier_failures(item, host_id))
        shutil.copy2(source, target)
        loaded[host_id] = item
        retained[host_id] = target
        copied.append(target)

    observed_ids = set(loaded)
    expected_ids = set(expected_hosts)
    missing_hosts = sorted(expected_ids - observed_ids)
    extra_hosts = sorted(observed_ids - expected_ids)
    if missing_hosts:
        failures.append(f"missing expected hosts: {', '.join(missing_hosts)}")
    if extra_hosts:
        failures.append(f"unexpected hosts: {', '.join(extra_hosts)}")

    host_rows: list[dict[str, Any]] = []
    resolved_domains = 0
    expected_domains = 0
    for host_id, expected in expected_hosts.items():
        observation = loaded.get(host_id)
        expected_igpu = 1 if expected.get("igpu") else 0
        expected_dgpu = len(expected.get("dgpus", []))
        expected_domains += expected_igpu + expected_dgpu
        if observation is None:
            inventory_failures.append(f"{host_id}: observation missing")
            device_failures.append(f"{host_id}: accelerator observation missing")
            continue
        system = observation.get("system", {})
        cpu = observation.get("cpu", [])
        memory = observation.get("memory", {})
        storage = observation.get("storage", {})
        discovery_failures, observed_failures = classify_observation_discovery(
            observation,
            expected,
            host_id=host_id,
        )
        inventory_failures.extend(discovery_failures)
        inventory_failures.extend(observed_failures)
        graphics = observation.get("graphics", {})
        adapters = graphics.get("adapters", []) if isinstance(graphics, Mapping) else []
        nvidia = graphics.get("nvidia", []) if isinstance(graphics, Mapping) else []
        igpus = [item for item in adapters if isinstance(item, Mapping) and classify_adapter(item) in {"igpu", "igpu-candidate"}]
        dgpus = [item for item in nvidia if isinstance(item, Mapping) and item.get("uuid")]
        if len(igpus) < expected_igpu:
            device_failures.append(f"{host_id}: expected {expected_igpu} iGPU identity, observed {len(igpus)} candidate(s)")
        else:
            resolved_domains += expected_igpu
        if len(dgpus) < expected_dgpu:
            device_failures.append(f"{host_id}: expected {expected_dgpu} dGPU UUID(s), observed {len(dgpus)}")
        else:
            resolved_domains += expected_dgpu
        fingerprints[host_id] = observed_host_fingerprint(observation)
        accelerators[host_id] = accelerator_identities(observation)
        host_rows.append(
            normalize_host_observation_for_aggregate(
                observation,
                host_id,
                source_file=retained[host_id],
                igpu_candidates=igpus,
                dgpu_identities=dgpus,
            )
        )

    identity_failures = physical_identity_failures(fingerprints, accelerators)

    aggregate = {
        "schema": "axm-community-lab/estate-observation@1",
        "estate_id": estate.get("estate_id"),
        "platform_rows": {host_id: observe_platform(observation) for host_id, observation in sorted(loaded.items())},
        "host_fingerprints": dict(sorted(fingerprints.items())),
        "generated_at": generated_at,
        "host_count_expected": len(expected_hosts),
        "host_count_observed": len(loaded),
        "accelerator_domains_expected": expected_domains,
        "accelerator_domains_resolved": resolved_domains,
        "hosts": host_rows,
        "source_digests": {host_id: observation_digest(item) for host_id, item in sorted(loaded.items())},
        "receipt_file_digests": dict(sorted(receipt_digests.items())),
        "unresolved": {
            "general": failures,
            "host_inventory": inventory_failures,
            "disabled_with_reason": disabled_reason_failures,
            "observation_digests": digest_failures,
            "source_identity": source_failures,
            "observation_receipts": receipt_failures,
            "privacy": private_failures,
            "physical_identity": identity_failures,
            "device_identity": device_failures,
        },
        "claim_boundary": "This aggregate records read-only host observations and explicit identity resolution. It does not admit workers, measure path cost, prove clock synchronization, or infer missing accelerator roles.",
    }
    aggregate["observation_sha256"] = sha256_json({k: v for k, v in aggregate.items() if k != "generated_at"})
    aggregate_path = run_dir / "estate-observation.json"
    write_json(aggregate_path, aggregate)

    host_inventory_ok = (
        not failures
        and not inventory_failures
        and not disabled_reason_failures
        and not digest_failures
        and not source_failures
        and not receipt_failures
        and not private_failures
        and not identity_failures
        and len(loaded) == len(expected_hosts)
    )
    device_identity_ok = host_inventory_ok and not device_failures and resolved_domains == expected_domains
    checks = [
        {
            "id": "three-distinct-host-records",
            "pass": not failures and len(loaded) == len(expected_hosts),
            "detail": failures or f"observed {len(loaded)} distinct expected hosts",
        },
        {
            "id": "stable-host-inventory",
            "pass": host_inventory_ok,
            "detail": inventory_failures or "CPU, RAM, OS, disk, and host identity fields are present",
        },
        {
            "id": "disabled-components-carry-reasons",
            "pass": not disabled_reason_failures,
            "detail": disabled_reason_failures or "every absent runtime is explicitly disabled with a reason",
        },
        {
            "id": "linux-observation-commit-receipts",
            "pass": not receipt_failures,
            "detail": receipt_failures or "every Linux observation carries its exact body-free sibling receipt",
        },
        {
            "id": "distinct-physical-hosts",
            "pass": not identity_failures,
            "detail": identity_failures
            or f"{len(fingerprints)} distinct observed host fingerprints, no accelerator identity observed twice",
        },
        {
            "id": "six-accelerator-domains-explicit",
            "pass": device_identity_ok,
            "detail": device_failures or f"resolved {resolved_domains} of {expected_domains} declared accelerator domains",
        },
        {
            "id": "deterministic-content-digest",
            "pass": bool(aggregate.get("observation_sha256")),
            "detail": aggregate.get("observation_sha256"),
        },
    ]
    supports: list[dict[str, str]] = []
    if host_inventory_ok:
        supports.append({"capability": "host_inventory", "tier": "observed"})
    if device_identity_ok:
        supports.append({"capability": "device_identity", "tier": "observed"})
    status = "PASS" if host_inventory_ok and device_identity_ok else ("PARTIAL" if supports else "FAIL")
    receipt = make_receipt(
        experiment_id="capture-estate-snapshot",
        status=status,
        generated_at=generated_at,
        checks=checks,
        artifact_paths=[aggregate_path, *copied],
        receipt_dir=run_dir,
        supports=supports,
        claim_boundary=aggregate["claim_boundary"],
        metadata={
            "estate_id": estate.get("estate_id"),
            "observation_sha256": aggregate["observation_sha256"],
        },
    )
    receipt["unresolved"] = aggregate["unresolved"]
    receipt["receipt_sha256"] = canonical_receipt_id(receipt)
    receipt_path = run_dir / "experiment.receipt.json"
    write_json(receipt_path, receipt)
    if supports and ingest:
        goals_doc, experiments_doc = source_docs()
        tier_order, _, _, _ = parse_inputs(goals_doc, experiments_doc)
        ledger, _ = ingest_receipts(
            read_json(paths["evidence"]),
            [receipt_path],
            experiments_doc,
            tier_order,
            as_of=generated_at,
        )
        write_json(paths["evidence"], ledger)
        build_state_plan(state_dir, generated_at=generated_at)
    return receipt_path, receipt


def start_protocol(experiment_id: str, state_dir: Path, *, generated_at: str) -> Path:
    paths = init_state(state_dir)
    plan = build_state_plan(state_dir, generated_at=generated_at)
    row = next((item for item in plan["experiments"] if item["id"] == experiment_id), None)
    if row is None:
        raise PlannerError(f"unknown experiment: {experiment_id}")
    if row["status"] == "blocked":
        chain = " -> ".join(row.get("enabling_chain") or [])
        raise PlannerError(f"experiment {experiment_id} is blocked; enabling chain: {chain}")
    if row["status"] == "complete":
        raise PlannerError(f"experiment {experiment_id} is already complete at its declared production tier")
    run_dir = paths["runs"] / f"{stamp(generated_at)}-{experiment_id}"
    if run_dir.exists():
        raise PlannerError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    protocol = {
        "schema": "axm-community-lab/experiment-run@1",
        "run_id": f"run_{sha256_json({'experiment': experiment_id, 'generated_at': generated_at, 'plan': plan['plan_sha256']})[:20]}",
        "generated_at": generated_at,
        "plan_sha256": plan["plan_sha256"],
        "experiment": row,
        "status": "OPEN",
        "authority": "operator-owned run package; no capability is promoted until an ingestible receipt passes",
    }
    protocol_path = run_dir / "protocol.json"
    write_json(protocol_path, protocol)
    return protocol_path


def validate_source() -> dict[str, Any]:
    estate = read_json(DATA / "estate.json")
    goals = read_json(DATA / "goals.json")
    experiments = read_json(DATA / "experiments.json")
    evidence = read_json(DATA / "evidence.json")
    parse_inputs(goals, experiments)
    plan = build_plan(estate, goals, experiments, evidence, generated_at="2026-08-05T00:00:00Z")
    checks: list[dict[str, Any]] = []
    checks.append({"id": "initial-top", "pass": [x["id"] for x in plan["now"][:2]] == ["capture-estate-snapshot", "freeze-one-function"]})
    html_path = ROOT / "index.html"
    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    meta_match = re.search(r'<meta name="axm-plan-sha256" content="([0-9a-f]{64})">', html_text)
    payload_match = re.search(r'<script id="embedded-data" type="application/octet-stream">([A-Za-z0-9+/=]+)</script>', html_text)
    embedded_plan = None
    try:
        if payload_match:
            embedded = json.loads(gzip.decompress(base64.b64decode(payload_match.group(1))).decode("utf-8"))
            embedded_plan = embedded.get("plan")
    except (ValueError, OSError, json.JSONDecodeError):
        embedded_plan = None
    checks.append({"id": "plan-digest", "pass": bool(meta_match) and meta_match.group(1) == plan["plan_sha256"]})
    checks.append({"id": "plan-body", "pass": embedded_plan == plan})
    checks.append({"id": "standalone-index", "pass": "id=\"embedded-data\"" in html_text and "fetch(" not in html_text})
    checks.append({"id": "no-external-runtime-assets", "pass": "<script src=" not in html_text and "<link rel=\"stylesheet\"" not in html_text})
    commands = [command for experiment in experiments["experiments"] for command in experiment.get("commands", [])]
    checks.append({"id": "authoritative-runner", "pass": all("scripts/lab.py" in command or "collect-windows.ps1" in command or "collect-linux.py" in command for command in commands)})
    failures = [check["id"] for check in checks if not check["pass"]]
    return {
        "schema": "axm-community-lab/source-validation@1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "plan_sha256": plan["plan_sha256"],
        "file_count": sum(1 for path in ROOT.rglob("*") if path.is_file()),
    }


def page_identity() -> dict[str, Any]:
    """Runtime-independent identity of the committed page product.

    ``identity`` holds only values that must be equal on every admitted
    runtime, so a cross-leg comparison can assert equality directly. ``runtime``
    records which interpreter produced the reading and is never compared.
    """
    html_path = ROOT / "index.html"
    raw = html_path.read_bytes() if html_path.is_file() else b""
    payload_match = re.search(
        r'<script id="embedded-data" type="application/octet-stream">([A-Za-z0-9+/=]+)</script>',
        raw.decode("utf-8", errors="replace"),
    )
    payload = base64.b64decode(payload_match.group(1)) if payload_match else b""
    try:
        embedded = gzip.decompress(payload) if payload else b""
    except (OSError, ValueError):
        embedded = b""
    return {
        "schema": "axm-community-lab/page-identity@1",
        "identity": {
            "path": "home-lab-gradient/index.html",
            "page_sha256": hashlib.sha256(raw).hexdigest(),
            "page_bytes": len(raw),
            "page_carries_cr": b"\r" in raw,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_bytes": len(payload),
            "embedded_sha256": hashlib.sha256(embedded).hexdigest(),
            "embedded_bytes": len(embedded),
            "compressor_fingerprint": compressor_fingerprint(),
            "authoritative_compressor_fingerprint": AUTHORITATIVE_COMPRESSOR_SHA256,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "os_name": os.name,
        },
    }


def render_seed(*, generated_at: str) -> dict[str, Any]:
    estate = read_json(DATA / "estate.json")
    goals = read_json(DATA / "goals.json")
    experiments = read_json(DATA / "experiments.json")
    evidence = read_json(DATA / "evidence.json")
    plan = build_plan(estate, goals, experiments, evidence, generated_at=generated_at)
    write_page(
        ROOT / "index.html",
        estate=estate,
        goals=goals,
        experiments=experiments,
        evidence=evidence,
        plan=plan,
    )
    return plan


def command_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=default_state_dir())
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the external operator-state directory")

    plan_parser = sub.add_parser("plan", help="recompute the capability gradient from current evidence")
    plan_parser.add_argument("--now", default=None)
    plan_parser.add_argument("--output", type=Path)

    sub.add_parser("next", help="print the currently admissible experiments")

    ingest_parser = sub.add_parser("ingest", help="validate receipts and append exact supports to the evidence ledger")
    ingest_parser.add_argument("receipts", type=Path, nargs="+")
    ingest_parser.add_argument("--now", default=None)

    scaffold_parser = sub.add_parser("scaffold-function", help="create the first bounded local inference contract")
    scaffold_parser.add_argument("--id", default="bounded-local-inference")
    scaffold_parser.add_argument("--model", default="qwen3.5:9b-q4_K_M")
    scaffold_parser.add_argument("--host", default="http://127.0.0.1:11434")
    scaffold_parser.add_argument("--output", type=Path)

    qualify_function_parser = sub.add_parser("qualify-function", help="execute and receipt a function contract replay")
    qualify_function_parser.add_argument("--contract", type=Path, required=True)
    qualify_function_parser.add_argument("--fixture", type=Path, required=True)
    qualify_function_parser.add_argument("--now", default=None)
    qualify_function_parser.add_argument("--no-ingest", action="store_true")

    qualify_estate_parser = sub.add_parser("qualify-estate", help="aggregate three read-only host observations (Windows @1 and/or Linux @2)")
    qualify_estate_parser.add_argument("observations", type=Path, nargs="+")
    qualify_estate_parser.add_argument("--now", default=None)
    qualify_estate_parser.add_argument("--no-ingest", action="store_true")

    start_parser = sub.add_parser("start", help="open a bound run package for an admissible experiment")
    start_parser.add_argument("experiment_id")
    start_parser.add_argument("--now", default=None)

    build_parser = sub.add_parser("build", help="rebuild committed seed plan and standalone page")
    build_parser.add_argument("--now", default="2026-08-05T00:00:00Z")

    sub.add_parser("validate", help="validate source contracts and generated projections")

    sub.add_parser("page-identity", help="print the runtime-independent identity of the committed page")

    args = parser.parse_args(argv)
    state_dir = args.state_dir.expanduser().resolve()
    try:
        if args.command == "init":
            paths = init_state(state_dir)
            print(json.dumps({"ok": True, "state_dir": str(paths["root"]), "evidence": str(paths["evidence"])}, indent=2))
            return 0
        if args.command == "plan":
            now = args.now or utc_now()
            plan = build_state_plan(state_dir, generated_at=now, output=args.output)
            print(json.dumps({"ok": True, "plan_sha256": plan["plan_sha256"], "now": [x["id"] for x in plan["now"]], "output": str(args.output or state_paths(state_dir)["plan"])}, indent=2))
            return 0
        if args.command == "next":
            plan = build_state_plan(state_dir, generated_at=utc_now())
            print(json.dumps({"plan_sha256": plan["plan_sha256"], "now": plan["now"], "control_question": plan["control_question"]}, indent=2))
            return 0
        if args.command == "ingest":
            now = args.now or utc_now()
            paths = init_state(state_dir)
            goals_doc, experiments_doc = source_docs()
            tier_order, _, _, _ = parse_inputs(goals_doc, experiments_doc)
            ledger, accepted = ingest_receipts(
                read_json(paths["evidence"]),
                args.receipts,
                experiments_doc,
                tier_order,
                as_of=now,
            )
            write_json(paths["evidence"], ledger)
            plan = build_state_plan(state_dir, generated_at=now)
            print(json.dumps({"ok": True, "receipts": accepted, "plan_sha256": plan["plan_sha256"], "now": [x["id"] for x in plan["now"]]}, indent=2))
            return 0
        if args.command == "scaffold-function":
            paths = init_state(state_dir)
            output = args.output or paths["functions"] / args.id
            contract, fixture = scaffold_function(args.id, output, model=args.model, host=args.host)
            print(json.dumps({"ok": True, "contract": str(contract), "fixture": str(fixture), "next": f'{sys.executable} {ROOT / "scripts" / "lab.py"} --state-dir {state_dir} qualify-function --contract {contract} --fixture {fixture}'}, indent=2))
            return 0
        if args.command == "qualify-function":
            now = args.now or utc_now()
            receipt_path, receipt = qualify_function(
                contract_path=args.contract,
                fixture_path=args.fixture,
                state_dir=state_dir,
                generated_at=now,
                ingest=not args.no_ingest,
            )
            print(json.dumps({"ok": receipt["status"] == "PASS", "status": receipt["status"], "receipt": str(receipt_path), "checks": receipt["checks"]}, indent=2))
            return 0 if receipt["status"] == "PASS" else 1
        if args.command == "qualify-estate":
            now = args.now or utc_now()
            receipt_path, receipt = qualify_estate(
                observations=args.observations,
                state_dir=state_dir,
                generated_at=now,
                ingest=not args.no_ingest,
            )
            print(json.dumps({"ok": receipt["status"] in {"PASS", "PARTIAL"}, "status": receipt["status"], "receipt": str(receipt_path), "supports": receipt["supports"], "checks": receipt["checks"]}, indent=2))
            return 0 if receipt["status"] in {"PASS", "PARTIAL"} else 1
        if args.command == "start":
            protocol = start_protocol(args.experiment_id, state_dir, generated_at=args.now or utc_now())
            print(json.dumps({"ok": True, "protocol": str(protocol)}, indent=2))
            return 0
        if args.command == "build":
            plan = render_seed(generated_at=args.now)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "index": str(ROOT / "index.html"),
                        "plan_sha256": plan["plan_sha256"],
                        "compressor_fingerprint": compressor_fingerprint(),
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "page-identity":
            print(json.dumps(page_identity(), indent=2, sort_keys=True))
            return 0
        if args.command == "validate":
            result = validate_source()
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "PASS" else 1
    except RenderError as exc:
        # A runtime that cannot reproduce the product must fail loudly here
        # rather than rewrite a tracked, digest-addressed page.
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "compressor_fingerprint": compressor_fingerprint(),
                    "authoritative_compressor_fingerprint": AUTHORITATIVE_COMPRESSOR_SHA256,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 4
    except PlannerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(command_main())



