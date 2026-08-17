#!/usr/bin/env python3
"""Extract the canonical P7 build and browser blocks for P8 replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "axm-tools/manzanita-p7-replay-plan@1"

REQUIRED_STEP_NAMES = (
    "Acquire the exact live source foundation",
    "Validate every source receipt and retained payload",
    "Rebuild the exact public-safe place donor",
    "Rebuild the seven-aperture donor",
    "Rebuild the Street Glide donors",
    "Rebuild the eight-overlay donor",
    "Rebuild the five-role and FAB handoff donors",
    "Build the exact whole experience",
    "Exercise the whole experience in Chromium",
)


class ReplayError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def select_steps(workflow: dict[str, Any]) -> list[dict[str, str]]:
    jobs = workflow.get("jobs")
    require(isinstance(jobs, dict), "P7 workflow lacks jobs")
    qualify = jobs.get("qualify")
    require(isinstance(qualify, dict), "P7 workflow lacks qualify job")
    raw_steps = qualify.get("steps")
    require(isinstance(raw_steps, list), "P7 qualify job lacks steps")
    by_name: dict[str, list[dict[str, Any]]] = {}
    for step in raw_steps:
        if isinstance(step, dict) and isinstance(step.get("name"), str):
            by_name.setdefault(step["name"], []).append(step)

    selected: list[dict[str, str]] = []
    for name in REQUIRED_STEP_NAMES:
        matches = by_name.get(name, [])
        require(len(matches) == 1, f"P7 workflow step {name!r} is missing or duplicated")
        run = matches[0].get("run")
        require(isinstance(run, str) and run.strip(), f"P7 workflow step {name!r} lacks a run block")
        selected.append({
            "name": name,
            "run": run.rstrip() + "\n",
            "run_sha256": sha256_bytes(run.encode("utf-8")),
        })
    return selected


def render_script(selected: list[dict[str, str]]) -> str:
    rows = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'ROOT="$(pwd)"',
        'test -f "$ROOT/.github/workflows/manzanita-whole-experience.yml"',
    ]
    for step in selected:
        rows.extend(["", f"echo {shlex.quote('### ' + step['name'])}", "("])
        if step["name"] == "Acquire the exact live source foundation":
            rows.extend(["  set +e", *["  " + line for line in step["run"].splitlines()], "  status=$?", '  echo "P7 acquisition exit code: $status"', "  exit 0"])
        else:
            rows.extend(["  set -euo pipefail", *["  " + line for line in step["run"].splitlines()]])
        rows.append(")")
    return "\n".join(rows) + "\n"


def build_plan(workflow_path: Path, script_path: Path, receipt_path: Path) -> dict[str, Any]:
    workflow_path = workflow_path.resolve()
    require(workflow_path.is_file(), f"P7 workflow is missing: {workflow_path}")
    raw = workflow_path.read_bytes()
    workflow = yaml.safe_load(raw.decode("utf-8"))
    require(isinstance(workflow, dict), "P7 workflow did not parse as a mapping")
    selected = select_steps(workflow)
    script = render_script(selected)
    script_path = script_path.resolve()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "result": "PASS",
        "workflow": {
            "path": workflow_path.as_posix(),
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
        },
        "step_count": len(selected),
        "steps": [{"name": row["name"], "run_sha256": row["run_sha256"]} for row in selected],
        "script": {
            "path": script_path.as_posix(),
            "bytes": len(script.encode("utf-8")),
            "sha256": sha256_bytes(script.encode("utf-8")),
        },
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": "This plan replays the exact P7 source, donor, whole-experience, and browser run blocks. It does not rerun the P7 board decision, mutate the P7 source workflow, authorize public release, or create a canonical task transition.",
    }
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    receipt["payload_sha256"] = sha256_bytes(payload)
    receipt_path = receipt_path.resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, default=Path(".github/workflows/manzanita-whole-experience.yml"))
    parser.add_argument("--output-script", type=Path, default=Path("/tmp/replay-p7.sh"))
    parser.add_argument("--receipt", type=Path, default=Path("manzanita-next/qualification/out/P7_REPLAY_PLAN.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build_plan(args.workflow, args.output_script, args.receipt)
    print(json.dumps({
        "result": receipt["result"],
        "step_count": receipt["step_count"],
        "workflow_sha256": receipt["workflow"]["sha256"],
        "script_sha256": receipt["script"]["sha256"],
        "receipt_sha256": receipt["payload_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
