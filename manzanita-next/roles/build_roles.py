#!/usr/bin/env python3
"""Build five deterministic functional role projections over one Manzanita place."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CONTRACT_SCHEMA = "axm-tools/manzanita-five-role-contract@1"
PUBLIC_DATA_SCHEMA = "axm-tools/manzanita-public-demo-data@1"
APERTURE_SCHEMA = "axm-tools/manzanita-seven-aperture-bundle@1"
OVERLAY_SCHEMA = "axm-tools/manzanita-eight-overlay-bundle@1"
CONSTITUTION_SCHEMA = "axm-tools/manzanita-design-constitution@1"
BUNDLE_SCHEMA = "axm-tools/manzanita-five-role-bundle@1"
FAB_HANDOFF_SCHEMA = "axm-tools/manzanita-fab-handoff@1"
BUILD_SCHEMA = "axm-tools/manzanita-five-role-build@1"

EXPECTED_ROLES = (
    "resident",
    "nursery_grower",
    "crew_steward",
    "planner_program",
    "successor",
)
EXPECTED_APERTURES = (
    "plant",
    "household",
    "property",
    "street",
    "neighborhood",
    "region",
    "stewardship",
)
EXPECTED_OVERLAYS = (
    "care",
    "shade",
    "water",
    "heat",
    "air",
    "fire",
    "access",
    "assistance",
)
NOMINAL_APERTURE_STATES = {"ok", "authored"}
NOMINAL_OVERLAY_STATES = {"available", "authored_demonstration"}
PROHIBITED_KEYS = {
    "address",
    "street_address",
    "precise_coordinates",
    "resident_name",
    "resident_email",
    "resident_phone",
    "credential",
    "credentials",
    "api_key",
    "access_token",
    "secret",
    "password",
    "account_id",
    "insurance_score",
    "enforcement_score",
    "eligibility_score",
    "property_score",
}


class RoleError(ValueError):
    """Raised when role projection admission fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RoleError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(recursive_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(recursive_keys(child))
    return keys


def ensure_text(
    row: dict[str, Any],
    fields: Iterable[str],
    label: str,
    *,
    minimum: int = 3,
) -> None:
    for field in fields:
        value = row.get(field)
        require(
            isinstance(value, str) and len(value.strip()) >= minimum,
            f"{label} lacks substantive {field}",
        )


def ensure_string_list(
    row: dict[str, Any],
    field: str,
    label: str,
    *,
    minimum: int = 1,
) -> list[str]:
    value = row.get(field)
    require(isinstance(value, list), f"{label} {field} must be a list")
    require(len(value) >= minimum, f"{label} lacks {field}")
    normalized = [str(item).strip() for item in value]
    require(all(len(item) >= 3 for item in normalized), f"{label} has an invalid {field} entry")
    require(len(normalized) == len(set(normalized)), f"{label} has duplicate {field} entries")
    return normalized


def admitted_effect(row: dict[str, Any]) -> str | None:
    value = row.get("public_effect")
    if value is None:
        value = row.get("release_effect")
    return value if isinstance(value, str) else None


def aperture_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "state": row.get("state"),
        "object_class": row.get("object_class"),
        "primary_actor": row.get("primary_actor"),
        "reading": row.get("reading"),
        "uncertainty": row.get("uncertainty"),
        "safe_action": row.get("safe_action"),
        "authority": row.get("authority"),
        "acceptance": row.get("acceptance"),
        "handoff": row.get("handoff"),
        "prohibited_consequence": row.get("prohibited_consequence"),
        "payload_sha256": row.get("payload_sha256"),
    }


