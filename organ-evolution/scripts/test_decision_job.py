from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import decision_job


class DecisionJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_path = TOOL / "data" / "fixtures" / "accepted-decision.fixture.json"
        self.model = decision_job.load_json(self.fixture_path)

    def build(self, model: dict | None = None) -> dict:
        return decision_job.build_job(copy.deepcopy(model or self.model))

    def test_fixture_builds_and_verifies(self) -> None:
        job = self.build()
        decision_job.verify_job(job)
        self.assertEqual(job["format"], decision_job.JOB_FORMAT)
        self.assertTrue(job["decision"]["decisionId"].startswith("orgdec1_"))
        self.assertTrue(job["jobId"].startswith("organjob1_"))
        self.assertTrue(job["execution"]["executionId"].startswith("organexec1_"))
        self.assertEqual(job["execution"]["jobId"], job["jobId"])

    def test_ids_are_stable_for_byte_equivalent_models(self) -> None:
        first = self.build()
        second = self.build(json.loads(json.dumps(self.model)))
        self.assertEqual(first, second)

    def test_execution_revision_does_not_rewrite_decision_or_job_identity(self) -> None:
        first = self.build()
        changed = copy.deepcopy(self.model)
        changed["decision"]["execution"]["verificationRefs"].append(
            "urn:fixture:verification:second"
        )
        second = self.build(changed)
        self.assertEqual(first["decision"]["decisionId"], second["decision"]["decisionId"])
        self.assertNotEqual(first["source"]["modelDigest"], second["source"]["modelDigest"])
        self.assertNotEqual(first["jobId"], second["jobId"])
        # The exact source model is custody evidence. Removing the execution
        # assertion therefore changes source identity while preserving decision.
        no_execution = copy.deepcopy(self.model)
        no_execution["decision"].pop("execution")
        third = self.build(no_execution)
        self.assertEqual(first["decision"]["decisionId"], third["decision"]["decisionId"])
        self.assertNotEqual(first["source"]["modelDigest"], third["source"]["modelDigest"])

    def test_job_identity_excludes_the_bound_execution_record(self) -> None:
        job = self.build()
        without_execution = copy.deepcopy(job)
        without_execution.pop("execution")
        without_execution["jobId"] = decision_job.digest(
            "organjob1", decision_job.without_keys(without_execution, "jobId")
        )
        self.assertEqual(job["jobId"], without_execution["jobId"])
        decision_job.verify_job(without_execution)

    def test_only_accepted_decisions_circulate(self) -> None:
        model = copy.deepcopy(self.model)
        model["decision"]["state"] = "proposed"
        with self.assertRaisesRegex(decision_job.DecisionJobError, "only an accepted"):
            self.build(model)

    def test_nonpassing_gate_is_refused(self) -> None:
        model = copy.deepcopy(self.model)
        model["candidates"][0]["gates"]["evidence"] = "open"
        with self.assertRaisesRegex(decision_job.DecisionJobError, "every hard gate"):
            self.build(model)

    def test_decider_must_be_declared_for_the_candidate(self) -> None:
        model = copy.deepcopy(self.model)
        model["candidates"][0]["actorLinks"]["deciders"] = []
        with self.assertRaisesRegex(decision_job.DecisionJobError, "not a declared decider"):
            self.build(model)

    def test_independent_anchor_is_required(self) -> None:
        model = copy.deepcopy(self.model)
        for evidence in model["evidence"]:
            evidence["independence"] = "mixed"
        with self.assertRaisesRegex(decision_job.DecisionJobError, "independent"):
            self.build(model)

    def test_complete_migration_ledger_is_required(self) -> None:
        model = copy.deepcopy(self.model)
        model["candidates"][0]["changes"].pop("retire")
        with self.assertRaisesRegex(decision_job.DecisionJobError, "keys differ"):
            self.build(model)

    def test_mandate_reference_and_basis_are_required(self) -> None:
        for key in ("mandateRef", "mandateBasis"):
            with self.subTest(key=key):
                model = copy.deepcopy(self.model)
                model["decision"][key] = ""
                with self.assertRaises(decision_job.DecisionJobError):
                    self.build(model)

    def test_terminal_execution_requires_both_reference_classes(self) -> None:
        for key in ("implementationRefs", "verificationRefs"):
            with self.subTest(key=key):
                model = copy.deepcopy(self.model)
                model["decision"]["execution"][key] = []
                with self.assertRaisesRegex(decision_job.DecisionJobError, "terminal execution"):
                    self.build(model)

    def test_not_started_execution_cannot_smuggle_evidence(self) -> None:
        model = copy.deepcopy(self.model)
        model["decision"]["execution"] = {
            "state": "not_started",
            "verificationRefs": ["urn:should-not-exist"],
        }
        with self.assertRaisesRegex(decision_job.DecisionJobError, "not-started"):
            self.build(model)

    def test_tampered_identities_fail_closed(self) -> None:
        for path in (
            ("decision", "decisionId"),
            (None, "jobId"),
            ("execution", "executionId"),
        ):
            with self.subTest(path=path):
                job = self.build()
                parent = job if path[0] is None else job[path[0]]
                parent[path[1]] = parent[path[1]][:-1] + (
                    "0" if parent[path[1]][-1] != "0" else "1"
                )
                with self.assertRaises(decision_job.DecisionJobError):
                    decision_job.verify_job(job)

    def test_authority_expansion_fails_closed(self) -> None:
        job = self.build()
        job.pop("execution")
        job["authority"]["compiler"] = "may accept outcomes"
        job["jobId"] = decision_job.digest(
            "organjob1", decision_job.without_keys(job, "jobId")
        )
        with self.assertRaisesRegex(decision_job.DecisionJobError, "authority membrane"):
            decision_job.verify_job(job)

    def test_duplicate_json_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text(
                '{"format":"axm-organ-evolution/1","format":"other"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(decision_job.DecisionJobError, "duplicate JSON key"):
                decision_job.load_json(path)

    def test_float_semantics_fail_closed(self) -> None:
        model = copy.deepcopy(self.model)
        model["candidates"][0]["dimensions"]["function"] = 4.0
        with self.assertRaisesRegex(decision_job.DecisionJobError, "integer 0..5"):
            decision_job.build_job(model)

    def test_cli_build_and_verify_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "job.json"
            build = subprocess.run(
                [
                    sys.executable,
                    str(HERE / "decision_job.py"),
                    "build",
                    str(self.fixture_path),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            verify = subprocess.run(
                [sys.executable, str(HERE / "decision_job.py"), "verify", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            built = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(build.stdout)["jobId"], built["jobId"])
            self.assertEqual(json.loads(verify.stdout)["jobId"], built["jobId"])


if __name__ == "__main__":
    unittest.main()
