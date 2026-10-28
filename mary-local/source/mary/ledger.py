from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, loads_strict, sha256_json
from .errors import MaryError

LEDGER_SCHEMA = "mary/outcome-ledger@1"
RECORD_SCHEMA = "mary/outcome-record@1"
ZERO_HASH = "0" * 64


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = loads_strict(line, f"ledger line {line_number}")
        if not isinstance(row, dict):
            raise MaryError(f"ledger line {line_number} must be an object")
        rows.append(row)
    return rows


def verify_ledger(path: Path) -> dict[str, Any]:
    rows = _records(path)
    previous = ZERO_HASH
    for index, row in enumerate(rows):
        required = {"schema", "sequence", "previous_hash", "event", "record_hash"}
        if set(row) != required:
            raise MaryError(f"ledger record {index} has incorrect keys")
        if row["schema"] != RECORD_SCHEMA:
            raise MaryError(f"ledger record {index} schema mismatch")
        if row["sequence"] != index:
            raise MaryError(f"ledger record {index} sequence mismatch")
        if row["previous_hash"] != previous:
            raise MaryError(f"ledger record {index} previous_hash mismatch")
        body = {
            "schema": row["schema"],
            "sequence": row["sequence"],
            "previous_hash": row["previous_hash"],
            "event": row["event"],
        }
        expected = sha256_json(body)
        if row["record_hash"] != expected:
            raise MaryError(f"ledger record {index} digest mismatch")
        previous = expected
    return {
        "schema": LEDGER_SCHEMA,
        "status": "pass",
        "records": len(rows),
        "head_hash": previous,
        "path": str(path),
    }


def read_events(path: Path) -> list[dict[str, Any]]:
    """Verify the ledger and return its outcome events in append order."""
    verify_ledger(path)
    return [row["event"] for row in _records(path)]


def append_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    verification = verify_ledger(path)
    sequence = verification["records"]
    previous = verification["head_hash"]
    body = {
        "schema": RECORD_SCHEMA,
        "sequence": sequence,
        "previous_hash": previous,
        "event": event,
    }
    record = {**body, "record_hash": sha256_json(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_bytes(record))
        handle.flush()
        os.fsync(handle.fileno())
    verify_ledger(path)
    return record
