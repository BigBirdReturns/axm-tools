#!/usr/bin/env python3
"""Build eight registered, source-bounded Manzanita overlay instruments."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CONTRACT_SCHEMA = "axm-tools/manzanita-eight-overlay-contract@1"
AUTHORED_SCHEMA = "axm-tools/manzanita-authored-overlay-demo@1"
PUBLIC_DATA_SCHEMA = "axm-tools/manzanita-public-demo-data@1"
PROJECTION_SCHEMA = "axm-tools/manzanita-public-projection-receipt@1"
APERTURE_SCHEMA = "axm-tools/manzanita-seven-aperture-bundle@1"
SCENE_SCHEMA = "axm-tools/manzanita-street-glide-scene-decision@1"
REGISTRATION_SCHEMA = "axm-tools/manzanita-natural-border-registration@1"
CONSTITUTION_SCHEMA = "axm-tools/manzanita-design-constitution@1"
BUNDLE_SCHEMA = "axm-tools/manzanita-eight-overlay-bundle@1"
BUILD_SCHEMA = "axm-tools/manzanita-eight-overlay-build@1"

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DEFAULT_CONTRACT = ROOT / "OVERLAY_CONTRACT.json"
DEFAULT_AUTHORED = ROOT / "AUTHORED_OVERLAY_DEMO.json"
DEFAULT_PUBLIC_DEMO = REPO_ROOT / "manzanita-next" / "public-demo" / "out"
DEFAULT_APERTURES = REPO_ROOT / "manzanita-next" / "apertures" / "out"
DEFAULT_STREET_GLIDE = REPO_ROOT / "manzanita-next" / "street-glide" / "out"
DEFAULT_CONSTITUTION = REPO_ROOT / "manzanita-next" / "design-system" / "CONSTITUTION.json"
DEFAULT_OUTPUT = ROOT / "out"

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
SOURCE_STATES = {
    "ok",
    "empty",
    "stale",
    "skipped_missing_credential",
    "rate_limited",
    "unavailable",
    "terms_blocked",
    "unknown",
}
OVERLAY_STATES = {
    "available",
    "degraded",
    "held_missing_source",
    "map_only",
    "authored_demonstration",
    "unknown",
}
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


class OverlayError(ValueError):
    """Raised when an overlay would exceed evidence, geometry, or authority custody."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OverlayError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OverlayError(f"Cannot load valid JSON from {path}: {exc}") from exc
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


def ensure_text(row: dict[str, Any], fields: Iterable[str], label: str) -> None:
    for field in fields:
        value = row.get(field)
        require(isinstance(value, str) and len(value.strip()) >= 20, f"{label} lacks a substantive {field}")


def source_row(public_row: dict[str, Any]) -> dict[str, Any]:
    state = str(public_row.get("state", "unknown"))
    require(state in SOURCE_STATES, f"Unknown public source state: {state}")
    return {
        "id": public_row.get("id"),
        "evidence_class": "public_source",
        "state": state,
        "label": public_row.get("label"),
        "source_time": public_row.get("source_time"),
        "retrieved_at": public_row.get("retrieved_at"),
        "payload_sha256": public_row.get("payload_sha256"),
        "attribution": public_row.get("attribution"),
        "rights": public_row.get("rights"),
        "storage_policy": public_row.get("storage_policy"),
        "claim_scope": public_row.get("claim_scope"),
        "uncertainty": (
            public_row.get("error")
            or "The public source retains its own scope and does not establish a private, local, physical, legal, field, or adverse condition."
        ),
        "receipt_path": public_row.get("receipt_path"),
    }


def missing_source_row(source_id: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "evidence_class": "public_source",
        "state": "unknown",
        "label": source_id.replace("_", " ").title(),
        "source_time": None,
        "retrieved_at": None,
        "payload_sha256": None,
        "attribution": "Registered source absent from the consumed public dossier",
        "rights": "Unknown because the source row is absent",
        "storage_policy": "No payload retained in the overlay bundle",
        "claim_scope": "No substantive claim permitted until source custody is restored",
        "uncertainty": "The registered source row is absent from the exact public-demo build.",
        "receipt_path": None,
    }