def overlay_summary(row: dict[str, Any]) -> dict[str, Any]:
    registration = row.get("base_registration")
    if not isinstance(registration, dict):
        registration = {}
    source_evidence = []
    for source in row.get("source_evidence", []):
        if not isinstance(source, dict):
            continue
        source_evidence.append(
            {
                "id": source.get("id"),
                "state": source.get("state"),
                "payload_sha256": source.get("payload_sha256"),
                "claim_scope": source.get("claim_scope"),
                "uncertainty": source.get("uncertainty"),
            }
        )
    return {
        "id": row.get("id"),
        "state": row.get("state"),
        "object_class": row.get("object_class"),
        "primary_actor": row.get("primary_actor"),
        "reading": row.get("reading"),
        "uncertainty": row.get("uncertainty"),
        "safe_action": row.get("safe_action"),
        "authority": row.get("authority"),
        "acceptance": row.get("acceptance"),
        "handoff": row.get("handoff"),
        "conflicts_with": sorted(str(value) for value in row.get("conflicts_with", [])),
        "missing_source_ids": sorted(str(value) for value in row.get("missing_source_ids", [])),
        "source_evidence": source_evidence,
        "degraded_source_count": row.get("degraded_source_count"),
        "selected_scene_mode": registration.get("selected_scene_mode"),
        "base_image_sha256": registration.get("base_image_sha256"),
        "prohibited_consequence": row.get("prohibited_consequence"),
        "payload_sha256": row.get("payload_sha256"),
    }


def distinct_hashes(rows: list[dict[str, Any]], field: str) -> None:
    digests = [sha256_bytes(canonical_bytes(row.get(field))) for row in rows]
    require(len(digests) == len(set(digests)), f"Roles do not have distinct {field}")


def relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def evidence_state(
    apertures: list[dict[str, Any]],
    overlays: list[dict[str, Any]],
) -> tuple[str, dict[str, int], int]:
    states = [str(row.get("state", "unknown")) for row in apertures + overlays]
    state_counts = dict(sorted(Counter(states).items()))
    degraded = sum(
        str(row.get("state")) not in NOMINAL_APERTURE_STATES
        for row in apertures
    ) + sum(
        str(row.get("state")) not in NOMINAL_OVERLAY_STATES
        for row in overlays
    )
    if any(str(row.get("state")) == "held_missing_source" for row in overlays):
        state = "held_missing_evidence"
    elif degraded:
        state = "degraded"
    else:
        state = "available"
    return state, state_counts, degraded


def build_fab_handoff(
    *,
    bundle: dict[str, Any],
    planner_role: dict[str, Any],
    resident_role: dict[str, Any],
) -> dict[str, Any]:
    evidence = planner_role["evidence"]
    handoff: dict[str, Any] = {
        "schema": FAB_HANDOFF_SCHEMA,
        "handoff_id": f"{bundle['bundle_id']}-fab-handoff",
        "classification": "bounded_internal_assistance_offer_preparation",
        "source_role": "planner_program",
        "affected_actor_role": "resident",
        "target_system": "Essential Attention",
        "target_object": "FAB offer register and executive review",
        "place_id": bundle["place"]["id"],
        "source_run_id": bundle["source_run_id"],
        "role_bundle_sha256": bundle["payload_sha256"],
        "evidence": {
            "aperture_ids": list(evidence["aperture_ids"]),
            "overlay_ids": list(evidence["overlay_ids"]),
            "state": planner_role["state"],
            "missing_source_ids": list(evidence["missing_source_ids"]),
            "unavailable_source_ids": list(evidence["unavailable_source_ids"]),
            "source_state_counts": dict(evidence["source_state_counts"]),
            "degraded_evidence_count": evidence["degraded_evidence_count"],
            "payload_sha256": evidence["payload_sha256"],
        },
        "proposal": {
            "question": planner_role["safe_actions"][1],
            "authority": planner_role["authority"],
            "acceptance": planner_role["acceptance"],
            "refusal_and_appeal": (
                "The affected actor may refuse, narrow, defer, correct, or appeal the proposed "
                "scope before any external effect or execution record exists."
            ),
            "resident_boundary": resident_role["authority"],
            "execution_state": "not_authorized",
            "award_state": "not_decided",
            "eligibility_state": "not_determined",
        },
        "effect_firewall": {
            "external_effect": "none",
            "contact": "not_authorized",
            "payment": "not_authorized",
            "publication": "not_authorized",
            "appointment": "not_authorized",
            "representation": "not_authorized",
            "insurance": "prohibited",
            "enforcement": "prohibited",
        },
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_state": "not_authorized",
        "claim_boundary": (
            "This is an internal, portable preparation record for later accountable review. "
            "It is not an offer, eligibility decision, award, assignment, work authorization, "
            "resident acceptance, institutional acceptance, or external communication."
        ),
        "control_question": (
            "Can Essential Attention receive the evidence, authority, refusal, appeal, and "
            "no-effect boundary without converting attention into eligibility or execution?"
        ),
    }
    handoff["payload_sha256"] = sha256_bytes(canonical_bytes(handoff))
    return handoff


