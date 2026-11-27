from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
import zipfile

import psutil

from schism_stack import bundle, identity
from schism_stack.common import Refusal, controller_command, process_alive, stop_owned
from schism_stack.engine import Engine, TERMINAL
from schism_stack.evidence import backup_application, export_evidence, restore_application, verify_evidence
from schism_stack.server import make_server

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schism-recipient-")
        self.root = Path(self.temp.name)
        self.publisher = Engine(self.root / "publisher", "Independent publisher")
        self.recipient = Engine(self.root / "recipient", "Independent recipient")
        self.engines = [self.publisher, self.recipient]
        self.serial = 0

    def tearDown(self):
        for engine in self.engines:
            for row in engine.store.all("SELECT * FROM runs"):
                stop_owned(row["pid"], row["process_created"], 0.3)
                stop_owned(row["runner_pid"], row["runner_created"], 0.3)
                stop_owned(row.get("launcher_pid"), row.get("launcher_created"), 0.3)
            for row in engine.store.all("SELECT * FROM jobs"):
                stop_owned(row["worker_pid"], row["worker_created"], 0.3)
        self.temp.cleanup()

    def package(self, app_id="work", version="1.0.0", script=None, kind="task", **fields):
        self.serial += 1
        source = self.root / ("source-" + str(self.serial))
        source.mkdir()
        document = {"schema": "schism.application/v1", "id": app_id, "name": "Recipient workload", "version": version,
                    "kind": kind, "command": ["{python}", "app.py"], "environment": {}, "secret_env": [], "data_schema": "1", "stop_timeout": 1, "task_timeout": 30}
        document.update(fields)
        (source / "schism.json").write_text(json.dumps(document), encoding="utf-8")
        script = script or "import os,json\nfrom pathlib import Path\np=Path(os.environ['SCHISM_DATA'])/'result.json'\nn=json.loads(p.read_text())['count'] if p.exists() else 0\np.write_text(json.dumps({'count':n+1}),encoding='utf-8')\nprint('résumé 日本語',flush=True)\n"
        (source / "app.py").write_text(script, encoding="utf-8")
        path = self.root / (str(self.serial) + ".schism")
        metadata = bundle.build(source, path, self.publisher.root)
        return path, metadata

    def job(self, engine, job_id, timeout=35):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            row = engine.job(job_id)
            if row["status"] in TERMINAL:
                return row
            time.sleep(0.05)
        self.fail("Job never reached a terminal state: " + repr(engine.job(job_id)))

    def action(self, operation, engine=None, succeeds=True, **request):
        engine = engine or self.recipient
        response = engine.submit(dict(request, operation=operation))
        row = self.job(engine, response["job_id"])
        self.assertEqual(row["status"], "succeeded" if succeeds else "failed", row)
        return row

    def trust(self, metadata, engine=None, apps=None):
        return self.action("trust", engine=engine, publisher=metadata["publisher"], apps=apps or [metadata["application"]["id"]])

    def test_arbitrary_task_authority_durable_identity_and_recipient_backup(self):
        package, release = self.package()
        self.recipient.import_package(package)
        self.action("deploy", release_id=release["release_id"], expected_generation=0, succeeds=False)
        self.trust(release, apps=["different-app"])
        self.action("deploy", release_id=release["release_id"], expected_generation=0, succeeds=False)
        self.trust(release)
        self.action("deploy", release_id=release["release_id"], expected_generation=0)
        result_path = self.recipient.root / "data" / "work" / "result.json"
        self.assertFalse(result_path.exists(), "Task activation must not execute task")
        # A distinct CLI process exits; its detached worker still records the actual result.
        child = subprocess.run(controller_command("--state", self.recipient.root, "run", "work", "--expect", "1", "--detach"), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        job_id = json.loads(child.stdout)["job_id"]
        run = self.job(self.recipient, job_id)
        self.assertEqual(run["status"], "succeeded", run)
        self.assertIn("résumé 日本語", run["log"])
        self.assertEqual(json.loads(result_path.read_text())["count"], 1)
        request = {"operation": "run", "app_id": "work", "expected_generation": 1, "request_id": "exact-work-request"}
        first = self.recipient.submit(request)
        self.assertEqual(self.job(self.recipient, first["job_id"])["status"], "succeeded")
        again = self.recipient.submit(request)
        self.assertEqual(first["job_id"], again["job_id"])
        self.assertEqual(json.loads(result_path.read_text())["count"], 2)
        with self.assertRaises(Refusal):
            self.recipient.submit(dict(request, operation="stop"))
        secret = "PRIVATE-RUNTIME-VALUE-DO-NOT-EXPORT"
        self.action("configure", app_id="work", environment={"MY_SECRET": secret})
        self.action("configure", app_id="work", environment={"schism_DATA": "different-root"}, succeeds=False)
        self.action("configure", app_id="work", environment={"port": "1", "PORT": "2"}, succeeds=False)
        evidence = self.root / "evidence.zip"
        export_evidence(self.recipient, evidence)
        verdict = verify_evidence(evidence, self.recipient.store.identity["key_id"])
        self.assertTrue(verdict["valid"])
        with zipfile.ZipFile(evidence) as z:
            self.assertNotIn(secret.encode(), z.read("evidence.json"))
        with self.assertRaises(ValueError):
            verify_evidence(evidence, self.publisher.store.identity["key_id"])
        backup = self.root / "application-backup.zip"
        backup_application(self.recipient, "work", backup)
        replacement = Engine(self.root / "replacement", "Replacement operator")
        self.engines.append(replacement)
        restored = restore_application(replacement, backup, self.recipient.store.identity["key_id"])
        self.assertEqual(restored["status"], "stopped")
        self.assertFalse(restored["trusted"])
        self.trust(release, engine=replacement)
        self.action("run", engine=replacement, app_id="work", expected_generation=1)
        self.assertEqual(json.loads((replacement.root / "data/work/result.json").read_text())["count"], 3)
        self.action("revoke", key_id=release["publisher"]["key_id"])
        self.action("run", app_id="work", expected_generation=1, succeeds=False)
        self.assertEqual(json.loads(result_path.read_text())["count"], 2)

    def test_service_update_rejection_rollback_and_data_continuity(self):
        port = free_port()
        script = (ROOT / "examples/counter-service/server.py").read_text(encoding="utf-8")
        options = {"kind": "service", "script": script, "health": {"type": "http", "url": f"http://127.0.0.1:{port}/health", "timeout": 8}, "environment": {"PORT": str(port), "RELEASE_LABEL": "first"}}
        first_path, first = self.package("service", **options)
        self.recipient.import_package(first_path)
        self.trust(first)
        self.action("deploy", release_id=first["release_id"], expected_generation=0)
        def value():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                return json.load(response)
        self.assertEqual(value(), {"healthy": True, "release": "first", "visits": 1})
        second_path, second = self.package("service", "2.0.0", **dict(options, environment={"PORT": str(port), "RELEASE_LABEL": "second"}))
        self.recipient.import_package(second_path)
        self.action("deploy", release_id=second["release_id"], expected_generation=1)
        self.assertEqual(value(), {"healthy": True, "release": "second", "visits": 2})
        self.action("rollback", app_id="service", expected_generation=2)
        self.assertEqual(value(), {"healthy": True, "release": "first", "visits": 3})
        bad_path, bad = self.package("service", "3.0.0", **dict(options, script="raise SystemExit(17)\n"))
        self.recipient.import_package(bad_path)
        self.action("deploy", release_id=bad["release_id"], expected_generation=3, succeeds=False)
        self.assertEqual(value()["release"], "first")
        self.assertEqual(self.recipient.store.app("service")["generation"], 3)
        schema_path, schema = self.package("service", "4.0.0", **dict(options, data_schema="2"))
        self.recipient.import_package(schema_path)
        self.action("deploy", release_id=schema["release_id"], expected_generation=3, succeeds=False)
        self.action("stop", app_id="service", expected_generation=2, succeeds=False)
        self.assertEqual(value()["release"], "first")
        with self.assertRaises(Refusal):
            backup_application(self.recipient, "service", self.root / "running-backup.zip")
        self.action("stop", app_id="service", expected_generation=3)
        (self.recipient.root / "releases" / first["release_id"] / "payload/app.py").write_text("print('changed')", encoding="utf-8")
        self.action("start", app_id="service", expected_generation=3, succeeds=False)

    def test_cancellation_and_interrupted_effect_are_not_replayed(self):
        script = "import os,time\nfrom pathlib import Path\np=Path(os.environ['SCHISM_DATA'])/'effects.txt'\nwith p.open('a') as f:f.write('effect\\n');f.flush()\nprint('started',flush=True)\ntime.sleep(60)\n"
        package, release = self.package("long-task", script=script, task_timeout=120)
        self.recipient.import_package(package)
        self.trust(release)
        self.action("deploy", release_id=release["release_id"], expected_generation=0)
        started = self.recipient.submit({"operation": "run", "app_id": "long-task", "expected_generation": 1})
        effects = self.recipient.root / "data/long-task/effects.txt"
        deadline = time.monotonic() + 10
        while not effects.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(effects.exists())
        self.action("cancel", job_id=started["job_id"])
        cancelled = self.job(self.recipient, started["job_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        run_id = cancelled["runs"][0]["id"]
        exits = [json.loads(row["envelope"])["payload"]["body"]["run_id"]
                 for row in self.recipient.store.all("SELECT envelope FROM events WHERE kind='process.exited'")]
        self.assertIn(run_id, exits, "Ordinary cancellation must let the observer retain the child exit")
        with self.recipient.store.db() as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(effects.read_text(), "effect\n")
        self.assertFalse(self.recipient._running(self.recipient.store.app("long-task")))
        second = self.recipient.submit({"operation": "run", "app_id": "long-task", "expected_generation": 1})
        deadline = time.monotonic() + 10
        while effects.read_text().count("effect") < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        row = self.recipient.store.job(second["job_id"])
        psutil.Process(row["worker_pid"]).kill()
        time.sleep(5.2)
        self.assertEqual(self.recipient.job(second["job_id"])["status"], "interrupted")
        self.action("recover", app_id="long-task")
        self.assertEqual(effects.read_text(), "effect\neffect\n")
        self.action("stop", app_id="long-task", expected_generation=1)
        with self.recipient.store.db() as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_loopback_origin_and_session_boundaries(self):
        server = make_server(self.recipient, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(url + "/api/token")
            with urllib.request.urlopen(urllib.request.Request(url + "/api/token", headers={"X-SCHISM-Token": server.session_token})) as response:
                token = json.load(response)["token"]
            for headers in ({"Host": "attacker.invalid"}, {"Origin": "https://attacker.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(urllib.request.Request(url + "/api/state", headers=headers))
                self.assertEqual(caught.exception.code, 403)
            request = urllib.request.Request(url + "/api/action", data=b'{"operation":"recover","app_id":"none"}', headers={"Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(request)
            request.add_header("X-SCHISM-Token", token)
            with urllib.request.urlopen(request) as response:
                job_id = json.load(response)["job_id"]
            self.assertEqual(self.job(self.recipient, job_id)["status"], "succeeded")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
