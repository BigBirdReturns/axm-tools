from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PIL import Image

EXPERIENCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIENCE_ROOT))

import build_experience as builder  # noqa: E402

APERTURES = ["plant", "household", "property", "street", "neighborhood", "region", "stewardship"]
OVERLAYS = ["care", "shade", "water", "heat", "air", "fire", "access", "assistance"]
ROLES = ["resident", "nursery_grower", "crew_steward", "planner_program", "successor"]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_row(source_id: str, state: str = "ok") -> dict[str, Any]:
    return {
        "id": source_id,
        "label": source_id.replace("_", " ").title(),
        "state": state,
        "source_time": "2026-08-16T00:00:00Z" if state == "ok" else None,
        "retrieved_at": "2026-08-16T00:01:00Z",
        "payload_sha256": hashlib.sha256(source_id.encode()).hexdigest() if state == "ok" else None,
        "attribution": f"Public attribution for {source_id}",
        "rights": "Public test terms",
        "storage_policy": "Retain bounded public test metadata",
        "claim_scope": f"Bounded public source claim for {source_id}",
        "error": None if state == "ok" else f"Public {state.replace('_', ' ')} state",
    }


class ExperienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.experience = self.repo / "manzanita-next" / "experience"
        self.public = self.repo / "manzanita-next" / "public-demo" / "out"
        self.apertures = self.repo / "manzanita-next" / "apertures" / "out"
        self.street = self.repo / "manzanita-next" / "street-glide" / "out"
        self.overlays = self.repo / "manzanita-next" / "overlays" / "out"
        self.roles = self.repo / "manzanita-next" / "roles" / "out"
        self.constitution = self.repo / "manzanita-next" / "design-system" / "CONSTITUTION.json"
        self.contract = self.experience / "EXPERIENCE_CONTRACT.json"
        self.template = self.experience / "template"
        self.output = self.experience / "out"

        self.experience.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(EXPERIENCE_ROOT / "EXPERIENCE_CONTRACT.json", self.contract)
        shutil.copytree(EXPERIENCE_ROOT / "template", self.template)
        self._write_donors()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_donors(self) -> None:
        place = {
            "id": "mw-public-test",
            "label": "Public Test Place",
            "latitude": 34.1433,
            "longitude": -118.055,
            "coordinate_precision_decimals": 4,
            "public_safe": True,
            "projection": "public_safe",
        }
        states = {
            "google_street_view": "skipped_missing_credential",
            "mapillary": "skipped_missing_credential",
            "kartaview": "empty",
            "panoramax": "empty",
            "airnow": "skipped_missing_credential",
            "firms": "skipped_missing_credential",
        }
        source_ids = [
            "nws_points", "nws_forecast", "nws_observation", "nws_alerts", "calfire_incidents",
            "usgs_imagery", "usgs_3dep_hillshade", "usgs_water_sites", "usgs_water_iv", "osm_overpass",
            "google_street_view", "mapillary", "kartaview", "panoramax", "airnow", "firms",
        ]
        public_data = {
            "schema": "axm-tools/manzanita-public-demo-data@1",
            "build_id": "public-build-test",
            "source_run_id": "source-run-test",
            "source_manifest_sha256": "1" * 64,
            "source_reference_time": "2026-08-16T00:00:00Z",
            "generated_at": "2026-08-16T00:00:00Z",
            "default_view": "household",
            "default_actor": "resident",
            "place": place,
            "sources": [source_row(source_id, states.get(source_id, "ok")) for source_id in source_ids],
            "failures": [],
            "claim_boundary": "Public-safe test projection only.",
            "public_effect": "none",
            "constitutional_count_effect": "none",
        }
        write_json(self.public / "PUBLIC_DATA.json", public_data)
        write_json(self.public / "PUBLIC_PROJECTION_RECEIPT.json", {
            "schema": "axm-tools/manzanita-public-projection-receipt@1",
            "result": "PASS",
            "place_id": place["id"],
            "payload_sha256": "2" * 64,
        })
        write_json(self.public / "BUILD_RECEIPT.json", {
            "schema": "axm-tools/manzanita-public-demo-build@1",
            "result": "PASS",
            "release_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "3" * 64,
        })
        image_path = self.public / "site" / "assets" / "base-imagery.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (160, 100), (102, 124, 94)).save(image_path, format="PNG")
        image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()

        aperture_rows = []
        aperture_states = {
            "plant": "authored", "street": "skipped_missing_credential", "region": "skipped_missing_credential",
            "stewardship": "authored",
        }
        for index, aperture_id in enumerate(APERTURES, start=1):
            row = {
                "id": aperture_id,
                "order": index,
                "place_id": place["id"],
                "source_run_id": "source-run-test",
                "state": aperture_states.get(aperture_id, "ok"),
                "object_class": f"{aperture_id}_governed_object",
                "geometry": {
                    "id": f"geometry-{aperture_id}",
                    "class": "authored_aperture_registration",
                    "source_class": "authored_aperture_registration",
                    "path": f"M50 {500-index*20} C280 430 710 280 1140 {80+index*8}",
                    "branch": f"M500 300 C560 {320+index} 620 380 670 430",
                    "authority_cut": "M640 390 l24 38",
                    "claim_boundary": "Authored test geometry; not observed or surveyed.",
                },
                "primary_actor": "resident" if index < 3 else "steward",
                "reading": f"Substantive reading for the {aperture_id} aperture and its governed object.",
                "uncertainty": f"The {aperture_id} test aperture retains bounded uncertainty and no private claim.",
                "safe_action": f"Verify the {aperture_id} evidence before taking any consequential action.",
                "authority": f"The accountable {aperture_id} actor may prepare a bounded internal question only.",
                "acceptance": f"The {aperture_id} result requires an accountable human acceptance receipt.",
                "handoff": f"Hand the {aperture_id} question to the next accountable seat with evidence intact.",
                "prohibited_consequence": f"No {aperture_id} adverse decision, work authorization, or completion claim.",
                "evidence_state_counts": {aperture_states.get(aperture_id, "ok"): 1},
                "payload_sha256": hashlib.sha256(aperture_id.encode()).hexdigest(),
            }
            aperture_rows.append(row)
        aperture_bundle = {
            "schema": "axm-tools/manzanita-seven-aperture-bundle@1",
            "place": place,
            "source_run_id": "source-run-test",
            "aperture_count": 7,
            "aperture_order": APERTURES,
            "apertures": aperture_rows,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "4" * 64,
        }
        write_json(self.apertures / "APERTURE_BUNDLE.json", aperture_bundle)
        write_json(self.apertures / "BUILD_RECEIPT.json", {
            "schema": "axm-tools/manzanita-seven-aperture-build@1",
            "result": "PASS",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "5" * 64,
        })

        scene = {
            "schema": "axm-tools/manzanita-street-glide-scene-decision@1",
            "result": "PASS",
            "place_id": place["id"],
            "source_run_id": "source-run-test",
            "selected_mode": "map_only",
            "selected_provider": "map_only",
            "selected_scene": None,
            "provider_attempts": [],
            "map_only_receipts": [],
            "safe_action": "Use map-only context and request an authorized source when street evidence matters.",
            "authority": "Map-only context supplies no field, property, access, or work authority.",
            "claim_boundary": "Internal scene decision only.",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "6" * 64,
        }
        write_json(self.street / "SCENE_DECISION.json", scene)
        registration = {
            "schema": "axm-tools/manzanita-natural-border-registration@1",
            "result": "PASS",
            "admission_state": "registration_proposal",
            "image": {"path": "base-imagery.png", "format": "PNG", "width": 160, "height": 100, "sha256": image_sha},
            "original_points": [[16, 78], [40, 69], [64, 60], [88, 51], [112, 42], [136, 34]],
            "proposed_points": [[16, 78], [40, 69], [64, 60], [89, 52], [112, 42], [136, 34]],
            "point_count": 6,
            "snapped_point_count": 1,
            "mean_displacement_pixels": 0.24,
            "mean_gradient_strength": 0.11,
            "confidence_class": "low_edge_alignment",
            "claim_boundary": "Derived image-edge registration proposal; no physical feature identity.",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "7" * 64,
        }
        write_json(self.street / "REGISTRATION_RECEIPT.json", registration)

        overlay_states = {
            "care": "authored_demonstration", "air": "held_missing_source", "fire": "degraded",
            "access": "map_only", "assistance": "authored_demonstration",
        }
        geometry_types = ["polygon", "polyline", "multipoint", "graph", "polygon", "polyline", "graph", "multipoint"]
        overlay_rows = []
        for index, overlay_id in enumerate(OVERLAYS, start=1):
            geometry_type = geometry_types[index - 1]
            coordinates = [[.08 + index * .03, .75], [.25 + index * .02, .55], [.5, .4], [.72, .22]]
            if geometry_type == "polygon": coordinates.append(coordinates[0])
            edges = [[0, 1], [1, 2], [2, 3]] if geometry_type == "graph" else []
            source_state = "skipped_missing_credential" if overlay_id == "air" else "ok"
            overlay_rows.append({
                "id": overlay_id,
                "order": index,
                "place_id": place["id"],
                "source_run_id": "source-run-test",
                "state": overlay_states.get(overlay_id, "available"),
                "object_class": f"{overlay_id}_registered_instrument",
                "primary_actor": "resident" if index < 3 else "steward",
                "geometry": {
                    "id": f"overlay-geometry-{overlay_id}",
                    "overlay_id": overlay_id,
                    "geometry_type": geometry_type,
                    "coordinate_space": "normalized_base_image",
                    "coordinates": coordinates,
                    "edges": edges,
                    "source_class": "authored_overlay_registration",
                    "legend_symbol": f"symbol-{overlay_id}",
                    "claim_boundary": "Authored normalized geometry; not observed or surveyed.",
                    "payload_sha256": hashlib.sha256(f"geometry-{overlay_id}".encode()).hexdigest(),
                },
                "base_registration": {
                    "coordinate_space": "normalized_base_image",
                    "base_image_sha256": image_sha,
                    "selected_scene_mode": "map_only",
                    "selected_provider": "map_only",
                    "registration_admission_state": "registration_proposal",
                },
                "legend": [{"id": f"legend-{overlay_id}", "symbol": "□", "meaning": f"Meaning for {overlay_id}", "non_claim": "No physical finding."}],
                "source_evidence": [source_row(f"source-{overlay_id}", source_state)],
                "missing_source_ids": [f"source-{overlay_id}"] if source_state != "ok" else [],
                "degraded_source_count": int(source_state != "ok"),
                "reading": f"The {overlay_id} instrument presents a distinct source-bound operational reading.",
                "uncertainty": f"The {overlay_id} instrument preserves missing, authored, and degraded evidence.",
                "safe_action": f"Verify {overlay_id} evidence with the accountable actor before acting.",
                "authority": f"The {overlay_id} instrument can prepare an internal question only.",
                "acceptance": f"The {overlay_id} projection requires accountable affected-actor acceptance.",
                "handoff": f"Hand off the {overlay_id} question with source and uncertainty intact.",
                "conflicts_with": [OVERLAYS[(index) % len(OVERLAYS)]],
                "conflict_behavior": f"Retain the {overlay_id} instrument and its counterpart without averaging.",
                "prohibited_consequence": f"No {overlay_id} adverse, field, insurance, enforcement, or completion consequence.",
                "payload_sha256": hashlib.sha256(overlay_id.encode()).hexdigest(),
            })
        # Make conflicts symmetric as pairs care/shade, water/heat, air/fire, access/assistance.
        for first, second in zip(OVERLAYS[::2], OVERLAYS[1::2]):
            next(row for row in overlay_rows if row["id"] == first)["conflicts_with"] = [second]
            next(row for row in overlay_rows if row["id"] == second)["conflicts_with"] = [first]
        overlay_bundle = {
            "schema": "axm-tools/manzanita-eight-overlay-bundle@1",
            "place": place,
            "source_run_id": "source-run-test",
            "base_image_sha256": image_sha,
            "overlay_count": 8,
            "overlay_order": OVERLAYS,
            "overlays": overlay_rows,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "8" * 64,
        }
        write_json(self.overlays / "OVERLAY_BUNDLE.json", overlay_bundle)
        write_json(self.overlays / "BUILD_RECEIPT.json", {
            "schema": "axm-tools/manzanita-eight-overlay-build@1",
            "result": "PASS",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "9" * 64,
        })

        role_states = {"resident": "available", "nursery_grower": "degraded", "crew_steward": "degraded", "planner_program": "held_missing_evidence", "successor": "held_missing_evidence"}
        role_rows = []
        for index, role_id in enumerate(ROLES, start=1):
            evidence = {
                "aperture_ids": APERTURES[max(0, index - 2):] or APERTURES,
                "overlay_ids": OVERLAYS[max(0, index - 2):] or OVERLAYS,
                "evidence_count": 10 + index,
                "degraded_evidence_count": index,
                "state_counts": {role_states[role_id]: 1},
                "source_state_counts": {"ok": 8, "skipped_missing_credential": index},
                "missing_source_ids": ["airnow"] if index > 1 else [],
                "unavailable_source_ids": ["airnow", "firms"] if index > 2 else [],
                "map_only_overlay_ids": ["access"],
                "payload_sha256": hashlib.sha256(f"evidence-{role_id}".encode()).hexdigest(),
            }
            export = {
                "format": "portable_json_packet",
                "contract": f"Bounded {role_id} export contract",
                "external_effect": "none",
                "release_state": "not_authorized",
                "claim_boundary": "Portable internal test record only; no contact, decision, or execution.",
                "payload_sha256": hashlib.sha256(f"export-{role_id}".encode()).hexdigest(),
            }
            role_rows.append({
                "id": role_id,
                "order": index,
                "label": role_id.replace("_", " ").title(),
                "place_id": place["id"],
                "source_run_id": "source-run-test",
                "state": role_states[role_id],
                "object_class": f"{role_id}_functional_projection",
                "primary_actor": role_id,
                "operating_purpose": f"Distinct operating purpose for the {role_id} functional seat.",
                "evidence": evidence,
                "controls": [f"Review {role_id} evidence", f"Prepare {role_id} handoff"],
                "reading": f"The {role_id} seat changes evidence, controls, authority, acceptance, export, and handoff.",
                "safe_actions": [f"Review the bounded {role_id} evidence", f"Prepare a no-effect {role_id} handoff"],
                "authority": f"The {role_id} seat has bounded internal preparation authority and no external effect.",
                "acceptance": f"The {role_id} result requires a distinct accountable acceptance receipt.",
                "export": export,
                "handoff_to": [value for value in ROLES if value != role_id],
                "handoff": f"Transfer a bounded {role_id} question without implied authority.",
                "failure_state": f"The {role_id} seat holds when required evidence or authority is absent.",
                "prohibited_consequence": f"No {role_id} contact, eligibility, work, adverse, or release consequence.",
                "payload_sha256": hashlib.sha256(role_id.encode()).hexdigest(),
            })
        role_bundle = {
            "schema": "axm-tools/manzanita-five-role-bundle@1",
            "bundle_id": "role-bundle-test",
            "place": place,
            "source_run_id": "source-run-test",
            "role_count": 5,
            "role_order": ROLES,
            "roles": role_rows,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "a" * 64,
        }
        write_json(self.roles / "ROLE_BUNDLE.json", role_bundle)
        write_json(self.roles / "BUILD_RECEIPT.json", {
            "schema": "axm-tools/manzanita-five-role-build@1",
            "result": "PASS",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "b" * 64,
        })
        write_json(self.roles / "FAB_HANDOFF.json", {
            "schema": "axm-tools/manzanita-fab-handoff@1",
            "handoff_id": "fab-handoff-test",
            "classification": "bounded_internal_assistance_offer_preparation",
            "source_role": "planner_program",
            "affected_actor_role": "resident",
            "target_system": "Essential Attention",
            "target_object": "FAB offer register and executive review",
            "place_id": place["id"],
            "source_run_id": "source-run-test",
            "role_bundle_sha256": role_bundle["payload_sha256"],
            "evidence": {"state": "held_missing_evidence", "degraded_evidence_count": 3, "missing_source_ids": ["airnow"], "payload_sha256": "c" * 64},
            "proposal": {
                "question": "Should an accountable operator prepare a bounded source-repair and assistance review?",
                "authority": "Internal preparation only.",
                "acceptance": "Affected-actor review is required.",
                "refusal_and_appeal": "The affected actor may refuse, narrow, defer, correct, or appeal.",
                "resident_boundary": "Resident authority remains separate.",
                "execution_state": "not_authorized",
                "award_state": "not_decided",
                "eligibility_state": "not_determined",
            },
            "effect_firewall": {"external_effect": "none", "contact": "not_authorized", "payment": "not_authorized", "publication": "not_authorized", "appointment": "not_authorized", "representation": "not_authorized", "insurance": "prohibited", "enforcement": "prohibited"},
            "release_state": "not_authorized",
            "claim_boundary": "Internal portable preparation record only.",
            "control_question": "Can the handoff preserve evidence and refusal without creating eligibility or execution?",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "payload_sha256": "d" * 64,
        })
        write_json(self.constitution, {
            "schema": "axm-tools/manzanita-design-constitution@1",
            "constitution_id": "M99-DESIGN-CONSTITUTION",
            "version": "1.0.0",
            "identity": {"name": "Forkline Field"},
        })

    def build(self, output: Path | None = None) -> dict[str, Any]:
        return builder.build(
            repo_root=self.repo,
            contract_path=self.contract,
            public_demo_root=self.public,
            aperture_root=self.apertures,
            street_glide_root=self.street,
            overlay_root=self.overlays,
            role_root=self.roles,
            constitution_path=self.constitution,
            template_root=self.template,
            output_root=output or self.output,
        )

    def test_builds_complete_source_bound_experience(self) -> None:
        receipt = self.build()
        data = json.loads((self.output / "EXPERIENCE_DATA.json").read_text())
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["experience"]["aperture_count"], 7)
        self.assertEqual(receipt["experience"]["overlay_count"], 8)
        self.assertEqual(receipt["experience"]["role_count"], 5)
        self.assertEqual(data["aperture_order"], APERTURES)
        self.assertEqual(data["overlay_order"], OVERLAYS)
        self.assertEqual(data["role_order"], ROLES)
        self.assertEqual(data["scene"]["selected_mode"], "map_only")
        self.assertEqual(data["fab_handoff"]["release_state"], "not_authorized")
        self.assertEqual(data["public_effect"], "none")
        self.assertEqual(data["constitutional_count_effect"], "none")
        self.assertEqual(data["release_effect"], "none")
        self.assertTrue(all(row["geometry"] for row in data["apertures"]))
        self.assertEqual(len(data["registration"]["original_points"]), 6)
        self.assertEqual(receipt["site"]["network_requests_required"], 0)
        self.assertEqual(receipt["site"]["file_count"], 5)

    def test_build_is_deterministic_for_identical_inputs(self) -> None:
        first = self.experience / "out-first"
        second = self.experience / "out-second"
        one = self.build(first)
        two = self.build(second)
        self.assertEqual(one["payload_sha256"], two["payload_sha256"])
        self.assertEqual((first / "EXPERIENCE_DATA.json").read_bytes(), (second / "EXPERIENCE_DATA.json").read_bytes())
        self.assertEqual((first / "site" / "experience-data.js").read_bytes(), (second / "site" / "experience-data.js").read_bytes())

    def test_private_or_credential_field_is_rejected(self) -> None:
        path = self.public / "PUBLIC_DATA.json"
        value = json.loads(path.read_text())
        value["place"]["street_address"] = "private test value"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "prohibited keys"):
            self.build()

    def test_non_none_donor_effect_is_rejected(self) -> None:
        path = self.overlays / "BUILD_RECEIPT.json"
        value = json.loads(path.read_text())
        value["public_effect"] = "public"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "public effect"):
            self.build()

    def test_public_build_release_effect_field_is_supported(self) -> None:
        path = self.public / "BUILD_RECEIPT.json"
        value = json.loads(path.read_text())
        value["release_effect"] = "none"
        write_json(path, value)
        self.assertEqual(self.build()["result"], "PASS")

    def test_place_identity_drift_is_rejected(self) -> None:
        path = self.roles / "ROLE_BUNDLE.json"
        value = json.loads(path.read_text())
        value["place"]["id"] = "different-place"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "role place identity drifted"):
            self.build()

    def test_source_run_drift_is_rejected(self) -> None:
        path = self.overlays / "OVERLAY_BUNDLE.json"
        value = json.loads(path.read_text())
        value["source_run_id"] = "different-run"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "overlay source-run identity drifted"):
            self.build()

    def test_registration_image_mismatch_is_rejected(self) -> None:
        path = self.street / "REGISTRATION_RECEIPT.json"
        value = json.loads(path.read_text())
        value["image"]["sha256"] = "0" * 64
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "Registration image identity drifted"):
            self.build()

    def test_fab_role_bundle_identity_drift_is_rejected(self) -> None:
        path = self.roles / "FAB_HANDOFF.json"
        value = json.loads(path.read_text())
        value["role_bundle_sha256"] = "0" * 64
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "FAB role bundle identity drifted"):
            self.build()

    def test_role_order_drift_is_rejected(self) -> None:
        path = self.roles / "ROLE_BUNDLE.json"
        value = json.loads(path.read_text())
        value["role_order"] = list(reversed(ROLES))
        write_json(path, value)
        with self.assertRaisesRegex(builder.ExperienceError, "Role order drifted"):
            self.build()

    def test_missing_template_blocks_build(self) -> None:
        (self.template / "app.js").unlink()
        with self.assertRaisesRegex(builder.ExperienceError, "Missing template_app"):
            self.build()

    def test_site_is_self_contained_and_has_no_remote_urls(self) -> None:
        self.build()
        site = self.output / "site"
        combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in site.iterdir() if path.suffix in {".html", ".css", ".js"})
        self.assertNotIn('<script src="http', combined.lower())
        self.assertNotIn('<link href="http', combined.lower())
        self.assertNotIn('@import url(http', combined.lower())
        self.assertNotIn('url(http', combined.lower())
        self.assertIn("connect-src 'none'", combined)
        self.assertNotIn("gradient(", combined.lower())
        self.assertNotIn("box-shadow:", combined.lower())

    def test_export_law_remains_no_effect(self) -> None:
        self.build()
        data = json.loads((self.output / "EXPERIENCE_DATA.json").read_text())
        self.assertEqual(data["export_law"]["external_effect"], "none")
        self.assertEqual(data["export_law"]["release_state"], "not_authorized")
        self.assertEqual(data["export_law"]["private_record_transfer"], "prohibited")

    def test_unavailable_sources_remain_visible(self) -> None:
        self.build()
        data = json.loads((self.output / "EXPERIENCE_DATA.json").read_text())
        states = {row["id"]: row["state"] for row in data["source_summary"]["sources"]}
        self.assertEqual(states["airnow"], "skipped_missing_credential")
        self.assertEqual(states["kartaview"], "empty")
        self.assertEqual(next(row for row in data["overlays"] if row["id"] == "air")["state"], "held_missing_source")
        self.assertEqual(next(row for row in data["overlays"] if row["id"] == "access")["state"], "map_only")


    def test_keyboard_group_binding_is_single_and_focus_safe(self) -> None:
        app = (EXPERIENCE_ROOT / "template" / "app.js").read_text(encoding="utf-8")
        self.assertIn('fieldset.dataset.keyboardBound === "true"', app)
        self.assertIn('fieldset.dataset.keyboardBound = "true"', app)
        self.assertIn("select(kind, id);", app)
        self.assertIn("focusControl(kind, id);", app)
        self.assertNotIn("buttons[next].click();", app)

if __name__ == "__main__":
    unittest.main()