def build_bundle(
    contract: dict[str, Any],
    public_data: dict[str, Any],
    public_build: dict[str, Any],
    aperture_bundle: dict[str, Any],
    aperture_build: dict[str, Any],
    overlay_bundle: dict[str, Any],
    overlay_build: dict[str, Any],
    constitution: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected role contract schema")
    require(public_data.get("schema") == PUBLIC_DATA_SCHEMA, "Unexpected public data schema")
    require(aperture_bundle.get("schema") == APERTURE_SCHEMA, "Unexpected aperture bundle schema")
    require(overlay_bundle.get("schema") == OVERLAY_SCHEMA, "Unexpected overlay bundle schema")
    require(constitution.get("schema") == CONSTITUTION_SCHEMA, "Unexpected design constitution schema")
    require(public_build.get("result") == "PASS", "Consumed public build did not pass")
    require(aperture_build.get("result") == "PASS", "Consumed aperture build did not pass")
    require(overlay_build.get("result") == "PASS", "Consumed overlay build did not pass")

    for label, value in (
        ("role contract", contract),
        ("public data", public_data),
        ("aperture bundle", aperture_bundle),
        ("overlay bundle", overlay_bundle),
    ):
        prohibited = recursive_keys(value) & PROHIBITED_KEYS
        require(not prohibited, f"{label} contains prohibited keys: {sorted(prohibited)}")

    object_row = contract.get("object")
    require(isinstance(object_row, dict), "Role contract lacks object boundary")
    for row in (object_row, public_build, aperture_build, overlay_bundle, overlay_build):
        require(admitted_effect(row) == "none", "A consumed donor carries a public effect")
        require(
            row.get("constitutional_count_effect") == "none",
            "A consumed donor carries a constitutional count effect",
        )

    place = public_data.get("place")
    require(isinstance(place, dict) and place.get("public_safe") is True, "Roles require a public-safe place")
    place_id = str(place.get("id"))
    source_run_id = str(public_data.get("source_run_id"))
    require(place_id and source_run_id, "Public place or source run identity is missing")

    require(aperture_bundle.get("place", {}).get("id") == place_id, "Aperture place identity drifted")
    require(aperture_bundle.get("source_run_id") == source_run_id, "Aperture source run drifted")
    require(overlay_bundle.get("place", {}).get("id") == place_id, "Overlay place identity drifted")
    require(overlay_bundle.get("source_run_id") == source_run_id, "Overlay source run drifted")
    require(aperture_bundle.get("aperture_count") == 7, "Role composer requires seven apertures")
    require(overlay_bundle.get("overlay_count") == 8, "Role composer requires eight overlays")
    require(tuple(aperture_bundle.get("aperture_order", [])) == EXPECTED_APERTURES, "Aperture order drifted")
    require(tuple(overlay_bundle.get("overlay_order", [])) == EXPECTED_OVERLAYS, "Overlay order drifted")

    apertures = {
        str(row.get("id")): row
        for row in aperture_bundle.get("apertures", [])
        if isinstance(row, dict) and row.get("id")
    }
    overlays = {
        str(row.get("id")): row
        for row in overlay_bundle.get("overlays", [])
        if isinstance(row, dict) and row.get("id")
    }
    require(tuple(apertures) == EXPECTED_APERTURES, "Aperture record identity or order drifted")
    require(tuple(overlays) == EXPECTED_OVERLAYS, "Overlay record identity or order drifted")

    contract_roles = contract.get("roles")
    require(isinstance(contract_roles, list), "Role contract lacks roles")
    require(tuple(str(row.get("id")) for row in contract_roles) == EXPECTED_ROLES, "Role identity or order drifted")
    require([row.get("order") for row in contract_roles] == list(range(1, 6)), "Role order must be one through five")
    require(tuple(contract.get("role_order", [])) == EXPECTED_ROLES, "Contract role order drifted")

    roles: list[dict[str, Any]] = []
    handoff_edges: list[dict[str, Any]] = []
    all_role_ids = set(EXPECTED_ROLES)

    for contract_role in contract_roles:
        role_id = str(contract_role["id"])
        label = f"role {role_id}"
        ensure_text(
            contract_role,
            (
                "label",
                "object_class",
                "primary_actor",
                "operating_purpose",
                "reading",
                "authority",
                "acceptance",
                "export_contract",
                "handoff",
                "failure_state",
                "prohibited_consequence",
            ),
            label,
        )
        aperture_ids = ensure_string_list(contract_role, "aperture_ids", label)
        overlay_ids = ensure_string_list(contract_role, "overlay_ids", label)
        controls = ensure_string_list(contract_role, "controls", label, minimum=2)
        safe_actions = ensure_string_list(contract_role, "safe_actions", label, minimum=2)
        handoff_to = ensure_string_list(contract_role, "handoff_to", label)

        require(set(aperture_ids).issubset(apertures), f"{label} references unknown apertures")
        require(set(overlay_ids).issubset(overlays), f"{label} references unknown overlays")
        require(set(handoff_to).issubset(all_role_ids), f"{label} references an unknown handoff role")
        require(role_id not in handoff_to, f"{label} cannot hand off to itself")

        aperture_rows = [aperture_summary(apertures[value]) for value in aperture_ids]
        overlay_rows = [overlay_summary(overlays[value]) for value in overlay_ids]
        state, state_counts, degraded_count = evidence_state(aperture_rows, overlay_rows)
        missing_source_ids = sorted(
            {
                source_id
                for row in overlay_rows
                for source_id in row.get("missing_source_ids", [])
            }
        )
        source_state_counts = dict(
            sorted(
                Counter(
                    str(source.get("state", "unknown"))
                    for row in overlay_rows
                    for source in row.get("source_evidence", [])
                ).items()
            )
        )
        unavailable_source_ids = sorted(
            {
                str(source.get("id"))
                for row in overlay_rows
                for source in row.get("source_evidence", [])
                if source.get("id") and source.get("state") != "ok"
            }
            | set(missing_source_ids)
        )
        map_only_overlay_ids = sorted(
            row["id"]
            for row in overlay_rows
            if row.get("selected_scene_mode") == "map_only"
        )
        evidence: dict[str, Any] = {
            "place_id": place_id,
            "source_run_id": source_run_id,
            "aperture_ids": aperture_ids,
            "overlay_ids": overlay_ids,
            "apertures": aperture_rows,
            "overlays": overlay_rows,
            "evidence_count": len(aperture_rows) + len(overlay_rows),
            "degraded_evidence_count": degraded_count,
            "state_counts": state_counts,
            "source_state_counts": source_state_counts,
            "missing_source_ids": missing_source_ids,
            "unavailable_source_ids": unavailable_source_ids,
            "map_only_overlay_ids": map_only_overlay_ids,
            "claim_boundary": (
                "Role evidence is a bounded projection of admitted public-safe, authored, "
                "map-only, and degraded records. Visibility does not transfer source, private, "
                "field, legal, adverse, execution, or release authority."
            ),
        }
        evidence["payload_sha256"] = sha256_bytes(canonical_bytes(evidence))

        export: dict[str, Any] = {
            "format": "portable_json_packet",
            "contract": contract_role["export_contract"],
            "included_fields": [
                "place_id",
                "source_run_id",
                "role_id",
                "evidence",
                "controls",
                "authority",
                "acceptance",
                "handoff",
                "failure_state",
                "prohibited_consequence",
            ],
            "private_record_transfer": "prohibited",
            "external_effect": "none",
            "release_state": "not_authorized",
            "claim_boundary": (
                "The packet preserves the role projection and its holds. It does not contact, "
                "purchase, publish, appoint, represent, authorize work, decide eligibility, "
                "or create institutional acceptance."
            ),
        }
        export["payload_sha256"] = sha256_bytes(canonical_bytes(export))

        role: dict[str, Any] = {
            "id": role_id,
            "order": contract_role["order"],
            "label": contract_role["label"],
            "place_id": place_id,
            "source_run_id": source_run_id,
            "object_class": contract_role["object_class"],
            "primary_actor": contract_role["primary_actor"],
            "operating_purpose": contract_role["operating_purpose"],
            "state": state,
            "evidence": evidence,
            "controls": controls,
            "reading": contract_role["reading"],
            "safe_actions": safe_actions,
            "authority": contract_role["authority"],
            "acceptance": contract_role["acceptance"],
            "export": export,
            "handoff_to": handoff_to,
            "handoff": contract_role["handoff"],
            "failure_state": contract_role["failure_state"],
            "prohibited_consequence": contract_role["prohibited_consequence"],
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "claim_boundary": object_row["claim_boundary"],
        }
        role["payload_sha256"] = sha256_bytes(canonical_bytes(role))
        roles.append(role)

        for target in handoff_to:
            edge = {
                "from_role": role_id,
                "to_role": target,
                "place_id": place_id,
                "source_run_id": source_run_id,
                "handoff": contract_role["handoff"],
                "acceptance_required": True,
                "authority_transfer": "none",
                "external_effect": "none",
                "claim_boundary": (
                    "The edge transfers a bounded question, correction, option, scope, or "
                    "continuity discrepancy. It does not transfer private data or authority by implication."
                ),
            }
            edge["payload_sha256"] = sha256_bytes(canonical_bytes(edge))
            handoff_edges.append(edge)

    for field in (
        "object_class",
        "operating_purpose",
        "evidence",
        "controls",
        "safe_actions",
        "authority",
        "acceptance",
        "export",
        "handoff",
        "failure_state",
        "prohibited_consequence",
    ):
        distinct_hashes(roles, field)

    aperture_coverage = [
        value for value in EXPECTED_APERTURES
        if any(value in row["evidence"]["aperture_ids"] for row in roles)
    ]
    overlay_coverage = [
        value for value in EXPECTED_OVERLAYS
        if any(value in row["evidence"]["overlay_ids"] for row in roles)
    ]
    require(tuple(aperture_coverage) == EXPECTED_APERTURES, "Role projections do not cover all apertures")
    require(tuple(overlay_coverage) == EXPECTED_OVERLAYS, "Role projections do not cover all overlays")

    edge_keys = [(row["from_role"], row["to_role"]) for row in handoff_edges]
    require(len(edge_keys) == len(set(edge_keys)), "Role handoff graph contains duplicate edges")
    require(all(any(edge["from_role"] == role for edge in handoff_edges) for role in EXPECTED_ROLES), "Every role must have an outbound handoff")
    require(all(any(edge["to_role"] == role for edge in handoff_edges) for role in EXPECTED_ROLES), "Every role must have an inbound handoff")

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "bundle_id": f"{place_id}-{source_run_id}-five-roles",
        "place": place,
        "public_demo_build_id": public_data.get("build_id"),
        "source_run_id": source_run_id,
        "source_manifest_sha256": public_data.get("source_manifest_sha256"),
        "aperture_bundle_sha256": aperture_bundle.get("payload_sha256"),
        "overlay_bundle_sha256": overlay_bundle.get("payload_sha256"),
        "design_constitution_version": constitution.get("version"),
        "role_count": len(roles),
        "role_order": list(EXPECTED_ROLES),
        "roles": roles,
        "state_counts": dict(sorted(Counter(row["state"] for row in roles).items())),
        "aperture_coverage": aperture_coverage,
        "overlay_coverage": overlay_coverage,
        "handoff_edge_count": len(handoff_edges),
        "handoff_edges": handoff_edges,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "adverse_action_boundary": contract["adverse_action_boundary"],
        "claim_boundary": object_row["claim_boundary"],
        "control_question": contract["control_question"],
    }
    prohibited = recursive_keys(bundle) & PROHIBITED_KEYS
    require(not prohibited, f"Role bundle contains prohibited keys: {sorted(prohibited)}")
    bundle["payload_sha256"] = sha256_bytes(canonical_bytes(bundle))

    by_id = {row["id"]: row for row in roles}
    fab_handoff = build_fab_handoff(
        bundle=bundle,
        planner_role=by_id["planner_program"],
        resident_role=by_id["resident"],
    )
    return bundle, fab_handoff


