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
    ingest_receipts,
    load_json,
    make_receipt,
    sha256_file,
    write_json,
)
from planner import PlannerError, build_plan, parse_inputs, read_json, sha256_json
from render import write_page

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    copied: list[Path] = []
    failures: list[str] = []
    for source in observations:
        item = load_json(source)
        if item.get("schema") != "axm-community-lab/windows-host-observation@1":
            failures.append(f"{source.name}: unsupported schema")
            continue
        host_id = str(item.get("host_id") or "")
        if not host_id:
            failures.append(f"{source.name}: host_id missing")
            continue
        if host_id in loaded:
            failures.append(f"duplicate host_id: {host_id}")
            continue
        target = inputs_dir / f"{host_id}.json"
        shutil.copy2(source, target)
        loaded[host_id] = item
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
    inventory_failures: list[str] = []
    device_failures: list[str] = []
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
        if not system.get("computer_name") or not cpu or not memory.get("total_bytes") or not storage.get("physical_disks"):
            inventory_failures.append(f"{host_id}: CPU, memory, OS, or physical disk identity incomplete")
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
        host_rows.append(
            {
                "host_id": host_id,
                "source_sha256": sha256_file(inputs_dir / f"{host_id}.json"),
                "computer_name": system.get("computer_name"),
                "cpu": cpu,
                "memory": memory,
                "physical_disks": storage.get("physical_disks", []),
                "network_adapters": observation.get("network", {}).get("adapters", []),
                "igpu_candidates": igpus,
                "dgpu_identities": dgpus,
                "clock": observation.get("clock"),
            }
        )

    aggregate = {
        "schema": "axm-community-lab/estate-observation@1",
        "estate_id": estate.get("estate_id"),
        "generated_at": generated_at,
        "host_count_expected": len(expected_hosts),
        "host_count_observed": len(loaded),
        "accelerator_domains_expected": expected_domains,
        "accelerator_domains_resolved": resolved_domains,
        "hosts": host_rows,
        "unresolved": {
            "general": failures,
            "host_inventory": inventory_failures,
            "device_identity": device_failures,
        },
        "claim_boundary": "This aggregate records read-only host observations and explicit identity resolution. It does not admit workers, measure path cost, prove clock synchronization, or infer missing accelerator roles.",
    }
    aggregate["observation_sha256"] = sha256_json({k: v for k, v in aggregate.items() if k != "generated_at"})
    aggregate_path = run_dir / "estate-observation.json"
    write_json(aggregate_path, aggregate)

    host_inventory_ok = not failures and not inventory_failures and len(loaded) == len(expected_hosts)
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
    checks.append({"id": "authoritative-runner", "pass": all("scripts/lab.py" in command or "collect-windows.ps1" in command for command in commands)})
    failures = [check["id"] for check in checks if not check["pass"]]
    return {
        "schema": "axm-community-lab/source-validation@1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "plan_sha256": plan["plan_sha256"],
        "file_count": sum(1 for path in ROOT.rglob("*") if path.is_file()),
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

    qualify_estate_parser = sub.add_parser("qualify-estate", help="aggregate three read-only Windows host observations")
    qualify_estate_parser.add_argument("observations", type=Path, nargs="+")
    qualify_estate_parser.add_argument("--now", default=None)
    qualify_estate_parser.add_argument("--no-ingest", action="store_true")

    start_parser = sub.add_parser("start", help="open a bound run package for an admissible experiment")
    start_parser.add_argument("experiment_id")
    start_parser.add_argument("--now", default=None)

    build_parser = sub.add_parser("build", help="rebuild committed seed plan and standalone page")
    build_parser.add_argument("--now", default="2026-08-05T00:00:00Z")

    sub.add_parser("validate", help="validate source contracts and generated projections")

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
            print(json.dumps({"ok": True, "index": str(ROOT / "index.html"), "plan_sha256": plan["plan_sha256"]}, indent=2))
            return 0
        if args.command == "validate":
            result = validate_source()
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "PASS" else 1
    except PlannerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(command_main())
