#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from operator_decision import DecisionError, load_json, validate

HERE = Path(__file__).resolve().parent
CONTRACT = load_json(HERE / "OPERATOR_REVIEW_CONTRACT.json")
TEMPLATE = load_json(HERE / "OPERATOR_DECISION_TEMPLATE.json")


class OperatorDecisionTests(unittest.TestCase):
    def test_pending_template_is_fail_closed(self) -> None:
        result = validate(copy.deepcopy(TEMPLATE), CONTRACT)
        self.assertEqual(result["decision"], "PENDING")
        self.assertEqual(result["operator_visual_acceptance"], "ABSENT")
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["merge_authorized"])
        self.assertEqual(result["public_route_effect"], "none")

    def test_pending_template_rejects_preaccepted_criterion(self) -> None:
        decision = copy.deepcopy(TEMPLATE)
        decision["criteria"][0]["result"] = "PASS"
        with self.assertRaises(DecisionError):
            validate(decision, CONTRACT)

    def test_authority_invariant_cannot_be_raised(self) -> None:
        decision = copy.deepcopy(TEMPLATE)
        decision["release_authorized"] = True
        with self.assertRaises(DecisionError):
            validate(decision, CONTRACT)

    def test_accepted_decision_requires_every_criterion(self) -> None:
        decision = self.recorded("ACCEPTED")
        decision["criteria"][3]["result"] = "FAIL"
        with self.assertRaises(DecisionError):
            validate(decision, CONTRACT)

    def test_revise_requires_a_failed_criterion(self) -> None:
        decision = self.recorded("REVISE")
        with self.assertRaises(DecisionError):
            validate(decision, CONTRACT)

    def test_recorded_receipt_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = self.recorded("ACCEPTED", root)
            validate(decision, CONTRACT, root)
            first = root / CONTRACT["required_receipts"][0]
            first.write_text("drift\n", encoding="utf-8")
            with self.assertRaises(DecisionError):
                validate(decision, CONTRACT, root)

    def test_accepted_decision_does_not_authorize_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = self.recorded("ACCEPTED", root)
            result = validate(decision, CONTRACT, root)
            self.assertEqual(result["operator_visual_acceptance"], "ACCEPTED")
            self.assertFalse(result["release_authorized"])
            self.assertFalse(result["merge_authorized"])
            self.assertEqual(result["external_effect"], "none")

    def recorded(self, state: str, receipt_root: Path | None = None) -> dict:
        decision = copy.deepcopy(TEMPLATE)
        decision.update({
            "generated_at": "2026-08-27T01:30:00+00:00",
            "decision": state,
            "operator": "Test Operator",
            "rationale": "This is a substantive test rationale for the bounded visual decision.",
            "operator_visual_acceptance": "ACCEPTED" if state == "ACCEPTED" else "NOT_ACCEPTED",
        })
        for row in decision["criteria"]:
            row["result"] = "PASS"
            row["notes"] = None
        receipts = {}
        for index, name in enumerate(CONTRACT["required_receipts"]):
            payload = f"receipt-{index}\n".encode()
            if receipt_root is not None:
                (receipt_root / name).write_bytes(payload)
            receipts[name] = {
                "path": name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        decision["reviewed_receipts"] = receipts
        return decision


if __name__ == "__main__":
    unittest.main()