def aperture_row(aperture: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": aperture.get("id"),
        "evidence_class": "aperture_record",
        "state": aperture.get("state"),
        "object_class": aperture.get("object_class"),
        "primary_actor": aperture.get("primary_actor"),
        "reading": aperture.get("reading"),
        "authority": aperture.get("authority"),
        "prohibited_consequence": aperture.get("prohibited_consequence"),
        "payload_sha256": aperture.get("payload_sha256"),
        "claim_scope": "Reference to the admitted aperture record within its retained source, authored, privacy, field, adverse, and release boundaries.",
    }


def street_scene_row(scene: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "street_scene_decision",
        "evidence_class": "street_scene_decision",
        "state": "map_only" if scene.get("selected_mode") == "map_only" else "ok",
        "selected_mode": scene.get("selected_mode"),
        "selected_provider": scene.get("selected_provider"),
        "selected_scene": scene.get("selected_scene"),
        "provider_attempt_count": len(scene.get("provider_attempts", [])),
        "map_only_receipts": scene.get("map_only_receipts", []),
        "safe_action": scene.get("safe_action"),
        "authority": scene.get("authority"),
        "prohibited_consequence": scene.get("prohibited_consequence"),
        "payload_sha256": scene.get("payload_sha256"),
        "claim_scope": scene.get("claim_boundary"),
    }


def registration_row(registration: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "street_registration_receipt",
        "evidence_class": "derived_image_edge_registration_proposal",
        "state": "ok" if registration.get("result") == "PASS" else "unknown",
        "admission_state": registration.get("admission_state"),
        "image_sha256": registration.get("image", {}).get("sha256"),
        "image_class": registration.get("image", {}).get("image_class"),
        "candidate_sha256": registration.get("candidate", {}).get("sha256"),
        "method": registration.get("method"),
        "point_count": registration.get("point_count"),
        "snapped_point_count": registration.get("snapped_point_count"),
        "mean_displacement_pixels": registration.get("mean_displacement_pixels"),
        "mean_gradient_strength": registration.get("mean_gradient_strength"),
        "confidence_class": registration.get("confidence_class"),
        "known": registration.get("known"),
        "unknown": registration.get("unknown"),
        "safe_action": registration.get("safe_action"),
        "authority": registration.get("authority"),
        "prohibited_consequence": registration.get("prohibited_consequence"),
        "payload_sha256": registration.get("payload_sha256"),
        "claim_scope": registration.get("claim_boundary"),
    }


def coordinate_pairs(geometry: dict[str, Any]) -> list[list[float]]:
    coordinates = geometry.get("coordinates")
    require(isinstance(coordinates, list), f"Geometry {geometry.get('id')} coordinates must be a list")
    pairs: list[list[float]] = []
    for index, pair in enumerate(coordinates):
        require(isinstance(pair, list) and len(pair) == 2, f"Geometry {geometry.get('id')} point {index} is invalid")
        require(all(isinstance(value, (int, float)) for value in pair), f"Geometry {geometry.get('id')} point {index} is not numeric")
        normalized = [float(pair[0]), float(pair[1])]
        require(all(0.0 <= value <= 1.0 for value in normalized), f"Geometry {geometry.get('id')} point {index} is outside normalized space")
        pairs.append(normalized)
    return pairs


def validate_geometry(geometry: dict[str, Any], overlay_id: str) -> dict[str, Any]:
    require(geometry.get("overlay_id") == overlay_id, f"Geometry {geometry.get('id')} is bound to the wrong overlay")
    require(geometry.get("source_class") == "authored_overlay_registration", f"Geometry {geometry.get('id')} lacks authored source class")
    geometry_type = geometry.get("geometry_type")
    require(geometry_type in {"polygon", "polyline", "multipoint", "graph"}, f"Unknown geometry type for {overlay_id}")
    pairs = coordinate_pairs(geometry)
    minimum = 4 if geometry_type == "polygon" else 2 if geometry_type in {"polyline", "graph"} else 1
    require(len(pairs) >= minimum, f"Geometry {geometry.get('id')} has too few points")
    if geometry_type == "polygon":
        require(pairs[0] == pairs[-1], f"Polygon {geometry.get('id')} is not closed")
    edges: list[list[int]] = []
    if geometry_type == "graph":
        raw_edges = geometry.get("edges")
        require(isinstance(raw_edges, list) and raw_edges, f"Graph {geometry.get('id')} lacks edges")
        for index, edge in enumerate(raw_edges):
            require(isinstance(edge, list) and len(edge) == 2, f"Graph edge {index} is invalid")
            require(all(isinstance(value, int) for value in edge), f"Graph edge {index} is not integral")
            require(all(0 <= value < len(pairs) for value in edge), f"Graph edge {index} references an unknown point")
            require(edge[0] != edge[1], f"Graph edge {index} is a self-loop")
            edges.append(list(edge))
    row = {
        "id": geometry.get("id"),
        "overlay_id": overlay_id,
        "geometry_type": geometry_type,
        "coordinate_space": "normalized_base_image",
        "coordinates": pairs,
        "edges": edges,
        "source_class": geometry.get("source_class"),
        "legend_symbol": geometry.get("legend_symbol"),
        "claim_boundary": geometry.get("claim_boundary"),
    }
    ensure_text(row, ["claim_boundary"], f"geometry {row['id']}")
    row["payload_sha256"] = sha256_bytes(canonical_bytes(row))
    return row


