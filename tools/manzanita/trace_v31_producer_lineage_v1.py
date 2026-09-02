#!/usr/bin/env python3
"""Fail-closed compatibility entrypoint for the superseded V31 producer-lineage tracer."""
from __future__ import annotations

import json
import os
from pathlib import Path

RESULT = "HOLD_SUPERSEDED_BY_V31_PRODUCER_LINEAGE_FALSE_POSITIVE_CORRECTION_V1"
CORRECTION = "V31_PRODUCER_LINEAGE_FALSE_POSITIVE_CORRECTION_RECEIPT_V1.json"
SUPERSEDED_RUN = 33678010810


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(os.getenv("V31_LINEAGE_OUT", "/tmp/v31-producer-lineage-v1"))
    root.mkdir(parents=True, exist_ok=True)

    census = {
        "schema": "manzanita/v31-producer-lineage-census@1",
        "result": RESULT,
        "classification": "SUPERSEDED_HEURISTIC_OUTPUT_NO_PRODUCER_AUTHORITY",
        "superseded_run_id": SUPERSEDED_RUN,
        "superseded_result": "PASS_PRODUCER_LINEAGE_OBSERVED_REGENERATION_CANDIDATES_EMITTED",
        "correction_receipt": CORRECTION,
        "reason": (
            "The prior tracer scanned its own target constants, admitted generic numeric matches, "
            "and promoted any Git or log observation to producer standing through bool(gm or lm)."
        ),
        "raw_exact_targets": ["neighborhood_cached"],
        "producer_regeneration_eligible": False,
        "producer_regeneration_executed": False,
        "v2_intake_invoked": False,
        "queue_advanced": False,
        "v15_created": False,
        "authority": {
            "product_files_modified": 0,
            "merge_authorized": False,
            "release_authorized": False,
            "public_route_effect": "none",
            "pages_effect": "none",
            "external_effect": "none",
        },
    }
    receipt = {
        "schema": "manzanita/v31-producer-lineage-receipt@1",
        "result": RESULT,
        "classification": census["classification"],
        "correction_receipt": CORRECTION,
        "superseded_run_id": SUPERSEDED_RUN,
        "regeneration_executed": False,
        "v2_intake_invoked": False,
        "queue_advanced": False,
        "v15_created": False,
        "authority": census["authority"],
    }
    status = f"""# V31 producer-lineage tracer\n\n`{RESULT}`\n\nThis compatibility entrypoint is intentionally fail-closed. Run {SUPERSEDED_RUN} is superseded by `{CORRECTION}` because its observation heuristic did not prove executable producer custody, complete producer inputs, or exact deterministic regeneration. No scan, regeneration, intake, product mutation, merge, release, or deployment is performed.\n"""

    write_json(root / "V31_PRODUCER_LINEAGE_CENSUS_V1.json", census)
    write_json(root / "V31_PRODUCER_LINEAGE_EXECUTION_RECEIPT_V1.json", receipt)
    (root / "V31_PRODUCER_LINEAGE_RELEASE_STATUS_V1.md").write_text(status, encoding="utf-8")
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
