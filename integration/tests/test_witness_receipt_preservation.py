"""Keep qualification evidence only when it names the current application bytes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "patch_axm_witness_theme_092.py"
SPEC = importlib.util.spec_from_file_location("patch_axm_witness_theme_092", SCRIPT)
PATCHER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(PATCHER)


class WitnessReceiptPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        PATCHER.RECEIPT = Path(self.temp.name) / "receipt.json"
        self.app_bytes = 503_601
        self.app_sha = "a" * 64

    def qualified_receipt(self):
        return {
            "schema": "axm-witness/theme-patch-qualification@1",
            "release": PATCHER.RELEASE,
            "base_application": {"bytes": PATCHER.BASE_BYTES, "sha256": PATCHER.BASE_SHA256},
            "patched_application": {"bytes": self.app_bytes, "sha256": self.app_sha},
            "qualification_boundary": "Theme and independently qualified corpus identity.",
            "controls": {
                "dark_first_run_default": "PASS",
                "public_corpus_release_identity": "PASS",
            },
            "corpus_ledger": {
                "download_release": "0.9.2",
                "identity_alignment": "PASS",
                "browser_smoke": {"runtime_network_requests": 0},
            },
        }

    def test_current_source_preserves_complete_qualified_receipt(self):
        prior = self.qualified_receipt()
        original = json.dumps(prior, indent=2) + "\n"
        PATCHER.RECEIPT.write_text(original, encoding="utf-8")

        PATCHER.write_receipt(self.app_bytes, self.app_sha)

        self.assertEqual(PATCHER.RECEIPT.read_text(encoding="utf-8"), original)
        self.assertEqual(json.loads(PATCHER.RECEIPT.read_text(encoding="utf-8")), prior)

    def test_changed_source_does_not_carry_forward_qualification(self):
        PATCHER.RECEIPT.write_text(json.dumps(self.qualified_receipt()), encoding="utf-8")
        next_sha = "b" * 64

        PATCHER.write_receipt(self.app_bytes + 1, next_sha)

        current = json.loads(PATCHER.RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(
            current["patched_application"],
            {"bytes": self.app_bytes + 1, "sha256": next_sha},
        )
        self.assertNotIn("controls", current)
        self.assertNotIn("browser_observation", current)
        self.assertNotIn("corpus_ledger", current)


if __name__ == "__main__":
    unittest.main()
