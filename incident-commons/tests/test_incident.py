# SPDX-License-Identifier: Apache-2.0
import json
import sys
import unittest
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import incident as ir


class IncidentCommonsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / "examples" / "synthetic-identity-export.jsonl").read_bytes()
        cls.events = ir.read_events(cls.raw)

    def test_valid_case(self):
        case = ir.case_for(self.raw, "SYNTH-001")
        self.assertEqual(case["event_count"], 13)
        self.assertEqual(ir.verify_case(case)["status"], "PASS")
        self.assertEqual(case["source_sha256"], ir.sha(self.raw))

    def test_detection_all_correlated(self):
        f = ir.analyze_events(self.events)
        rules = {row["rule"] for row in f}
        self.assertTrue({"PASSWORD_SPRAY", "LOGIN_AFTER_FAILURES",
                         "IDENTITY_PERSISTENCE", "TOKEN_TO_EXPORT",
                         "UNTRUSTED_PAYLOAD"}.issubset(rules))
        self.assertTrue(all(set(row["evidence_ids"]).issubset(
            {e["id"] for e in self.events}) for row in f))

    def test_tenants_isolated(self):
        f = ir.analyze_events(self.events)
        for finding in f:
            tenants = {e["tenant"] for e in self.events
                       if e["id"] in finding["evidence_ids"]}
            self.assertEqual(len(tenants), 1)

    def test_untrusted_text_is_not_execution(self):
        f = ir.analyze_events(self.events)
        self.assertTrue(any(x["rule"] == "UNTRUSTED_PAYLOAD" for x in f))
        self.assertTrue(all(x["authority"] == "REQUIRES_ORGANIZATION_APPROVAL" for x in f))

    def test_degraded_non_matching_event_not_invented(self):
        lone = [{"id": "test", "ts": "2026-11-16T00:00:00Z",
                 "tenant": "alpha", "kind": "auth_success", "actor": "a",
                 "src": "192.0.2.2", "target": "sso", "outcome": "success"}]
        self.assertEqual(ir.analyze_events(lone), [])

    def test_duplicate_rejected(self):
        data = self.raw + self.raw.splitlines()[0] + b"\n"
        with self.assertRaisesRegex(ir.Refusal, "DUPLICATE_OR_INVALID_ID"):
            ir.read_events(data)

    def test_bad_event_kind_rejected(self):
        data = json.dumps([{**self.events[0], "kind": "sudo rm -rf /"}]).encode()
        with self.assertRaisesRegex(ir.Refusal, "UNKNOWN_KIND"):
            ir.read_events(data)

    def test_invalid_timestamps_rejected(self):
        data = json.dumps([{**self.events[0], "ts": "2026-11-16T12:00:00"}]).encode()
        with self.assertRaisesRegex(ir.Refusal, "BAD_TIMESTAMP"):
            ir.read_events(data)

    def test_oversize_refused(self):
        with self.assertRaisesRegex(ir.Refusal, "SIZE_LIMIT"):
            ir.read_events(b"x" * (ir.MAX_BYTES + 1))

    def test_missing_field_refused(self):
        d = dict(self.events[0]); del d["actor"]
        with self.assertRaisesRegex(ir.Refusal, "REQUIRED_FIELD"):
            ir.read_events(json.dumps([d]).encode())

    def test_boolean_byte_count_refused(self):
        d = dict(self.events[0]); d["bytes_out"] = True
        with self.assertRaisesRegex(ir.Refusal, "BAD_BYTE_COUNT"):
            ir.read_events(json.dumps([d]).encode())

    def test_case_tamper_refused(self):
        case = ir.case_for(self.raw, "SYNTH-001")
        case["events"][0]["actor"] = "attacker-substitution"
        with self.assertRaisesRegex(ir.Refusal, "CASE_TAMPER"):
            ir.verify_case(case)

    def test_orphan_reference_refused_even_with_valid_digest(self):
        case = ir.case_for(self.raw, "SYNTH-001")
        case["findings"][0]["evidence_ids"].append("ghost-event")
        case["sha256"] = ir.sha(ir.canonical({k:v for k,v in case.items() if k != "sha256"}).encode())
        with self.assertRaisesRegex(ir.Refusal, "ORPHAN_EVIDENCE"):
            ir.verify_case(case)

    def test_share_preview_excludes_sensitive_data(self):
        packet = ir.public_preview(ir.case_for(self.raw, "SYNTH-001"))
        text = ir.canonical(packet)
        for forbidden in ("203.0.113", "analyst-a", "svc-payments",
                          "customer-dataset", "ev-001", "production-secret-store"):
            self.assertNotIn(forbidden, text)
        self.assertFalse(packet["source_attested"])

    def test_attacks_at_time_distance_do_not_correlate(self):
        copies = [dict(self.events[0]), dict(self.events[1]),
                  dict(self.events[2]), dict(self.events[3]), dict(self.events[4])]
        for i,e in enumerate(copies):
            e["ts"] = f"2026-11-16T{str(i*2).zfill(2)}:00:00Z"
        self.assertFalse(any(f["rule"] == "PASSWORD_SPRAY" for f in ir.analyze_events(copies)))

    def test_failed_token_without_export_not_exfil(self):
        subset = [e for e in self.events if e["kind"] in ("auth_failure", "token_created")]
        self.assertFalse(any(f["rule"] == "TOKEN_TO_EXPORT" for f in ir.analyze_events(subset)))

    def test_json_array_import_supported(self):
        data = json.dumps(self.events).encode()
        self.assertEqual(len(ir.read_events(data)), len(self.events))


if __name__ == "__main__":
    unittest.main(verbosity=2)
