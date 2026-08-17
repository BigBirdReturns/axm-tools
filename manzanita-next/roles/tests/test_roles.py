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

ROLE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROLE_ROOT))

import build_roles as builder  # noqa: E402

EXPECTED_ROLES = [
    "resident",
    "nursery_grower",
    "crew_steward",
    "planner_program",
    "successor",
]
EXPECTED_APERTURES = [
    "plant",
    "household",
    "property",
    "street",
    "neighborhood",
    "region",
    "stewardship",
]
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def payload_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def aperture_row(aperture_id: str, order: int) -> dict[str, Any]:
    row = {
        "id": aperture_id,
        "order": order,
        "place_id": "mw-public-test",
        "source_run_id": "source-run-test",
        "object_class": f"{aperture_id}_operating_object",
        "primary_actor": "resident" if order <= 2 else "steward",
        "state": "authored" if aperture_id == "plant" else "ok",
        "reading": f"Bounded reading for the {aperture_id} aperture and its retained evidence.",
        "uncertainty": f"Uncertainty remains explicit for the {aperture_id} aperture.",
        "safe_action": f"Review the {aperture_id} evidence before any later action.",
        "authority": f"The accountable actor retains authority for the {aperture_id} aperture.",
        "acceptance": f"Acceptance for {aperture_id} requires an explicit accountable receipt.",
        "handoff": f"Hand off the {aperture_id} question with its evidence and limits.",
        "prohibited_consequence": f"No adverse or external consequence follows from {aperture_id}.",
    }
    row["payload_sha256"] = payload_hash(row)
    return row


def overlay_row(overlay_id: str, order: int) -> dict[str, Any]:
    state = "available"
    missing: list[str] = []
    selected_mode = "source_backed"
    if overlay_id == "air":
        state = "held_missing_source"
        missing = ["airnow"]
    elif overlay_id == "fire":
        state = "degraded"
        missing = ["firms"]
    elif overlay_id == "access":
        state = "map_only"
        selected_mode = "map_only"
    elif overlay_id in {"care", "assistance"}:
        state = "authored_demonstration"
    row = {
        "id": overlay_id,
        "order": order,
        "place_id": "mw-public-test",
        "source_run_id": "source-run-test",
        "object_class": f"{overlay_id}_operating_instrument",
        "primary_actor": "resident" if order <= 3 else "program_operator",
        "state": state,
        "base_registration": {
            "selected_scene_mode": selected_mode,
            "base_image_sha256": "a" * 64,
        },
        "reading": f"Bounded reading for the {overlay_id} overlay and its evidence state.",
        "uncertainty": f"Uncertainty remains explicit for the {overlay_id} overlay.",
        "safe_action": f"Review the {overlay_id} evidence before any later action.",
        "authority": f"The accountable actor retains authority for the {overlay_id} overlay.",
        "acceptance": f"Acceptance for {overlay_id} requires an explicit accountable receipt.",
        "handoff": f"Hand off the {overlay_id} question with its evidence and limits.",
        "conflicts_with": [],
        "missing_source_ids": [],
        "source_evidence": [
            {
                "id": source_id,
                "state": state_name,
                "payload_sha256": hashlib.sha256(source_id.encode()).hexdigest()
                if state_name == "ok"
                else None,
                "claim_scope": f"Bounded source scope for {source_id}.",
                "uncertainty": f"Uncertainty remains explicit for {source_id}.",
            }
            for source_id, state_name in (
                ([("airnow", "skipped_missing_credential")] if overlay_id == "air" else [])
                + ([("firms", "skipped_missing_credential")] if overlay_id == "fire" else [])
                + ([(f"{overlay_id}_source", "ok")] if overlay_id not in {"air", "fire"} else [])
            )
        ],
        "degraded_source_count": len(missing),
        "prohibited_consequence": f"No adverse or external consequence follows from {overlay_id}.",
    }
    row["payload_sha256"] = payload_hash(row)
    return row


class RoleProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.roles = self.repo / "manzanita-next" / "roles"
        self.public = self.repo / "manzanita-next" / "public-demo" / "out"
        self.apertures = self.repo / "manzanita-next" / "apertures" / "out"
        self.overlays = self.repo / "manzanita-next" / "overlays" / "out"
        self.constitution = (
            self.repo / "manzanita-next" / "design-system" / "CONSTITUTION.json"
        )
        self.contract = self.roles / "ROLE_CONTRACT.json"
        self.output = self.roles / "out"

        self.roles.mkdir(parents=True)
        shutil.copyfile(ROLE_ROOT / "ROLE_CONTRACT.json", self.contract)
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
        public_data = {
            "schema": "axm-tools/manzanita-public-demo-data@1",
            "build_id": "public-build-test",
            "source_run_id": "source-run-test",
            "source_manifest_sha256": "1" * 64,
            "place": {
                "id": "mw-public-test",
                "label": "Public Test Place",
                "latitude": 34.1433,
                "longitude": -118.055,
                "coordinate_precision_decimals": 4,
                "public_safe": True,
                "projection": "public_safe",
            },
            "sources": [],
        }
        write_json(self.public / "PUBLIC_DATA.json", public_data)
        write_json(
            self.public / "BUILD_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-public-demo-build@1",
                "result": "PASS",
                "release_effect": "none",
                "constitutional_count_effect": "none",
                "payload_sha256": "2" * 64,
            },
        )

        aperture_rows = [
            aperture_row(aperture_id, index)
            for index, aperture_id in enumerate(EXPECTED_APERTURES, start=1)
        ]
        aperture_bundle = {
            "schema": "axm-tools/manzanita-seven-aperture-bundle@1",
            "bundle_id": "aperture-bundle-test",
            "place": public_data["place"],
            "source_run_id": "source-run-test",
            "aperture_count": 7,
            "aperture_order": EXPECTED_APERTURES,
            "apertures": aperture_rows,
            "public_effect": "none",
            "constitutional_count_effect": "none",
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
                "payload_sha256": "3" * 64,
            },
        )

        overlay_rows = [
            overlay_row(overlay_id, index)
            for index, overlay_id in enumerate(EXPECTED_OVERLAYS, start=1)
        ]
        overlay_bundle = {
            "schema": "axm-tools/manzanita-eight-overlay-bundle@1",
            "bundle_id": "overlay-bundle-test",
            "place": public_data["place"],
            "source_run_id": "source-run-test",
            "overlay_count": 8,
            "overlay_order": EXPECTED_OVERLAYS,
            "overlays": overlay_rows,
            "public_effect": "none",
            "constitutional_count_effect": "none",
        }
        overlay_bundle["payload_sha256"] = payload_hash(overlay_bundle)
        write_json(self.overlays / "OVERLAY_BUNDLE.json", overlay_bundle)
        write_json(
            self.overlays / "BUILD_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-eight-overlay-build@1",
                "result": "PASS",
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "payload_sha256": "4" * 64,
            },
        )

    def build(self, output: Path | None = None) -> dict[str, Any]:
        return builder.build(
            self.repo,
            self.contract,
            self.public,
            self.apertures,
            self.overlays,
            self.constitution,
            output or self.output,
        )

    def role_bundle(self, output: Path | None = None) -> dict[str, Any]:
        root = output or self.output
        return json.loads((root / "ROLE_BUNDLE.json").read_text(encoding="utf-8"))

    def fab_handoff(self, output: Path | None = None) -> dict[str, Any]:
        root = output or self.output
        return json.loads((root / "FAB_HANDOFF.json").read_text(encoding="utf-8"))

    def test_builds_five_distinct_roles_and_fab_handoff(self) -> None:
        receipt = self.build()
        bundle = self.role_bundle()
        handoff = self.fab_handoff()
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(bundle["role_count"], 5)
        self.assertEqual(bundle["role_order"], EXPECTED_ROLES)
        self.assertEqual([row["id"] for row in bundle["roles"]], EXPECTED_ROLES)
        self.assertEqual(handoff["target_system"], "Essential Attention")
        self.assertEqual(handoff["source_role"], "planner_program")
        self.assertEqual(handoff["affected_actor_role"], "resident")

    def test_every_role_changes_all_governed_semantics(self) -> None:
        self.build()
        roles = self.role_bundle()["roles"]
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
            values = [
                json.dumps(row[field], sort_keys=True, separators=(",", ":"))
                for row in roles
            ]
            self.assertEqual(len(values), len(set(values)), field)

    def test_one_place_and_source_run_are_retained(self) -> None:
        self.build()
        bundle = self.role_bundle()
        self.assertEqual(
            {row["place_id"] for row in bundle["roles"]},
            {"mw-public-test"},
        )
        self.assertEqual(
            {row["source_run_id"] for row in bundle["roles"]},
            {"source-run-test"},
        )

    def test_all_apertures_and_overlays_are_covered(self) -> None:
        self.build()
        bundle = self.role_bundle()
        self.assertEqual(bundle["aperture_coverage"], EXPECTED_APERTURES)
        self.assertEqual(bundle["overlay_coverage"], EXPECTED_OVERLAYS)

    def test_degraded_map_only_and_missing_states_remain_visible(self) -> None:
        self.build()
        roles = self.role_bundle()["roles"]
        planner = next(row for row in roles if row["id"] == "planner_program")
        crew = next(row for row in roles if row["id"] == "crew_steward")
        self.assertEqual(planner["state"], "held_missing_evidence")
        self.assertIn("airnow", planner["evidence"]["unavailable_source_ids"])
        self.assertIn("firms", planner["evidence"]["unavailable_source_ids"])
        self.assertEqual(planner["evidence"]["source_state_counts"]["skipped_missing_credential"], 2)
        self.assertIn("access", crew["evidence"]["map_only_overlay_ids"])

    def test_private_or_credential_key_is_rejected(self) -> None:
        path = self.public / "PUBLIC_DATA.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["place"]["street_address"] = "private value"
        write_json(path, value)
        with self.assertRaisesRegex(builder.RoleError, "prohibited keys"):
            self.build()

    def test_non_none_public_effect_is_rejected(self) -> None:
        path = self.overlays / "BUILD_RECEIPT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["public_effect"] = "public"
        write_json(path, value)
        with self.assertRaisesRegex(builder.RoleError, "public effect"):
            self.build()

    def test_constitutional_count_effect_is_rejected(self) -> None:
        path = self.apertures / "BUILD_RECEIPT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["constitutional_count_effect"] = "closed_task"
        write_json(path, value)
        with self.assertRaisesRegex(builder.RoleError, "constitutional count"):
            self.build()

    def test_unknown_aperture_reference_is_rejected(self) -> None:
        value = json.loads(self.contract.read_text(encoding="utf-8"))
        value["roles"][0]["aperture_ids"].append("unknown_aperture")
        write_json(self.contract, value)
        with self.assertRaisesRegex(builder.RoleError, "unknown apertures"):
            self.build()

    def test_unknown_overlay_reference_is_rejected(self) -> None:
        value = json.loads(self.contract.read_text(encoding="utf-8"))
        value["roles"][0]["overlay_ids"].append("unknown_overlay")
        write_json(self.contract, value)
        with self.assertRaisesRegex(builder.RoleError, "unknown overlays"):
            self.build()

    def test_self_handoff_is_rejected(self) -> None:
        value = json.loads(self.contract.read_text(encoding="utf-8"))
        value["roles"][0]["handoff_to"].append("resident")
        write_json(self.contract, value)
        with self.assertRaisesRegex(builder.RoleError, "cannot hand off to itself"):
            self.build()

    def test_label_only_role_difference_is_rejected(self) -> None:
        value = json.loads(self.contract.read_text(encoding="utf-8"))
        value["roles"][1]["operating_purpose"] = value["roles"][0]["operating_purpose"]
        write_json(self.contract, value)
        with self.assertRaisesRegex(builder.RoleError, "distinct operating_purpose"):
            self.build()

    def test_source_run_drift_is_rejected(self) -> None:
        path = self.overlays / "OVERLAY_BUNDLE.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["source_run_id"] = "different-run"
        write_json(path, value)
        with self.assertRaisesRegex(builder.RoleError, "source run drifted"):
            self.build()

    def test_every_export_preserves_no_effect_and_no_release(self) -> None:
        self.build()
        for role in self.role_bundle()["roles"]:
            self.assertEqual(role["export"]["external_effect"], "none")
            self.assertEqual(role["export"]["release_state"], "not_authorized")
            self.assertEqual(role["public_effect"], "none")
            self.assertEqual(role["constitutional_count_effect"], "none")

    def test_fab_handoff_preserves_refusal_appeal_and_firewall(self) -> None:
        self.build()
        handoff = self.fab_handoff()
        self.assertIn("refuse", handoff["proposal"]["refusal_and_appeal"].lower())
        self.assertIn("appeal", handoff["proposal"]["refusal_and_appeal"].lower())
        self.assertEqual(handoff["proposal"]["execution_state"], "not_authorized")
        self.assertEqual(handoff["proposal"]["eligibility_state"], "not_determined")
        self.assertEqual(handoff["effect_firewall"]["external_effect"], "none")
        self.assertEqual(handoff["effect_firewall"]["insurance"], "prohibited")
        self.assertEqual(handoff["effect_firewall"]["enforcement"], "prohibited")

    def test_build_is_deterministic_for_same_inputs(self) -> None:
        first = self.roles / "out-first"
        second = self.roles / "out-second"
        first_receipt = self.build(first)
        second_receipt = self.build(second)
        self.assertEqual(first_receipt["payload_sha256"], second_receipt["payload_sha256"])
        for name in ("ROLE_BUNDLE.json", "FAB_HANDOFF.json", "BUILD_RECEIPT.json"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
