from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "casezero.py"


class CaseZeroTests(unittest.TestCase):
    def invoke(self, source: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "intake",
                "--input", str(source),
                "--output", str(output),
                "--case-id", "TEST-CZ-001",
                "--custody-mode", "redcat_local",
                "--as-of", "2026-09-01T12:00:00Z",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_clean_intake_is_deterministic_and_body_free(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            source = base / "source"
            source.mkdir()
            (source / "proposal.md").write_text("Fixed PoC scope\n", encoding="utf-8")
            (source / "acceptance-tests.md").write_text("PASS when schema validates\n", encoding="utf-8")
            first = base / "first"
            second = base / "second"
            one = self.invoke(source, first)
            two = self.invoke(source, second)
            self.assertEqual(one.returncode, 0, one.stderr)
            self.assertEqual(two.returncode, 0, two.stderr)
            m1 = json.loads((first / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
            m2 = json.loads((second / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(m1["corpus_digest"], m2["corpus_digest"])
            self.assertFalse(m1["source_root_disclosed"])
            self.assertEqual(m1["source_files_copied"], 0)
            self.assertEqual(m1["network_calls"], 0)
            self.assertNotIn(str(source), (first / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertTrue((first / "SHA256SUMS").exists())

    def test_secret_signal_holds_without_disclosing_value(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            source = base / "source"
            source.mkdir()
            secret = "AKIAABCDEFGHIJKLMNOP"
            (source / "environment.txt").write_text(f"AWS_KEY={secret}\n", encoding="utf-8")
            output = base / "output"
            result = self.invoke(source, output)
            self.assertEqual(result.returncode, 3)
            state = json.loads((output / "CASE_ZERO_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(state["state"], "HOLD_REDACTION_REQUIRED")
            rendered = (output / "SOURCE_MANIFEST.json").read_text(encoding="utf-8")
            self.assertNotIn(secret, rendered)
            self.assertIn("aws_access_key", rendered)

    def test_nonempty_output_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            source = base / "source"
            source.mkdir()
            (source / "notes.txt").write_text("x", encoding="utf-8")
            output = base / "output"
            output.mkdir()
            (output / "existing.txt").write_text("do not overwrite", encoding="utf-8")
            result = self.invoke(source, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("absent or empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
