from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_release_control as release  # noqa: E402
import replay_p9_workflow as replay  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class ReleaseControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.control = self.repo / "manzanita-next/release-control"
        self.control.mkdir(parents=True)
        shutil.copy2(ROOT / "RELEASE_CONTRACT.json", self.control / "RELEASE_CONTRACT.json")
        shutil.copy2(
            ROOT / "EXTERNAL_CAMPAIGN_LEDGER.json",
            self.control / "EXTERNAL_CAMPAIGN_LEDGER.json",
        )
        self.output = self.control / "out"
        self._write_candidate()
        self._write_rollback()
        self._write_evidence()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_candidate(self) -> None:
        site = self.repo / "manzanita-next/experience/out/site"
        (site / "assets").mkdir(parents=True)
        (site / "index.html").write_text(
            "<!doctype html><html lang='en'><title>Manzanita candidate</title></html>\n",
            encoding="utf-8",
        )
        (site / "style.css").write_text("body { color: #111; }\n", encoding="utf-8")
        (site / "app.js").write_text("document.title = 'Manzanita candidate';\n", encoding="utf-8")
        (site / "experience-data.js").write_text(
            "window.__MANZANITA_WHOLE_EXPERIENCE__ = {};\n",
            encoding="utf-8",
        )
        (site / "assets/base-imagery.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    def _write_rollback(self) -> None:
        rollback = self.repo / "manzanita"
        (rollback / "assets").mkdir(parents=True)
        (rollback / "index.html").write_text(
            "<!doctype html><html lang='en'><title>Historical donor</title></html>\n",
            encoding="utf-8",
        )
        (rollback / "style.css").write_text("body { color: #222; }\n", encoding="utf-8")
        (rollback / "app.js").write_text("document.title = 'Historical donor';\n", encoding="utf-8")
        (rollback / "assets/place.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")

    def _write_evidence(self) -> None:
        experience = {
            "schema": "axm-tools/manzanita-whole-experience-data@1",
            "place": {"id": "mw-public-test", "public_safe": True},
            "source_run_id": "source-run-test",
            "apertures": [{"id": f"a-{index}"} for index in range(7)],
            "overlays": [{"id": f"o-{index}"} for index in range(8)],
            "roles": [{"id": f"r-{index}"} for index in range(5)],
            "payload_sha256": "1" * 64,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "release_effect": "none",
        }
        write_json(
            self.repo / "manzanita-next/experience/out/EXPERIENCE_DATA.json",
            experience,
        )
        write_json(
            self.repo / "manzanita-next/experience/out/BUILD_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-whole-experience-build@1",
                "result": "PASS",
                "payload_sha256": "2" * 64,
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "release_effect": "none",
            },
        )
        write_json(
            self.repo / "manzanita-next/experience/out/browser/BROWSER_CAMPAIGN.json",
            {
                "schema": "axm-tools/manzanita-whole-experience-browser-campaign@1",
                "result": "PASS",
                "console_errors": [],
                "page_errors": [],
                "external_requests": [],
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "release_effect": "none",
            },
        )
        p8_campaigns = [
            {"id": f"campaign-{index:02d}", "result": "PASS"}
            for index in range(19)
        ]
        write_json(
            self.repo / "manzanita-next/qualification/out/QUALIFICATION_REPORT.json",
            {
                "schema": "axm-tools/manzanita-resilience-qualification@1",
                "result": "PASS",
                "campaign_count": 19,
                "campaigns": p8_campaigns,
                "physical_campaigns_performed": False,
                "real_assistive_technology_claim": False,
                "real_device_claim": False,
                "actual_network_claim": False,
                "private_projection_claim": False,
                "credentialed_provider_claim": False,
                "field_operation_claim": False,
                "payload_sha256": "3" * 64,
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "release_effect": "none",
            },
        )
        write_json(
            self.repo / "manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-review-board-receipt@1",
                "result": "PASS",
                "outcome": "admit_with_holds",
                "open_vetoes": [],
                "open_critical_or_high_defects": [],
                "release_effect": "internal_candidate_only",
                "constitutional_count_effect": "none",
                "payload_sha256": "4" * 64,
            },
        )
        p9_register = {
            "schema": "axm-tools/manzanita-estate-parity-register@1",
            "surface_count": 10,
            "component_count": 104,
            "uncovered_surfaces": [],
            "unknown_components": [],
            "successor_candidate": {
                "state": "qualified_internal_candidate",
                "campaign_count": 19,
                "public_release_authorized": False,
            },
            "payload_sha256": "5" * 64,
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "release_effect": "none",
        }
        write_json(
            self.repo / "manzanita-next/parity/out/PARITY_REGISTER.json",
            p9_register,
        )
        write_json(
            self.repo / "manzanita-next/parity/out/BUILD_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-estate-parity-build@1",
                "result": "PASS",
                "payload_sha256": "6" * 64,
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "release_effect": "none",
            },
        )
        write_json(
            self.repo / "manzanita-next/parity/out/BOARD_DECISION_RECEIPT.json",
            {
                "schema": "axm-tools/manzanita-review-board-receipt@1",
                "result": "PASS",
                "outcome": "admit_with_holds",
                "open_vetoes": [],
                "open_critical_or_high_defects": [],
                "release_effect": "internal_candidate_only",
                "constitutional_count_effect": "none",
                "payload_sha256": "7" * 64,
            },
        )

    def build(self, output: Path | None = None) -> dict:
        return release.build(
            self.repo,
            Path("manzanita-next/release-control/RELEASE_CONTRACT.json"),
            Path("manzanita-next/release-control/EXTERNAL_CAMPAIGN_LEDGER.json"),
            output or Path("manzanita-next/release-control/out"),
        )

    def test_builds_exact_internal_candidate_and_preserves_release_hold(self) -> None:
        receipt = self.build()
        manifest = json.loads((self.output / "package/RELEASE_MANIFEST.json").read_text())
        decision = json.loads((self.output / "RELEASE_DECISION.json").read_text())
        continuity = json.loads((self.output / "CONTINUITY_RECEIPT.json").read_text())
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["release_state"], "HOLD")
        self.assertEqual(
            receipt["automated_candidate_state"],
            "QUALIFIED_INTERNAL_RELEASE_CANDIDATE",
        )
        self.assertFalse(receipt["public_release_authorized"])
        self.assertEqual(receipt["blocking_campaign_count"], 10)
        self.assertEqual(decision["state"], "HOLD")
        self.assertEqual(decision["blocking_campaign_count"], 10)
        self.assertEqual(continuity["result"], "PASS")
        self.assertEqual(continuity["release_decision_state"], "HOLD")
        self.assertFalse(continuity["public_endpoint_claim"])
        self.assertFalse(continuity["real_deployed_rollback_claim"])
        self.assertFalse(continuity["independent_cold_successor_claim"])
        self.assertGreater(manifest["candidate_file_count"], 0)
        self.assertGreater(manifest["rollback_file_count"], 0)
        self.assertEqual(manifest["evidence_file_count"], 10)
        self.assertFalse(manifest["public_release_authorized"])
        self.assertEqual(manifest["public_effect"], "none")
        self.assertEqual(manifest["constitutional_count_effect"], "none")

    def test_archive_and_receipts_are_deterministic(self) -> None:
        first_root = Path("manzanita-next/release-control/out-first")
        second_root = Path("manzanita-next/release-control/out-second")
        first = self.build(first_root)
        second = self.build(second_root)
        first_path = self.repo / first_root
        second_path = self.repo / second_root
        self.assertEqual(first["archive"]["sha256"], second["archive"]["sha256"])
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(
            (first_path / "package/RELEASE_MANIFEST.json").read_bytes(),
            (second_path / "package/RELEASE_MANIFEST.json").read_bytes(),
        )
        self.assertEqual(
            (first_path / "RELEASE_DECISION.json").read_bytes(),
            (second_path / "RELEASE_DECISION.json").read_bytes(),
        )

    def test_portable_archive_has_safe_unique_paths(self) -> None:
        self.build()
        archive_path = self.output / "MANZANITA_INTERNAL_RELEASE_CANDIDATE.zip"
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertIn("RELEASE_MANIFEST.json", names)
            self.assertIn("VERIFY_RELEASE.py", names)
            for name in names:
                self.assertFalse(Path(name).is_absolute())
                self.assertNotIn("..", Path(name).parts)

    def test_candidate_tamper_is_detected(self) -> None:
        self.build()
        extracted = self.output / "reimported/candidate"
        target = extracted / "index.html"
        target.write_text("tampered", encoding="utf-8")
        manifest = json.loads((self.output / "reimported/RELEASE_MANIFEST.json").read_text())
        rows = [
            {**row, "path": row["path"].removeprefix("candidate/")}
            for row in manifest["files"]
            if row["path"].startswith("candidate/")
        ]
        with self.assertRaisesRegex(
            release.ReleaseControlError,
            "Byte count drift|SHA-256 drift",
        ):
            release.verify_rows(extracted, rows)

    def test_private_key_in_evidence_is_rejected(self) -> None:
        path = self.repo / "manzanita-next/parity/out/PARITY_REGISTER.json"
        value = json.loads(path.read_text())
        value["resident_name"] = "private value"
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseControlError, "prohibited keys"):
            self.build()

    def test_public_effect_in_experience_is_rejected(self) -> None:
        path = self.repo / "manzanita-next/experience/out/EXPERIENCE_DATA.json"
        value = json.loads(path.read_text())
        value["public_effect"] = "public"
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseControlError, "public effect"):
            self.build()

    def test_failed_p8_campaign_is_rejected(self) -> None:
        path = self.repo / "manzanita-next/qualification/out/QUALIFICATION_REPORT.json"
        value = json.loads(path.read_text())
        value["campaigns"][3]["result"] = "FAIL"
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseControlError, "P8 campaign"):
            self.build()

    def test_uncovered_p9_surface_is_rejected(self) -> None:
        path = self.repo / "manzanita-next/parity/out/PARITY_REGISTER.json"
        value = json.loads(path.read_text())
        value["uncovered_surfaces"] = ["missing-surface"]
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseControlError, "uncovered surfaces"):
            self.build()

    def test_rollback_simulation_ends_on_historical_donor(self) -> None:
        self.build()
        continuity = json.loads((self.output / "CONTINUITY_RECEIPT.json").read_text())
        rollback = continuity["rollback_simulation"]
        self.assertEqual(rollback["result"], "PASS")
        self.assertEqual(rollback["active_after_simulation"], "rollback")
        self.assertFalse(rollback["public_deployment_claim"])
        self.assertFalse(rollback["deployed_rollback_claim"])
        self.assertEqual(
            rollback["rollback_manifest_sha256"],
            continuity["rollback_served_byte_proof"]["manifest_sha256"],
        )

    def test_isolated_successor_uses_no_repository_import_or_private_credential(self) -> None:
        self.build()
        continuity = json.loads((self.output / "CONTINUITY_RECEIPT.json").read_text())
        cold = continuity["isolated_same_runner_successor"]
        self.assertEqual(cold["result"], "PASS")
        self.assertEqual(cold["process_isolation"], "python_-I")
        self.assertFalse(cold["repository_imports"])
        self.assertFalse(cold["private_credentials"])
        self.assertFalse(cold["independent_operator_claim"])
        self.assertFalse(cold["independent_machine_claim"])
        self.assertFalse(cold["independent_archive_claim"])

    def test_all_external_campaigns_can_reach_review_without_self_authorizing_release(self) -> None:
        contract = json.loads((self.control / "RELEASE_CONTRACT.json").read_text())
        ledger = json.loads((self.control / "EXTERNAL_CAMPAIGN_LEDGER.json").read_text())
        for row in ledger["campaigns"]:
            row.update(
                {
                    "state": "passed",
                    "operator": "accountable operator",
                    "venue": "actual venue",
                    "procedure": "versioned real campaign procedure",
                    "evidence_receipts": [f"receipt:{row['id']}"],
                    "acceptance": "Campaign acceptance met",
                    "failure_disposition": "No unresolved failure",
                }
            )
        automated = {
            "archive_reimport": {"result": "PASS"},
            "isolated_same_runner_successor": {"result": "PASS"},
            "local_candidate_served_bytes": {"result": "PASS"},
            "local_rollback_served_bytes": {"result": "PASS"},
            "atomic_local_rollback": {"result": "PASS"},
        }
        decision = release.release_decision(contract, ledger, automated)
        self.assertEqual(decision["state"], "READY_FOR_PUBLIC_RELEASE_REVIEW")
        self.assertEqual(decision["blocking_campaigns"], [])
        self.assertFalse(decision["public_release_authorized"])

    def test_replay_selects_exact_p9_run_blocks(self) -> None:
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
        self.assertEqual(
            [row["name"] for row in selected],
            list(replay.REQUIRED_STEP_NAMES),
        )
        script = replay.render_script(selected)
        self.assertIn("Audit the exact estate reopening ledger", script)
        self.assertIn("Run the contained multidisciplinary P9 review", script)

    def test_replay_rejects_missing_p9_step(self) -> None:
        workflow = {
            "jobs": {
                "qualify": {
                    "steps": [
                        {"name": replay.REQUIRED_STEP_NAMES[0], "run": "echo only"}
                    ]
                }
            }
        }
        with self.assertRaisesRegex(replay.ReplayError, "one P9 qualification job|missing"):
            replay.select_steps(workflow)


if __name__ == "__main__":
    unittest.main()
