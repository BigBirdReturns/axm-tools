#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

REQUIRED = [
    "index.html",
    "app.js",
    "style-base.css",
    "style.css",
    "WORKING_MODEL_CONTRACT.json",
    "RELEASE_CONTRACT.json",
    "README.md",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    for name in REQUIRED:
        path = ROOT / name
        require(path.is_file(), f"required release file absent: {name}")
        require(path.stat().st_size > 0, f"required release file empty: {name}")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    base_css = (ROOT / "style-base.css").read_text(encoding="utf-8")
    override_css = (ROOT / "style.css").read_text(encoding="utf-8")
    css = base_css + "\n" + override_css
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    contract = json.loads((ROOT / "WORKING_MODEL_CONTRACT.json").read_text(encoding="utf-8"))
    release_contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))

    require('content="mw-working-model-v1.0.0"' in html, "release marker absent")
    require(contract["schema"] == "manzanita-works/working-model-contract@1", "contract schema differs")
    require(contract["state"] == "released_public_safe_working_model", "release state differs")
    require(contract["object"]["public_effect"] == "public_static_route_only", "public effect differs")
    require(release_contract["schema"] == "manzanita-works/working-model-release@1", "release contract schema differs")
    require(release_contract["release"] == "mw-working-model-v1.0.0", "release identity differs")
    require(release_contract["publication_authority"]["institutional_acceptance"] is False, "release may not accept institution")
    require(release_contract["publication_authority"]["program_external_effect"] == "none", "release may not create program effect")
    require(contract["object"]["institutional_acceptance"] is False, "institutional acceptance must remain false")
    require(contract["object"]["external_effect"] == "none", "contract external effect must remain none")
    require(contract["pilot_export"]["external_effect"] == "none", "pilot export external effect must remain none")
    require(contract["pilot_export"]["institutional_acceptance"] is False, "pilot export may not accept institution")
    require(contract["pilot_export"]["field_authority"] is False, "pilot export may not create field authority")
    require(contract["pilot_export"]["release_authority"] is False, "pilot export may not create release authority")

    grammar = contract["operating_grammar"]
    require(grammar == ["signal", "source", "authority", "safe_action", "fallback", "closure", "learning"], "operating grammar differs")
    require(len(contract["pilot_gates"]) == 5, "pilot gate count differs")
    require(len(contract["representative_cases"]) == 4, "representative case count differs")
    require(len(contract["source_surfaces"]) >= 6, "source-surface registry is incomplete")

    for phrase in [
        "Start with one accountable case",
        "One real problem.",
        "One bounded promise.",
        "Silence creates no consent, assignment, rejection, or completion.",
        "Run one case",
        "The system is already built.",
        "Five rules bound the work.",
        "Five decisions make one bounded pilot possible.",
        "Produce one pilot packet, not another scoping cycle.",
        "A return moves one case forward. It does not restart the explanation.",
        "No institutional acceptance implied.",
    ]:
        require(phrase in html, f"required public phrase absent: {phrase}")

    for scenario in ["wildfire", "tools", "mobility", "continuity"]:
        require(f'data-scenario="{scenario}"' in html, f"scenario tab absent: {scenario}")
        require(f"{scenario}: {{" in js, f"scenario data absent: {scenario}")

    require(html.count('class="scenario-tab') == 4, "scenario-tab count differs")
    require(html.count('class="decision-number') == 5, "decision count differs")
    require(html.count('class="proof-card') == 4, "proof-card count differs")
    require(html.count('class="proof-instrument') == 4, "proof-instrument count differs")

    for link in ["../manzanita/", "../essential-attention/", "../manzanita-works/"]:
        require(link in html, f"existing-surface link absent: {link}")

    for asset in ["assets/property.webp", "assets/household.webp"]:
        require(not (ROOT / asset).exists(), f"removed photo asset remains in current release: {asset}")
        require(asset not in html, f"removed photo asset remains in public HTML: {asset}")

    for hook in [
        'class="hero-visual hero-console"',
        'class="console-grammar"',
        'class="console-ledger"',
        'class="proof-instrument place-instrument"',
        'class="proof-instrument attention-instrument"',
        'class="proof-instrument fabric-instrument"',
        'class="proof-instrument glide-instrument"',
        'class="attention-stack"',
        'class="organ-grid"',
        'class="source-chain"',
        'class="role-strip"',
        'No adverse use',
    ]:
        require(hook in html, f"operational evidence hook absent: {hook}")
    require("<img" not in html, "working-model main surface may not render photography")
    for residue in ["N=0", "compression-band", "capacity-section", "proof-symbol", 'id="theme"', "data-theme="]:
        require(residue not in html, f"public visual or editorial residue remains: {residue}")
    require("THEME_KEY" not in js and "applyTheme" not in js, "theme subsystem remains in script")
    visual = contract["visual_evidence"]
    require(visual["primary_mode"] == "operational_instrumentation", "visual evidence mode differs")
    require(visual["historical_or_low_resolution_photography_used_as_primary_proof"] is False, "legacy photography must not carry primary proof")
    require(visual["current_release_photo_assets"] == [], "current release photo asset list must be empty")
    require(visual["field_activity_claimed"] is False, "visual system may not manufacture field activity")
    require(release_contract["release_files"] == REQUIRED, "release-file contract differs from static release list")
    require(release_contract["visual_evidence"]["current_release_photo_assets"] == [], "release contract retained current photo assets")
    require(release_contract["visual_evidence"]["rendered_image_elements"] == 0, "release contract rendered-image count differs")
    personalized = ["Mila", "Jonathan", "Stu", "Cavala", "Sandhu"]
    for token in personalized:
        require(token not in html, f"personalized public token prohibited: {token}")
        require(token not in js, f"personalized script token prohibited: {token}")
        require(token not in json.dumps(contract), f"personalized contract token prohibited: {token}")

    require(not re.search(r'https?://', html), "public HTML contains an absolute runtime URL")
    require("fetch(" not in js, "script contains fetch()")
    require("XMLHttpRequest" not in js, "script contains XMLHttpRequest")
    require("WebSocket" not in js, "script contains WebSocket")
    require("sendBeacon" not in js, "script contains sendBeacon")
    for prohibited in ["mailto:", "stripe.com", "givebutter", "calendar.google", "api_key", "access_token", "password"]:
        require(prohibited.lower() not in (html + js).lower(), f"prohibited runtime/effect token present: {prohibited}")

    require("external_effect: 'none'" in js, "pilot packet no-effect field absent")
    require("institutional_acceptance: false" in js, "pilot packet acceptance hold absent")
    require("participant_consent: false" in js, "pilot packet consent hold absent")
    require("field_authority: false" in js, "pilot packet field hold absent")
    require("release_authority: false" in js, "pilot packet release hold absent")
    require("UNRESOLVED" in js, "unresolved value law absent")
    require("function scenarioFromHash()" in js, "hash route parser absent")
    require("window.addEventListener('hashchange'" in js, "same-document hash route listener absent")

    require('@import url("style-base.css")' in override_css, "base style import absent")
    require("@media (max-width: 640px)" in css, "mobile CSS floor absent")
    require("@media (max-width: 360px)" in override_css, "narrow accessibility hardening absent")
    require("@media (max-width: 480px)" in override_css, "compact instrument breakpoint absent")
    require(".console-grammar" in override_css, "compact grammar treatment absent")
    require("@media (prefers-reduced-motion: reduce)" in css, "reduced-motion law absent")
    require(":focus-visible" in css, "focus-visible treatment absent")
    require("min-height: 48px" in css, "minimum primary form/control target hook absent")

    source_paths = [
        REPO / "manzanita" / "README.md",
        REPO / "essential-attention" / "README.md",
        REPO / "manzanita-works" / "README.md",
        REPO / "manzanita-next" / "street-glide" / "STREET_GLIDE_CONTRACT.json",
        REPO / "manzanita-next" / "roles" / "ROLE_CONTRACT.json",
        REPO / "manzanita-next" / "experience" / "EXPERIENCE_CONTRACT.json",
    ]
    for path in source_paths:
        require(path.is_file(), f"source contract absent: {path.relative_to(REPO)}")

    release_files = [ROOT / name for name in REQUIRED]
    digest = hashlib.sha256()
    for path in sorted(release_files, key=lambda p: p.as_posix()):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    print(json.dumps({
        "result": "PASS_WORKING_MODEL_STATIC_RELEASE_CONTRACT",
        "release": "mw-working-model-v1.0.0",
        "files": len(release_files),
        "scenarios": 4,
        "pilot_gates": 5,
        "external_effect": "none",
        "release_bundle_digest": digest.hexdigest(),
    }, indent=2))


if __name__ == "__main__":
    main()
