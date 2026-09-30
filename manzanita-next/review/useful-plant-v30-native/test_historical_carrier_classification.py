#!/usr/bin/env python3
from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import io
import tarfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "classify_historical_carrier.py"
SPEC = importlib.util.spec_from_file_location("historical_carrier", MODULE_PATH)
assert SPEC and SPEC.loader
historical_carrier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(historical_carrier)


def make_tar_gz(name: str = "safe/file.txt") -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
        payload = b"bounded historical carrier\n"
        info = tarfile.TarInfo(name=name)
        info.size = len(payload)
        info.mtime = 0
        archive.addfile(info, io.BytesIO(payload))
    return gzip.compress(tar_buffer.getvalue(), mtime=0)


class HistoricalCarrierClassificationTests(unittest.TestCase):
    def test_complete_safe_archive_is_valid(self) -> None:
        payload = make_tar_gz()
        encoded = base64.b64encode(payload)
        specs = historical_carrier.candidate_specs(encoded)
        self.assertEqual(len(specs), 1)
        evaluation, decoded = historical_carrier.evaluate_candidate(*specs[0])
        self.assertTrue(evaluation["gzip_valid"])
        self.assertTrue(evaluation["tar_valid"])
        self.assertEqual(decoded, payload)
        self.assertEqual(
            evaluation["decoded_sha256"], hashlib.sha256(payload).hexdigest()
        )

    def test_unpadded_three_remainder_tests_padding_and_terminal_symbols(self) -> None:
        encoded = b"YWJ"
        specs = historical_carrier.candidate_specs(encoded)
        self.assertEqual(len(specs), 65)
        self.assertEqual(specs[0][0], "padding_only")
        self.assertEqual(specs[1][0], "append_missing_terminal_symbol")

    def test_truncated_archive_remains_invalid(self) -> None:
        payload = make_tar_gz()
        encoded = base64.b64encode(payload)[:-17]
        evaluations = [
            historical_carrier.evaluate_candidate(*spec)[0]
            for spec in historical_carrier.candidate_specs(encoded)
        ]
        self.assertFalse(any(row.get("tar_valid") for row in evaluations))

    def test_unsafe_tar_member_is_rejected(self) -> None:
        payload = make_tar_gz("../escape.txt")
        encoded = base64.b64encode(payload)
        evaluation, _ = historical_carrier.evaluate_candidate(
            *historical_carrier.candidate_specs(encoded)[0]
        )
        self.assertTrue(evaluation["gzip_valid"])
        self.assertFalse(evaluation["tar_valid"])
        self.assertEqual(evaluation["unsafe_tar_members"], ["../escape.txt"])


if __name__ == "__main__":
    unittest.main()
