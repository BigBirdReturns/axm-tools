#!/usr/bin/env python3
"""Validate the contained Manzanita review board and emit a deterministic receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

CHARTER_SCHEMA = "axm-tools/manzanita-review-board-charter@1"
PACKET_SCHEMA = "axm-tools/manzanita-review-packet@1"
DECISION_SCHEMA = "axm-tools/manzanita-review-decision@1"
ACTIVATION_SCHEMA = "axm-tools/manzanita-review-board-activation@1"
RECEIPT_SCHEMA = "axm-tools/manzanita-review-board-receipt@1"
BOARD_ID = "M99-CONTAINED-REVIEW-BOARD"
TASK_REFERENCE = "JDB99-027"

EXPECTED_SEATS = {
    "board_chair",
    "creative_direction",
    "product_interaction",
    "information_design",
    "typography",
    "motion",
    "source_custody",
    "field_operations",
    "accessibility",
    "performance_resilience",
    "security_privacy",
    "continuity_release",
}
EXPECTED_GATES = {
    "object_classification",
    "actors_and_authority",
    "mechanism_fidelity",
    "source_and_authorship_custody",
    "interaction_semantics",
    "visual_and_typographic_finish",
    "motion_and_temporal_continuity",
    "responsive_and_accessible_operation",
    "performance_resilience_and_failure",
    "security_privacy_rights_and_purpose",
    "continuity_export_rollback_and_succession",
    "qualification_receipts_and_public_effect",
}
GATE_STATES = {"pass", "partial", "fail", "unknown", "not_applicable"}
DECISION_STATES = {
    "admit",
    "admit_with_holds",
    "admit_governance_only",
    "hold",
    "reject",
    "supersede",
}
ADMISSION_OUTCOMES = {"admit", "admit_with_holds", "admit_governance_only"}
DISPOSITIONS = {"pass", "pass_with_findings", "hold", "reject", "not_applicable"}

ROOT = Path(__file__).resolve().parent
DEFAULT_CHARTER = ROOT / "BOARD_CHARTER.json"
DEFAULT_ACTIVATION = ROOT / "ACTIVATION_STATE.json"
DEFAULT_PACKET = ROOT / "cases" / "M99-RB-PKT-001.json"
DEFAULT_DECISION = ROOT / "cases" / "M99-RB-DEC-001.json"
DEFAULT_PACKET_SCHEMA = ROOT / "review-packet.schema.json"
DEFAULT_DECISION_SCHEMA = ROOT / "review-decision.schema.json"
DEFAULT_RECEIPT = ROOT / "out" / "BOARD_ACTIVATION_RECEIPT.json"


class ReviewError(ValueError):
    """Raised when the review board contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"Cannot read valid JSON from {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def clean_relative_path(value: str) -> str:
    require(isinstance(value, str) and value, "Repository path must be a non-empty string")
    path = PurePosixPath(value)
    require(not path.is_absolute(), f"Absolute repository path is prohibited: {value}")
    require(".." not in path.parts, f"Repository path escapes its root: {value}")
    require(value not in {".", ""}, f"Invalid repository path: {value}")
    return path.as_posix()


def resolve_repo_path(repo_root: Path, relative: str) -> Path:
    clean = clean_relative_path(relative)
    candidate = (repo_root / clean).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ReviewError(f"Repository path escapes its root: {relative}") from exc
    return candidate


def unique_ids(rows: Iterable[dict[str, Any]], key: str, label: str) -> set[str]:
    values: list[str] = []
    for row in rows:
        require(isinstance(row, dict), f"Every {label} must be an object")
        value = row.get(key)
        require(isinstance(value, str) and value, f"Every {label} needs {key}")
        values.append(value)
    require(len(values) == len(set(values)), f"Duplicate {label} {key} values")
    return set(values)


