#!/usr/bin/env python3
"""Extract the exact source-audit, P7, P8, and P9 run blocks from the admitted workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

import yaml

REQUIRED_STEP_NAMES = (
    "Audit the exact estate reopening ledger",
    "Rebuild the exact P7 and P8 evidence chain",
    "Build the exact complete-coverage parity register",
    "Run the contained multidisciplinary P9 review",
)


class ReplayError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ReplayError(f"Cannot load workflow {path}: {exc}") from exc
    require(isinstance(value, dict), "Workflow must contain a mapping")
    return value


def workflow_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = workflow.get("jobs")
    require(isinstance(jobs, dict) and jobs, "Workflow contains no jobs")
    candidates = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        names = {str(row.get("name")) for row in steps if isinstance(row, dict)}
        if set(REQUIRED_STEP_NAMES).issubset(names):
            candidates.append((job_id, steps))
    require(len(candidates) == 1, f"Expected one P9 qualification job, observed {len(candidates)}")
    return candidates[0][1]


def select_steps(workflow: dict[str, Any]) -> list[dict[str, str]]:
    steps = workflow_steps(workflow)
    selected = []
    for required_name in REQUIRED_STEP_NAMES:
        matches = [
            row for row in steps
            if isinstance(row, dict) and row.get("name") == required_name
        ]
        require(
            len(matches) == 1,
            f"P9 workflow step is missing or duplicated: {required_name}",
        )
        run = matches[0].get("run")
        require(isinstance(run, str) and run.strip(), f"P9 step has no run block: {required_name}")
        selected.append({"name": required_name, "run": run.rstrip()})
    return selected


def render_script(selected: list[dict[str, str]]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'ROOT="${REPO_ROOT:-$PWD}"',
        'cd "$ROOT"',
    ]
    for index, row in enumerate(selected, start=1):
        lines.extend(
            [
                "",
                f"echo {shlex.quote('### ' + row['name'])}",
                "(",
                "  set -euo pipefail",
                *["  " + line for line in row["run"].splitlines()],
                ")",
            ]
        )
    return "\n".join(lines) + "\n"


def build_plan(workflow_path: Path, script_path: Path, receipt_path: Path) -> dict[str, Any]:
    workflow_path = workflow_path.resolve()
    script_path = script_path.resolve()
    receipt_path = receipt_path.resolve()
    workflow = load_workflow(workflow_path)
    selected = select_steps(workflow)
    script = render_script(selected)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
    receipt: dict[str, Any] = {
        "schema": "axm-tools/manzanita-p9-replay-plan@1",
        "result": "PASS",
        "workflow": workflow_path.as_posix(),
        "workflow_sha256": sha256_file(workflow_path),
        "step_count": len(selected),
        "step_names": [row["name"] for row in selected],
        "step_sha256": {
            row["name"]: sha256_bytes(row["run"].encode("utf-8"))
            for row in selected
        },
        "script": script_path.as_posix(),
        "script_sha256": sha256_bytes(script.encode("utf-8")),
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": "This plan replays only the exact source audit, P7, P8, P9 build, and P9 contained-review commands from the admitted workflow. It imports no merge, publication, deployment, external-effect, score, or canonical task authority.",
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--output-script", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_plan(args.workflow, args.output_script, args.receipt)
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "step_count": receipt["step_count"],
                "workflow_sha256": receipt["workflow_sha256"],
                "script_sha256": receipt["script_sha256"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ReplayError as exc:
        raise SystemExit(str(exc)) from exc
