from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from evidence import ingest_receipts, make_receipt, validate_receipt, write_json  # noqa: E402
from planner import PlannerError, parse_inputs, read_json  # noqa: E402


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.goals = read_json(ROOT / "data" / "goals.json")
        self.experiments = read_json(ROOT / "data" / "experiments.json")
        self.evidence = read_json(ROOT / "data" / "evidence.json")
        self.tiers, _, _, _ = parse_inputs(self.goals, self.experiments)

    def make_valid_receipt(self, directory: Path) -> Path:
        artifact = directory / "function-contract.json"
        artifact.write_text('{"ok":true}\n', encoding="utf-8")
        receipt = make_receipt(
            experiment_id="freeze-one-function",
            status="PASS",
            generated_at="2026-08-05T00:00:00Z",
            checks=[{"id": "contract", "pass": True}],
            artifact_paths=[artifact],
            receipt_dir=directory,
            supports=[{"capability": "function_contract", "tier": "qualified"}],
            claim_boundary="fixture qualification only",
        )
        path = directory / "experiment.receipt.json"
        write_json(path, receipt)
        return path

    def test_valid_receipt_ingests_exact_support(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.make_valid_receipt(Path(raw))
            ledger, accepted = ingest_receipts(
                self.evidence,
                [path],
                self.experiments,
                self.tiers,
                as_of="2026-08-05T00:00:00Z",
            )
            self.assertTrue(accepted[0]["ingested"])
            self.assertEqual(ledger["records"][-1]["supports"], [{"capability": "function_contract", "tier": "qualified"}])

    def test_tampered_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            path = self.make_valid_receipt(directory)
            (directory / "function-contract.json").write_text('{"ok":false}\n', encoding="utf-8")
            with self.assertRaises(PlannerError):
                validate_receipt(read_json(path), path, self.experiments, self.tiers)

    def test_receipt_cannot_promote_above_experiment_ceiling(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            path = self.make_valid_receipt(directory)
            receipt = read_json(path)
            receipt["supports"][0]["tier"] = "accepted"
            receipt.pop("receipt_sha256")
            write_json(path, receipt)
            with self.assertRaises(PlannerError):
                validate_receipt(read_json(path), path, self.experiments, self.tiers)

    def test_duplicate_receipt_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.make_valid_receipt(Path(raw))
            ledger, first = ingest_receipts(self.evidence, [path], self.experiments, self.tiers, as_of="2026-08-05T00:00:00Z")
            ledger2, second = ingest_receipts(ledger, [path], self.experiments, self.tiers, as_of="2026-08-05T00:00:00Z")
            self.assertTrue(first[0]["ingested"])
            self.assertFalse(second[0]["ingested"])
            self.assertEqual(len(ledger["records"]), len(ledger2["records"]))


if __name__ == "__main__":
    unittest.main()