def validate_schema_documents(packet_schema: dict[str, Any], decision_schema: dict[str, Any]) -> None:
    require(
        packet_schema.get("$id", "").endswith("review-packet.schema.json"),
        "Review packet schema identity drifted",
    )
    require(
        decision_schema.get("$id", "").endswith("review-decision.schema.json"),
        "Review decision schema identity drifted",
    )
    packet_required = set(packet_schema.get("required", []))
    decision_required = set(decision_schema.get("required", []))
    require(
        {"packet_id", "object", "actors", "mechanism", "evidence", "gates", "seat_prompts"}
        <= packet_required,
        "Review packet schema lost constitutional fields",
    )
    require(
        {"decision_id", "seat_reviews", "defects", "vetoes", "gate_disposition", "outcome", "release_effect"}
        <= decision_required,
        "Review decision schema lost constitutional fields",
    )


def validate_charter(charter: dict[str, Any]) -> dict[str, Any]:
    require(charter.get("schema") == CHARTER_SCHEMA, "Unexpected board charter schema")
    require(charter.get("board_id") == BOARD_ID, "Unexpected board identity")
    require(charter.get("task_reference") == TASK_REFERENCE, "Charter must reference JDB99-027")
    require(
        isinstance(charter.get("version"), str)
        and re.fullmatch(r"\d+\.\d+\.\d+", charter["version"]),
        "Charter version must be semantic",
    )
    require(charter.get("accountable_actor") == "design_integrator", "Design integrator must remain accountable")
    require(charter.get("decision_authority") == "release_authority", "Release authority must remain the deciding seat")
    require(set(charter.get("decision_states", [])) == DECISION_STATES, "Decision state law drifted")
    require(set(charter.get("gate_states", [])) == GATE_STATES, "Gate state law drifted")
    require(set(charter.get("required_gates", [])) == EXPECTED_GATES, "Required gate set drifted")

    seats = charter.get("seats")
    require(isinstance(seats, list), "Charter seats must be a list")
    seat_ids = unique_ids(seats, "id", "seat")
    require(seat_ids == EXPECTED_SEATS, f"Seat coverage drifted: {sorted(seat_ids ^ EXPECTED_SEATS)}")
    for seat in seats:
        for field in ("discipline", "role"):
            require(isinstance(seat.get(field), str) and len(seat[field]) >= 10, f"{seat['id']} lacks {field}")
        for field in ("required_questions", "evidence_minimum", "vetoes", "non_authority"):
            value = seat.get(field)
            require(isinstance(value, list) and value, f"{seat['id']} lacks {field}")
            require(all(isinstance(item, str) and len(item) >= 8 for item in value), f"{seat['id']} has an invalid {field} entry")

    occupancy = str(charter.get("seat_occupancy_law", "")).lower()
    require("functional" in occupancy and "named" in occupancy, "Seat occupancy law must reject personality simulation")
    authority = charter.get("authority_boundary")
    require(isinstance(authority, dict), "Authority boundary is required")
    may = authority.get("board_may")
    may_not = authority.get("board_may_not")
    require(isinstance(may, list) and may, "Board authority list is empty")
    require(isinstance(may_not, list) and may_not, "Board non-authority list is empty")
    prohibited_text = " ".join(str(item).lower() for item in may_not)
    for term in ("deploy", "external", "adverse", "historical", "backlog"):
        require(term in prohibited_text, f"Board non-authority boundary lost {term!r}")
    require(bool(charter.get("qualification_boundary")), "Charter qualification boundary is required")
    return {"seat_ids": seat_ids, "version": charter["version"]}


def validate_activation(activation: dict[str, Any], charter: dict[str, Any]) -> None:
    require(activation.get("schema") == ACTIVATION_SCHEMA, "Unexpected activation schema")
    require(activation.get("task_reference") == TASK_REFERENCE, "Activation task reference drifted")
    require(activation.get("board_id") == BOARD_ID, "Activation board identity drifted")
    require(activation.get("board_version") == charter.get("version"), "Activation charter version drifted")
    require(activation.get("state") == "operational_governance_only", "Activation must remain governance-only")
    require(activation.get("closure_effect") == "none_until_successor_register_admission", "Activation cannot mutate constitutional counts")
    prohibited = " ".join(str(item).lower() for item in activation.get("prohibited_claims", []))
    for term in ("external review", "product qualification", "release", "task-count"):
        require(term in prohibited, f"Activation prohibited-claim boundary lost {term!r}")


