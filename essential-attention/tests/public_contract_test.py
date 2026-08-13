from __future__ import annotations

import hashlib
import json
import re
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

setup_labels = [
    "Understand the loaded case",
    "Inspect all seven records",
    "Review all five decisions",
    "Run the contained seats",
    "Pass cold continuity replay",
    "Export the portable packet",
]

role_home_labels = [
    "Whole case",
    "Source custody",
    "Relationship stewardship",
    "Decision authority",
    "Execution preparation",
    "Continuity and audit",
]

checks = {
    "doctype": source.lstrip().lower().startswith("<!doctype html>"),
    "release_1_1_0": "Essential Attention v1.1.0" in source and "version:'1.1.0'" in source,
    "plain_no_atob": "atob(" not in source,
    "plain_no_decompression_loader": "DecompressionStream" not in source,
    "one_inline_script": source.count("<script>") == 1 and "<script src=" not in source,
    "one_inline_style": source.count("<style>") == 1,
    "network_connect_none": "connect-src 'none'" in source,
    "local_state_v3": "essential-attention/local-state@3" in source,
    "guided_setup_view": 'id="view-start"' in source and 'data-view="start"' in source and "Setup assistant" in source,
    "first_run_help": 'id="helpDialog"' in source and "onboarding_seen:false" in source,
    "guided_tour_8": "const TOUR_STEPS" in source and source.count("{view:") >= 8 and 'id="tourBar"' in source,
    "setup_assistant_6": all(label in source for label in setup_labels) and 'id="startSetupChecklist"' in source,
    "guidance_center": all(token in source for token in ['id="guidanceDrawer"', 'id="guidanceButton"', "VIEW_GUIDANCE", "Snooze guidance until tomorrow"]),
    "role_aware_home": all(label in source for label in role_home_labels) and 'id="homeRoleSelect"' in source,
    "attention_assistant": 'id="assistantQueue"' in source and "What needs attention now" in source,
    "quick_actions": all(token in source for token in ['id="homeNextObject"', 'id="homeNextDecision"', 'id="homeRunInternal"', 'id="homeExport"']),
    "readiness_drilldowns": 'id="readinessGrid"' in source and "Conditions, not vanity metrics" in source,
    "activity_timeline": 'id="activityTimeline"' in source and "What changed in this browser" in source,
    "recent_records": 'id="recentObjects"' in source and "Continue where you left off" in source,
    "held_effects": 'id="heldEffects"' in source and all(effect in source for effect in ["Email", "Calendar", "Payment", "Publication", "Acceptance", "Representation"]),
    "register_views": all(token in source for token in ['data-register-mode="list"', 'data-register-mode="board"', 'id="savedViews"', 'id="offerBoard"']),
    "record_path": 'class="record-path"' in source and "RECORD_STAGES" in source and len(re.findall(r"'[^']+'", re.search(r"const RECORD_STAGES = Object.freeze\(\[(.*?)\]\);", source, re.S).group(1))) == 7,
    "record_guidance": "Guidance for this stage" in source and 'class="guidance-for-success"' in source,
    "record_tabs": all(token in source for token in ['data-record-tab="details"', 'data-record-tab="activity"', 'data-record-tab="related"']),
    "decision_queue": 'id="decisionSummary"' in source and 'id="decisionDialog"' in source and "No executive theater" in source,
    "register_objects_7": source.count("offer_id:'FAB-") == 7,
    "executive_decisions_5": source.count("decision_id:'EA-DEC-") == 5,
    "contained_roles_7": all(f"id:'{role}'" in source for role in required_roles),
    "effect_firewall": "external effect blocked" in source,
    "successor_replay": "Cold replay passed" in source,
    "case_ledger_flavor": "FAB Operating Cockpit" in source and "pixel-dandelion" in source,
    "case_topology": "case-map-shell" in source and "function-spine" in source,
    "embedded_house_fonts": all(token in source for token in ["Barlow Condensed", "IBM Plex Mono", "IBM Plex Sans", "Lora"]) and "font-src data:" in source,
    "frozen_palette": all(token in source for token in ["#0D0C09", "#ECE7D8", "#7C7F57", "#C24B2C"]),
    "readme_present": README.exists() and len(readme) > 8000,
    "readme_first_use": "## First use" in readme and "Take the guided tour" in readme,
    "readme_cockpit": "## v1.1.0 operating cockpit" in readme and "setup assistant" in readme.lower() and "attention assistant" in readme.lower(),
    "readme_contents": "The default FAB cartridge contains seven case objects" in readme,
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("qualification failed: " + ", ".join(failed))

script = re.search(r"<script>(.*?)</script>", source, re.S)
if not script:
    raise SystemExit("inline runtime script missing")
Path("/tmp/essential-attention-inline.js").write_text(script.group(1), encoding="utf-8")

digest = hashlib.sha256(HTML.read_bytes()).hexdigest()
receipt = {
    "schema": "essential-attention/pages-qualification@3",
    "release": "1.1.0",
    "artifact": "essential-attention/index.html",
    "sha256": digest,
    "bytes": HTML.stat().st_size,
    "readme_bytes": README.stat().st_size,
    "checks": checks,
    "operator_surface": "AXM Operating Cockpit with guided setup, role home, record path, activity, and drill-down",
    "external_effect_adapters": 0,
}
QUALIFICATION.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
