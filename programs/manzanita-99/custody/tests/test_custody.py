from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CUSTODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CUSTODY))

import audit_history  # noqa: E402
import build_custody  # noqa: E402
import validate_custody  # noqa: E402


def write(path: Path, text: str) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    path.write_bytes(payload)
    return payload


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class CustodyV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        public = write(self.root / "manzanita/index.html", "<h1>historical</h1>\n")
        write(self.root / "manzanita-next/source.txt", "successor\n")
        write(self.root / "programs/manzanita-99/review-board/board.json", "{}\n")
        write(self.root / "programs/manzanita-99/recovery/recovery.json", "{}\n")
        write(self.root / "resolution-backfill/inventory.json", "{}\n")
        write(self.root / ".github/workflows/manzanita-one.yml", "name: one\n")
        write(self.root / ".github/workflows/other.yml", "name: other\n")
        write(self.root / ".github/pages-deployment.json", "{}\n")
        self.directory = self.root / "programs/manzanita-99/custody"
        self.contract_path = self.directory / "CUSTODY_CONTRACT.json"
        self.register_path = self.directory / "DONOR_REGISTER.json"
        self.observed_path = self.directory / "OBSERVED_EXECUTION_LEDGER.json"
        self.manifest_path = self.directory / "CUSTODY_MANIFEST.json"
        self.contract = {
            "schema": "axm-tools/manzanita-donor-custody-contract@2",
            "contract_id": "test",
            "state": "in_progress",
            "required_classes": ["historical_public_release", "successor_source", "governance", "failure_receipt", "qualification_receipt", "deployment_receipt", "visual_golden"],
            "archive_scopes": [
                {"id": "public", "class": "historical_public_release", "path": "manzanita", "required": True, "include": ["**"], "exclude": []},
                {"id": "next", "class": "successor_source", "path": "manzanita-next", "required": True, "include": ["**"], "exclude": []},
                {"id": "board", "class": "governance", "path": "programs/manzanita-99/review-board", "required": True, "include": ["**"], "exclude": []},
                {"id": "recovery", "class": "failure_receipt", "path": "programs/manzanita-99/recovery", "required": True, "include": ["**"], "exclude": []},
                {"id": "backfill", "class": "qualification_receipt", "path": "resolution-backfill", "required": True, "include": ["**"], "exclude": []},
                {"id": "workflows", "class": "qualification_receipt", "path": ".github/workflows", "required": True, "include": ["manzanita-*.yml"], "exclude": []},
                {"id": "pages", "class": "deployment_receipt", "path": ".github/pages-deployment.json", "required": True, "include": ["**"], "exclude": []},
                {"id": "custody", "class": "governance", "path": "programs/manzanita-99/custody", "required": True, "include": ["**"], "exclude": ["CUSTODY_MANIFEST.json"]},
            ],
            "public_route_guard": {"path": "manzanita", "files": {"manzanita/index.html": {"git_blob_sha1": build_custody.git_blob_sha1(public)}}},
            "qualification_boundary": "Partial custody only.",
            "close_law": {"canonical_task_count_effect": "none_without_exact_row_source"},
        }
        self.register = {
            "schema": "axm-tools/manzanita-donor-register@2",
            "contract_id": "test",
            "state": "in_progress",
            "donors": [
                {"id": "public", "class": "historical_public_release", "custody_state": "archived_repo", "archive_scope_ids": ["public"], "claim_boundary": "Historical donor."},
                {"id": "next", "class": "successor_source", "custody_state": "archived_repo", "archive_scope_ids": ["next"], "claim_boundary": "Internal donor."},
                {"id": "board", "class": "governance", "custody_state": "archived_repo", "archive_scope_ids": ["board"], "claim_boundary": "Governance donor."},
                {"id": "recovery", "class": "failure_receipt", "custody_state": "archived_repo", "archive_scope_ids": ["recovery"], "claim_boundary": "Failure donor."},
                {"id": "qualification", "class": "qualification_receipt", "custody_state": "archived_repo", "archive_scope_ids": ["backfill", "workflows"], "claim_boundary": "Qualification donor."},
                {"id": "deployment", "class": "deployment_receipt", "custody_state": "archived_repo", "archive_scope_ids": ["pages"], "claim_boundary": "Deployment donor."},
            ],
            "gaps": [
                {"id": "goldens", "class": "visual_golden", "state": "open", "required_for_close": True, "target": "Recover goldens.", "admission": "Hash them.", "failure_mode": "They disappear."}
            ],
            "canonical_task_count_effect": "none",
        }
        self.observed = {
            "schema": "axm-tools/manzanita-observed-execution-ledger@1",
            "constitutional_source_state": "original_row_level_register_unavailable",
            "records": [{"pull_request": 1, "state": "merged_observed", "canonical_task_count_effect": "none"}],
            "external_campaign_state": {"release_state": "HOLD", "passed_campaigns": [], "not_performed_campaigns": [f"c{i}" for i in range(10)], "public_release_authorized": False},
            "canonical_task_count_effect": "none",
        }
        write_json(self.contract_path, self.contract)
        write_json(self.register_path, self.register)
        write_json(self.observed_path, self.observed)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self):
        value = build_custody.build_manifest(self.root, self.contract_path, self.register_path, self.observed_path, self.manifest_path)
        write_json(self.manifest_path, value)
        return value

    def validate(self, complete=False):
        contract, contract_raw = validate_custody.load_json(self.contract_path)
        register, register_raw = validate_custody.load_json(self.register_path)
        observed, observed_raw = validate_custody.load_json(self.observed_path)
        manifest, _ = validate_custody.load_json(self.manifest_path)
        required = validate_custody.validate_contract(contract)
        validate_custody.validate_register(register, contract, required)
        validate_custody.validate_observed(observed)
        validate_custody.validate_manifest(self.root, contract, contract_raw, register, register_raw, observed_raw, manifest, complete)

    def test_manifest_is_deterministic_and_partial(self):
        first = self.build()
        first_bytes = self.manifest_path.read_bytes()
        second = self.build()
        self.assertEqual(first_bytes, self.manifest_path.read_bytes())
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(first["status"], "PARTIAL")
        self.validate()

    def test_source_tamper_is_detected(self):
        self.build()
        write(self.root / "manzanita-next/source.txt", "changed\n")
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "Byte count changed|SHA-256 changed"):
            self.validate()

    def test_public_route_tamper_is_detected(self):
        self.build()
        write(self.root / "manzanita/index.html", "replacement\n")
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "Historical public route changed"):
            self.validate()

    def test_false_closure_is_rejected(self):
        closed = copy.deepcopy(self.register)
        closed["state"] = "closed"
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "cannot close"):
            validate_custody.validate_register(closed, self.contract, set(self.contract["required_classes"]))

    def test_require_complete_rejects_partial(self):
        self.build()
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "remains partial"):
            self.validate(complete=True)

    def test_workflow_filter_excludes_unrelated_workflows(self):
        manifest = self.build()
        paths = {row["path"] for row in manifest["files"]}
        self.assertIn(".github/workflows/manzanita-one.yml", paths)
        self.assertNotIn(".github/workflows/other.yml", paths)

    def test_observed_ledger_cannot_invent_passed_campaign(self):
        value = copy.deepcopy(self.observed)
        value["external_campaign_state"]["passed_campaigns"] = ["c0"]
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "invents"):
            validate_custody.validate_observed(value)

    def test_manifest_excludes_itself(self):
        manifest = self.build()
        self.assertNotIn("programs/manzanita-99/custody/CUSTODY_MANIFEST.json", {row["path"] for row in manifest["files"]})

    def test_missing_class_coverage_is_rejected(self):
        register = copy.deepcopy(self.register)
        register["gaps"] = []
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "lack donor or gap coverage"):
            validate_custody.validate_register(register, self.contract, set(self.contract["required_classes"]))

    @unittest.skipIf(os.name == "nt", "Symlink creation requires POSIX test privileges")
    def test_scope_symlink_is_rejected_before_resolution(self):
        link = self.root / "manzanita-next/source-link.txt"
        link.symlink_to(self.root / "manzanita-next/source.txt")
        with self.assertRaisesRegex(build_custody.CustodyBuildError, "symbolic link"):
            self.build()

    @unittest.skipIf(os.name == "nt", "Symlink creation requires POSIX test privileges")
    def test_manifest_source_replaced_by_symlink_is_rejected(self):
        self.build()
        source = self.root / "manzanita-next/source.txt"
        replacement = self.root / "replacement.txt"
        replacement.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        source.unlink()
        source.symlink_to(replacement)
        with self.assertRaisesRegex(validate_custody.CustodyValidationError, "symbolic link"):
            self.validate()

    def test_current_source_foundation_uses_successor_scope(self):
        package_register = json.loads((Path(__file__).resolve().parents[1] / "DONOR_REGISTER.json").read_text(encoding="utf-8"))
        donor = next(row for row in package_register["donors"] if row["id"] == "pr-90-source_foundation")
        self.assertIn("successor-source-tree", donor["archive_scope_ids"])
        self.assertNotIn("contained-review-board", donor["archive_scope_ids"])

    def test_current_release_control_represents_generated_candidate(self):
        directory = Path(__file__).resolve().parents[1]
        package_contract = json.loads((directory / "CUSTODY_CONTRACT.json").read_text(encoding="utf-8"))
        package_register = json.loads((directory / "DONOR_REGISTER.json").read_text(encoding="utf-8"))
        donor = next(row for row in package_register["donors"] if row["id"] == "pr-109-release_control")
        self.assertEqual(donor["class"], "generated_candidate")
        represented = {row["class"] for row in package_register["donors"]}
        represented.update(row["class"] for row in package_register["gaps"])
        self.assertEqual(set(package_contract["required_classes"]) - represented, set())

    def test_history_audit_distinguishes_trees_from_releases(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "first"], cwd=self.root, check=True, capture_output=True)
        write(self.root / "manzanita/index.html", "second\n")
        subprocess.run(["git", "add", "manzanita/index.html"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "second"], cwd=self.root, check=True, capture_output=True)
        value = audit_history.audit(self.root)
        self.assertEqual(value["unique_historical_public_route_tree_count"], 2)
        self.assertIn("not automatically an approved release", value["classification_boundary"])


if __name__ == "__main__":
    unittest.main()
