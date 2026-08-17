#!/usr/bin/env python3
"""Build a deterministic source-bound Manzanita whole-experience candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CONTRACT_SCHEMA = "axm-tools/manzanita-whole-experience-contract@1"
PUBLIC_DATA_SCHEMA = "axm-tools/manzanita-public-demo-data@1"
PROJECTION_SCHEMA = "axm-tools/manzanita-public-projection-receipt@1"
APERTURE_SCHEMA = "axm-tools/manzanita-seven-aperture-bundle@1"
SCENE_SCHEMA = "axm-tools/manzanita-street-glide-scene-decision@1"
REGISTRATION_SCHEMA = "axm-tools/manzanita-natural-border-registration@1"
OVERLAY_SCHEMA = "axm-tools/manzanita-eight-overlay-bundle@1"
ROLE_SCHEMA = "axm-tools/manzanita-five-role-bundle@1"
FAB_SCHEMA = "axm-tools/manzanita-fab-handoff@1"
CONSTITUTION_SCHEMA = "axm-tools/manzanita-design-constitution@1"
DATA_SCHEMA = "axm-tools/manzanita-whole-experience-data@1"
BUILD_SCHEMA = "axm-tools/manzanita-whole-experience-build@1"

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
EXPECTED_ROLES = (
    "resident",
    "nursery_grower",
    "crew_steward",
    "planner_program",
    "successor",
)
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


class ExperienceError(ValueError):
    """Raised when whole-experience admission fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperienceError(message)


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


def admitted_effect(row: dict[str, Any]) -> str | None:
    value = row.get("public_effect")
    if value is None:
        value = row.get("release_effect")
    return value if isinstance(value, str) else None


def ensure_text(row: dict[str, Any], fields: Iterable[str], label: str) -> None:
    for field in fields:
        value = row.get(field)
        require(
            isinstance(value, str) and len(value.strip()) >= 3,
            f"{label} lacks substantive {field}",
        )


def source_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "label": row.get("label") or str(row.get("id", "")).replace("_", " ").title(),
        "state": row.get("state"),
        "source_time": row.get("source_time"),
        "retrieved_at": row.get("retrieved_at"),
        "payload_sha256": row.get("payload_sha256"),
        "attribution": row.get("attribution"),
        "rights": row.get("rights"),
        "storage_policy": row.get("storage_policy"),
        "claim_scope": row.get("claim_scope"),
        "error": row.get("error"),
    }


def aperture_summary(row: dict[str, Any]) -> dict[str, Any]:
    geometry = row.get("geometry")
    require(isinstance(geometry, dict), f"Aperture {row.get('id')} lacks geometry")
    evidence_uncertainty = [
        str(item.get("uncertainty")).strip()
        for item in row.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("uncertainty"), str) and item.get("uncertainty", "").strip()
    ]
    uncertainty = row.get("uncertainty")
    if not isinstance(uncertainty, str) or not uncertainty.strip():
        if evidence_uncertainty:
            uncertainty = " ".join(dict.fromkeys(evidence_uncertainty))
        elif row.get("missing_source_ids"):
            uncertainty = "Registered source evidence is unavailable for: " + ", ".join(str(value) for value in row.get("missing_source_ids", [])) + "."
        else:
            uncertainty = "No additional aperture-level uncertainty statement is retained beyond the evidence rows and claim boundary."
    summary = {
        "id": row.get("id"),
        "order": row.get("order"),
        "state": row.get("state"),
        "geometry": geometry,
        "object_class": row.get("object_class"),
        "primary_actor": row.get("primary_actor"),
        "reading": row.get("reading"),
        "uncertainty": uncertainty,
        "safe_action": row.get("safe_action"),
        "authority": row.get("authority"),
        "acceptance": row.get("acceptance"),
        "handoff": row.get("handoff"),
        "prohibited_consequence": row.get("prohibited_consequence"),
        "evidence_state_counts": row.get("evidence_state_counts", {}),
        "payload_sha256": row.get("payload_sha256"),
    }
    ensure_text(
        summary,
        (
            "id",
            "object_class",
            "primary_actor",
            "reading",
            "uncertainty",
            "safe_action",
            "authority",
            "acceptance",
            "handoff",
            "prohibited_consequence",
        ),
        f"aperture {summary['id']}",
    )
    require(isinstance(summary["state"], str) and summary["state"], f"aperture {summary['id']} lacks state")
    return summary


