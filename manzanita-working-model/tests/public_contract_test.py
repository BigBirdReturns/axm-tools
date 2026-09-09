#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
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
    require(contract["visual_contract"]["rendered_photography"] is False, "working visual contract differs")

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

    require("img" not in parser.tags, "rendered image element remains")
    require(set(parser.scenarios) == {"wildfire", "tools", "mobility", "continuity"}, "scenario set differs")
    require(len(parser.scenarios) == 4, "scenario tab count differs")
    require(parser.classes.count("system-card") == 4, "system card count differs")
    require(parser.classes.count("scenario-tab") == 4, "scenario tab class count differs")
    require(parser.classes.count("guardrail-grid") == 1, "guardrail section differs")
    require(parser.classes.count("pilot-form") == 1, "pilot form differs")

    required_ids = {
        "main", "try", "systems", "pilot", "scenario-panel", "scenario-title",
        "scenario-summary", "scenario-output", "scenario-prohibited", "stage-list",
        "pilot-form", "pilot-scenario", "pilot-sponsor", "pilot-operator",
        "pilot-basis", "pilot-stop", "form-status", "packet-standing",
        "packet-next", "export-pilot", "clear-pilot",
    }
    require(required_ids <= parser.ids, f"required IDs absent: {sorted(required_ids - parser.ids)}")

    for phrase in [
        "One real problem.",
        "One accountable owner.",
        "One bounded promise.",
        "Four problems. One operating grammar.",
        "Three rules keep the model useful.",
        "Five facts convert a useful model into an accountable proposal.",
        "The export stays on this device.",
    ]:
        require(phrase in html, f"required first-order copy absent: {phrase}")

    require("font-size: 8px" not in css and "font: 8px" not in css, "sub-9px CSS text remains")
    require("@media (max-width: 360px)" in css, "narrow-screen contract absent")
    require("prefers-reduced-motion" in css, "reduced-motion contract absent")
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
        "pilot_gates": 5,
        "rendered_images": 0,
        "obsolete_visible_rhetoric": 0,
        "external_effect": "none",
        "release_bundle_digest": hashlib.sha256(bundle.encode("utf-8")).hexdigest(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
