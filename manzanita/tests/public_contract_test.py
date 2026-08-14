from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT / "QUALIFICATION.json").read_text(encoding="utf-8"))

assert receipt["schema"] == "manzanita-works/pages-qualification@4"
assert receipt["release"] == "1.4.0"
assert receipt["visual_system"] == "signal-sheet"
assert receipt["themes"] == ["light", "dark"]
assert receipt["scales"] == 7
assert receipt["overlays"] == 8
assert receipt["functional_views"] == 5
assert receipt["instruments"] == 6
assert receipt["external_effect_adapters"] == 0
assert receipt["external_visual_dependencies"] == 0

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
    'data-release="1.4.0"',
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
):
    assert phrase in html, phrase

assert html.count('data-layer="') == 0
assert '<img' not in html.lower()
assert html.count('<svg') >= 3
assert 'connect-src \'none\'' in html
assert 'https://bigbirdreturns.github.io/axm-tools/essential-attention/' in html
assert 'themeToggle' in html
assert 'rel="icon"' in html
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
):
    assert rule in constitution, rule

print("Manzanita Works v1.4.0 Signal Sheet static contract: PASS")