def overlay_summary(row: dict[str, Any]) -> dict[str, Any]:
    geometry = row.get("geometry")
    require(isinstance(geometry, dict), f"Overlay {row.get('id')} lacks geometry")
    registration = row.get("base_registration")
    require(isinstance(registration, dict), f"Overlay {row.get('id')} lacks base registration")
    legend = row.get("legend")
    require(isinstance(legend, list) and legend, f"Overlay {row.get('id')} lacks legend")
    source_evidence = [
        source_summary(source)
        for source in row.get("source_evidence", [])
        if isinstance(source, dict)
    ]
    summary = {
        "id": row.get("id"),
        "order": row.get("order"),
        "state": row.get("state"),
        "object_class": row.get("object_class"),
        "primary_actor": row.get("primary_actor"),
        "geometry": geometry,
        "base_registration": registration,
        "legend": legend,
        "source_evidence": source_evidence,
        "missing_source_ids": list(row.get("missing_source_ids", [])),
        "degraded_source_count": row.get("degraded_source_count", 0),
        "reading": row.get("reading"),
        "uncertainty": row.get("uncertainty"),
        "safe_action": row.get("safe_action"),
        "authority": row.get("authority"),
        "acceptance": row.get("acceptance"),
        "handoff": row.get("handoff"),
        "conflicts_with": list(row.get("conflicts_with", [])),
        "conflict_behavior": row.get("conflict_behavior"),
        "prohibited_consequence": row.get("prohibited_consequence"),
        "payload_sha256": row.get("payload_sha256"),
    }
    ensure_text(
        summary,
        (
            "id",
            "state",
            "object_class",
            "primary_actor",
            "reading",
            "uncertainty",
            "safe_action",
            "authority",
            "acceptance",
            "handoff",
            "conflict_behavior",
            "prohibited_consequence",
        ),
        f"overlay {summary['id']}",
    )
    return summary


