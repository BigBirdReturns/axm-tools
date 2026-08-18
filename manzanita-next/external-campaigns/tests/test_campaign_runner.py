from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

import campaign_runner as runner  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class ExternalCampaignRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.contract_path = self.root / "CAMPAIGN_CONTRACT.json"
        shutil.copy2(ROOT / "CAMPAIGN_CONTRACT.json", self.contract_path)
        self.contract = json.loads(self.contract_path.read_text())
        self.ledger_path = self.root / "EXTERNAL_CAMPAIGN_LEDGER.json"
        shutil.copy2(
            REPO_ROOT / "manzanita-next/release-control/EXTERNAL_CAMPAIGN_LEDGER.json",
            self.ledger_path,
        )
        self.campaign_id = "M99-PHYS-DEVICE-001"
        self.definition = runner.campaign_definition(self.contract, self.campaign_id)
        self.workspace = self.root / "workspace"
        self.evidence_root = self.root / "evidence"
        self.evidence_root.mkdir()
        self.receipt_path = self.root / "CAMPAIGN_RECEIPT.json"
        runner.initialize_workspace(
            self.contract_path,
            self.campaign_id,
            self.workspace,
            operator="accountable device operator",
            venue="named physical device laboratory",
            procedure="Manzanita real-device campaign",
            procedure_version="1.0.0",
            started_at="2026-08-17T00:00:00Z",
            receipt_visibility="public_safe",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add_all_evidence(self, workspace: Path | None = None) -> list[str]:
        workspace = workspace or self.workspace
        ids: list[str] = []
        for index, evidence_class in enumerate(
            self.definition["required_evidence_classes"], start=1
        ):
            source = self.evidence_root / f"evidence-{index:02d}.txt"
            source.write_text(
                f"bounded evidence for {evidence_class}\n",
                encoding="utf-8",
            )
            evidence_id = f"E-{index:02d}"
            ids.append(evidence_id)
            runner.add_evidence(
                workspace,
                source,
                evidence_id=evidence_id,
                evidence_class=evidence_class,
                observed_at=f"2026-08-17T00:{index:02d}:00Z",
                actor="accountable device operator",
                rights="Operator-controlled test evidence",
                claim_scope=f"Bounded evidence for {evidence_class}",
                visibility="public_safe",
                locator=f"device-campaign/{source.name}",
            )
        return ids

    def add_all_observations(
        self,
        evidence_ids: list[str],
        workspace: Path | None = None,
        *,
        result: str = "pass",
    ) -> None:
        workspace = workspace or self.workspace
        for index, observation_type in enumerate(
            self.definition["required_observation_types"], start=1
        ):
            runner.record_observation(
                workspace,
                observation_id=f"O-{index:02d}",
                observation_type=observation_type,
                observed_at=f"2026-08-17T01:{index:02d}:00Z",
                actor="accountable device operator",
                object_name=f"Device campaign {observation_type}",
                mechanism=f"Versioned observation mechanism for {observation_type}",
                result=result,
                notes=f"Observed {observation_type} within the bounded campaign.",
                evidence_ids=[evidence_ids[(index - 1) % len(evidence_ids)]],
            )

    def complete_campaign(
        self,
        workspace: Path | None = None,
        receipt_path: Path | None = None,
    ) -> dict:
        workspace = workspace or self.workspace
        receipt_path = receipt_path or self.receipt_path
        evidence_ids = self.add_all_evidence(workspace)
        self.add_all_observations(evidence_ids, workspace)
        return runner.finalize_campaign(
            workspace,
            receipt_path,
            decision="PASSED",
            completed_at="2026-08-17T03:00:00Z",
            acceptance="Every required device observation and evidence class passed.",
            failure_disposition="No unresolved failure; release remains separately held.",
            deciding_actor="device campaign authority",
        )

    def test_contract_has_ten_unique_campaigns(self) -> None:
        runner.validate_contract(self.contract)
        ids = [row["id"] for row in self.contract["campaigns"]]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))

    def test_initial_workspace_is_hold_and_lists_every_gap(self) -> None:
        status = runner.campaign_status(self.workspace)
        self.assertEqual(status["state"], "HOLD")
        self.assertEqual(
            set(status["missing_observation_types"]),
            set(self.definition["required_observation_types"]),
        )
        self.assertEqual(
            set(status["missing_evidence_classes"]),
            set(self.definition["required_evidence_classes"]),
        )
        self.assertEqual(status["observation_count"], 0)
        self.assertEqual(status["evidence_count"], 0)

    def test_first_evidence_transitions_workspace_to_in_progress(self) -> None:
        source = self.evidence_root / "one.txt"
        source.write_text("one\n", encoding="utf-8")
        runner.add_evidence(
            self.workspace,
            source,
            evidence_id="E-ONE",
            evidence_class=self.definition["required_evidence_classes"][0],
            observed_at="2026-08-17T00:01:00Z",
            actor="operator",
            rights="Operator evidence",
            claim_scope="One bounded item",
            visibility="public_safe",
            locator="one.txt",
        )
        self.assertEqual(runner.campaign_status(self.workspace)["state"], "IN_PROGRESS")

    def test_complete_campaign_finalizes_and_verifies_with_readback(self) -> None:
        receipt = self.complete_campaign()
        result = runner.verify_receipt(
            self.receipt_path,
            evidence_root=self.evidence_root,
        )
        self.assertEqual(receipt["decision"], "PASSED")
        self.assertTrue(receipt["evidence_bytes_verified"])
        self.assertEqual(receipt["missing_observation_types"], [])
        self.assertEqual(receipt["missing_evidence_classes"], [])
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["decision"], "PASSED")
        self.assertEqual(
            set(result["evidence_readback_ids"]),
            {
                f"E-{index:02d}"
                for index in range(
                    1,
                    len(self.definition["required_evidence_classes"]) + 1,
                )
            },
        )

    def test_public_receipt_omits_local_paths_and_private_bytes(self) -> None:
        receipt = self.complete_campaign()
        serialized = json.dumps(receipt, sort_keys=True)
        self.assertNotIn("local_path", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("file_content", serialized)
        self.assertNotIn("raw_evidence", serialized)
        self.assertFalse(receipt["public_release_authorized"])
        self.assertFalse(receipt["ledger_mutation_authorized"])
        self.assertEqual(receipt["public_effect"], "none")
        self.assertEqual(receipt["constitutional_count_effect"], "none")

    def test_missing_observation_blocks_pass(self) -> None:
        evidence_ids = self.add_all_evidence()
        runner.record_observation(
            self.workspace,
            observation_id="O-ONLY",
            observation_type=self.definition["required_observation_types"][0],
            observed_at="2026-08-17T01:00:00Z",
            actor="operator",
            object_name="Partial device campaign",
            mechanism="One observation only",
            result="pass",
            notes="Only one observation is present.",
            evidence_ids=[evidence_ids[0]],
        )
        with self.assertRaisesRegex(runner.CampaignError, "lacks required observations"):
            runner.finalize_campaign(
                self.workspace,
                self.receipt_path,
                decision="PASSED",
                completed_at="2026-08-17T02:00:00Z",
                acceptance="Incomplete campaign cannot pass.",
                failure_disposition="Missing observations remain open.",
                deciding_actor="campaign authority",
            )

    def test_missing_evidence_class_blocks_pass(self) -> None:
        source = self.evidence_root / "partial.txt"
        source.write_text("partial\n", encoding="utf-8")
        runner.add_evidence(
            self.workspace,
            source,
            evidence_id="E-PARTIAL",
            evidence_class=self.definition["required_evidence_classes"][0],
            observed_at="2026-08-17T00:00:00Z",
            actor="operator",
            rights="Operator evidence",
            claim_scope="Partial evidence",
            visibility="public_safe",
            locator="partial.txt",
        )
        for index, observation_type in enumerate(
            self.definition["required_observation_types"], start=1
        ):
            runner.record_observation(
                self.workspace,
                observation_id=f"O-{index:02d}",
                observation_type=observation_type,
                observed_at="2026-08-17T01:00:00Z",
                actor="operator",
                object_name="Partial evidence campaign",
                mechanism="Complete observations, incomplete evidence classes",
                result="pass",
                notes="Observation exists but evidence classes are incomplete.",
                evidence_ids=["E-PARTIAL"],
            )
        with self.assertRaisesRegex(runner.CampaignError, "lacks required evidence classes"):
            runner.finalize_campaign(
                self.workspace,
                self.receipt_path,
                decision="PASSED",
                completed_at="2026-08-17T02:00:00Z",
                acceptance="Incomplete evidence cannot pass.",
                failure_disposition="Missing evidence classes remain open.",
                deciding_actor="campaign authority",
            )

    def test_tampered_evidence_blocks_pass(self) -> None:
        evidence_ids = self.add_all_evidence()
        self.add_all_observations(evidence_ids)
        (self.evidence_root / "evidence-01.txt").write_text(
            "tampered\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(runner.CampaignError, "evidence hashes failed"):
            runner.finalize_campaign(
                self.workspace,
                self.receipt_path,
                decision="PASSED",
                completed_at="2026-08-17T02:00:00Z",
                acceptance="Tampered campaign cannot pass.",
                failure_disposition="Evidence tamper blocks admission.",
                deciding_actor="campaign authority",
            )

    def test_nonpassing_observation_blocks_pass(self) -> None:
        evidence_ids = self.add_all_evidence()
        self.add_all_observations(evidence_ids, result="hold")
        with self.assertRaisesRegex(runner.CampaignError, "non-passing observations"):
            runner.finalize_campaign(
                self.workspace,
                self.receipt_path,
                decision="PASSED",
                completed_at="2026-08-17T02:00:00Z",
                acceptance="Held observations cannot pass.",
                failure_disposition="Observation holds remain open.",
                deciding_actor="campaign authority",
            )

    def test_observation_without_evidence_blocks_pass(self) -> None:
        evidence_ids = self.add_all_evidence()
        for index, observation_type in enumerate(
            self.definition["required_observation_types"], start=1
        ):
            runner.record_observation(
                self.workspace,
                observation_id=f"O-{index:02d}",
                observation_type=observation_type,
                observed_at="2026-08-17T01:00:00Z",
                actor="operator",
                object_name="Unlinked observation campaign",
                mechanism="Observation without evidence link",
                result="pass",
                notes="Observation deliberately lacks an evidence reference.",
                evidence_ids=[] if index == 1 else [evidence_ids[0]],
            )
        with self.assertRaisesRegex(runner.CampaignError, "observations without evidence"):
            runner.finalize_campaign(
                self.workspace,
                self.receipt_path,
                decision="PASSED",
                completed_at="2026-08-17T02:00:00Z",
                acceptance="Unlinked evidence cannot pass.",
                failure_disposition="Evidence linkage remains open.",
                deciding_actor="campaign authority",
            )

    def test_duplicate_evidence_and_observation_ids_are_rejected(self) -> None:
        source = self.evidence_root / "duplicate.txt"
        source.write_text("duplicate\n", encoding="utf-8")
        kwargs = dict(
            evidence_id="DUPLICATE",
            evidence_class=self.definition["required_evidence_classes"][0],
            observed_at="2026-08-17T00:00:00Z",
            actor="operator",
            rights="Operator evidence",
            claim_scope="Duplicate id test",
            visibility="public_safe",
            locator="duplicate.txt",
        )
        runner.add_evidence(self.workspace, source, **kwargs)
        with self.assertRaisesRegex(runner.CampaignError, "Duplicate evidence id"):
            runner.add_evidence(self.workspace, source, **kwargs)
        observation_kwargs = dict(
            observation_id="O-DUPLICATE",
            observation_type=self.definition["required_observation_types"][0],
            observed_at="2026-08-17T01:00:00Z",
            actor="operator",
            object_name="Duplicate observation",
            mechanism="Duplicate id test",
            result="pass",
            notes="First observation.",
            evidence_ids=["DUPLICATE"],
        )
        runner.record_observation(self.workspace, **observation_kwargs)
        with self.assertRaisesRegex(runner.CampaignError, "Duplicate observation id"):
            runner.record_observation(self.workspace, **observation_kwargs)

    def test_receipt_tamper_is_detected(self) -> None:
        self.complete_campaign()
        receipt = json.loads(self.receipt_path.read_text())
        receipt["acceptance"] = "tampered acceptance"
        write_json(self.receipt_path, receipt)
        with self.assertRaisesRegex(runner.CampaignError, "payload checksum"):
            runner.verify_receipt(self.receipt_path)

    def test_prohibited_public_key_is_rejected_even_with_valid_checksum(self) -> None:
        receipt = self.complete_campaign()
        receipt["resident_email"] = "private@example.invalid"
        write_json(self.receipt_path, runner.add_payload(receipt))
        with self.assertRaisesRegex(runner.CampaignError, "prohibited public keys"):
            runner.verify_receipt(self.receipt_path)

    def test_hold_can_be_recorded_but_cannot_propose_pass(self) -> None:
        receipt = runner.finalize_campaign(
            self.workspace,
            self.receipt_path,
            decision="HOLD",
            completed_at="2026-08-17T02:00:00Z",
            acceptance="Campaign remains held.",
            failure_disposition="Required observations and evidence remain missing.",
            deciding_actor="campaign authority",
        )
        self.assertEqual(receipt["decision"], "HOLD")
        with self.assertRaisesRegex(runner.CampaignError, "Only a passed campaign"):
            runner.propose_ledger_amendment(
                self.ledger_path,
                self.receipt_path,
                self.root / "proposed-ledger.json",
                self.root / "amendment.json",
            )

    def test_passed_receipt_proposes_exactly_one_bounded_ledger_row(self) -> None:
        receipt = self.complete_campaign()
        source = json.loads(self.ledger_path.read_text())
        target_before = next(
            row for row in source["campaigns"] if row["id"] == self.campaign_id
        )
        if target_before["state"] == "passed":
            self.skipTest("The repository ledger already passed the device campaign")
        output_ledger = self.root / "proposed-ledger.json"
        amendment_path = self.root / "amendment.json"
        amendment = runner.propose_ledger_amendment(
            self.ledger_path,
            self.receipt_path,
            output_ledger,
            amendment_path,
        )
        proposed = json.loads(output_ledger.read_text())
        changed = [
            (before, after)
            for before, after in zip(
                source["campaigns"], proposed["campaigns"], strict=True
            )
            if before != after
        ]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][1]["id"], self.campaign_id)
        self.assertEqual(changed[0][1]["state"], "passed")
        self.assertEqual(proposed["release_state"], "HOLD")
        self.assertFalse(proposed["public_release_authorized"])
        self.assertEqual(amendment["state"], "PROPOSED")
        self.assertTrue(amendment["release_authority_review_required"])
        self.assertFalse(amendment["ledger_mutation_authorized"])
        self.assertFalse(amendment["public_release_authorized"])
        self.assertEqual(amendment["campaign_receipt_sha256"], receipt["payload_sha256"])

    def test_already_passed_ledger_row_refuses_duplicate_proposal(self) -> None:
        self.complete_campaign()
        ledger = json.loads(self.ledger_path.read_text())
        target = next(row for row in ledger["campaigns"] if row["id"] == self.campaign_id)
        target.update(
            {
                "state": "passed",
                "operator": "prior operator",
                "venue": "prior venue",
                "procedure": "prior procedure",
                "evidence_receipts": ["prior receipt"],
                "acceptance": "prior acceptance",
                "failure_disposition": "prior disposition",
            }
        )
        write_json(self.ledger_path, ledger)
        with self.assertRaisesRegex(runner.CampaignError, "already records"):
            runner.propose_ledger_amendment(
                self.ledger_path,
                self.receipt_path,
                self.root / "proposed-ledger.json",
                self.root / "amendment.json",
            )

    def test_qualification_matches_canonical_ids_without_performing_campaign(self) -> None:
        output = self.root / "RUNNER_QUALIFICATION.json"
        receipt = runner.qualify_runner(
            self.contract_path,
            self.ledger_path,
            output,
        )
        ledger = json.loads(self.ledger_path.read_text())
        expected_passed = [
            row["id"] for row in ledger["campaigns"] if row["state"] == "passed"
        ]
        self.assertEqual(receipt["campaign_count"], 10)
        self.assertEqual(receipt["campaign_ids"], [row["id"] for row in ledger["campaigns"]])
        self.assertEqual(receipt["passed_campaigns"], expected_passed)
        self.assertEqual(receipt["passed_campaign_count"], len(expected_passed))
        self.assertEqual(receipt["open_campaign_count"], 10 - len(expected_passed))
        self.assertFalse(receipt["campaign_performed_by_qualification"])
        self.assertFalse(receipt["physical_standing"])
        self.assertFalse(receipt["ledger_mutation_authorized"])
        self.assertFalse(receipt["public_release_authorized"])
        self.assertEqual(receipt["release_ledger"]["release_state"], "HOLD")

    def test_qualification_rejects_identity_drift(self) -> None:
        ledger = json.loads(self.ledger_path.read_text())
        ledger["campaigns"][0]["id"] = "DRIFTED-ID"
        write_json(self.ledger_path, ledger)
        with self.assertRaisesRegex(runner.CampaignError, "identities drifted"):
            runner.qualify_runner(
                self.contract_path,
                self.ledger_path,
                self.root / "qualification.json",
            )

    def test_qualification_rejects_incomplete_passed_row(self) -> None:
        ledger = json.loads(self.ledger_path.read_text())
        target = next(row for row in ledger["campaigns"] if row["id"] == self.campaign_id)
        target["state"] = "passed"
        target["operator"] = None
        write_json(self.ledger_path, ledger)
        with self.assertRaisesRegex(runner.CampaignError, "lacks operator"):
            runner.qualify_runner(
                self.contract_path,
                self.ledger_path,
                self.root / "qualification.json",
            )

    @unittest.skipIf(os.name == "nt", "Windows symlink creation requires extra privilege")
    def test_symlink_evidence_is_rejected(self) -> None:
        source = self.evidence_root / "source.txt"
        source.write_text("source\n", encoding="utf-8")
        link = self.evidence_root / "link.txt"
        link.symlink_to(source)
        with self.assertRaisesRegex(runner.CampaignError, "symlink"):
            runner.add_evidence(
                self.workspace,
                link,
                evidence_id="E-LINK",
                evidence_class=self.definition["required_evidence_classes"][0],
                observed_at="2026-08-17T00:00:00Z",
                actor="operator",
                rights="Operator evidence",
                claim_scope="Symlink refusal test",
                visibility="public_safe",
                locator="link.txt",
            )

    def test_invalid_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(runner.CampaignError, "ISO-8601"):
            runner.initialize_workspace(
                self.contract_path,
                self.campaign_id,
                self.root / "bad-time-workspace",
                operator="operator",
                venue="venue",
                procedure="procedure",
                procedure_version="1.0.0",
                started_at="not-a-time",
                receipt_visibility="public_safe",
            )

    def test_receipt_is_deterministic_across_workspace_locations(self) -> None:
        first = self.complete_campaign()
        second_workspace = self.root / "workspace-two"
        second_receipt = self.root / "receipt-two.json"
        runner.initialize_workspace(
            self.contract_path,
            self.campaign_id,
            second_workspace,
            operator="accountable device operator",
            venue="named physical device laboratory",
            procedure="Manzanita real-device campaign",
            procedure_version="1.0.0",
            started_at="2026-08-17T00:00:00Z",
            receipt_visibility="public_safe",
        )
        second = self.complete_campaign(second_workspace, second_receipt)
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(self.receipt_path.read_bytes(), second_receipt.read_bytes())

    def test_unknown_campaign_evidence_and_observation_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(runner.CampaignError, "Unknown or duplicate campaign"):
            runner.campaign_definition(self.contract, "M99-UNKNOWN")
        source = self.evidence_root / "unknown.txt"
        source.write_text("unknown\n", encoding="utf-8")
        with self.assertRaisesRegex(runner.CampaignError, "not admitted"):
            runner.add_evidence(
                self.workspace,
                source,
                evidence_id="E-UNKNOWN",
                evidence_class="unknown_class",
                observed_at="2026-08-17T00:00:00Z",
                actor="operator",
                rights="Operator evidence",
                claim_scope="Unknown class test",
                visibility="public_safe",
                locator="unknown.txt",
            )
        with self.assertRaisesRegex(runner.CampaignError, "not admitted"):
            runner.record_observation(
                self.workspace,
                observation_id="O-UNKNOWN",
                observation_type="unknown_type",
                observed_at="2026-08-17T01:00:00Z",
                actor="operator",
                object_name="Unknown observation",
                mechanism="Unknown type test",
                result="pass",
                notes="Unknown observation type.",
                evidence_ids=[],
            )


if __name__ == "__main__":
    unittest.main()
