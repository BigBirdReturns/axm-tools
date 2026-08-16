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

APERTURES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APERTURES_ROOT))

import build_apertures as builder  # noqa: E402

EXPECTED_APERTURES = [
    "plant",
    "household",
    "property",
    "street",
    "neighborhood",
    "region",
    "stewardship",
]
SOURCE_IDS = [
    "nws_points",
    "nws_forecast",
    "nws_forecast_hourly",
    "nws_stations",
    "nws_observation",
    "nws_alerts",
    "airnow",
    "calfire_incidents",
    "calfire_incidents_normalized",
    "firms",
    "usgs_imagery",
    "usgs_3dep_hillshade",
    "usgs_water_sites",
    "usgs_water_iv",
    "osm_overpass",
    "google_street_view",
    "mapillary",
    "kartaview_coverage",
    "kartaview",
    "panoramax",
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ApertureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.apertures = self.repo / "manzanita-next" / "apertures"
        self.public_demo = self.repo / "manzanita-next" / "public-demo" / "out"
        self.constitution_path = self.repo / "manzanita-next" / "design-system" / "CONSTITUTION.json"
        self.contract_path = self.apertures / "APERTURE_CONTRACT.json"
        self.authored_path = self.apertures / "AUTHORED_DEMO.json"
        self.output = self.apertures / "out"

        self.apertures.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(APERTURES_ROOT / "APERTURE_CONTRACT.json", self.contract_path)
        shutil.copyfile(APERTURES_ROOT / "AUTHORED_DEMO.json", self.authored_path)
        write_json(
            self.constitution_path,
            {
                "schema": "axm-tools/manzanita-design-constitution@1",
                "version": "1.0.0",
            },
        )
        self._write_public_demo()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _source_row(self, source_id: str, state: str = "ok") -> dict[str, Any]:
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

    def _write_public_demo(self) -> None:
        states = {
            "google_street_view": "skipped_missing_credential",
            "mapillary": "skipped_missing_credential",
            "airnow": "skipped_missing_credential",
            "firms": "skipped_missing_credential",
            "kartaview_coverage": "empty",
            "kartaview": "empty",
            "panoramax": "empty",
        }
        sources = [self._source_row(source_id, states.get(source_id, "ok")) for source_id in SOURCE_IDS]
        write_json(
            self.public_demo / "PUBLIC_DATA.json",
            {
                "schema": "axm-tools/manzanita-public-demo-data@1",
                "build_id": "mw-public-test-source-run-test",
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
                "sources": sources,
                "views": {},
                "actors": {},
                "adverse_action_boundary": {},
                "claim_boundary": "Public-safe test dossier only.",
            },
        )
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
                "release_effect": "none",
                "constitutional_count_effect": "none",
                "payload_sha256": "3" * 64,
            },
        )

    def build(self, output: Path | None = None) -> dict[str, Any]:
        return builder.build(
            self.repo,
            self.contract_path,
            self.authored_path,
            self.public_demo,
            self.constitution_path,
            output or self.output,
        )

    def test_contract_has_seven_distinct_operating_apertures(self) -> None:
        contract = json.loads(self.contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], "axm-tools/manzanita-seven-aperture-contract@1")
        self.assertEqual(contract["task_reference"], "JDB99-013")
        self.assertEqual(contract["object"]["public_effect"], "none")
        self.assertEqual(contract["object"]["constitutional_count_effect"], "none")
        rows = contract["apertures"]
        self.assertEqual([row["id"] for row in rows], EXPECTED_APERTURES)
        self.assertEqual([row["order"] for row in rows], list(range(1, 8)))
        for field in (
            "object_class",
            "geometry_id",
            "reading",
            "safe_action",
            "authority",
            "acceptance",
            "handoff",
            "prohibited_consequence",
        ):
            self.assertEqual(len({row[field] for row in rows}), 7, field)
        adverse = " ".join(contract["adverse_action_boundary"]["prohibited_uses"]).lower()
        for term in ("insurance", "property", "evacuation", "field entry", "public deployment"):
            self.assertIn(term, adverse)

    def test_authored_cartridge_is_public_safe_and_explicit(self) -> None:
        authored = json.loads(self.authored_path.read_text(encoding="utf-8"))
        self.assertEqual(authored["schema"], "axm-tools/manzanita-authored-aperture-demo@1")
        self.assertTrue(authored["public_safe"])
        self.assertFalse(authored["private_household"])
        self.assertEqual(set(authored["records"]), {"plant", "household", "stewardship"})
        records = [row for rows in authored["records"].values() for row in rows]
        self.assertEqual(len(records), 6)
        self.assertEqual(len({row["id"] for row in records}), 6)
        self.assertTrue(all(row["state"] == "authored" for row in records))
        serialized = json.dumps(authored).lower()
        for term in ("not observations", "not a private record", "no real hotspot"):
            self.assertIn(term, serialized)

    def test_build_emits_one_place_and_seven_distinct_apertures(self) -> None:
        receipt = self.build()
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["public_effect"], "none")
        self.assertEqual(receipt["constitutional_count_effect"], "none")
        bundle = json.loads((self.output / "APERTURE_BUNDLE.json").read_text(encoding="utf-8"))
        self.assertEqual(bundle["schema"], "axm-tools/manzanita-seven-aperture-bundle@1")
        self.assertEqual(bundle["aperture_count"], 7)
        self.assertEqual(bundle["aperture_order"], EXPECTED_APERTURES)
        self.assertEqual({row["place_id"] for row in bundle["apertures"]}, {"mw-public-test"})
        self.assertEqual({row["source_run_id"] for row in bundle["apertures"]}, {"source-run-test"})
        for field in (
            "object_class",
            "reading",
            "safe_action",
            "authority",
            "acceptance",
            "handoff",
            "prohibited_consequence",
        ):
            self.assertEqual(len({row[field] for row in bundle["apertures"]}), 7, field)
        self.assertEqual(len({row["geometry"]["id"] for row in bundle["apertures"]}), 7)
        self.assertEqual(len({row["geometry"]["path"] for row in bundle["apertures"]}), 7)
        self.assertTrue(all(row["evidence_count"] >= 2 for row in bundle["apertures"]))
        self.assertEqual(bundle["apertures"][0]["parent_aperture"], None)
        self.assertEqual(bundle["apertures"][1]["parent_aperture"], "plant")
        self.assertEqual(bundle["apertures"][-1]["parent_aperture"], "region")
        self.assertEqual(bundle["public_effect"], "none")
        self.assertEqual(bundle["constitutional_count_effect"], "none")
        self.assertEqual(len(bundle["payload_sha256"]), 64)

    def test_source_and_authored_evidence_remain_distinct(self) -> None:
        self.build()
        bundle = json.loads((self.output / "APERTURE_BUNDLE.json").read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in bundle["apertures"]}
        plant = by_id["plant"]
        property_aperture = by_id["property"]
        street = by_id["street"]
        stewardship = by_id["stewardship"]
        self.assertEqual({row["state"] for row in plant["evidence"]}, {"authored"})
        self.assertEqual({row["evidence_class"] for row in property_aperture["evidence"]}, {"public_source"})
        self.assertIn("skipped_missing_credential", {row["state"] for row in street["evidence"]})
        self.assertEqual({row["state"] for row in stewardship["evidence"]}, {"authored"})
        for row in plant["evidence"] + stewardship["evidence"]:
            self.assertIn("demonstration", row["claim_scope"].lower())
            self.assertEqual(row["attribution"], "Manzanita design integrator")

    def test_missing_registered_source_becomes_unknown_evidence(self) -> None:
        public_data_path = self.public_demo / "PUBLIC_DATA.json"
        public_data = json.loads(public_data_path.read_text(encoding="utf-8"))
        public_data["sources"] = [row for row in public_data["sources"] if row["id"] != "osm_overpass"]
        write_json(public_data_path, public_data)
        self.build()
        bundle = json.loads((self.output / "APERTURE_BUNDLE.json").read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in bundle["apertures"]}
        for aperture_id in ("property", "street", "neighborhood"):
            aperture = by_id[aperture_id]
            self.assertIn("osm_overpass", aperture["missing_source_ids"])
            missing = next(row for row in aperture["evidence"] if row["id"] == "osm_overpass")
            self.assertEqual(missing["state"], "unknown")
            self.assertIn("no substantive claim", missing["claim_scope"].lower())

    def test_missing_authored_record_is_a_hard_failure(self) -> None:
        authored = json.loads(self.authored_path.read_text(encoding="utf-8"))
        authored["records"]["plant"] = authored["records"]["plant"][1:]
        write_json(self.authored_path, authored)
        with self.assertRaisesRegex(builder.ApertureError, "Missing authored record"):
            self.build()

    def test_private_or_credential_key_is_rejected(self) -> None:
        public_data_path = self.public_demo / "PUBLIC_DATA.json"
        public_data = json.loads(public_data_path.read_text(encoding="utf-8"))
        public_data["place"]["street_address"] = "private value"
        write_json(public_data_path, public_data)
        with self.assertRaisesRegex(builder.ApertureError, "prohibited keys"):
            self.build()

    def test_public_projection_place_identity_mismatch_is_rejected(self) -> None:
        projection_path = self.public_demo / "PUBLIC_PROJECTION_RECEIPT.json"
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        projection["place_id"] = "different-place"
        write_json(projection_path, projection)
        with self.assertRaisesRegex(builder.ApertureError, "place identity disagree"):
            self.build()

    def test_duplicate_geometry_path_is_rejected(self) -> None:
        original = copy.deepcopy(builder.GEOMETRY)
        try:
            builder.GEOMETRY["household"] = copy.deepcopy(builder.GEOMETRY["plant"])
            with self.assertRaisesRegex(builder.ApertureError, "distinct path"):
                self.build()
        finally:
            builder.GEOMETRY.clear()
            builder.GEOMETRY.update(original)

    def test_build_is_deterministic_for_same_inputs(self) -> None:
        first_output = self.apertures / "out-first"
        second_output = self.apertures / "out-second"
        first = self.build(first_output)
        second = self.build(second_output)
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(first["bundle"]["payload_sha256"], second["bundle"]["payload_sha256"])
        self.assertEqual(
            (first_output / "APERTURE_BUNDLE.json").read_bytes(),
            (second_output / "APERTURE_BUNDLE.json").read_bytes(),
        )
        self.assertEqual(file_sha(first_output / "BUILD_RECEIPT.json"), file_sha(second_output / "BUILD_RECEIPT.json"))


if __name__ == "__main__":
    unittest.main()
