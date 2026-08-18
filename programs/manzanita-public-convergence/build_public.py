#!/usr/bin/env python3
"""Build the bounded public Manzanita photographic convergence release."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "manzanita"
ASSETS = OUT / "assets"
RELEASE = "1.6.0"
PHOTO_COMMIT = "507ace9af2d2121cb93614158809ee5ff88437f2"
PHOTO_RELEASE = "1.1.2"
PREDECESSOR_COMMIT = "750ad90f40462ab442a546bdbc2c7f02c81e2b27"
PREDECESSOR_TREE = "f6ea68bd4c5e07919277a099039354a5920d7b2b"
CANVAS = (1600, 1000)


def run(*args: str) -> str:
    result = subprocess.run(args, cwd=REPO, check=True, capture_output=True, text=True)
    return result.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def extract_photo_assets() -> dict[str, Image.Image]:
    source = run("git", "show", f"{PHOTO_COMMIT}:manzanita/app.js")
    match = re.match(r"\s*const\s+A\s*=\s*(\{.*?\});", source, re.S)
    if not match:
        raise RuntimeError("Photographic donor asset object was not found")
    values = json.loads(match.group(1))
    images: dict[str, Image.Image] = {}
    for key, value in values.items():
        if not isinstance(value, str) or not value.startswith("data:image/") or "," not in value:
            continue
        header, encoded = value.split(",", 1)
        if ";base64" not in header:
            continue
        image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
        images[key] = image
    if len(images) < 2:
        raise RuntimeError(f"Expected at least two photographic donor assets, found {sorted(images)}")
    return images


def fit(image: Image.Image, size: tuple[int, int] = CANVAS) -> Image.Image:
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def entropy_crop(image: Image.Image, ratio: float = 0.56) -> Image.Image:
    image = fit(image)
    width, height = image.size
    crop_w = int(width * ratio)
    crop_h = int(height * ratio)
    best: tuple[float, tuple[int, int, int, int]] | None = None
    gray = image.convert("L")
    for yi in range(5):
        for xi in range(7):
            left = int((width - crop_w) * xi / 6)
            top = int((height - crop_h) * yi / 4)
            box = (left, top, left + crop_w, top + crop_h)
            sample = gray.crop(box).resize((160, 100), Image.Resampling.BILINEAR)
            score = ImageStat.Stat(sample).var[0]
            if best is None or score > best[0]:
                best = (score, box)
    assert best is not None
    return ImageOps.fit(image.crop(best[1]), CANVAS, method=Image.Resampling.LANCZOS)


def street_crop(image: Image.Image) -> Image.Image:
    image = fit(image)
    width, height = image.size
    crop = image.crop((0, int(height * 0.32), width, height))
    crop = ImageOps.fit(crop, CANVAS, method=Image.Resampling.LANCZOS, centering=(0.5, 0.64))
    return ImageEnhance.Contrast(crop).enhance(1.06)


def neighborhood_composite(household: Image.Image, prop: Image.Image) -> Image.Image:
    a = fit(household, (800, 500))
    b = fit(prop, (800, 500))
    canvas = Image.new("RGB", CANVAS, "#171813")
    canvas.paste(a, (0, 0))
    canvas.paste(b, (800, 0))
    canvas.paste(ImageOps.mirror(b), (0, 500))
    canvas.paste(ImageOps.mirror(a), (800, 500))
    veil = Image.new("RGBA", CANVAS, (20, 23, 18, 62))
    return Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB")


def region_composite(household: Image.Image, prop: Image.Image) -> Image.Image:
    """Compose a legible modeled regional aperture without fabricating observation.

    The earlier version blurred two donors into a low-information wash. This version
    retains visible photographic texture, separates four contextual cells, and adds
    authored contour and relay marks so the regional aperture reads as an analytical
    composition rather than a soft background treatment.
    """

    household_full = fit(household)
    property_full = fit(prop)

    tiles = [
        ImageEnhance.Contrast(fit(household_full.crop((0, 0, 1120, 720)), (800, 500))).enhance(1.08),
        ImageEnhance.Color(fit(property_full.crop((480, 0, 1600, 720)), (800, 500))).enhance(0.82),
        ImageEnhance.Color(fit(property_full.crop((0, 280, 1120, 1000)), (800, 500))).enhance(0.70),
        ImageEnhance.Contrast(fit(household_full.crop((480, 280, 1600, 1000)), (800, 500))).enhance(1.16),
    ]

    canvas = Image.new("RGB", CANVAS, "#151712")
    canvas.paste(tiles[0], (0, 0))
    canvas.paste(tiles[1], (800, 0))
    canvas.paste(tiles[2], (0, 500))
    canvas.paste(tiles[3], (800, 500))

    analytical = canvas.convert("RGBA")
    veil = Image.new("RGBA", CANVAS, (17, 20, 15, 54))
    analytical = Image.alpha_composite(analytical, veil)
    draw = ImageDraw.Draw(analytical, "RGBA")

    # Cell boundaries remain explicit because these are modeled contextual
    # fragments, not one registered regional photograph.
    draw.line((800, 0, 800, 1000), fill=(244, 239, 227, 165), width=4)
    draw.line((0, 500, 1600, 500), fill=(244, 239, 227, 165), width=4)

    contours = [
        [(0, 176), (180, 126), (360, 158), (548, 86), (736, 142), (928, 92), (1112, 132), (1320, 72), (1600, 118)],
        [(0, 342), (174, 282), (356, 318), (526, 248), (720, 296), (902, 236), (1104, 270), (1304, 210), (1600, 254)],
        [(0, 710), (190, 650), (388, 688), (566, 620), (760, 660), (952, 604), (1150, 638), (1360, 578), (1600, 616)],
        [(0, 886), (194, 824), (382, 858), (584, 790), (780, 832), (980, 764), (1170, 802), (1378, 742), (1600, 772)],
    ]
    for index, points in enumerate(contours):
        draw.line(points, fill=(229, 223, 207, 188 - index * 18), width=5)

    # Relay nodes and one assistance route are authored analytical marks.
    nodes = [(228, 258), (604, 194), (1032, 316), (1372, 194), (382, 728), (932, 696), (1286, 798)]
    for x, y in nodes:
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(255, 90, 43, 228), outline=(244, 239, 227, 235), width=3)
    route = [(228, 258), (604, 194), (1032, 316), (1372, 194)]
    draw.line(route, fill=(255, 90, 43, 232), width=7, joint="curve")

    # A quiet analytical frame makes the classification visible at a glance.
    draw.rectangle((28, 28, 1572, 972), outline=(244, 239, 227, 195), width=4)
    draw.rectangle((52, 52, 408, 116), fill=(18, 19, 16, 205), outline=(244, 239, 227, 170), width=2)
    draw.text((76, 72), "MODELED REGIONAL CONTEXT", fill=(244, 239, 227, 235))

    return analytical.convert("RGB")


def stewardship_composite(household: Image.Image, prop: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", CANVAS, "#11120f")
    a = fit(household, (690, 430))
    b = fit(prop, (690, 430))
    canvas.paste(a, (70, 92))
    canvas.paste(b, (840, 478))
    return canvas


def save_webp(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "WEBP", quality=86, method=6)


def edge_profile(image: Image.Image) -> list[list[float]]:
    normalized = fit(image, (500, 312)).convert("L").filter(ImageFilter.FIND_EDGES)
    rows: list[list[float]] = []
    for band in range(9):
        y0 = int((normalized.height - 1) * (band + 1) / 11)
        points: list[float] = []
        for column in range(11):
            x0 = int(normalized.width * column / 11)
            x1 = int(normalized.width * (column + 1) / 11)
            strip = normalized.crop((x0, max(0, y0 - 22), x1, min(normalized.height, y0 + 22)))
            extrema = strip.getextrema()
            threshold = max(72, int((extrema[1] if extrema else 128) * 0.63))
            best_y = y0
            best_value = -1
            pixels = strip.load()
            for yy in range(strip.height):
                value = sum(1 for xx in range(strip.width) if pixels[xx, yy] >= threshold)
                if value > best_value:
                    best_value = value
                    best_y = max(0, y0 - 22) + yy
            points.append(round(best_y / normalized.height * 625, 1))
        rows.append(points)
    return rows


def paths_from_profile(rows: list[list[float]]) -> dict[str, list[str]]:
    def path(row: list[float], offset: float = 0.0) -> str:
        pts = [(round(i * 100, 1), round(max(18, min(607, y + offset)), 1)) for i, y in enumerate(row)]
        return "M " + " L ".join(f"{x} {y}" for x, y in pts)

    return {
        "habitat": [path(rows[1], -34), path(rows[2], 8)],
        "shade": [path(rows[0], 2), path(rows[1], 26)],
        "water": [path(rows[6], 18)],
        "fire": [path(rows[3], -6), path(rows[5], 10)],
        "air": [path(rows[0], -58)],
        "access": [path(rows[7], 30), path(rows[8], 6)],
        "labor": [path(rows[4], 18)],
        "authority": ["M 36 36 L 964 36 L 964 589 L 36 589 Z"],
    }


def write_assets() -> dict[str, Any]:
    donor = extract_photo_assets()
    household_source = donor.get("household") or next(iter(donor.values()))
    property_source = donor.get("property") or list(donor.values())[1]
    rendered = {
        "plant": entropy_crop(household_source, 0.48),
        "household": fit(household_source),
        "property": fit(property_source),
        "street": street_crop(property_source),
        "neighborhood": neighborhood_composite(household_source, property_source),
        "region": region_composite(household_source, property_source),
        "stewardship": stewardship_composite(household_source, property_source),
    }
    classification = {
        "plant": "derived photographic detail",
        "household": "retained photographic donor",
        "property": "retained photographic donor",
        "street": "derived photographic street-edge crop",
        "neighborhood": "derived multi-place analytical composite",
        "region": "derived modeled regional context",
        "stewardship": "derived continuity contact sheet",
    }
    scene_data: dict[str, Any] = {}
    for key, image in rendered.items():
        save_webp(image, ASSETS / f"{key}.webp")
        scene_data[key] = {
            "asset": f"assets/{key}.webp",
            "classification": classification[key],
            "registration": paths_from_profile(edge_profile(image)),
        }
    (ASSETS / "scene-data.json").write_text(json.dumps(scene_data, indent=2) + "\n", encoding="utf-8")
    return scene_data


INDEX = r'''<!doctype html>
<html lang="en" data-release="1.6.0" data-visual-system="photographic-place-fabric">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#151611">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="A public-safe photographic place fabric spanning useful plant, household, property, street, neighborhood, region, and stewardship.">
  <meta name="application-name" content="Manzanita Works">
  <meta name="robots" content="index,follow">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Manzanita Works · The Place Fabric">
  <meta property="og:description" content="Photographic place apertures, natural-border registration, assistance-first remediation, and durable handoff without parcel scoring.">
  <meta property="og:url" content="https://bigbirdreturns.github.io/axm-tools/manzanita/">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="https://bigbirdreturns.github.io/axm-tools/manzanita/">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23151611'/%3E%3Cpath d='M5 26 26 5M7 8h6v6H7zm11 10h6v6h-6z' fill='none' stroke='%23ff5a2b' stroke-width='2'/%3E%3C/svg%3E">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <title>Manzanita Works · The Place Fabric</title>
  <script src="theme-init.js"></script>
  <link rel="stylesheet" href="style.css">
  <script src="app.js" defer></script>
</head>
<body>
  <a class="skip" href="#main">Skip to the place fabric</a>
  <p class="sr-only" id="liveStatus" aria-live="polite" aria-atomic="true"></p>
  <header class="topbar">
    <a class="brand" href="#top" aria-label="Manzanita Works home"><span class="brand-mark" aria-hidden="true"></span><span>Manzanita Works</span></a>
    <nav aria-label="Primary navigation"><a href="#fabric">Place fabric</a><a href="#assistance">Assistance</a><a href="#estate">Estate</a><a href="#handoff">Handoff</a></nav>
    <div class="header-actions"><button id="printSheet" class="quiet-button" type="button">Print</button><button id="themeToggle" class="quiet-button" type="button" aria-pressed="false"><span id="themeLabel">Light</span></button></div>
  </header>

  <main id="main">
    <section class="hero" id="top">
      <figure class="hero-photo">