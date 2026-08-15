#!/usr/bin/env python3
"""Validate the Manzanita 99 program contract and complete task register."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKLOG = ROOT / "MASTER_BACKLOG.json"
SCORECARD = ROOT / "SCORECARD.json"

EXPECTED_TOTAL = 497
EXPECTED_PRIORITY = {"P0": 318, "P1": 168, "P2": 11}
EXPECTED_PHASES = {f"P{index}" for index in range(11)}


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "extract_backlog.py")], check=True)
    data = json.loads(BACKLOG.read_text(encoding="utf-8"))
    score = json.loads(SCORECARD.read_text(encoding="utf-8"))

    tasks = data.get("tasks", [])
    if len(tasks) != EXPECTED_TOTAL:
        fail(f"Expected {EXPECTED_TOTAL} tasks, found {len(tasks)}")

    ids = [task.get("id") for task in tasks]
    duplicates = sorted(task_id for task_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        fail(f"Duplicate task IDs: {duplicates}")
    id_set = set(ids)

    priorities = Counter(task.get("priority") for task in tasks)
    if dict(priorities) != EXPECTED_PRIORITY:
        fail(f"Priority totals drifted: {dict(priorities)}")

    unknown_phases = sorted({task.get("phase") for task in tasks} - EXPECTED_PHASES)
    if unknown_phases:
        fail(f"Unknown phases: {unknown_phases}")

    unresolved = []
    for task in tasks:
        for dependency in task.get("depends_on", []):
            if dependency not in id_set:
                unresolved.append((task.get("id"), dependency))
    if unresolved:
        fail(f"Unresolved task dependencies: {unresolved[:20]}")

    for task in tasks:
        required = [
            "id",
            "title",
            "priority",
            "phase",
            "workstream",
            "owner_seat",
            "status",
            "deliverable",
            "acceptance",
            "evidence_required",
            "depends_on",
        ]
        missing = [field for field in required if field not in task]
        if missing:
            fail(f"{task.get('id')} is missing fields: {missing}")
        if not task["acceptance"] or not task["evidence_required"]:
            fail(f"{task['id']} lacks acceptance or evidence requirements")

    dimensions = score.get("dimensions", [])
    if sum(item.get("weight", 0) for item in dimensions) != 100:
        fail("Scorecard weights must total 100")
    if any(item.get("target") != 99 for item in dimensions):
        fail("Every scorecard dimension must retain the 99 target")

    release = score.get("release_rule", {})
    hard_values = {
        "weighted_score_minimum": 99,
        "dimension_floor": 95,
        "p0_open_allowed": 0,
        "critical_defects_allowed": 0,
        "high_defects_allowed": 0,
        "unknown_applicable_gates_allowed": 0,
    }
    for key, expected in hard_values.items():
        if release.get(key) != expected:
            fail(f"Release rule drift: {key}={release.get(key)!r}, expected {expected!r}")

    if data.get("benchmark", {}).get("no_affiliation") != score.get("benchmark", {}).get("no_affiliation"):
        fail("No-affiliation statement drifted between backlog and scorecard")

    print(
        json.dumps(
            {
                "result": "PASS",
                "tasks": len(tasks),
                "priority": dict(priorities),
                "phases": sorted(EXPECTED_PHASES),
                "dependencies": "resolved",
                "score_weight": 100,
                "release_floor": release,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
