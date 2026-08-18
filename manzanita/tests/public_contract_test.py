from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT / "QUALIFICATION.json").read_text(encoding="utf-8"))
release_receipt = json.loads((ROOT / "RELEASE_RECEIPT.json").read_text(encoding="utf-8"))

assert receipt["schema"] == "manzanita-works/pages-qualification@5"
assert receipt["release"] == "1.4.1"
assert receipt["visual_system"] == "signal-sheet"
assert receipt["themes"] == ["light", "dark"]
assert receipt["scales"] == 7
assert receipt["overlays"] == 8
assert receipt["functional_views"] == 5
assert receipt["instruments"] == 6
assert receipt["external_effect_adapters"] == 0
assert receipt["external_visual_dependencies"] == 0
assert receipt["shareable_url_state"] is True
assert receipt["keyboard_group_navigation"] == ["Arrow", "Home", "End"]
assert receipt["print_save_sheet"] is True
assert receipt["predecessor_release"]["release"] == "1.4.0"
assert release_receipt["schema"] == "manzanita-works/release-receipt@1"
assert release_receipt["release"] == "1.4.1"
assert release_receipt["predecessor"]["route_tree"] == "846132be374b1e1da5a9444dc67da877bbb32224"
assert release_receipt["authority"]["successor_program_effect"] == "none"
assert release_receipt["authority"]["canonical_task_count_effect"] == "none"

for name, expected in receipt["files"].items():
    data = (ROOT / name).read_bytes()
    assert len(data) == expected["bytes"], (name, len(data), expected["bytes"])
    digest = hashlib.sha256(data).hexdigest()
    assert digest == expected["sha256"], (name, digest, expected["sha256"])

html = (ROOT / "index.html").read_text(encoding="utf-8")
css = (ROOT / "style.css").read_text(encoding="utf-8")
js = (ROOT / "app.js").read_text(encoding="utf-8")
theme = (ROOT / "theme-init.js").read_text(encoding="utf-8")
constitution = (ROOT / "VISUAL_CONSTITUTION.md").read_text(encoding="utf-8")

for phrase in (
    'data-release="1.4.1"',
    'data-visual-system="signal-sheet"',
    "One place.<br>Every scale.",
    "Fresh catnip exposed the whole system.",
    "Change the scale. Keep the record.",
    "Six instruments. One durable record.",
    "Risk context should start help.",
    "Prevention data stays prevention data.",
    "Essential Attention keeps the work alive when people change.",
    "Automatic insurance denial",
    "No backend · no external-effect adapters",
    "Print / save signal sheet",
    "The address records the current scale",
):
    assert phrase in html, phrase

assert html.count('data-layer="') == 0
assert '<img' not in html.lower()
assert html.count('<svg') >= 3
assert 'connect-src \'none\'' in html
assert 'https://bigbirdreturns.github.io/axm-tools/essential-attention/' in html
assert 'themeToggle' in html
assert 'rel="icon"' in html
assert 'rel="canonical" href="https://bigbirdreturns.github.io/axm-tools/manzanita/"' in html
assert 'property="og:title"' in html
assert 'id="interactionStatus"' in html
assert 'id="printSheet"' in html
assert 'history.replaceState' in js
assert 'URLSearchParams' in js
assert 'window.print()' in js
assert "'ArrowRight'" in js and "'Home'" in js and "'End'" in js
assert '@media print' in css
assert '.sr-only' in css
assert 'style="' not in js
assert '.scene-stroke-15' in css and '.scene-stroke-13' in css
assert 'manzanita-theme' in theme
assert "prefers-color-scheme: dark" in theme

assert len(re.findall(r"id:'(?:plant|household|property|street|neighborhood|region|stewardship)'", js)) == 7
assert len(re.findall(r"id:'(?:habitat|shade|water|fire|air|access|labor|authority)'", js)) == 8
assert len(re.findall(r"id:'(?:resident|nursery|crew|planner|successor)'", js)) == 5
assert "fetch(" not in js
assert "XMLHttpRequest" not in js
assert "WebSocket" not in js
assert "EventSource" not in js
assert "navigator.sendBeacon" not in js

for forbidden in (
    "linear-gradient",
    "radial-gradient",
    "backdrop-filter",
    "box-shadow",
    "border-radius",
    "color-mix",
    "@import",
):
    assert forbidden not in css, forbidden

for required in (
    ':root[data-theme="dark"]',
    "--signal:#ff4b1f",
    "font-weight:900",
    ".instrument-ledger",
    ".sequence",
    ".firewall-ledger",
    ".theme-toggle",
):
    assert required in css, required

for rule in (
    "No section may introduce a decorative gradient",
    "Dark mode is the same grammar inverted",
    "A release fails when the public endpoint loses the exact release marker",
    "The current scale, perspective, and visible conditions may be encoded in the page address",
    "A printed or saved sheet may suppress interactive controls",
):
    assert rule in constitution, rule

root_index = (ROOT.parent / "index.html").read_text(encoding="utf-8")
root_readme = (ROOT.parent / "README.md").read_text(encoding="utf-8")
assert root_index.count('href="manzanita/"') >= 2
assert "[`manzanita/`](manzanita/)" in root_readme

print("Manzanita Works v1.4.1 Signal Sheet static contract: PASS")
