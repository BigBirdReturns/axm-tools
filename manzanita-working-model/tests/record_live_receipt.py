#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RELEASE = "mw-working-model-v1.1.0"
RECEIPT = REPO / ".github" / "receipts" / "manzanita-working-model-live-v1.1.0.json"


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    byte_manifest = load(os.environ["BYTE_MANIFEST"])
    browser_result = load(os.environ["BROWSER_RESULT"])
    pages_receipt = load(REPO / ".github" / "pages-deployment.json")
    release_contract = load(REPO / "manzanita-working-model" / "RELEASE_CONTRACT.json")
    trigger_sha = os.environ["TRIGGER_SHA"]

    assert byte_manifest["result"] == "PASS_EXACT_LIVE_RELEASE_BYTES"
    assert browser_result["result"] == "PASS_LIVE_WORKING_MODEL_CHROMIUM_RELEASE_CAMPAIGN"
    assert pages_receipt["source_sha"] == trigger_sha
    assert release_contract["release"] == RELEASE
    assert byte_manifest["source_sha"] == trigger_sha
    assert browser_result["source_sha"] == trigger_sha
    assert byte_manifest["release_file_count"] == 6
    assert byte_manifest["rendered_photography"] is False
    assert byte_manifest["dead_visual_assets_in_release"] is False
    assert browser_result["rendered_images"] == 0
    assert browser_result["minimum_text_floor_css_px"] == 11

    receipt = {
        "schema": "manzanita-works/working-model-public-release-receipt@3",
        "result": "PASS_PUBLIC_WORKING_MODEL_V1_1_RELEASED_NO_INSTITUTIONAL_EFFECT",
        "release": RELEASE,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_sha": trigger_sha,
        "repository_head_when_recorded": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "page_url": byte_manifest["page_url"],
        "root_url": byte_manifest["root_url"],
        "proofs": {
            "static_release_contract": "PASS_WORKING_MODEL_STATIC_RELEASE_CONTRACT",
            "local_chromium": "PASS_WORKING_MODEL_CHROMIUM_RELEASE_CAMPAIGN",
            "exact_live_bytes": byte_manifest["result"],
            "live_chromium": browser_result["result"],
            "root_directory_link": byte_manifest["root_directory_link"],
            "release_file_count": 6,
            "rendered_photography": False,
            "dead_visual_assets_in_release": False,
            "minimum_text_floor_css_px": 11,
            "height_budgets": "PASS",
        },
        "live_byte_readback": byte_manifest,
        "live_browser": browser_result,
        "pages_deployment": pages_receipt,
        "workflow": {
            "run_id": int(os.environ["RUN_ID"]),
            "run_attempt": int(os.environ["RUN_ATTEMPT"]),
            "artifact_id": int(os.environ["ARTIFACT_ID"]),
            "artifact_url": os.environ["ARTIFACT_URL"],
            "artifact_digest": os.environ["ARTIFACT_DIGEST"],
        },
        "authority": {
            "repository_owner_publication_authority_exercised": True,
            "public_static_route_published": True,
            "institutional_acceptance": False,
            "participant_consent": False,
            "field_authority": False,
            "spend_authority": False,
            "assignment_authority": False,
            "representation_authority": False,
            "eligibility_or_award_authority": False,
            "program_external_effect": "none",
        },
        "terminal_condition": "All six public files matched the merged source bytes; local and live browser campaigns passed; the public surface contains no rendered photography, dead visual asset, stale candidate rhetoric, sub-11px text, document overflow, or unbounded pilot effect."
    }

    if RECEIPT.exists():
        previous = load(RECEIPT)
        if previous.get("source_sha") == trigger_sha and previous.get("result") == receipt["result"]:
            print("Exact live-release receipt already recorded for this source SHA.")
            return

    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
