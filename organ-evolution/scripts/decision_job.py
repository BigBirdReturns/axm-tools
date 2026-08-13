#!/usr/bin/env python3
"""Compile and verify an accepted Organ Evolution circulation job.

The compiler serializes a human-owned, already accepted decision. It does not
authenticate the decider, create a mandate, choose a lane, schedule an actor,
execute an adaptation, or accept an outcome. Bloodstream may preserve and route
the resulting job only under the same authority membrane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

MODEL_FORMAT = "axm-organ-evolution/1"
DECISION_FORMAT = "axm-organ-decision/1"
JOB_FORMAT = "axm-organ-evolution-job/1"
EXECUTION_FORMAT = "axm-organ-execution/1"
MAX_JSON_BYTES = 4_000_000
MAX_TEXT = 32_000
MAX_REFERENCES = 256
DIMENSIONS = {
    "function",
    "authority",
    "reversibility",
    "dependency",
    "adaptability",
    "observability",
    "succession",
    "efficiency",
    "userValue",
    "captureResistance",
    "containment",
    "evidence",
}
GATES = {"function", "authority", "evidence", "migration", "reversibility"}
TERMINAL_OUTCOMES = {"done", "abandoned", "superseded", "refused", "failed"}
EXECUTION_STATES = {"in_progress", "verified", "failed"}
EVIDENCE_TIERS = {"confirmed", "measured", "reported", "derived", "judgment", "open"}
INDEPENDENCE = {"independent", "mixed", "self", "unknown"}
DIGEST_RE = re.compile(r"^[a-z0-9]+_[0-9a-f]{64}$")
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


def exact_keys(value: Any, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionJobError(f"{label} must be an object")
    keys = set(value)
    if keys != required:
        missing = sorted(required - keys)
        extra = sorted(keys - required)
        raise DecisionJobError(f"{label} keys differ; missing={missing}, extra={extra}")
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
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise DecisionJobError(f"unsupported JSON semantic value: {type(value).__name__}")


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


def without_keys(value: dict[str, Any], *keys: str) -> dict[str, Any]:
    removed = set(keys)
    return {name: item for name, item in value.items() if name not in removed}



def source_model_projection(model: dict[str, Any]) -> dict[str, Any]:
    """Bind the accepted workspace without optional execution evidence."""
    projection = json.loads(json.dumps(model))
    decision = projection.get("decision")
    if isinstance(decision, dict):
        decision.pop("execution", None)
    return projection


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


def optional_text(value: Any, label: str, *, maximum: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > maximum:
        raise DecisionJobError(f"{label} must be bounded text")
    return value.strip()


def iso_time(value: Any, label: str) -> str:
    text = required_text(value, label, maximum=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionJobError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DecisionJobError(f"{label} must include a timezone")
    return text


def string_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise DecisionJobError(f"{label} must be an array")
    if len(value) > MAX_REFERENCES:
        raise DecisionJobError(f"{label} contains too many entries")
    result = [required_text(item, label, maximum=4_096) for item in value]
    if not allow_empty and not result:
        raise DecisionJobError(f"{label} must not be empty")
    if len(set(result)) != len(result):
        raise DecisionJobError(f"{label} contains duplicate entries")
    return result


def validate_digest(value: Any, prefix: str, label: str) -> str:
    text = required_text(value, label, maximum=128)
    if not text.startswith(prefix + "_") or not DIGEST_RE.fullmatch(text):
        raise DecisionJobError(f"{label} is not a supported {prefix} identity")
    return text


def evidence_is_independent(row: dict[str, Any]) -> bool:
    return row["independence"] == "independent" and row["tier"] in {
        "confirmed",
        "measured",
        "reported",
    }


def normalize_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise DecisionJobError("decision.evidence must be a non-empty array")
    if len(value) > MAX_REFERENCES:
        raise DecisionJobError("decision.evidence contains too many records")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    required = {"id", "title", "tier", "independence", "source", "claim", "limits"}
    for raw in value:
        row = exact_keys(raw, required, "decision evidence record")
        evidence_id = required_text(row["id"], "evidence.id", maximum=256)
        if evidence_id in seen:
            raise DecisionJobError(f"duplicate decision evidence ID: {evidence_id}")
        seen.add(evidence_id)
        tier = required_text(row["tier"], f"{evidence_id}.tier", maximum=64)
        independence = required_text(
            row["independence"], f"{evidence_id}.independence", maximum=64
        )
        if tier not in EVIDENCE_TIERS:
            raise DecisionJobError(f"{evidence_id} has unsupported tier {tier}")
        if independence not in INDEPENDENCE:
            raise DecisionJobError(
                f"{evidence_id} has unsupported independence {independence}"
            )
        rows.append(
            {
                "id": evidence_id,
                "title": required_text(row["title"], f"{evidence_id}.title"),
                "tier": tier,
                "independence": independence,
                "source": required_text(row["source"], f"{evidence_id}.source"),
                "claim": required_text(row["claim"], f"{evidence_id}.claim"),
                "limits": required_text(row["limits"], f"{evidence_id}.limits"),
            }
        )
    rows.sort(key=lambda row: row["id"])
    if not any(evidence_is_independent(row) for row in rows):
        raise DecisionJobError(
            "accepted circulation requires at least one independent confirmed, measured, or reported evidence record"
        )
    return rows


def normalize_migration(value: Any) -> dict[str, list[str]]:
    row = exact_keys(value, {"preserve", "alter", "retire", "introduce"}, "decision.migration")
    return {
        key: string_list(row[key], f"decision.migration.{key}")
        for key in ("preserve", "alter", "retire", "introduce")
    }


def normalize_dimensions(value: Any) -> dict[str, int]:
    row = exact_keys(value, DIMENSIONS, "decision.dimensions")
    result: dict[str, int] = {}
    for key in sorted(DIMENSIONS):
        score = row[key]
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5:
            raise DecisionJobError(f"decision dimension {key} must be integer 0..5")
        result[key] = score
    return result


def normalize_gates(value: Any) -> dict[str, str]:
    row = exact_keys(value, GATES, "decision.gates")
    if any(row[key] != "pass" for key in GATES):
        raise DecisionJobError("only a decision with every hard gate passing may circulate")
    return {key: "pass" for key in sorted(GATES)}


def normalize_circulation(value: Any) -> dict[str, Any]:
    row = exact_keys(
        value,
        {"lane", "task", "surface", "producer", "consumers", "blockedOn"},
        "job.circulation",
    )
    if row["lane"] not in {"A", "B"}:
        raise DecisionJobError("job.circulation.lane must be A or B")
    return {
        "lane": row["lane"],
        "task": required_text(row["task"], "job.circulation.task"),
        "surface": required_text(row["surface"], "job.circulation.surface", maximum=1_024),
        "producer": required_text(row["producer"], "job.circulation.producer", maximum=1_024),
        "consumers": string_list(
            row["consumers"], "job.circulation.consumers", allow_empty=False
        ),
        "blockedOn": optional_text(
            row["blockedOn"], "job.circulation.blockedOn", maximum=256
        ),
    }


def source_circulation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionJobError("decision.circulation must be an object")
    return normalize_circulation(
        {
            "lane": value.get("lane"),
            "task": value.get("task"),
            "surface": value.get("surface"),
            "producer": value.get("producer"),
            "consumers": value.get("consumers"),
            "blockedOn": value.get("blockedOn", ""),
        }
    )


def source_execution(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DecisionJobError("decision.execution must be an object")
    state = value.get("state", "not_started")
    if state == "not_started":
        extra = set(value) - {"state"}
        if extra:
            raise DecisionJobError(
                f"not-started execution cannot carry evidence fields: {sorted(extra)}"
            )
        return None
    if state not in EXECUTION_STATES:
        raise DecisionJobError(f"unsupported execution state: {state!r}")
    implementation = string_list(
        value.get("implementationRefs", []), "decision.execution.implementationRefs"
    )
    verification = string_list(
        value.get("verificationRefs", []), "decision.execution.verificationRefs"
    )
    result: dict[str, Any] = {
        "state": state,
        "authority": required_text(
            value.get("authority"), "decision.execution.authority"
        ),
        "implementationRefs": implementation,
        "verificationRefs": verification,
    }
    if state in {"verified", "failed"}:
        outcome = value.get("outcome")
        if outcome not in TERMINAL_OUTCOMES:
            raise DecisionJobError(
                f"terminal execution requires outcome in {sorted(TERMINAL_OUTCOMES)}"
            )
        if not implementation or not verification:
            raise DecisionJobError(
                "terminal execution requires implementation and verification references"
            )
        result["outcome"] = outcome
        result["completedAt"] = iso_time(
            value.get("completedAt"), "decision.execution.completedAt"
        )
    else:
        if value.get("outcome") is not None or value.get("completedAt") is not None:
            raise DecisionJobError(
                "in-progress execution cannot carry a terminal outcome or completion time"
            )
    return result


def build_execution(value: dict[str, Any], job_id: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "format": EXECUTION_FORMAT,
        "jobId": job_id,
        **value,
    }
    record["executionId"] = digest("organexec1", record)
    verify_execution(record, job_id)
    return record


def verify_execution(value: Any, job_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionJobError("job.execution must be an object")
    state = value.get("state")
    base = {
        "format",
        "jobId",
        "state",
        "authority",
        "implementationRefs",
        "verificationRefs",
        "executionId",
    }
    required = base | ({"outcome", "completedAt"} if state in {"verified", "failed"} else set())
    row = exact_keys(value, required, "job.execution")
    if row["format"] != EXECUTION_FORMAT:
        raise DecisionJobError(f"job.execution must use {EXECUTION_FORMAT}")
    if row["jobId"] != job_id:
        raise DecisionJobError("execution does not bind the enclosing job identity")
    source = {
        "state": state,
        "authority": row["authority"],
        "implementationRefs": row["implementationRefs"],
        "verificationRefs": row["verificationRefs"],
    }
    if state in {"verified", "failed"}:
        source["outcome"] = row["outcome"]
        source["completedAt"] = row["completedAt"]
    normalized = source_execution(source)
    if normalized is None:
        raise DecisionJobError("job.execution cannot be not_started")
    expected = {"format": EXECUTION_FORMAT, "jobId": job_id, **normalized}
    expected["executionId"] = digest("organexec1", expected)
    if row != expected:
        raise DecisionJobError("execution record is not canonical or its identity mismatches")
    return row


def build_decision(model: dict[str, Any]) -> dict[str, Any]:
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

    source = model.get("decision")
    if not isinstance(source, dict):
        raise DecisionJobError("model.decision must be an object")
    if source.get("state") != "accepted":
        raise DecisionJobError("only an accepted decision may enter circulation")
    organ_id = required_text(source.get("organId"), "decision.organId", maximum=256)
    candidate_id = required_text(
        source.get("candidateId"), "decision.candidateId", maximum=256
    )
    decider_id = required_text(source.get("decider"), "decision.decider", maximum=256)
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
                "title": row.get("title"),
                "tier": row.get("tier"),
                "independence": row.get("independence"),
                "source": row.get("source"),
                "claim": row.get("claim"),
                "limits": row.get("limits"),
            }
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
        "decidedAt": iso_time(source.get("decidedAt"), "decision.decidedAt"),
        "mandate": {
            "ref": required_text(
                source.get("mandateRef"), "decision.mandateRef", maximum=2_048
            ),
            "basis": required_text(source.get("mandateBasis"), "decision.mandateBasis"),
            "authentication": "not performed by the compiler",
        },
        "rationale": required_text(source.get("rationale"), "decision.rationale"),
        "openQuestions": string_list(
            source.get("openQuestions", []), "decision.openQuestions"
        ),
        "gates": normalize_gates(candidate.get("gates")),
        "dimensions": normalize_dimensions(candidate.get("dimensions")),
        "migration": normalize_migration(candidate.get("changes")),
        "evidence": normalize_evidence(evidence_rows),
    }
    decision["decisionId"] = digest("orgdec1", decision)
    verify_decision(decision)
    return decision


def verify_decision(value: Any) -> dict[str, Any]:
    required = {
        "format",
        "estateId",
        "organId",
        "organName",
        "candidateId",
        "candidateName",
        "action",
        "state",
        "posture",
        "decider",
        "decidedAt",
        "mandate",
        "rationale",
        "openQuestions",
        "gates",
        "dimensions",
        "migration",
        "evidence",
        "decisionId",
    }
    row = exact_keys(value, required, "job.decision")
    if row["format"] != DECISION_FORMAT:
        raise DecisionJobError(f"job.decision must use {DECISION_FORMAT}")
    if row["state"] != "accepted" or row["posture"] != "admissible":
        raise DecisionJobError("job decision is not accepted and admissible")
    required_text(row["estateId"], "decision.estateId", maximum=256)
    required_text(row["organId"], "decision.organId", maximum=256)
    required_text(row["organName"], "decision.organName")
    required_text(row["candidateId"], "decision.candidateId", maximum=256)
    required_text(row["candidateName"], "decision.candidateName")
    required_text(row["action"], "decision.action", maximum=128)
    decider = exact_keys(row["decider"], {"id", "name"}, "decision.decider")
    required_text(decider["id"], "decision.decider.id", maximum=256)
    required_text(decider["name"], "decision.decider.name")
    iso_time(row["decidedAt"], "decision.decidedAt")
    mandate = exact_keys(
        row["mandate"], {"ref", "basis", "authentication"}, "decision.mandate"
    )
    required_text(mandate["ref"], "decision.mandate.ref", maximum=2_048)
    required_text(mandate["basis"], "decision.mandate.basis")
    if mandate["authentication"] != "not performed by the compiler":
        raise DecisionJobError("decision mandate authentication claim is unsupported")
    required_text(row["rationale"], "decision.rationale")
    string_list(row["openQuestions"], "decision.openQuestions")
    normalize_gates(row["gates"])
    normalize_dimensions(row["dimensions"])
    normalize_migration(row["migration"])
    normalize_evidence(row["evidence"])
    expected = digest("orgdec1", without_keys(row, "decisionId"))
    if row["decisionId"] != expected:
        raise DecisionJobError("decision identity mismatch")
    validate_digest(row["decisionId"], "orgdec1", "decision.decisionId")
    return row


def build_job(model: dict[str, Any]) -> dict[str, Any]:
    decision = build_decision(model)
    estate_id = decision["estateId"]
    source_decision = model["decision"]
    source = {
        "modelFormat": MODEL_FORMAT,
        "estateId": estate_id,
        "modelDigest": digest("orgmodel1", source_model_projection(model)),
    }
    bundle: dict[str, Any] = {
        "format": JOB_FORMAT,
        "source": source,
        "decision": decision,
        "circulation": source_circulation(source_decision.get("circulation")),
        "authority": json.loads(json.dumps(AUTHORITY)),
        "limits": [
            "The compiler validates structure and declared decision geometry; it does not authenticate the mandate, decider, cited evidence, implementation, or outcome.",
            "Bloodstream may preserve and report this job but cannot admit it, prioritize it, execute it, or accept its outcome.",
            "Any consumer must verify cited implementation and verification references independently when that distinction matters.",
        ],
    }
    bundle["jobId"] = digest("organjob1", bundle)
    execution_source = source_execution(source_decision.get("execution"))
    if execution_source is not None:
        bundle["execution"] = build_execution(execution_source, bundle["jobId"])
    verify_job(bundle)
    return bundle


def verify_job(value: dict[str, Any]) -> None:
    validate_depth(value)
    required = {"format", "source", "decision", "circulation", "authority", "limits", "jobId"}
    if "execution" in value:
        required.add("execution")
    bundle = exact_keys(value, required, "job bundle")
    if bundle["format"] != JOB_FORMAT:
        raise DecisionJobError(f"job bundle must use {JOB_FORMAT}")
    source = exact_keys(
        bundle["source"], {"modelFormat", "estateId", "modelDigest"}, "job.source"
    )
    if source["modelFormat"] != MODEL_FORMAT:
        raise DecisionJobError("job source model format is unsupported")
    required_text(source["estateId"], "job.source.estateId", maximum=256)
    validate_digest(source["modelDigest"], "orgmodel1", "job.source.modelDigest")
    decision = verify_decision(bundle["decision"])
    if source["estateId"] != decision["estateId"]:
        raise DecisionJobError("job source and decision estate identities differ")
    circulation = normalize_circulation(bundle["circulation"])
    if circulation != bundle["circulation"]:
        raise DecisionJobError("circulation record is not canonical")
    if bundle["authority"] != AUTHORITY:
        raise DecisionJobError("job authority membrane differs from the compiler contract")
    limits = string_list(bundle["limits"], "job.limits", allow_empty=False)
    if limits != bundle["limits"]:
        raise DecisionJobError("job limits are not canonical")
    expected_job = digest(
        "organjob1", without_keys(bundle, "jobId", "execution")
    )
    if bundle["jobId"] != expected_job:
        raise DecisionJobError("job identity mismatch")
    validate_digest(bundle["jobId"], "organjob1", "job.jobId")
    if "execution" in bundle:
        verify_execution(bundle["execution"], bundle["jobId"])


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
                        "executionId": (value.get("execution") or {}).get("executionId"),
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
                        "executionId": (value.get("execution") or {}).get("executionId"),
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
