#!/usr/bin/env python3
"""Receipt and evidence handling for Home Lab Capability Gradient.

The module never promotes narrative relevance. A receipt may support only a
capability and tier explicitly declared by the experiment catalog, and every
referenced artifact must be present and digest-correct at ingestion time.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from planner import PlannerError, canonical_bytes, require_keys, sha256_json

RECEIPT_SCHEMA = "axm-community-lab/experiment-receipt@1"
EVIDENCE_SCHEMA = "axm-community-lab/evidence-ledger@1"
INGESTIBLE_RECEIPT_STATUS = {"PASS", "PARTIAL"}
ALL_RECEIPT_STATUS = {"PASS", "PARTIAL", "FAIL"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlannerError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlannerError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlannerError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_receipt_id(receipt: Mapping[str, Any]) -> str:
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    return sha256_json(body)


def _experiment_map(experiments_doc: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = experiments_doc.get("experiments")
    if not isinstance(raw, list):
        raise PlannerError("experiment document requires experiments[]")
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise PlannerError(f"experiments[{index}] must be an object")
        require_keys(item, ["id", "produces", "acceptance"], f"experiments[{index}]")
        experiment_id = str(item["id"])
        if experiment_id in result:
            raise PlannerError(f"duplicate experiment: {experiment_id}")
        result[experiment_id] = item
    return result


def _allowed_productions(experiment: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    raw = experiment.get("produces")
    if not isinstance(raw, list):
        raise PlannerError(f"experiment {experiment.get('id')} produces must be an array")
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise PlannerError(f"experiment {experiment.get('id')} produces[{index}] must be an object")
        require_keys(item, ["capability", "tier"], f"experiment {experiment.get('id')} produces[{index}]")
        result[str(item["capability"])] = str(item["tier"])
    return result


def validate_receipt(
    receipt: Mapping[str, Any],
    receipt_path: Path,
    experiments_doc: Mapping[str, Any],
    tier_order: Sequence[str],
) -> dict[str, Any]:
    require_keys(
        receipt,
        [
            "schema",
            "experiment_id",
            "status",
            "checks",
            "artifacts",
            "supports",
            "claim_boundary",
        ],
        f"receipt {receipt_path}",
    )
    if receipt["schema"] != RECEIPT_SCHEMA:
        raise PlannerError(f"unsupported receipt schema in {receipt_path}: {receipt['schema']}")
    status = str(receipt["status"])
    if status not in INGESTIBLE_RECEIPT_STATUS:
        raise PlannerError(f"receipt {receipt_path} is not ingestible: status={status}")

    experiments = _experiment_map(experiments_doc)
    experiment_id = str(receipt["experiment_id"])
    if experiment_id not in experiments:
        raise PlannerError(f"receipt {receipt_path} references unknown experiment {experiment_id}")
    experiment = experiments[experiment_id]
    allowed = _allowed_productions(experiment)
    tiers = {tier: index for index, tier in enumerate(tier_order)}

    checks = receipt["checks"]
    if not isinstance(checks, list) or not checks:
        raise PlannerError(f"receipt {receipt_path} requires checks[]")
    seen_checks: set[str] = set()
    passing_checks = 0
    for index, check in enumerate(checks):
        if not isinstance(check, Mapping):
            raise PlannerError(f"receipt {receipt_path} checks[{index}] must be an object")
        require_keys(check, ["id", "pass"], f"receipt {receipt_path} checks[{index}]")
        check_id = str(check["id"])
        if check_id in seen_checks:
            raise PlannerError(f"receipt {receipt_path} has duplicate check {check_id}")
        seen_checks.add(check_id)
        if not isinstance(check["pass"], bool):
            raise PlannerError(f"receipt {receipt_path} check {check_id} pass must be boolean")
        passing_checks += int(check["pass"])
    if passing_checks == 0:
        raise PlannerError(f"receipt {receipt_path} has no passing checks")
    if status == "PASS" and passing_checks != len(checks):
        raise PlannerError(f"PASS receipt {receipt_path} contains a failing check")

    supports = receipt["supports"]
    if not isinstance(supports, list) or not supports:
        raise PlannerError(f"receipt {receipt_path} supports no capability")
    normalized_supports: list[dict[str, str]] = []
    seen_supports: set[str] = set()
    for index, support in enumerate(supports):
        if not isinstance(support, Mapping):
            raise PlannerError(f"receipt {receipt_path} supports[{index}] must be an object")
        require_keys(support, ["capability", "tier"], f"receipt {receipt_path} supports[{index}]")
        capability = str(support["capability"])
        tier = str(support["tier"])
        if capability in seen_supports:
            raise PlannerError(f"receipt {receipt_path} repeats support for {capability}")
        if capability not in allowed:
            raise PlannerError(
                f"receipt {receipt_path} promotes {capability}, which experiment {experiment_id} does not produce"
            )
        if tier not in tiers or allowed[capability] not in tiers:
            raise PlannerError(f"receipt {receipt_path} uses unknown evidence tier {tier}")
        if tiers[tier] > tiers[allowed[capability]]:
            raise PlannerError(
                f"receipt {receipt_path} promotes {capability} to {tier} above experiment ceiling {allowed[capability]}"
            )
        seen_supports.add(capability)
        normalized_supports.append({"capability": capability, "tier": tier})

    artifacts = receipt["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise PlannerError(f"receipt {receipt_path} requires at least one artifact")
    normalized_artifacts: list[dict[str, Any]] = []
    receipt_dir = receipt_path.parent.resolve()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            raise PlannerError(f"receipt {receipt_path} artifacts[{index}] must be an object")
        require_keys(artifact, ["path", "sha256"], f"receipt {receipt_path} artifacts[{index}]")
        relative = Path(str(artifact["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise PlannerError(f"receipt {receipt_path} artifact path escapes receipt directory: {relative}")
        absolute = (receipt_dir / relative).resolve()
        try:
            absolute.relative_to(receipt_dir)
        except ValueError as exc:
            raise PlannerError(f"receipt {receipt_path} artifact path escapes receipt directory: {relative}") from exc
        if not absolute.is_file():
            raise PlannerError(f"receipt {receipt_path} artifact missing: {relative}")
        observed = sha256_file(absolute)
        expected = str(artifact["sha256"]).lower()
        if observed != expected:
            raise PlannerError(
                f"receipt {receipt_path} artifact digest mismatch for {relative}: expected {expected}, got {observed}"
            )
        normalized_artifacts.append(
            {
                "path": relative.as_posix(),
                "sha256": observed,
                "bytes": absolute.stat().st_size,
            }
        )

    receipt_id = canonical_receipt_id(receipt)
    declared_receipt_id = receipt.get("receipt_sha256")
    if declared_receipt_id is not None and str(declared_receipt_id) != receipt_id:
        raise PlannerError(
            f"receipt {receipt_path} identity mismatch: expected {declared_receipt_id}, recomputed {receipt_id}"
        )

    return {
        "receipt_id": receipt_id,
        "experiment_id": experiment_id,
        "status": status,
        "supports": normalized_supports,
        "checks_passed": passing_checks,
        "checks_total": len(checks),
        "artifacts": normalized_artifacts,
        "claim_boundary": str(receipt["claim_boundary"]),
    }


def ingest_receipts(
    evidence_doc: Mapping[str, Any],
    receipt_paths: Iterable[Path],
    experiments_doc: Mapping[str, Any],
    tier_order: Sequence[str],
    *,
    as_of: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if evidence_doc.get("schema") != EVIDENCE_SCHEMA:
        raise PlannerError(f"unsupported evidence schema: {evidence_doc.get('schema')}")
    records = evidence_doc.get("records")
    if not isinstance(records, list):
        raise PlannerError("evidence document requires records[]")

    output_records = [dict(record) for record in records]
    known_receipts = {
        str(record.get("receipt_sha256"))
        for record in output_records
        if isinstance(record, Mapping) and record.get("receipt_sha256")
    }
    accepted: list[dict[str, Any]] = []
    for path in receipt_paths:
        receipt = load_json(path)
        validation = validate_receipt(receipt, path, experiments_doc, tier_order)
        if validation["receipt_id"] in known_receipts:
            accepted.append({**validation, "ingested": False, "reason": "already-present"})
            continue
        record = {
            "id": f"receipt-{validation['receipt_id'][:16]}",
            "tier": max(
                (support["tier"] for support in validation["supports"]),
                key=lambda tier: tier_order.index(tier),
            ),
            "status": "current",
            "source": "validated experiment receipt",
            "experiment_id": validation["experiment_id"],
            "receipt_sha256": validation["receipt_id"],
            "supports": validation["supports"],
            "facts": {
                "receipt_status": validation["status"],
                "checks_passed": validation["checks_passed"],
                "checks_total": validation["checks_total"],
                "artifacts": validation["artifacts"],
            },
            "boundary": validation["claim_boundary"],
        }
        output_records.append(record)
        known_receipts.add(validation["receipt_id"])
        accepted.append({**validation, "ingested": True})

    output = dict(evidence_doc)
    output["as_of"] = as_of
    output["records"] = output_records
    output["ledger_sha256"] = sha256_json(
        {
            "schema": output["schema"],
            "as_of": output["as_of"],
            "records": output["records"],
            "claim_boundary": output.get("claim_boundary"),
        }
    )
    return output, accepted


def make_receipt(
    *,
    experiment_id: str,
    status: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    artifact_paths: Iterable[Path],
    receipt_dir: Path,
    supports: list[dict[str, str]],
    claim_boundary: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in ALL_RECEIPT_STATUS:
        raise PlannerError(f"unsupported receipt status: {status}")
    receipt_dir = receipt_dir.resolve()
    artifacts: list[dict[str, Any]] = []
    for absolute in artifact_paths:
        absolute = absolute.resolve()
        try:
            relative = absolute.relative_to(receipt_dir)
        except ValueError as exc:
            raise PlannerError(f"artifact must be inside receipt directory: {absolute}") from exc
        artifacts.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256_file(absolute),
                "bytes": absolute.stat().st_size,
            }
        )
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "experiment_id": experiment_id,
        "status": status,
        "generated_at": generated_at,
        "checks": checks,
        "artifacts": artifacts,
        "supports": supports,
        "metadata": dict(metadata or {}),
        "claim_boundary": claim_boundary,
    }
    receipt["receipt_sha256"] = canonical_receipt_id(receipt)
    return receipt
