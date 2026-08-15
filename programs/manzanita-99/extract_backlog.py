#!/usr/bin/env python3
"""Expand the canonical Manzanita 99 backlog and emit a practical CSV view."""

from __future__ import annotations

import base64
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "MASTER_BACKLOG.json.gz.b64"
JSON_OUT = ROOT / "MASTER_BACKLOG.json"
CSV_OUT = ROOT / "MASTER_BACKLOG.csv"


def scalar(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def main() -> None:
    encoded = SOURCE.read_text(encoding="utf-8").strip()
    raw = gzip.decompress(base64.b64decode(encoded, validate=True))
    data = json.loads(raw.decode("utf-8"))

    expected = data.get("summary", {}).get("tasks_total")
    tasks = data.get("tasks", [])
    if expected != len(tasks):
        raise SystemExit(f"Task-count mismatch: summary={expected!r}, tasks={len(tasks)}")

    JSON_OUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    fields = [
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
    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for task in tasks:
            writer.writerow({field: scalar(task.get(field)) for field in fields})

    print(f"Expanded {len(tasks)} tasks to {JSON_OUT.name} and {CSV_OUT.name}")


if __name__ == "__main__":
    main()