def overlay_state(
    contract_row: dict[str, Any],
    sources: list[dict[str, Any]],
    scene: dict[str, Any],
) -> str:
    requirement = contract_row.get("source_requirement")
    if requirement in {"authored_only", "authored_and_context"}:
        return "authored_demonstration"
    if requirement == "street_scene_or_map_only":
        if scene.get("selected_mode") == "map_only":
            return "map_only"
        return "available" if scene.get("selected_scene") else "unknown"
    primary_ids = set(contract_row.get("primary_source_ids", []))
    primary = [row for row in sources if row.get("id") in primary_ids]
    if not primary_ids:
        return "unknown"
    if not primary or all(row.get("state") != "ok" for row in primary):
        return "held_missing_source"
    all_states = {str(row.get("state")) for row in sources}
    return "available" if all_states <= {"ok"} else "degraded"


def validate_conflicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {str(row["id"]) for row in rows}
    declared = {str(row["id"]): set(row.get("conflicts_with", [])) for row in rows}
    for overlay_id, conflicts in declared.items():
        require(overlay_id not in conflicts, f"Overlay {overlay_id} conflicts with itself")
        unknown = conflicts - ids
        require(not unknown, f"Overlay {overlay_id} references unknown conflicts: {sorted(unknown)}")
        for other in conflicts:
            require(overlay_id in declared[other], f"Conflict {overlay_id}/{other} is not symmetric")
    by_id = {str(row["id"]): row for row in rows}
    matrix: list[dict[str, Any]] = []
    for first in sorted(ids):
        for second in sorted(declared[first]):
            if first >= second:
                continue
            matrix.append(
                {
                    "first": first,
                    "second": second,
                    "first_behavior": by_id[first]["conflict_behavior"],
                    "second_behavior": by_id[second]["conflict_behavior"],
                    "law": "Retain both instruments, their source states, uncertainties, actions, authorities, and non-claims. Do not average, erase, or convert them into one score.",
                }
            )
    return matrix


def distinct(rows: list[dict[str, Any]], field: str) -> None:
    values = [row.get(field) for row in rows]
    require(len(values) == len(set(values)), f"Overlays do not have distinct {field}")


