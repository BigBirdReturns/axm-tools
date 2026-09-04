#!/usr/bin/env python3
"""Independent adversarial audit of Gradient issue #151 exact head fe48d3.

This review program changes no Gradient product byte, contacts no physical host,
and produces no physical observation. It first reproduces the candidate's own
source denominator, then exercises the prior review attacks and two transaction
boundaries not covered by the implementation hand's suite.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GRADIENT = ROOT / "home-lab-gradient"
SCRIPTS = GRADIENT / "scripts"
TESTS = GRADIENT / "tests"

CANDIDATE = "fe48d3ad39fa5b52031fb42053bdcaf6c5915c10"
CANDIDATE_TREE = "8033cc3e86c806d5aa5245b42687fc5ac7e3944d"
BASE = "194a3f5e53fc15eaa18e08fb37d57a1750949f9e"
EXPECTED_COMMITS = 4
EXPECTED_TESTS = 141
EXPECTED_SEED_ID = "47db0d3241d23e3020f54be278fc2c884b531ad226685563b996c3e64f14651a"
EXPECTED_PAGE_SHA256 = "caee2b06ec5f0bd5c48be804668a6f979132f1df4ede0d3a7f1376e21a9abdf0"
EXPECTED_PATHS = [
    ".github/workflows/home-lab-gradient-validate.yml",
    "home-lab-gradient/.gitattributes",
    "home-lab-gradient/README.md",
    "home-lab-gradient/data/experiments.json",
    "home-lab-gradient/index.html",
    "home-lab-gradient/scripts/collect-linux",
    "home-lab-gradient/scripts/collect-linux.py",
    "home-lab-gradient/scripts/lab.py",
    "home-lab-gradient/scripts/render.py",
    "home-lab-gradient/seed/README.md",
    "home-lab-gradient/seed/collect-linux-host-observation-2.schema.json",
    "home-lab-gradient/seed/collect-linux.validator.py",
    "home-lab-gradient/seed/host-observation-receipt-1.schema.json",
    "home-lab-gradient/seed/reconstruct.py",
    "home-lab-gradient/seed/seed-manifest.json",
    "home-lab-gradient/seed/sha256sums.txt",
    "home-lab-gradient/seed/verify.py",
    "home-lab-gradient/tests/test_collect_linux.py",
    "home-lab-gradient/tests/test_lab.py",
    "home-lab-gradient/tests/test_render.py",
    "home-lab-gradient/tests/test_seed.py",
]


class AuditError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
        "stdout_sha256": sha256_bytes(process.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(process.stderr.encode("utf-8")),
    }
    if process.returncode != 0:
        detail = (process.stderr or process.stdout)[-5000:]
        raise AuditError(f"command failed ({process.returncode}): {' '.join(command)}\n{detail}")
    record["stdout"] = process.stdout
    record["stderr"] = process.stderr
    return record


def git_text(*arguments: str) -> str:
    return str(run(["git", *arguments])["stdout"]).strip()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise AuditError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exact_source_gate() -> dict[str, Any]:
    tree = git_text("rev-parse", f"{CANDIDATE}^{{tree}}")
    if tree != CANDIDATE_TREE:
        raise AuditError(f"candidate tree mismatch: {tree}")
    if git_text("merge-base", BASE, CANDIDATE) != BASE:
        raise AuditError("candidate does not preserve the PR #52 base by ancestry")
    commits = int(git_text("rev-list", "--count", f"{BASE}..{CANDIDATE}"))
    if commits != EXPECTED_COMMITS:
        raise AuditError(f"candidate commit denominator differs: {commits}")
    paths = sorted(filter(None, git_text("diff", "--name-only", BASE, CANDIDATE).splitlines()))
    if paths != sorted(EXPECTED_PATHS):
        raise AuditError(f"candidate changed-path denominator differs: {paths}")
    product_drift = git_text("diff", "--name-only", CANDIDATE, "HEAD", "--", "home-lab-gradient")
    if product_drift:
        raise AuditError(f"review branch changes Gradient product bytes: {product_drift}")
    seed_id = sha256_file(GRADIENT / "seed" / "sha256sums.txt")
    page_id = sha256_file(GRADIENT / "index.html")
    if seed_id != EXPECTED_SEED_ID:
        raise AuditError(f"seed identity differs: {seed_id}")
    if page_id != EXPECTED_PAGE_SHA256:
        raise AuditError(f"page identity differs: {page_id}")
    cr_members = []
    for path in [
        GRADIENT / "index.html",
        GRADIENT / "scripts" / "collect-linux",
        GRADIENT / "scripts" / "collect-linux.py",
        GRADIENT / "tests" / "test_collect_linux.py",
        GRADIENT / "tests" / "test_seed.py",
        *sorted((GRADIENT / "seed").rglob("*")),
    ]:
        if path.is_file() and b"\r" in path.read_bytes():
            cr_members.append(path.relative_to(ROOT).as_posix())
    if cr_members:
        raise AuditError(f"LF-pinned members contain CR bytes: {cr_members}")
    return {
        "head": CANDIDATE,
        "tree": tree,
        "base": BASE,
        "commits": commits,
        "changed_paths": paths,
        "seed_id": seed_id,
        "page_sha256": page_id,
        "lf_pinned_cr_members": cr_members,
    }


def candidate_denominator() -> dict[str, Any]:
    count = run(
        [
            sys.executable,
            "-c",
            (
                "import unittest;"
                "s=unittest.defaultTestLoader.discover('home-lab-gradient/tests');"
                "n=s.countTestCases();print(n);"
                f"raise SystemExit(0 if n=={EXPECTED_TESTS} else 1)"
            ),
        ]
    )
    suite = run([sys.executable, "-m", "unittest", "discover", "-s", "home-lab-gradient/tests", "-v"])
    combined = str(suite["stdout"]) + str(suite["stderr"])
    if f"Ran {EXPECTED_TESTS} tests" not in combined or "OK" not in combined:
        raise AuditError("candidate suite did not report the exact passing denominator")
    verify = run([sys.executable, str(GRADIENT / "seed" / "verify.py"), "--root", str(GRADIENT)])
    reconstruct = run([sys.executable, str(GRADIENT / "seed" / "reconstruct.py"), "--root", str(GRADIENT)])
    validate = run([sys.executable, str(SCRIPTS / "lab.py"), "validate"])
    build = run(
        [
            sys.executable,
            str(SCRIPTS / "lab.py"),
            "build",
            "--now",
            "2026-08-05T00:00:00Z",
        ]
    )
    drift = git_text("status", "--porcelain", "--", "home-lab-gradient")
    if drift:
        raise AuditError(f"fixed build or tests leave tracked product drift: {drift}")
    verification = json.loads(str(verify["stdout"]))
    reconstruction = json.loads(str(reconstruct["stdout"]))
    validation = json.loads(str(validate["stdout"]))
    if verification.get("seed_id") != EXPECTED_SEED_ID or not verification.get("ok"):
        raise AuditError("seed verification did not reproduce the expected identity")
    if not reconstruction.get("ok") or not reconstruction.get("byte_identical"):
        raise AuditError("seed reconstruction was not byte-identical")
    if validation.get("status") != "PASS":
        raise AuditError(f"source validation refused: {validation}")
    return {
        "test_count": EXPECTED_TESTS,
        "tests": "PASS",
        "seed_verification": verification,
        "seed_reconstruction": reconstruction,
        "source_validation": validation,
        "page_sha256_after_build": sha256_file(GRADIENT / "index.html"),
        "commands": [
            {key: value for key, value in row.items() if key not in {"stdout", "stderr"}}
            for row in (count, suite, verify, reconstruct, validate, build)
        ],
    }


def import_candidate() -> tuple[Any, Any, Any, Any]:
    sys.path.insert(0, str(SCRIPTS))
    import lab  # type: ignore

    test_lab = load_module("gradient_fe48d3_test_lab", TESTS / "test_lab.py")
    test_collect = load_module("gradient_fe48d3_test_collect", TESTS / "test_collect_linux.py")
    validator = load_module(
        "gradient_fe48d3_seed_validator",
        GRADIENT / "seed" / "collect-linux.validator.py",
    )
    return lab, test_lab, test_collect, validator


def write_observation(path: Path, item: dict[str, Any], canonical: Callable[[Any], bytes]) -> Path:
    item["observation_sha256"] = sha256_bytes(
        canonical({key: value for key, value in item.items() if key != "observation_sha256"})
    )
    path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def replay_relabelled_host(lab: Any, fixtures: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gradient-fe48-relabel-") as raw:
        root = Path(raw)
        template = fixtures.observation("one-machine", "GPU-ONE-MACHINE")
        template["system"]["computer_name"] = "one-machine"
        template["cpu"][0]["processor_id"] = "ONE-PROCESSOR"
        template["graphics"]["adapters"][0]["pnp_device_id"] = "ONE-IGPU"
        template["graphics"]["adapters"][1]["pnp_device_id"] = "ONE-DGPU"
        template["graphics"]["nvidia"][0]["uuid"] = "GPU-ONE-MACHINE"
        paths = []
        for ordinal, role in enumerate(("control-host", "heavy-host-a", "heavy-host-b"), 1):
            item = copy.deepcopy(template)
            item["host_id"] = role
            item["observed_at"] = f"2026-09-04T00:00:0{ordinal}Z"
            paths.append(write_observation(root / f"{role}.json", item, fixtures.canonical_bytes))
        receipt_path, receipt = lab.qualify_estate(
            observations=paths,
            state_dir=root / "state",
            generated_at="2026-09-04T00:01:00Z",
            ingest=False,
        )
        distinct = next(row for row in receipt["checks"] if row["id"] == "distinct-physical-hosts")
        return {
            "status": receipt["status"],
            "supports": receipt["supports"],
            "distinct_physical_hosts_pass": distinct["pass"],
            "receipt_sha256": sha256_file(receipt_path),
            "closed": receipt["status"] == "FAIL" and not receipt["supports"] and distinct["pass"] is False,
        }


def replay_hard_link(linux_tests: Any) -> dict[str, Any]:
    case = linux_tests.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    try:
        case.output.parent.mkdir(parents=True, exist_ok=True)
        victim = case.base / "unlisted.txt"
        original = b"unlisted bytes must remain unchanged\n"
        victim.write_bytes(original)
        historical = case.collector.temp_path_for(case.output.resolve())
        os.link(victim, historical)
        _, failures = case.run_collect()
        receipt = case.output.parent / "heavy-host-b.receipt.json"
        return {
            "failures": failures,
            "victim_unchanged": victim.read_bytes() == original,
            "observation_published": case.output.exists(),
            "receipt_published": receipt.exists(),
            "alias_retained": historical.exists(),
            "closed": bool(failures)
            and victim.read_bytes() == original
            and not case.output.exists()
            and not receipt.exists(),
        }
    finally:
        case.doCleanups()


def replay_coordinate_refusals(linux_tests: Any) -> dict[str, Any]:
    case = linux_tests.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    reads = 0

    def tripwire(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal reads
        reads += 1
        raise AssertionError("host surface read")

    results: list[str] = []
    try:
        with mock.patch.object(case.collector, "read_uname", tripwire):
            for host_id, name in (
                ("undeclared-host", "undeclared-host.json"),
                ("heavy-host-b", "not-the-host-id.json"),
            ):
                target = case.base / "never-created" / name
                try:
                    case.collector.collect(host_id, target)
                except case.collector.CoordinateError as exc:
                    results.append(str(exc))
        return {
            "refusals": results,
            "host_surface_reads": reads,
            "directory_created": (case.base / "never-created").exists(),
            "closed": len(results) == 2 and reads == 0 and not (case.base / "never-created").exists(),
        }
    finally:
        case.doCleanups()


def replay_aggregate_compatibility(lab: Any, fixtures: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gradient-fe48-aggregate-") as raw:
        root = Path(raw)
        paths = []
        for host_id, gpu in (
            ("control-host", "GPU-CONTROL"),
            ("heavy-host-a", "GPU-HEAVY-A"),
            ("heavy-host-b", "GPU-HEAVY-B"),
        ):
            paths.append(
                write_observation(root / f"{host_id}.json", fixtures.observation(host_id, gpu), fixtures.canonical_bytes)
            )
        receipt_path, receipt = lab.qualify_estate(
            observations=paths,
            state_dir=root / "state",
            generated_at="2026-09-04T00:02:00Z",
            ingest=False,
        )
        aggregate = json.loads((receipt_path.parent / "estate-observation.json").read_text(encoding="utf-8"))
        rows = aggregate["hosts"]
        compatible = receipt["status"] == "PASS"
        for row in rows:
            retained = receipt_path.parent / "inputs" / f"{row['host_id']}.json"
            compatible = compatible and (
                row.get("source_sha256") == sha256_file(retained)
                and row.get("source_file_sha256") == sha256_file(retained)
                and row.get("observation_sha256")
                == json.loads(retained.read_text(encoding="utf-8"))["observation_sha256"]
                and "igpu_candidates" in row
                and "dgpu_identities" in row
            )
        return {
            "status": receipt["status"],
            "host_rows": len(rows),
            "compatible": bool(compatible),
            "closed": bool(compatible),
        }


def replay_receipt_contract(linux_tests: Any, validator: Any) -> dict[str, Any]:
    case = linux_tests.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    try:
        _, failures = case.run_collect()
        receipt_path = case.output.parent / "heavy-host-b.receipt.json"
        observation = json.loads(case.output.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_failures = validator.validate_receipt(receipt, observation, case.output)
        return {
            "collector_failures": failures,
            "receipt_failures": receipt_failures,
            "carries_observation_body": receipt.get("carries_observation_body"),
            "closed": not failures
            and not receipt_failures
            and receipt.get("carries_observation_body") is False,
        }
    finally:
        case.doCleanups()


def final_output_symlink_attack(linux_tests: Any) -> dict[str, Any]:
    case = linux_tests.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    try:
        case.output.parent.mkdir(parents=True, exist_ok=True)
        outside = case.base / "outside-boundary"
        outside.mkdir()
        victim = outside / "victim.json"
        original = b"outside object the operator did not name\n"
        victim.write_bytes(original)
        try:
            os.symlink(victim, case.output)
        except (OSError, NotImplementedError) as exc:
            return {
                "supported": False,
                "reason_class": type(exc).__name__,
                "vulnerable": False,
            }
        _, failures = case.run_collect()
        escaped_receipt = outside / "heavy-host-b.receipt.json"
        vulnerable = (
            not failures
            and case.output.is_symlink()
            and victim.read_bytes() != original
            and escaped_receipt.is_file()
        )
        return {
            "supported": True,
            "collector_failures": failures,
            "requested_output_remains_symlink": case.output.is_symlink(),
            "unlisted_victim_modified": victim.read_bytes() != original,
            "receipt_written_outside_requested_directory": escaped_receipt.is_file(),
            "vulnerable": vulnerable,
        }
    finally:
        case.doCleanups()


def incomplete_two_file_transaction_attack(
    lab: Any,
    fixtures: Any,
    linux_tests: Any,
) -> dict[str, Any]:
    case = linux_tests.CollectLinuxTestCase(methodName="runTest")
    case.setUp()
    try:
        real_write = case.collector.write_atomic_json
        call_count = 0

        def fail_second(payload: Any, path: Path) -> Path:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise case.collector.CollectorError("injected receipt publication failure")
            return real_write(payload, path)

        with mock.patch.object(case.collector, "write_atomic_json", side_effect=fail_second):
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    case.run_collect()
                except case.collector.CollectorError:
                    pass
        body_exists = case.output.is_file()
        receipt_path = case.output.parent / "heavy-host-b.receipt.json"
        receipt_exists = receipt_path.is_file()

        join_root = case.base / "join"
        join_root.mkdir()
        paths = []
        for host_id, gpu in (
            ("control-host", "GPU-CONTROL"),
            ("heavy-host-a", "GPU-HEAVY-A"),
        ):
            paths.append(
                write_observation(
                    join_root / f"{host_id}.json",
                    fixtures.observation(host_id, gpu),
                    fixtures.canonical_bytes,
                )
            )
        if body_exists:
            paths.append(case.output)
        join_status = "NOT_RUN"
        join_supports: list[dict[str, Any]] = []
        if len(paths) == 3:
            _, join_receipt = lab.qualify_estate(
                observations=paths,
                state_dir=join_root / "state",
                generated_at="2026-09-04T00:03:00Z",
                ingest=False,
            )
            join_status = join_receipt["status"]
            join_supports = join_receipt["supports"]
        vulnerable = body_exists and not receipt_exists and join_status == "PASS"
        return {
            "injected_failure_on_publication_number": 2,
            "observation_body_survived": body_exists,
            "body_free_receipt_survived": receipt_exists,
            "qualifier_accepts_observation_without_receipt": join_status == "PASS",
            "join_status": join_status,
            "join_supports": join_supports,
            "vulnerable": vulnerable,
        }
    finally:
        case.doCleanups()


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
        baseline = candidate_denominator()
        lab, fixtures, linux_tests, validator = import_candidate()
        prior_repairs = {
            "relabelled_physical_host": replay_relabelled_host(lab, fixtures),
            "deterministic_temp_hard_link": replay_hard_link(linux_tests),
            "seed_coordinate_refusals": replay_coordinate_refusals(linux_tests),
            "aggregate_compatibility": replay_aggregate_compatibility(lab, fixtures),
            "body_free_receipt_contract": replay_receipt_contract(linux_tests, validator),
            "deterministic_page_identity": {
                "observed": baseline["page_sha256_after_build"],
                "expected": EXPECTED_PAGE_SHA256,
                "closed": baseline["page_sha256_after_build"] == EXPECTED_PAGE_SHA256,
            },
        }
        if not all(row.get("closed") is True for row in prior_repairs.values()):
            raise AuditError(f"one or more declared repairs did not reproduce: {prior_repairs}")

        findings = {
            "P1_FINAL_OUTPUT_SYMLINK_ESCAPE": final_output_symlink_attack(linux_tests),
            "P1_RECEIPTLESS_BODY_CAN_ENTER_THREE_HOST_JOIN": incomplete_two_file_transaction_attack(
                lab, fixtures, linux_tests
            ),
        }
        reproduced = [
            name
            for name, row in findings.items()
            if row.get("vulnerable") is True
        ]
        result = {
            "schema": "axm-tools/gradient-151-fe48d3-independent-audit@1",
            "status": (
                "HOLD_INDEPENDENT_REVIEW_FINDINGS_REPRODUCED"
                if reproduced
                else "PASS_INDEPENDENT_SOURCE_REVIEW"
            ),
            "candidate_source": source,
            "candidate_denominator": baseline,
            "prior_review_repairs": prior_repairs,
            "findings": findings,
            "reproduced_finding_ids": reproduced,
            "physical_host_contacted": False,
            "physical_observation_generated": False,
            "provider_calls": 0,
            "model_calls": 0,
            "product_source_mutations": 0,
            "authority": "none",
            "claim_boundary": (
                "Synthetic exact-source audit only. It establishes neither a physical N01 "
                "observation nor a three-host Estate PASS and grants no merge or A-17 authority."
            ),
        }
        atomic_write(args.out, result)
        print(json.dumps({"status": result["status"], "findings": reproduced}, sort_keys=True))
        return 0
    except Exception as exc:
        result = {
            "schema": "axm-tools/gradient-151-fe48d3-independent-audit@1",
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
