from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
README = ROOT / "README.md"
QUALIFICATION = ROOT / "QUALIFICATION.json"

source = HTML.read_text(encoding="utf-8")
readme = README.read_text(encoding="utf-8")

required_roles = [
    "source-custodian",
    "interpreter",
    "relationship-steward",
    "attention-sovereign",
    "execution-steward",
    "verifier",
    "continuity-steward",
]

checks = {
    "doctype": source.lstrip().lower().startswith("<!doctype html>"),
    "release_1_2_0": "Essential Attention v1.2.0" in source and "version:'1.2.0'" in source,
    "plain_no_atob": "atob(" not in source,
    "plain_no_decompression_loader": "DecompressionStream" not in source,
    "one_inline_script": source.count("<script>") == 1 and "<script src=" not in source,
    "one_inline_style": source.count("<style>") == 1,
    "network_connect_none": "connect-src 'none'" in source,
    "local_state_v3": "essential-attention/local-state@3" in source,
    "five_ordinary_places": all(
        f'data-view="{view}"' in source
        for view in ["overview", "register", "executive", "sources", "handoff"]
    ),
    "today_primary_action": all(
        token in source
        for token in ['id="todayStatus"', 'id="primaryAction"', "Best next action", "Can move safely"]
    ),
    "compact_first_visit": 'id="helpDialog"' in source and "Take the 90-second tour" in source,
    "guided_tour_5": "const TOUR_STEPS" in source
    and len(re.findall(r"\{view:'", re.search(r"const TOUR_STEPS = Object.freeze\(\[(.*?)\]\);", source, re.S).group(1))) == 5,
    "records_7": source.count("offer_id:'FAB-") == 7,
    "record_summary_contract": all(
        token in source
        for token in ["What happened", "Current state", "Next safe step", "Authority boundary", "Bounded scope"]
    ),
    "record_tabs_3": all(
        token in source
        for token in [
            'data-record-tab="summary"',
            'data-record-tab="details"',
            'data-record-tab="activity"',
            "Evidence &amp; authority",
        ]
    ),
    "decisions_5": source.count("decision_id:'EA-DEC-") == 5,
    "evidence_local_hashing": "sha256Bytes" in source and "network_transmitted:false" in source,
    "handoff_primary_flow": all(
        token in source
        for token in ['id="handoffRunButton"', 'id="handoffReplayButton"', 'id="exportPacketButton"']
    ),
    "advanced_tools": all(
        token in source
        for token in ["Advanced tools", "effect firewall", 'id="importPacketButton"', 'id="downloadAppButton"']
    ),
    "contained_roles_7": all(f"id:'{role}'" in source for role in required_roles),
    "effect_firewall": "external effect blocked" in source,
    "successor_replay": "Cold replay passed" in source,
    "motion_polish": "dialog-in" in source and "sheet-in" in source and "prefers-reduced-motion" in source,
    "responsive_floor": "@media(max-width:780px)" in source,
    "case_ledger_flavor": "Operating Desk" in source and "pixel-dandelion" in source,
    "embedded_house_fonts": all(
        token in source for token in ["Barlow Condensed", "IBM Plex Mono", "IBM Plex Sans", "Lora"]
    ) and "font-src data:" in source,
    "frozen_palette": all(token in source for token in ["#0D0C09", "#ECE7D8", "#7C7F57", "#C24B2C"]),
    "readme_present": README.exists() and len(readme) > 8000,
    "readme_operating_desk": "## v1.2.0 operating desk" in readme.lower(),
    "readme_contents": "The default FAB cartridge contains seven case objects" in readme,
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("qualification failed: " + ", ".join(failed))

script = re.search(r"<script>(.*?)</script>", source, re.S)
if not script:
    raise SystemExit("inline runtime script missing")
(Path(tempfile.gettempdir()) / "essential-attention-inline.js").write_text(script.group(1), encoding="utf-8")

artifact_bytes = source.encode("utf-8")
readme_bytes = readme.encode("utf-8")
digest = hashlib.sha256(artifact_bytes).hexdigest()
receipt = {
    "schema": "essential-attention/pages-qualification@4",
    "release": "1.2.0",
    "artifact": "essential-attention/index.html",
    "sha256": digest,
    "bytes": len(artifact_bytes),
    "readme_bytes": len(readme_bytes),
    "checks": checks,
    "operator_surface": "AXM Operating Desk with Today, Records, Decisions, Evidence, Handoff, and progressive advanced tools",
    "external_effect_adapters": 0,
}
QUALIFICATION.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
