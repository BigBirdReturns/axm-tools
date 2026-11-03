from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from integration import pages_publication as pages


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        (self.root / "index.html").write_text("<h1>Toolbox</h1>\n")
        (self.root / "publications").mkdir()
        (self.root / "publications/index.html").write_text("<h1>Publications</h1>\n")
        (self.root / ".private").write_text("never stage")
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__/x.pyc").write_bytes(b"ignored")
        for args in (("init",), ("add", "index.html", "publications/index.html"), ("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "fixture")):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.head = pages.git(self.root, "rev-parse", "HEAD")
        self.context = {"repository": "owner/repo", "trigger_sha": "a" * 40, "run_id": "123", "run_attempt": "2", "artifact_name": "github-pages-123-2", "workflow": "fixture"}
        self.stage = self.base / "stage"
        self.receipt_path = self.base / "receipt.json"

    def prepared(self):
        return pages.prepare(self.root, self.stage, self.receipt_path, context=self.context, check_current=False)

    def archive(self, stage=None):
        archive = self.base / "artifact.tar"
        with tarfile.open(archive, "w") as bundle:
            bundle.add(stage or self.stage, arcname=".")
        return archive

    def bound(self):
        receipt = self.prepared()
        artifact = {"id": 456, "name": receipt["artifact_name"], "workflow_run": {"id": 123}, "digest": "sha256:" + "d" * 64, "size_in_bytes": 900}
        return pages.bind_artifact(receipt, self.archive(), artifact)

    def test_trigger_revision_and_built_revision_remain_distinct(self):
        receipt = self.prepared()
        self.assertEqual(receipt["trigger_sha"], "a" * 40)
        self.assertEqual(receipt["built_sha"], self.head)
        self.assertNotEqual(receipt["trigger_sha"], receipt["built_sha"])
        self.assertEqual(receipt["source_sha"], receipt["trigger_sha"])
        self.assertFalse((self.stage / ".private").exists())
        self.assertFalse((self.stage / "__pycache__").exists())
        self.assertEqual(json.loads((self.stage / pages.MARKER).read_text())["built_sha"], self.head)

    def test_same_input_produces_same_marker_and_tree_identity(self):
        first = self.prepared()
        second = pages.prepare(self.root, self.base / "other-stage", self.base / "other-receipt.json", context=self.context, check_current=False)
        self.assertEqual(first, second)

    def test_existing_stage_is_retained(self):
        self.prepared()
        with self.assertRaisesRegex(pages.PublicationError, "stage_exists"):
            self.prepared()

    def test_nested_stage_and_private_receipt_are_refused(self):
        with self.assertRaises(pages.PublicationError):
            pages.prepare(self.root, self.root / "stage", self.receipt_path, context=self.context)
        with self.assertRaises(pages.PublicationError):
            pages.prepare(self.root, self.stage, self.stage / "receipt.json", context=self.context)

    def test_external_symlink_cannot_enter_public_tree(self):
        (self.root / "linked").symlink_to(self.base)
        with self.assertRaisesRegex(pages.PublicationError, "symlink"):
            self.prepared()

    def test_marker_cannot_be_replaced_by_source(self):
        (self.root / pages.MARKER).write_text("{}");
        with self.assertRaisesRegex(pages.PublicationError, "reserved"):
            self.prepared()

    def test_archive_content_must_match_every_staged_byte(self):
        receipt = self.prepared()
        (self.stage / "index.html").write_text("unexpected edit")
        with self.assertRaisesRegex(pages.PublicationError, "archive_content_mismatch"):
            pages.verify_archive(self.archive(), receipt["files"])

    def test_archive_extra_or_missing_file_refused(self):
        receipt = self.prepared()
        (self.stage / "private.txt").write_text("unexpected")
        with self.assertRaisesRegex(pages.PublicationError, "unexpected_archive_member"):
            pages.verify_archive(self.archive(), receipt["files"])
        (self.stage / "private.txt").unlink()
        (self.stage / "index.html").unlink()
        with self.assertRaisesRegex(pages.PublicationError, "archive_missing_files"):
            pages.verify_archive(self.archive(), receipt["files"])

    def test_archive_symlinks_refused(self):
        receipt = self.prepared()
        archive = self.archive()
        with tarfile.open(archive, "a") as bundle:
            entry = tarfile.TarInfo("unexpected-link")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "/private"
            bundle.addfile(entry)
        with self.assertRaisesRegex(pages.PublicationError, "unexpected_archive_member"):
            pages.verify_archive(archive, receipt["files"])

    def test_artifact_binding_uses_actual_provider_identity_and_two_digests(self):
        receipt = self.bound()
        self.assertEqual(receipt["artifact"]["id"], 456)
        self.assertEqual(receipt["artifact"]["provider_digest"], "sha256:" + "d" * 64)
        self.assertEqual(receipt["artifact"]["tar"]["sha256"], pages.file_digest(self.base / "artifact.tar"))
        self.assertEqual(receipt["state"], "UPLOADED_ARTIFACT_VERIFIED")

    def test_wrong_workflow_artifact_or_missing_digest_refused(self):
        receipt = self.prepared()
        archive = self.archive()
        artifact = {"id": 2, "name": receipt["artifact_name"], "workflow_run": {"id": 999}, "digest": "sha256:" + "d" * 64}
        with self.assertRaisesRegex(pages.PublicationError, "artifact_run_mismatch"):
            pages.bind_artifact(receipt, archive, artifact)
        artifact["workflow_run"]["id"] = 123
        artifact.pop("digest")
        with self.assertRaisesRegex(pages.PublicationError, "provider_digest_missing"):
            pages.bind_artifact(receipt, archive, artifact)

    def test_live_readback_requires_marker_and_indexes(self):
        receipt = self.bound()
        def fetch(url):
            relative = url.split("/site/", 1)[1].split("?", 1)[0]
            return (self.stage / relative).read_bytes()
        result = pages.verify_live(receipt, "https://example.test/site/", fetch, attempts=1)
        self.assertEqual([row["path"] for row in result["checks"]], [pages.MARKER, "index.html", "publications/index.html"])
        with self.assertRaisesRegex(pages.PublicationError, "live_readback_failed"):
            pages.verify_live(receipt, "https://example.test/site/", lambda url: b"stale", attempts=2, sleep=lambda _: None)

    def test_deployment_id_requires_same_run_and_trigger(self):
        receipt = self.bound()
        deployment = {"id": 987, "sha": receipt["trigger_sha"], "environment": "github-pages", "url": "https://api.github.com/repos/owner/repo/deployments/987"}
        status = {"state": "in_progress", "log_url": "https://github.com/owner/repo/actions/runs/123/job/5"}
        result = pages.matching_deployment(receipt, [deployment], lambda _: [status])
        self.assertEqual(result["id"], 987)
        self.assertEqual(result["kind"], "github-environment-deployment")
        status["log_url"] = "https://github.com/owner/repo/actions/runs/1234/job/5"
        with self.assertRaisesRegex(pages.PublicationError, "identity_unresolved"):
            pages.matching_deployment(receipt, [deployment], lambda _: [status])

    def test_current_source_guard_refuses_remote_advance(self):
        with patch.object(pages, "git", side_effect=[self.head, "b" * 40 + "\trefs/heads/main"]):
            with self.assertRaisesRegex(pages.PublicationError, "source_advanced"):
                pages.assert_current(self.root)

    def test_receipt_commit_requires_observed_live_state(self):
        self.prepared()
        with self.assertRaisesRegex(pages.PublicationError, "live_acceptance_required"):
            pages.commit_receipt(self.root, self.receipt_path, self.base / "worktree")


if __name__ == "__main__":
    unittest.main()
