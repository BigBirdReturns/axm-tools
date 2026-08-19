#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageDraw, ImageOps
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATES = [
    ("01-household-shade", "household", "shade", "reference", 0, "resident", "evidence", 1600, 1000),
    ("02-property-shade", "property", "shade", "reference", 0, "crew_steward", "evidence", 1600, 1000),
    ("03-street-shade-reference", "street", "shade", "reference", 0, "crew_steward", "evidence", 1600, 1000),
    ("04-street-shade-live-a", "street", "shade", "live", 0, "crew_steward", "evidence", 1600, 1000),
    ("05-street-shade-live-b", "street", "shade", "live", 1, "crew_steward", "evidence", 1600, 1000),
    ("06-household-water", "household", "water", "reference", 0, "resident", "evidence", 1600, 1000),
    ("07-property-water", "property", "water", "reference", 0, "crew_steward", "evidence", 1600, 1000),
    ("08-street-access-live-b", "street", "access", "live", 1, "crew_steward", "evidence", 1600, 1000),
    ("09-neighborhood-water-held-geometry", "neighborhood", "water", "reference", 0, "planner_program", "evidence", 1600, 1000),
    ("10-region-fire", "region", "fire", "reference", 0, "planner_program", "operate", 1600, 1000),
    ("11-street-map-access", "street", "access", "map", 0, "successor", "evidence", 1600, 1000),
    ("12-household-held-water", "household", "water", "held", 0, "successor", "operate", 1600, 1000),
    ("13-mobile-household-water", "household", "water", "reference", 0, "resident", "operate", 390, 844),
]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@contextlib.contextmanager
def serve(directory: Path) -> Iterator[str]:
    class BoundHandler(QuietHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown(); thread.join(timeout=5)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_sheet(captures: list[dict], output: Path, indexes: list[int], cols: int, name: str) -> dict:
    thumb_w, thumb_h, label_h = 800, 500, 68
    rows = (len(indexes) + cols - 1) // cols
    sheet = Image.new("RGB", (thumb_w * cols, (thumb_h + label_h) * rows), "#0d120d")
    draw = ImageDraw.Draw(sheet)
    for position, index in enumerate(indexes):
        capture = captures[index]
        with Image.open(output / capture["file"]) as source:
            image = ImageOps.fit(source.convert("RGB"), (thumb_w, thumb_h), method=Image.Resampling.LANCZOS)
        x = (position % cols) * thumb_w; y = (position // cols) * (thumb_h + label_h)
        sheet.paste(image, (x, y)); draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label_h), fill="#efe9da")
        state = capture["state"]
        label = f"{state['aperture'].upper()} · {state['instrument'].upper()} · {state['mode'].upper()} · FEATURES {state['feature_count']}"
        draw.text((x + 16, y + thumb_h + 22), label, fill="#151713")
    path = output / name; sheet.save(path, quality=94)
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence")
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    captures = []

    base = (args.site / "index.html").resolve().as_uri()
    with sync_playwright() as pw:
        chromium = Path("/usr/bin/chromium")
        browser = pw.chromium.launch(executable_path=str(chromium) if chromium.exists() else None)
        for name, aperture, instrument, mode, provider_scene, seat, detail, width, height in STATES:
            context = browser.new_context(viewport={"width": width, "height": height}, color_scheme="dark")
            page = context.new_page(); errors: list[str] = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + f"?aperture={aperture}&instrument={instrument}&mode={mode}&providerScene={provider_scene}&seat={seat}&detail={detail}", wait_until="networkidle")
            path = args.output / f"{name}.png"; page.screenshot(path=str(path), full_page=False)
            state = page.evaluate("window.__MANZANITA_V5__.getState()")
            overflow = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
            captures.append({"name": name, "file": path.name, "viewport": [width, height], "state": state, "horizontal_overflow": overflow, "errors": errors, "bytes": path.stat().st_size, "sha256": sha256(path)})
            context.close()
        browser.close()

    contact = make_sheet(captures, args.output, list(range(len(captures))), 2, "contact-sheet.jpg")
    shade = make_sheet(captures, args.output, [0, 1, 2, 3, 4], 2, "semantic-shade-proof.jpg")
    water = make_sheet(captures, args.output, [5, 6, 8], 2, "semantic-water-proof.jpg")
    access = make_sheet(captures, args.output, [7, 10], 2, "semantic-access-proof.jpg")
    mechanisms = make_sheet(captures, args.output, [9, 11, 12], 2, "degraded-and-nonspatial-proof.jpg")

    receipt = {
        "schema": "manzanita-works/semantic-instruments-review-captures@2",
        "result": "PASS" if all(not row["errors"] and row["horizontal_overflow"] <= 1 for row in captures) else "FAIL",
        "captures": captures,
        "contact_sheet": contact,
        "semantic_shade_proof": shade,
        "semantic_water_proof": water,
        "semantic_access_proof": access,
        "degraded_and_nonspatial_proof": mechanisms,
        "public_route_effect": "none",
    }
    (args.output / "CAPTURE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if receipt["result"] != "PASS": raise SystemExit(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
