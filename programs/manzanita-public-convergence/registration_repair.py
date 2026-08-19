#!/usr/bin/env python3
"""Prevent compact layout from separating the image and normalized registration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "manzanita"

css_path = ROOT / "style.css"
css = css_path.read_text(encoding="utf-8")
css = css.replace(".scene{aspect-ratio:4/3}", ".scene{aspect-ratio:8/5}")
css_path.write_text(css, encoding="utf-8")

browser_path = ROOT / "tests" / "browser_test.py"
browser = browser_path.read_text(encoding="utf-8")
needle = "assert page.locator('#sceneClass').text_content().strip()\n"
addition = """assert page.locator('#sceneClass').text_content().strip()\n        image_box=page.locator('#sceneImage').bounding_box(); svg_box=page.locator('#overlaySvg').bounding_box()\n        assert image_box and svg_box\n        assert abs(image_box['x']-svg_box['x']) < 0.5 and abs(image_box['y']-svg_box['y']) < 0.5\n        assert abs(image_box['width']-svg_box['width']) < 0.5 and abs(image_box['height']-svg_box['height']) < 0.5\n"""
if needle not in browser:
    raise SystemExit("Could not install image-registration continuity assertion")
browser_path.write_text(browser.replace(needle, addition, 1), encoding="utf-8")

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
qualification["image_registration_shared_box"] = True
qualification_path.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")
print("Compact image-registration continuity repair: APPLIED")
