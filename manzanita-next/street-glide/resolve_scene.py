#!/usr/bin/env python3
"""Resolve one admissible Street Glide scene or an explicit map-only hold."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "axm-tools/manzanita-street-glide-scene-decision@1"
CONTRACT_SCHEMA = "axm-tools/manzanita-street-glide-contract@1"
PUBLIC_DATA_SCHEMA = "axm-tools/manzanita-public-demo-data@1"
DEMO_SCHEMA = "axm-tools/manzanita-authored-registration-demo@1"

ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT / "STREET_GLIDE_CONTRACT.json"
DEFAULT_PUBLIC_DATA = ROOT.parent / "public-demo" / "out" / "PUBLIC_DATA.json"
DEFAULT_SCENES = ROOT / "AUTHORED_REGISTRATION_DEMO.json"
DEFAULT_OUTPUT = ROOT / "out" / "SCENE_DECISION.json"

PROHIBITED_KEYS = {
    "address",
    "street_address",
    "resident",
    "resident_name",
    "owner_name",
    "email",
    "phone",
    "account",
    "account_id",
    "token",
    "access_token",
    "api_key",
    "secret",
    "credential",
    "password",
}


class SceneResolutionError(ValueError):
    """Raised when scene resolution would exceed source or authority custody."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SceneResolutionError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneResolutionError(f"Cannot load valid JSON from {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(recursive_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def angle_difference(first: float, second: float) -> float:
    return abs((first - second + 180.0) % 360.0 - 180.0)


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def scene_sort_key(scene: dict[str, Any], reference_time: datetime) -> tuple[float, float, float, str]:
    capture = parse_time(scene.get("capture_time"))
    age = (reference_time - capture).total_seconds() if capture else float("inf")
    return (
        float(scene.get("distance_meters", float("inf"))),
        float(scene.get("heading_difference_degrees", float("inf"))),
        age,
        str(scene.get("scene_id", "")),
    )


def public_source_rows(public_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("id")): row
        for row in public_data.get("sources", [])
        if isinstance(row, dict) and row.get("id")
    }


def candidate_source_state(
    provider_id: str,
    source_rows: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> str:
    source = source_rows.get(provider_id)
    if source:
        return str(source.get("state", "unknown"))
    candidate_states = {
        str(row.get("source_state", "unknown"))
        for row in candidates
        if row.get("provider_id") == provider_id
    }
    return candidate_states.pop() if len(candidate_states) == 1 else "unknown"


def sanitize_scene(scene: dict[str, Any], target_heading: float) -> dict[str, Any]:
    allowed = {
        "provider_id",
        "source_state",
        "scene_id",
        "capture_time",
        "latitude",
        "longitude",
        "heading_degrees",
        "distance_meters",
        "attribution",
        "rights",
        "storage_policy",
        "claim_scope",
        "render_or_payload_path",
        "generated",
        "modeled",
        "owned_capture_authority",
        "privacy_review",
    }
    row = {key: scene.get(key) for key in allowed if key in scene}
    heading = float(row.get("heading_degrees", 0.0)) if finite_number(row.get("heading_degrees")) else 0.0
    row["heading_difference_degrees"] = round(angle_difference(heading, target_heading), 3)
    return row


def reject_reason(
    scene: dict[str, Any],
    contract: dict[str, Any],
    reference_time: datetime,
    target_heading: float,
) -> tuple[str | None, str]:
    required = contract["scene_eligibility"]["required_fields"]
    missing = [field for field in required if scene.get(field) in {None, ""}]
    if missing:
        return "rejected_metadata", f"Required scene metadata is missing: {', '.join(missing)}"
    if scene.get("generated") is True:
        return "rejected_generated", "Generated imagery is prohibited as observed street evidence."
    if scene.get("modeled") is True:
        return "rejected_generated", "Modeled imagery is prohibited as observed street evidence."
    if str(scene.get("source_state")) != "ok":
        state = str(scene.get("source_state", "unknown"))
        return state if state in contract["scene_states"] else "unknown", f"Scene source state is {state}."
    if not finite_number(scene.get("latitude")) or not finite_number(scene.get("longitude")):
        return "rejected_metadata", "Scene coordinates are not finite numeric values."
    if not finite_number(scene.get("distance_meters")):
        return "rejected_metadata", "Scene distance is not a finite numeric value."
    if float(scene["distance_meters"]) > float(contract["scene_eligibility"]["maximum_distance_meters"]):
        return "rejected_distance", "Scene exceeds the maximum admitted distance."
    if not finite_number(scene.get("heading_degrees")):
        return "rejected_metadata", "Scene heading is not a finite numeric value."
    heading_diff = angle_difference(float(scene["heading_degrees"]), target_heading)
    if heading_diff > float(contract["scene_eligibility"]["heading_tolerance_degrees"]):
        return "rejected_heading", "Scene heading exceeds the admitted direction tolerance."
    capture = parse_time(scene.get("capture_time"))
    if capture is None:
        return "rejected_metadata", "Scene capture time is invalid or missing."
    age_days = max(0.0, (reference_time - capture).total_seconds() / 86400.0)
    if age_days > float(contract["scene_eligibility"]["maximum_scene_age_days"]):
        return "stale", "Scene exceeds the admitted maximum age."
    rights = str(scene.get("rights", "")).strip().lower()
    if not rights or rights in {"unknown", "none", "unreviewed"}:
        return "rejected_rights", "Scene rights are absent or unreviewed."
    if not str(scene.get("attribution", "")).strip():
        return "rejected_rights", "Scene attribution is absent."
    if not str(scene.get("storage_policy", "")).strip():
        return "rejected_rights", "Scene storage policy is absent."
    if not str(scene.get("claim_scope", "")).strip():
        return "rejected_metadata", "Scene claim scope is absent."
    if not str(scene.get("render_or_payload_path", "")).strip():
        return "rejected_metadata", "Scene has no admitted render or payload path."
    if scene.get("provider_id") == "owned_capture":
        if scene.get("owned_capture_authority") is not True or scene.get("privacy_review") is not True:
            return "rejected_rights", "Owned capture lacks retained authority or privacy review."
    return None, "Eligible scene."


def public_attempt_reason(source_state: str) -> str:
    return {
        "ok": "The public source row is healthy; scene metadata is evaluated separately.",
        "empty": "The provider responded but returned no qualifying scene or coverage.",
        "stale": "The retained provider evidence exceeds its admitted freshness window.",
        "skipped_missing_credential": "An approved provider credential is not configured; no request was attempted.",
        "rate_limited": "The provider deferred or refused the request under a rate or quota limit.",
        "unavailable": "The provider, network, transform, or required artifact was unavailable.",
        "terms_blocked": "Provider rights or redistribution terms block the requested scene use.",
        "unknown": "The retained receipt does not support a more specific provider state.",
    }.get(source_state, f"Provider source state is {source_state}.")


def resolve(
    contract: dict[str, Any],
    public_data: dict[str, Any],
    demo: dict[str, Any],
    *,
    target_heading: float = 0.0,
) -> dict[str, Any]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected Street Glide contract schema")
    require(public_data.get("schema") == PUBLIC_DATA_SCHEMA, "Unexpected public-demo data schema")
    require(demo.get("schema") == DEMO_SCHEMA, "Unexpected authored registration demo schema")
    require(public_data.get("place", {}).get("public_safe") is True, "Street Glide resolver requires a public-safe place")
    require(demo.get("public_safe") is True and demo.get("private_household") is False, "Registration demo is not public-safe")
    require(contract.get("object", {}).get("public_effect") == "none", "Contract requests a public effect")
    require(contract.get("object", {}).get("constitutional_count_effect") == "none", "Contract requests a constitutional count effect")
    require(0.0 <= target_heading < 360.0, "Target heading must be in [0, 360)")

    candidates = demo.get("scene_candidates", [])
    require(isinstance(candidates, list), "Scene candidates must be a list")
    source_rows = public_source_rows(public_data)
    provider_attempts: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    selected_provider: str | None = None
    reference_time = (
        parse_time(public_data.get("source_reference_time"))
        or parse_time(public_data.get("generated_at"))
        or datetime(2026, 8, 16, tzinfo=timezone.utc)
    )

    for provider in contract["provider_order"]:
        provider_id = str(provider["id"])
        if provider_id == "map_only":
            break
        provider_candidates = [
            sanitize_scene(row, target_heading)
            for row in candidates
            if isinstance(row, dict) and row.get("provider_id") == provider_id
        ]
        source_state = candidate_source_state(provider_id, source_rows, provider_candidates)
        attempt: dict[str, Any] = {
            "rank": provider["rank"],
            "provider_id": provider_id,
            "source_state": source_state,
            "candidate_count": len(provider_candidates),
            "result": source_state if source_state != "ok" else "empty",
            "reason": public_attempt_reason(source_state),
            "candidate_receipts": [],
        }
        if source_state != "ok":
            provider_attempts.append(attempt)
            continue
        if not provider_candidates:
            attempt["result"] = "empty"
            attempt["reason"] = "The provider source is healthy but no admissible scene metadata was supplied."
            provider_attempts.append(attempt)
            continue

        eligible: list[dict[str, Any]] = []
        for scene in provider_candidates:
            rejection, reason = reject_reason(scene, contract, reference_time, target_heading)
            receipt = {
                "scene_id": scene.get("scene_id"),
                "result": rejection or "eligible",
                "reason": reason,
                "distance_meters": scene.get("distance_meters"),
                "heading_difference_degrees": scene.get("heading_difference_degrees"),
                "capture_time": scene.get("capture_time"),
            }
            attempt["candidate_receipts"].append(receipt)
            if rejection is None:
                eligible.append(scene)

        if eligible:
            eligible.sort(key=lambda row: scene_sort_key(row, reference_time))
            selected = eligible[0]
            selected_provider = provider_id
            attempt["result"] = "selected"
            attempt["reason"] = f"Selected {selected['scene_id']} as the first eligible scene in provider order."
            attempt["selected_scene_id"] = selected["scene_id"]
            provider_attempts.append(attempt)
            break

        attempt["result"] = "rejected_metadata"
        if attempt["candidate_receipts"]:
            first_result = attempt["candidate_receipts"][0]["result"]
            if all(row["result"] == first_result for row in attempt["candidate_receipts"]):
                attempt["result"] = first_result
        attempt["reason"] = "No candidate for this provider satisfied every scene eligibility gate."
        provider_attempts.append(attempt)

    map_source_ids = ("osm_overpass", "usgs_imagery", "usgs_3dep_hillshade")
    map_only_receipts = [
        {
            "source_id": source_id,
            "state": source_rows.get(source_id, {}).get("state", "unknown"),
            "source_time": source_rows.get(source_id, {}).get("source_time"),
            "retrieved_at": source_rows.get(source_id, {}).get("retrieved_at"),
            "payload_sha256": source_rows.get(source_id, {}).get("payload_sha256"),
            "attribution": source_rows.get(source_id, {}).get("attribution"),
            "rights": source_rows.get(source_id, {}).get("rights"),
            "claim_scope": source_rows.get(source_id, {}).get("claim_scope"),
        }
        for source_id in map_source_ids
    ]

    if selected is None:
        decision: dict[str, Any] = {
            "schema": SCHEMA,
            "result": "PASS",
            "place_id": public_data["place"]["id"],
            "source_run_id": public_data["source_run_id"],
            "target_heading_degrees": target_heading,
            "selected_mode": "map_only",
            "selected_provider": "map_only",
            "selected_scene": None,
            "provider_attempts": provider_attempts,
            "map_only_receipts": map_only_receipts,
            "safe_action": demo["map_only"]["safe_action"],
            "authority": demo["map_only"]["authority"],
            "prohibited_consequence": demo["map_only"]["prohibited_consequence"],
            "claim_boundary": contract["object"]["claim_boundary"],
            "public_effect": "none",
            "constitutional_count_effect": "none",
        }
    else:
        decision = {
            "schema": SCHEMA,
            "result": "PASS",
            "place_id": public_data["place"]["id"],
            "source_run_id": public_data["source_run_id"],
            "target_heading_degrees": target_heading,
            "selected_mode": "provider_scene" if selected_provider != "owned_capture" else "owned_capture",
            "selected_provider": selected_provider,
            "selected_scene": selected,
            "provider_attempts": provider_attempts,
            "map_only_receipts": map_only_receipts,
            "safe_action": "Review the selected source, capture time, direction, distance, rights, and claim scope before applying any registration or field interpretation.",
            "authority": "The selected scene provides source imagery within its exact provider and rights scope. It does not establish a physical feature, property, access, safety, inspection, work, or completion authority.",
            "prohibited_consequence": "No parcel, insurance, enforcement, access, pruning, hazard, traffic, work, completion, or adverse decision.",
            "claim_boundary": contract["object"]["claim_boundary"],
            "public_effect": "none",
            "constitutional_count_effect": "none",
        }

    prohibited = recursive_keys(decision) & PROHIBITED_KEYS
    require(not prohibited, f"Scene decision contains prohibited keys: {sorted(prohibited)}")
    decision["payload_sha256"] = sha256_bytes(canonical_bytes(decision))
    return decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--public-data", type=Path, default=DEFAULT_PUBLIC_DATA)
    parser.add_argument("--scenes", type=Path, default=DEFAULT_SCENES)
    parser.add_argument("--target-heading", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    decision = resolve(
        load_json(args.contract),
        load_json(args.public_data),
        load_json(args.scenes),
        target_heading=args.target_heading,
    )
    write_json(args.output, decision)
    print(
        json.dumps(
            {
                "result": decision["result"],
                "selected_mode": decision["selected_mode"],
                "selected_provider": decision["selected_provider"],
                "provider_attempts": len(decision["provider_attempts"]),
                "map_only_receipts": len(decision["map_only_receipts"]),
                "public_effect": decision["public_effect"],
                "constitutional_count_effect": decision["constitutional_count_effect"],
                "decision_sha256": decision["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SceneResolutionError as exc:
        raise SystemExit(str(exc)) from exc
