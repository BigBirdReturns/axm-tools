#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREFIX = "manzanita-next/review/mw-habitat-live-photo-030-continuation/"
WORKFLOW = ".github/workflows/manzanita-useful-plant-v30-continuation-review.yml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()

    process = subprocess.run(
        ["git", "diff", "--name-only", args.base, args.head],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    paths = [path for path in process.stdout.splitlines() if path]
    rejected = [path for path in paths if path != WORKFLOW and not path.startswith(PREFIX)]
    public = [path for path in paths if path == "manzanita" or path.startswith("manzanita/")]
    checks = {
        "git_diff_succeeded": process.returncode == 0,
        "changed_paths_nonempty": bool(paths),
        "all_paths_allowed": not rejected,
        "public_manzanita_untouched": not public,
        "workflow_in_review_scope": WORKFLOW in paths,
        "review_tree_in_scope": any(path.startswith(PREFIX) for path in paths),
    }
    result = {
        "schema": "manzanita/useful-plant-v30-bootstrap-scope@2",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": "PASS" if all(checks.values()) else "FAIL",
        "base": args.base,
        "head": args.head,
        "changed_paths": paths,
        "rejected_paths": rejected,
        "public_route_paths": public,
        "checks": checks,
        "operator_visual_acceptance": "ABSENT",
        "release_authorized": False,
        "public_route_effect": "none",
        "external_effect": "none",
    }
    output = ROOT / PREFIX / "BOOTSTRAP_SCOPE_RECEIPT.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
