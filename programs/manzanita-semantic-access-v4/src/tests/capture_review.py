#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

STATES = [
    ("01-street-access-reference", "street", "access", "reference", 0, "crew_steward", "evidence", 1600, 1000),
    ("02-street-access-live-a", "street", "access", "live", 0, "crew_steward", "evidence", 1600, 1000),
    ("03-street-access-live-b", "street", "access", "live", 1, "crew_steward", "evidence", 1600, 1000),
    ("04-street-access-cached", "street", "access", "cached", 0, "successor", "handoff", 1600, 1000),
    ("05-street-access-map", "street", "access", "map", 0, "planner_program", "evidence", 1600, 1000),
    ("06-street-access-held", "street", "access", "held", 0, "successor", "operate", 1600, 1000),
    ("07-property-shade-no-geometry", "property", "shade", "reference", 0, "crew_steward", "evidence", 1600, 1000),
    ("08-neighborhood-water-no-geometry", "neighborhood", "water", "reference", 0, "planner_program", "evidence", 1600, 1000),
    ("09-mobile-street-access-live", "street", "access", "live", 1, "resident", "operate", 390, 844),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    url = (args.site / "index.html").resolve().as_uri()
    captures = []

    with sync_playwright() as pw:
        system_chromium = Path("/usr/bin/chromium")
        browser = pw.chromium.launch(executable_path=str(system_chromium) if system_chromium.exists() else None)
        for name, aperture, instrument, mode, provider_scene, seat, detail, width, height in STATES:
            context = browser.new_context(viewport={"width": width, "height": height}, color_scheme="dark")
            page = context.new_page()
            errors: list[str] = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(
                url
                + f"?aperture={aperture}&instrument={instrument}&mode={mode}"
                + f"&providerScene={provider_scene}&seat={seat}&detail={detail}",
                wait_until="networkidle",
            )
            path = args.output / f"{name}.png"
            page.screenshot(path=str(path), full_page=False)
            state = page.evaluate("window.__MANZANITA_V4__.getState()")
            overflow = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
            captures.append({
                "name": name,
                "file": path.name,
                "viewport": [width, height],
                "state": state,
                "horizontal_overflow": overflow,
                "errors": errors,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
            context.close()
        browser.close()

    # Full review sheet.
    thumb_w, thumb_h, label_h, cols = 800, 500, 68, 2
    rows = (len(captures) + cols - 1) // cols
    sheet = Image.new("RGB", (thumb_w * cols, (thumb_h + label_h) * rows), "#0d120d")
    draw = ImageDraw.Draw(sheet)
    for index, capture in enumerate(captures):
        with Image.open(args.output / capture["file"]) as source:
            image = ImageOps.fit(source.convert("RGB"), (thumb_w, thumb_h), method=Image.Resampling.LANCZOS)
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + label_h)
        sheet.paste(image, (x, y))
        draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label_h), fill="#efe9da")
        state = capture["state"]
        label = f"{state['aperture'].upper()} · {state['instrument'].upper()} · {state['mode'].upper()} · FEATURES {state['feature_count']}"
        draw.text((x + 16, y + thumb_h + 22), label, fill="#151713")
    contact = args.output / "contact-sheet.jpg"
    sheet.save(contact, quality=94)

    # Three exact scenes, three exact semantic receipts.
    proof_w, proof_h, proof_label = 900, 562, 58
    proof = Image.new("RGB", (proof_w * 3, proof_h + proof_label), "#efe9da")
    proof_draw = ImageDraw.Draw(proof)
    for index, capture in enumerate(captures[:3]):
        with Image.open(args.output / capture["file"]) as source:
            image = ImageOps.fit(source.convert("RGB"), (proof_w, proof_h), method=Image.Resampling.LANCZOS)
        proof.paste(image, (index * proof_w, 0))
        state = capture["state"]
        proof_draw.text(
            (index * proof_w + 14, proof_h + 19),
            f"{state['mode'].upper()} · ASSET {state['asset_id'][:12]} · RECEIPT {state['registration_id'][:12]} · {state['feature_count']} FEATURES",
            fill="#151713",
        )
    proof_path = args.output / "semantic-feature-proof.jpg"
    proof.save(proof_path, quality=95)

    receipt = {
        "schema": "manzanita-works/semantic-access-review-captures@1",
        "result": "PASS" if all(not row["errors"] and row["horizontal_overflow"] <= 1 for row in captures) else "FAIL",
        "captures": captures,
        "contact_sheet": {"path": contact.name, "bytes": contact.stat().st_size, "sha256": sha256(contact)},
        "semantic_feature_proof": {"path": proof_path.name, "bytes": proof_path.stat().st_size, "sha256": sha256(proof_path)},
        "public_route_effect": "none",
    }
    (args.output / "CAPTURE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if receipt["result"] != "PASS":
        raise SystemExit(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
