from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

BOARD_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(BOARD_ROOT))

import validate_review_board as review  # noqa: E402


class ReviewBoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.charter = review.load_json(BOARD_ROOT / "BOARD_CHARTER.json")
        self.activation = review.load_json(BOARD_ROOT / "ACTIVATION_STATE.json")
        self.packet = review.load_json(BOARD_ROOT / "cases" / "M99-RB-PKT-001.json")
        self.decision = review.load_json(BOARD_ROOT / "cases" / "M99-RB-DEC-001.json")
        self.packet_schema = review.load_json(BOARD_ROOT / "review-packet.schema.json")
        self.decision_schema = review.load_json(BOARD_ROOT / "review-decision.schema.json")

    def validate_documents(self, packet=None, decision=None):
        packet = packet or self.packet
        decision = decision or self.decision
        review.validate_schema_documents(self.packet_schema, self.decision_schema)
        review.validate_charter(self.charter)
        review.validate_activation(self.activation, self.charter)
        packet_result = review.validate_packet(REPO_ROOT, self.charter, packet)
        decision_result = review.validate_decision(
            self.charter,
            packet,
            decision,
            packet_result,
        )
        return packet_result, decision_result

    def test_activation_case_passes_and_is_governance_only(self) -> None:
        _, decision_result = self.validate_documents()
        self.assertEqual(decision_result["outcome"], "admit_governance_only")
        self.assertEqual(decision_result["release_effect"], "none")
        self.assertEqual(decision_result["seat_ids"], review.EXPECTED_SEATS)
        self.assertEqual(decision_result["open_vetoes"], [])
        self.assertEqual(decision_result["open_severe_defects"], [])

    def test_receipt_is_deterministic(self) -> None:
        first, _ = review.validate_board(REPO_ROOT, head_override="0" * 40)
        second, _ = review.validate_board(REPO_ROOT, head_override="0" * 40)
        self.assertEqual(first, second)
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(first["constitutional_count_effect"], "none")
        self.assertEqual(first["seat_count"], 12)

    def test_missing_seat_blocks_decision(self) -> None:
        decision = copy.deepcopy(self.decision)
        decision["seat_reviews"] = decision["seat_reviews"][:-1]
        with self.assertRaisesRegex(review.ReviewError, "seat coverage drifted"):
            self.validate_documents(decision=decision)

    def test_unknown_applicable_gate_blocks_admission(self) -> None:
        decision = copy.deepcopy(self.decision)
        decision["gate_disposition"]["mechanism_fidelity"]["state"] = "unknown"
        decision["gate_disposition"]["mechanism_fidelity"]["reason"] = (
            "The mechanism has not been established by retained evidence."
        )
        with self.assertRaisesRegex(review.ReviewError, "unknown applicable gates"):
            self.validate_documents(decision=decision)

    def test_open_high_veto_blocks_admission(self) -> None:
        decision = copy.deepcopy(self.decision)
        veto = {
            "id": "M99-RB-VETO-001",
            "seat_id": "source_custody",
            "severity": "high",
            "title": "Evidence identity is unresolved",
            "mechanism": "The reviewed claim cannot be bound to the evidence object submitted in the packet.",
            "evidence_ids": ["E-CHARTER"],
            "state": "open",
            "resolution": "Await a new evidence-backed decision."
        }
        decision["vetoes"].append(veto)
        source_review = next(
            row for row in decision["seat_reviews"] if row["seat_id"] == "source_custody"
        )
        source_review["veto_ids"].append(veto["id"])
        with self.assertRaisesRegex(review.ReviewError, "open critical or high veto"):
            self.validate_documents(decision=decision)

    def test_open_high_defect_blocks_admission(self) -> None:
        decision = copy.deepcopy(self.decision)
        decision["defects"].append(
            {
                "id": "M99-RB-DEF-002",
                "severity": "high",
                "title": "Authority boundary is unresolved",
                "mechanism": "The decision could be interpreted to authorize an effect outside the packet scope.",
                "evidence_ids": ["E-CHARTER"],
                "owner": "release_authority",
                "acceptance": "Rewrite and re-review the authority receipt until the excessive effect is impossible.",
                "disposition": "open"
            }
        )
        with self.assertRaisesRegex(review.ReviewError, "unresolved critical or high defect"):
            self.validate_documents(decision=decision)

    def test_governance_activation_cannot_acquire_release_effect(self) -> None:
        decision = copy.deepcopy(self.decision)
        decision["release_effect"] = "release_authority_required"
        with self.assertRaisesRegex(review.ReviewError, "cannot have a release effect"):
            self.validate_documents(decision=decision)

    def test_external_review_claim_is_rejected(self) -> None:
        decision = copy.deepcopy(self.decision)
        decision["external_review_claim"] = True
        with self.assertRaisesRegex(review.ReviewError, "cannot claim external review"):
            self.validate_documents(decision=decision)

    def test_missing_evidence_file_is_rejected(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["evidence"][0]["path"] = "programs/manzanita-99/review-board/DOES_NOT_EXIST.json"
        with self.assertRaisesRegex(review.ReviewError, "Evidence file does not exist"):
            self.validate_documents(packet=packet)

    def test_unknown_evidence_reference_is_rejected(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["gates"]["object_classification"]["evidence_ids"].append("E-UNKNOWN")
        with self.assertRaisesRegex(review.ReviewError, "cites unknown evidence"):
            self.validate_documents(packet=packet)

    def test_not_applicable_gate_requires_bounded_reason(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["gates"]["interaction_semantics"]["reason"] = (
            "This gate is outside current scope."
        )
        with self.assertRaisesRegex(review.ReviewError, "not-applicable reason"):
            self.validate_documents(packet=packet)

    def test_exact_source_binding_requires_commit_sha(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["source_ref"] = {
            "repository": "BigBirdReturns/axm-tools",
            "binding": "exact_commit",
            "ref": "main"
        }
        with self.assertRaisesRegex(review.ReviewError, "must be a commit SHA"):
            self.validate_documents(packet=packet)


if __name__ == "__main__":
    unittest.main()
