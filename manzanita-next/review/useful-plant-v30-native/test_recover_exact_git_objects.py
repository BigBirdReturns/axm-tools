#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "recover_exact_git_objects.py"
SPEC = importlib.util.spec_from_file_location("recover_exact_git_objects", MODULE_PATH)
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recovery
SPEC.loader.exec_module(recovery)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def git(
    repo: Path, *args: str, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        input=input_bytes,
        capture_output=True,
        check=True,
    )


class ExactGitObjectRecoveryTests(unittest.TestCase):
    def test_safe_member_name(self) -> None:
        self.assertTrue(recovery.safe_member_name("safe/path/file.txt"))
        self.assertFalse(recovery.safe_member_name("../escape.txt"))
        self.assertFalse(recovery.safe_member_name("/absolute/file.txt"))
        self.assertFalse(recovery.safe_member_name(r"C:\escape.txt"))

    def test_full_cli_recovers_all_three_carrier_classes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.invalid")
            git(repo, "config", "user.name", "Test Runner")

            origin = (
                b'<svg viewBox="0 0 1600 1000">'
                b'<path d="M0 0h1v1z"/></svg>\n'
            )
            cached = b"RIFF" + (b"CACHED-PLANT-BYTES-" * 11) + b"WEBP"
            v29 = zip_bytes({"MANIFEST.json": b'{"release":"v29"}\n'})
            carrier = zip_bytes(
                {"nested/mw-habitat-live-photo-029.zip": v29}
            )
            html = (
                b'<html><body><img src="data:image/webp;base64,'
                + base64.b64encode(cached)
                + b'"></body></html>\n'
            )
            (repo / "embedded.html").write_bytes(html)
            (repo / "carrier.zip").write_bytes(carrier)
            git(repo, "add", "embedded.html", "carrier.zip")
            git(repo, "commit", "-qm", "add bounded carriers")

            dangling = git(
                repo, "hash-object", "-w", "--stdin", input_bytes=origin
            )
            dangling_oid = dangling.stdout.decode().strip()
            self.assertTrue(dangling_oid)

            parent_contract = root / "V29_PARENT_ADMISSION_CONTRACT.json"
            plant_contract = root / "PLANT_DONOR_ADMISSION_CONTRACT.json"
            parent_contract.write_text(
                json.dumps(
                    {
                        "required_archive": {
                            "filename": "mw-habitat-live-photo-029.zip",
                            "bytes": len(v29),
                            "sha256": sha256(v29),
                        }
                    }
                ),
                encoding="utf-8",
            )
            plant_contract.write_text(
                json.dumps(
                    {
                        "required_donors": {
                            "origin": {
                                "filename": "plant-origin.svg",
                                "bytes": len(origin),
                                "sha256": sha256(origin),
                                "media_type": "image/svg+xml",
                            },
                            "cached": {
                                "filename": "plant-derived-reference.webp",
                                "bytes": len(cached),
                                "sha256": sha256(cached),
                                "media_type": "image/webp",
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            output = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--repo",
                    str(repo),
                    "--output-dir",
                    str(output),
                    "--parent-contract",
                    str(parent_contract),
                    "--plant-contract",
                    str(plant_contract),
                    "--max-blob-bytes",
                    "10485760",
                    "--max-zip-entry-bytes",
                    "10485760",
                    "--max-zip-total-bytes",
                    "10485760",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual((output / "plant-origin.svg").read_bytes(), origin)
            self.assertEqual(
                (output / "plant-derived-reference.webp").read_bytes(), cached
            )
            self.assertEqual(
                (output / "mw-habitat-live-photo-029.zip").read_bytes(), v29
            )

            receipt = json.loads(
                (output / "EXACT_GIT_OBJECT_RECOVERY_RECEIPT.json").read_text()
            )
            self.assertEqual(
                receipt["result"], "PASS_EXACT_GIT_OBJECT_SCAN_COMPLETE"
            )
            self.assertTrue(receipt["plant_pair_recovered"])
            self.assertTrue(receipt["v29_archive_recovered"])
            self.assertEqual(
                receipt["targets"]["plant_origin"]["matches"][0]["source"][
                    "git_blob_sha1"
                ],
                dangling_oid,
            )
            self.assertEqual(
                receipt["targets"]["plant_cached"]["matches"][0]["source"][
                    "carrier_kind"
                ],
                "embedded_data_url",
            )
            self.assertEqual(
                receipt["targets"]["v29_archive"]["matches"][0]["source"][
                    "carrier_kind"
                ],
                "zip_member",
            )
            self.assertEqual(receipt["operator_visual_acceptance"], "ABSENT")
            self.assertFalse(receipt["merge_authorized"])
            self.assertFalse(receipt["release_authorized"])
            self.assertEqual(receipt["public_route_effect"], "none")
            self.assertEqual(receipt["pages_deployment_effect"], "none")
            self.assertEqual(receipt["external_effect"], "none")

    def test_size_collision_does_not_materialize_target(self) -> None:
        target_payload = b"exact"
        wrong_payload = b"wrong"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            target = recovery.Target(
                target_id="object",
                filename="object.bin",
                bytes=len(target_payload),
                sha256=sha256(target_payload),
            )
            scanner = recovery.RecoveryScanner(
                {"object": target},
                output,
                max_blob_bytes=1024,
                max_zip_entry_bytes=1024,
                max_zip_total_bytes=4096,
                max_zip_depth=1,
            )
            scanner.consider(wrong_payload, {"source_type": "test"})
            self.assertFalse((output / "object.bin").exists())
            self.assertEqual(len(scanner.size_collisions), 1)


if __name__ == "__main__":
    unittest.main()