def build_bundle(
    contract: dict[str, Any],
    authored: dict[str, Any],
    public_data: dict[str, Any],
    projection: dict[str, Any],
    public_build: dict[str, Any],
    aperture_bundle: dict[str, Any],
    aperture_build: dict[str, Any],
    scene: dict[str, Any],
    registration: dict[str, Any],
    constitution: dict[str, Any],
    base_image_sha256: str,
) -> dict[str, Any]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected overlay contract schema")
    require(authored.get("schema") == AUTHORED_SCHEMA, "Unexpected authored overlay schema")
    require(public_data.get("schema") == PUBLIC_DATA_SCHEMA, "Unexpected public-demo data schema")
    require(projection.get("schema") == PROJECTION_SCHEMA, "Unexpected public projection schema")
    require(aperture_bundle.get("schema") == APERTURE_SCHEMA, "Unexpected aperture bundle schema")
    require(scene.get("schema") == SCENE_SCHEMA, "Unexpected Street Glide scene schema")
    require(registration.get("schema") == REGISTRATION_SCHEMA, "Unexpected Street Glide registration schema")
    require(constitution.get("schema") == CONSTITUTION_SCHEMA, "Unexpected design constitution schema")
    require(public_build.get("result") == "PASS", "Consumed public-demo build did not pass")
    require(aperture_build.get("result") == "PASS", "Consumed aperture build did not pass")
    require(scene.get("result") == "PASS", "Consumed Street Glide scene decision did not pass")
    require(registration.get("result") == "PASS", "Consumed Street Glide registration did not pass")
    for row in (contract["object"], public_build, aperture_build, scene, registration):
        require(row.get("public_effect") == "none", "A consumed donor carries a public effect")
        require(row.get("constitutional_count_effect") == "none", "A consumed donor carries a constitutional count effect")
    require(public_data.get("place", {}).get("public_safe") is True, "Overlay composer requires a public-safe place")
    require(authored.get("public_safe") is True and authored.get("private_household") is False, "Authored overlay cartridge is not public-safe")
    require(projection.get("result") == "PASS", "Consumed public projection did not pass")
    place_id = public_data["place"]["id"]
    source_run_id = public_data["source_run_id"]
    require(projection.get("place_id") == place_id, "Public projection and public data place identity disagree")
    require(aperture_bundle.get("place", {}).get("id") == place_id, "Aperture place identity drifted")
    require(aperture_bundle.get("source_run_id") == source_run_id, "Aperture source run drifted")
    require(scene.get("place_id") == place_id, "Street Glide place identity drifted")
    require(scene.get("source_run_id") == source_run_id, "Street Glide source run drifted")
    require(registration.get("image", {}).get("sha256") == base_image_sha256, "Registration image digest does not match the exact public-demo base image")
    require(authored.get("coordinate_space") == "normalized_base_image", "Authored overlay coordinate space drifted")

    public_sources = {
        str(row.get("id")): row
        for row in public_data.get("sources", [])
        if isinstance(row, dict) and row.get("id")
    }
    apertures = {
        str(row.get("id")): row
        for row in aperture_bundle.get("apertures", [])
        if isinstance(row, dict) and row.get("id")
    }
    authored_geometries = {
        str(row.get("id")): row
        for row in authored.get("geometries", [])
        if isinstance(row, dict) and row.get("id")
    }
    require(len(authored_geometries) == len(authored.get("geometries", [])), "Authored geometry ids are missing or duplicated")

    contract_rows = contract.get("overlays", [])
    require(isinstance(contract_rows, list), "Overlay contract lacks overlay rows")
    require(tuple(row.get("id") for row in contract_rows) == EXPECTED_OVERLAYS, "Overlay identity or order drifted")
    require([row.get("order") for row in contract_rows] == list(range(1, 9)), "Overlay order must be one through eight")

    overlays: list[dict[str, Any]] = []
    geometry_digests: set[str] = set()
    for contract_row in contract_rows:
        overlay_id = str(contract_row["id"])
        ensure_text(
            contract_row,
            [
                "reading",
                "uncertainty",
                "safe_action",
                "authority",
                "acceptance",
                "handoff",
                "conflict_behavior",
                "prohibited_consequence",
            ],
            f"overlay {overlay_id}",
        )
        geometry_id = str(contract_row.get("authored_geometry_id"))
        require(geometry_id in authored_geometries, f"Missing authored geometry {geometry_id} for {overlay_id}")
        geometry = validate_geometry(authored_geometries[geometry_id], overlay_id)
        require(geometry["payload_sha256"] not in geometry_digests, f"Duplicate authored geometry for {overlay_id}")
        geometry_digests.add(geometry["payload_sha256"])

        source_evidence: list[dict[str, Any]] = []
        missing_source_ids: list[str] = []
        for source_id in contract_row.get("source_ids", []):
            public_row = public_sources.get(str(source_id))
            if public_row is None:
                source_evidence.append(missing_source_row(str(source_id)))
                missing_source_ids.append(str(source_id))
            else:
                source_evidence.append(source_row(public_row))

        aperture_evidence: list[dict[str, Any]] = []
        for aperture_id in contract_row.get("aperture_ids", []):
            require(aperture_id in apertures, f"Overlay {overlay_id} references missing aperture {aperture_id}")
            aperture_evidence.append(aperture_row(apertures[aperture_id]))

        street_evidence: list[dict[str, Any]] = []
        for street_input in contract_row.get("street_inputs", []):
            if street_input == "scene_decision":
                street_evidence.append(street_scene_row(scene))
            elif street_input == "registration_receipt":
                street_evidence.append(registration_row(registration))
            else:
                raise OverlayError(f"Overlay {overlay_id} references unknown Street Glide input {street_input}")

        legend = contract_row.get("legend")
        require(isinstance(legend, list) and legend, f"Overlay {overlay_id} lacks legend entries")
        legend_ids: set[str] = set()
        for entry in legend:
            require(isinstance(entry, dict), f"Overlay {overlay_id} has an invalid legend entry")
            require(entry.get("id") not in legend_ids, f"Overlay {overlay_id} has duplicate legend ids")
            legend_ids.add(str(entry.get("id")))
            ensure_text(entry, ["meaning", "non_claim"], f"legend {entry.get('id')}")
            require(isinstance(entry.get("symbol"), str) and entry.get("symbol"), f"Legend {entry.get('id')} lacks a symbol")

        state = overlay_state(contract_row, source_evidence, scene)
        require(state in OVERLAY_STATES, f"Overlay {overlay_id} has an invalid derived state")
        overlay: dict[str, Any] = {
            "id": overlay_id,
            "order": contract_row["order"],
            "place_id": place_id,
            "source_run_id": source_run_id,
            "object_class": contract_row["object_class"],
            "primary_actor": contract_row["primary_actor"],
            "state": state,
            "base_registration": {
                "coordinate_space": "normalized_base_image",
                "base_image_sha256": base_image_sha256,
                "scene_decision_sha256": scene.get("payload_sha256"),
                "registration_receipt_sha256": registration.get("payload_sha256"),
                "registration_admission_state": registration.get("admission_state"),
                "selected_scene_mode": scene.get("selected_mode"),
                "selected_provider": scene.get("selected_provider"),
                "claim_boundary": "Shared coordinate and image identity only. Shared registration does not create shared source, physical-feature, field, legal, or adverse authority.",
            },
            "geometry": geometry,
            "source_requirement": contract_row["source_requirement"],
            "primary_source_ids": list(contract_row.get("primary_source_ids", [])),
            "source_evidence": source_evidence,
            "aperture_evidence": aperture_evidence,
            "street_evidence": street_evidence,
            "missing_source_ids": missing_source_ids,
            "legend": legend,
            "reading": contract_row["reading"],
            "uncertainty": contract_row["uncertainty"],
            "safe_action": contract_row["safe_action"],
            "authority": contract_row["authority"],
            "acceptance": contract_row["acceptance"],
            "handoff": contract_row["handoff"],
            "conflicts_with": sorted(contract_row.get("conflicts_with", [])),
            "conflict_behavior": contract_row["conflict_behavior"],
            "prohibited_consequence": contract_row["prohibited_consequence"],
            "evidence_count": len(source_evidence) + len(aperture_evidence) + len(street_evidence) + 1,
            "degraded_source_count": sum(row.get("state") != "ok" for row in source_evidence),
        }
        overlay["payload_sha256"] = sha256_bytes(canonical_bytes(overlay))
        overlays.append(overlay)

    for field in (
        "object_class",
        "reading",
        "uncertainty",
        "safe_action",
        "authority",
        "acceptance",
        "handoff",
        "conflict_behavior",
        "prohibited_consequence",
    ):
        distinct(overlays, field)
    distinct([row["geometry"] for row in overlays], "id")
    distinct([row["geometry"] for row in overlays], "payload_sha256")
    conflicts = validate_conflicts(overlays)

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "bundle_id": f"{place_id}-{source_run_id}-eight-overlays",
        "place": public_data["place"],
        "public_demo_build_id": public_data["build_id"],
        "source_run_id": source_run_id,
        "source_manifest_sha256": public_data["source_manifest_sha256"],
        "public_projection_receipt_sha256": projection.get("payload_sha256"),
        "aperture_bundle_sha256": aperture_bundle.get("payload_sha256"),
        "scene_decision_sha256": scene.get("payload_sha256"),
        "registration_receipt_sha256": registration.get("payload_sha256"),
        "base_image_sha256": base_image_sha256,
        "design_constitution_version": constitution.get("version"),
        "authored_cartridge_id": authored["cartridge_id"],
        "coordinate_space": "normalized_base_image",
        "overlay_count": len(overlays),
        "overlay_order": list(EXPECTED_OVERLAYS),
        "overlays": overlays,
        "state_counts": dict(sorted(Counter(row["state"] for row in overlays).items())),
        "source_state_counts": dict(
            sorted(Counter(evidence["state"] for row in overlays for evidence in row["source_evidence"]).items())
        ),
        "conflict_count": len(conflicts),
        "conflict_matrix": conflicts,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "adverse_action_boundary": contract["adverse_action_boundary"],
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    prohibited = recursive_keys(bundle) & PROHIBITED_KEYS
    require(not prohibited, f"Overlay bundle contains prohibited keys: {sorted(prohibited)}")
    bundle["payload_sha256"] = sha256_bytes(canonical_bytes(bundle))
    return bundle


