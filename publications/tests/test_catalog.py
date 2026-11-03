from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("publication_catalog", Path(__file__).resolve().parents[1] / "scripts/catalog.py")
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "source"
        self.data.mkdir()
        self.fixture = json.loads((Path(__file__).parent / "fixtures/synthetic-catalog.json").read_text())
        self.path = self.data / "catalog.json"
        self.write(self.fixture)

    def write(self, value):
        self.path.write_bytes(catalog.encoded(value))

    def test_upstream_export_contract_and_standalone_render(self):
        value, files = catalog.load_catalog(self.path)
        self.assertEqual(len(value["entries"]), 1)
        self.assertEqual(set(files), {"catalog.json"})
        body = catalog.render(value).decode()
        self.assertIn(value["entries"][0]["canonical_url"], body)
        self.assertNotIn("<script", body)

    def test_candidate_does_not_appear_as_published(self):
        self.fixture["entries"][0]["state"] = "candidate"
        self.write(self.fixture)
        with self.assertRaisesRegex(catalog.CatalogError, "published_entry_required"):
            catalog.load_catalog(self.path)

    def test_archive_import_is_distinct_from_pipeline_release(self):
        self.fixture["entries"][0]["release"]["evidence_kind"] = "OBSERVED_EXISTING_PUBLICATION"
        self.write(self.fixture)
        value, _ = catalog.load_catalog(self.path)
        self.assertIn("Archive import", catalog.render(value).decode())
        self.fixture["entries"][0]["release"]["evidence_kind"] = "unrecognized"
        self.write(self.fixture)
        with self.assertRaisesRegex(catalog.CatalogError, "unknown_release_evidence_kind"):
            catalog.load_catalog(self.path)

    def test_missing_or_wrong_revision_release_refused(self):
        row = self.fixture["entries"][0]
        row["release"]["revision"] = "f" * 64
        self.write(self.fixture)
        with self.assertRaisesRegex(catalog.CatalogError, "release_identity_mismatch"):
            catalog.load_catalog(self.path)
        row.pop("release")
        self.write(self.fixture)
        with self.assertRaises(catalog.CatalogError):
            catalog.load_catalog(self.path)

    def test_private_fields_paths_and_credentials_refused(self):
        for mutate in (
            lambda row: row.update(private_path="/mnt/private/article"),
            lambda row: row.update(title="file /mnt/private/article"),
            lambda row: row["release"].update(secret="private"),
            lambda row: row["links"][0].update(url="https://user:secret@example.test/"),
        ):
            changed = copy.deepcopy(self.fixture)
            mutate(changed["entries"][0])
            self.write(changed)
            with self.assertRaises(catalog.CatalogError):
                catalog.load_catalog(self.path)

    def test_live_readback_must_match_canonical_with_timezone(self):
        observed = self.fixture["entries"][0]["release"]["readback"]
        for key, value in (("url", "https://other.example.test/"), ("http_status", 404), ("observed_at", "2026-11-03T00:00:00")):
            old = observed[key]
            observed[key] = value
            self.write(self.fixture)
            with self.assertRaises(catalog.CatalogError):
                catalog.load_catalog(self.path)
            observed[key] = old

    def test_image_path_hash_and_exact_file_allowlist(self):
        body = b"synthetic image bytes used only to test digest custody"
        name = "assets/" + catalog.digest(body) + ".webp"
        (self.data / "assets").mkdir()
        (self.data / name).write_bytes(body)
        self.fixture["entries"][0]["feature_image"] = {"path": name, "alt": "Synthetic test"}
        self.write(self.fixture)
        _, files = catalog.load_catalog(self.path)
        self.assertEqual(files[name], body)
        (self.data / name).write_bytes(b"modified")
        with self.assertRaisesRegex(catalog.CatalogError, "asset_digest_mismatch"):
            catalog.load_catalog(self.path)
        (self.data / name).write_bytes(body)
        (self.data / "private-source.txt").write_text("not allowed")
        with self.assertRaisesRegex(catalog.CatalogError, "outside_catalog_allowlist"):
            catalog.exact_files(self.data)

    def test_symlink_asset_refused(self):
        outside = self.root / "private"
        outside.write_bytes(b"private")
        name = "assets/" + catalog.digest(b"private") + ".webp"
        (self.data / "assets").mkdir()
        (self.data / name).symlink_to(outside)
        self.fixture["entries"][0]["feature_image"] = {"path": name, "alt": "Test"}
        self.write(self.fixture)
        with self.assertRaisesRegex(catalog.CatalogError, "regular_bounded_file_required"):
            catalog.load_catalog(self.path)

    def test_import_exact_rerun_and_guarded_conflict(self):
        destination = self.root / "destination"
        first = catalog.import_catalog(self.data, destination, expected_current_sha="absent")
        self.assertEqual(first["state"], "imported")
        second = catalog.import_catalog(self.data, destination, expected_current_sha=first["catalog_sha256"])
        self.assertEqual(second["state"], "unchanged")
        before = (destination / "catalog.json").read_bytes()
        with self.assertRaisesRegex(catalog.CatalogError, "changed_since_review"):
            catalog.import_catalog(self.data, destination, expected_current_sha="0" * 64)
        self.assertEqual((destination / "catalog.json").read_bytes(), before)

    def test_active_or_uncertain_writer_retained(self):
        destination = self.root / "destination"
        lock = self.root / ".destination-import.lock"
        lock.write_text("retained")
        with self.assertRaisesRegex(catalog.CatalogError, "active_or_uncertain"):
            catalog.import_catalog(self.data, destination, expected_current_sha="absent")
        self.assertEqual(lock.read_text(), "retained")

    def test_symlink_destination_parent_is_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(catalog.CatalogError, "symlink_catalog_path"):
            catalog.import_catalog(self.data, alias / "data", expected_current_sha="absent")
        self.assertEqual(list(outside.iterdir()), [])

    def test_html_is_escaped_and_empty_catalog_is_honest(self):
        value = copy.deepcopy(self.fixture)
        value["entries"][0]["title"] = '<script>alert("injection")</script>'
        rendered = catalog.render(value).decode()
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        empty = catalog.render({"schema": "publication-catalog/0.1", "entries": []}).decode()
        self.assertIn("Explore the essay archive", empty)
        self.assertNotIn("<article>", empty)


if __name__ == "__main__":
    unittest.main()
