"""Focused proof-boundary tests; fixtures are synthetic and remain temporary."""
from __future__ import annotations

import copy
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

APP = Path(__file__).resolve().parents[1] / "app" / "studio.py"
SPEC = importlib.util.spec_from_file_location("research_studio", APP)
studio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(studio)


class StudioBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "record.json"
        self.source.write_text('{"attempted": 7, "completed": 5}', encoding="utf-8")
        self.pin = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.catalog_path = self.root / "catalog.json"
        self.spec_path = self.root / "spec.json"
        self.spec = {
            "read_roots": [str(self.root)],
            "sources": [{"id": "record-1", "title": "Synthetic retained record",
                         "path": str(self.source), "kind": "recorded_report",
                         "expected_sha256": self.pin,
                         "extract": {"attempted": "/attempted", "completed": "/completed"}}],
            "catalog": {"title": "Boundary-test fixture", "sources": [],
                        "components": [], "lineage": [], "gaps": [], "vendors": [],
                        "campaigns": [{"id": "run-a", "title": "Synthetic campaign",
                                       "record_class": "recorded_report", "source_ref": "record-1",
                                       "derive": {"attempted": {"source_ref": "record-1", "field": "attempted"},
                                                  "completed": {"source_ref": "record-1", "field": "completed"}}}]}}

    def collect(self):
        studio.write_json(self.spec_path, self.spec)
        result = studio.collect(self.spec_path, self.catalog_path)
        return result, studio.load_json(self.catalog_path)

    def test_source_mutation_and_pin_mismatch_do_not_promote_values(self):
        result, catalog = self.collect()
        self.assertFalse(result["findings"])
        self.assertTrue(studio.verify(self.catalog_path, [self.root])["passed"])
        self.source.write_text('{"attempted": 9, "completed": 9}', encoding="utf-8")
        verification = studio.verify(self.catalog_path, [self.root])
        self.assertFalse(verification["passed"])
        self.assertEqual(verification["results"][0]["status"], "changed")
        result, changed = self.collect()
        self.assertEqual(result["unverified"], 1)
        self.assertEqual(changed["sources"][0]["status"], "unverified")
        self.assertIsNone(changed["campaigns"][0]["attempted"])
        self.assertIsNone(changed["campaigns"][0]["completed"])
        self.assertEqual(result["new_simulations"], 0)

    def test_extraction_uses_the_exact_hashed_bytes(self):
        studio.write_json(self.spec_path, self.spec)
        original_parse = studio.parse_json
        def mutate_after_read(payload):
            value = original_parse(payload)
            if isinstance(value, dict) and value.get("attempted") == 7:
                self.source.write_text('{"attempted": 99, "completed": 99}', encoding="utf-8")
            return value
        with mock.patch.object(studio, "parse_json", side_effect=mutate_after_read):
            studio.collect(self.spec_path, self.catalog_path)
        catalog = studio.load_json(self.catalog_path)
        self.assertEqual(catalog["sources"][0]["sha256"], self.pin)
        self.assertEqual(catalog["campaigns"][0]["attempted"], 7)
        self.assertFalse(studio.verify(self.catalog_path, [self.root])["passed"])

    def test_tampered_projection_cannot_pass_source_reverification(self):
        _, catalog = self.collect()
        catalog["sources"][0]["extracted"]["attempted"] = 99
        catalog["campaigns"][0]["attempted"] = 99
        studio.write_json(self.catalog_path, catalog)
        result = studio.verify(self.catalog_path, [self.root])
        self.assertFalse(result["passed"])
        self.assertEqual(result["results"][0]["status"], "derived-mismatch")

    def test_all_provenance_lists_are_checked(self):
        _, catalog = self.collect()
        catalog["components"] = [{"id": "component", "evidence_refs": ["record-1"],
                                  "source_refs": ["missing-source"]}]
        with self.assertRaisesRegex(ValueError, "unresolved source reference"):
            studio.validate_catalog(catalog)

    def test_optional_findings_keep_source_bindings_and_withhold_changed_sources(self):
        _, legacy = self.collect()
        self.assertNotIn("findings", legacy)
        studio.validate_catalog(legacy)
        document = {"title": "Synthetic documentary finding", "summary": "A bounded review.",
                    "metrics": [{"label": "Reviewed records", "value": 2, "scope": "Fixture roster"}],
                    "notes": ["Published reports have their own evidence scope."]}
        self.source.write_text(json.dumps(document), encoding="utf-8")
        self.spec["sources"][0].update(
            expected_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
            extract={key: "/" + key for key in document})
        self.spec["catalog"]["campaigns"] = []
        self.spec["catalog"]["findings"] = [{
            "id": "vendor-summary", "kind": "vendor-summary", "source_refs": ["record-1"],
            "derive": {key: {"source_ref": "record-1", "field": key} for key in document}}]
        _, catalog = self.collect()
        self.assertEqual(catalog["findings"][0]["metrics"], document["metrics"])
        self.assertTrue(studio.verify(self.catalog_path, [self.root])["passed"])
        altered = copy.deepcopy(catalog)
        altered["findings"][0]["metrics"][0]["value"] = 99
        with self.assertRaisesRegex(ValueError, "differs from its source"):
            studio.validate_catalog(altered)
        altered = copy.deepcopy(catalog)
        altered["findings"][0]["source_refs"].append("missing-source")
        with self.assertRaisesRegex(ValueError, "unresolved source reference"):
            studio.validate_catalog(altered)
        document["metrics"][0]["value"] = 3
        self.source.write_text(json.dumps(document), encoding="utf-8")
        _, changed = self.collect()
        self.assertEqual(changed["findings"][0]["status"], "source-unverified")
        for field in document:
            self.assertIsNone(changed["findings"][0][field])

    def test_native_replay_preserves_source_projection_and_context_provenance(self):
        native = {"balls": [{"traj": [[1, 2, 3], [4, 5, 6]]}], "frames": 2, "fps": 30}
        self.source.write_text(json.dumps(native), encoding="utf-8")
        self.spec["sources"][0].update(expected_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
                                        extract={"film": ""})
        campaign = self.spec["catalog"]["campaigns"][0]
        campaign["derive"] = {"replay": {"source_ref": "record-1", "field": "film"}}
        campaign["replay_context"] = {"source_refs": ["record-1"], "units": {"x": "source units", "t": "s"}}
        _, catalog = self.collect()
        self.assertEqual(catalog["campaigns"][0]["replay"], native)
        self.assertTrue(studio.verify(self.catalog_path, [self.root])["passed"])
        catalog["campaigns"][0]["replay_context"]["source_refs"] = ["missing-film"]
        with self.assertRaisesRegex(ValueError, "unresolved source reference"):
            studio.validate_catalog(catalog)
        catalog["campaigns"][0]["replay_context"]["source_refs"] = ["record-1"]
        catalog["campaigns"][0]["replay"]["frames"] = 3
        with self.assertRaisesRegex(ValueError, "trajectory length"):
            studio.validate_catalog(catalog)

    def test_vendor_documentation_does_not_count_as_execution(self):
        _, catalog = self.collect()
        vendor = {"name": "Synthetic vendor", "state": "executed",
                  "source_ref": "record-1", "execution_source_ref": "record-1"}
        catalog["vendors"] = [vendor]
        with self.assertRaisesRegex(ValueError, "verified execution_record"):
            studio.validate_catalog(catalog)
        catalog["sources"][0]["kind"] = "execution_record"
        with self.assertRaisesRegex(ValueError, "source-derived execution identity"):
            studio.validate_catalog(catalog)
        vendor["state"] = "documentation_only"
        del vendor["execution_source_ref"]
        studio.validate_catalog(catalog)

    def test_documentary_projection_binds_vendor_and_component_fields(self):
        document = {"vendor": "Synthetic vendor", "notes": ["Documentary record"], "rows": 245}
        self.source.write_text(json.dumps(document), encoding="utf-8")
        self.spec["sources"][0].update(
            expected_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
            expected_bytes=self.source.stat().st_size,
            extract={"name": "/vendor", "notes": "/notes", "rows": "/rows"})
        self.spec["catalog"]["campaigns"] = []
        self.spec["catalog"]["vendors"] = [{"id": "vendor", "state": "documentation_only",
            "derive": {key: {"source_ref": "record-1", "field": key} for key in ("name", "notes")}}]
        self.spec["catalog"]["components"] = [{"id": "catalog", "derive": {
            "row_count": {"source_ref": "record-1", "field": "rows"}}}]
        _, catalog = self.collect()
        self.assertEqual(catalog["vendors"][0]["name"], "Synthetic vendor")
        self.assertEqual(catalog["components"][0]["row_count"], 245)
        self.assertTrue(studio.verify(self.catalog_path, [self.root])["passed"])
        catalog["vendors"][0]["notes"] = ["Altered claim"]
        with self.assertRaisesRegex(ValueError, "differs from its source projection"):
            studio.validate_catalog(catalog)
        self.spec["sources"][0]["expected_bytes"] += 1
        result, catalog = self.collect()
        self.assertEqual(result["unverified"], 1)
        self.assertIsNone(catalog["vendors"][0]["name"])
        self.assertIsNone(catalog["components"][0]["row_count"])

    def test_vendor_execution_identity_is_preserved_from_source(self):
        identity = {"vendor": "Synthetic vendor", "implementation": "fixture-only",
                    "version": "0", "artifact_sha256": "a" * 64, "invocation_id": "synthetic-run"}
        self.source.write_text(json.dumps({"execution_identity": identity}), encoding="utf-8")
        self.spec["sources"][0].update(kind="execution_record",
                                       expected_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
                                       extract={"execution_identity": "/execution_identity"})
        self.spec["catalog"]["campaigns"] = []
        self.spec["catalog"]["vendors"] = [{"name": "Synthetic vendor", "state": "executed",
                                             "execution_source_ref": "record-1"}]
        _, catalog = self.collect()
        self.assertTrue(studio.verify(self.catalog_path, [self.root])["passed"])
        catalog["vendors"][0]["name"] = "Another vendor"
        with self.assertRaisesRegex(ValueError, "does not match"):
            studio.validate_catalog(catalog)

    def test_overlapping_campaigns_keep_separate_counts(self):
        second = copy.deepcopy(self.spec["catalog"]["campaigns"][0])
        second.update(id="run-a-rescored", record_class="rescoring")
        self.spec["catalog"]["campaigns"].append(second)
        result, catalog = self.collect()
        self.assertEqual([row["attempted"] for row in catalog["campaigns"]], [7, 7])
        self.assertIsNone(result["aggregate_episode_count"])
        catalog["collection"]["aggregate_episode_count"] = 14
        with self.assertRaisesRegex(ValueError, "cannot aggregate"):
            studio.validate_catalog(catalog)

    def test_pointer_rejects_noncanonical_array_indices(self):
        for path in ("/-1", "/01", "/+1", "/~2"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                studio.pointer(["first", "second"], path)

    def test_source_symlink_cannot_escape_read_roots(self):
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            link = self.root / "escape"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "outside declared read roots"):
                studio.source_path(link, [self.root])

    def test_server_is_loopback_read_only_and_revalidates_catalog(self):
        self.collect()
        before = self.catalog_path.read_bytes()
        server = studio.make_server(self.catalog_path, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        def request(method, path, host=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            headers = {"Host": host} if host else {}
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            connection.close()
            return result
        status, headers, payload = request("GET", "/api/catalog")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["schema"], studio.SCHEMA)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(request("HEAD", "/api/catalog")[2], b"")
        self.assertEqual(request("GET", "/api/catalog", "external.example")[0], 403)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(request(method, "/api/catalog")[0], 405)
        self.assertEqual(self.catalog_path.read_bytes(), before)
        self.assertEqual(request("GET", "/../studio.py")[0], 404)
        self.catalog_path.write_text('{"schema":"invalid"}', encoding="utf-8")
        self.assertEqual(request("GET", "/api/catalog")[0], 503)

    def test_fresh_service_stages_schema_before_receiving_catalog(self):
        server = studio.make_server(self.catalog_path, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def get(path):
            c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            c.request("GET", path)
            response = c.getresponse()
            result = response.status, response.read()
            c.close()
            return result
        status, body = get("/health")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["catalog_present"])
        self.assertEqual(get("/api/catalog")[0], 503)
        self.assertFalse(self.catalog_path.exists())
        self.collect()
        self.assertEqual(get("/api/catalog")[0], 200)
        self.assertTrue(json.loads(get("/health")[1])["catalog_present"])


if __name__ == "__main__":
    unittest.main()
