from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

STREET_GLIDE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STREET_GLIDE))

import register_natural_border as registration  # noqa: E402
import resolve_scene as resolver  # noqa: E402

PROVIDER_IDS = [
    "google_street_view",
    "mapillary",
    "kartaview",
    "panoramax",
]


def load(name: str) -> dict[str, Any]:
    return json.loads((STREET_GLIDE / name).read_text(encoding="utf-8"))


def source_row(source_id: str, state: str = "ok") -> dict[str, Any]:
    return {
        "id": source_id,
        "label": source_id.replace("_", " ").title(),
        "state": state,
        "source_time": "2026-08-15T00:00:00Z" if state == "ok" else None,
        "retrieved_at": "2026-08-16T00:00:00Z",
        "payload_sha256": hashlib.sha256(source_id.encode()).hexdigest() if state == "ok" else None,
        "attribution": f"Public source attribution for {source_id}",
        "rights": "Public test terms",
        "storage_policy": "Retain public test metadata",
        "claim_scope": f"Bounded public source scope for {source_id}",
        "error": None if state == "ok" else f"Public {state.replace('_', ' ')} state",
        "receipt_path": f"receipts/{source_id}.json",
    }


def scene(
    provider_id: str,
    scene_id: str,
    *,
    distance: float = 20.0,
    heading: float = 90.0,
    capture_time: str = "2026-08-15T00:00:00Z",
    rights: str = "Provider test rights",
    generated: bool = False,
    modeled: bool = False,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "source_state": "ok",
        "scene_id": scene_id,
        "capture_time": capture_time,
        "latitude": 34.1432,
        "longitude": -118.055,
        "heading_degrees": heading,
        "distance_meters": distance,
        "attribution": f"Provider attribution for {provider_id}",
        "rights": rights,
        "storage_policy": "Provider test storage policy",
        "claim_scope": "Provider scene metadata and imagery within returned terms",
        "render_or_payload_path": f"provider://{provider_id}/{scene_id}",
        "generated": generated,
        "modeled": modeled,
    }


class StreetGlideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load("STREET_GLIDE_CONTRACT.json")
        self.demo = load("AUTHORED_REGISTRATION_DEMO.json")
        self.public_data = {
            "schema": "axm-tools/manzanita-public-demo-data@1",
            "build_id": "public-build-test",
            "source_run_id": "source-run-test",
            "source_manifest_sha256": "1" * 64,
            "generated_at": "2026-08-16T00:00:00Z",
            "source_reference_time": "2026-08-16T00:00:00Z",
            "place": {
                "id": "mw-public-test",
                "label": "Public Test Place",
                "latitude": 34.1432,
                "longitude": -118.055,
                "coordinate_precision_decimals": 4,
                "public_safe": True,
                "projection": "public_safe",
            },
            "sources": [
                source_row("osm_overpass"),
                source_row("usgs_imagery"),
                source_row("usgs_3dep_hillshade"),
                *[source_row(provider_id, "empty") for provider_id in PROVIDER_IDS],
            ],
        }
        self.temp = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def set_provider_state(self, provider_id: str, state: str) -> None:
        for row in self.public_data["sources"]:
            if row["id"] == provider_id:
                row.update(source_row(provider_id, state))
                return
        self.public_data["sources"].append(source_row(provider_id, state))

    def test_contract_freezes_provider_order_and_claim_boundaries(self) -> None:
        self.assertEqual(self.contract["schema"], "axm-tools/manzanita-street-glide-contract@1")
        self.assertEqual(self.contract["task_reference"], "JDB99-014")
        self.assertEqual(
            [row["id"] for row in self.contract["provider_order"]],
            [
                "google_street_view",
                "mapillary",
                "kartaview",
                "panoramax",
                "owned_capture",
                "map_only",
            ],
        )
        self.assertEqual(self.contract["object"]["public_effect"], "none")
        self.assertEqual(self.contract["object"]["constitutional_count_effect"], "none")
        serialized = json.dumps(self.contract).lower()
        for phrase in (
            "generated_scene_prohibited",
            "unknown_boundary_must_remain_open",
            "feature_identity_prohibited",
            "insurance denial",
            "image gradient",
        ):
            self.assertIn(phrase, serialized)

    def test_mapillary_is_selected_after_google_missing_credential(self) -> None:
        self.set_provider_state("google_street_view", "skipped_missing_credential")
        self.set_provider_state("mapillary", "ok")
        demo = copy.deepcopy(self.demo)
        demo["scene_candidates"] = [scene("mapillary", "mapillary-1")]
        decision = resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)
        self.assertEqual(decision["result"], "PASS")
        self.assertEqual(decision["selected_mode"], "provider_scene")
        self.assertEqual(decision["selected_provider"], "mapillary")
        self.assertEqual(decision["selected_scene"]["scene_id"], "mapillary-1")
        self.assertEqual(decision["provider_attempts"][0]["provider_id"], "google_street_view")
        self.assertEqual(decision["provider_attempts"][0]["result"], "skipped_missing_credential")
        self.assertEqual(decision["provider_attempts"][1]["result"], "selected")

    def test_provider_rank_beats_lower_provider_distance(self) -> None:
        self.set_provider_state("google_street_view", "ok")
        self.set_provider_state("mapillary", "ok")
        demo = copy.deepcopy(self.demo)
        demo["scene_candidates"] = [
            scene("google_street_view", "google-1", distance=80.0),
            scene("mapillary", "mapillary-1", distance=5.0),
        ]
        decision = resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)
        self.assertEqual(decision["selected_provider"], "google_street_view")
        self.assertEqual(decision["selected_scene"]["scene_id"], "google-1")
        self.assertEqual(len(decision["provider_attempts"]), 1)

    def test_generated_higher_rank_scene_is_rejected_and_fallback_is_selected(self) -> None:
        self.set_provider_state("google_street_view", "ok")
        self.set_provider_state("mapillary", "ok")
        demo = copy.deepcopy(self.demo)
        demo["scene_candidates"] = [
            scene("google_street_view", "generated-google", generated=True),
            scene("mapillary", "mapillary-1"),
        ]
        decision = resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)
        self.assertEqual(decision["selected_provider"], "mapillary")
        first = decision["provider_attempts"][0]
        self.assertEqual(first["result"], "rejected_generated")
        self.assertEqual(first["candidate_receipts"][0]["result"], "rejected_generated")
        self.assertIn("Generated imagery", first["candidate_receipts"][0]["reason"])

    def test_stale_distance_heading_and_rights_rejections_are_retained(self) -> None:
        self.set_provider_state("google_street_view", "ok")
        self.set_provider_state("mapillary", "ok")
        self.set_provider_state("kartaview", "ok")
        self.set_provider_state("panoramax", "ok")
        demo = copy.deepcopy(self.demo)
        demo["scene_candidates"] = [
            scene("google_street_view", "stale", capture_time="2000-01-01T00:00:00Z"),
            scene("mapillary", "far", distance=500.0),
            scene("kartaview", "wrong-heading", heading=270.0),
            scene("panoramax", "no-rights", rights="unknown"),
        ]
        decision = resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)
        self.assertEqual(decision["selected_mode"], "map_only")
        results = {row["provider_id"]: row["result"] for row in decision["provider_attempts"]}
        self.assertEqual(results["google_street_view"], "stale")
        self.assertEqual(results["mapillary"], "rejected_distance")
        self.assertEqual(results["kartaview"], "rejected_heading")
        self.assertEqual(results["panoramax"], "rejected_rights")

    def test_zero_coverage_produces_explicit_map_only_mode(self) -> None:
        self.set_provider_state("google_street_view", "skipped_missing_credential")
        self.set_provider_state("mapillary", "skipped_missing_credential")
        self.set_provider_state("kartaview", "empty")
        self.set_provider_state("panoramax", "empty")
        decision = resolver.resolve(self.contract, self.public_data, self.demo, target_heading=0.0)
        self.assertEqual(decision["result"], "PASS")
        self.assertEqual(decision["selected_mode"], "map_only")
        self.assertEqual(decision["selected_provider"], "map_only")
        self.assertIsNone(decision["selected_scene"])
        self.assertEqual(len(decision["provider_attempts"]), 5)
        self.assertEqual(len(decision["map_only_receipts"]), 3)
        self.assertIn("request an authorized source", decision["safe_action"].lower())
        self.assertIn("no fabricated street scene", decision["prohibited_consequence"].lower())
        self.assertEqual(decision["public_effect"], "none")
        self.assertEqual(decision["constitutional_count_effect"], "none")

    def test_prohibited_scene_input_key_is_rejected(self) -> None:
        self.set_provider_state("mapillary", "ok")
        demo = copy.deepcopy(self.demo)
        candidate = scene("mapillary", "mapillary-1")
        candidate["access_token"] = "not-a-real-token"
        demo["scene_candidates"] = [candidate]
        with self.assertRaisesRegex(resolver.SceneResolutionError, "prohibited keys"):
            resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)

    def test_scene_resolution_is_deterministic(self) -> None:
        self.set_provider_state("mapillary", "ok")
        demo = copy.deepcopy(self.demo)
        demo["scene_candidates"] = [
            scene("mapillary", "second", distance=30.0),
            scene("mapillary", "first", distance=10.0),
        ]
        first = resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)
        second = resolver.resolve(self.contract, self.public_data, demo, target_heading=90.0)
        self.assertEqual(first, second)
        self.assertEqual(first["selected_scene"]["scene_id"], "first")

    def vertical_edge_image(self, name: str = "vertical-edge.png") -> Path:
        path = self.temp_path / name
        image = Image.new("L", (160, 100), 20)
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 0, 159, 99), fill=235)
        image.save(path, format="PNG")
        return path

    def constant_image(self) -> Path:
        path = self.temp_path / "constant.png"
        Image.new("L", (160, 100), 128).save(path, format="PNG")
        return path

    def registration_demo(self, *, x_normalized: float, max_displacement: float = 24.0) -> dict[str, Any]:
        demo = copy.deepcopy(self.demo)
        demo["registration"]["candidate_points"] = [
            [x_normalized, 0.15],
            [x_normalized, 0.35],
            [x_normalized, 0.55],
            [x_normalized, 0.75],
            [x_normalized, 0.9],
        ]
        demo["registration"]["search_radius_pixels"] = 18
        demo["registration"]["minimum_gradient_strength"] = 0.05
        demo["registration"]["maximum_mean_displacement_pixels"] = max_displacement
        return demo

    def test_registration_snaps_vertical_seed_to_vertical_image_edge(self) -> None:
        image = self.vertical_edge_image()
        demo = self.registration_demo(x_normalized=0.45)
        receipt = registration.propose(self.contract, demo, image)
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["admission_state"], "registration_proposal")
        self.assertEqual(receipt["snapped_point_count"], receipt["point_count"])
        proposed_x = [row[0] for row in receipt["proposed_points"]]
        self.assertTrue(all(77.0 <= value <= 82.0 for value in proposed_x), proposed_x)
        self.assertTrue(all(row["gradient_alignment"] >= 0.95 for row in receipt["point_receipts"]))
        self.assertGreater(receipt["mean_gradient_strength"], 0.2)
        self.assertIn(receipt["confidence_class"], {"medium_edge_alignment", "high_edge_alignment"})
        self.assertIn("not a curb", receipt["claim_boundary"].lower())
        self.assertIn("physical identity", receipt["unknown"].lower())
        self.assertEqual(receipt["public_effect"], "none")
        self.assertEqual(receipt["constitutional_count_effect"], "none")

    def test_constant_image_preserves_original_points_as_no_snap(self) -> None:
        image = self.constant_image()
        demo = self.registration_demo(x_normalized=0.45)
        receipt = registration.propose(self.contract, demo, image)
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["admission_state"], "no_snap_proposal")
        self.assertEqual(receipt["snapped_point_count"], 0)
        self.assertEqual(receipt["unsnapped_point_count"], receipt["point_count"])
        self.assertEqual(receipt["original_points"], receipt["proposed_points"])
        self.assertEqual(receipt["confidence_class"], "no_admissible_snap")
        self.assertTrue(all(row["no_snap_reason"] for row in receipt["point_receipts"]))

    def test_registration_displacement_gate_can_hold_a_proposal(self) -> None:
        image = self.vertical_edge_image()
        demo = self.registration_demo(x_normalized=0.45, max_displacement=2.0)
        receipt = registration.propose(self.contract, demo, image)
        self.assertEqual(receipt["result"], "HOLD")
        self.assertEqual(receipt["admission_state"], "displacement_hold")
        self.assertFalse(receipt["within_displacement_gate"])
        self.assertGreater(receipt["mean_displacement_pixels"], 2.0)

    def test_registration_rejects_excessive_search_radius(self) -> None:
        image = self.vertical_edge_image()
        demo = self.registration_demo(x_normalized=0.45)
        demo["registration"]["search_radius_pixels"] = 100
        with self.assertRaisesRegex(registration.RegistrationError, "Search radius exceeds"):
            registration.propose(self.contract, demo, image)

    def test_registration_is_deterministic_and_path_is_portable(self) -> None:
        image = self.vertical_edge_image()
        demo = self.registration_demo(x_normalized=0.45)
        first = registration.propose(self.contract, demo, image)
        second = registration.propose(self.contract, demo, image)
        self.assertEqual(first, second)
        self.assertFalse(Path(first["image"]["path"]).is_absolute())
        self.assertEqual(len(first["image"]["sha256"]), 64)
        self.assertEqual(len(first["candidate"]["sha256"]), 64)
        self.assertEqual(len(first["payload_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
