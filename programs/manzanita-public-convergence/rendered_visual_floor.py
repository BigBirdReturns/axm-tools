#!/usr/bin/env python3
"""Exercise rendered composition, photographic substance, and responsive continuity."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
LOCAL = "http://127.0.0.1:8876/manzanita/"
APERTURES = ["plant", "household", "property", "street", "neighborhood", "region", "stewardship"]


def wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.3)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"server did not open port {port}")


def entropy(image: Image.Image) -> float:
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    return -sum((count / total) * math.log2(count / total) for count in histogram if count)


def edge_density(image: Image.Image) -> float:
    edge = image.convert("L").resize((320, 200)).filter(ImageFilter.FIND_EDGES)
    histogram = edge.histogram()
    return sum(histogram[42:]) / sum(histogram)


def rms(left: Image.Image, right: Image.Image) -> float:
    a = left.resize((160, 100)).convert("RGB")
    b = right.resize((160, 100)).convert("RGB")
    total = 0
    count = 0
    for pa, pb in zip(a.getdata(), b.getdata()):
        for av, bv in zip(pa, pb):
            total += (av - bv) ** 2
            count += 1
    return math.sqrt(total / count)


def image_metrics(path: Path) -> dict[str, float | int | str]:
    image = Image.open(path).convert("RGB")
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "width": image.width,
        "height": image.height,
        "entropy_bits": round(entropy(image), 4),
        "edge_density": round(edge_density(image), 4),
    }


def main(target: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    server = None
    if target == LOCAL:
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", "8876", "--bind", "127.0.0.1"],
            cwd=REPO,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_port(8876)

    report: dict[str, object] = {
        "schema": "manzanita-works/rendered-visual-floor@1",
        "release": "1.6.0",
        "target": target,
        "composition": {},
        "apertures": {},
        "pairwise_scene_rms": {},
        "responsive": {},
        "result": "PENDING",
    }
    scenes: dict[str, Image.Image] = {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            desktop = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page = desktop.new_page()
            response = page.goto(target, wait_until="networkidle", timeout=60_000)
            assert response is not None and response.status == 200
            assert page.locator("html").get_attribute("data-release") == "1.6.0"
            hero = page.locator(".hero").bounding_box()
            photo = page.locator(".hero-photo").bounding_box()
            copy = page.locator(".hero-copy").bounding_box()
            image = page.locator(".hero-photo > img").bounding_box()
            assert hero and photo and copy and image
            photo_share = photo["width"] / hero["width"]
            copy_share = copy["width"] / hero["width"]
            assert 0.60 <= photo_share <= 0.75, photo_share
            assert 0.25 <= copy_share <= 0.40, copy_share
            assert abs(image["width"] - photo["width"]) < 1
            assert abs(image["height"] - photo["height"]) < 1
            headline = page.locator(".hero h1").bounding_box()
            assert headline and headline["width"] <= copy["width"] + 1
            report["composition"] = {
                "hero_photo_share": round(photo_share, 4),
                "hero_copy_share": round(copy_share, 4),
                "headline_width": round(headline["width"], 2),
                "hero_height": round(hero["height"], 2),
            }
            page.locator(".hero").screenshot(path=str(output / "desktop-hero.png"))

            for aperture in APERTURES:
                page.locator(f'button[data-aperture="{aperture}"]').click()
                page.wait_for_timeout(80)
                image_box = page.locator("#sceneImage").bounding_box()
                svg_box = page.locator("#overlaySvg").bounding_box()
                assert image_box and svg_box
                for key in ("x", "y", "width", "height"):
                    assert abs(image_box[key] - svg_box[key]) < 0.6, (aperture, key, image_box[key], svg_box[key])
                assert page.locator("#overlaySvg .overlay-path").count() >= 1
                path = output / f"scene-{aperture}.png"
                page.locator("#scene").screenshot(path=str(path))
                metrics = image_metrics(path)
                assert metrics["entropy_bits"] >= 5.0, (aperture, metrics)
                assert metrics["edge_density"] >= 0.04, (aperture, metrics)
                report["apertures"][aperture] = metrics
                scenes[aperture] = Image.open(path).convert("RGB")

            for index, left in enumerate(APERTURES):
                for right in APERTURES[index + 1 :]:
                    value = round(rms(scenes[left], scenes[right]), 3)
                    report["pairwise_scene_rms"][f"{left}:{right}"] = value
                    assert value >= 4.5, (left, right, value)
            desktop.close()

            for label, width, height, font_scale in (
                ("tablet", 1024, 900, 100),
                ("mobile", 390, 844, 100),
                ("compact-200", 320, 720, 200),
            ):
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
                page = context.new_page()
                response = page.goto(target, wait_until="networkidle", timeout=60_000)
                assert response is not None and response.status == 200
                if font_scale != 100:
                    page.evaluate("scale => document.documentElement.style.fontSize = scale + '%'", font_scale)
                overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                assert overflow <= 1, (label, overflow)
                controls = page.locator("button[data-aperture]")
                assert controls.count() == 7
                minimum_height = min(button.bounding_box()["height"] for button in controls.all() if button.bounding_box())
                assert minimum_height >= 44, (label, minimum_height)
                image_box = page.locator("#sceneImage").bounding_box()
                svg_box = page.locator("#overlaySvg").bounding_box()
                assert image_box and svg_box
                assert abs(image_box["width"] - svg_box["width"]) < 0.6
                assert abs(image_box["height"] - svg_box["height"]) < 0.6
                path = output / f"{label}-full.png"
                page.screenshot(path=str(path), full_page=True)
                report["responsive"][label] = {
                    "viewport": [width, height],
                    "font_scale_percent": font_scale,
                    "horizontal_overflow": overflow,
                    "minimum_aperture_control_height": round(minimum_height, 2),
                    "screenshot": image_metrics(path),
                }
                context.close()

            browser.close()
    finally:
        if server is not None:
            server.terminate()
            with contextlib.suppress(Exception):
                server.wait(timeout=5)

    report["result"] = "PASS"
    (output / "VISUAL_FLOOR.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=os.environ.get("MANZANITA_URL", LOCAL))
    parser.add_argument("--output", type=Path, default=Path("/tmp/manzanita-rendered-visual-floor"))
    args = parser.parse_args()
    main(args.target, args.output)
