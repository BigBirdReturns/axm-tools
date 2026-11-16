"""Deterministic host-local acceptance tests. No GPU or outbound network required."""
from __future__ import annotations
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sovereign import (Registry, Ledger, Refusal, activate, revoke, rollback,
                       localhost_url, run_cli, subject, genesis_binding, verify_genesis, canonical)


def sha(b): return hashlib.sha256(b).hexdigest()


class FakeEngine(BaseHTTPRequestHandler):
    models = set(["demo-base"])
    loads = 0
    fail_load = False

    def log_message(self, *a): pass

    def respond(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path != "/v1/models":
            return self.respond(404, {})
        self.respond(200, {"data": [{"id": m} for m in sorted(type(self).models)]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(n))
        if self.path == "/v1/load_lora_adapter":
            if type(self).fail_load:
                return self.respond(503, {"error": "simulated fail"})
            type(self).loads += 1
            type(self).models.add(req["lora_name"])
            return self.respond(200, {"ok": True})
        if self.path == "/v1/unload_lora_adapter":
            type(self).models.discard(req["lora_name"])
            return self.respond(200, {"ok": True})
        return self.respond(404, {})


class Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ThreadingHTTPServer(("127.0.0.1", 0), FakeEngine)
        cls.thread = threading.Thread(target=cls.engine.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.engine.shutdown()
        cls.thread.join(timeout=3)
        cls.engine.server_close()

    def setUp(self):
        FakeEngine.models = {"demo-base"}
        FakeEngine.loads = 0
        FakeEngine.fail_load = False
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("base", "tokenizer", "adapters/quality", "adapters/finance"):
            (self.root / name).mkdir(parents=True)
        (self.root / "base" / "model.safetensors").write_bytes(b"synthetic-base")
        (self.root / "tokenizer" / "tokenizer.json").write_bytes(b"synthetic-tokenizer")
        self.cfg = {"base_model_name_or_path": "synthetic/base", "r": 8, "peft_type": "LORA"}
        for adapter in ("quality", "finance"):
            d = self.root / "adapters" / adapter
            (d / "adapter_config.json").write_text(json.dumps(self.cfg))
            (d / "adapter_model.safetensors").write_bytes(("synthetic-" + adapter).encode())
        t = sha(b"synthetic-tokenizer")
        self.template = {
            "schema": "axm/sovereign-gpu-hubs@1",
            "artifact_root": str(self.root),
            "pools": {"us-west": {
                "admin_url": f"http://127.0.0.1:{self.engine.server_port}",
                "base_model": "synthetic/base",
                "base_revision": "synthetic-fixture-revision-001",
                "served_model": "demo-base",
                "base_path": str(self.root / "base"),
                "base_files": {"model.safetensors": sha(b"synthetic-base")},
                "tokenizer_path": str(self.root / "tokenizer"),
                "tokenizer_files": {"tokenizer.json": t},
                "tokenizer_primary": "tokenizer.json",
                "tokenizer_sha256": t,
                "max_lora_rank": 16,
            }},
            "tenants": {"alpha": {
                "regions": ["us-west"], "adapters": ["quality", "finance"],
                "max_active": 1}},
            "adapters": {},
        }
        for name in ("quality", "finance"):
            d = self.root / "adapters" / name
            self.template["adapters"][name] = {
                "path": str(d), "base_model": "synthetic/base",
                "base_revision": "synthetic-fixture-revision-001",
                "tokenizer_sha256": t, "rank": 8,
                "files": {fn: sha((d / fn).read_bytes()) for fn in
                          ("adapter_config.json", "adapter_model.safetensors")},
            }
        self.registry_path = self.root / "registry.json"
        self.save()
        self.ledger = Ledger(self.root / "state" / "admissions.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.registry_path.write_text(json.dumps(self.template))

    def reg(self):
        return Registry(self.registry_path)

    def test_one_warm_base_two_adapters_with_tenant_quota(self):
        first = activate(self.reg(), self.ledger, "alpha", "quality", "us-west",
                         skip_genesis=True)
        self.assertEqual(first["status"], "ACTIVATED")
        self.assertEqual(FakeEngine.loads, 1)
        self.assertEqual(activate(self.reg(), self.ledger, "alpha", "quality", "us-west",
                                  skip_genesis=True)["status"], "ALREADY_ACTIVE")
        self.assertEqual(FakeEngine.loads, 1)
        with self.assertRaisesRegex(Refusal, "TENANT_QUOTA"):
            activate(self.reg(), self.ledger, "alpha", "finance", "us-west",
                     skip_genesis=True)
        self.assertEqual(len(self.ledger.routes()[0]), 1)
        self.assertEqual(self.ledger.events()[-1]["op"], "ACTIVATION_FAILED")
        self.assertEqual(revoke(self.ledger, "alpha", "quality", "us-west", unload=True)["status"], "REVOKED")
        self.assertEqual(activate(self.reg(), self.ledger, "alpha", "finance", "us-west",
                                  skip_genesis=True)["status"], "ACTIVATED")

    def test_region_and_tenant_isolation(self):
        with self.assertRaisesRegex(Refusal, "REGION_UNKNOWN"):
            self.reg().evaluate("alpha", "quality", "eu")
        with self.assertRaisesRegex(Refusal, "TENANT_UNKNOWN"):
            self.reg().evaluate("beta", "quality", "us-west")
        self.template["pools"]["eu"] = dict(self.template["pools"]["us-west"])
        self.save()
        with self.assertRaisesRegex(Refusal, "RESIDENCY_DENIED"):
            self.reg().evaluate("alpha", "quality", "eu")

    def test_digest_and_tokenizer_fail_closed(self):
        self.assertTrue(self.reg().evaluate("alpha", "quality", "us-west")["alias"])
        (self.root / "adapters/quality/adapter_model.safetensors").write_bytes(b"TAMPER")
        with self.assertRaisesRegex(Refusal, "HASH_MISMATCH"):
            self.reg().evaluate("alpha", "quality", "us-west")
        (self.root / "adapters/quality/adapter_model.safetensors").write_bytes(b"synthetic-quality")
        self.template["adapters"]["quality"]["tokenizer_sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(Refusal, "TOKENIZER_MISMATCH"):
            self.reg().evaluate("alpha", "quality", "us-west")

    def test_admin_endpoint_rejects_remote(self):
        for url in ("http://10.0.0.1:8000", "https://127.0.0.1:8000",
                    "http://127.0.0.1:8000/foo", "http://localhost:8000",
                    "http://user:pw@127.0.0.1:8000"):
            with self.assertRaisesRegex(Refusal, "UNTRUSTED_ADMIN_ENDPOINT"):
                localhost_url(url)

    def test_uncertain_engine_failure_retained(self):
        FakeEngine.fail_load = True
        with self.assertRaises(Refusal):
            activate(self.reg(), self.ledger, "alpha", "quality", "us-west",
                     skip_genesis=True)
        self.assertFalse(self.ledger.routes()[0])
        self.assertEqual(self.ledger.events()[-1]["op"], "ACTIVATION_FAILED")

    def test_genesis_mandatory_by_default(self):
        with self.assertRaisesRegex(Refusal, "GENESIS_REQUIRED"):
            activate(self.reg(), self.ledger, "alpha", "quality", "us-west")
        self.assertEqual(self.ledger.events()[-1]["op"], "ACTIVATION_FAILED")

    def test_rollback_restricted_to_pinned_manifest(self):
        activate(self.reg(), self.ledger, "alpha", "quality", "us-west", skip_genesis=True)
        revoke(self.ledger, "alpha", "quality", "us-west")
        self.assertEqual(rollback(self.reg(), self.ledger, "alpha", "quality", "us-west",
                                  skip_genesis=True)["status"], "ROLLED_BACK")
        # Changed weights must never resurrect an old cached alias.
        revoke(self.ledger, "alpha", "quality", "us-west")
        self.template["adapters"]["quality"]["files"]["adapter_model.safetensors"] = "0" * 64
        self.save()
        with self.assertRaises(Refusal):
            rollback(self.reg(), self.ledger, "alpha", "quality", "us-west",
                     skip_genesis=True)

    def test_unsigned_fixture_never_routes(self):
        from types import SimpleNamespace
        activate(self.reg(), self.ledger, "alpha", "quality", "us-west", skip_genesis=True)
        args = SimpleNamespace(action="resolve", ledger=str(self.ledger.path),
                               registry=str(self.registry_path), tenant="alpha",
                               adapter="quality", region="us-west")
        with self.assertRaisesRegex(Refusal, "UNVERIFIED_ROUTE"):
            run_cli(args)

    def test_genesis_binding_checks_exact_signed_source(self):
        record = self.reg().evaluate("alpha", "quality", "us-west")
        shard = self.root / "shard"
        (shard / "content").mkdir(parents=True)
        record["genesis_shard"] = str(shard)
        source = shard / "content" / "source.txt"
        source.write_bytes(canonical(genesis_binding(record)).encode("utf-8"))
        fake = self.root / "fake-verifier"
        fake.write_bytes(bytes.fromhex("23212f62696e2f73680a6578697420300a"))
        fake.chmod(0o700)
        public = self.root / "trusted.pub"
        public.write_text("test-key")
        self.assertTrue(verify_genesis(record, str(public), str(fake)))
        source.write_bytes(b"{}")
        with self.assertRaisesRegex(Refusal, "GENESIS_BINDING_MISMATCH"):
            verify_genesis(record, str(public), str(fake))

    def test_hash_chain_tamper_refused(self):
        activate(self.reg(), self.ledger, "alpha", "quality", "us-west", skip_genesis=True)
        self.assertEqual(len(self.ledger.events()), 1)
        s = self.ledger.path.read_text()
        self.ledger.path.write_text(s.replace("ACTIVATED", "CORRUPTED"))
        with self.assertRaisesRegex(Refusal, "LEDGER_CORRUPT"):
            self.ledger.routes()


if __name__ == "__main__":
    unittest.main(verbosity=2)