def build(
    repo_root: Path,
    contract_path: Path,
    authored_path: Path,
    public_demo_root: Path,
    aperture_root: Path,
    street_glide_root: Path,
    constitution_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = contract_path.resolve()
    authored_path = authored_path.resolve()
    public_demo_root = public_demo_root.resolve()
    aperture_root = aperture_root.resolve()
    street_glide_root = street_glide_root.resolve()
    constitution_path = constitution_path.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "contract": contract_path,
        "authored_demo": authored_path,
        "public_data": public_demo_root / "PUBLIC_DATA.json",
        "public_projection": public_demo_root / "PUBLIC_PROJECTION_RECEIPT.json",
        "public_build": public_demo_root / "BUILD_RECEIPT.json",
        "base_image": public_demo_root / "site" / "assets" / "base-imagery.png",
        "aperture_bundle": aperture_root / "APERTURE_BUNDLE.json",
        "aperture_build": aperture_root / "BUILD_RECEIPT.json",
        "scene_decision": street_glide_root / "SCENE_DECISION.json",
        "registration_receipt": street_glide_root / "REGISTRATION_RECEIPT.json",
        "design_constitution": constitution_path,
    }
    for label, path in paths.items():
        require(path.is_file(), f"Missing {label}: {path}")

    contract = load_json(paths["contract"])
    authored = load_json(paths["authored_demo"])
    public_data = load_json(paths["public_data"])
    projection = load_json(paths["public_projection"])
    public_build = load_json(paths["public_build"])
    aperture_bundle = load_json(paths["aperture_bundle"])
    aperture_build = load_json(paths["aperture_build"])
    scene = load_json(paths["scene_decision"])
    registration = load_json(paths["registration_receipt"])
    constitution = load_json(paths["design_constitution"])
    base_image_sha256 = sha256_file(paths["base_image"])

    bundle = build_bundle(
        contract,
        authored,
        public_data,
        projection,
        public_build,
        aperture_bundle,
        aperture_build,
        scene,
        registration,
        constitution,
        base_image_sha256,
    )
    bundle_path = output_root / "OVERLAY_BUNDLE.json"
    write_json(bundle_path, bundle)

    input_receipts = {
        label: {
            "path": path.relative_to(repo_root).as_posix(),
            "sha256": sha256_file(path),
        }
        for label, path in paths.items()
    }
    receipt: dict[str, Any] = {
        "schema": BUILD_SCHEMA,
        "result": "PASS",
        "inputs": input_receipts,
        "bundle": {
            "path": "OVERLAY_BUNDLE.json",
            "sha256": sha256_file(bundle_path),
            "payload_sha256": bundle["payload_sha256"],
            "overlay_count": bundle["overlay_count"],
            "overlay_order": bundle["overlay_order"],
            "state_counts": bundle["state_counts"],
            "source_state_counts": bundle["source_state_counts"],
            "conflict_count": bundle["conflict_count"],
        },
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_root / "BUILD_RECEIPT.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--authored", type=Path, default=DEFAULT_AUTHORED)
    parser.add_argument("--public-demo-root", type=Path, default=DEFAULT_PUBLIC_DEMO)
    parser.add_argument("--aperture-root", type=Path, default=DEFAULT_APERTURES)
    parser.add_argument("--street-glide-root", type=Path, default=DEFAULT_STREET_GLIDE)
    parser.add_argument("--constitution", type=Path, default=DEFAULT_CONSTITUTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        args.repo_root,
        args.contract,
        args.authored,
        args.public_demo_root,
        args.aperture_root,
        args.street_glide_root,
        args.constitution,
        args.output,
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "overlays": receipt["bundle"]["overlay_count"],
                "order": receipt["bundle"]["overlay_order"],
                "states": receipt["bundle"]["state_counts"],
                "source_states": receipt["bundle"]["source_state_counts"],
                "conflicts": receipt["bundle"]["conflict_count"],
                "public_effect": receipt["public_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except OverlayError as exc:
        raise SystemExit(str(exc)) from exc
