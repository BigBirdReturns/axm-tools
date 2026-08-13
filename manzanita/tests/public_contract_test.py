from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
CSS = ROOT / "style.css"
JS = ROOT / "app.js"
README = ROOT / "README.md"
QUALIFICATION = ROOT / "QUALIFICATION.json"

html = HTML.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")
js = JS.read_text(encoding="utf-8")
readme = README.read_text(encoding="utf-8")

checks = {
    "doctype": html.lstrip().lower().startswith("<!doctype html>"),
    "static_runtime": '<link rel="stylesheet" href="style.css">' in html and '<script src="app.js" defer></script>' in html,
    "network_connect_none": "connect-src 'none'" in html,
    "seven_scales": all(f"id:'{token}'" in js for token in ["plant", "household", "property", "street", "neighborhood", "region", "stewardship"]),
    "eight_overlays": all(f"id:'{token}'" in js for token in ["habitat", "shade", "water", "fire", "air", "access", "labor", "authority"]),
    "five_role_views": all(f"id:'{token}'" in js for token in ["resident", "nursery", "crew", "planner", "successor"]),
    "household_habitat": html.count("Household Habitat") >= 4,
    "street_glide": html.count("Street Glide") >= 4,
    "regional_observatory": html.count("Regional Observatory") >= 4,
    "manzanita_works": html.count("Manzanita Works") >= 5,
    "essential_attention": html.count("Essential Attention") >= 5,
    "purpose_firewall": "Automatic insurance denial" in html and "Punitive enforcement without review" in html,
    "essential_attention_link": html.count('href="../essential-attention/"') >= 3,
    "public_private_boundary": "Private household, meeting, and source records are not published here." in html,
    "estate_palette": all(token in css for token in ["#0D0C09", "#ECE7D8", "#7C7F57", "#C24B2C"]),
    "readme_present": README.exists() and len(readme) > 2000,
    "external_effect_adapters": "fetch(" not in js and "XMLHttpRequest" not in js and "WebSocket" not in js,
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("qualification failed: " + ", ".join(failed))

bundle_hash = hashlib.sha256(HTML.read_bytes() + CSS.read_bytes() + JS.read_bytes()).hexdigest()
receipt = {
    "schema": "manzanita-works/pages-qualification@1",
    "release": "1.0.0",
    "entrypoint": "manzanita/index.html",
    "bundle_sha256": bundle_hash,
    "bytes": {
        "index_html": HTML.stat().st_size,
        "style_css": CSS.stat().st_size,
        "app_js": JS.stat().st_size,
        "readme": README.stat().st_size,
    },
    "checks": checks,
    "external_effect_adapters": 0,
    "public_private_boundary": "public-safe illustrated reference place; private source bytes absent",
}
QUALIFICATION.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
