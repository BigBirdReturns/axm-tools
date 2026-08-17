from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import replay_p7_workflow as replay  # noqa: E402
import run_qualification as qualify  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def synthetic_data() -> dict:
    apertures = [
        {"id": name, "state": "ok", "reading": f"Reading {name}"}
        for name in ("plant", "household", "property", "street", "neighborhood", "region", "stewardship")
    ]
    overlays = [{"id": name, "state": "ok"} for name in ("care", "shade", "water", "heat", "air", "fire", "access", "assistance")]
    roles = [{"id": name, "label": name, "state": "ok"} for name in ("resident", "nursery_grower", "crew_steward", "planner_program", "successor")]
    data = {
        "schema": qualify.DATA_SCHEMA,
        "contract_id": "M99-WHOLE-EXPERIENCE-001",
        "contract_version": "1.0.0",
        "experience_id": "fixture-whole-experience",
        "place": {"id": "fixture-place", "label": "Fixture", "public_safe": True},
        "source_run_id": "fixture-run",
        "donor_digests": {"public_projection": "a" * 64},
        "aperture_order": [row["id"] for row in apertures],
        "apertures": apertures,
        "overlay_order": [row["id"] for row in overlays],
        "overlays": overlays,
        "role_order": [row["id"] for row in roles],
        "roles": roles,
        "source_summary": {
            "source_count": 2,
            "state_counts": {"ok": 1, "empty": 1},
            "sources": [
                {"id": "source-a", "label": "A", "state": "ok", "source_time": "2026-08-16T00:00:00Z", "error": None},
                {"id": "source-b", "label": "B", "state": "empty", "source_time": None, "error": "No coverage"},
            ],
        },
        "scene": {"selected_mode": "map_only"},
        "registration": {"admission_state": "registration_proposal"},
        "fab_handoff": {"release_state": "not_authorized"},
        "export_law": {"private_record_transfer": "prohibited"},
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
    }
    data["payload_sha256"] = qualify.sha256_bytes(qualify.canonical_bytes(data))
    return data


class QualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.contract = json.loads((ROOT / "QUALIFICATION_CONTRACT.json").read_text(encoding="utf-8"))
        self.data = synthetic_data()
        self.data_path = self.root / "EXPERIENCE_DATA.json"
        self.site = self.root / "site"
        (self.site / "assets").mkdir(parents=True)
        write_json(self.data_path, self.data)
        (self.site / "index.html").write_text(
            "<!doctype html><html lang='en'><head>"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'\">"
            "<link rel='stylesheet' href='style.css'><script src='experience-data.js' defer></script><script src='app.js' defer></script>"
            "</head><body><a class='skip-link' href='#main'>Skip</a><main id='main'></main></body></html>",
            encoding="utf-8",
        )
        (self.site / "style.css").write_text("button { min-height: 44px; }\n", encoding="utf-8")
        (self.site / "app.js").write_text("const escapeHTML = (value) => String(value);\n", encoding="utf-8")
        (self.site / "experience-data.js").write_text(qualify.experience_script(self.data), encoding="utf-8")
        (self.site / "assets/base-imagery.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_contract_has_nineteen_unique_campaigns(self) -> None:
        rows = self.contract["required_campaigns"]
        self.assertEqual(len(rows), 19)
        self.assertEqual(len(rows), len(set(rows)))
        for required in ("low_end_cpu", "offline_after_load", "stale_source", "provider_outage", "contradictory_source", "hostile_text", "export_reimport"):
            self.assertIn(required, rows)

    def test_static_integrity_accepts_bounded_site(self) -> None:
        receipt = qualify.static_integrity(self.site, self.data_path, self.contract)
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["site_file_count"], 5)
        self.assertEqual(len(receipt["manifest_sha256"]), 64)

    def test_static_integrity_rejects_runtime_fetch(self) -> None:
        (self.site / "app.js").write_text("const escapeHTML = String; fetch('/remote');\n", encoding="utf-8")
        with self.assertRaisesRegex(qualify.QualificationError, "network primitive"):
            qualify.static_integrity(self.site, self.data_path, self.contract)

    def test_static_integrity_rejects_csp_drift(self) -> None:
        index = (self.site / "index.html").read_text(encoding="utf-8").replace("connect-src 'none'", "connect-src 'self'")
        (self.site / "index.html").write_text(index, encoding="utf-8")
        with self.assertRaisesRegex(qualify.QualificationError, "CSP omits"):
            qualify.static_integrity(self.site, self.data_path, self.contract)

    def test_privacy_scan_rejects_private_key_name(self) -> None:
        data = copy.deepcopy(self.data)
        data["resident_name"] = "Private person"
        with self.assertRaisesRegex(qualify.QualificationError, "Private or credential keys"):
            qualify.privacy_secret_scan(self.site, data, self.contract)

    def test_secret_scan_rejects_high_confidence_token(self) -> None:
        (self.site / "app.js").write_text("const escapeHTML = String; const key = 'AKIAABCDEFGHIJKLMNOP';\n", encoding="utf-8")
        with self.assertRaisesRegex(qualify.QualificationError, "secret"):
            qualify.static_integrity(self.site, self.data_path, self.contract)

    def test_source_mutations_remain_distinct(self) -> None:
        states = {}
        for mode in ("stale_source", "provider_outage", "contradictory_source"):
            mutated = qualify.mutate_data(self.data, mode)
            states[mode] = set(mutated["source_summary"]["state_counts"])
            self.assertEqual(mutated["qualification_injection"]["authority"], "automated_test_only")
            self.assertEqual(mutated["qualification_injection"]["public_effect"], "none")
        self.assertIn("stale", states["stale_source"])
        self.assertIn("unavailable", states["provider_outage"])
        self.assertIn("contradictory", states["contradictory_source"])

    def test_hostile_data_serializes_as_literal_external_javascript(self) -> None:
        mutated = qualify.mutate_data(self.data, "hostile_text")
        script = qualify.experience_script(mutated)
        payload = json.loads(script.split("=", 1)[1].strip().removesuffix(";"))
        self.assertEqual(payload["roles"][0]["label"], qualify.HOSTILE_MARKER)
        self.assertIn("window.__MANZANITA_WHOLE_EXPERIENCE__", script)
        self.assertEqual(mutated["qualification_injection"]["release_effect"], "none")

    def test_snapshot_reimport_preserves_boundaries(self) -> None:
        snapshot = {
            "schema": qualify.SNAPSHOT_SCHEMA,
            "experience_id": self.data["experience_id"],
            "place": self.data["place"],
            "source_run_id": self.data["source_run_id"],
            "selected": {"aperture": "household", "overlay": "care", "role": "resident", "theme": "auto"},
            "donor_digests": self.data["donor_digests"],
            "export_law": {"private_record_transfer": "prohibited"},
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "release_state": "not_authorized",
        }
        receipt = qualify.verify_snapshot(snapshot, self.data)
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["release_state"], "not_authorized")

    def test_snapshot_reimport_rejects_unknown_role(self) -> None:
        snapshot = {
            "schema": qualify.SNAPSHOT_SCHEMA,
            "experience_id": self.data["experience_id"],
            "place": self.data["place"],
            "source_run_id": self.data["source_run_id"],
            "selected": {"aperture": "household", "overlay": "care", "role": "invented", "theme": "auto"},
            "donor_digests": self.data["donor_digests"],
            "export_law": {"private_record_transfer": "prohibited"},
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "release_state": "not_authorized",
        }
        with self.assertRaisesRegex(qualify.QualificationError, "role"):
            qualify.verify_snapshot(snapshot, self.data)

    def test_replay_selects_exact_canonical_p7_steps(self) -> None:
        workflow = {
            "jobs": {
                "qualify": {
                    "steps": [
                        {"name": name, "run": f"echo {index}"}
                        for index, name in enumerate(replay.REQUIRED_STEP_NAMES)
                    ]
                }
            }
        }
        selected = replay.select_steps(workflow)
        self.assertEqual([row["name"] for row in selected], list(replay.REQUIRED_STEP_NAMES))
        script = replay.render_script(selected)
        self.assertIn("P7 acquisition exit code", script)
        self.assertIn("Build the exact whole experience", script)

    def test_replay_rejects_missing_donor_step(self) -> None:
        workflow = {"jobs": {"qualify": {"steps": [{"name": replay.REQUIRED_STEP_NAMES[0], "run": "echo one"}]}}}
        with self.assertRaisesRegex(replay.ReplayError, "missing or duplicated"):
            replay.select_steps(workflow)


if __name__ == "__main__":
    unittest.main()
