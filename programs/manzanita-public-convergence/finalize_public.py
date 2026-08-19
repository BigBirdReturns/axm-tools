#!/usr/bin/env python3
"""Finalize the generated public site without a runtime network fetch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "manzanita"

scene_json = ROOT / "assets" / "scene-data.json"
scene_value = json.loads(scene_json.read_text(encoding="utf-8"))
(ROOT / "assets" / "scene-data.js").write_text(
    "window.MANZANITA_SCENES=" + json.dumps(scene_value, separators=(",", ":")) + ";\n",
    encoding="utf-8",
)

index = ROOT / "index.html"
text = index.read_text(encoding="utf-8")
needle = '  <script src="app.js" defer></script>'
replacement = '  <script src="assets/scene-data.js" defer></script>\n  <script src="app.js" defer></script>'
if needle not in text:
    raise SystemExit("Could not install scene-data.js before the application runtime")
index.write_text(text.replace(needle, replacement, 1), encoding="utf-8")

app = ROOT / "app.js"
text = app.read_text(encoding="utf-8")
old = "state.sceneData=await fetch('assets/scene-data.json').then(r=>{if(!r.ok)throw new Error(`scene-data ${r.status}`);return r.json()});"
new = "state.sceneData=window.MANZANITA_SCENES||{};if(Object.keys(state.sceneData).length!==7)throw new Error('scene-data unavailable');"
if old not in text:
    raise SystemExit("Could not replace the runtime scene-data fetch")
app.write_text(text.replace(old, new, 1), encoding="utf-8")

static_test = ROOT / "tests" / "public_contract_test.py"
text = static_test.read_text(encoding="utf-8")
text = text.replace("assert \"fetch('assets/scene-data.json')\" in js", "assert 'window.MANZANITA_SCENES' in js\nassert 'fetch(' not in js")
static_test.write_text(text, encoding="utf-8")

qualification_path = ROOT / "QUALIFICATION.json"
qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
files = {}
for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "QUALIFICATION.json"):
    payload = path.read_bytes()
    files[path.relative_to(ROOT).as_posix()] = {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
qualification["files"] = files
qualification["runtime_network_requests"] = 0
qualification_path.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")

print(json.dumps({"scene_data_embedded": True, "qualified_files": len(files)}, indent=2))
