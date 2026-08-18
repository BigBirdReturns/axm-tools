#!/usr/bin/env python3
"""Local-first evidence runner for Manzanita external release campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "axm-tools/manzanita-external-campaign-contract@1"
LEDGER_SCHEMA = "axm-tools/manzanita-external-campaign-ledger@1"
WORKSPACE_SCHEMA = "axm-tools/manzanita-external-campaign-workspace@1"
EVIDENCE_SCHEMA = "axm-tools/manzanita-external-campaign-evidence@1"
OBSERVATION_SCHEMA = "axm-tools/manzanita-external-campaign-observations@1"
RECEIPT_SCHEMA = "axm-tools/manzanita-external-campaign-receipt@1"
AMENDMENT_SCHEMA = "axm-tools/manzanita-external-campaign-amendment@1"
QUALIFICATION_SCHEMA = "axm-tools/manzanita-external-campaign-runner-qualification@1"

WORKSPACE_FILE = "CAMPAIGN_WORKSPACE.json"
EVIDENCE_FILE = "EVIDENCE_MANIFEST.json"
OBSERVATION_FILE = "OBSERVATIONS.json"

PROHIBITED_PUBLIC_KEYS = {
    "street_address",
    "resident_name",
    "resident_email",
    "resident_phone",
    "household_address",
    "api_key",
    "access_token",
    "authorization",
    "password",
    "secret",
    "cookie",
    "private_key",
    "raw_evidence",
    "file_content",
    "local_path",
}


class CampaignError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CampaignError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignError(f"Cannot load {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add_payload(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result.pop("payload_sha256", None)
    result["payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def verify_payload(value: dict[str, Any], label: str) -> None:
    payload = dict(value)
    supplied = payload.pop("payload_sha256", None)
    require(
        supplied == sha256_bytes(canonical_bytes(payload)),
        f"{label} payload checksum is invalid",
    )


def recursive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key).lower())
            found.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(recursive_keys(item))
    return found


def validate_public_boundary(value: Any, label: str) -> None:
    prohibited = recursive_keys(value) & PROHIBITED_PUBLIC_KEYS
    require(not prohibited, f"{label} contains prohibited public keys: {sorted(prohibited)}")
    serialized = json.dumps(value, sort_keys=True).lower()
    for token in (
        "email_sent",
        "calendar_event_created",
        "payment_executed",
        "publication_completed",
        "institutional_acceptance_recorded",
        "external_effect_completed",
    ):
        require(token not in serialized, f"{label} implies an external effect: {token}")


def validate_timestamp(value: str, label: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{label} is required")
    candidate = value.strip()
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CampaignError(f"{label} must be an ISO-8601 timestamp") from exc
    return candidate


def require_text(value: str, label: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{label} is required")
    return value.strip()


def require_regular_file(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    require(candidate.exists() or candidate.is_symlink(), f"{label} is missing: {candidate}")
    mode = candidate.lstat().st_mode
    require(not stat.S_ISLNK(mode), f"{label} may not be a symlink: {candidate}")
    require(stat.S_ISREG(mode), f"{label} is not a regular file: {candidate}")
    return candidate.resolve()


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected campaign contract schema")
    campaigns = contract.get("campaigns")
    require(isinstance(campaigns, list) and campaigns, "Campaign contract has no campaigns")
    ids = [row.get("id") for row in campaigns]
    require(all(isinstance(value, str) and value for value in ids), "Campaign id is missing")
    require(len(ids) == len(set(ids)), "Campaign ids are duplicated")
    require(len(ids) == 10, "Campaign contract must cover exactly ten release campaigns")
    for row in campaigns:
        for field in (
            "class",
            "object",
            "required_actors",
            "venue_requirements",
            "required_observation_types",
            "required_evidence_classes",
            "pass_criteria",
            "prohibited_claims",
        ):
            require(row.get(field), f"Campaign {row['id']} lacks {field}")
        require(
            len(row["required_observation_types"])
            == len(set(row["required_observation_types"])),
            f"Campaign {row['id']} duplicates observation types",
        )
        require(
            len(row["required_evidence_classes"])
            == len(set(row["required_evidence_classes"])),
            f"Campaign {row['id']} duplicates evidence classes",
        )


def campaign_definition(contract: dict[str, Any], campaign_id: str) -> dict[str, Any]:
    validate_contract(contract)
    matches = [row for row in contract["campaigns"] if row.get("id") == campaign_id]
    require(len(matches) == 1, f"Unknown or duplicate campaign id: {campaign_id}")
    return matches[0]


def workspace_paths(workspace: Path) -> tuple[Path, Path, Path]:
    root = workspace.expanduser().resolve()
    return root / WORKSPACE_FILE, root / EVIDENCE_FILE, root / OBSERVATION_FILE


def initialize_workspace(
    contract_path: Path,
    campaign_id: str,
    workspace: Path,
    *,
    operator: str,
    venue: str,
    procedure: str,
    procedure_version: str,
    started_at: str,
    receipt_visibility: str,
) -> dict[str, Any]:
    contract_path = require_regular_file(contract_path, "Campaign contract")
    contract = load_json(contract_path)
    definition = campaign_definition(contract, campaign_id)
    require(
        receipt_visibility in contract["receipt_visibility"],
        f"Unknown receipt visibility: {receipt_visibility}",
    )
    root = workspace.expanduser().resolve()
    require(not root.exists() or not any(root.iterdir()), "Workspace is not empty")
    root.mkdir(parents=True, exist_ok=True)

    object_row = add_payload(
        {
            "schema": WORKSPACE_SCHEMA,
            "campaign_id": campaign_id,
            "campaign_class": definition["class"],
            "state": "HOLD",
            "operator": require_text(operator, "Operator"),
            "venue": require_text(venue, "Venue"),
            "procedure": require_text(procedure, "Procedure"),
            "procedure_version": require_text(procedure_version, "Procedure version"),
            "started_at": validate_timestamp(started_at, "Started-at time"),
            "receipt_visibility": receipt_visibility,
            "contract": {
                "contract_id": contract["contract_id"],
                "contract_version": contract["version"],
                "contract_file_name": contract_path.name,
                "contract_sha256": sha256_file(contract_path),
            },
            "campaign_definition": definition,
            "claim_boundary": contract["claim_boundary"],
            "control_question": contract["control_question"],
        }
    )
    evidence = add_payload(
        {
            "schema": EVIDENCE_SCHEMA,
            "campaign_id": campaign_id,
            "items": [],
        }
    )
    observations = add_payload(
        {
            "schema": OBSERVATION_SCHEMA,
            "campaign_id": campaign_id,
            "items": [],
        }
    )
    workspace_path, evidence_path, observations_path = workspace_paths(root)
    write_json(workspace_path, object_row)
    write_json(evidence_path, evidence)
    write_json(observations_path, observations)
    return object_row


def load_workspace(workspace: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    workspace_path, evidence_path, observations_path = workspace_paths(workspace)
    object_row = load_json(workspace_path)
    evidence = load_json(evidence_path)
    observations = load_json(observations_path)
    require(object_row.get("schema") == WORKSPACE_SCHEMA, "Unexpected workspace schema")
    require(evidence.get("schema") == EVIDENCE_SCHEMA, "Unexpected evidence schema")
    require(observations.get("schema") == OBSERVATION_SCHEMA, "Unexpected observation schema")
    verify_payload(object_row, "Workspace")
    verify_payload(evidence, "Evidence manifest")
    verify_payload(observations, "Observation register")
    campaign_id = object_row.get("campaign_id")
    require(evidence.get("campaign_id") == campaign_id, "Evidence campaign identity drifted")
    require(observations.get("campaign_id") == campaign_id, "Observation campaign identity drifted")
    return object_row, evidence, observations


def set_workspace_state(workspace: Path, object_row: dict[str, Any], state: str) -> None:
    updated = dict(object_row)
    updated["state"] = state
    write_json(workspace_paths(workspace)[0], add_payload(updated))


def add_evidence(
    workspace: Path,
    source_path: Path,
    *,
    evidence_id: str,
    evidence_class: str,
    observed_at: str,
    actor: str,
    rights: str,
    claim_scope: str,
    visibility: str,
    locator: str | None,
) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    object_row, manifest, _ = load_workspace(root)
    definition = object_row["campaign_definition"]
    require(
        evidence_class in definition["required_evidence_classes"],
        f"Evidence class is not admitted for this campaign: {evidence_class}",
    )
    require(visibility in {"public_safe", "private_controlled"}, "Unknown evidence visibility")
    source = require_regular_file(source_path, "Evidence file")
    evidence_id = require_text(evidence_id, "Evidence id")
    items = manifest.get("items")
    require(isinstance(items, list), "Evidence items must be a list")
    require(evidence_id not in {row.get("id") for row in items}, f"Duplicate evidence id: {evidence_id}")
    payload = source.read_bytes()
    row = {
        "id": evidence_id,
        "class": evidence_class,
        "file_name": source.name,
        "local_path": source.as_posix(),
        "locator": require_text(locator or source.name, "Evidence locator"),
        "media_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "observed_at": validate_timestamp(observed_at, "Observed-at time"),
        "actor": require_text(actor, "Evidence actor"),
        "rights": require_text(rights, "Evidence rights"),
        "claim_scope": require_text(claim_scope, "Evidence claim scope"),
        "visibility": visibility,
    }
    items.append(row)
    manifest["items"] = sorted(items, key=lambda item: item["id"])
    write_json(workspace_paths(root)[1], add_payload(manifest))
    if object_row.get("state") == "HOLD":
        set_workspace_state(root, object_row, "IN_PROGRESS")
    return {key: value for key, value in row.items() if key != "local_path"}


def record_observation(
    workspace: Path,
    *,
    observation_id: str,
    observation_type: str,
    observed_at: str,
    actor: str,
    object_name: str,
    mechanism: str,
    result: str,
    notes: str,
    evidence_ids: list[str],
) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    object_row, evidence, observations = load_workspace(root)
    definition = object_row["campaign_definition"]
    require(
        observation_type in definition["required_observation_types"],
        f"Observation type is not admitted for this campaign: {observation_type}",
    )
    require(result in {"pass", "fail", "hold", "not_observed"}, f"Invalid observation result: {result}")
    observation_id = require_text(observation_id, "Observation id")
    available_evidence = {row.get("id") for row in evidence.get("items", [])}
    require(set(evidence_ids).issubset(available_evidence), "Observation cites unknown evidence")
    items = observations.get("items")
    require(isinstance(items, list), "Observation items must be a list")
    require(observation_id not in {row.get("id") for row in items}, f"Duplicate observation id: {observation_id}")
    row = {
        "id": observation_id,
        "type": observation_type,
        "observed_at": validate_timestamp(observed_at, "Observed-at time"),
        "actor": require_text(actor, "Observation actor"),
        "object": require_text(object_name, "Observation object"),
        "mechanism": require_text(mechanism, "Observation mechanism"),
        "result": result,
        "notes": require_text(notes, "Observation notes"),
        "evidence_ids": sorted(set(evidence_ids)),
    }
    items.append(row)
    observations["items"] = sorted(items, key=lambda item: item["id"])
    write_json(workspace_paths(root)[2], add_payload(observations))
    if object_row.get("state") == "HOLD":
        set_workspace_state(root, object_row, "IN_PROGRESS")
    return row


def evidence_integrity(evidence: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing_files: list[str] = []
    hash_failures: list[str] = []
    for row in evidence.get("items", []):
        path = Path(row["local_path"])
        if not path.exists():
            missing_files.append(row["id"])
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            hash_failures.append(row["id"])
            continue
        payload = path.read_bytes()
        if len(payload) != row["bytes"] or sha256_bytes(payload) != row["sha256"]:
            hash_failures.append(row["id"])
    return sorted(missing_files), sorted(hash_failures)


def campaign_status(workspace: Path) -> dict[str, Any]:
    object_row, evidence, observations = load_workspace(workspace)
    definition = object_row["campaign_definition"]
    observed_types = {row.get("type") for row in observations.get("items", [])}
    evidence_classes = {row.get("class") for row in evidence.get("items", [])}
    missing_files, hash_failures = evidence_integrity(evidence)
    return {
        "campaign_id": object_row["campaign_id"],
        "state": object_row["state"],
        "missing_observation_types": sorted(set(definition["required_observation_types"]) - observed_types),
        "missing_evidence_classes": sorted(set(definition["required_evidence_classes"]) - evidence_classes),
        "evidence_missing_files": missing_files,
        "evidence_hash_failures": hash_failures,
        "observation_count": len(observations.get("items", [])),
        "evidence_count": len(evidence.get("items", [])),
        "nonpassing_observations": sorted(
            row["id"]
            for row in observations.get("items", [])
            if row.get("result") != "pass"
        ),
        "observations_without_evidence": sorted(
            row["id"]
            for row in observations.get("items", [])
            if not row.get("evidence_ids")
        ),
    }


def public_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key != "local_path"}
        for row in rows
    ]


def finalize_campaign(
    workspace: Path,
    output_path: Path,
    *,
    decision: str,
    completed_at: str,
    acceptance: str,
    failure_disposition: str,
    deciding_actor: str,
) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    object_row, evidence, observations = load_workspace(root)
    current = campaign_status(root)
    require(decision in {"PASSED", "FAILED", "HOLD", "ABORTED"}, f"Invalid campaign decision: {decision}")
    if decision == "PASSED":
        require(not current["missing_observation_types"], f"Campaign lacks required observations: {current['missing_observation_types']}")
        require(not current["missing_evidence_classes"], f"Campaign lacks required evidence classes: {current['missing_evidence_classes']}")
        require(not current["evidence_missing_files"], f"Campaign evidence files are missing: {current['evidence_missing_files']}")
        require(not current["evidence_hash_failures"], f"Campaign evidence hashes failed: {current['evidence_hash_failures']}")
        require(not current["nonpassing_observations"], f"Passed campaign contains non-passing observations: {current['nonpassing_observations']}")
        require(not current["observations_without_evidence"], f"Passed campaign contains observations without evidence: {current['observations_without_evidence']}")

    evidence_rows = public_evidence(evidence.get("items", []))
    receipt = add_payload(
        {
            "schema": RECEIPT_SCHEMA,
            "receipt_id": f"{object_row['campaign_id']}-RECEIPT-001",
            "campaign_id": object_row["campaign_id"],
            "campaign_class": object_row["campaign_class"],
            "decision": decision,
            "operator": object_row["operator"],
            "venue": object_row["venue"],
            "procedure": object_row["procedure"],
            "procedure_version": object_row["procedure_version"],
            "started_at": object_row["started_at"],
            "completed_at": validate_timestamp(completed_at, "Completed-at time"),
            "deciding_actor": require_text(deciding_actor, "Deciding actor"),
            "receipt_visibility": object_row["receipt_visibility"],
            "campaign_definition": object_row["campaign_definition"],
            "observations": observations.get("items", []),
            "evidence": evidence_rows,
            "evidence_manifest_sha256": sha256_bytes(canonical_bytes(evidence_rows)),
            "evidence_bytes_verified": not current["evidence_missing_files"] and not current["evidence_hash_failures"],
            "missing_observation_types": current["missing_observation_types"],
            "missing_evidence_classes": current["missing_evidence_classes"],
            "acceptance": require_text(acceptance, "Acceptance"),
            "failure_disposition": require_text(failure_disposition, "Failure disposition"),
            "public_release_authorized": False,
            "ledger_mutation_authorized": False,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "claim_boundary": object_row["claim_boundary"],
            "control_question": object_row["control_question"],
        }
    )
    validate_public_boundary(receipt, "Campaign receipt")
    output = output_path.expanduser().resolve()
    write_json(output, receipt)
    updated = dict(object_row)
    updated.update(
        {
            "state": decision,
            "completed_at": receipt["completed_at"],
            "receipt_file_name": output.name,
            "receipt_sha256": sha256_file(output),
        }
    )
    write_json(workspace_paths(root)[0], add_payload(updated))
    return receipt


def verify_receipt(receipt_path: Path, evidence_root: Path | None = None) -> dict[str, Any]:
    path = require_regular_file(receipt_path, "Campaign receipt")
    receipt = load_json(path)
    require(receipt.get("schema") == RECEIPT_SCHEMA, "Unexpected campaign receipt schema")
    verify_payload(receipt, "Campaign receipt")
    validate_public_boundary(receipt, "Campaign receipt")
    require(receipt.get("public_release_authorized") is False, "Receipt self-authorizes public release")
    require(receipt.get("ledger_mutation_authorized") is False, "Receipt self-authorizes ledger mutation")
    require(receipt.get("public_effect") == "none", "Receipt carries a public effect")
    require(receipt.get("constitutional_count_effect") == "none", "Receipt carries a count effect")
    evidence = receipt.get("evidence")
    require(isinstance(evidence, list), "Receipt evidence must be a list")
    require(receipt.get("evidence_manifest_sha256") == sha256_bytes(canonical_bytes(evidence)), "Receipt evidence manifest checksum is invalid")
    ids = [row.get("id") for row in evidence]
    require(len(ids) == len(set(ids)), "Receipt evidence ids are duplicated")

    readback: list[str] = []
    if evidence_root is not None:
        root = evidence_root.expanduser().resolve()
        require(root.is_dir() and not root.is_symlink(), "Evidence root is not a regular directory")
        file_names = [row["file_name"] for row in evidence]
        require(len(file_names) == len(set(file_names)), "Evidence readback requires unique file names")
        for row in evidence:
            candidate = require_regular_file(root / row["file_name"], f"Evidence readback {row['id']}")
            payload = candidate.read_bytes()
            require(len(payload) == row["bytes"], f"Evidence byte drift: {row['id']}")
            require(sha256_bytes(payload) == row["sha256"], f"Evidence hash drift: {row['id']}")
            readback.append(row["id"])

    if receipt.get("decision") == "PASSED":
        require(not receipt.get("missing_observation_types"), "Passed receipt lacks observations")
        require(not receipt.get("missing_evidence_classes"), "Passed receipt lacks evidence classes")
        require(receipt.get("evidence_bytes_verified") is True, "Passed receipt lacks evidence verification")
        require(all(row.get("result") == "pass" for row in receipt.get("observations", [])), "Passed receipt contains a non-passing observation")
        require(all(row.get("evidence_ids") for row in receipt.get("observations", [])), "Passed receipt contains an observation without evidence")
    return {
        "result": "PASS",
        "campaign_id": receipt["campaign_id"],
        "decision": receipt["decision"],
        "evidence_count": len(evidence),
        "evidence_readback_ids": sorted(readback),
        "payload_sha256": receipt["payload_sha256"],
        "public_release_authorized": False,
        "ledger_mutation_authorized": False,
    }


def propose_ledger_amendment(
    ledger_path: Path,
    receipt_path: Path,
    output_ledger_path: Path,
    amendment_path: Path,
) -> dict[str, Any]:
    ledger_file = require_regular_file(ledger_path, "Canonical campaign ledger")
    receipt_file = require_regular_file(receipt_path, "Campaign receipt")
    ledger = load_json(ledger_file)
    receipt = load_json(receipt_file)
    verification = verify_receipt(receipt_file)
    require(ledger.get("schema") == LEDGER_SCHEMA, "Unexpected release campaign ledger schema")
    require(receipt.get("decision") == "PASSED", "Only a passed campaign can propose a ledger pass")
    campaigns = ledger.get("campaigns")
    require(isinstance(campaigns, list), "Ledger campaigns must be a list")
    matches = [row for row in campaigns if row.get("id") == receipt.get("campaign_id")]
    require(len(matches) == 1, "Receipt campaign is absent or duplicated in the ledger")
    require(matches[0].get("state") != "passed", "Canonical ledger already records this campaign as passed")

    proposed = json.loads(json.dumps(ledger))
    target = next(row for row in proposed["campaigns"] if row["id"] == receipt["campaign_id"])
    target.update(
        {
            "state": "passed",
            "operator": receipt["operator"],
            "venue": receipt["venue"],
            "procedure": {
                "name": receipt["procedure"],
                "version": receipt["procedure_version"],
                "started_at": receipt["started_at"],
                "completed_at": receipt["completed_at"],
            },
            "evidence_receipts": [receipt["payload_sha256"]],
            "acceptance": receipt["acceptance"],
            "failure_disposition": receipt["failure_disposition"],
        }
    )
    proposed["release_state"] = "HOLD"
    proposed["public_release_authorized"] = False
    proposed["public_effect"] = "none"
    proposed["constitutional_count_effect"] = "none"
    proposed_path = output_ledger_path.expanduser().resolve()
    write_json(proposed_path, proposed)
    amendment = add_payload(
        {
            "schema": AMENDMENT_SCHEMA,
            "campaign_id": receipt["campaign_id"],
            "campaign_receipt_sha256": receipt["payload_sha256"],
            "receipt_verification": verification,
            "source_ledger": {
                "file_name": ledger_file.name,
                "sha256": sha256_file(ledger_file),
            },
            "proposed_ledger": {
                "file_name": proposed_path.name,
                "sha256": sha256_file(proposed_path),
            },
            "state": "PROPOSED",
            "release_authority_review_required": True,
            "ledger_mutation_authorized": False,
            "public_release_authorized": False,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "claim_boundary": "This amendment proves that one passed campaign receipt can produce a bounded proposed ledger update. It does not modify the canonical ledger or authorize public release.",
        }
    )
    validate_public_boundary(amendment, "Campaign amendment")
    write_json(amendment_path.expanduser().resolve(), amendment)
    return amendment


def qualify_runner(contract_path: Path, ledger_path: Path, output_path: Path) -> dict[str, Any]:
    contract_file = require_regular_file(contract_path, "Campaign contract")
    ledger_file = require_regular_file(ledger_path, "Release campaign ledger")
    contract = load_json(contract_file)
    ledger = load_json(ledger_file)
    validate_contract(contract)
    require(ledger.get("schema") == LEDGER_SCHEMA, "Unexpected release campaign ledger schema")
    contract_ids = [row["id"] for row in contract["campaigns"]]
    ledger_rows = ledger.get("campaigns")
    require(isinstance(ledger_rows, list), "Ledger campaigns must be a list")
    ledger_ids = [row.get("id") for row in ledger_rows]
    require(contract_ids == ledger_ids, f"Campaign runner and release ledger identities drifted: {sorted(set(contract_ids) ^ set(ledger_ids))}")
    require(ledger.get("release_state") == "HOLD", "Runner qualification requires release HOLD")
    require(ledger.get("public_release_authorized") is False, "Runner qualification found public release authority")
    allowed_states = {"not_performed", "scheduled", "in_progress", "blocked", "failed", "passed"}
    require(all(row.get("state") in allowed_states for row in ledger_rows), "Ledger contains an unknown campaign state")
    for row in ledger_rows:
        if row.get("state") == "passed":
            for field in ("operator", "venue", "procedure", "evidence_receipts", "acceptance", "failure_disposition"):
                require(row.get(field), f"Passed ledger campaign {row['id']} lacks {field}")
    passed = [row["id"] for row in ledger_rows if row.get("state") == "passed"]
    open_campaigns = [row["id"] for row in ledger_rows if row.get("state") != "passed"]
    source_manifest = []
    root = Path(__file__).resolve().parent
    for path in sorted(root.rglob("*")):
        if path.is_file() and "out" not in path.parts and "__pycache__" not in path.parts and path.suffix != ".pyc":
            source_manifest.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    receipt = add_payload(
        {
            "schema": QUALIFICATION_SCHEMA,
            "result": "PASS",
            "contract_id": contract["contract_id"],
            "contract_version": contract["version"],
            "campaign_count": len(contract_ids),
            "campaign_ids": contract_ids,
            "passed_campaigns": passed,
            "open_campaigns": open_campaigns,
            "passed_campaign_count": len(passed),
            "open_campaign_count": len(open_campaigns),
            "source_manifest": source_manifest,
            "source_manifest_sha256": sha256_bytes(canonical_bytes(source_manifest)),
            "release_ledger": {
                "file_name": ledger_file.name,
                "sha256": sha256_file(ledger_file),
                "release_state": ledger["release_state"],
                "campaign_states": sorted({row["state"] for row in ledger_rows}),
            },
            "campaign_performed_by_qualification": False,
            "physical_standing": False,
            "ledger_mutation_authorized": False,
            "public_release_authorized": False,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "claim_boundary": contract["claim_boundary"],
            "control_question": contract["control_question"],
        }
    )
    validate_public_boundary(receipt, "Runner qualification")
    write_json(output_path.expanduser().resolve(), receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize one held campaign workspace")
    init.add_argument("--contract", type=Path, default=Path("manzanita-next/external-campaigns/CAMPAIGN_CONTRACT.json"))
    init.add_argument("--campaign-id", required=True)
    init.add_argument("--workspace", type=Path, required=True)
    init.add_argument("--operator", required=True)
    init.add_argument("--venue", required=True)
    init.add_argument("--procedure", required=True)
    init.add_argument("--procedure-version", required=True)
    init.add_argument("--started-at", required=True)
    init.add_argument("--receipt-visibility", choices=("public_safe", "private_controlled"), default="public_safe")

    evidence = sub.add_parser("add-evidence", help="Hash and register one operator-controlled evidence file")
    evidence.add_argument("--workspace", type=Path, required=True)
    evidence.add_argument("--file", type=Path, required=True)
    evidence.add_argument("--evidence-id", required=True)
    evidence.add_argument("--evidence-class", required=True)
    evidence.add_argument("--observed-at", required=True)
    evidence.add_argument("--actor", required=True)
    evidence.add_argument("--rights", required=True)
    evidence.add_argument("--claim-scope", required=True)
    evidence.add_argument("--visibility", choices=("public_safe", "private_controlled"), default="public_safe")
    evidence.add_argument("--locator")

    observe = sub.add_parser("observe", help="Record one contract-admitted campaign observation")
    observe.add_argument("--workspace", type=Path, required=True)
    observe.add_argument("--observation-id", required=True)
    observe.add_argument("--observation-type", required=True)
    observe.add_argument("--observed-at", required=True)
    observe.add_argument("--actor", required=True)
    observe.add_argument("--object", required=True)
    observe.add_argument("--mechanism", required=True)
    observe.add_argument("--result", choices=("pass", "fail", "hold", "not_observed"), required=True)
    observe.add_argument("--notes", required=True)
    observe.add_argument("--evidence-id", action="append", default=[])

    status_cmd = sub.add_parser("status", help="Report exact missing campaign requirements")
    status_cmd.add_argument("--workspace", type=Path, required=True)

    finalize = sub.add_parser("finalize", help="Finalize a campaign receipt")
    finalize.add_argument("--workspace", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)
    finalize.add_argument("--decision", choices=("PASSED", "FAILED", "HOLD", "ABORTED"), required=True)
    finalize.add_argument("--completed-at", required=True)
    finalize.add_argument("--acceptance", required=True)
    finalize.add_argument("--failure-disposition", required=True)
    finalize.add_argument("--deciding-actor", required=True)

    verify = sub.add_parser("verify", help="Verify a public campaign receipt and optional evidence readback")
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--evidence-root", type=Path)

    propose = sub.add_parser("propose-ledger", help="Create a bounded proposed one-row ledger amendment")
    propose.add_argument("--ledger", type=Path, required=True)
    propose.add_argument("--receipt", type=Path, required=True)
    propose.add_argument("--output-ledger", type=Path, required=True)
    propose.add_argument("--amendment", type=Path, required=True)

    qualify = sub.add_parser("qualify", help="Qualify the runner without performing a campaign")
    qualify.add_argument("--contract", type=Path, default=Path("manzanita-next/external-campaigns/CAMPAIGN_CONTRACT.json"))
    qualify.add_argument("--ledger", type=Path, default=Path("manzanita-next/release-control/EXTERNAL_CAMPAIGN_LEDGER.json"))
    qualify.add_argument("--output", type=Path, default=Path("manzanita-next/external-campaigns/out/RUNNER_QUALIFICATION.json"))
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "init":
        value = initialize_workspace(
            args.contract,
            args.campaign_id,
            args.workspace,
            operator=args.operator,
            venue=args.venue,
            procedure=args.procedure,
            procedure_version=args.procedure_version,
            started_at=args.started_at,
            receipt_visibility=args.receipt_visibility,
        )
        output = {"result": "PASS", "campaign_id": value["campaign_id"], "state": value["state"], "workspace": str(args.workspace.expanduser().resolve())}
    elif args.command == "add-evidence":
        value = add_evidence(
            args.workspace,
            args.file,
            evidence_id=args.evidence_id,
            evidence_class=args.evidence_class,
            observed_at=args.observed_at,
            actor=args.actor,
            rights=args.rights,
            claim_scope=args.claim_scope,
            visibility=args.visibility,
            locator=args.locator,
        )
        output = {"result": "PASS", "evidence": value}
    elif args.command == "observe":
        value = record_observation(
            args.workspace,
            observation_id=args.observation_id,
            observation_type=args.observation_type,
            observed_at=args.observed_at,
            actor=args.actor,
            object_name=args.object,
            mechanism=args.mechanism,
            result=args.result,
            notes=args.notes,
            evidence_ids=args.evidence_id,
        )
        output = {"result": "PASS", "observation": value}
    elif args.command == "status":
        output = campaign_status(args.workspace)
    elif args.command == "finalize":
        value = finalize_campaign(
            args.workspace,
            args.output,
            decision=args.decision,
            completed_at=args.completed_at,
            acceptance=args.acceptance,
            failure_disposition=args.failure_disposition,
            deciding_actor=args.deciding_actor,
        )
        output = {"result": "PASS", "campaign_id": value["campaign_id"], "decision": value["decision"], "payload_sha256": value["payload_sha256"]}
    elif args.command == "verify":
        output = verify_receipt(args.receipt, args.evidence_root)
    elif args.command == "propose-ledger":
        value = propose_ledger_amendment(args.ledger, args.receipt, args.output_ledger, args.amendment)
        output = {"result": "PASS", "campaign_id": value["campaign_id"], "state": value["state"], "payload_sha256": value["payload_sha256"]}
    elif args.command == "qualify":
        value = qualify_runner(args.contract, args.ledger, args.output)
        output = {
            "result": value["result"],
            "campaign_count": value["campaign_count"],
            "passed_campaign_count": value["passed_campaign_count"],
            "open_campaign_count": value["open_campaign_count"],
            "release_state": value["release_ledger"]["release_state"],
            "campaign_performed_by_qualification": value["campaign_performed_by_qualification"],
            "public_release_authorized": value["public_release_authorized"],
            "receipt_sha256": value["payload_sha256"],
        }
    else:
        raise CampaignError(f"Unknown command: {args.command}")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except CampaignError as exc:
        raise SystemExit(str(exc)) from exc
