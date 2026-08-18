#!/usr/bin/env python3
"""Keep state attributes off the control-count and interaction contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "manzanita"

app_path = ROOT / "app.js"
app = app_path.read_text(encoding="utf-8")
app = app.replace("document.querySelectorAll('[data-aperture]')", "document.querySelectorAll('button[data-aperture]')")
app = app.replace("document.querySelectorAll('[data-role]')", "document.querySelectorAll('button[data-role]')")
app_path.write_text(app, encoding="utf-8")

browser_path = ROOT / "tests" / "browser_test.py"
browser = browser_path.read_text(encoding="utf-8")
browser = browser.replace("page.locator('[data-aperture]').count()", "page.locator('button[data-aperture]').count()")
browser = browser.replace("page.locator('[data-role]').count()", "page.locator('button[data-role]').count()")
browser = browser.replace("page.locator('[data-aperture]').all()", "page.locator('button[data-aperture]').all()")
browser_path.write_text(browser, encoding="utf-8")

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
qualification["control_selector_scope"] = "button_only"
qualification_path.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")
print("Aperture and seat acceptance selector repair: APPLIED")
