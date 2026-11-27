"""Recipient identity must bind the operation before any remote effect."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from schism_stack import bundle, identity, transport
from schism_stack.common import Refusal, canonical, digest
from schism_stack.engine import Engine


class RecipientTransport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schism-transport-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.controller = Engine(self.root / "controller")
        self.recipient = Engine(self.root / "recipient")

    def test_missing_or_changed_recipient_refuses_import_and_action_before_effects(self):
        source = self.root / "application"
        source.mkdir()
        (source / "schism.json").write_text(json.dumps({
            "schema": "schism.application/v1", "id": "remote-work", "name": "Remote work",
            "version": "1", "kind": "task", "command": ["{python}", "main.py"]
        }), encoding="utf-8")
        (source / "main.py").write_text("print('remote work')\n", encoding="utf-8")
        package = self.root / "application.schism"
        metadata = bundle.build(source, package, self.controller.root)
        requests = [
            {"operation": "import", "package": base64.b64encode(package.read_bytes()).decode("ascii")},
            {"operation": "action", "request": {"operation": "trust", "publisher": metadata["publisher"],
                                                  "apps": ["remote-work"], "request_id": "remote-trust"}},
        ]
        baseline_trust = self.recipient.store.all("SELECT * FROM trust")
        for pin in (None, self.controller.store.identity["key_id"]):
            for request in requests:
                wire = dict(request, nonce="identity-boundary", recipient_key_id=pin)
                with self.subTest(pin=pin, operation=request["operation"]):
                    envelope = transport.remote_response(self.recipient, wire)
                    payload = identity.verify(envelope, "schism.remote/v1", self.recipient.store.identity["key_id"])
                    self.assertIn("Recipient identity", payload["error"])
                    self.assertIsNone(payload["reply"])
                    self.assertEqual(payload["request_sha256"], digest(wire))
                    self.assertEqual(self.recipient.store.all("SELECT * FROM jobs"), [])
                    self.assertEqual(self.recipient.store.all("SELECT * FROM releases"), [])
                    self.assertEqual(self.recipient.store.all("SELECT * FROM trust"), baseline_trust)
                    for directory in ("incoming", "packages", "releases"):
                        self.assertEqual(list((self.recipient.root / directory).iterdir()), [])

    def test_enrollment_and_requests_bind_the_recipient_and_exact_signed_request(self):
        seen = []

        def exchange(command, *, input, **kwargs):
            wire = json.loads(input)
            seen.append(wire)
            envelope = transport.remote_response(self.recipient, wire)
            return subprocess.CompletedProcess(command, 0, canonical(envelope), b"")

        with mock.patch.object(transport.subprocess, "run", side_effect=exchange):
            enrolled = transport.add_peer(self.controller, {"name": "recipient", "host": "existing-alias",
                                                            "root": "/installed/source", "state": "/owned/state"})
            self.assertEqual(enrolled["key_id"], self.recipient.store.identity["key_id"])
            self.assertNotIn("recipient_key_id", seen[0])
            state = transport.peer_request(self.controller, "recipient", {"operation": "state"})
        self.assertEqual(state["identity"]["key_id"], self.recipient.store.identity["key_id"])
        self.assertEqual(seen[1]["recipient_key_id"], enrolled["key_id"])
        self.assertEqual(len(seen[1]["nonce"]), 32)
        event = self.controller.store.one("SELECT envelope FROM events WHERE kind='node.requested'")
        payload = identity.verify(json.loads(event["envelope"]), "schism.event/v1", self.controller.store.identity["key_id"])
        self.assertEqual(payload["body"]["request_sha256"], digest(seen[1]))
        replay = transport.remote_response(self.recipient, seen[1])
        with mock.patch.object(transport.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, canonical(replay), b"")):
            with self.assertRaisesRegex(Refusal, "different request"):
                transport.peer_request(self.controller, "recipient", {"operation": "state"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
