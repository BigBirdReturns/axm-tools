#!/usr/bin/env python3
"""Independent, non-authoritative audit of Gradient issue #151 candidate.

The audit executes the candidate's own denominator and then presents hostile
inputs that the product contract says must refuse. It changes no product source,
contacts no physical host, and emits only synthetic/body-free findings.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GRADIENT = ROOT / "home-lab-gradient"
SCRIPTS = GRADIENT / "scripts"
TESTS = GRADIENT / "tests"

CANDIDATE = "88a9589752eccfe109396483fd3a5f173b295135"
BASE = "194a3f5e53fc15eaa18e08fb37d57a1750949f9e"
EXPECTED_TREE = "55d10344c3d06f6f93e19a7bd589613ec4e8a171"
EXPECTED_SEED_ID = "892586ae4056d48df44b1671db04d73335d4b66e18fb61ccba2f6b7a3d3f4ca1"
EXPECTED_PRODUCT_PATHS = [
    "home-lab-gradient/.gitattributes",
    "home-lab-gradient/README.md",
    "home-lab-gradient/data/experiments.json",
    "home-lab-gradient/index.html",
    "home-lab-gradient/scripts/collect-linux",
    "home-lab-gradient/scripts/collect-linux.py",
    "home-lab-gradient/scripts/lab.py",
    "home-lab-gradient/seed/README.md",
    "home-lab-gradient/seed/collect-linux-host-observation-2.schema.json",
    "home-lab-gradient/seed/collect-linux.validator.py",
    "home-lab-gradient/seed/reconstruct.py",
    "home-lab-gradient/seed/seed-manifest.json",
    "home-lab-gradient/seed/sha256sums.txt",
    "home-lab-gradient/seed/verify.py",
    "home-lab-gradient/tests/test_collect_linux.py",
    "home-lab-gradient/tests/test_lab.py",
    "home-lab-gradient/tests/test_seed.py",
]


class AuditFailure(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path = ROOT) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    record = {
        "command": command,
        "returncode": process.returncode,
        "stdout_sha256": hashlib.sha256(process.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr.encode("utf-8")).hexdigest(),
    }
    if process.returncode != 0:
        excerpt = (process.stderr or process.stdout)[-4000:]
        raise AuditFailure(f"command failed ({process.returncode}): {' '.join(command)}\n{excerpt}")
    record["stdout"] = process.stdout
    record["stderr"] = process.stderr
    return record


def git_text(*args: str) -> str:
    result = run(["git", *args])
    return str(result["stdout"]).strip()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise AuditFailure(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exact_source_gate() -> dict[str, Any]:
    candidate_tree = git_text("rev-parse", f"{CANDIDATE}^{{tree}}")
    if candidate_tree != EXPECTED_TREE:
        raise AuditFailure(f"candidate tree differs: {candidate_tree}")
    merge_base = git_text("merge-base", BASE, CANDIDATE)
    if merge_base != BASE:
        raise AuditFailure(f"candidate does not preserve base by ancestry: {merge_base}")
    count = int(git_text("rev-list", "--count", f"{BASE}..{CANDIDATE}"))
    if count != 1:
        raise AuditFailure(f"expected one candidate commit, observed {count}")
    paths = sorted(filter(None, git_text("diff", "--name-only", BASE, CANDIDATE).splitlines()))
    if paths != sorted(EXPECTED_PRODUCT_PATHS):
        raise AuditFailure(f"candidate path denominator differs: {paths}")
    product_drift = git_text("diff", "--name-only", CANDIDATE, "HEAD", "--", "home-lab-gradient")
    if product_drift:
        raise AuditFailure(f"audit branch changes product source: {product_drift}")
    lf_paths = [
        GRADIENT / "scripts" / "collect-linux",
        GRADIENT / "scripts" / "collect-linux.py",
        *sorted((GRADIENT / "seed").rglob("*")),
        GRADIENT / "tests" / "test_collect_linux.py",
        GRADIENT / "tests" / "test_seed.py",
    ]
    cr_paths = [
        path.relative_to(ROOT).as_posix()
        for path in lf_paths
        if path.is_file() and b"\r" in path.read_bytes()
    ]
    if cr_paths:
        raise AuditFailure(f"LF-pinned members contain CR bytes: {cr_paths}")
    seed_id = hashlib.sha256((GRADIENT / "seed" / "sha256sums.txt").read_bytes()).hexdigest()
    if seed_id != EXPECTED_SEED_ID:
        raise AuditFailure(f"seed identity differs: {seed_id}")
    return {
        "candidate": CANDIDATE,
        "candidate_tree": candidate_tree,
        "base": BASE,
        "commits": count,
        "changed_paths": paths,
        "lf_pinned_cr_members": cr_paths,
        "seed_id": seed_id,
    }


def baseline_denominator() -> dict[str, Any]:
    build = run([sys.executable, str(SCRIPTS / "lab.py"), "build", "--now", "2026-08-05T00:00:00Z"])
    count_probe = run(
        [
            sys.executable,
            "-c",
            (
                "import unittest;"
                "s=unittest.defaultTestLoader.discover('home-lab-gradient/tests');"
                "c=s.countTestCases();print(c);"
                "raise SystemExit(0 if c==99 else 1)"
            ),
        ]
    )
    suite = run([sys.executable, "-m", "unittest", "discover", "-s", "home-lab-gradient/tests", "-v"])
    combined = str(suite["stdout"]) + str(suite["stderr"])
    match = re.search(r"Ran\s+(\d+)\s+tests?", combined)
    if match is None or int(match.group(1)) != 99 or not re.search(r"\bOK\b", combined):
        raise AuditFailure("candidate suite did not report exact 99/99 success")
    validate = run([sys.executable, str(SCRIPTS / "lab.py"), "validate"])
    try:
        validation = json.loads(str(validate["stdout"]))
    except json.JSONDecodeError as exc:
        raise AuditFailure(f"source validation did not emit JSON: {exc}") from exc
    if validation.get("status") != "PASS":
        raise AuditFailure(f"source validation refused: {validation}")
    verify = run([sys.executable, str(GRADIENT / "seed" / "verify.py"), "--root", str(GRADIENT)])
    reconstruct = run([sys.executable, str(GRADIENT / "seed" / "reconstruct.py"), "--root", str(GRADIENT)])
    try:
        seed_verify = json.loads(str(verify["stdout"]))
        seed_reconstruct = json.loads(str(reconstruct["stdout"]))
    except json.JSONDecodeError as exc:
        raise AuditFailure(f"seed tools did not emit JSON: {exc}") from exc
    if seed_verify.get("seed_id") != EXPECTED_SEED_ID:
        raise AuditFailure("seed verifier returned another identity")
    if not seed_reconstruct.get("ok") or not seed_reconstruct.get("byte_identical"):
        raise AuditFailure("seed reconstruction did not prove byte identity")
    dirty = git_text("diff", "--name-only", CANDIDATE, "--", "home-lab-gradient")
    if dirty:
        raise AuditFailure(f"candidate denominator modified its own source: {dirty}")
    return {
        "test_count": 99,
        "tests": "PASS",
        "source_validation": validation,
        "seed_verification": {
            "ok": seed_verify.get("ok"),
            "seed_id": seed_verify.get("seed_id"),
        },
        "seed_reconstruction": {
            "ok": seed_reconstruct.get("ok"),
            "byte_identical": seed_reconstruct.get("byte_identical"),
            "source_bundle_sha256": seed_reconstruct.get("source_bundle_sha256"),
        },
        "command_receipts": [
            {k: v for k, v in row.items() if k not in {"stdout", "stderr"}}
            for row in (build, count_probe, suite, validate, verify, reconstruct)
        ],
    }


def write_observation(path: Path, item: dict[str, Any], canonical_bytes: Any) -> None:
    item["observation_sha256"] = hashlib.sha256(
        canonical_bytes({key: value for key, value in item.items() if key != "observation_sha256"})
    ).hexdigest()
    path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8", newline="\n")


def import_candidate_modules() -> tuple[Any, Any, Any]:
    sys.path.insert(0, str(SCRIPTS))
    import lab  # type: ignore
    test_lab = load_module("gradient_candidate_test_lab", TESTS / "test_lab.py")
    test_collect = load_module("gradient_candidate_test_collect_linux", TESTS / "test_collect_linux.py")
    return lab, test_lab, test_collect


def relabelled_physical_host_attack(lab: Any, fixtures: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gradient-review-relabel-") as raw:
        base = Path(raw)
        state = base / "state"
        template = fixtures.observation("single-physical-seat", "GPU-SAME-PHYSICAL-DEVICE")
        template["system"]["computer_name"] = "single-physical-seat"
        template["cpu"][0]["processor_id"] = "SAME-PROCESSOR"
        template["graphics"]["adapters"][0]["pnp_device_id"] = "SAME-IGPU"
        template["graphics"]["adapters"][1]["pnp_device_id"] = "SAME-DGPU"
        template["graphics"]["nvidia"][0]["uuid"] = "GPU-SAME-PHYSICAL-DEVICE"
        paths: list[Path] = []
        for index, host_id in enumerate(("control-host", "heavy-host-a", "heavy-host-b"), start=1):
            item = copy.deepcopy(template)
            item["host_id"] = host_id
            item["observed_at"] = f"2026-08-05T00:00:0{index}Z"
            path = base / f"{host_id}.json"
            write_observation(path, item, fixtures.canonical_bytes)
            paths.append(path)
        receipt_path, receipt = lab.qualify_estate(
            observations=paths,
            state_dir=state,
            generated_at="2026-08-05T06:00:00Z",
            ingest=False,
        )
        aggregate = json.loads((receipt_path.parent / "estate-observation.json").read_text(encoding="utf-8"))
        same_names = {
            row.get("computer_name")
            for row in aggregate.get("hosts", [])
            if isinstance(row, dict)
        }
        return {
            "attack": "one physical fixture relabelled as three expected host_ids",
            "same_observed_computer_name_count": len(same_names),
            "same_gpu_uuid_submitted": True,
            "candidate_status": receipt.get("status"),
            "candidate_supports": receipt.get("supports"),
            "finding_reproduced": receipt.get("status") == "PASS",
        }


def unimplemented_seed_coordinate_contract_attack(test_collect: Any) -> dict[str, Any]:
    case = test_collect.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    try:
        target = case.base / "observations" / "not-the-host-id.json"
        _, failures = case.run_collect(host_id="undeclared-host", out_file=target)
        payload = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        accepted = not failures and target.is_file() and payload.get("host_id") == "undeclared-host"
        return {
            "attack": "undeclared host_id plus output basename unrelated to host_id",
            "collector_failures": failures,
            "published": target.is_file(),
            "published_host_id": payload.get("host_id"),
            "finding_reproduced": accepted,
        }
    finally:
        case.doCleanups()


def linked_temporary_output_attack(test_collect: Any) -> dict[str, Any]:
    case = test_collect.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    try:
        target = case.base / "observations" / "heavy-host-b.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = case.collector.temp_path_for(target.resolve())
        victim = case.base / "outside-named-output.txt"
        victim.write_text("sentinel-outside-the-named-output\n", encoding="utf-8")
        try:
            os.link(victim, temporary)
        except OSError as exc:
            return {
                "attack": "pre-existing hard-linked temporary output",
                "supported": False,
                "reason_class": type(exc).__name__,
                "finding_reproduced": False,
            }
        before = hashlib.sha256(victim.read_bytes()).hexdigest()
        _, failures = case.run_collect(host_id="heavy-host-b", out_file=target)
        after = hashlib.sha256(victim.read_bytes()).hexdigest()
        published = target.is_file()
        return {
            "attack": "pre-existing same-directory temp hard-linked to an unlisted file",
            "supported": True,
            "collector_failures": failures,
            "published": published,
            "unlisted_file_modified": before != after,
            "finding_reproduced": not failures and published and before != after,
        }
    finally:
        case.doCleanups()


def aggregate_identity_regression(lab: Any, fixtures: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gradient-review-aggregate-") as raw:
        base = Path(raw)
        state = base / "state"
        paths: list[Path] = []
        for host_id, gpu in (
            ("control-host", "GPU-4060-UNIQUE"),
            ("heavy-host-a", "GPU-3090-A-UNIQUE"),
            ("heavy-host-b", "GPU-3090-B-UNIQUE"),
        ):
            item = fixtures.observation(host_id, gpu)
            path = base / f"{host_id}.json"
            write_observation(path, item, fixtures.canonical_bytes)
            paths.append(path)
        receipt_path, receipt = lab.qualify_estate(
            observations=paths,
            state_dir=state,
            generated_at="2026-08-05T06:10:00Z",
            ingest=False,
        )
        aggregate = json.loads((receipt_path.parent / "estate-observation.json").read_text(encoding="utf-8"))
        rows = aggregate.get("hosts", [])
        missing_device_rows = all(
            isinstance(row, dict)
            and "dgpu_identities" not in row
            and "igpu_candidates" not in row
            and "graphics" not in row
            for row in rows
        )
        source_semantic_relabel = True
        for row in rows:
            host_id = row["host_id"]
            retained = receipt_path.parent / "inputs" / f"{host_id}.json"
            retained_bytes_sha = hashlib.sha256(retained.read_bytes()).hexdigest()
            stored = json.loads(retained.read_text(encoding="utf-8"))
            source_semantic_relabel = source_semantic_relabel and (
                row.get("source_sha256") == stored.get("observation_sha256")
                and row.get("source_sha256") != retained_bytes_sha
            )
        base_source = git_text("show", f"{BASE}:home-lab-gradient/scripts/lab.py")
        predecessor_fields = all(
            token in base_source
            for token in (
                '"source_sha256": sha256_file(inputs_dir / f"{host_id}.json")',
                '"igpu_candidates": igpus',
                '"dgpu_identities": dgpus',
            )
        )
        supports_device = any(
            isinstance(row, dict) and row.get("capability") == "device_identity"
            for row in receipt.get("supports", [])
        )
        return {
            "attack": "inspect PASS aggregate emitted under unchanged estate-observation@1 schema",
            "candidate_status": receipt.get("status"),
            "device_identity_support_claimed": supports_device,
            "device_identity_rows_absent": missing_device_rows,
            "source_sha256_semantics_changed": source_semantic_relabel,
            "predecessor_contract_confirmed": predecessor_fields,
            "finding_reproduced": (
                receipt.get("status") == "PASS"
                and supports_device
                and missing_device_rows
                and source_semantic_relabel
                and predecessor_fields
            ),
        }


def body_free_execution_receipt_gap() -> dict[str, Any]:
    manifest = json.loads((GRADIENT / "seed" / "seed-manifest.json").read_text(encoding="utf-8"))
    readme = (GRADIENT / "seed" / "README.md").read_text(encoding="utf-8")
    declared_files = [str(item) for item in manifest.get("files", [])]
    receipt_member = any("receipt" in Path(item).name.lower() for item in declared_files)
    receipt_schema = False
    for relative in declared_files:
        path = GRADIENT / relative
        if path.is_file() and path.suffix.lower() in {".py", ".json", ".md", ""}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if "host-observation-execution-receipt" in text or "n01-observation-receipt" in text:
                receipt_schema = True
                break
    return_only_observation = "Return **only** the single `<host-id>.json` observation file." in readme
    return {
        "requirement": "body-contained N01 observation plus body-free receipt for the W01 join",
        "seed_manifest_receipt_member": receipt_member,
        "receipt_schema_present": receipt_schema,
        "readme_requires_only_observation": return_only_observation,
        "finding_reproduced": return_only_observation and not receipt_member and not receipt_schema,
    }


def permanent_ci_gap() -> dict[str, Any]:
    workflow = (ROOT / ".github" / "workflows" / "home-lab-gradient-validate.yml").read_text(encoding="utf-8")
    windows_present = bool(re.search(r"windows-(?:latest|20\d\d)", workflow, re.IGNORECASE))
    matrix_present = "matrix:" in workflow
    return {
        "workflow": ".github/workflows/home-lab-gradient-validate.yml",
        "windows_leg_present": windows_present,
        "matrix_present": matrix_present,
        "finding_reproduced": not windows_present,
    }


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        source = exact_source_gate()
        baseline = baseline_denominator()
        lab, fixtures, test_collect = import_candidate_modules()
        findings = [
            {
                "id": "P1-RELABELLED-PHYSICAL-HOST",
                "severity": "P1",
                **relabelled_physical_host_attack(lab, fixtures),
            },
            {
                "id": "P2-AGGREGATE-DEVICE-IDENTITY-LOSS",
                "severity": "P2",
                **aggregate_identity_regression(lab, fixtures),
            },
            {
                "id": "P2-SEED-COORDINATE-CONTRACT-UNENFORCED",
                "severity": "P2",
                **unimplemented_seed_coordinate_contract_attack(test_collect),
            },
            {
                "id": "P1-LINKED-TEMPORARY-OUTPUT-ESCAPES-BOUNDARY",
                "severity": "P1",
                **linked_temporary_output_attack(test_collect),
            },
            {
                "id": "GATE-BODY-FREE-N01-RECEIPT-ABSENT",
                "severity": "acceptance-gate",
                **body_free_execution_receipt_gap(),
            },
            {
                "id": "GATE-WINDOWS-CI-ABSENT",
                "severity": "acceptance-gate",
                **permanent_ci_gap(),
            },
        ]
        all_reproduced = all(
            row["finding_reproduced"] or row.get("supported") is False
            for row in findings
        )
        result = {
            "schema": "axm-tools/gradient-151-independent-audit@1",
            "status": (
                "HOLD_REVIEW_FINDINGS_REPRODUCED"
                if all_reproduced
                else "REFUSED_AUDIT_EXPECTATION_NOT_REPRODUCED"
            ),
            "candidate_source": source,
            "baseline": baseline,
            "findings": findings,
            "physical_host_contacted": False,
            "physical_observation_generated": False,
            "provider_calls": 0,
            "model_calls": 0,
            "product_source_mutations": 0,
            "authority": "none",
            "claim_boundary": (
                "Independent synthetic source audit only. It does not establish or "
                "replace a physical N01 observation, three-host Estate qualification, "
                "merge authority, or A-17 authority."
            ),
        }
        atomic_write(args.out, result)
        print(json.dumps({"status": result["status"], "findings": [row["id"] for row in findings]}, sort_keys=True))
        return 0 if all_reproduced else 2
    except Exception as exc:
        result = {
            "schema": "axm-tools/gradient-151-independent-audit@1",
            "status": "REFUSED_AUDIT_EXECUTION",
            "error_class": type(exc).__name__,
            "error": str(exc),
            "physical_host_contacted": False,
            "physical_observation_generated": False,
            "provider_calls": 0,
            "model_calls": 0,
            "product_source_mutations": 0,
            "authority": "none",
        }
        try:
            atomic_write(args.out, result)
        except OSError:
            pass
        print(json.dumps(result, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
