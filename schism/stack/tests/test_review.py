"""Regression cases for acceptance, committed selection and recipient import boundaries."""
from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import zipfile

import psutil

from schism_stack import bundle, identity
from schism_stack.common import Refusal, canonical, digest, now
from schism_stack.engine import Engine
from schism_stack.evidence import backup_application, export_evidence, restore_application, verify_evidence


class ReviewBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schism-review-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / "operator")
        self.serial = 0

    def package(self, version="1", app_id="review-app", kind="service", data_schema="1"):
        self.serial += 1
        source = self.root / ("source-" + str(self.serial))
        source.mkdir()
        manifest = {"schema": "schism.application/v1", "id": app_id, "name": "Review application",
                    "version": version, "kind": kind, "command": ["{python}", "main.py"], "data_schema": data_schema}
        (source / "schism.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "main.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        path = self.root / (str(self.serial) + ".schism")
        metadata = bundle.build(source, path, self.engine.root)
        self.engine.import_package(path)
        return path, metadata

    def selected(self, release):
        application = release["application"]
        with self.engine.store.db() as con:
            con.execute("INSERT INTO apps VALUES(?,?,?,?,?,?,?,?)",
                        (application["id"], release["release_id"], None, 1, "running", None,
                         application["data_schema"], None))

    def test_http_acceptance_refuses_another_address_on_the_same_port(self):
        class Healthy(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"unrelated service")

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Healthy)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_port
        script = ("import socket,time\n"
                  "s=socket.socket();s.bind(('127.0.0.2'," + str(port) + "));s.listen()\n"
                  "print('ready',flush=True)\n"
                  "time.sleep(30)\n")
        child = subprocess.Popen([sys.executable, "-u", "-c", script], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            ready = child.stdout.readline().strip()
            if ready != "ready":
                self.skipTest("Host cannot bind a second numeric loopback address: " + child.stderr.read())
            created = psutil.Process(child.pid).create_time()
            with self.engine.store.db() as con:
                con.execute("INSERT INTO runs(id,app_id,release_id,kind,status,pid,process_created,created_at) VALUES(?,?,?,?,?,?,?,?)",
                            ("address-probe", "review-app", "none", "service", "running", child.pid, created, now()))
            application = {"health": {"type": "http", "url": f"http://127.0.0.1:{port}/health", "timeout": 0.4, "status": 200}}
            with self.assertRaises(Refusal):
                self.engine._health("address-probe", application, None)
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
            child.stdout.close()
            child.stderr.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_receipt_failure_cannot_split_selected_release_from_running_release(self):
        _, old = self.package("1")
        _, candidate = self.package("2")
        self.selected(old)
        real_event = self.engine.store.event

        def failing_receipt(kind, body, **kwargs):
            if kind == "release.activated":
                raise OSError("Injected receipt storage failure")
            return real_event(kind, body, **kwargs)

        with mock.patch.object(self.engine, "checkpoint"), \
             mock.patch.object(self.engine, "_running", return_value=True), \
             mock.patch.object(self.engine, "_spawn", side_effect=["candidate-run", "recovery-run"]), \
             mock.patch.object(self.engine, "_health"), \
             mock.patch.object(self.engine, "_stop_run") as stopped, \
             mock.patch.object(self.engine.store, "event", side_effect=failing_receipt):
            with self.assertRaisesRegex(OSError, "Injected receipt storage failure"):
                self.engine._deploy("review-app", candidate["release_id"], 1, "test-job")
            selected = self.engine.store.app("review-app")
            if selected["release_id"] == candidate["release_id"]:
                self.assertEqual(selected["run_id"], "candidate-run")
                self.assertEqual(selected["generation"], 2)
                self.assertNotIn(mock.call("candidate-run"), stopped.call_args_list)
            else:
                self.assertEqual(selected["release_id"], old["release_id"])
                self.assertEqual(selected["generation"], 1)
                self.assertEqual(selected["run_id"], "recovery-run")

    def test_failed_recovery_stops_its_unaccepted_process(self):
        _, old = self.package("1")
        _, candidate = self.package("2")
        self.selected(old)
        with mock.patch.object(self.engine, "checkpoint"), \
             mock.patch.object(self.engine, "_running", return_value=True), \
             mock.patch.object(self.engine, "_spawn", side_effect=["candidate-run", "recovery-run"]), \
             mock.patch.object(self.engine, "_health", side_effect=Refusal("Injected failed acceptance")), \
             mock.patch.object(self.engine, "_stop_run") as stopped:
            with self.assertRaises(Refusal):
                self.engine._deploy("review-app", candidate["release_id"], 1, "test-job")
            self.assertIn(mock.call("candidate-run"), stopped.call_args_list)
            self.assertIn(mock.call("recovery-run"), stopped.call_args_list)
        selected = self.engine.store.app("review-app")
        self.assertEqual(selected["release_id"], old["release_id"])
        self.assertEqual(selected["generation"], 1)

    def test_unselected_partial_data_retains_its_original_schema(self):
        _, first = self.package("1", data_schema="1")
        _, incompatible = self.package("2", kind="task", data_schema="2")
        _, compatible = self.package("3", kind="task", data_schema="1")
        data = self.engine.root / "data/review-app/partial-effect.txt"

        def failed_first_acceptance(*args):
            data.write_text("schema-one effect before acceptance", encoding="utf-8")
            raise Refusal("Injected first activation failure")

        with mock.patch.object(self.engine, "checkpoint"), \
             mock.patch.object(self.engine, "_spawn", return_value="unselected-run"), \
             mock.patch.object(self.engine, "_health", side_effect=failed_first_acceptance), \
             mock.patch.object(self.engine, "_stop_run"):
            with self.assertRaises(Refusal):
                self.engine._deploy("review-app", first["release_id"], 0, "test-job")
        self.assertIsNone(self.engine.store.app("review-app", False))
        recovered = self.engine._recover("review-app")
        self.assertFalse(recovered["automatic_replay"])
        self.assertEqual(recovered["generation"], 0)
        with mock.patch.object(self.engine, "checkpoint"):
            with self.assertRaises(Refusal):
                self.engine._deploy("review-app", incompatible["release_id"], 0, "test-job")
            accepted = self.engine._deploy("review-app", compatible["release_id"], 0, "test-job")
        self.assertEqual(accepted["generation"], 1)
        self.assertEqual(data.read_text(encoding="utf-8"), "schema-one effect before acceptance")

    def evidence_payload(self):
        self.package(kind="task")
        path = self.root / "evidence.zip"
        export_evidence(self.engine, path)
        with zipfile.ZipFile(path) as archive:
            envelope = json.loads(archive.read("evidence.json"))
        return envelope["payload"]

    def signed_evidence(self, payload):
        path = self.root / "altered-evidence.zip"
        envelope = identity.sign(self.engine.root, payload, "schism.evidence/v1")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("evidence.json", canonical(envelope))
            archive.writestr("VERIFY.txt", "Use an independently established signer fingerprint.\n")
        return path

    def test_evidence_binds_operator_descriptor_to_signer(self):
        payload = self.evidence_payload()
        other = Engine(self.root / "other-operator")
        payload["operator"] = other.store.identity
        with self.assertRaises(Refusal):
            verify_evidence(self.signed_evidence(payload), self.engine.store.identity["key_id"])

    def test_evidence_validates_inner_release_identity(self):
        payload = self.evidence_payload()
        item = payload["releases"][0]
        item["release"]["release_id"] = "0" * 64
        item["signature"] = identity.sign(self.engine.root, item["release"], "schism.release/v1")
        with self.assertRaises(Refusal):
            verify_evidence(self.signed_evidence(payload), self.engine.store.identity["key_id"])

    def test_backup_refuses_a_linked_application_data_root(self):
        _, release = self.package(kind="task")
        self.selected(release)
        outside = self.root / "unrelated-data"
        outside.mkdir()
        (outside / "unrelated.txt").write_text("not application data", encoding="utf-8")
        data = self.engine.root / "data/review-app"
        try:
            data.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("This account cannot create a directory symlink: " + str(exc))
        destination = self.root / "linked-data.zip"
        with self.assertRaises(Refusal):
            backup_application(self.engine, "review-app", destination)
        self.assertFalse(destination.exists())

    def test_backup_normalizes_output_before_live_state_exclusion(self):
        _, release = self.package(kind="task")
        self.selected(release)
        outside = self.root / "outside"
        outside.mkdir()
        destination = outside / ".." / "operator" / "inside-state.zip"
        with self.assertRaises(Refusal):
            backup_application(self.engine, "review-app", destination)
        self.assertFalse((self.engine.root / "inside-state.zip").exists())

    def backup_parts(self):
        _, release = self.package(kind="task")
        self.selected(release)
        data = self.engine.root / "data/review-app"
        data.mkdir()
        (data / "state.txt").write_text("retained work", encoding="utf-8")
        path = self.root / "backup.zip"
        backup_application(self.engine, "review-app", path)
        with zipfile.ZipFile(path) as archive:
            payload = json.loads(archive.read("backup.json"))["payload"]
            files = {name: archive.read(name) for name in archive.namelist() if name != "backup.json"}
        return payload, files

    def signed_backup(self, payload, files, name="altered-backup.zip"):
        payload = copy.deepcopy(payload)
        payload["files"] = [{"path": name, "size": len(raw), "sha256": digest(raw)} for name, raw in files.items()]
        envelope = identity.sign(self.engine.root, payload, "schism.backup/v1")
        path = self.root / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("backup.json", canonical(envelope))
            for name, raw in files.items():
                archive.writestr(name, raw)
        return path

    def test_restore_refuses_portable_aliases_before_import(self):
        payload, files = self.backup_parts()
        for index, additions in enumerate((
                {"data/A/one": b"one", "data/a/two": b"two"},
                {"data/con.txt": b"reserved"},
                {"data/name.": b"alias"},
                {"data/caf\u00e9/one": b"one", "data/cafe\u0301/two": b"two"})):
            with self.subTest(paths=list(additions)):
                recipient = Engine(self.root / ("recipient-" + str(index)))
                path = self.signed_backup(payload, dict(files, **additions), "aliased-" + str(index) + ".zip")
                with self.assertRaises(Refusal):
                    restore_application(recipient, path, self.engine.store.identity["key_id"])
                self.assertEqual(recipient.store.all("SELECT release_id FROM releases"), [])
                self.assertIsNone(recipient.store.app("review-app", False))
                self.assertFalse((recipient.root / "data/review-app").exists())

    def test_restore_preflights_every_package_and_previous_identity(self):
        payload, files = self.backup_parts()
        other_path, other = self.package(app_id="different-app", kind="task")
        foreign_files = dict(files)
        foreign_files["packages/" + other["release_id"] + ".schism"] = other_path.read_bytes()
        for index, (document, contents) in enumerate((
                (payload, foreign_files),
                (dict(payload, previous_release_id="0" * 64), files),
                (dict(payload, previous_release_id=other["release_id"]), foreign_files))):
            recipient = Engine(self.root / ("preflight-recipient-" + str(index)))
            path = self.signed_backup(document, contents, "preflight-" + str(index) + ".zip")
            with self.subTest(case=index), self.assertRaises(Refusal):
                restore_application(recipient, path, self.engine.store.identity["key_id"])
            self.assertEqual(recipient.store.all("SELECT release_id FROM releases"), [])
            self.assertIsNone(recipient.store.app("review-app", False))
            self.assertFalse((recipient.root / "data/review-app").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
