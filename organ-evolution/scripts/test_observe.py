#!/usr/bin/env python3
"""Stdlib regression tests for the neutral estate observation compiler."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
SPEC = importlib.util.spec_from_file_location("observe", HERE / "observe.py")
observe = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = observe
SPEC.loader.exec_module(observe)


class ObserveTests(unittest.TestCase):
    def setUp(self) -> None:
        fixtures = TOOL / "data" / "fixtures"
        self.sources = observe.load_json(fixtures / "sources.fixture.json", observe.SOURCES_FORMAT)
        self.local = observe.load_json(fixtures / "observed.fixture.json", observe.LOCAL_FORMAT)
        self.fixture = observe.load_json(fixtures / "github.fixture.json")
        self.now = observe.parse_time("2026-07-28T00:00:00Z")
        assert self.now

    def compile(self, now=None):
        return observe.compile_observations(
            self.sources,
            self.local,
            observe.FixtureProvider(self.fixture),
            now or self.now,
        )

    def test_compiles_neutral_observation_product(self):
        result = self.compile()
        self.assertEqual(result["format"], observe.FORMAT)
        self.assertEqual(len(result["organs"]), 2)
        self.assertEqual(result["unavailable"], [])
        self.assertTrue(result["sourceDigest"].startswith("organobs1_"))
        self.assertNotIn("decision", json.dumps(result))
        self.assertNotIn('"gates"', json.dumps(result))
        self.assertNotIn('"dimensions"', json.dumps(result))
        self.assertNotIn('"health"', json.dumps(result))

    def test_findings_keep_failure_and_succession_gap_visible(self):
        result = self.compile()
        blood = next(row for row in result["organs"] if row["organId"] == "organ.bloodstream")
        codes = {row["code"] for row in blood["findings"]}
        self.assertIn("workflow_not_green", codes)
        self.assertIn("succession_record_absent", codes)
        self.assertIn("stale_draft_pr", codes)
        self.assertIn("release_tag_absent", codes)

    def test_local_observation_remains_attributed_and_limited(self):
        result = self.compile()
        blood = next(row for row in result["organs"] if row["organId"] == "organ.bloodstream")
        row = blood["localObservations"][0]
        self.assertEqual(row["source"], "operator restart receipt")
        self.assertEqual(row["limits"], "One workstation and one ledger only.")
        self.assertEqual(row["evidenceRefs"], ["local://bloodstream/restart-001"])

    def test_source_digest_excludes_collection_time_only(self):
        first = self.compile(observe.parse_time("2026-07-28T00:00:00Z"))
        second = self.compile(observe.parse_time("2026-07-28T00:05:00Z"))
        self.assertNotEqual(first["generatedAt"], second["generatedAt"])
        self.assertEqual(first["sourceDigest"], second["sourceDigest"])

    def test_unavailable_repository_is_a_visible_fact(self):
        fixture = json.loads(json.dumps(self.fixture))
        fixture["repositories"]["BigBirdReturns/axm-bloodstream"] = {"error": "fixture outage"}
        result = observe.compile_observations(
            self.sources,
            self.local,
            observe.FixtureProvider(fixture),
            self.now,
        )
        self.assertEqual(len(result["unavailable"]), 1)
        blood = next(row for row in result["organs"] if row["organId"] == "organ.bloodstream")
        self.assertEqual(blood["findings"][0]["code"], "repository_unavailable")

    def test_duplicate_keys_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"format":"x","format":"y"}', encoding="utf-8")
            with self.assertRaises(observe.ObservationError):
                observe.load_json(path)

    def test_output_json_and_javascript_are_exact_twins(self):
        result = self.compile()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "observations.json"
            js_output = root / "observations.js"
            observe.write_outputs(result, output, js_output)
            parsed = json.loads(output.read_text(encoding="utf-8"))
            js = js_output.read_text(encoding="utf-8")
            self.assertEqual(parsed, result)
            self.assertTrue(js.startswith("window.AXM_ORGAN_OBSERVATIONS = "))
            self.assertTrue(js.rstrip().endswith(";"))
            self.assertEqual(json.loads(js[len("window.AXM_ORGAN_OBSERVATIONS = "):].rstrip()[:-1]), result)

    def test_production_source_map_matches_the_declared_estate(self):
        production_sources = observe.load_json(TOOL / "data" / "sources.json", observe.SOURCES_FORMAT)
        production_local = observe.load_json(TOOL / "data" / "observed.json", observe.LOCAL_FORMAT)
        source_rows, _ = observe.validate_sources(production_sources)
        declared = {
            "organ.genesis", "organ.core", "organ.embodied", "organ.bloodstream",
            "organ.hinge", "organ.tierbench", "organ.arc", "organ.world", "organ.tools",
        }
        mapped = {row["organId"] for row in source_rows}
        self.assertEqual(mapped, declared)
        self.assertEqual(observe.validate_local(production_local, declared), [])

    def test_committed_observation_projections_are_exact_and_non_authoritative(self):
        observed = observe.load_json(TOOL / "data" / "observations.json", observe.FORMAT)
        observe.assert_no_authority_mutation(observed)
        js = (TOOL / "data" / "observations.js").read_text(encoding="utf-8")
        self.assertTrue(js.startswith("window.AXM_ORGAN_OBSERVATIONS = "))
        self.assertEqual(json.loads(js[len("window.AXM_ORGAN_OBSERVATIONS = "):].rstrip()[:-1]), observed)


if __name__ == "__main__":
    unittest.main()
