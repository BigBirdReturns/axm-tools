"""End-to-end witness-to-witness acceptance against fresh local evidence vaults."""
import argparse
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from decision_floor.cli import execute
from decision_floor import peer

ROOT = Path(__file__).resolve().parents[1]
SCOPE = {"site": "PLANT-07", "sku": "VALVE-P204", "period": "2026-10"}
FIELDS = ["kind", "record_id", "quantity", "occurred_at", "recorded_at",
          "source_digest", "locator"]


class PeerExchange(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="df-bilateral-")
        self.root = Path(self.tmp.name)
        self.a = self.root / "a"
        self.b = self.root / "b"
        peer.init_party(self.a, "supplierA")
        peer.init_party(self.b, "buyerB")
        peer.trust_peer(self.a, "buyerB", self.b / "public.pem")
        peer.trust_peer(self.b, "supplierA", self.a / "public.pem")
        for own, other in [(self.a, "buyerB"), (self.b, "supplierA")]:
            peer.install_contract(own, {
                "schema": peer.CONTRACT_SCHEMA, "contract_id": "contract-Q4",
                "party": ("supplierA" if own == self.a else "buyerB"),
                "counterparty": other, "scope": SCOPE,
                "allowed_kinds": ["decision", "commitment", "floor"],
                "allowed_fields": FIELDS, "max_records": 50})
        for party in (self.a, self.b):
            src = party / "incoming"
            shutil.copytree(ROOT / "sample_inputs" / "missed", src)
        # Two independently held versions of the exact same PO revision.
        p = self.b / "incoming" / "procurement_po.csv"
        s = p.read_text()
        assert "PO-908-2,PLANT-07,VALVE-P204,2026-10,12000," in s
        p.write_text(s.replace("PO-908-2,PLANT-07,VALVE-P204,2026-10,12000,",
                               "PO-908-2,PLANT-07,VALVE-P204,2026-10,7000,"))
        for party in (self.a, self.b):
            args = argparse.Namespace(input=str(party / "incoming"),
                config=str(ROOT / "config" / "sources.json"),
                workspace=str(party / "state"), out=str(party / "report"),
                as_of=None)
            result = execute(args)
            self.assertEqual(result["verification"]["status"], "PASS")

    def tearDown(self):
        self.tmp.cleanup()

    def _a_packet(self):
        result = peer.export_events(self.a, self.a / "state", "contract-Q4")
        packet = Path(result["file"])
        return result, packet

    def test_bilateral_claims_reconcile_review_and_replay(self):
        result, packet = self._a_packet()
        self.assertEqual(result["source_bytes_disclosed"], 0)
        body = packet.read_text()
        for sensitive in ("Verbatim_Promise", "Supplier release", "source_original", "Original sales-led"):
            self.assertNotIn(sensitive, body)
        receive = peer.receive(self.b, packet, self.b / "state")
        self.assertEqual(receive["status"], "VERIFIED_REVIEW_REQUIRED")
        contradicted = [f for f in receive["findings"] if f["state"] == "CONTRADICTORY_RECORDED_VALUE"]
        self.assertEqual([f["record_id"] for f in contradicted], ["PO-908-2"])
        self.assertGreaterEqual(len([f for f in receive["findings"]
                                      if f["state"] == "CORROBORATED_VALUE"]), 3)
        self.assertEqual(peer.receive(self.b, packet, self.b / "state")["status"], "DUPLICATE")
        reply = peer.respond(self.b, receive["packet_id"], "contested", "Procurement controller")
        back = peer.receive(self.a, Path(reply["file"]), self.a / "state")
        self.assertEqual(back["message_type"], "review")
        self.assertEqual(back["findings"][0]["disposition"], "contested")
        # A new packet from A links back to its predecessor without replaying it.
        more = peer.export_events(self.a, self.a / "state", "contract-Q4")
        p2 = json.loads(Path(more["file"]).read_text())
        self.assertEqual(p2["payload"]["predecessor"], result["packet_id"])
        self.assertEqual(peer.receive(self.b, Path(more["file"]), self.b / "state")["status"],
                         "VERIFIED_REVIEW_REQUIRED")

    def test_signature_refuses_tamper_even_when_hash_updated(self):
        _, file = self._a_packet()
        pkt = json.loads(file.read_text())
        pkt["payload"]["claims"][0]["quantity"] = 123456
        pkt["payload_sha256"] = peer._sha(peer._canonical(pkt["payload"]))
        tamper = self.root / "tamper.json"
        tamper.write_bytes(peer._canonical(pkt))
        with self.assertRaises(ValueError):
            peer.receive(self.b, tamper, self.b / "state")
        self.assertEqual(list((self.b / "inbox").glob("*.json")) if (self.b / "inbox").exists() else [], [])

    def test_signature_refuses_wrong_key_and_scope(self):
        _, file = self._a_packet()
        pkt = json.loads(file.read_text())
        pkt["public_fingerprint"] = "0" * 64
        forgery = self.root / "forgery.json"
        forgery.write_bytes(peer._canonical(pkt))
        with self.assertRaisesRegex(ValueError, "not pinned"):
            peer.receive(self.b, forgery)
        p = json.loads(file.read_text())
        p["payload"]["scope"]["sku"] = "DIFFERENT-SKU"
        scope = self.root / "wrong-scope.json"
        scope.write_bytes(peer._canonical(p))
        with self.assertRaisesRegex(ValueError, "Scope outside"):
            peer.receive(self.b, scope)

    def test_case_policy_and_explicit_trust_cannot_drift(self):
        with self.assertRaises(ValueError):
            peer.trust_peer(self.a, "buyerB", self.a / "public.pem")
        contract = peer._contract(self.a, "contract-Q4")
        contract["allowed_kinds"] = ["decision"]
        with self.assertRaises(ValueError):
            peer.install_contract(self.a, contract)
        contract = peer._contract(self.a, "contract-Q4")
        contract["allowed_fields"] = FIELDS + ["notes"]
        with self.assertRaises(ValueError):
            peer.install_contract(self.a, contract)

    def test_source_alteration_refuses_export(self):
        _, packet = self._a_packet()
        claim = json.loads(packet.read_text())["payload"]["claims"][0]
        obj = self.a / "state" / "vault" / "objects" / claim["source_digest"]
        obj.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "missing or altered"):
            peer.export_events(self.a, self.a / "state", "contract-Q4")

    def test_peer_exchange_works_without_network_socket(self):
        def disabled(*args, **kwargs):
            raise AssertionError("Network socket attempted")
        with patch.object(socket, "socket", side_effect=disabled):
            _, file = self._a_packet()
            result = peer.receive(self.b, file, self.b / "state")
        self.assertEqual(result["status"], "VERIFIED_REVIEW_REQUIRED")

    def test_strict_cross_contract_and_missing_predecessor(self):
        _, file = self._a_packet()
        original = json.loads(file.read_text())
        payload = dict(original["payload"])
        payload["predecessor"] = "f" * 64
        packet = peer._envelope(self.a, payload)
        foreign = self.root / "predecessor.json"
        foreign.write_bytes(peer._canonical(packet))
        with self.assertRaisesRegex(ValueError, "chain gap or fork"):
            peer.receive(self.b, foreign, self.b / "state")
        with self.assertRaises(FileExistsError):
            peer.init_party(self.a, "supplierA")

    def test_signed_branch_fork_is_refused(self):
        original, first = self._a_packet()
        self.assertIn("VERIFIED", peer.receive(self.b, first, self.b / "state")["status"])
        branch = dict(json.loads(first.read_text())["payload"])
        branch["nonce"] = "a" * 24
        branch["predecessor"] = None
        fork = peer._envelope(self.a, branch)
        other = self.root / "signed-fork.json"
        other.write_bytes(peer._canonical(fork))
        with self.assertRaisesRegex(ValueError, "chain gap or fork"):
            peer.receive(self.b, other, self.b / "state")

    def test_recorded_timestamp_scope_prevents_fictitious_hindsight(self):
        # Existing investigator replay remains the authority; exchange carries
        # source-recorded clocks without projecting future rows backward.
        _, file = self._a_packet()
        payload = json.loads(file.read_text())["payload"]
        d = next(r for r in payload["claims"] if r["record_id"] == "SOP-017")
        self.assertEqual(d["quantity"], 7000)
        self.assertEqual(d["recorded_at"], "2026-10-06T18:08:00+00:00")
        self.assertLess(d["occurred_at"], d["recorded_at"])


if __name__ == "__main__":
    unittest.main()
