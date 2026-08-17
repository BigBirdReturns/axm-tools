from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

PARITY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PARITY_ROOT.parents[1]
sys.path.insert(0, str(PARITY_ROOT))

import build_parity as builder  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def surface(surface_id: str, resolution_status: str = "reopened") -> dict[str, Any]:
    gates = {
        "object_classification": "partial",
        "actors_authority": "partial",
        "source_custody": "partial",
        "mechanism_fidelity": "partial",
        "live_data_failure_states": "partial",
        "interaction_semantics": "partial",
        "visual_typography": "fail",
        "responsive_accessibility": "unknown",
        "negative_stress_offline": "partial",
        "continuity_export_succession": "partial",
        "provenance_rights_privacy": "partial",
        "qualification_receipts": "partial",
    }
    return {
        "id": surface_id,
        "class": "synthetic_surface",
        "paths": [f"products/{surface_id}"],
        "current_claim": f"{surface_id} is a bounded synthetic surface used only for deterministic parity tests.",
        "claim_evidence": [f"products/{surface_id}/README.md"],
        "resolution_status": resolution_status,
        "evidence_tier": "synthetic_direct_test",
        "actors": ["source owner", "release authority"],
        "mechanism": "The synthetic surface exposes one exact finding and one required asset for parity classification tests.",
        "gates": gates,
        "findings": [
            {
                "severity": "high",
                "title": "Synthetic parity finding remains deliberately open",
                "mechanism": "The test surface retains one unresolved mechanism so the parity register cannot confuse complete accounting with product completion.",
                "evidence": [f"products/{surface_id}/README.md"],
                "acceptance": "An exact source-linked receipt must resolve the synthetic finding before the source surface can become qualified.",
            }
        ],
        "assets_required": ["one source-linked synthetic acceptance receipt"],
        "next_gate": "Retain the source-specific finding and required asset without manufacturing completion.",
    }


class ParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir(parents=True)
        self.parity = self.repo / "manzanita-next/parity"
        self.backfill = self.repo / "resolution-backfill"
        self.output = self.parity / "out"

        contract = json.loads((PARITY_ROOT / "PARITY_CONTRACT.json").read_text(encoding="utf-8"))
        contract["expected_surface_count"] = 2
        contract["expected_component_count"] = 6
        write_json(self.parity / "PARITY_CONTRACT.json", contract)

        dispositions = json.loads((PARITY_ROOT / "SURFACE_DISPOSITIONS.json").read_text(encoding="utf-8"))
        dispositions["surfaces"] = [
            {
                "surface_id": "alpha",
                "disposition": "held",
                "relationship": "explicit_noninheritance",
                "reason": "Alpha remains an independently governed source product whose unresolved synthetic finding and required asset remain open.",
                "authority_owner": "Alpha's source-product release authority retains product, qualification, and public standing.",
                "acceptance": "Alpha may change state only through an exact source-linked amendment naming evidence, authority, unresolved holds, and release effect.",
            },
            {
                "surface_id": "manzanita",
                "disposition": "donor",
                "relationship": "historical_public_rollback_donor",
                "reason": "The synthetic Manzanita public route remains a historical rollback donor rather than the internally qualified successor candidate.",
                "authority_owner": "The historical route's source-product release authority retains its public and rollback standing.",
                "acceptance": "The donor relationship may change only through an exact public-byte, deployment, rollback, and release-authority campaign.",
            },
        ]
        write_json(self.parity / "SURFACE_DISPOSITIONS.json", dispositions)

        inventory = {
            "schema": builder.INVENTORY_SCHEMA,
            "generated_at": "2026-08-17T00:00:00Z",
            "base_ref": "main",
            "base_sha": "0" * 40,
            "policy": {},
            "donors": [],
            "surface_files": ["surfaces/alpha.json", "surfaces/manzanita.json"],
        }
        write_json(self.backfill / "inventory.json", inventory)
        write_json(self.backfill / "surfaces/alpha.json", surface("alpha"))
        write_json(self.backfill / "surfaces/manzanita.json", surface("manzanita"))
        schema_target = self.backfill / "contracts/surface.schema.json"
        schema_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            REPO_ROOT / "resolution-backfill/contracts/surface.schema.json",
            schema_target,
        )

        report = {
            "schema": builder.BACKFILL_REPORT_SCHEMA,
            "generated_at": "2026-08-17T00:00:00Z",
            "result": "PASS",
            "meaning": "PASS qualifies the completeness and honesty of the reopening ledger, not the remediation of the products it audits.",
            "base_ref": "main",
            "base_sha": "0" * 40,
            "head_sha": "1" * 40,
            "inventory_sha256": "2" * 64,
            "summary": {
                "surface_count": 2,
                "status_counts": {"reopened": 2},
                "gate_counts": {"partial": 18, "fail": 2, "unknown": 2, "not_applicable": 2},
                "finding_counts": {"high": 2},
                "asset_requirements": 2,
                "evidence_receipts": 4,
                "legacy_records": 1,
            },
            "surfaces": [],
            "errors": [],
        }
        qualification = {
            "schema": builder.BACKFILL_QUALIFICATION_SCHEMA,
            "qualified_at": "2026-08-17T00:00:00Z",
            "result": "PASS",
            "qualification_scope": "completeness, evidence addressability, and honesty of the estate-wide reopening ledger",
            "explicit_exclusion": "This result does not qualify any underlying product as remediated or complete.",
            "base_sha": "0" * 40,
            "head_sha": "1" * 40,
            "surface_count": 2,
            "qualified_surface_count": 0,
            "critical_findings": 0,
            "failed_gates": 2,
            "unknown_gates": 2,
            "artifacts": {},
        }
        write_json(self.backfill / "out/report.json", report)
        write_json(self.backfill / "out/qualification.json", qualification)

        p7 = {
            "schema": "axm-tools/manzanita-whole-experience-build@1",
            "result": "PASS",
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "release_effect": "none",
            "payload_sha256": "3" * 64,
        }
        write_json(self.repo / "manzanita-next/experience/out/BUILD_RECEIPT.json", p7)
        campaigns = [{"id": f"campaign-{index:02d}", "result": "PASS"} for index in range(19)]
        p8 = {
            "schema": builder.P8_REPORT_SCHEMA,
            "result": "PASS",
            "campaign_count": 19,
            "campaigns": campaigns,
            "physical_campaigns_performed": False,
            "real_assistive_technology_claim": False,
            "real_device_claim": False,
            "actual_network_claim": False,
            "private_projection_claim": False,
            "credentialed_provider_claim": False,
            "field_operation_claim": False,
            "retained_holds": ["Real campaigns remain open."],
            "public_effect": "none",
            "constitutional_count_effect": "none",
            "release_effect": "none",
            "payload_sha256": "4" * 64,
        }
        board = {
            "schema": builder.P8_BOARD_SCHEMA,
            "result": "PASS",
            "packet_id": "M99-RB-PKT-010",
            "decision_id": "M99-RB-DEC-010",
            "outcome": "admit_with_holds",
            "release_effect": "internal_candidate_only",
            "constitutional_count_effect": "none",
            "seat_count": 12,
            "open_vetoes": [],
            "open_critical_or_high_defects": [],
            "payload_sha256": "5" * 64,
        }
        write_json(self.repo / "manzanita-next/qualification/out/QUALIFICATION_REPORT.json", p8)
        write_json(self.repo / "manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json", board)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, output: Path | None = None) -> dict[str, Any]:
        return builder.build(
            self.repo,
            self.parity / "PARITY_CONTRACT.json",
            self.parity / "SURFACE_DISPOSITIONS.json",
            self.backfill / "inventory.json",
            self.backfill / "contracts/surface.schema.json",
            self.backfill / "out/report.json",
            self.backfill / "out/qualification.json",
            self.repo / "manzanita-next/experience/out/BUILD_RECEIPT.json",
            self.repo / "manzanita-next/qualification/out/QUALIFICATION_REPORT.json",
            self.repo / "manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json",
            output or self.output,
        )

    def test_complete_register_accounts_for_every_surface_and_component(self) -> None:
        receipt = self.build()
        register = json.loads((self.output / "PARITY_REGISTER.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(register["surface_count"], 2)
        self.assertEqual(register["component_count"], 6)
        self.assertEqual(register["uncovered_surfaces"], [])
        self.assertEqual(register["unknown_components"], [])
        self.assertEqual(register["held_public_surfaces"], ["alpha"])
        self.assertEqual(register["donor_public_surfaces"], ["manzanita"])
        self.assertEqual(register["successor_candidate"]["state"], "qualified_internal_candidate")
        self.assertFalse(register["successor_candidate"]["public_release_authorized"])

    def test_missing_surface_disposition_is_rejected(self) -> None:
        path = self.parity / "SURFACE_DISPOSITIONS.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["surfaces"].pop()
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "lacks a P9 disposition|coverage drifted"):
            self.build()

    def test_duplicate_surface_disposition_is_rejected(self) -> None:
        path = self.parity / "SURFACE_DISPOSITIONS.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["surfaces"].append(copy.deepcopy(value["surfaces"][0]))
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "duplicated"):
            self.build()

    def test_component_count_drift_is_rejected(self) -> None:
        path = self.backfill / "surfaces/alpha.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["assets_required"].append("unexpected source component")
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "component count drifted"):
            self.build()

    def test_source_surface_cannot_be_upgraded_by_disposition(self) -> None:
        path = self.parity / "SURFACE_DISPOSITIONS.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["surfaces"][0]["disposition"] = "qualified"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "cannot qualify"):
            self.build()

    def test_private_key_is_rejected(self) -> None:
        path = self.backfill / "surfaces/alpha.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["resident_name"] = "private fixture"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "schema failure|prohibited keys"):
            self.build()

    def test_p8_regression_is_rejected(self) -> None:
        path = self.repo / "manzanita-next/qualification/out/QUALIFICATION_REPORT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["campaigns"][3]["result"] = "FAIL"
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "campaign did not pass"):
            self.build()

    def test_open_high_board_defect_is_rejected(self) -> None:
        path = self.repo / "manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["open_critical_or_high_defects"] = ["M99-RB-DEF-999"]
        write_json(path, value)
        with self.assertRaisesRegex(builder.ParityError, "critical or high"):
            self.build()

    def test_build_is_deterministic_for_identical_inputs(self) -> None:
        first = self.build(self.parity / "out-first")
        second = self.build(self.parity / "out-second")
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(
            (self.parity / "out-first/PARITY_REGISTER.json").read_bytes(),
            (self.parity / "out-second/PARITY_REGISTER.json").read_bytes(),
        )

    def test_no_public_release_or_count_effect(self) -> None:
        receipt = self.build()
        register = json.loads((self.output / "PARITY_REGISTER.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["public_effect"], "none")
        self.assertEqual(receipt["constitutional_count_effect"], "none")
        self.assertEqual(receipt["release_effect"], "none")
        self.assertEqual(register["public_effect"], "none")
        self.assertEqual(register["constitutional_count_effect"], "none")
        self.assertEqual(register["release_effect"], "none")
        self.assertTrue(all(row["public_effect"] == "none" for row in register["components"]))


    def test_relative_paths_are_normalized_against_the_repository_root(self) -> None:
        original = Path.cwd()
        try:
            os.chdir(self.repo)
            receipt = builder.build(
                Path("."),
                Path("manzanita-next/parity/PARITY_CONTRACT.json"),
                Path("manzanita-next/parity/SURFACE_DISPOSITIONS.json"),
                Path("resolution-backfill/inventory.json"),
                Path("resolution-backfill/contracts/surface.schema.json"),
                Path("resolution-backfill/out/report.json"),
                Path("resolution-backfill/out/qualification.json"),
                Path("manzanita-next/experience/out/BUILD_RECEIPT.json"),
                Path("manzanita-next/qualification/out/QUALIFICATION_REPORT.json"),
                Path("manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json"),
                Path("manzanita-next/parity/out-relative"),
            )
        finally:
            os.chdir(original)
        self.assertEqual(receipt["result"], "PASS")
        register = json.loads(
            (self.parity / "out-relative/PARITY_REGISTER.json").read_text(encoding="utf-8")
        )
        self.assertEqual(register["source_inventory"], "resolution-backfill/inventory.json")
        self.assertEqual(
            register["surface_schema"],
            "resolution-backfill/contracts/surface.schema.json",
        )



if __name__ == "__main__":
    unittest.main()
