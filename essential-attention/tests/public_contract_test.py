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

checks = {
    "doctype": source.lstrip().lower().startswith("<!doctype html>"),
    "release_1_0_3": "Essential Attention v1.0.3" in source and "version:'1.0.3'" in source,
    "plain_no_atob": "atob(" not in source,
    "plain_no_decompression_loader": "DecompressionStream" not in source,
    "one_inline_script": source.count("<script>") == 1 and "<script src=" not in source,
    "one_inline_style": source.count("<style>") == 1,
    "network_connect_none": "connect-src 'none'" in source,
    "start_here_view": 'id="view-start"' in source and 'data-view="start"' in source,
    "first_run_help": 'id="helpDialog"' in source and "onboarding_seen:false" in source,
    "guided_tour": "const TOUR_STEPS" in source and 'id="tourBar"' in source,
    "plain_orientation": "working case file for what the first FAB meeting created" in source,
    "register_objects_7": source.count("offer_id:'FAB-") == 7,
    "executive_decisions_5": source.count("decision_id:'EA-DEC-") == 5,
    "contained_roles_7": all(f"id:'{role}'" in source for role in required_roles),
    "effect_firewall": "external effect blocked" in source,
    "successor_replay": "Cold replay passed" in source,
    "readme_present": README.exists() and len(readme) > 5000,
    "readme_first_use": "## First use" in readme and "Take the guided tour" in readme,
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
    "schema": "essential-attention/pages-qualification@2",
    "release": "1.0.3",
    "artifact": "essential-attention/index.html",
    "sha256": digest,
    "bytes": HTML.stat().st_size,
    "readme_bytes": README.stat().st_size,
    "checks": checks,
    "operator_surface": "plain standalone HTML with first-run orientation",
    "external_effect_adapters": 0,
}
QUALIFICATION.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
