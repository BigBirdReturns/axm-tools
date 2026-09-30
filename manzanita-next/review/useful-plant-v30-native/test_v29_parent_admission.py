#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("v29_parent_gate", HERE / "verify_v29_parent.py")
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, members[name])


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def contract_for(path: Path, members: dict[str, bytes], semantic: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required_members = [
        {"path": name, "bytes": len(payload), "sha256": sha(payload)}
        for name, payload in sorted(members.items())
        if name != "SEAL.json"
    ]
    required_members.append({"path": "SEAL.json"})
    payload = path.read_bytes()
    return {
        "schema": "test",
        "gate_id": "TEST-V29",
        "parent_release_id": "mw-habitat-live-photo-029",
        "required_archive": {
            "filename": path.name,
            "bytes": len(payload),
            "sha256": sha(payload),
        },
        "required_members": required_members,
        "semantic_receipts": semantic,
        "authority": {
            "operator_visual_acceptance": "ABSENT",
            "merge_authorized": False,
            "release_authorized": False,
            "public_route_effect": "none",
            "pages_deployment_effect": "none",
            "external_effect": "none",
        },
        "next_gate_after_pass": "next",
    }


def valid_fixture(root: Path) -> tuple[Path, dict[str, Any], dict[str, bytes]]:
    qualification = {
        "schema": "qualification",
        "release_id": "mw-habitat-live-photo-029",
        "result": "PASS",
        "operator_acceptance": "absent",
        "release_authorized": False,
        "external_effect": "none",
    }
    identity = {
        "schema": "identity",
        "release_id": "mw-habitat-live-photo-029",
        "result": "PASS",
    }
    members: dict[str, bytes] = {
        "index.html": b"same household\n",
        "mw-habitat-live-photo-029.STANDALONE.html": b"same household\n",
        "receipts/QUALIFICATION_RECEIPT.json": canonical_json(qualification),
        "receipts/IDENTITY_CONTINUITY_RECEIPT.json": canonical_json(identity),
    }
    preliminary_rows = [
        {"path": name, "bytes": len(payload), "sha256": sha(payload)}
        for name, payload in sorted(members.items())
    ]
    seal = {
        "schema": "seal",
        "release_id": "mw-habitat-live-photo-029",
        "result": "PASS",
        "operator_acceptance": "absent",
        "release_authorized": False,
        "external_effect": "none",
        "files": preliminary_rows,
    }
    members["SEAL.json"] = canonical_json(seal)
    archive = root / "fixture.zip"
    make_zip(archive, members)
    semantic = {
        "qualification": {
            "path": "receipts/QUALIFICATION_RECEIPT.json",
            "required": qualification,
        },
        "identity_continuity": {
            "path": "receipts/IDENTITY_CONTINUITY_RECEIPT.json",
            "required": identity,
        },
        "seal": {
            "path": "SEAL.json",
            "required": {
                key: seal[key]
                for key in (
                    "schema",
                    "release_id",
                    "result",
                    "operator_acceptance",
                    "release_authorized",
                    "external_effect",
                )
            },
            "member_ledger_field": "files",
        },
    }
    return archive, contract_for(archive, members, semantic), members


class ParentAdmissionTests(unittest.TestCase):
    def test_exact_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, contract, _ = valid_fixture(Path(tmp))
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "PASS_EXACT_V29_PARENT_ADMITTED")
            self.assertTrue(receipt["archive_admitted"])
            self.assertFalse(receipt["release_authorized"])

    def test_missing_archive_holds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, contract, _ = valid_fixture(Path(tmp))
            archive.unlink()
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "HOLD_PARENT_ARCHIVE_UNMOUNTED")
            self.assertFalse(receipt["archive_admitted"])
            self.assertEqual(receipt["operator_visual_acceptance"], "ABSENT")

    def test_archive_identity_drift_fails_before_admission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, contract, _ = valid_fixture(Path(tmp))
            with archive.open("ab") as handle:
                handle.write(b"drift")
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "FAIL_PARENT_ADMISSION")
            self.assertFalse(receipt["archive_admitted"])

    def test_member_drift_fails_even_when_archive_contract_is_rebased(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, contract, members = valid_fixture(root)
            members["index.html"] = b"changed\n"
            make_zip(archive, members)
            payload = archive.read_bytes()
            contract["required_archive"]["bytes"] = len(payload)
            contract["required_archive"]["sha256"] = sha(payload)
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "FAIL_PARENT_ADMISSION")
            self.assertTrue(any(not row["pass"] and "index.html" in row["name"] for row in receipt["checks"]))

    def test_semantic_authority_escalation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, contract, members = valid_fixture(root)
            qualification = json.loads(members["receipts/QUALIFICATION_RECEIPT.json"])
            qualification["release_authorized"] = True
            members["receipts/QUALIFICATION_RECEIPT.json"] = canonical_json(qualification)
            seal = json.loads(members["SEAL.json"])
            for row in seal["files"]:
                if row["path"] == "receipts/QUALIFICATION_RECEIPT.json":
                    payload = members[row["path"]]
                    row["bytes"] = len(payload)
                    row["sha256"] = sha(payload)
            members["SEAL.json"] = canonical_json(seal)
            make_zip(archive, members)
            contract = contract_for(archive, members, contract["semantic_receipts"])
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "FAIL_PARENT_ADMISSION")
            self.assertTrue(any(row["name"] == "qualification: release_authorized" and not row["pass"] for row in receipt["checks"]))

    def test_path_traversal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, contract, members = valid_fixture(root)
            members["../escape.txt"] = b"no"
            make_zip(archive, members)
            contract = contract_for(archive, members, contract["semantic_receipts"])
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "FAIL_PARENT_ADMISSION")
            self.assertTrue(any(row["name"] == "ZIP paths safe" and not row["pass"] for row in receipt["checks"]))

    def test_case_collision_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, contract, members = valid_fixture(root)
            members["INDEX.HTML"] = b"collision"
            make_zip(archive, members)
            contract = contract_for(archive, members, contract["semantic_receipts"])
            receipt = GATE.evaluate_archive(archive, contract)
            self.assertEqual(receipt["result"], "FAIL_PARENT_ADMISSION")
            self.assertTrue(any(row["name"] == "ZIP paths case-unique" and not row["pass"] for row in receipt["checks"]))


if __name__ == "__main__":
    unittest.main()
