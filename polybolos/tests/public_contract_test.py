#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BYTES = 117_546
EXPECTED_SHA256 = "4beaae5aec641a3f0ba3f3e6c7d6c44b3ba2284b0b70ec50e34c24b73475543f"


def main() -> None:
    path = ROOT / "index.html"
    data = path.read_bytes()
    assert len(data) == EXPECTED_BYTES
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256
    html = data.decode("utf-8")

    required = [
        "polybolos-evidence-contract/2.0.0",
        "FIRST DATA HANDOFF · COMPLETE",
        "MARK HANDOFF · COMPLETE",
        "The network disappears.",
        "The authority does not widen.",
        "“2 of 16” is not a score.",
        "No full qualification profile is selected.",
        "AVAILABLE PROSPECTIVELY",
        "NOT REQUESTED · NOT CLAIMED",
        "REFERENCE · NOT MARK SCORECARD",
        "Include original source bytes in private bundle",
    ]
    for phrase in required:
        assert phrase in html, f"missing required product language: {phrase}"

    forbidden = [
        "ACCEPTANCE ELIGIBLE FALSE",
        "MARK AUTOMATIC STATUS       INCOMPLETE",
        "IyBTdGFuZGluZyBPcmRlcnMgcHJvb2YgbG9n",
        "id=SO-CHROME-R1-00",
        "__AXM_POLYBOLOS_PAYLOAD",
        "DecompressionStream",
    ]
    for phrase in forbidden:
        assert phrase not in html, f"forbidden public content: {phrase}"

    assert not (ROOT / "assets").exists()
    assert not (ROOT / "LOADER_MANIFEST.json").exists()
    assert not (ROOT / "examples/standing_orders_proof_20260802_215108.log").exists()
    assert not (ROOT / "examples/Standing_Orders_Partition_Epoch_Report.html").exists()

    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, re.I)
    assert len(scripts) >= 4
    assert not re.search(r"<script[^>]+src=", html, re.I)

    receipt = json.loads((ROOT / "data/mark-public-receipt.json").read_text(encoding="utf-8"))
    assert receipt["publicRawBytesPackaged"] is False
    assert receipt["requestedTransaction"]["result"] == "complete"
    assert receipt["scenarioReceipt"]["result"] == "pass"
    observed = receipt["scenarioReceipt"]["observed"]
    assert observed == {
        "eventRecords": 54,
        "authorize": 10,
        "safeDeny": 5,
        "mappingDeviations": 0,
        "lastAck": 15,
        "partitionMs": 25505,
        "communications": ["UP", "DOWN", "UP"],
        "standingOrders": ["INACTIVE", "ACTIVE", "INACTIVE"],
    }
    statuses = {item["label"]: item["status"] for item in receipt["tiers"]}
    assert statuses["Presentation integration"] == "COMPLETE"
    assert statuses["Source-bound evidence"] == "COMPLETE FOR THIS HANDOFF"
    assert statuses["Bounded scenario demonstration"] == "PASS"
    assert statuses["Claim-specific qualification"] == "AVAILABLE PROSPECTIVELY"
    assert statuses["Operational acceptance"] == "NOT REQUESTED · NOT CLAIMED"

    catalog = json.loads((ROOT / "data/qualification-catalog.json").read_text(encoding="utf-8"))
    assert "no effect until it is selected" in catalog["rule"].lower()
    assert len(catalog["plans"]) >= 6
    assert len({plan["id"] for plan in catalog["plans"]}) == len(catalog["plans"])
    for plan in catalog["plans"]:
        for key in ("claim", "requires", "passes", "excludes"):
            assert plan[key], f"{plan['id']} missing {key}"

    print("public_contract_test.py: PASS")
    print(f"direct bytes {len(data)}")
    print(f"direct sha256 {EXPECTED_SHA256}")
    print(f"inline scripts {len(scripts)}")


if __name__ == "__main__":
    main()
