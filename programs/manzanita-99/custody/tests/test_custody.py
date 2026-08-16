from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

CUSTODY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CUSTODY_DIR))

import build_custody  # noqa: E402
import validate_custody  # noqa: E402


def write(path: Path, text: str) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    path.write_bytes(payload)
    return payload


class CustodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        public = write(self.root / "manzanita/index.html", "<h1>donor</h1>\n")
        write(self.root / "programs/manzanita-99/README.md", "# Program\n")
        write(self.root / ".github/pages-deployment.json", "{}\n")
        self.register_path = self.root / "programs/manzanita-99/custody/DONOR_REGISTER.json"
        self.output_path = self.root / "programs/manzanita-99/custody/CUSTODY_MANIFEST.json"
        self.register = {
            "schema": "axm-tools/manzanita-99-donor-register@1",
            "task": "JDB99-001",
            "state": "in_progress",
            "qualification_boundary": "Custody consistency only.",
            "required_classes": ["public_release", "visual_golden"],
            "archive_scopes": [
                {
                    "id": "public",
                    "class": "public_release",
                    "path": "manzanita",
                    "required": True,
                    "exclude": [],
                },
                {
                    "id": "program",
                    "class": "public_release",
                    "path": "programs/manzanita-99",
                    "required": True,
                    "exclude": [
                        "programs/manzanita-99/custody/CUSTODY_MANIFEST.json"
                    ],
                },
            ],
            "public_route_guard": {
                "path": "manzanita",
                "files": {
                    "manzanita/index.html": {
                        "git_blob_sha1": build_custody.git_blob_sha1(public),
                        "sha256": hashlib.sha256(public).hexdigest(),
                    }
                },
            },
            "donors": [
                {
                    "id": "public-v1",
                    "class": "public_release",
                    "custody_state": "archived",
                    "archive_scope_ids": ["public"],
                    "anchors": {"release": "1"},
                    "claim_boundary": "Historical donor.",
                }
            ],
            "gaps": [
                {
                    "id": "gap-golden",
                    "class": "visual_golden",
                    "state": "open",
                    "required_for_close": True,
                    "target": "Recover goldens.",
                    "admission": "Hash and classify them.",
                    "failure_mode": "Approval context is lost.",
                }
            ],
        }
        self.register_path.parent.mkdir(parents=True, exist_ok=True)
        self.register_path.write_text(json.dumps(self.register, indent=2) + "\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self) -> dict:
        manifest = build_custody.build_manifest(
            self.root,
            self.register_path,
            self.output_path,
            git_commit="0" * 40,
        )
        build_custody.write_manifest(manifest, self.output_path)
        return manifest

    def validate(self) -> dict:
        register, register_raw = validate_custody.load_json(self.register_path)
        manifest, _ = validate_custody.load_json(self.output_path)
        validate_custody.validate_register(register)
        return validate_custody.validate_manifest(
            self.root,
            register,
            register_raw,
            manifest,
        )

    def test_manifest_is_deterministic_and_partial(self) -> None:
        first = self.build()
        first_bytes = self.output_path.read_bytes()
        second = self.build()
        self.assertEqual(first_bytes, self.output_path.read_bytes())
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(first["status"], "PARTIAL")
        result = self.validate()
        self.assertEqual(result["status"], "PARTIAL")

    def test_manifest_detects_source_tamper(self) -> None:
        self.build()
        write(self.root / "programs/manzanita-99/README.md", "# Changed\n")
        with self.assertRaisesRegex(validate_custody.CustodyError, "SHA-256 changed"):
            self.validate()

    def test_public_route_guard_detects_change(self) -> None:
        self.build()
        write(self.root / "manzanita/index.html", "<h1>replacement</h1>\n")
        with self.assertRaisesRegex(
            validate_custody.CustodyError,
            "Historical public route changed",
        ):
            self.validate()

    def test_register_refuses_false_closure(self) -> None:
        closed = copy.deepcopy(self.register)
        closed["state"] = "closed"
        with self.assertRaisesRegex(
            validate_custody.CustodyError,
            "cannot close while required gaps remain",
        ):
            validate_custody.validate_register(closed)

    def test_require_complete_rejects_partial_manifest(self) -> None:
        self.build()
        register, register_raw = validate_custody.load_json(self.register_path)
        manifest, _ = validate_custody.load_json(self.output_path)
        validate_custody.validate_register(register)
        with self.assertRaisesRegex(validate_custody.CustodyError, "remains partial"):
            validate_custody.validate_manifest(
                self.root,
                register,
                register_raw,
                manifest,
                require_complete=True,
            )


if __name__ == "__main__":
    unittest.main()
