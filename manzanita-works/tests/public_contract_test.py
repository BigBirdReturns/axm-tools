#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    qualification = json.loads((ROOT / "QUALIFICATION.json").read_text(encoding="utf-8"))

    required = [
        'mw-operating-dreamboard-v0.2.0',
        'Fundraising is a view, not the system.',
        'What the organization already has',
        'What the institutional architect is doing',
        'The Operating Fabric',
        'Essential Tools',
        'Essential Time',
        'Essential Pilotage',
        'Mobility / E-bike',
        'Prevention & Support',
        'Stewardship / Place',
        'Money / Fundraising',
        'Fundraising dashboard',
        'Rules that keep the organization sovereign',
        'Receipts: this is an implemented method, not a mood board',
        'connect-src \'none\'',
        '?focus=fundraising',
    ]
    for marker in required:
        if marker not in html and marker not in readme:
            raise SystemExit(f"missing required marker: {marker}")

    forbidden = [
        'What Mila already has',
        'What Jonathan is actually doing',
        "Stu's dashboard",
        'victim-service records',
        'mailto:',
        'fetch(',
        'XMLHttpRequest',
        'WebSocket',
    ]
    for marker in forbidden:
        if marker in html:
            raise SystemExit(f"forbidden public marker: {marker}")

    # External URLs are permitted only as explicit user-initiated links to retained public receipts.
    urls = re.findall(r'https://[^\"\'\s<]+', html)
    allowed = {
        'https://bigbirdreturns.github.io/axm-tools/manzanita/',
        'https://bigbirdreturns.github.io/axm-tools/essential-attention/',
    }
    if set(urls) != allowed:
        raise SystemExit(f"unexpected public URLs: {sorted(set(urls) - allowed)}")

    expected_files = qualification["files"]
    for name, expected in expected_files.items():
        observed = digest(ROOT / name)
        if observed != expected:
            raise SystemExit(f"file identity mismatch for {name}: {observed} != {expected}")

    if qualification["state"] != "PASS":
        raise SystemExit("qualification state is not PASS")

    print("Manzanita Works Operating Fabric Dreamboard static contract: PASS")


if __name__ == "__main__":
    main()