def validate_gate_map(
    gates: Any,
    evidence_ids: set[str],
    *,
    label: str,
) -> dict[str, str]:
    require(isinstance(gates, dict), f"{label} gates must be an object")
    require(set(gates) == EXPECTED_GATES, f"{label} gate coverage drifted")
    states: dict[str, str] = {}
    for gate_id in sorted(EXPECTED_GATES):
        row = gates[gate_id]
        require(isinstance(row, dict), f"{label} gate {gate_id} must be an object")
        state = row.get("state")
        require(state in GATE_STATES, f"{label} gate {gate_id} has invalid state {state!r}")
        reason = row.get("reason")
        require(isinstance(reason, str) and len(reason) >= 15, f"{label} gate {gate_id} lacks a reason")
        refs = row.get("evidence_ids")
        require(isinstance(refs, list), f"{label} gate {gate_id} evidence_ids must be a list")
        require(len(refs) == len(set(refs)), f"{label} gate {gate_id} repeats evidence")
        require(set(refs).issubset(evidence_ids), f"{label} gate {gate_id} cites unknown evidence")
        if state == "not_applicable":
            require("not" in reason.lower() or "no " in reason.lower(), f"{label} gate {gate_id} lacks a bounded not-applicable reason")
        states[gate_id] = state
    return states


