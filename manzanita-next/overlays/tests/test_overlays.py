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

OVERLAY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OVERLAY_ROOT))

import build_overlays as builder  # noqa: E402

EXPECTED_OVERLAYS = [
    "care",
    "shade",
    "water",
    "heat",
    "air",
    "fire",
    "access",
    "assistance",
]
SOURCE_IDS = sorted(
    {
        "nws_forecast",
        "usgs_imagery",
        "usgs_3dep_hillshade",
        "nws_forecast_hourly",
        "usgs_water_sites",
        "usgs_water_iv",
        "nws_observation",
        "nws_alerts",
        "airnow",
        "calfire_incidents",
        "calfire_incidents_normalized",
        "firms",
        "osm_overpass",
        "google_street_view",
        "mapillary",
        "kartaview_coverage",
        "kartaview",
        "panoramax",
    }
)
APERTURE_IDS = [
    "plant",
    "household",
    "property",
    "street",
    "neighborhood",
    "region",
    "stewardship",
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def payload_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_row(source_id: str, state: str = "ok") -> dict[str, Any]:
    return {
        "id": source_id,
        "label": source_id.replace("_", " ").title(),
        "state": state,
        "source_time": "2026-08-16T00:00:00Z" if state == "ok" else None,
        "retrieved_at": "2026-08-16T00:00:00Z",
        "payload_sha256": hashlib.sha256(source_id.encode()).hexdigest() if state == "ok" else None,
        "attribution": f"Public source attribution for {source_id}",
        "rights": "Public test terms",
        "storage_policy": "Retain public test metadata",
        "claim_scope": f"Bounded public source scope for {source_id}",
        "error": None if state == "ok" else f"Public {state.replace('_', ' ')} state",
        "receipt_path": f"receipts/{source_id}.json",
    }


class OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.overlays = self.repo / "manzanita-next" / "overlays"
        self.public_demo = self.repo / "manzanita-next" / "public-demo" / "out"
        self.apertures = self.repo / "manzanita-next" / "apertures" / "out"
        self.street = self.repo / "manzanita-next" / "street-glide" / "out"
        self.constitution = self.repo / "manzanita-next" / "design-system" / "CONSTITUTION.json"
        self.contract = self.overlays / "OVERLAY_CONTRACT.json"
        self.authored = self.overlays / "AUTHORED_OVERLAY_DEMO.json"
        self.output = self.overlays / "out"

        self.overlays.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OVERLAY_ROOT / "OVERLAY_CONTRACT.json", self.contract)
        shutil.copyfile(OVERLAY_ROOT / "AUTHORED_OVERLAY_DEMO.json", self.authored)
        write_json(
            self.constitution,
            {
                "schema": "axm-tools/manzanita-design-constitution@1",
                "version": "1.0.0",
            },
        )
        self._write_donors()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_donors(self) -> None:
        states = {
            "airnow": "skipped_missing_credential",
            "firms": "skipped_missing_credential",
            "google_street_view": "skipped_missing_credential",
            "mapillary": "skipped_missing_credential",
            "kartaview_coverage": "empty",
            "kartaview": "empty",
            "panoramax": "empty",
        }
        public_data = {
            "schema": "axm-tools/manzanita-public-demo-data@1",
            "build_id": "public-build-test",
            "source_run_id": "source-run-test",
            "source_manifest_sha256": "1" * 64,
            "place": {
                "id": "mw-public-test",
                "label": "Public Test Place",
                "latitude": 34.1432,
                "longitude": -118.055,
                "coordinate_precision_decimals": 4,
                "public_safe": True,
                "projection": "public_safe",
            },
            "sources": [source_row(source_id, states.get(source_id, "ok")) for source_id in SOURCE_IDS],
        }
        write_json(self.public_demo / "PUBLIC_DATA.json", public_data)
        write_json(
            self.public_demo / "PUBLIC_PROJECTION_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-public-projection-receipt@1",
                "result": "PASS",
                "place_id": "mw-public-test",
                "payload_sha256": "2" * 64,
            },
        )
        write_json(
            self.public_demo / "BUILD_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-public-demo-build@1",
                "result": "PASS",
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "payload_sha256": "3" * 64,
            },
        )
        image_path = self.public_demo / "site" / "assets" / "base-imagery.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (160, 100), (120, 145, 110)).save(image_path, format="PNG")
        image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()

        aperture_rows = []
        for index, aperture_id in enumerate(APERTURE_IDS, start=1):
            row = {
                "id": aperture_id,
                "order": index,
                "place_id": "mw-public-test",
                "source_run_id": "source-run-test",
                "object_class": f"{aperture_id}_test_object",
                "primary_actor": "resident" if index <= 2 else "steward" if index <= 4 else "program_operator",
                "state": "authored" if aperture_id in {"plant", "household", "stewardship"} else "ok",
                "reading": f"Substantive bounded reading for the {aperture_id} test aperture and its retained evidence.",
                "authority": f"Substantive bounded authority for the {aperture_id} test aperture with no external effect.",
                "prohibited_consequence": f"No private, field, adverse, public, or completion consequence follows from the {aperture_id} test aperture.",
            }
            row["payload_sha256"] = payload_hash(row)
            aperture_rows.append(row)
        aperture_bundle = {
            "schema": "axm-tools/manzanita-seven-aperture-bundle@1",
            "place": public_data["place"],
            "source_run_id": "source-run-test",
            "apertures": aperture_rows,
        }
        aperture_bundle["payload_sha256"] = payload_hash(aperture_bundle)
        write_json(self.apertures / "APERTURE_BUNDLE.json", aperture_bundle)
        write_json(
            self.apertures / "BUILD_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-seven-aperture-build@1",
                "result": "PASS",
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "payload_sha256": "4" * 64,
            },
        )

        scene = {
            "schema": "axm-tools/manzanita-street-glide-scene-decision@1",
            "result": "PASS",
            "place_id": "mw-public-test",
            "source_run_id": "source-run-test",
            "selected_mode": "map_only",
            "selected_provider": "map_only",
            "selected_scene": None,
            "provider_attempts": [
                {"provider_id": provider_id, "result": states.get(provider_id, "unknown")}
                for provider_id in [
                    "google_street_view",
                    "mapillary",
                    "kartaview",
                    "panoramax",
                    "owned_capture",
                ]
            ],
            "map_only_receipts": [
                {"source_id": source_id, "state": "ok"}
                for source_id in ["osm_overpass", "usgs_imagery", "usgs_3dep_hillshade"]
            ],
            "safe_action": "Use public map context and request an authorized current capture when street evidence matters.",
            "authority": "Map-only mode provides public context and no entry, inspection, work, or field authority.",
            "prohibited_consequence": "No fabricated street scene, field finding, property consequence, work, or adverse action.",
            "claim_boundary": "Internal map-only Street Glide decision only.",
            "public_effect": "none",
            "constitutional_count_effect": "none",
        }
        scene["payload_sha256"] = payload_hash(scene)
        write_json(self.street / "SCENE_DECISION.json", scene)

        registration = {
            "schema": "axm-tools/manzanita-natural-border-registration@1",
            "result": "PASS",
            "admission_state": "registration_proposal",
            "image": {
                "path": "manzanita-next/public-demo/out/site/assets/base-imagery.png",
                "format": "PNG",
                "width": 160,
                "height": 100,
                "sha256": image_sha,
                "image_class": "public_base_imagery_demonstration",
            },
            "candidate": {
                "id": "candidate-test",
                "source_class": "authored_registration_candidate",
                "sha256": "5" * 64,
            },
            "method": {
                "id": "sobel_normal_search_v1",
                "source_class": "derived_image_edge_registration_proposal",
                "normal_search_only": True,
                "feature_identity": "prohibited",
            },
            "point_count": 6,
            "snapped_point_count": 4,
            "mean_displacement_pixels": 8.0,
            "mean_gradient_strength": 0.25,
            "confidence_class": "medium_edge_alignment",
            "known": "The source image, digest, authored line, bounded search, displacement, and gradient are known.",
            "unknown": "The physical identity, ownership, legal status, field condition, and safety of the edge remain unknown.",
            "safe_action": "Review and verify the physical feature and authority before operational use.",
            "authority": "The kernel proposes image registration geometry and no field or physical-feature authority.",
            "prohibited_consequence": "No property, access, hazard, safety, work, insurance, enforcement, or adverse decision.",
            "claim_boundary": "Derived image-edge registration proposal only; not a physical or legal feature.",
            "public_effect": "none",
            "constitutional_count_effect": "none",
        }
        registration["payload_sha256"] = payload_hash(registration)
        write_json(self.street / "REGISTRATION_RECEIPT.json", registration)

    def build(self, output: Path | None = None) -> dict[str, Any]:
        return builder.build(
            self.repo,
            self.contract,
            self.authored,
            self.public_demo,
            self.apertures,
            self.street,
            self.constitution,
            output or self.output,
        )

    def test_contract_has_eight_distinct_registered_instruments(self) -> None:
        contract = json.loads(self.contract.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], "axm-tools/manzanita-eight-overlay-contract@1")
        self.assertEqual(contract["task_reference"], "JDB99-015")
        self.assertEqual(contract["object"]["public_effect"], "none")
        self.assertEqual(contract["object"]["constitutional_count_effect"], "none")
        rows = contract["overlays"]
        self.assertEqual([row["id"] for row in rows], EXPECTED_OVERLAYS)
        self.assertEqual([row["order"] for row in rows], list(range(1, 9)))
        for field in (
            "object_class",
            "authored_geometry_id",
            "reading",
            "uncertainty",
            "safe_action",
            "authority",
            "acceptance",
            "handoff",
            "conflict_behavior",
            "prohibited_consequence",
        ):
            self.assertEqual(len({row[field] for row in rows}), 8, field)
        conflicts = {row["id"]: set(row["conflicts_with"]) for row in rows}
        for overlay_id, others in conflicts.items():
            self.assertNotIn(overlay_id, others)
            for other in others:
                self.assertIn(overlay_id, conflicts[other])
        self.assertIn("one severity", json.dumps(contract).lower())

    def test_authored_geometry_is_public_safe_normalized_and_unique(self) -> None:
        authored = json.loads(self.authored.read_text(encoding="utf-8"))
        self.assertEqual(authored["schema"], "axm-tools/manzanita-authored-overlay-demo@1")
        self.assertTrue(authored["public_safe"])
        self.assertFalse(authored["private_household"])
        self.assertEqual(authored["coordinate_space"], "normalized_base_image")
        rows = authored["geometries"]
        self.assertEqual([row["overlay_id"] for row in rows], EXPECTED_OVERLAYS)
        self.assertEqual(len({row["id"] for row in rows}), 8)
        self.assertEqual(len({json.dumps(row["coordinates"]) for row in rows}), 8)
        for row in rows:
            for pair in row["coordinates"]:
                self.assertEqual(len(pair), 2)
                self.assertTrue(all(0 <= value <= 1 for value in pair))
            self.assertIn("not", row["claim_boundary"].lower())

    def test_build_emits_one_place_and_eight_complete_overlays(self) -> None:
        receipt = self.build()
        self.assertEqual(receipt["result"], "PASS")
        bundle = json.loads((self.output / "OVERLAY_BUNDLE.json").read_text(encoding="utf-8"))
        self.assertEqual(bundle["schema"], "axm-tools/manzanita-eight-overlay-bundle@1")
        self.assertEqual(bundle["overlay_count"], 8)
        self.assertEqual(bundle["overlay_order"], EXPECTED_OVERLAYS)
        self.assertEqual({row["place_id"] for row in bundle["overlays"]}, {"mw-public-test"})
        self.assertEqual({row["source_run_id"] for row in bundle["overlays"]}, {"source-run-test"})
        self.assertEqual({row["base_registration"]["coordinate_space"] for row in bundle["overlays"]}, {"normalized_base_image"})
        self.assertEqual(len({row["base_registration"]["base_image_sha256"] for row in bundle["overlays"]}), 1)
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
            self.assertEqual(len({row[field] for row in bundle["overlays"]}), 8, field)
        self.assertEqual(len({row["geometry"]["id"] for row in bundle["overlays"]}), 8)
        self.assertEqual(len({row["geometry"]["payload_sha256"] for row in bundle["overlays"]}), 8)
        self.assertTrue(all(row["legend"] for row in bundle["overlays"]))
        self.assertTrue(all(row["evidence_count"] >= 2 for row in bundle["overlays"]))
        self.assertGreater(bundle["conflict_count"], 0)
        self.assertEqual(bundle["public_effect"], "none")
        self.assertEqual(bundle["constitutional_count_effect"], "none")
        self.assertEqual(len(bundle["payload_sha256"]), 64)

    def test_expected_degraded_states_remain_distinct(self) -> None:
        self.build()
        bundle = json.loads((self.output / "OVERLAY_BUNDLE.json").read_text(encoding="utf-8"))
        states = {row["id"]: row["state"] for row in bundle["overlays"]}
        self.assertEqual(states["care"], "authored_demonstration")
        self.assertEqual(states["assistance"], "authored_demonstration")
        self.assertEqual(states["air"], "held_missing_source")
        self.assertEqual(states["fire"], "degraded")
        self.assertEqual(states["access"], "map_only")
        self.assertEqual(states["shade"], "available")
        self.assertEqual(states["water"], "available")
        self.assertEqual(states["heat"], "available")
        air = next(row for row in bundle["overlays"] if row["id"] == "air")
        airnow = next(row for row in air["source_evidence"] if row["id"] == "airnow")
        self.assertEqual(airnow["state"], "skipped_missing_credential")
        self.assertIsNone(airnow["payload_sha256"])

    def test_missing_source_becomes_explicit_unknown_evidence(self) -> None:
        public_path = self.public_demo / "PUBLIC_DATA.json"
        public_data = json.loads(public_path.read_text(encoding="utf-8"))
        public_data["sources"] = [row for row in public_data["sources"] if row["id"] != "nws_observation"]
        write_json(public_path, public_data)
        self.build()
        bundle = json.loads((self.output / "OVERLAY_BUNDLE.json").read_text(encoding="utf-8"))
        for overlay_id in ("heat", "air"):
            overlay = next(row for row in bundle["overlays"] if row["id"] == overlay_id)
            self.assertIn("nws_observation", overlay["missing_source_ids"])
            missing = next(row for row in overlay["source_evidence"] if row["id"] == "nws_observation")
            self.assertEqual(missing["state"], "unknown")
            self.assertIn("no substantive claim", missing["claim_scope"].lower())

    def test_out_of_range_geometry_is_rejected(self) -> None:
        authored = json.loads(self.authored.read_text(encoding="utf-8"))
        authored["geometries"][0]["coordinates"][0] = [1.5, 0.5]
        write_json(self.authored, authored)
        with self.assertRaisesRegex(builder.OverlayError, "outside normalized space"):
            self.build()

    def test_duplicate_geometry_is_rejected(self) -> None:
        authored = json.loads(self.authored.read_text(encoding="utf-8"))
        authored["geometries"][1]["coordinates"] = copy.deepcopy(authored["geometries"][0]["coordinates"])
        authored["geometries"][1]["geometry_type"] = authored["geometries"][0]["geometry_type"]
        authored["geometries"][1]["legend_symbol"] = authored["geometries"][0]["legend_symbol"]
        authored["geometries"][1]["claim_boundary"] = authored["geometries"][0]["claim_boundary"]
        write_json(self.authored, authored)
        with self.assertRaisesRegex(builder.OverlayError, "Duplicate authored geometry"):
            self.build()

    def test_asymmetric_conflict_is_rejected(self) -> None:
        contract = json.loads(self.contract.read_text(encoding="utf-8"))
        care = next(row for row in contract["overlays"] if row["id"] == "care")
        care["conflicts_with"].remove("water")
        write_json(self.contract, contract)
        with self.assertRaisesRegex(builder.OverlayError, "is not symmetric"):
            self.build()

    def test_private_or_credential_key_is_rejected(self) -> None:
        public_path = self.public_demo / "PUBLIC_DATA.json"
        public_data = json.loads(public_path.read_text(encoding="utf-8"))
        public_data["place"]["street_address"] = "private value"
        write_json(public_path, public_data)
        with self.assertRaisesRegex(builder.OverlayError, "prohibited keys"):
            self.build()

    def test_scene_identity_drift_is_rejected(self) -> None:
        scene_path = self.street / "SCENE_DECISION.json"
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        scene["source_run_id"] = "different-run"
        write_json(scene_path, scene)
        with self.assertRaisesRegex(builder.OverlayError, "source run drifted"):
            self.build()

    def test_registration_image_digest_mismatch_is_rejected(self) -> None:
        registration_path = self.street / "REGISTRATION_RECEIPT.json"
        registration = json.loads(registration_path.read_text(encoding="utf-8"))
        registration["image"]["sha256"] = "0" * 64
        write_json(registration_path, registration)
        with self.assertRaisesRegex(builder.OverlayError, "image digest"):
            self.build()

    def test_build_is_deterministic_for_same_inputs(self) -> None:
        first_output = self.overlays / "out-first"
        second_output = self.overlays / "out-second"
        first = self.build(first_output)
        second = self.build(second_output)
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(first["bundle"]["payload_sha256"], second["bundle"]["payload_sha256"])
        self.assertEqual(
            (first_output / "OVERLAY_BUNDLE.json").read_bytes(),
            (second_output / "OVERLAY_BUNDLE.json").read_bytes(),
        )
        self.assertEqual(
            (first_output / "BUILD_RECEIPT.json").read_bytes(),
            (second_output / "BUILD_RECEIPT.json").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