def build(
    repo_root: Path,
    contract_path: Path,
    public_demo_root: Path,
    aperture_root: Path,
    overlay_root: Path,
    constitution_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = contract_path.resolve()
    public_demo_root = public_demo_root.resolve()
    aperture_root = aperture_root.resolve()
    overlay_root = overlay_root.resolve()
    constitution_path = constitution_path.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "contract": contract_path,
        "public_data": public_demo_root / "PUBLIC_DATA.json",
        "public_build": public_demo_root / "BUILD_RECEIPT.json",
        "aperture_bundle": aperture_root / "APERTURE_BUNDLE.json",
        "aperture_build": aperture_root / "BUILD_RECEIPT.json",
        "overlay_bundle": overlay_root / "OVERLAY_BUNDLE.json",
        "overlay_build": overlay_root / "BUILD_RECEIPT.json",
        "design_constitution": constitution_path,
    }
    for label, path in paths.items():
        require(path.is_file(), f"Missing {label}: {path}")

    contract = load_json(paths["contract"])
    public_data = load_json(paths["public_data"])
    public_build = load_json(paths["public_build"])
    aperture_bundle = load_json(paths["aperture_bundle"])
    aperture_build = load_json(paths["aperture_build"])
    overlay_bundle = load_json(paths["overlay_bundle"])
    overlay_build = load_json(paths["overlay_build"])
    constitution = load_json(paths["design_constitution"])

    bundle, fab_handoff = build_bundle(
        contract,
        public_data,
        public_build,
        aperture_bundle,
        aperture_build,
        overlay_bundle,
        overlay_build,
        constitution,
    )
    bundle_path = output_root / "ROLE_BUNDLE.json"
    fab_path = output_root / "FAB_HANDOFF.json"
    write_json(bundle_path, bundle)
    write_json(fab_path, fab_handoff)

    input_receipts = {
        label: {
            "path": relative_path(repo_root, path),
            "sha256": sha256_file(path),
        }
        for label, path in paths.items()
    }
    receipt: dict[str, Any] = {
        "schema": BUILD_SCHEMA,
        "result": "PASS",
        "inputs": input_receipts,
        "bundle": {
            "path": "ROLE_BUNDLE.json",
            "sha256": sha256_file(bundle_path),
            "payload_sha256": bundle["payload_sha256"],
            "role_count": bundle["role_count"],
            "role_order": bundle["role_order"],
            "state_counts": bundle["state_counts"],
            "aperture_coverage": bundle["aperture_coverage"],
            "overlay_coverage": bundle["overlay_coverage"],
            "handoff_edge_count": bundle["handoff_edge_count"],
        },
        "fab_handoff": {
            "path": "FAB_HANDOFF.json",
            "sha256": sha256_file(fab_path),
            "payload_sha256": fab_handoff["payload_sha256"],
            "source_role": fab_handoff["source_role"],
            "target_system": fab_handoff["target_system"],
            "release_state": fab_handoff["release_state"],
        },
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    receipt_path = output_root / "BUILD_RECEIPT.json"
    write_json(receipt_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("manzanita-next/roles/ROLE_CONTRACT.json"),
    )
    parser.add_argument(
        "--public-demo-root",
        type=Path,
        default=Path("manzanita-next/public-demo/out"),
    )
    parser.add_argument(
        "--aperture-root",
        type=Path,
        default=Path("manzanita-next/apertures/out"),
    )
    parser.add_argument(
        "--overlay-root",
        type=Path,
        default=Path("manzanita-next/overlays/out"),
    )
    parser.add_argument(
        "--constitution",
        type=Path,
        default=Path("manzanita-next/design-system/CONSTITUTION.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manzanita-next/roles/out"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        args.repo_root,
        args.contract,
        args.public_demo_root,
        args.aperture_root,
        args.overlay_root,
        args.constitution,
        args.output,
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "roles": receipt["bundle"]["role_count"],
                "order": receipt["bundle"]["role_order"],
                "states": receipt["bundle"]["state_counts"],
                "apertures": receipt["bundle"]["aperture_coverage"],
                "overlays": receipt["bundle"]["overlay_coverage"],
                "handoff_edges": receipt["bundle"]["handoff_edge_count"],
                "fab_target": receipt["fab_handoff"]["target_system"],
                "public_effect": receipt["public_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