def validate_packet(
    repo_root: Path,
    charter: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    require(packet.get("schema") == PACKET_SCHEMA, "Unexpected review packet schema")
    require(packet.get("board_id") == BOARD_ID, "Packet board identity drifted")
    require(re.fullmatch(r"M99-RB-PKT-\d{3}", str(packet.get("packet_id", ""))) is not None, "Invalid packet id")
    require(packet.get("requested_decision") in DECISION_STATES, "Packet requests an unknown decision")
    require(isinstance(packet.get("object"), str) and len(packet["object"]) >= 20, "Packet object is not classified")
    require(isinstance(packet.get("mechanism"), str) and len(packet["mechanism"]) >= 40, "Packet lacks mechanism fidelity")
    require(isinstance(packet.get("actors"), list) and len(packet["actors"]) >= 2, "Packet lacks actors")
    require(len(packet["actors"]) == len(set(packet["actors"])), "Packet actor list contains duplicates")
    require(isinstance(packet.get("claim_boundary"), str) and len(packet["claim_boundary"]) >= 40, "Packet lacks a claim boundary")

    source_ref = packet.get("source_ref")
    require(isinstance(source_ref, dict), "Packet source_ref is required")
    require(source_ref.get("repository") == "BigBirdReturns/axm-tools", "Packet repository identity drifted")
    binding = source_ref.get("binding")
    ref_value = source_ref.get("ref")
    require(binding in {"exact_commit", "validation_head"}, "Packet source binding is invalid")
    require(isinstance(ref_value, str) and ref_value, "Packet source ref is empty")
    if binding == "exact_commit":
        require(re.fullmatch(r"[0-9a-f]{40}", ref_value) is not None, "Exact packet ref must be a commit SHA")

    target_paths = packet.get("target_paths")
    require(isinstance(target_paths, list) and target_paths, "Packet has no target paths")
    require(len(target_paths) == len(set(target_paths)), "Packet target paths contain duplicates")
    for relative in target_paths:
        target = resolve_repo_path(repo_root, relative)
        require(target.exists(), f"Packet target path does not exist: {relative}")

    evidence = packet.get("evidence")
    require(isinstance(evidence, list) and evidence, "Packet has no evidence")
    evidence_ids = unique_ids(evidence, "id", "evidence")
    evidence_paths: dict[str, str] = {}
    for row in evidence:
        relative = clean_relative_path(row.get("path", ""))
        path = resolve_repo_path(repo_root, relative)
        require(path.is_file(), f"Evidence file does not exist: {relative}")
        require(isinstance(row.get("claim"), str) and len(row["claim"]) >= 20, f"Evidence {row['id']} lacks a claim")
        evidence_paths[row["id"]] = relative

    gate_states = validate_gate_map(packet.get("gates"), evidence_ids, label="packet")
    prompts = packet.get("seat_prompts")
    require(isinstance(prompts, dict), "Packet seat prompts must be an object")
    require(set(prompts) == EXPECTED_SEATS, "Packet seat prompt coverage drifted")
    for seat_id, questions in prompts.items():
        require(isinstance(questions, list) and questions, f"Packet has no prompt for {seat_id}")
        require(all(isinstance(item, str) and len(item) >= 15 for item in questions), f"Packet prompt is invalid for {seat_id}")

    requested_authority = packet.get("requested_authority")
    public_effect = packet.get("public_effect")
    require(isinstance(requested_authority, str) and requested_authority, "Packet requested authority is missing")
    require(public_effect in {"none", "internal_only", "public_read_only", "external_effect"}, "Packet public effect is invalid")
    if requested_authority == "governance_activation_only":
        require(public_effect == "none", "Governance activation cannot request a public effect")
        require(packet.get("requested_decision") in {"admit_governance_only", "hold", "reject"}, "Governance activation requests excessive decision authority")

    adverse = packet.get("adverse_action_boundary")
    require(isinstance(adverse, dict), "Packet adverse-action boundary is required")
    require(isinstance(adverse.get("prohibited_uses"), list) and adverse["prohibited_uses"], "Packet prohibited-use list is empty")
    require(isinstance(adverse.get("required_human_control"), str) and len(adverse["required_human_control"]) >= 20, "Packet lacks human-control boundary")
    continuity = packet.get("continuity")
    require(isinstance(continuity, dict), "Packet continuity object is required")
    for field in ("recovery_path", "rollback_target", "successor_test"):
        require(isinstance(continuity.get(field), str) and continuity[field], f"Packet continuity lacks {field}")
    require(isinstance(packet.get("control_question"), str) and len(packet["control_question"]) >= 30, "Packet lacks a control question")

    return {
        "evidence_ids": evidence_ids,
        "evidence_paths": evidence_paths,
        "gate_states": gate_states,
        "binding": binding,
        "ref": ref_value,
    }


def validate_decision(
    charter: dict[str, Any],
    packet: dict[str, Any],
    decision: dict[str, Any],
    packet_result: dict[str, Any],
) -> dict[str, Any]:
    require(decision.get("schema") == DECISION_SCHEMA, "Unexpected review decision schema")
    require(decision.get("board_id") == BOARD_ID, "Decision board identity drifted")
    require(decision.get("board_version") == charter.get("version"), "Decision board version drifted")
    require(decision.get("packet_id") == packet.get("packet_id"), "Decision packet identity drifted")
    require(re.fullmatch(r"M99-RB-DEC-\d{3}", str(decision.get("decision_id", ""))) is not None, "Invalid decision id")
    require(decision.get("external_review_claim") is False, "Contained review cannot claim external review")

    reviewed_ref = decision.get("reviewed_ref")
    require(isinstance(reviewed_ref, dict), "Decision reviewed_ref is required")
    require(reviewed_ref.get("binding") == packet_result["binding"], "Decision source binding drifted")
    require(reviewed_ref.get("ref") == packet_result["ref"], "Decision source ref drifted")

    reviews = decision.get("seat_reviews")
    require(isinstance(reviews, list), "Decision seat reviews must be a list")
    seat_ids = unique_ids(reviews, "seat_id", "seat review")
    require(seat_ids == EXPECTED_SEATS, f"Decision seat coverage drifted: {sorted(seat_ids ^ EXPECTED_SEATS)}")

    evidence_ids = packet_result["evidence_ids"]
    for review in reviews:
        require(review.get("disposition") in DISPOSITIONS, f"Invalid disposition for {review['seat_id']}")
        findings = review.get("findings")
        require(isinstance(findings, list) and findings, f"{review['seat_id']} has no findings")
        require(all(isinstance(item, str) and len(item) >= 20 for item in findings), f"{review['seat_id']} has an invalid finding")
        refs = review.get("evidence_ids")
        require(isinstance(refs, list) and refs, f"{review['seat_id']} cites no evidence")
        require(set(refs).issubset(evidence_ids), f"{review['seat_id']} cites unknown evidence")
        require(isinstance(review.get("uncertainty"), str) and len(review["uncertainty"]) >= 15, f"{review['seat_id']} lacks uncertainty")
        require(isinstance(review.get("veto_ids"), list), f"{review['seat_id']} veto_ids must be a list")

    defects = decision.get("defects")
    vetoes = decision.get("vetoes")
    require(isinstance(defects, list), "Decision defects must be a list")
    require(isinstance(vetoes, list), "Decision vetoes must be a list")
    defect_ids = unique_ids(defects, "id", "defect") if defects else set()
    veto_ids = unique_ids(vetoes, "id", "veto") if vetoes else set()

    for defect in defects:
        require(defect.get("severity") in {"critical", "high", "medium", "low"}, f"Invalid defect severity: {defect['id']}")
        require(defect.get("disposition") in {"open", "accepted_hold", "resolved", "rejected"}, f"Invalid defect disposition: {defect['id']}")
        require(isinstance(defect.get("owner"), str) and defect["owner"], f"Defect {defect['id']} lacks an owner")
        require(isinstance(defect.get("acceptance"), str) and len(defect["acceptance"]) >= 20, f"Defect {defect['id']} lacks acceptance")
        require(set(defect.get("evidence_ids", [])).issubset(evidence_ids), f"Defect {defect['id']} cites unknown evidence")

    for veto in vetoes:
        require(veto.get("seat_id") in EXPECTED_SEATS, f"Veto {veto['id']} cites an unknown seat")
        require(veto.get("severity") in {"critical", "high"}, f"Veto {veto['id']} has invalid severity")
        require(veto.get("state") in {"open", "resolved"}, f"Veto {veto['id']} has invalid state")
        require(set(veto.get("evidence_ids", [])).issubset(evidence_ids), f"Veto {veto['id']} cites unknown evidence")
        require(isinstance(veto.get("resolution"), str) and len(veto["resolution"]) >= 15, f"Veto {veto['id']} lacks resolution text")

    for review in reviews:
        refs = set(review.get("veto_ids", []))
        require(refs.issubset(veto_ids), f"{review['seat_id']} cites an unknown veto")
        for veto_id in refs:
            veto = next(row for row in vetoes if row["id"] == veto_id)
            require(veto["seat_id"] == review["seat_id"], f"{review['seat_id']} cites another seat's veto")

    gate_states = validate_gate_map(decision.get("gate_disposition"), evidence_ids, label="decision")
    outcome = decision.get("outcome")
    require(outcome in DECISION_STATES, "Decision outcome is invalid")
    requested = packet.get("requested_decision")
    allowed = {
        "admit": {"admit", "admit_with_holds", "hold", "reject"},
        "admit_with_holds": {"admit_with_holds", "hold", "reject"},
        "admit_governance_only": {"admit_governance_only", "hold", "reject"},
        "hold": {"hold", "reject"},
        "reject": {"reject"},
        "supersede": {"supersede", "hold", "reject"},
    }
    require(outcome in allowed[requested], "Decision exceeds the packet's requested disposition")

    open_vetoes = [row for row in vetoes if row.get("state") == "open"]
    open_severe_defects = [
        row
        for row in defects
        if row.get("severity") in {"critical", "high"} and row.get("disposition") != "resolved"
    ]
    if outcome in ADMISSION_OUTCOMES:
        require(not open_vetoes, "Admission is blocked by an open critical or high veto")
        require(not open_severe_defects, "Admission is blocked by an unresolved critical or high defect")
        unknown = sorted(gate for gate, state in gate_states.items() if state == "unknown")
        failed = sorted(gate for gate, state in gate_states.items() if state == "fail")
        require(not unknown, f"Admission is blocked by unknown applicable gates: {unknown}")
        require(not failed, f"Admission is blocked by failed gates: {failed}")
        held_or_rejected = [row["seat_id"] for row in reviews if row.get("disposition") in {"hold", "reject"}]
        require(not held_or_rejected, f"Admission is blocked by seat disposition: {held_or_rejected}")

    release_effect = decision.get("release_effect")
    require(release_effect in {"none", "internal_candidate_only", "public_read_only_candidate", "release_authority_required"}, "Decision release effect is invalid")
    if packet.get("requested_authority") == "governance_activation_only":
        require(outcome in {"admit_governance_only", "hold", "reject"}, "Governance activation received product authority")
        require(release_effect == "none", "Governance activation cannot have a release effect")

    holds = decision.get("holds")
    require(isinstance(holds, list), "Decision holds must be a list")
    if outcome in {"admit_with_holds", "admit_governance_only"}:
        require(holds, "A bounded admission must retain its holds")

    authority = decision.get("authority_receipt")
    require(isinstance(authority, dict), "Decision authority receipt is required")
    require(authority.get("deciding_seat") == "release_authority", "Decision authority receipt names the wrong seat")
    require(isinstance(authority.get("decision_scope"), str) and len(authority["decision_scope"]) >= 20, "Decision scope is missing")
    prohibited = authority.get("prohibited_effects")
    require(isinstance(prohibited, list) and prohibited, "Decision prohibited effects are missing")
    require(isinstance(decision.get("qualification_boundary"), str) and len(decision["qualification_boundary"]) >= 40, "Decision qualification boundary is missing")
    require(isinstance(decision.get("control_question"), str) and len(decision["control_question"]) >= 30, "Decision control question is missing")

    return {
        "seat_ids": seat_ids,
        "defect_ids": defect_ids,
        "veto_ids": veto_ids,
        "open_vetoes": [row["id"] for row in open_vetoes],
        "open_severe_defects": [row["id"] for row in open_severe_defects],
        "gate_states": gate_states,
        "outcome": outcome,
        "release_effect": release_effect,
    }


def git_head(repo_root: Path, override: str | None = None) -> str:
    if override:
        return override
    for env_name in ("REVIEW_HEAD_SHA", "GITHUB_HEAD_SHA"):
        value = os.environ.get(env_name, "")
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else "WORKTREE"


def iter_target_files(repo_root: Path, target_paths: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for relative in target_paths:
        target = resolve_repo_path(repo_root, relative)
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            relative_parts = path.relative_to(repo_root).parts
            if "out" in relative_parts or "__pycache__" in relative_parts or path.suffix == ".pyc":
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield resolved


def file_row(repo_root: Path, path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def build_receipt(
    repo_root: Path,
    charter_path: Path,
    activation_path: Path,
    packet_path: Path,
    decision_path: Path,
    packet_schema_path: Path,
    decision_schema_path: Path,
    charter: dict[str, Any],
    activation: dict[str, Any],
    packet: dict[str, Any],
    decision: dict[str, Any],
    packet_result: dict[str, Any],
    decision_result: dict[str, Any],
    *,
    head_override: str | None = None,
) -> dict[str, Any]:
    manifest = [file_row(repo_root, path) for path in iter_target_files(repo_root, packet["target_paths"])]
    manifest.sort(key=lambda row: row["path"])
    evidence_manifest = [
        {
            "id": evidence_id,
            **file_row(repo_root, resolve_repo_path(repo_root, relative)),
        }
        for evidence_id, relative in sorted(packet_result["evidence_paths"].items())
    ]
    source_files = {
        "charter": file_row(repo_root, charter_path),
        "activation": file_row(repo_root, activation_path),
        "packet": file_row(repo_root, packet_path),
        "decision": file_row(repo_root, decision_path),
        "packet_schema": file_row(repo_root, packet_schema_path),
        "decision_schema": file_row(repo_root, decision_schema_path),
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS",
        "board_status": "ACTIVE",
        "board_id": BOARD_ID,
        "board_version": charter["version"],
        "task_reference": TASK_REFERENCE,
        "operating_state": activation["state"],
        "constitutional_count_effect": "none",
        "reviewed_head": git_head(repo_root, head_override),
        "packet_id": packet["packet_id"],
        "decision_id": decision["decision_id"],
        "outcome": decision_result["outcome"],
        "release_effect": decision_result["release_effect"],
        "seat_count": len(decision_result["seat_ids"]),
        "seat_ids": sorted(decision_result["seat_ids"]),
        "gate_states": dict(sorted(decision_result["gate_states"].items())),
        "open_vetoes": decision_result["open_vetoes"],
        "open_critical_or_high_defects": decision_result["open_severe_defects"],
        "holds": decision.get("holds", []),
        "source_files": source_files,
        "evidence_manifest": evidence_manifest,
        "target_manifest": manifest,
        "target_manifest_sha256": sha256_bytes(canonical_bytes(manifest)),
        "admitted_claim": decision["admitted_claim"],
        "qualification_boundary": decision["qualification_boundary"],
        "control_question": decision["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    return receipt


def validate_board(
    repo_root: Path,
    *,
    charter_path: Path = DEFAULT_CHARTER,
    activation_path: Path = DEFAULT_ACTIVATION,
    packet_path: Path = DEFAULT_PACKET,
    decision_path: Path = DEFAULT_DECISION,
    packet_schema_path: Path = DEFAULT_PACKET_SCHEMA,
    decision_schema_path: Path = DEFAULT_DECISION_SCHEMA,
    head_override: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repo_root = repo_root.resolve()
    charter = load_json(charter_path)
    activation = load_json(activation_path)
    packet = load_json(packet_path)
    decision = load_json(decision_path)
    packet_schema = load_json(packet_schema_path)
    decision_schema = load_json(decision_schema_path)

    validate_schema_documents(packet_schema, decision_schema)
    charter_result = validate_charter(charter)
    validate_activation(activation, charter)
    packet_result = validate_packet(repo_root, charter, packet)
    decision_result = validate_decision(charter, packet, decision, packet_result)
    receipt = build_receipt(
        repo_root,
        charter_path.resolve(),
        activation_path.resolve(),
        packet_path.resolve(),
        decision_path.resolve(),
        packet_schema_path.resolve(),
        decision_schema_path.resolve(),
        charter,
        activation,
        packet,
        decision,
        packet_result,
        decision_result,
        head_override=head_override,
    )
    return receipt, {
        "charter": charter_result,
        "packet": packet_result,
        "decision": decision_result,
    }


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--activation", type=Path, default=DEFAULT_ACTIVATION)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--packet-schema", type=Path, default=DEFAULT_PACKET_SCHEMA)
    parser.add_argument("--decision-schema", type=Path, default=DEFAULT_DECISION_SCHEMA)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--head")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt, _ = validate_board(
        args.repo_root,
        charter_path=args.charter,
        activation_path=args.activation,
        packet_path=args.packet,
        decision_path=args.decision,
        packet_schema_path=args.packet_schema,
        decision_schema_path=args.decision_schema,
        head_override=args.head,
    )
    write_receipt(args.receipt, receipt)
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "board_status": receipt["board_status"],
                "task_reference": receipt["task_reference"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "reviewed_head": receipt["reviewed_head"],
                "packet_id": receipt["packet_id"],
                "decision_id": receipt["decision_id"],
                "outcome": receipt["outcome"],
                "release_effect": receipt["release_effect"],
                "seats": receipt["seat_count"],
                "open_vetoes": len(receipt["open_vetoes"]),
                "open_critical_or_high_defects": len(receipt["open_critical_or_high_defects"]),
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ReviewError as exc:
        raise SystemExit(str(exc)) from exc
