from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT / "QUALIFICATION.json").read_text(encoding="utf-8"))

assert receipt["release"] == "1.1.2"
assert receipt["entrypoint"] == "manzanita/index.html"
assert receipt["scales"] == 7
assert receipt["overlays"] == 8
assert receipt["functional_views"] == 5
assert receipt["embedded_photos"] == 4
assert receipt["external_effect_adapters"] == 0

for name, expected in receipt["files"].items():
    path = ROOT / name
    data = path.read_bytes()
    assert len(data) == expected["bytes"], (name, len(data), expected["bytes"])
    digest = hashlib.sha256(data).hexdigest()
    assert digest == expected["sha256"], (name, digest, expected["sha256"])

html = (ROOT / "index.html").read_text(encoding="utf-8")
css = (ROOT / "style.css").read_text(encoding="utf-8")
js = (ROOT / "app.js").read_text(encoding="utf-8")

for phrase in (
    "One place.<br>Every scale.",
    "Household Habitat",
    "Street Glide",
    "Regional Observatory",
    "Civic Planner",
    "Manzanita Works",
    "Essential Attention",
    "Purpose firewall",
    "Automatic insurance denial",
    "Public-safe reference world",
):
    assert phrase in html, phrase

assert html.count('data-layer="') == 8
assert len(re.findall(r"\['(?:Plant|Household|Property|Street|Neighborhood|Region|Stewardship)'", js)) == 7
assert js.count("data:image/webp;base64,") == 4
assert "fetch(" not in js
assert "XMLHttpRequest" not in js
assert "WebSocket" not in js
assert "EventSource" not in js
assert "navigator.sendBeacon" not in js
assert "@media(max-width:850px)" in css
assert "connect-src 'none'" in html

print("Manzanita Works v1.1.2 static contract: PASS")
