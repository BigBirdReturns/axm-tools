#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "mw-working-model-v1.1.0"
RELEASE_FILES = [
    "index.html",
    "app.js",
    "style.css",
    "WORKING_MODEL_CONTRACT.json",
    "RELEASE_CONTRACT.json",
    "README.md",
]


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: set[str] = set()
        self.scenarios: list[str] = []
        self.classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if values.get("data-scenario"):
            self.scenarios.append(str(values["data-scenario"]))
        if values.get("class"):
            self.classes.extend(str(values["class"]).split())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block(html: str, class_name: str, tag: str) -> str:
    match = re.search(
        rf'<{tag} class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</{tag}>',
        html,
        re.S,
    )
    require(match is not None, f"block absent: {class_name}")
    return match.group(1)


def main() -> None:
    for relative in RELEASE_FILES:
        require((ROOT / relative).is_file(), f"release file absent: {relative}")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    contract = json.loads((ROOT / "WORKING_MODEL_CONTRACT.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))

    parser = DocumentParser()
    parser.feed(html)

    require(f'content="{RELEASE}"' in html, "HTML release identity differs")
    require(f"const RELEASE = '{RELEASE}';" in app, "application release identity differs")
    require(release["release"] == RELEASE, "release contract identity differs")
    require(contract["version"] == "1.1.0", "working contract version differs")
    require(release["release_files"] == RELEASE_FILES, "release file list differs")
    require(release["visual_posture"]["rendered_photography"] is False, "photography posture differs")
    require(release["visual_posture"]["dead_visual_assets_in_release"] is False, "dead asset posture differs")
    require(release["visual_posture"]["receiver_first_language"] is True, "release language posture differs")
    require(contract["visual_contract"]["rendered_photography"] is False, "working visual contract differs")
    require(contract["public_language"]["receiver_first"] is True, "receiver-first language contract absent")
    require(contract["public_language"]["technical_identifiers_confined_to_contracts_and_exports"] is True, "technical identifier boundary differs")
    expected_stage_labels = {
        "signal": "Need",
        "source": "Evidence",
        "authority": "Decision owner",
        "safe_action": "Safe next step",
        "fallback": "Backup path",
        "closure": "Outcome",
        "learning": "Next improvement",
    }
    require(contract["public_language"]["public_stage_labels"] == expected_stage_labels, "public stage-label contract differs")
    require(release["visual_posture"]["public_stage_labels"] == 7, "release stage-label count differs")
    for stage_id, public_label in expected_stage_labels.items():
        require(f"{stage_id}: '{public_label}'" in app, f"application stage label differs: {stage_id}")
    require("heading.textContent = stageLabels[stageId];" in app, "stage renderer bypasses receiver labels")

    for obsolete in [
        "Not another architecture review",
        "public-safe",
        "If leadership returns tomorrow",
        "Do not schedule a scoping call",
        "N=0",
        "assets/property.webp",
        "assets/household.webp",
        "style-base.css",
    ]:
        require(obsolete not in html, f"obsolete visible rhetoric or asset reference remains: {obsolete}")

    public_text = html.lower()
    for jargon in [
        "operating grammar",
        "public projection",
        "administrative runtime",
        "institutional architecture",
        "bounded kernel",
        "cold-replayable",
        "role projections",
        "execution basis",
        "effect boundary",
        "continuity operator",
        "front door routes",
        "accountable sponsor",
        "sponsor review",
        "no adverse use",
        "authority stays separate",
        "separate authorization",
        "adverse standing",
        "qualified field evidence",
        "role-specific views",
        "source fallback",
    ]:
        require(jargon not in public_text, f"untranslated public jargon remains: {jargon}")

    for jargon in [
        "qualified field evidence",
        "lived facts",
        "the sponsor controls",
        "first-party constraints",
        "participant fitness",
        "decision rights",
        "unstated authority",
        "institutional authority",
        "budget, scope",
        "separate authority is still required",
    ]:
        require(jargon not in app.lower(), f"untranslated dynamic language remains: {jargon}")

    require('<link rel="icon" href="data:,">' in html, "inline empty favicon absent")
    require('placeholder="Name or role"' in html, "compact accountable-owner placeholder absent")
    require('placeholder="Funded owner"' in html, "compact day-to-day-owner placeholder absent")
    require("img" not in parser.tags, "rendered image element remains")
    require("--fill" not in html and "--fill" not in css, "synthetic capacity metric remains")
    require(set(parser.scenarios) == {"wildfire", "tools", "mobility", "continuity"}, "scenario set differs")
    require(len(parser.scenarios) == 4, "scenario tab count differs")
    require(parser.classes.count("system-card") == 4, "system card count differs")
    require(parser.classes.count("scenario-tab") == 4, "scenario tab class count differs")
    require(parser.classes.count("guardrail-grid") == 1, "guardrail section differs")
    require(parser.classes.count("pilot-form") == 1, "pilot form differs")

    runtime = block(html, "runtime-trace", "ol")
    require(runtime.count("<li") == 4, "hero case state must contain exactly four non-duplicative rows")
    require("Signal" not in runtime and "Learning" not in runtime, "seven-stage grammar duplicated in hero")

    capacity_rows = [
        '<div><span>Physical</span><strong>Tools + materials</strong></div>',
        '<div><span>Human</span><strong>Time + skill</strong></div>',
        '<div><span>Mobility</span><strong>Transport + access</strong></div>',
        '<div><span>Money</span><strong>Dues + grants</strong></div>',
        '<div><span>Place</span><strong>Place evidence</strong></div>',
        '<div><span>Continuity</span><strong>Decisions + handoff</strong></div>',
    ]
    require(html.count('class="instrument capacity-instrument"') == 1, "capacity-class instrument count differs")
    for row in capacity_rows:
        require(html.count(row) == 1, f"capacity-class row differs: {row}")

    required_ids = {
        "main", "try", "systems", "pilot", "scenario-panel", "scenario-title",
        "scenario-summary", "scenario-output", "scenario-prohibited", "stage-list",
        "pilot-form", "pilot-scenario", "pilot-problem", "pilot-sponsor", "pilot-operator",
        "pilot-basis", "pilot-stop", "form-status", "packet-standing",
        "packet-next", "export-pilot", "clear-pilot",
    }
    require(required_ids <= parser.ids, f"required IDs absent: {sorted(required_ids - parser.ids)}")

    for phrase in [
        "One real problem.",
        "One accountable owner.",
        "One bounded promise.",
        "Four problems. The same path to accountable action.",
        "Four parts already handle four different jobs.",
        "Three rules keep help accountable.",
        "Five facts turn the model into an accountable proposal.",
        "The file stays on this device.",
        "Who owns the promise?",
        "Who keeps the work running?",
        "Where and with what?",
    ]:
        require(phrase in html, f"required receiver-language copy absent: {phrase}")

    require("font-size: 8px" not in css and "font: 8px" not in css, "sub-9px CSS text remains")
    require("font-size: 9px" not in css and "font-size: 10px" not in css, "sub-11px CSS text remains")
    require("font-size: clamp(62px, 5.2vw, 84px)" in css, "desktop hero scale contract differs")
    require("@media (max-width: 360px)" in css, "narrow-screen contract absent")
    require("prefers-reduced-motion" in css, "reduced-motion contract absent")
    require("position: static" in css, "mobile non-sticky header contract absent")
    require(".gate-map ol { display: none; }" in css, "mobile duplicate-gate suppression absent")
    require("bounded-pilot-preparation@2" in app, "pilot export schema differs")
    require("institutional_acceptance: false" in app, "authority hold absent")
    require("external_effect: 'none'" in app, "external-effect hold absent")

    bundle = "\n".join(f"{digest(ROOT / path)}  {path}" for path in RELEASE_FILES)
    result = {
        "result": "PASS_WORKING_MODEL_STATIC_RELEASE_CONTRACT",
        "release": RELEASE,
        "files": len(RELEASE_FILES),
        "scenarios": 4,
        "stages_per_scenario": 7,
        "hero_state_rows": 4,
        "pilot_gates": 5,
        "rendered_images": 0,
        "synthetic_capacity_metrics": 0,
        "obsolete_visible_rhetoric": 0,
        "untranslated_public_jargon": 0,
        "receiver_first_language": True,
        "public_stage_labels": 7,
        "visible_internal_nomenclature": 0,
        "compact_input_placeholders": True,
        "external_effect": "none",
        "release_bundle_digest": hashlib.sha256(bundle.encode("utf-8")).hexdigest(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
