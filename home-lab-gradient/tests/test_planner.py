from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from planner import PlannerError, build_plan, read_json  # noqa: E402


class PlannerTests(unittest.TestCase):
    def docs(self):
        return (
            read_json(ROOT / "data" / "estate.json"),
            read_json(ROOT / "data" / "goals.json"),
            read_json(ROOT / "data" / "experiments.json"),
            read_json(ROOT / "data" / "evidence.json"),
        )

    def test_seed_selects_two_zero_package_easy_wins(self):
        plan = build_plan(*self.docs(), generated_at="2026-08-05T00:00:00Z")
        self.assertEqual(
            [row["id"] for row in plan["now"][:2]],
            ["capture-estate-snapshot", "freeze-one-function"],
        )
        self.assertTrue(all(row["cost"]["new_packages"] == 0 for row in plan["now"]))
        self.assertTrue(all(row["cost"]["irreversible"] == 0 for row in plan["now"]))

    def test_plan_identity_excludes_projection_time(self):
        docs = self.docs()
        first = build_plan(*docs, generated_at="2026-08-05T00:00:00Z")
        second = build_plan(*docs, generated_at="2026-08-06T00:00:00Z")
        self.assertEqual(first["plan_sha256"], second["plan_sha256"])
        self.assertNotEqual(first["generated_at"], second["generated_at"])

    def test_named_support_advances_only_named_capability(self):
        estate, goals, experiments, evidence = self.docs()
        evidence = copy.deepcopy(evidence)
        evidence["records"].append(
            {
                "id": "qualified-function",
                "tier": "qualified",
                "supports": [{"capability": "function_contract", "tier": "qualified"}],
            }
        )
        plan = build_plan(estate, goals, experiments, evidence, generated_at="2026-08-05T00:00:00Z")
        states = {row["id"]: row["state"] for row in plan["capabilities"]}
        self.assertEqual(states["function_contract"], "qualified")
        self.assertEqual(states["receipt_binding"], "unknown")
        admissible = {row["id"] for row in plan["ranked_admissible"]}
        self.assertIn("bind-function-receipts", admissible)

    def test_narrative_without_support_does_not_promote(self):
        estate, goals, experiments, evidence = self.docs()
        evidence = copy.deepcopy(evidence)
        evidence["records"].append(
            {
                "id": "strong-narrative",
                "tier": "accepted",
                "supports": [],
                "facts": {"claim": "everything works"},
            }
        )
        plan = build_plan(estate, goals, experiments, evidence, generated_at="2026-08-05T00:00:00Z")
        self.assertEqual(plan["summary"]["capabilities_satisfied"], 0)

    def test_unknown_capability_reference_is_rejected(self):
        estate, goals, experiments, evidence = self.docs()
        broken = copy.deepcopy(experiments)
        broken["experiments"][0]["produces"][0]["capability"] = "imaginary"
        with self.assertRaises(PlannerError):
            build_plan(estate, goals, broken, evidence, generated_at="2026-08-05T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
