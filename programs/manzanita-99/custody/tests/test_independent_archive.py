from __future__ import annotations

import json
import unittest
from pathlib import Path


CUSTODY = Path(__file__).resolve().parents[1]


class IndependentArchiveReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = json.loads(
            (CUSTODY / "INDEPENDENT_ARCHIVE_RECEIPT.json").read_text(encoding="utf-8")
        )
        self.register = json.loads(
            (CUSTODY / "DONOR_REGISTER.json").read_text(encoding="utf-8")
        )
        self.observed = json.loads(
            (CUSTODY / "OBSERVED_EXECUTION_LEDGER.json").read_text(encoding="utf-8")
        )

    def test_receipt_proves_exact_readback_and_clean_recovery(self) -> None:
        self.assertEqual(
            self.receipt["schema"],
            "axm-tools/manzanita-independent-archive-receipt@1",
        )
        self.assertEqual(self.receipt["gap_id"], "M99-CUSTODY-GAP-002")
        self.assertEqual(
            self.receipt["archive_control"]["permission_class"], "owner_only"
        )
        self.assertFalse(self.receipt["archive_control"]["shared"])
        self.assertFalse(self.receipt["archive_control"]["public_discovery"])
        expected = {
            "M99-ARCHIVE-OBJECT-CANDIDATE-001": (
                696968,
                "73a222505b40ffd74c3c2464a0a313b0fc5c4ff7df9f9b6e996cba8be036e90b",
            ),
            "M99-ARCHIVE-OBJECT-EVIDENCE-001": (
                10247061,
                "d57f3878f9958b446d2ac55dfdd395ae3881cf9be44fffbfddffd7932cd47454",
            ),
        }
        self.assertEqual(
            {row["id"] for row in self.receipt["objects"]}, set(expected)
        )
        for row in self.receipt["objects"]:
            self.assertEqual(
                (row["bytes"], row["sha256"]), expected[row["id"]]
            )
            self.assertTrue(row["metadata_readback"])
            self.assertTrue(row["byte_readback"])
            self.assertEqual(row["zip_integrity"], "PASS")
            self.assertEqual(row["unsafe_paths"], 0)
            self.assertEqual(row["symbolic_links"], 0)
        recovery = self.receipt["cold_recovery"]
        self.assertEqual(recovery["result"], "PASS")
        self.assertTrue(recovery["extracted_to_clean_directory"])
        self.assertFalse(recovery["repository_imports"])
        self.assertFalse(recovery["private_credentials"])
        self.assertEqual(
            recovery["source_commit"],
            "ed387ac8d27576484c71a13a7d0c8c8194f9b2ed",
        )
        self.assertEqual(recovery["file_count"], 24)
        self.assertEqual(
            recovery["manifest_sha256"],
            "35a2b2ffc8be0d51191b40bd45cdd04cbf117cb2176829db91fe5f4402742a74",
        )

    def test_public_receipt_is_provider_neutral_and_grants_no_effect(self) -> None:
        serialized = json.dumps(self.receipt, sort_keys=True).lower()
        for token in (
            "drive.google",
            "gmail.com",
            "@gmail",
            "1_dsq",
            "1eax",
            "17m4_",
        ):
            self.assertNotIn(token, serialized)
        self.assertFalse(self.receipt["public_release_authorized"])
        self.assertEqual(self.receipt["external_campaign_effect"], "none")
        self.assertEqual(self.receipt["public_effect"], "none")
        self.assertEqual(self.receipt["constitutional_count_effect"], "none")

    def test_register_closes_only_the_independent_archive_gap(self) -> None:
        gaps = {row["id"]: row for row in self.register["gaps"]}
        self.assertEqual(gaps["M99-CUSTODY-GAP-002"]["state"], "closed")
        self.assertTrue(
            gaps["M99-CUSTODY-GAP-002"]["closure_evidence"]
        )
        self.assertEqual(
            sum(row["state"] == "closed" for row in self.register["gaps"]),
            1,
        )
        donor = next(
            row for row in self.register["donors"] if row["id"] == "p10-independent-archive-001"
        )
        self.assertEqual(donor["class"], "independent_archive")
        self.assertEqual(donor["custody_state"], "archived_external")
        self.assertEqual(
            donor["anchors"]["receipt"],
            "programs/manzanita-99/custody/INDEPENDENT_ARCHIVE_RECEIPT.json",
        )

    def test_external_campaign_and_release_hold_remain_unchanged(self) -> None:
        external = self.observed["external_campaign_state"]
        self.assertEqual(external["release_state"], "HOLD")
        self.assertEqual(external["passed_campaigns"], [])
        self.assertEqual(len(external["not_performed_campaigns"]), 10)
        self.assertFalse(external["public_release_authorized"])
        self.assertFalse(self.receipt["public_release_authorized"])


if __name__ == "__main__":
    unittest.main()
