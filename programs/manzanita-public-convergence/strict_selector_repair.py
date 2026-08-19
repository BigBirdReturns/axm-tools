#!/usr/bin/env python3
"""Prevent root state attributes from colliding with strict control locators."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "manzanita"

browser_path = ROOT / "tests" / "browser_test.py"
text = browser_path.read_text(encoding="utf-8")
text = text.replace("page.locator('[data-aperture=\"plant\"]')", "page.locator('button[data-aperture=\"plant\"]')")
text = text.replace("page.locator('[data-aperture=\"stewardship\"]')", "page.locator('button[data-aperture=\"stewardship\"]')")
text = text.replace("page.locator('[data-role=\"planner\"]')", "page.locator('button[data-role=\"planner\"]')")
browser_path.write_text(text, encoding="utf-8")

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
qualification["strict_interaction_selectors"] = "button_only"
qualification_path.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")
print("Strict interaction selector repair: APPLIED")
