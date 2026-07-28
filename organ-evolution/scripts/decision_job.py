#!/usr/bin/env python3
"""Compile and verify an accepted Organ Evolution decision circulation job.

The compiler serializes a human-owned, already accepted decision. It does not
authenticate the decider, create a mandate, choose a lane, schedule an actor, or
accept an execution outcome. Bloodstream may later record the resulting job but
must retain the same boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

MODEL_FORMAT = "axm-organ-evolution/1"
DECISION_FORMAT = "axm-organ-decision/1"
JOB_FORMAT = "axm-organ-evolution-job/1"
MAX_JSON_BYTES = 4_000_000
MAX_TEXT = 32_000
MAX_REFERENCES = 256
GATES = {"function", "authority", "evidence", "migration", "reversibility"}
TERMINAL_OUTCOMES = {"done", "abandoned", "superseded", "refused", "failed"}
EXECUTION_STATES = {"not_started", "in_progress", "verified", "failed"}
AUTHORITY = {
    "decision": "external human-owned decision assertion; this compiler does not authenticate the mandate or decider",
    "circulation": "Bloodstream may record, route, block, invalidate, recover, and report the job only",
    "execution": "the owning implementation organ and cited verifiers",
    "acceptance": "the named decision authority under the cited mandate",
    "compiler": "canonical serialization and structural refusal only",
    "forbidden": [
        "automatic admission",
        "priority inference",
        "supplier selection",
        "agent scheduling",
        "branch merge",
        "action execution",
        "outcome acceptance",
        "campaign mutation",
    ],
}


class DecisionJobError(ValueError):
    pass


def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DecisionJobError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def validate_depth(value: Any, depth: int = 0) -> None:
    if depth > 128:
        raise DecisionJobError("JSON nesting exceeds 128")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or len(key) > 256:
                raise DecisionJobError("JSON object key is invalid or oversized")
            validate_depth(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > 100_000:
            raise DecisionJobError("JSON array is oversized")
        for child in value:
            validate_depth(child, depth + 1)
    elif isinstance(value, str) and len(value) > MAX_TEXT:
        raise DecisionJobError("JSON text value is oversized")
    elif isinstance(value, float):
        raise DecisionJobError("floating-point semantic values are not permitted")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DecisionJobError(f"JSON source is absent: {path}")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise DecisionJobError(f"JSON source exceeds {MAX_JSON_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecisionJobError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DecisionJobError(f"JSON root must be an object: {path}")
    validate_depth(value)
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def without_key(value: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: item for name, item in value.items() if name != key}


def indexed(rows: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise DecisionJobError(f"{label} must be an array")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise DecisionJobError(f"{label} records require stable string IDs")
        if row["id"] in result:
            raise DecisionJobError(f"duplicate {label} ID: {row['id']}")
        result[row["id"]] = row
    return result


def required_text(value: Any, label: str, *, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionJobError(f"{label} must be a non-empty string")
    clean = value.strip()
    if len(clean) > maximum:
        raise DecisionJobError(f"{label} exceeds {maximum} characters")
    return clean


def string_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise DecisionJobError(f"{label} must be an array")
    if len(value) > MAX_REFERENCES:
        raise DecisionJobError(f"{label} contains too many entries")
    result: list[str] = []
    for item in value:
        result.append(required_text(item, label, maximum=4_096))
    if not allow_empty and not result:
        raise DecisionJobError(f"{label} must not be empty")
    if len(set(result)) != len(result):
        raise DecisionJobError(f"{label} contains duplicate entries")
    return result


def evidence_is_independent(row: dict[str, Any]) -> bool:
    return (
        row.get("independence") == "independent"
        and row.get("tier") in {"confirmed", "measured", "reported"}
    )


def validate_execution(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionJobError("decision.execution must be an object")
    state = value.get("state")
    if state not in EXECUTION_STATES:
        raise DecisionJobError(f"unsupported execution state: {state!r}")
    result: dict[str, Any] = {
        "state": state,
        "authority": required_text(value.get("authority"), "decision.execution.authority"),
    }
    implementation = string_list(
        value.get("implementationRefs", []),
        "decision.execution.implementationRefs",
    )
    verification = string_list(
        value.get("verificationRefs", []),
        "decision.execution.verificationRefs",
    )
    if implementation:
        result["implementationRefs"] = implementation
    if verification:
        result["verificationRefs"] = verification
    if state in {"verified", "failed"}:
        outcome = value.get("outcome")
        if outcome not in TERMINAL_OUTCOMES:
            raise DecisionJobError(
                f"terminal execution requires outcome in {sorted(TERMINAL_OUTCOMES)}"
            )
        result["outcome"] = outcome
        result["completedAt"] = required_text(
            value.get("completedAt"), "decision.execution.completedAt", maximum=128
        )
        if not implementation or not verification:
            raise DecisionJobError(
                "terminal execution requires implementation and verification references"
            )
    elif value.get("outcome") is not None:
        raise DecisionJobError("non-terminal execution cannot carry an outcome")
    return result


def validate_circulation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionJobError("decision.circulation must be an object")
    lane = value.get("lane")
    if lane not in {"A", "B"}:
        raise DecisionJobError("decision.circulation.lane must be A or B")
    consumers = string_list(
        value.get("consumers"),
        "decision.circulation.consumers",
        allow_empty=False,
    )
    blocked_on = value.get("blockedOn", "")
    if not isinstance(blocked_on, str) or len(blocked_on) > 256:
        raise DecisionJobError("decision.circulation.blockedOn must be bounded text")
    return {
        "lane": lane,
        "task": required_text(value.get("task"), "decision.circulation.task"),
        "surface": required_text(value.get("surface"), "decision.circulation.surface", maximum=1_024),
        "producer": required_text(value.get("producer"), "decision.circulation.producer", maximum=1_024),
        "consumers": consumers,
        "blockedOn": blocked_on.strip(),
    }


def build_job(model: dict[str, Any]) -> dict[str, Any]:
    if model.get("format") != MODEL_FORMAT:
        raise DecisionJobError(f"model must use {MODEL_FORMAT}")
    estate = model.get("estate")
    if not isinstance(estate, dict):
        raise DecisionJobError("model.estate must be an object")
    estate_id = required_text(estate.get("id"), "estate.id", maximum=256)
    organs = indexed(model.get("organs"), "organ")
    candidates = indexed(model.get("candidates"), "candidate")
    actors = indexed(model.get("actors"), "actor")
    evidence = indexed(model.get("evidence"), "evidence")

    source_decision = model.get("decision")
    if not isinstance(source_decision, dict):
        raise DecisionJobError("model.decision must be an object")
    if source_decision.get("state") != "accepted":
        raise DecisionJobError("only an accepted decision may enter circulation")
    organ_id = required_text(source_decision.get("organId"), "decision.organId", maximum=256)
    candidate_id = required_text(
        source_decision.get("candidateId"), "decision.candidateId", maximum=256
    )
    decider_id = required_text(source_decision.get("decider"), "decision.decider", maximum=256)
    organ = organs.get(organ_id)
    candidate = candidates.get(candidate_id)
    decider = actors.get(decider_id)
    if organ is None:
        raise DecisionJobError(f"decision references unknown organ {organ_id}")
    if candidate is None or candidate.get("organId") != organ_id:
        raise DecisionJobError(
            f"decision candidate {candidate_id} does not belong to {organ_id}"
        )
    if decider is None:
        raise DecisionJobError(f"decision references unknown actor {decider_id}")
    declared_deciders = ((candidate.get("actorLinks") or {}).get("deciders") or [])
    if decider_id not in declared_deciders:
        raise DecisionJobError(
            f"decision actor {decider_id} is not a declared decider for {candidate_id}"
        )

    gates = candidate.get("gates")
    if not isinstance(gates, dict) or set(gates) != GATES:
        raise DecisionJobError("candidate hard-gate set is incomplete")
    if any(value != "pass" for value in gates.values()):
        raise DecisionJobError("only a candidate with every hard gate passing may circulate")
    dimensions = candidate.get("dimensions")
    if not isinstance(dimensions, dict):
        raise DecisionJobError("candidate dimensions are absent")
    if any(not isinstance(value, int) or not 0 <= value <= 5 for value in dimensions.values()):
        raise DecisionJobError("candidate dimensions must be integer values from 0 to 5")

    changes = candidate.get("changes")
    if not isinstance(changes, dict) or set(changes) != {
        "preserve",
        "alter",
        "retire",
        "introduce",
    }:
        raise DecisionJobError("candidate migration ledger is incomplete")
    migration = {
        key: string_list(changes[key], f"candidate.changes.{key}")
        for key in ("preserve", "alter", "retire", "introduce")
    }

    evidence_rows: list[dict[str, Any]] = []
    for evidence_id in string_list(
        candidate.get("evidenceIds", []), "candidate.evidenceIds", allow_empty=False
    ):
        row = evidence.get(evidence_id)
        if row is None:
            raise DecisionJobError(f"candidate references unknown evidence {evidence_id}")
        evidence_rows.append(
            {
                "id": evidence_id,
                "title": required_text(row.get("title"), f"{evidence_id}.title"),
                "tier": required_text(row.get("tier"), f"{evidence_id}.tier", maximum=64),
                "independence": required_text(
                    row.get("independence"), f"{evidence_id}.independence", maximum=64
                ),
                "source": required_text(row.get("source"), f"{evidence_id}.source"),
                "claim": required_text(row.get("claim"), f"{evidence_id}.claim"),
                "limits": required_text(row.get("limits"), f"{evidence_id}.limits"),
            }
        )
    if not any(evidence_is_independent(row) for row in evidence_rows):
        raise DecisionJobError(
            "accepted circulation requires at least one independent confirmed, measured, or reported evidence record"
        )

    decision: dict[str, Any] = {
        "format": DECISION_FORMAT,
        "estateId": estate_id,
        "organId": organ_id,
        "organName": required_text(organ.get("name"), "organ.name"),
        "candidateId": candidate_id,
        "candidateName": required_text(candidate.get("name"), "candidate.name"),
        "action": required_text(candidate.get("action"), "candidate.action", maximum=128),
        "state": "accepted",
        "posture": "admissible",
        "decider": {
            "id": decider_id,
            "name": required_text(decider.get("name"), "decider.name"),
        },
        "decidedAt": required_text(
            source_decision.get("decidedAt"), "decision.decidedAt", maximum=128
        ),
        "mandate": {
            "ref": required_text(
                source_decision.get("mandateRef"), "decision.mandateRef", maximum=2_048
            ),
            "basis": required_text(
                source_decision.get("mandateBasis"), "decision.mandateBasis"
            ),
            "authentication": "not performed by the compiler",
        },
        "rationale": required_text(source_decision.get("rationale"), "decision.rationale"),
        "openQuestions": string_list(
            source_decision.get("openQuestions", []), "decision.openQuestions"
        ),
        "gates": {key: gates[key] for key in sorted(gates)},
        "dimensions": {key: dimensions[key] for key in sorted(dimensions)},
        "migration": migration,
        "evidence": sorted(evidence_rows, key=lambda row: row["id"]),
        "execution": validate_execution(source_decision.get("execution")),
    }
    decision["decisionId"] = digest("orgdec1", decision)

    bundle: dict[str, Any] = {
        "format": JOB_FORMAT,
        "source": {
            "modelFormat": MODEL_FORMAT,
            "estateId": estate_id,
            "modelDigest": digest("orgmodel1", model),
        },
        "decision": decision,
        "circulation": validate_circulation(source_decision.get("circulation")),
        "authority": AUTHORITY,
        "limits": [
            "The compiler validates structure and declared decision geometry; it does not authenticate the mandate, decider, cited evidence, implementation, or outcome.",
            "Bloodstream may preserve and report this job but cannot admit it, prioritize it, execute it, or accept its outcome.",
            "Any consumer must verify cited implementation and verification references independently when that distinction matters.",
        ],
    }
    bundle["jobId"] = digest("organjob1", bundle)
    verify_job(bundle)
    return bundle


def verify_job(bundle: dict[str, Any]) -> None:
    validate_depth(bundle)
    if bundle.get("format") != JOB_FORMAT:
        raise DecisionJobError(f"job bundle must use {JOB_FORMAT}")
    if bundle.get("authority") != AUTHORITY:
        raise DecisionJobError("job authority membrane differs from the compiler contract")
    decision = bundle.get("decision")
    if not isinstance(decision, dict) or decision.get("format") != DECISION_FORMAT:
        raise DecisionJobError("job contains no supported decision record")
    if decision.get("state") != "accepted" or decision.get("posture") != "admissible":
        raise DecisionJobError("job decision is not accepted and admissible")
    if set(decision.get("gates") or {}) != GATES or any(
        value != "pass" for value in (decision.get("gates") or {}).values()
    ):
        raise DecisionJobError("job decision hard gates do not all pass")
    expected_decision = digest("orgdec1", without_key(decision, "decisionId"))
    if decision.get("decisionId") != expected_decision:
        raise DecisionJobError("decision identity mismatch")
    circulation = validate_circulation(bundle.get("circulation"))
    if circulation != bundle.get("circulation"):
        raise DecisionJobError("circulation record is not canonical")
    validate_execution(decision.get("execution"))
    expected_job = digest("organjob1", without_key(bundle, "jobId"))
    if bundle.get("jobId") != expected_job:
        raise DecisionJobError("job identity mismatch")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("model", type=Path)
    build.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("job", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "build":
            value = build_job(load_json(args.model))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "format": JOB_FORMAT,
                        "status": "pass",
                        "decisionId": value["decision"]["decisionId"],
                        "jobId": value["jobId"],
                        "output": str(args.output),
                    },
                    sort_keys=True,
                )
            )
        else:
            value = load_json(args.job)
            verify_job(value)
            print(
                json.dumps(
                    {
                        "format": JOB_FORMAT,
                        "status": "pass",
                        "decisionId": value["decision"]["decisionId"],
                        "jobId": value["jobId"],
                    },
                    sort_keys=True,
                )
            )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
