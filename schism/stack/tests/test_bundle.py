"""Authority and hostile-package boundary tests, with no application execution."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

from schism_stack import bundle, identity
from schism_stack.common import Refusal
from schism_stack.store import Store


class PackageBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schism-package-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "application"
        self.source.mkdir()
        self.state = self.root / "operator"
        self.application = {"schema": "schism.application/v1", "id": "unlisted-workload",
                            "name": "A user's application", "version": "2026.1",
                            "kind": "task", "command": ["{python}", "main.py", "{data}/arbitrary.json"]}
        self.write_manifest(self.application)
        (self.source / "main.py").write_text("raise SystemExit('this payload must never execute during inspection')\n", encoding="utf-8")
        self.package = self.root / "app.schism"

    def write_manifest(self, document):
        (self.source / "schism.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    def build(self):
        return bundle.build(self.source, self.package, self.state)

    def entries(self):
        with zipfile.ZipFile(self.package) as archive:
            return [(copy.copy(info), archive.read(info)) for info in archive.infolist()]

    def rewrite(self, entries, name="modified.schism"):
        out = self.root / name
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(out, "w") as archive:
                for info, raw in entries:
                    archive.writestr(info, raw)
        return out

    def resigned(self, transform):
        entries = self.entries()
        release = json.loads(next(raw for info, raw in entries if info.filename == "release.json"))
        transform(release)
        body = {key: value for key, value in release.items() if key != "release_id"}
        release["release_id"] = hashlib.sha256(identity.canonical(body)).hexdigest()
        envelope = identity.sign(self.state, release, "schism.release/v1")
        rewritten = []
        for info, raw in entries:
            if info.filename == "release.json":
                raw = identity.canonical(release)
            elif info.filename == "signature.json":
                raw = identity.canonical(envelope)
            rewritten.append((info, raw))
        return self.rewrite(rewritten)

    def test_identity_accepts_initialized_state_and_reuses_exact_key(self):
        store = Store(self.state, "Operator α")
        before = (self.state / "identity/private.key").read_bytes()
        again = identity.ensure_identity(self.state, "Different display argument")
        self.assertEqual(store.identity, again)
        self.assertEqual(before, (self.state / "identity/private.key").read_bytes())
        self.assertEqual(again["key_id"], hashlib.sha256(base64.b64decode(again["public_key"])).hexdigest())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE((self.state / "identity/private.key").stat().st_mode), 0o600)

    def test_identity_signature_tamper_purpose_and_independent_pin(self):
        publisher = identity.ensure_identity(self.state)
        packet = identity.sign(self.state, {"release": "a", "unicode": "é / 🐙"}, "test.release/v1")
        self.assertEqual(identity.verify(packet, "test.release/v1", publisher["key_id"])["release"], "a")
        for mutation in ("payload", "purpose", "key", "extra"):
            changed = copy.deepcopy(packet)
            if mutation == "payload": changed["payload"]["release"] = "b"
            if mutation == "purpose": changed["purpose"] = "test.other/v1"
            if mutation == "key": changed["public_key"] = base64.b64encode(b"x" * 32).decode()
            if mutation == "extra": changed["authority"] = True
            with self.subTest(mutation=mutation), self.assertRaises(Refusal):
                identity.verify(changed, "test.release/v1")
        with self.assertRaises(Refusal): identity.verify(packet, expected_key_id="0" * 64)
        with self.assertRaises(Refusal): identity.verify(packet, "different/v1")

    def test_incomplete_identity_never_silently_rotates(self):
        identity.ensure_identity(self.state)
        private = (self.state / "identity/private.key").read_bytes()
        (self.state / "identity/public.json").unlink()
        with self.assertRaisesRegex(Refusal, "Incomplete"):
            identity.ensure_identity(self.state)
        self.assertEqual(private, (self.state / "identity/private.key").read_bytes())

    def test_arbitrary_argv_defaults_and_closed_extraction(self):
        metadata = self.build()
        self.assertEqual(metadata, bundle.inspect(self.package))
        self.assertEqual(metadata["application"]["id"], "unlisted-workload")
        for key, value in {"environment": {}, "secret_env": [], "data_schema": "1", "cwd": ".",
                           "stop_timeout": 5, "task_timeout": 300,
                           "health": {"type": "process", "grace": 1, "timeout": 10}}.items():
            self.assertEqual(metadata["application"][key], value)
        destination = self.root / "extracted"
        self.assertEqual(bundle.extract(self.package, destination), metadata)
        self.assertEqual(bundle.verify_directory(destination), metadata)
        self.assertEqual({p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()},
                         {"release.json", "signature.json", "payload/schism.json", "payload/main.py"})
        self.assertFalse(any("private" in row["path"] for row in metadata["files"]))

    def test_payload_tamper_is_refused_before_extraction(self):
        self.build()
        entries = [(info, raw + b"\nchanged" if info.filename == "payload/main.py" else raw) for info, raw in self.entries()]
        changed = self.rewrite(entries)
        with self.assertRaisesRegex(Refusal, "signed inventory"):
            bundle.extract(changed, self.root / "must-not-exist")
        self.assertFalse((self.root / "must-not-exist").exists())

    def test_signature_tamper_and_release_identity_are_distinct_gates(self):
        self.build()
        entries = self.entries()
        for info, raw in entries:
            if info.filename == "signature.json":
                value = json.loads(raw)
                value["signature"] = base64.b64encode(b"x" * 64).decode()
                raw = identity.canonical(value)
            if info.filename == "signature.json":
                changed = self.rewrite([(i, raw if i.filename == "signature.json" else r) for i, r in entries])
        with self.assertRaisesRegex(Refusal, "signature verification"):
            bundle.inspect(changed)
        release = json.loads(next(raw for info, raw in entries if info.filename == "release.json"))
        release["release_id"] = "0" * 64
        signature = identity.sign(self.state, release, "schism.release/v1")
        changed = self.rewrite([(info, identity.canonical(release) if info.filename == "release.json" else
                                identity.canonical(signature) if info.filename == "signature.json" else raw)
                               for info, raw in entries], "wrong-id.schism")
        with self.assertRaisesRegex(Refusal, "content identity"):
            bundle.inspect(changed)

    def test_signed_metadata_cannot_disagree_with_original_application(self):
        self.build()
        changed = self.resigned(lambda release: release["application"].update(version="invented"))
        with self.assertRaisesRegex(Refusal, "Original application document"):
            bundle.inspect(changed)

    def test_traversal_windows_aliases_and_case_collisions(self):
        self.build()
        names = ["../escape", "/absolute", "payload/../escape", "payload\\escape", "C:/escape",
                 "payload/a:b", "payload/CON.txt", "payload/file.", "payload/file ",
                 "payload/MAIN.py", "payload//file", "PAYLOAD/extra"]
        for index, name in enumerate(names):
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            changed = self.rewrite(self.entries() + [(info, b"bad")], "unsafe-" + str(index) + ".schism")
            with self.subTest(name=name), self.assertRaises(Refusal):
                bundle.inspect(changed)

    def test_duplicate_zip_member_and_unicode_collision(self):
        self.build()
        entries = self.entries()
        with self.assertRaisesRegex(Refusal, "Duplicate"):
            bundle.inspect(self.rewrite(entries + [entries[-1]]))
        extra = []
        for name in ["payload/é.txt", "payload/e\u0301.txt"]:
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            extra.append((info, b"same"))
        with self.assertRaisesRegex(Refusal, "colliding"):
            bundle.inspect(self.rewrite(entries + extra, "unicode.schism"))

    def test_zip_links_special_files_and_executable_modes_are_refused(self):
        self.build()
        for index, mode in enumerate([stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFREG | 0o755]):
            entries = self.entries()
            for info, _ in entries:
                if info.filename == "payload/main.py":
                    info.external_attr = mode << 16
            with self.subTest(mode=mode), self.assertRaises(Refusal):
                bundle.inspect(self.rewrite(entries, "mode-" + str(index) + ".schism"))

    def test_unknown_fields_rejected_at_application_release_and_signature(self):
        for key, value in [("shell", True), ("allow_all", True), ("publisher", {})]:
            changed = dict(self.application, **{key: value})
            self.write_manifest(changed)
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "Unknown application"):
                self.build()
        self.write_manifest(self.application)
        self.build()
        changed = self.resigned(lambda release: release.update(extra=True))
        with self.assertRaisesRegex(Refusal, "Unknown release"):
            bundle.inspect(changed)
        entries = []
        for info, raw in self.entries():
            if info.filename == "signature.json":
                doc = json.loads(raw)
                doc["authority"] = True
                raw = identity.canonical(doc)
            entries.append((info, raw))
        with self.assertRaisesRegex(Refusal, "Unknown signature"):
            bundle.inspect(self.rewrite(entries, "unknown-signature.schism"))

    def test_private_paths_and_secret_files_refused_cache_excluded(self):
        for name in [".env", ".git/config", "credentials.json", "prod-secret.yaml", "private.key", "id_ed25519", "schism-state.json"]:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private-value", encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(Refusal): self.build()
            path.unlink()
            if path.parent != self.source: path.parent.rmdir()
        cache = self.source / "__pycache__"
        cache.mkdir()
        (cache / "main.pyc").write_bytes(b"generated")
        (self.source / "generated.pyc").write_bytes(b"generated")
        self.assertEqual({row["path"] for row in self.build()["files"]}, {"schism.json", "main.py"})

    def test_secret_environment_names_are_declared_without_values(self):
        self.write_manifest(dict(self.application, secret_env=["API_TOKEN"], environment={"PORT": "12345"}))
        self.assertEqual(self.build()["application"]["secret_env"], ["API_TOKEN"])
        for fields in [dict(environment={"API_TOKEN": "embedded"}),
                       dict(secret_env=["SOMETHING"], environment={"SOMETHING": "embedded"}),
                       dict(environment={"SCHISM_DATA": "/escape"}),
                       dict(secret_env=["Secret", "SECRET"]),
                       dict(environment={"Path": "a", "PATH": "b"})]:
            with self.subTest(fields=fields), self.assertRaises(Refusal):
                bundle.normalize_application(dict(self.application, **fields))

    def test_health_is_bounded_numeric_loopback_and_working_directory_is_relative(self):
        service = dict(self.application, kind="service", health={"type": "http", "url": "http://127.0.0.1:8765/health"})
        normalized = bundle.normalize_application(service)
        self.assertEqual(normalized["health"], {"type": "http", "url": "http://127.0.0.1:8765/health", "timeout": 10, "status": 200})
        for url in ["http://example.com/", "http://localhost/", "http://127.0.0.1.evil/", "http://user:password@127.0.0.1/", "http://127.0.0.1/#part", "file:///tmp/health", "http://192.0.2.1/"]:
            with self.subTest(url=url), self.assertRaises(Refusal):
                bundle.normalize_application(dict(service, health={"type": "http", "url": url}))
        for key, value in [("cwd", "../outside"), ("task_timeout", float("inf")), ("stop_timeout", True), ("command", "python main.py"), ("kind", []), ("health", {"type": []})]:
            with self.subTest(key=key), self.assertRaises(Refusal):
                bundle.normalize_application(dict(self.application, **{key: value}))
        self.write_manifest(dict(self.application, cwd="absent"))
        with self.assertRaisesRegex(Refusal, "working directory"):
            self.build()

    def test_output_exclusivity_and_normalized_source_separation(self):
        with self.assertRaisesRegex(Refusal, "outside"):
            bundle.build(self.source, self.source / "created.schism", self.state)
        redundant_source = self.source / "unused" / ".."
        with self.assertRaisesRegex(Refusal, "outside"):
            bundle.build(redundant_source, self.source / "created.schism", self.state)
        self.build()
        before = self.package.read_bytes()
        with self.assertRaisesRegex(Refusal, "already exists"):
            self.build()
        self.assertEqual(before, self.package.read_bytes())
        with self.assertRaisesRegex(Refusal, "outside"):
            bundle.build(self.source, self.root / "other.schism", self.source / "operator")

    def test_source_symlink_and_hardlink_refused(self):
        target = self.root / "outside.txt"
        target.write_text("not package input", encoding="utf-8")
        link = self.source / "innocent.txt"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("This OS account cannot create a symlink")
        with self.assertRaisesRegex(Refusal, "symlink"):
            self.build()
        link.unlink()
        os.link(target, link)
        with self.assertRaisesRegex(Refusal, "hard links"):
            self.build()

    def test_directory_content_extra_files_and_modes_reverified(self):
        self.build()
        destination = self.root / "release"
        bundle.extract(self.package, destination)
        path = destination / "payload/main.py"
        old = path.read_bytes()
        path.write_bytes(old + b"# changed\n")
        with self.assertRaisesRegex(Refusal, "signed inventory"):
            bundle.verify_directory(destination)
        path.write_bytes(old)
        extra = destination / "payload/extra"
        extra.mkdir()
        with self.assertRaisesRegex(Refusal, "not closed"):
            bundle.verify_directory(destination)
        extra.rmdir()
        if os.name != "nt":
            path.chmod(0o755)
            with self.assertRaisesRegex(Refusal, "Executable mode"):
                bundle.verify_directory(destination)

    def test_duplicate_json_members_and_size_limits(self):
        (self.source / "schism.json").write_bytes(b'{"schema":"schism.application/v1","schema":"other"}')
        with self.assertRaisesRegex(Refusal, "Duplicate JSON"):
            self.build()
        self.write_manifest(self.application)
        with mock.patch.object(bundle, "MAX_FILE_BYTES", 10):
            with self.assertRaises(Refusal):
                self.build()
            self.assertFalse(self.package.exists())
        self.build()
        with mock.patch.object(bundle, "MAX_ARCHIVE_BYTES", 10):
            with self.assertRaisesRegex(Refusal, "bound"):
                bundle.inspect(self.package)

    def test_release_version_changes_identity_without_mutating_prior_packet(self):
        first = self.build()
        before = self.package.read_bytes()
        self.write_manifest(dict(self.application, version="2026.2"))
        second = bundle.build(self.source, self.root / "v2.schism", self.state)
        self.assertNotEqual(first["release_id"], second["release_id"])
        self.assertEqual(first, bundle.inspect(self.package))
        self.assertEqual(before, self.package.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
