from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import replay_p9_workflow as replay  # noqa: E402


class ReplayEnvironmentReceiptTests(unittest.TestCase):
    def test_replay_receipt_records_every_explicit_secret_environment_name(self) -> None:
        steps = []
        for index, name in enumerate(replay.REQUIRED_STEP_NAMES):
            row = {"name": name, "run": f"echo {index}"}
            if index == 1:
                row["env"] = {
                    "USGS_API_KEY": "${{ secrets.USGS_API_KEY }}",
                    "AIRNOW_API_KEY": "${{ secrets.AIRNOW_API_KEY }}",
                }
            steps.append(row)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / "p9-workflow.json"
            script = root / "replay-p9.sh"
            receipt = root / "P9_REPLAY_PLAN.json"
            workflow.write_text(
                json.dumps({"jobs": {"qualify": {"steps": steps}}}, indent=2) + "\n",
                encoding="utf-8",
            )

            plan = replay.build_plan(workflow, script, receipt)
            retained = json.loads(receipt.read_text(encoding="utf-8"))
            script_text = script.read_text(encoding="utf-8")

        self.assertEqual(
            plan["required_environment"],
            ["AIRNOW_API_KEY", "USGS_API_KEY"],
        )
        self.assertEqual(retained["required_environment"], plan["required_environment"])
        self.assertIn('export AIRNOW_API_KEY="${AIRNOW_API_KEY-}"', script_text)
        self.assertIn('export USGS_API_KEY="${USGS_API_KEY-}"', script_text)


if __name__ == "__main__":
    unittest.main()
