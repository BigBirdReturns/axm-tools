from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from PIL import Image

PUBLIC_DEMO = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PUBLIC_DEMO))

import build_public_demo as builder  # noqa: E402

EXPECTED_VIEWS = {"place", "weather", "water", "fire"}
EXPECTED_ACTORS = {"visitor", "steward", "program_operator"}
EXPECTED_SOURCE_STATES = {
    "ok",
    "empty",
    "stale",
    "skipped_missing_credential",
    "rate_limited",
    "unavailable",
    "terms_blocked",
    "unknown",
}
REQUIRED_SOURCE_IDS = [
    "nws_points",
    "nws_forecast",
    "nws_forecast_hourly",
    "nws_stations",
    "nws_observation",
    "nws_alerts",
    "calfire_incidents",
    "calfire_incidents_normalized",
    "usgs_imagery",
    "usgs_3dep_hillshade",
    "usgs_water_sites",
    "usgs_water_iv",
    "osm_overpass",
    "kartaview_coverage",
    "kartaview",
    "panoramax",
    "airnow",
    "firms",
    "google_street_view",
    "mapillary",
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TemplateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.external: list[str] = []
        self.forms = 0
        self.buttons: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheets.append(values.get("href", ""))
        if tag == "form":
            self.forms += 1
        if tag == "button":
            self.buttons.append(values)
        for key in ("href", "src"):
            value = values.get(key, "")
            if value.startswith(("http://", "https://", "//")):
                self.external.append(value)


class PublicDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.public_demo = self.repo / "manzanita-next" / "public-demo"
        self.template = self.public_demo / "template"
        self.acquisition = self.repo / "manzanita-next" / "out"
        self.output = self.public_demo / "out"
        self.contract_path = self.public_demo / "PLACE_DEMO_CONTRACT.json"
        self.place_path = self.repo / "manzanita-next" / "config" / "place-demo.json"
        self.registry_path = self.repo / "manzanita-next" / "config" / "source-registry.json"
        self.constitution_path = self.repo / "manzanita-next" / "design-system" / "CONSTITUTION.json"

        self.public_demo.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PUBLIC_DEMO / "PLACE_DEMO_CONTRACT.json", self.contract_path)
        shutil.copytree(PUBLIC_DEMO / "template", self.template)
        write_json(
            self.place_path,
            {
                "schema": "manzanita-works/governed-place@1",
                "place_id": "mw-public-demo-test-001",
                "public_label": "Public Arboretum Test Place",
                "public_safe": True,
                "centroid": {"lat": 34.14325, "lon": -118.05501},
                "private_projection": {
                    "address": "must never enter output",
                    "resident_name": "must never enter output",
                },
            },
        )
        write_json(
            self.registry_path,
            {
                "schema": "manzanita-works/source-registry@1",
                "sources": [
                    {
                        "source_id": source_id,
                        "label": source_id.replace("_", " ").title(),
                        "attribution": f"Public attribution for {source_id}",
                        "license": "Public test terms",
                        "storage_policy": "Retain public test metadata",
                        "claim_scope": f"Bounded public test scope for {source_id}",
                    }
                    for source_id in REQUIRED_SOURCE_IDS
                ],
            },
        )
        write_json(
            self.constitution_path,
            {
                "schema": "axm-tools/manzanita-design-constitution@1",
                "version": "1.0.0",
                "materials": {
                    "semantic_tokens": [
                        {"id": "paper", "light": "#f2ecde", "dark": "#151713", "meaning": "field"},
                        {"id": "paper_alt", "light": "#e5dcc9", "dark": "#22251f", "meaning": "secondary field"},
                        {"id": "ink", "light": "#171a16", "dark": "#f0e8d8", "meaning": "text"},
                        {"id": "ink_muted", "light": "#555b50", "dark": "#b9b4a8", "meaning": "context"},
                        {"id": "bark", "light": "#9f3f2f", "dark": "#e77962", "meaning": "consequence"},
                        {"id": "leaf", "light": "#5c6b43", "dark": "#a7bb7d", "meaning": "living"},
                        {"id": "water", "light": "#2f6a78", "dark": "#79b3c0", "meaning": "source"},
                        {"id": "sun", "light": "#b66f1f", "dark": "#e6ad5f", "meaning": "heat"},
                        {"id": "uncertain", "light": "#726a5a", "dark": "#aaa18f", "meaning": "unknown"},
                        {"id": "failure", "light": "#7d2431", "dark": "#ff8792", "meaning": "failure"},
                    ]
                },
            },
        )
        self._make_acquisition()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_receipt(
        self,
        source_id: str,
        *,
        status: str,
        payload_path: str | None = None,
        source_time: str | None = "2026-08-16T00:00:00Z",
        error: str | None = None,
        max_age_seconds: int = 86400,
    ) -> None:
        payload_bytes = 0
        payload_sha = None
        if payload_path:
            path = self.acquisition / payload_path
            payload_bytes = path.stat().st_size
            payload_sha = sha256(path)
        write_json(
            self.acquisition / "receipts" / f"{source_id}.json",
            {
                "source_id": source_id,
                "status": status,
                "retrieval_id": f"{source_id}-test",
                "retrieved_at": "2026-08-16T00:00:00Z",
                "request_url": f"https://public.example.invalid/{source_id}",
                "http_status": 200 if status in {"ok", "empty"} else None,
                "payload_path": payload_path,
                "payload_bytes": payload_bytes,
                "payload_sha256": payload_sha,
                "source_time": source_time,
                "max_age_seconds": max_age_seconds,
                "source_attribution": f"Public attribution for {source_id}",
                "license": "Public test terms",
                "storage_policy": "Retain public test metadata",
                "claim_scope": f"Bounded public test scope for {source_id}",
                "error": error,
            },
        )

    def _payload(self, source_id: str, value: Any, suffix: str = ".json") -> str:
        relative = f"payloads/{source_id}{suffix}"
        path = self.acquisition / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if suffix in {".json", ".geojson"}:
            write_json(path, value)
        else:
            raise AssertionError("Binary payloads are created separately")
        return relative

    def _make_image(self, source_id: str) -> str:
        relative = f"payloads/{source_id}.png"
        path = self.acquisition / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (160, 100), "#8d9876")
        image.save(path, format="PNG")
        return relative

    def _make_acquisition(self) -> None:
        self.acquisition.mkdir(parents=True, exist_ok=True)
        write_json(
            self.acquisition / "manifest.json",
            {
                "schema": "manzanita-works/source-acquisition-manifest@1",
                "run_id": "synthetic-public-run-001",
                "generated_at": "2026-08-16T00:00:00Z",
                "place_id": "mw-public-demo-test-001",
            },
        )

        image_payload = self._make_image("usgs_imagery")
        hillshade_payload = self._make_image("usgs_3dep_hillshade")
        self._write_receipt("usgs_imagery", status="ok", payload_path=image_payload)
        self._write_receipt("usgs_3dep_hillshade", status="ok", payload_path=hillshade_payload)

        simple_payloads = {
            "nws_points": {"properties": {"gridId": "LOX"}},
            "nws_forecast": {
                "properties": {
                    "periods": [
                        {
                            "name": "Today",
                            "temperature": 82,
                            "temperatureUnit": "F",
                            "shortForecast": "Clear",
                            "detailedForecast": "Clear public test forecast.",
                        }
                    ]
                }
            },
            "nws_forecast_hourly": {"properties": {"periods": [{"temperature": 80}]}},
            "nws_stations": {"features": [{"id": "station-1"}]},
            "nws_observation": {
                "properties": {
                    "timestamp": "2026-08-16T00:00:00Z",
                    "temperature": {"value": 25},
                    "textDescription": "Clear",
                }
            },
            "nws_alerts": {"features": []},
            "calfire_incidents": {"type": "FeatureCollection", "features": [{"id": "public-feature"}]},
            "calfire_incidents_normalized": {"features": [{"id": "normalized-public-feature"}]},
            "usgs_water_sites": {"sites": [{"site": "public-monitor-1"}, {"site": "public-monitor-2"}]},
            "usgs_water_iv": {"value": {"timeSeries": [{"name": "public-series-1"}]}},
            "osm_overpass": {"elements": [{"type": "node"}, {"type": "way"}, {"type": "relation"}]},
        }
        for source_id, payload in simple_payloads.items():
            relative = self._payload(source_id, payload)
            self._write_receipt(source_id, status="ok", payload_path=relative)

        for source_id in ("kartaview_coverage", "kartaview", "panoramax"):
            relative = self._payload(source_id, {"features": []})
            self._write_receipt(source_id, status="empty", payload_path=relative)

        for source_id in ("airnow", "firms", "google_street_view", "mapillary"):
            self._write_receipt(
                source_id,
                status="skipped_missing_credential",
                error=f"{source_id.upper()}_CREDENTIAL is not configured",
                source_time=None,
                max_age_seconds=0,
            )

    def build(self, output: Path | None = None) -> dict[str, Any]:
        return builder.build(
            self.repo,
            self.contract_path,
            self.place_path,
            self.registry_path,
            self.constitution_path,
            self.template,
            self.acquisition,
            output or self.output,
        )

    def test_contract_has_complete_views_actors_and_boundaries(self) -> None:
        contract = json.loads(self.contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], "axm-tools/manzanita-public-demo-contract@1")
        self.assertEqual(contract["task_reference"], "JDB99-018")
        self.assertEqual(contract["object"]["public_effect"], "none")
        self.assertEqual(contract["object"]["constitutional_count_effect"], "none")
        self.assertEqual({row["id"] for row in contract["views"]}, EXPECTED_VIEWS)
        self.assertEqual({row["id"] for row in contract["actors"]}, EXPECTED_ACTORS)
        self.assertEqual({row["id"] for row in contract["source_states"]}, EXPECTED_SOURCE_STATES)
        for view in contract["views"]:
            for field in ("object", "safe_action", "authority", "prohibited_consequence"):
                self.assertGreaterEqual(len(view[field]), 20)
        adverse = " ".join(contract["adverse_action_boundary"]["prohibited_uses"]).lower()
        for term in ("insurance", "enforcement", "evacuation", "inspection", "household"):
            self.assertIn(term, adverse)

    def test_template_is_self_contained_read_only_and_accessible(self) -> None:
        parser = TemplateParser()
        html = (self.template / "index.html").read_text(encoding="utf-8")
        parser.feed(html)
        self.assertEqual(parser.external, [])
        self.assertEqual(parser.forms, 0)
        self.assertEqual(parser.scripts, ["demo-data.js", "app.js"])
        self.assertEqual(parser.stylesheets, ["tokens.css", "style.css"])
        required = {
            "place-instrument",
            "base-imagery",
            "field-svg",
            "source-rail-title",
            "metric-list",
            "actor-title",
            "failure-list",
            "projection-title",
        }
        self.assertTrue(required.issubset(parser.ids))
        self.assertEqual(len(parser.buttons), 10)
        for button in parser.buttons:
            self.assertEqual(button.get("type"), "button")
            self.assertIn(button.get("aria-pressed"), {"true", "false"})
        lower = html.lower()
        for phrase in ("public projection", "read-only", "no adverse action", "no insurance", "not deployed"):
            self.assertIn(phrase, lower)

    def test_builder_emits_public_safe_projection_and_receipts(self) -> None:
        receipt = self.build()
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["release_effect"], "none")
        self.assertEqual(receipt["constitutional_count_effect"], "none")
        self.assertTrue(receipt["site_manifest"])
        self.assertEqual(len(receipt["site_manifest_sha256"]), 64)

        public_data = json.loads((self.output / "PUBLIC_DATA.json").read_text(encoding="utf-8"))
        projection = json.loads((self.output / "PUBLIC_PROJECTION_RECEIPT.json").read_text(encoding="utf-8"))
        self.assertEqual(public_data["schema"], "axm-tools/manzanita-public-demo-data@1")
        self.assertEqual(public_data["place"]["id"], "mw-public-demo-test-001")
        self.assertEqual(public_data["place"]["latitude"], 34.1432)
        self.assertEqual(public_data["place"]["longitude"], -118.055)
        self.assertEqual(public_data["place"]["coordinate_precision_decimals"], 4)
        self.assertTrue(public_data["place"]["public_safe"])
        self.assertEqual(set(public_data["views"]), EXPECTED_VIEWS)
        self.assertEqual(set(public_data["actors"]), EXPECTED_ACTORS)
        self.assertEqual(len(public_data["sources"]), len(REQUIRED_SOURCE_IDS))
        self.assertEqual(public_data["source_state_counts"]["ok"], 13)
        self.assertEqual(public_data["source_state_counts"]["empty"], 3)
        self.assertEqual(public_data["source_state_counts"]["skipped_missing_credential"], 4)
        self.assertEqual(len(public_data["failures"]), 7)
        self.assertEqual(projection["result"], "PASS")
        self.assertEqual(projection["prohibited_keys_found"], [])
        self.assertEqual(projection["secret_scan"]["result"], "PASS")
        self.assertEqual(projection["secret_scan"]["high_confidence_findings"], [])

        serialized = json.dumps(public_data).lower()
        self.assertNotIn("must never enter output", serialized)
        self.assertNotIn("resident_name", serialized)
        self.assertNotIn("street_address", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("https://public.example.invalid", serialized)

    def test_builder_preserves_distinct_failure_states(self) -> None:
        self.build()
        public_data = json.loads((self.output / "PUBLIC_DATA.json").read_text(encoding="utf-8"))
        states = {row["id"]: row["state"] for row in public_data["sources"]}
        self.assertEqual(states["kartaview"], "empty")
        self.assertEqual(states["airnow"], "skipped_missing_credential")
        self.assertEqual(states["firms"], "skipped_missing_credential")
        self.assertEqual(states["usgs_imagery"], "ok")
        place_view = public_data["views"]["place"]
        fire_view = public_data["views"]["fire"]
        self.assertIn("google_street_view", place_view["source_ids"])
        self.assertIn("firms", fire_view["source_ids"])
        self.assertIn("insurance", fire_view["prohibited_consequence"].lower())
        fire_metrics = " ".join(
            f"{row['label']} {row['value']} {row['detail']}" for row in fire_view["metrics"]
        ).lower()
        self.assertIn("not a local threat count", fire_metrics)
        self.assertIn("not a confirmed incident", fire_metrics)

    def test_builder_copies_permitted_media_and_generates_tokens(self) -> None:
        self.build()
        site = self.output / "site"
        base = site / "assets" / "base-imagery.png"
        hillshade = site / "assets" / "hillshade.png"
        self.assertTrue(base.is_file())
        self.assertTrue(hillshade.is_file())
        self.assertEqual(sha256(base), sha256(self.acquisition / "payloads" / "usgs_imagery.png"))
        self.assertEqual(sha256(hillshade), sha256(self.acquisition / "payloads" / "usgs_3dep_hillshade.png"))
        tokens = (site / "tokens.css").read_text(encoding="utf-8")
        for token in ("paper", "paper-alt", "ink", "bark", "leaf", "water", "failure"):
            self.assertIn(f"--{token}:", tokens)
        data_script = (site / "demo-data.js").read_text(encoding="utf-8")
        self.assertTrue(data_script.startswith("window.__MANZANITA_PUBLIC_DEMO__"))
        self.assertNotIn("must never enter output", data_script)

    def test_build_is_deterministic_for_the_same_acquisition_bundle(self) -> None:
        first_output = self.public_demo / "out-first"
        second_output = self.public_demo / "out-second"
        first = self.build(first_output)
        second = self.build(second_output)
        self.assertEqual(first["site_manifest_sha256"], second["site_manifest_sha256"])
        self.assertEqual(first["public_projection_receipt"]["payload_sha256"], second["public_projection_receipt"]["payload_sha256"])
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(
            (first_output / "PUBLIC_DATA.json").read_bytes(),
            (second_output / "PUBLIC_DATA.json").read_bytes(),
        )

    def test_non_public_place_is_rejected(self) -> None:
        place = json.loads(self.place_path.read_text(encoding="utf-8"))
        place["public_safe"] = False
        write_json(self.place_path, place)
        with self.assertRaisesRegex(builder.BuildError, "not explicitly public-safe"):
            self.build()

    def test_prohibited_public_key_is_rejected(self) -> None:
        contract = json.loads(self.contract_path.read_text(encoding="utf-8"))
        altered = copy.deepcopy(contract)
        altered["actors"][0]["token"] = "not-a-real-secret-but-a-prohibited-field"
        write_json(self.contract_path, altered)
        with self.assertRaisesRegex(builder.BuildError, "prohibited keys"):
            self.build()

    def test_secret_scan_detects_high_confidence_credential_pattern(self) -> None:
        path = self.repo / "candidate.txt"
        path.write_text("AIza" + "A" * 34, encoding="utf-8")
        scan = builder.secret_scan([path])
        self.assertEqual(scan["result"], "FAIL")
        self.assertEqual(scan["high_confidence_findings"][0]["pattern"], "google_api_key")

    def test_receipt_payload_path_cannot_escape_acquisition_root(self) -> None:
        result = builder.receipt_payload_path(
            self.acquisition,
            {"payload_path": "../private-secret.json"},
        )
        self.assertIsNone(result)

    def test_stale_source_is_not_reported_as_current_ok(self) -> None:
        receipt_path = self.acquisition / "receipts" / "nws_observation.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["source_time"] = "2026-08-01T00:00:00Z"
        receipt["max_age_seconds"] = 900
        write_json(receipt_path, receipt)
        self.build()
        public_data = json.loads((self.output / "PUBLIC_DATA.json").read_text(encoding="utf-8"))
        states = {row["id"]: row["state"] for row in public_data["sources"]}
        self.assertEqual(states["nws_observation"], "stale")
        self.assertGreaterEqual(public_data["source_state_counts"]["stale"], 1)


if __name__ == "__main__":
    unittest.main()