def role_summary(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence")
    export = row.get("export")
    require(isinstance(evidence, dict), f"Role {row.get('id')} lacks evidence")
    require(isinstance(export, dict), f"Role {row.get('id')} lacks export contract")
    summary = {
        "id": row.get("id"),
        "order": row.get("order"),
        "label": row.get("label"),
        "state": row.get("state"),
        "object_class": row.get("object_class"),
        "primary_actor": row.get("primary_actor"),
        "operating_purpose": row.get("operating_purpose"),
        "evidence": {
            "aperture_ids": list(evidence.get("aperture_ids", [])),
            "overlay_ids": list(evidence.get("overlay_ids", [])),
            "evidence_count": evidence.get("evidence_count"),
            "degraded_evidence_count": evidence.get("degraded_evidence_count"),
            "state_counts": dict(evidence.get("state_counts", {})),
            "source_state_counts": dict(evidence.get("source_state_counts", {})),
            "missing_source_ids": list(evidence.get("missing_source_ids", [])),
            "unavailable_source_ids": list(evidence.get("unavailable_source_ids", [])),
            "map_only_overlay_ids": list(evidence.get("map_only_overlay_ids", [])),
            "payload_sha256": evidence.get("payload_sha256"),
        },
        "controls": list(row.get("controls", [])),
        "reading": row.get("reading"),
        "safe_actions": list(row.get("safe_actions", [])),
        "authority": row.get("authority"),
        "acceptance": row.get("acceptance"),
        "export": {
            "format": export.get("format"),
            "contract": export.get("contract"),
            "external_effect": export.get("external_effect"),
            "release_state": export.get("release_state"),
            "claim_boundary": export.get("claim_boundary"),
            "payload_sha256": export.get("payload_sha256"),
        },
        "handoff_to": list(row.get("handoff_to", [])),
        "handoff": row.get("handoff"),
        "failure_state": row.get("failure_state"),
        "prohibited_consequence": row.get("prohibited_consequence"),
        "payload_sha256": row.get("payload_sha256"),
    }
    ensure_text(
        summary,
        (
            "id",
            "label",
            "state",
            "object_class",
            "primary_actor",
            "operating_purpose",
            "reading",
            "authority",
            "acceptance",
            "handoff",
            "failure_state",
            "prohibited_consequence",
        ),
        f"role {summary['id']}",
    )
    require(len(summary["controls"]) >= 2, f"Role {summary['id']} lacks controls")
    require(len(summary["safe_actions"]) >= 2, f"Role {summary['id']} lacks safe actions")
    return summary


def build_experience_data(
    contract: dict[str, Any],
    public_data: dict[str, Any],
    projection: dict[str, Any],
    public_build: dict[str, Any],
    aperture_bundle: dict[str, Any],
    aperture_build: dict[str, Any],
    scene: dict[str, Any],
    registration: dict[str, Any],
    overlay_bundle: dict[str, Any],
    overlay_build: dict[str, Any],
    role_bundle: dict[str, Any],
    role_build: dict[str, Any],
    fab_handoff: dict[str, Any],
    constitution: dict[str, Any],
    base_image_sha256: str,
) -> dict[str, Any]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected experience contract schema")
    require(public_data.get("schema") == PUBLIC_DATA_SCHEMA, "Unexpected public data schema")
    require(projection.get("schema") == PROJECTION_SCHEMA, "Unexpected public projection schema")
    require(aperture_bundle.get("schema") == APERTURE_SCHEMA, "Unexpected aperture bundle schema")
    require(scene.get("schema") == SCENE_SCHEMA, "Unexpected Street Glide scene schema")
    require(registration.get("schema") == REGISTRATION_SCHEMA, "Unexpected registration schema")
    require(overlay_bundle.get("schema") == OVERLAY_SCHEMA, "Unexpected overlay bundle schema")
    require(role_bundle.get("schema") == ROLE_SCHEMA, "Unexpected role bundle schema")
    require(fab_handoff.get("schema") == FAB_SCHEMA, "Unexpected FAB handoff schema")
    require(constitution.get("schema") == CONSTITUTION_SCHEMA, "Unexpected design constitution schema")

    for label, row in (
        ("public build", public_build),
        ("aperture build", aperture_build),
        ("overlay build", overlay_build),
        ("role build", role_build),
    ):
        require(row.get("result") == "PASS", f"Consumed {label} did not pass")

    for label, row in (
        ("experience contract", contract.get("object", {})),
        ("public build", public_build),
        ("aperture bundle", aperture_bundle),
        ("aperture build", aperture_build),
        ("scene", scene),
        ("registration", registration),
        ("overlay bundle", overlay_bundle),
        ("overlay build", overlay_build),
        ("role bundle", role_bundle),
        ("role build", role_build),
        ("FAB handoff", fab_handoff),
    ):
        require(admitted_effect(row) == "none", f"Consumed {label} carries a public effect")
        require(
            row.get("constitutional_count_effect") == "none",
            f"Consumed {label} carries a constitutional count effect",
        )

    for label, value in (
        ("public data", public_data),
        ("aperture bundle", aperture_bundle),
        ("overlay bundle", overlay_bundle),
        ("role bundle", role_bundle),
        ("FAB handoff", fab_handoff),
    ):
        prohibited = recursive_keys(value) & PROHIBITED_KEYS
        require(not prohibited, f"{label} contains prohibited keys: {sorted(prohibited)}")

    place = public_data.get("place")
    require(isinstance(place, dict) and place.get("public_safe") is True, "Experience requires a public-safe place")
    place_id = str(place.get("id"))
    source_run_id = str(public_data.get("source_run_id"))
    require(place_id and source_run_id, "Place or source-run identity is missing")
    require(projection.get("place_id") == place_id, "Projection place identity drifted")

    for label, value in (
        ("aperture", aperture_bundle),
        ("overlay", overlay_bundle),
        ("role", role_bundle),
    ):
        require(value.get("place", {}).get("id") == place_id, f"{label} place identity drifted")
        require(value.get("source_run_id") == source_run_id, f"{label} source-run identity drifted")
    require(scene.get("place_id") == place_id, "Scene place identity drifted")
    require(scene.get("source_run_id") == source_run_id, "Scene source-run identity drifted")
    require(fab_handoff.get("place_id") == place_id, "FAB place identity drifted")
    require(fab_handoff.get("source_run_id") == source_run_id, "FAB source-run identity drifted")
    require(fab_handoff.get("role_bundle_sha256") == role_bundle.get("payload_sha256"), "FAB role bundle identity drifted")

    require(aperture_bundle.get("aperture_count") == 7, "Experience requires seven apertures")
    require(overlay_bundle.get("overlay_count") == 8, "Experience requires eight overlays")
    require(role_bundle.get("role_count") == 5, "Experience requires five roles")
    require(tuple(aperture_bundle.get("aperture_order", [])) == EXPECTED_APERTURES, "Aperture order drifted")
    require(tuple(overlay_bundle.get("overlay_order", [])) == EXPECTED_OVERLAYS, "Overlay order drifted")
    require(tuple(role_bundle.get("role_order", [])) == EXPECTED_ROLES, "Role order drifted")
    require(tuple(contract.get("aperture_order", [])) == EXPECTED_APERTURES, "Contract aperture order drifted")
    require(tuple(contract.get("overlay_order", [])) == EXPECTED_OVERLAYS, "Contract overlay order drifted")
    require(tuple(contract.get("role_order", [])) == EXPECTED_ROLES, "Contract role order drifted")

    require(overlay_bundle.get("base_image_sha256") == base_image_sha256, "Overlay base-image identity drifted")
    require(registration.get("image", {}).get("sha256") == base_image_sha256, "Registration image identity drifted")
    require(scene.get("selected_mode") in {"scene", "map_only"}, "Street Glide mode is invalid")

    apertures = [aperture_summary(row) for row in aperture_bundle.get("apertures", [])]
    overlays = [overlay_summary(row) for row in overlay_bundle.get("overlays", [])]
    roles = [role_summary(row) for row in role_bundle.get("roles", [])]
    require(tuple(row["id"] for row in apertures) == EXPECTED_APERTURES, "Aperture records drifted")
    require(tuple(row["id"] for row in overlays) == EXPECTED_OVERLAYS, "Overlay records drifted")
    require(tuple(row["id"] for row in roles) == EXPECTED_ROLES, "Role records drifted")

    sources = [
        source_summary(row)
        for row in public_data.get("sources", [])
        if isinstance(row, dict)
    ]
    require(sources, "Experience requires source rows")
    source_state_counts = dict(sorted(Counter(str(row.get("state", "unknown")) for row in sources).items()))

    defaults = {
        "aperture": str(public_data.get("default_view") or "household"),
        "overlay": "care",
        "role": str(public_data.get("default_actor") or "resident"),
        "theme": "auto",
    }
    if defaults["aperture"] not in EXPECTED_APERTURES:
        defaults["aperture"] = "household"
    if defaults["role"] not in EXPECTED_ROLES:
        defaults["role"] = "resident"

    scene_summary = {
        "selected_mode": scene.get("selected_mode"),
        "selected_provider": scene.get("selected_provider"),
        "selected_scene": scene.get("selected_scene"),
        "provider_attempts": scene.get("provider_attempts"),
        "map_only_receipts": scene.get("map_only_receipts"),
        "safe_action": scene.get("safe_action"),
        "authority": scene.get("authority"),
        "claim_boundary": scene.get("claim_boundary"),
        "payload_sha256": scene.get("payload_sha256"),
    }
    registration_summary = {
        "admission_state": registration.get("admission_state"),
        "image": registration.get("image"),
        "original_points": registration.get("original_points", []),
        "proposed_points": registration.get("proposed_points", []),
        "point_count": registration.get("point_count"),
        "snapped_count": registration.get("snapped_point_count", registration.get("snapped_count")),
        "mean_displacement_pixels": registration.get("mean_displacement_pixels"),
        "mean_gradient_strength": registration.get("mean_gradient_strength"),
        "confidence_class": registration.get("confidence_class"),
        "claim_boundary": registration.get("claim_boundary"),
        "payload_sha256": registration.get("payload_sha256"),
    }

    fab = {
        "handoff_id": fab_handoff.get("handoff_id"),
        "classification": fab_handoff.get("classification"),
        "source_role": fab_handoff.get("source_role"),
        "affected_actor_role": fab_handoff.get("affected_actor_role"),
        "target_system": fab_handoff.get("target_system"),
        "target_object": fab_handoff.get("target_object"),
        "evidence": fab_handoff.get("evidence"),
        "proposal": fab_handoff.get("proposal"),
        "effect_firewall": fab_handoff.get("effect_firewall"),
        "release_state": fab_handoff.get("release_state"),
        "claim_boundary": fab_handoff.get("claim_boundary"),
        "control_question": fab_handoff.get("control_question"),
        "payload_sha256": fab_handoff.get("payload_sha256"),
    }

    data: dict[str, Any] = {
        "schema": DATA_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "experience_id": f"{place_id}-{source_run_id}-whole-experience",
        "place": place,
        "source_run_id": source_run_id,
        "source_manifest_sha256": public_data.get("source_manifest_sha256"),
        "source_reference_time": public_data.get("source_reference_time"),
        "generated_at": public_data.get("source_reference_time") or public_data.get("generated_at"),
        "design_constitution": {
            "id": constitution.get("constitution_id"),
            "version": constitution.get("version"),
            "identity": constitution.get("identity", {}).get("name"),
        },
        "donor_digests": {
            "public_projection": projection.get("payload_sha256"),
            "apertures": aperture_bundle.get("payload_sha256"),
            "scene": scene.get("payload_sha256"),
            "registration": registration.get("payload_sha256"),
            "overlays": overlay_bundle.get("payload_sha256"),
            "roles": role_bundle.get("payload_sha256"),
            "fab_handoff": fab_handoff.get("payload_sha256"),
            "base_image": base_image_sha256,
        },
        "section_order": list(contract["section_order"]),
        "defaults": defaults,
        "themes": list(contract["theme_order"]),
        "viewports": list(contract["viewports"]),
        "source_summary": {
            "state_counts": source_state_counts,
            "source_count": len(sources),
            "sources": sources,
            "failures": public_data.get("failures", []),
            "claim_boundary": public_data.get("claim_boundary"),
        },
        "scene": scene_summary,
        "registration": registration_summary,
        "aperture_order": list(EXPECTED_APERTURES),
        "apertures": apertures,
        "overlay_order": list(EXPECTED_OVERLAYS),
        "overlays": overlays,
        "role_order": list(EXPECTED_ROLES),
        "roles": roles,
        "fab_handoff": fab,
        "failure_states": list(contract["failure_states"]),
        "help": {
            "object": contract["object"],
            "controls": contract["controls"],
            "release_holds": contract["release_holds"],
            "adverse_action_boundary": contract["adverse_action_boundary"],
            "export_law": contract["export_law"],
        },
        "export_law": contract["export_law"],
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    prohibited = recursive_keys(data) & PROHIBITED_KEYS
    require(not prohibited, f"Experience data contains prohibited keys: {sorted(prohibited)}")
    data["payload_sha256"] = sha256_bytes(canonical_bytes(data))
    return data


def relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def build(
    *,
    repo_root: Path,
    contract_path: Path,
    public_demo_root: Path,
    aperture_root: Path,
    street_glide_root: Path,
    overlay_root: Path,
    role_root: Path,
    constitution_path: Path,
    template_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = contract_path.resolve()
    public_demo_root = public_demo_root.resolve()
    aperture_root = aperture_root.resolve()
    street_glide_root = street_glide_root.resolve()
    overlay_root = overlay_root.resolve()
    role_root = role_root.resolve()
    constitution_path = constitution_path.resolve()
    template_root = template_root.resolve()
    output_root = output_root.resolve()
    site_root = output_root / "site"
    assets_root = site_root / "assets"
    output_root.mkdir(parents=True, exist_ok=True)
    assets_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "contract": contract_path,
        "public_data": public_demo_root / "PUBLIC_DATA.json",
        "public_projection": public_demo_root / "PUBLIC_PROJECTION_RECEIPT.json",
        "public_build": public_demo_root / "BUILD_RECEIPT.json",
        "base_image": public_demo_root / "site" / "assets" / "base-imagery.png",
        "aperture_bundle": aperture_root / "APERTURE_BUNDLE.json",
        "aperture_build": aperture_root / "BUILD_RECEIPT.json",
        "scene_decision": street_glide_root / "SCENE_DECISION.json",
        "registration_receipt": street_glide_root / "REGISTRATION_RECEIPT.json",
        "overlay_bundle": overlay_root / "OVERLAY_BUNDLE.json",
        "overlay_build": overlay_root / "BUILD_RECEIPT.json",
        "role_bundle": role_root / "ROLE_BUNDLE.json",
        "role_build": role_root / "BUILD_RECEIPT.json",
        "fab_handoff": role_root / "FAB_HANDOFF.json",
        "design_constitution": constitution_path,
        "template_index": template_root / "index.html",
        "template_style": template_root / "style.css",
        "template_app": template_root / "app.js",
    }
    for label, path in paths.items():
        require(path.is_file(), f"Missing {label}: {path}")

    contract = load_json(paths["contract"])
    public_data = load_json(paths["public_data"])
    projection = load_json(paths["public_projection"])
    public_build = load_json(paths["public_build"])
    aperture_bundle = load_json(paths["aperture_bundle"])
    aperture_build = load_json(paths["aperture_build"])
    scene = load_json(paths["scene_decision"])
    registration = load_json(paths["registration_receipt"])
    overlay_bundle = load_json(paths["overlay_bundle"])
    overlay_build = load_json(paths["overlay_build"])
    role_bundle = load_json(paths["role_bundle"])
    role_build = load_json(paths["role_build"])
    fab_handoff = load_json(paths["fab_handoff"])
    constitution = load_json(paths["design_constitution"])
    base_image_sha256 = sha256_file(paths["base_image"])

    data = build_experience_data(
        contract,
        public_data,
        projection,
        public_build,
        aperture_bundle,
        aperture_build,
        scene,
        registration,
        overlay_bundle,
        overlay_build,
        role_bundle,
        role_build,
        fab_handoff,
        constitution,
        base_image_sha256,
    )

    data_path = output_root / "EXPERIENCE_DATA.json"
    write_json(data_path, data)
    data_script = (
        "window.__MANZANITA_WHOLE_EXPERIENCE__ = "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    (site_root / "experience-data.js").write_text(data_script, encoding="utf-8")
    shutil.copyfile(paths["template_index"], site_root / "index.html")
    shutil.copyfile(paths["template_style"], site_root / "style.css")
    shutil.copyfile(paths["template_app"], site_root / "app.js")
    shutil.copyfile(paths["base_image"], assets_root / "base-imagery.png")

    site_files = sorted(path for path in site_root.rglob("*") if path.is_file())
    site_manifest = [
        {
            "path": path.relative_to(site_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in site_files
    ]
    input_receipts = {
        label: {
            "path": relative_path(repo_root, path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for label, path in paths.items()
    }
    receipt: dict[str, Any] = {
        "schema": BUILD_SCHEMA,
        "result": "PASS",
        "inputs": input_receipts,
        "experience": {
            "id": data["experience_id"],
            "payload_sha256": data["payload_sha256"],
            "aperture_count": len(data["apertures"]),
            "overlay_count": len(data["overlays"]),
            "role_count": len(data["roles"]),
            "source_count": data["source_summary"]["source_count"],
            "theme_count": len(data["themes"]),
            "viewport_count": len(data["viewports"]),
        },
        "site": {
            "file_count": len(site_manifest),
            "manifest": site_manifest,
            "manifest_sha256": sha256_bytes(canonical_bytes(site_manifest)),
            "self_contained": True,
            "network_requests_required": 0,
        },
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_root / "BUILD_RECEIPT.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path, default=root / "EXPERIENCE_CONTRACT.json")
    parser.add_argument("--public-demo-root", type=Path, required=True)
    parser.add_argument("--aperture-root", type=Path, required=True)
    parser.add_argument("--street-glide-root", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    parser.add_argument("--role-root", type=Path, required=True)
    parser.add_argument(
        "--constitution",
        type=Path,
        default=root.parent / "design-system" / "CONSTITUTION.json",
    )
    parser.add_argument("--template-root", type=Path, default=root / "template")
    parser.add_argument("--output", type=Path, default=root / "out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        repo_root=args.repo_root,
        contract_path=args.contract,
        public_demo_root=args.public_demo_root,
        aperture_root=args.aperture_root,
        street_glide_root=args.street_glide_root,
        overlay_root=args.overlay_root,
        role_root=args.role_root,
        constitution_path=args.constitution,
        template_root=args.template_root,
        output_root=args.output,
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "experience_id": receipt["experience"]["id"],
                "apertures": receipt["experience"]["aperture_count"],
                "overlays": receipt["experience"]["overlay_count"],
                "roles": receipt["experience"]["role_count"],
                "sources": receipt["experience"]["source_count"],
                "site_files": receipt["site"]["file_count"],
                "public_effect": receipt["public_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
