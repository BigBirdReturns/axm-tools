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

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat

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
    a = fit(household)
    b = fit(prop)
    blended = Image.blend(a, b, 0.52).filter(ImageFilter.GaussianBlur(radius=7))
    blended = ImageEnhance.Color(blended).enhance(0.58)
    blended = ImageEnhance.Contrast(blended).enhance(1.18)
    return blended


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
        <img src="assets/household.webp" alt="A retained photographic household landscape used as the public demonstration place for Manzanita Works.">
        <figcaption><span>Retained photographic donor</span><span>Public demonstration place · no surveyed geometry</span></figcaption>
        <div class="hero-trace" aria-hidden="true"><span></span><span></span><span></span></div>
      </figure>
      <div class="hero-copy">
        <p class="eyebrow">Useful plant → lived place → shared capacity → durable care</p>
        <h1>The place is the operating record.</h1>
        <p class="lede">Manzanita Works carries one landscape through seven genuine apertures without collapsing people, plants, animals, labor, evidence, authority, or uncertainty into a property score.</p>
        <div class="hero-actions"><a class="primary" href="#fabric">Open the place fabric</a><a class="secondary" href="#firewall">Read the purpose firewall</a></div>
        <dl class="hero-ledger"><div><dt>7</dt><dd>place apertures</dd></div><div><dt>8</dt><dd>independent conditions</dd></div><div><dt>5</dt><dd>operating seats</dd></div><div><dt>0</dt><dd>external effects</dd></div></dl>
      </div>
    </section>

    <section class="origin-band" aria-labelledby="originTitle">
      <div><p class="eyebrow">The actual origin</p><h2 id="originTitle">Fresh catnip exposed the entire system.</h2></div>
      <p>A household wanted fresh “cat bud” without paying a recurring premium. That small use case immediately connected propagation, attention, water, shade, animal use, tools, local supply, care burden, memory, and continuity. The fabric widened from there.</p>
    </section>

    <section class="fabric" id="fabric" aria-labelledby="fabricTitle">
      <header class="section-head"><div><p class="eyebrow">One canonical place, seven operating apertures</p><h2 id="fabricTitle">Change the aperture. Keep the record.</h2></div><p>The image, registration, evidence class, next safe action, authority boundary, and handoff change together. A scale control is not a crop switch.</p></header>

      <div class="aperture-rail" id="apertureRail" role="group" aria-label="Place apertures"></div>

      <div class="workbench">
        <article class="scene-card">
          <div class="scene-topline"><span id="sceneCode">MW-AP-01</span><span id="sceneClass">Derived photographic detail</span></div>
          <div class="scene" id="scene">
            <img id="sceneImage" src="assets/plant.webp" alt="">
            <svg id="overlaySvg" viewBox="0 0 1000 625" preserveAspectRatio="none" aria-label="Registered analytical conditions over the current place aperture"></svg>
            <div class="scene-label"><strong id="sceneLabel">Useful plant</strong><span id="sceneSource">Photographic donor · derived detail</span></div>
          </div>
          <p class="scene-caption" id="sceneCaption"></p>
        </article>

        <aside class="reading-card" aria-live="polite">
          <p class="eyebrow" id="apertureKicker"></p>
          <h3 id="apertureTitle"></h3>
          <p id="apertureBody"></p>
          <dl class="reading-ledger"><div><dt>Evidence in view</dt><dd id="evidenceView"></dd></div><div><dt>What matters</dt><dd id="whatMatters"></dd></div><div><dt>Next safe action</dt><dd id="nextAction"></dd></div><div><dt>Authority boundary</dt><dd id="authorityBoundary"></dd></div></dl>
          <button class="primary full" id="nextAperture" type="button">Continue through the place</button>
        </aside>
      </div>

      <div class="instrument-grid">
        <article class="control-card"><p class="eyebrow">Eight independent conditions</p><h3>Reveal a condition, not a verdict.</h3><div class="chip-row" id="overlayRail" role="group" aria-label="Condition overlays"></div><p class="small">Every mark is registered to this demonstration image. It remains authored analytical geometry, not field observation, survey, inspection, enforcement, coverage, or completed work.</p></article>
        <article class="control-card"><p class="eyebrow">Five operating seats</p><h3>Change who is acting and what they may do.</h3><div class="chip-row" id="roleRail" role="group" aria-label="Operating seats"></div><div class="role-reading"><span id="roleCode"></span><div><h4 id="roleTitle"></h4><p id="roleBody"></p></div></div><dl class="role-ledger"><div><dt>Available action</dt><dd id="roleAction"></dd></div><div><dt>Acceptance</dt><dd id="roleAcceptance"></dd></div><div><dt>Handoff</dt><dd id="roleHandoff"></dd></div></dl></article>
      </div>
      <div class="portable-row"><p>The current aperture, seat, and visible conditions are encoded in the address. This exact public reading can be reopened without creating a network request or external effect.</p><button class="secondary" id="exportState" type="button">Export this reading</button></div>
    </section>

    <section class="assistance" id="assistance" aria-labelledby="assistTitle">
      <header class="section-head inverse-head"><div><p class="eyebrow">Assistance-first operation</p><h2 id="assistTitle">Risk context should start help.</h2></div><p>Broad signals and verified local evidence remain separate. The route begins with capacity, consent, and assistance rather than punishment.</p></header>
      <ol class="sequence"><li><span>01</span><h3>Observe</h3><p>Retain source, place, time, transform, uncertainty, and rights.</p></li><li><span>02</span><h3>Verify</h3><p>Separate visible signal from accountable determination.</p></li><li><span>03</span><h3>Offer</h3><p>Route grants, tools, plants, advice, or trusted help.</p></li><li><span>04</span><h3>Plan</h3><p>Bound consent, access, scope, dependencies, and acceptance.</p></li><li><span>05</span><h3>Remediate</h3><p>Perform horticultural or operational work under real authority.</p></li><li><span>06</span><h3>Preserve</h3><p>Verify the result and retain a cold-successor handoff.</p></li></ol>
    </section>

    <section class="firewall" id="firewall" aria-labelledby="firewallTitle"><div><p class="eyebrow">Purpose firewall</p><h2 id="firewallTitle">Prevention data stays prevention data.</h2><p>Wildfire, heat, water, access, habitat, air, labor, and program context may start assistance. They do not silently become an adverse property verdict.</p></div><div class="firewall-grid"><article><span>May support</span><p>Inspection priority, grants, nursery supply, tool lending, crew coordination, horticultural remediation, community assistance, and emergency triage.</p></article><article class="deny"><span>Cannot silently become</span><p>Automatic insurance denial, unrelated property scoring, resident reputation ranking, eligibility punishment, or enforcement without accountable review and lawful authority.</p></article></div></section>

    <section class="estate" id="estate" aria-labelledby="estateTitle"><header class="section-head"><div><p class="eyebrow">The connected estate</p><h2 id="estateTitle">Six instruments. One durable record.</h2></div><p>Each instrument owns a bounded function. Their composition carries the place without turning the estate into one all-purpose platform.</p></header><div class="estate-grid"><article><span>01</span><h3>Household Habitat</h3><p>Lived use, pets, food, shade, water, access, tools, burden, and household agency.</p><small>Object: inhabited place</small></article><article><span>02</span><h3>Street Glide</h3><p>Claims registered to curb, canopy, roof, sidewalk, driveway, utility, and work edges.</p><small>Object: visible edge</small></article><article><span>03</span><h3>Regional Observatory</h3><p>Heat, fire, air, water, access, supply, labor, and program context without parcel certainty.</p><small>Object: wider signal</small></article><article><span>04</span><h3>Civic Planner</h3><p>Possible futures kept separate from permission, commitment, funding, or completed work.</p><small>Object: bounded possibility</small></article><article><span>05</span><h3>Manzanita Works</h3><p>Assistance, horticulture, tools, crews, remediation, verification, and monitoring.</p><small>Object: assistance path</small></article><article><span>06</span><h3>Essential Attention</h3><p>Evidence, bounded decisions, held effects, execution receipts, and successor continuity.</p><small>Object: durable handoff</small></article></div></section>

    <section class="handoff" id="handoff" aria-labelledby="handoffTitle"><div><p class="eyebrow">Governance and follow-through</p><h2 id="handoffTitle">The record survives the role.</h2><p>A condition becomes a source-bound object. The right function sees it. Authority stays explicit. Safe preparation continues. External effects remain held until authorized. The next person can reconstruct why the work exists.</p></div><div class="handoff-card"><div class="handoff-head"><span>Essential Attention</span><span>Public-safe handoff</span></div><div class="handoff-main"><small>Prepared next move</small><strong id="handoffMove">Carry the current place reading into a bounded evidence and decision record.</strong><p>No source-system writeback, assignment, purchase, scheduling, coverage, or enforcement effect is released here.</p></div><a id="handoffLink" class="primary full" href="../essential-attention/?from=manzanita-1.6.0">Open the FAB operating desk</a></div></section>

    <section class="provenance" aria-labelledby="provTitle"><header class="section-head"><div><p class="eyebrow">Visual and evidentiary provenance</p><h2 id="provTitle">Every image says what it is.</h2></div><p>The photographic donor is retained from the qualified v1.1.2 public release. Several apertures are deterministically derived analytical compositions. Registration marks are authored for the demonstration and acquire no physical standing.</p></header><div class="provenance-grid"><article><span>Retained photographic donor</span><p>Household and property images are recovered from exact commit <code>507ace9…</code>.</p></article><article><span>Derived photographic detail</span><p>Plant and street plates are deterministic crops of retained donor bytes.</p></article><article><span>Modeled context</span><p>Neighborhood, region, and stewardship plates compose retained bytes to expose wider relationships and continuity.</p></article><article><span>Public boundary</span><p>No private address, resident identity, credential, correspondence, meeting record, or field finding appears here.</p></article></div></section>
  </main>

  <footer><span>Manzanita Works · Public Place Fabric v1.6.0</span><span><a href="../">All axm-tools</a> · Static · local interaction · zero external-effect adapters</span></footer>
</body>
</html>
'''


STYLE = r''':root{color-scheme:light;--paper:#f1eee5;--paper-2:#e2ddd0;--ink:#171813;--muted:#65675f;--line:#b9b5a8;--signal:#f4512a;--sage:#7e8c62;--water:#4e91a7;--air:#8599b6;--violet:#8d759d;--dark:#151611;--dark-2:#20221b;--dark-ink:#f3efe5;--dark-muted:#b1ada2;--positive:#2c7557;--mono:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;--sans:Arial,"Helvetica Neue",Helvetica,sans-serif}
:root[data-theme="dark"]{color-scheme:dark;--paper:#151611;--paper-2:#20221b;--ink:#f3efe5;--muted:#b1ada2;--line:#484a40;--dark:#ece7db;--dark-2:#d8d2c4;--dark-ink:#171813;--dark-muted:#5f625a;--signal:#ff6540;--sage:#a9b58a;--water:#78b7c9;--air:#a9b8d1;--violet:#bea9cd;--positive:#73b18f}
*{box-sizing:border-box}html{scroll-behavior:smooth;background:var(--paper)}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 var(--sans);text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}a{color:inherit}button{font:inherit}button,a{touch-action:manipulation}.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}.skip{position:fixed;z-index:1000;left:1rem;top:-5rem;background:var(--signal);color:#151611;padding:.75rem 1rem;font:800 .72rem/1 var(--mono);text-transform:uppercase;letter-spacing:.08em}.skip:focus{top:1rem}.topbar{position:sticky;top:0;z-index:80;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;min-height:64px;padding:.65rem clamp(1rem,3vw,3rem);border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--paper) 94%,transparent);backdrop-filter:blur(14px)}.brand{display:flex;align-items:center;gap:.7rem;width:max-content;text-decoration:none;font:900 .76rem/1 var(--sans);letter-spacing:.09em;text-transform:uppercase}.brand-mark{position:relative;width:18px;height:18px}.brand-mark:before,.brand-mark:after{content:"";position:absolute;left:8px;top:-2px;width:2px;height:22px;background:var(--signal);transform:rotate(45deg)}.brand-mark:after{left:4px;top:3px;width:7px;height:7px;border:2px solid var(--signal);background:transparent;transform:none}.topbar nav{display:flex;gap:1.25rem}.topbar nav a{text-decoration:none;font:800 .64rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:.45rem 0;border-bottom:1px solid transparent}.topbar nav a:hover,.topbar nav a:focus-visible{border-color:var(--signal)}.header-actions{justify-self:end;display:flex;gap:.45rem}.quiet-button{min-height:42px;border:1px solid var(--line);background:transparent;color:var(--ink);padding:.65rem .85rem;cursor:pointer;font:800 .62rem/1 var(--mono);letter-spacing:.07em;text-transform:uppercase}.quiet-button:hover,.quiet-button:focus-visible{outline:2px solid var(--signal);outline-offset:2px}.hero{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(360px,.65fr);min-height:calc(100svh - 64px);border-bottom:1px solid var(--line)}.hero-photo{position:relative;margin:0;overflow:hidden;background:#111}.hero-photo>img{display:block;width:100%;height:100%;min-height:650px;object-fit:cover}.hero-photo:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 45%,rgba(9,10,8,.68))}.hero-photo figcaption{position:absolute;z-index:3;left:0;right:0;bottom:0;display:flex;justify-content:space-between;gap:1rem;padding:1rem 1.25rem;color:#f5f0e6;font:750 .6rem/1.3 var(--mono);letter-spacing:.08em;text-transform:uppercase}.hero-photo figcaption span:first-child{color:#ff6540}.hero-trace{position:absolute;z-index:2;inset:0;pointer-events:none}.hero-trace span{position:absolute;height:1px;background:rgba(255,255,255,.65);transform-origin:left}.hero-trace span:nth-child(1){left:7%;top:26%;width:39%;transform:rotate(7deg)}.hero-trace span:nth-child(2){right:8%;top:48%;width:31%;transform:rotate(-13deg)}.hero-trace span:nth-child(3){left:18%;bottom:19%;width:46%;transform:rotate(-4deg);background:var(--signal)}.hero-copy{display:flex;flex-direction:column;justify-content:center;padding:clamp(3rem,6vw,7rem) clamp(1.4rem,4vw,4rem);background:var(--dark);color:var(--dark-ink)}.eyebrow{margin:0 0 1rem;color:var(--signal);font:800 .66rem/1.4 var(--mono);letter-spacing:.15em;text-transform:uppercase}.hero h1,.section-head h2,.origin-band h2,.firewall h2,.handoff h2{margin:0;font-weight:900;letter-spacing:-.055em;line-height:.9}.hero h1{font-size:clamp(3.6rem,6vw,7.2rem);max-width:8.8ch}.lede{margin:1.8rem 0 0;color:var(--dark-muted);font-size:clamp(1rem,1.35vw,1.25rem);max-width:34rem}.hero-actions{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:2rem}.primary,.secondary{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:.78rem 1rem;border:1px solid currentColor;text-decoration:none;cursor:pointer;font:850 .65rem/1 var(--mono);letter-spacing:.07em;text-transform:uppercase}.primary{background:var(--signal);border-color:var(--signal);color:#151611}.secondary{background:transparent;color:inherit}.primary:hover,.primary:focus-visible,.secondary:hover,.secondary:focus-visible{outline:2px solid var(--signal);outline-offset:3px}.full{width:100%}.hero-ledger{display:grid;grid-template-columns:repeat(4,1fr);margin:2.5rem 0 0;border-top:1px solid #44463d;border-left:1px solid #44463d}.hero-ledger div{padding:1rem;border-right:1px solid #44463d;border-bottom:1px solid #44463d}.hero-ledger dt{font:900 1.7rem/1 var(--mono);color:var(--signal)}.hero-ledger dd{margin:.4rem 0 0;color:var(--dark-muted);font:700 .58rem/1.3 var(--mono);letter-spacing:.06em;text-transform:uppercase}.origin-band{display:grid;grid-template-columns:minmax(280px,.8fr) minmax(360px,1.2fr);gap:clamp(2rem,7vw,8rem);padding:clamp(4rem,8vw,8rem) clamp(1.3rem,5vw,5rem);border-bottom:1px solid var(--line)}.origin-band h2{font-size:clamp(2.7rem,5vw,6.2rem)}.origin-band>p{margin:0;color:var(--muted);font-size:1.08rem;max-width:58rem;align-self:end}.fabric,.estate,.provenance{padding:clamp(5rem,8vw,8rem) clamp(1.3rem,4vw,4rem)}.fabric{background:var(--paper-2);border-bottom:1px solid var(--line)}.section-head{display:grid;grid-template-columns:minmax(320px,1.15fr) minmax(300px,.85fr);gap:clamp(2rem,6vw,7rem);align-items:end;max-width:1550px;margin:0 auto 2.5rem}.section-head h2{font-size:clamp(3rem,5.7vw,7rem)}.section-head>p{margin:0;color:var(--muted);max-width:48rem}.aperture-rail{display:grid;grid-template-columns:repeat(7,1fr);max-width:1550px;margin:0 auto 1rem;border-top:1px solid var(--line);border-left:1px solid var(--line)}.aperture-rail button,.chip-row button{min-height:46px;border:0;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:transparent;color:var(--ink);padding:.78rem .65rem;cursor:pointer;font:800 .61rem/1.2 var(--mono);letter-spacing:.06em;text-transform:uppercase}.aperture-rail button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}.aperture-rail button:hover,.aperture-rail button:focus-visible,.chip-row button:hover,.chip-row button:focus-visible{outline:2px solid var(--signal);outline-offset:-2px}.workbench{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(330px,.55fr);max-width:1550px;margin:0 auto;border:1px solid var(--line)}.scene-card{min-width:0;padding:1rem;border-right:1px solid var(--line);background:var(--paper)}.scene-topline{display:flex;justify-content:space-between;gap:1rem;margin-bottom:.75rem;font:750 .59rem/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase}.scene-topline span:first-child{color:var(--signal)}.scene{position:relative;aspect-ratio:8/5;overflow:hidden;background:#111}.scene>img{display:block;width:100%;height:100%;object-fit:cover}.scene>svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.scene-label{position:absolute;left:0;bottom:0;z-index:4;display:flex;justify-content:space-between;gap:1rem;width:100%;padding:.75rem 1rem;background:rgba(17,18,15,.88);color:#f5f0e6;font:750 .6rem/1.2 var(--mono);letter-spacing:.07em;text-transform:uppercase}.scene-label span{color:#bcb7aa}.scene-caption{margin:.85rem 0 0;color:var(--muted);font-size:.82rem}.reading-card{padding:clamp(1.3rem,2.6vw,2.4rem);background:var(--paper)}.reading-card h3{margin:0;font-size:clamp(2rem,3.2vw,3.7rem);line-height:.92;letter-spacing:-.045em;text-transform:uppercase}.reading-card>p:not(.eyebrow){color:var(--muted)}.reading-ledger,.role-ledger{margin:1.8rem 0}.reading-ledger div,.role-ledger div{padding:1rem 0;border-top:1px solid var(--line)}.reading-ledger dt,.role-ledger dt{font:800 .59rem/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--signal)}.reading-ledger dd,.role-ledger dd{margin:.42rem 0 0;font-size:.9rem}.instrument-grid{display:grid;grid-template-columns:1fr 1fr;max-width:1550px;margin:1rem auto 0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.control-card{padding:1.4rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--paper)}.control-card h3{margin:0;font-size:1.4rem;text-transform:uppercase;letter-spacing:-.025em}.chip-row{display:flex;flex-wrap:wrap;margin-top:1rem;border-top:1px solid var(--line);border-left:1px solid var(--line)}.chip-row button[aria-pressed="true"]{background:var(--signal);color:#151611}.small{color:var(--muted);font-size:.79rem;max-width:58rem}.role-reading{display:grid;grid-template-columns:auto 1fr;gap:.6rem 1rem;margin-top:1.2rem;padding-top:1.2rem;border-top:1px solid var(--line)}.role-reading>span{font:850 .62rem/1 var(--mono);color:var(--signal)}.role-reading h4{margin:0;font-size:1.25rem;text-transform:uppercase}.role-reading p{margin:.35rem 0 0;color:var(--muted)}.portable-row{display:flex;align-items:center;justify-content:space-between;gap:2rem;max-width:1550px;margin:1rem auto 0;padding:1rem;border:1px solid var(--line);background:var(--paper)}.portable-row p{margin:0;color:var(--muted);font-size:.85rem;max-width:65rem}.assistance{padding:clamp(5rem,8vw,8rem) clamp(1.3rem,4vw,4rem);background:var(--dark);color:var(--dark-ink)}.inverse-head>p{color:var(--dark-muted)}.sequence{display:grid;grid-template-columns:repeat(3,1fr);max-width:1550px;margin:0 auto;padding:0;list-style:none;border-top:1px solid #484a40;border-left:1px solid #484a40}.sequence li{min-height:180px;padding:1.3rem;border-right:1px solid #484a40;border-bottom:1px solid #484a40}.sequence span,.estate-grid>article>span{font:800 .62rem/1 var(--mono);color:var(--signal)}.sequence h3,.estate-grid h3{margin:.8rem 0 .4rem;font-size:1.1rem}.sequence p{margin:0;color:var(--dark-muted);font-size:.88rem}.firewall{display:grid;grid-template-columns:minmax(300px,.85fr) minmax(420px,1.15fr);gap:clamp(3rem,7vw,8rem);padding:clamp(5rem,8vw,8rem) clamp(1.3rem,5vw,5rem);border-bottom:1px solid var(--line)}.firewall h2{font-size:clamp(3rem,5.7vw,7rem)}.firewall>div:first-child>p:not(.eyebrow){color:var(--muted);max-width:42rem}.firewall-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-self:start}.firewall-grid article{padding:1.5rem;border-top:4px solid var(--positive);background:var(--paper-2)}.firewall-grid .deny{border-color:var(--signal)}.firewall-grid span{font:800 .65rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase}.firewall-grid p{margin:.8rem 0 0;color:var(--muted)}.estate{border-bottom:1px solid var(--line)}.estate-grid{display:grid;grid-template-columns:repeat(3,1fr);max-width:1550px;margin:0 auto;border-top:1px solid var(--line);border-left:1px solid var(--line)}.estate-grid article{min-height:210px;padding:1.4rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.estate-grid p{margin:0;color:var(--muted);font-size:.88rem}.estate-grid small{display:block;margin-top:1.4rem;padding-top:.75rem;border-top:1px solid var(--line);color:var(--muted);font:700 .58rem/1.4 var(--mono);letter-spacing:.06em;text-transform:uppercase}.handoff{display:grid;grid-template-columns:minmax(320px,1.15fr) minmax(330px,.85fr);gap:clamp(3rem,7vw,8rem);align-items:center;padding:clamp(5rem,8vw,8rem) clamp(1.3rem,5vw,5rem);background:var(--signal);color:#151611}.handoff h2{font-size:clamp(3rem,5.7vw,7rem)}.handoff>div:first-child>p:not(.eyebrow){max-width:50rem}.handoff .eyebrow{color:#151611}.handoff-card{border:1px solid #151611;background:var(--paper);color:var(--ink)}.handoff-head{display:flex;justify-content:space-between;gap:1rem;padding:.8rem 1rem;border-bottom:1px solid var(--line);font:800 .62rem/1 var(--mono);letter-spacing:.07em;text-transform:uppercase}.handoff-main{padding:1.4rem}.handoff-main small{color:var(--signal);font:800 .59rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase}.handoff-main strong{display:block;margin:.7rem 0;font-size:1.35rem;line-height:1.05}.handoff-main p{margin:0;color:var(--muted);font-size:.86rem}.provenance-grid{display:grid;grid-template-columns:repeat(4,1fr);max-width:1550px;margin:0 auto;border-top:1px solid var(--line);border-left:1px solid var(--line)}.provenance-grid article{padding:1.3rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.provenance-grid span{font:800 .62rem/1.3 var(--mono);letter-spacing:.07em;text-transform:uppercase;color:var(--signal)}.provenance-grid p{margin:.7rem 0 0;color:var(--muted);font-size:.84rem}.provenance-grid code{font-family:var(--mono)}footer{display:flex;justify-content:space-between;gap:1rem;padding:1rem clamp(1rem,4vw,4rem);border-top:1px solid var(--line);color:var(--muted);font:700 .59rem/1.4 var(--mono);letter-spacing:.06em;text-transform:uppercase}.overlay-path{fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;filter:drop-shadow(0 1px 1px rgba(0,0,0,.35))}.overlay-habitat{stroke:var(--sage)}.overlay-shade{stroke:#d1c78c}.overlay-water{stroke:var(--water)}.overlay-fire{stroke:var(--signal)}.overlay-air{stroke:var(--air)}.overlay-access{stroke:#f2eee3}.overlay-labor{stroke:var(--violet)}.overlay-authority{stroke:#f2eee3;stroke-dasharray:8 7}.overlay-tag{font:800 13px/1 var(--mono);letter-spacing:.05em;text-transform:uppercase;paint-order:stroke;stroke:#151611;stroke-width:3px;stroke-linejoin:round}
@media(max-width:1100px){.topbar{grid-template-columns:1fr auto}.topbar nav{display:none}.hero{grid-template-columns:1fr}.hero-photo>img{min-height:56svh}.hero-copy{min-height:auto}.section-head,.origin-band,.firewall{grid-template-columns:1fr}.workbench{grid-template-columns:1fr}.scene-card{border-right:0;border-bottom:1px solid var(--line)}.aperture-rail{grid-template-columns:repeat(4,1fr)}.estate-grid{grid-template-columns:repeat(2,1fr)}.provenance-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:720px){.topbar{min-height:58px;padding:.55rem .8rem}.brand{font-size:.68rem}.header-actions .quiet-button:first-child{display:none}.hero-photo>img{min-height:54svh}.hero-copy{padding:3rem 1rem}.hero h1{font-size:clamp(3rem,16vw,5.3rem)}.hero-ledger{grid-template-columns:1fr 1fr}.origin-band,.fabric,.assistance,.estate,.provenance,.firewall,.handoff{padding:4rem 1rem}.section-head h2,.origin-band h2,.firewall h2,.handoff h2{font-size:clamp(2.6rem,13vw,4.7rem)}.aperture-rail{display:flex;overflow-x:auto}.aperture-rail button{min-width:132px}.instrument-grid,.firewall-grid,.handoff{grid-template-columns:1fr}.portable-row{align-items:stretch;flex-direction:column}.sequence{grid-template-columns:1fr 1fr}.estate-grid,.provenance-grid{grid-template-columns:1fr}.scene-topline,.scene-label{font-size:.52rem}.scene-label{align-items:flex-start;flex-direction:column}.reading-card h3{font-size:2.3rem}footer{align-items:flex-start;flex-direction:column}}
@media(max-width:420px){.sequence{grid-template-columns:1fr}.hero-actions{flex-direction:column}.hero-actions a{width:100%}.chip-row button{flex:1 1 48%;min-height:48px}.quiet-button{min-height:44px}.scene{aspect-ratio:4/3}.workbench{border-left:0;border-right:0}.control-card{padding:1rem}.aperture-rail{margin-inline:-1rem}.aperture-rail button{min-width:124px}.hero-photo figcaption{font-size:.5rem}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
@media print{.topbar,.hero-actions,.aperture-rail,.chip-row,.portable-row button,#nextAperture{display:none!important}body{background:#fff;color:#111}.hero{display:block;min-height:auto}.hero-photo>img{min-height:0;max-height:46vh}.hero-copy,.assistance{background:#fff;color:#111}.hero-copy{padding:1.5rem}.hero h1{font-size:42pt}.hero-copy .lede,.sequence p{color:#333}.fabric,.estate,.provenance,.firewall,.handoff,.origin-band,.assistance{padding:1.2rem}.workbench,.instrument-grid,.estate-grid,.provenance-grid{break-inside:avoid}.handoff{background:#fff}.handoff-card{max-width:6.5in}footer{font-size:8pt}}
'''


APP = r'''(() => {
  'use strict';
  const apertures = [
    {id:'plant',code:'MW-AP-01',label:'Useful plant',kicker:'Origin object',title:'One useful plant reveals the operating system.',body:'Fresh catnip joins household value, animal use, propagation, water, light, space, cost, care cadence, tools, and memory in one small object.',evidence:'Derived photographic detail from the retained household donor.',matters:'A repeatable growing method that fits the household’s actual attention and space.',next:'Test the smallest complete care loop and preserve what worked.',authority:'The household decides whether the object belongs in its life.',caption:'The origin remains deliberately small, useful, and observable.',source:'Photographic donor · derived detail'},
    {id:'household',code:'MW-AP-02',label:'Household',kicker:'Lived system',title:'The yard is an inhabited operating environment.',body:'People, animals, food, play, sensory relief, shade, water, tools, maintenance, and caregiver attention occupy the same place.',evidence:'Retained household photograph from the qualified v1.1.2 public donor.',matters:'Daily use and care burden before ornamental category or outside judgment.',next:'Map the routines and capacities the place must support before proposing change.',authority:'Observation cannot override household consent or invent household capacity.',caption:'Household Habitat keeps lived use and burden in the same record.',source:'Retained photographic donor'},
    {id:'property',code:'MW-AP-03',label:'Property',kicker:'Visible twin',title:'Overlapping conditions stay independently inspectable.',body:'Shade, water, access, fuel, habitat, labor, structures, and authority share one physical place without becoming one score.',evidence:'Retained property photograph from the qualified v1.1.2 public donor.',matters:'Natural borders, dependencies, visible edges, source quality, and what remains unknown.',next:'Attach each claim to a bounded zone or edge and retain uncertainty.',authority:'A visual interpretation is not a survey, inspection, entry right, or work authorization.',caption:'The property aperture exposes dependencies without manufacturing parcel certainty.',source:'Retained photographic donor'},
    {id:'street',code:'MW-AP-04',label:'Street',kicker:'Street Glide',title:'The public edge is read through natural borders.',body:'Curb, canopy, roof, sidewalk, driveway, utility, parcel, and work edges divide responsibility while the street remains one inhabited scene.',evidence:'Derived street-edge crop with authored, image-registered analytical marks.',matters:'Where a visible condition meets access, ownership, public responsibility, and shared effects.',next:'Read the edge, retain uncertainty, and distinguish household, neighbor, utility, and public roles.',authority:'A street observation creates no access, enforcement, ownership, or maintenance authority.',caption:'Street Glide follows the visible landscape instead of floating geometry.',source:'Derived photographic street-edge crop'},
    {id:'neighborhood',code:'MW-AP-05',label:'Neighborhood',kicker:'Shared capacity',title:'Linked conditions meet unequal capacity.',body:'Adjacent households share heat, canopy, water, access, smoke, tools, nurseries, trusted relays, and labor without becoming interchangeable units.',evidence:'Derived multi-place analytical composite from retained donor bytes.',matters:'The specific shared condition and the specific capacity gap, with household boundaries intact.',next:'Route the capacity gap to the function able to help before adding obligations.',authority:'Neighborhood context cannot become a household verdict, ranking, or reputation score.',caption:'The neighborhood aperture widens effects and resources while retaining household agency.',source:'Derived multi-place analytical composite'},
    {id:'region',code:'MW-AP-06',label:'Region',kicker:'Regional Observatory',title:'Wide context remains separate from local determination.',body:'Heat, air, wildfire, water, access, supply, labor, terrain, and public programs shape many places differently and change over time.',evidence:'Modeled regional context derived from retained photographic donors.',matters:'Signal, verified finding, capacity, completed mitigation, and time must remain distinct.',next:'Use regional context to prioritize assistance and evidence collection.',authority:'No automatic insurance denial, unrelated scoring, evacuation order, or parcel determination.',caption:'The regional aperture widens the record without manufacturing local certainty.',source:'Derived modeled regional context'},
    {id:'stewardship',code:'MW-AP-07',label:'Stewardship',kicker:'Continuity',title:'The work survives a change of hands.',body:'Evidence, rationale, authority, safe preparation, verification, held effects, and unresolved branches remain reconstructable after a role changes.',evidence:'Derived continuity contact sheet plus the current public interaction state.',matters:'Why the condition mattered, what authority existed, what was prepared, what happened, and what remains safe.',next:'Verify the result and export a trustworthy handoff.',authority:'External effects require real authority. Internal preparation and continuity do not require finding a person.',caption:'Stewardship turns the place into a durable, bounded handoff.',source:'Derived continuity contact sheet'}
  ];
  const overlays = [
    {id:'habitat',label:'Habitat',cls:'overlay-habitat'},
    {id:'shade',label:'Shade + heat',cls:'overlay-shade'},
    {id:'water',label:'Water',cls:'overlay-water'},
    {id:'fire',label:'Fire',cls:'overlay-fire'},
    {id:'air',label:'Air',cls:'overlay-air'},
    {id:'access',label:'Access',cls:'overlay-access'},
    {id:'labor',label:'Labor + tools',cls:'overlay-labor'},
    {id:'authority',label:'Authority + programs',cls:'overlay-authority'}
  ];
  const roles = [
    {id:'resident',code:'R-01',label:'Resident',body:'Reads the place through daily use, consent, cost, care load, correction, and recourse.',action:'Correct, narrow, defer, or prepare a household-safe next step.',acceptance:'The reading supports lived use without adding an unrequested burden.',handoff:'A bounded household context packet with no external effect.',layers:['habitat','shade','water']},
    {id:'nursery',code:'R-02',label:'Nursery / grower',body:'Reads what can be propagated, supplied, maintained, replaced, and supported locally.',action:'Prepare fit, timing, supply, replacement, and survival questions.',acceptance:'The plant and supply option match the place, season, and care capacity.',handoff:'A source-bounded plant and supply brief.',layers:['habitat','water','labor']},
    {id:'crew',code:'R-03',label:'Crew / steward',body:'Reads what work is authorized, accessible, safe, dependent, and verifiable.',action:'Prepare scope, access, tools, dependencies, hazards, and acceptance criteria.',acceptance:'The work can be performed within real access and authority.',handoff:'A bounded work-preparation packet, not an assignment.',layers:['access','labor','fire']},
    {id:'planner',code:'R-04',label:'Planner / program',body:'Reads where shared conditions justify resources without inventing parcel certainty.',action:'Prepare assistance eligibility questions and affected-interest review.',acceptance:'Resources reach the named capacity gap without adverse reuse.',handoff:'A purpose-limited assistance-routing record.',layers:['fire','air','authority']},
    {id:'successor',code:'R-05',label:'Successor',body:'Reads why the current state exists and what remains safe to continue.',action:'Verify sources, rationale, authority, receipts, failures, and open branches.',acceptance:'A cold successor can reconstruct the object without private oral history.',handoff:'A portable continuity packet with unresolved branches intact.',layers:['authority','access','labor']}
  ];
  const defaults = {plant:['habitat','water'],household:['habitat','shade'],property:['water','access'],street:['access','authority'],neighborhood:['shade','labor'],region:['fire','air'],stewardship:['authority','labor']};
  const state = {aperture:'plant',role:'resident',layers:new Set(defaults.plant),sceneData:{}};
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function params(){return new URLSearchParams(location.search)}
  function announce(text){const region=$('#liveStatus');if(region)region.textContent=text}
  function currentAperture(){return apertures.find(item=>item.id===state.aperture)||apertures[0]}
  function currentRole(){return roles.find(item=>item.id===state.role)||roles[0]}
  function syncUrl(){const url=new URL(location.href);url.searchParams.set('aperture',state.aperture);url.searchParams.set('role',state.role);url.searchParams.set('layers',overlays.filter(o=>state.layers.has(o.id)).map(o=>o.id).join(','));history.replaceState(null,'',`${url.pathname}?${url.searchParams.toString()}${url.hash}`)}
  function hydrateFromUrl(){const p=params();if(apertures.some(a=>a.id===p.get('aperture')))state.aperture=p.get('aperture');if(roles.some(r=>r.id===p.get('role')))state.role=p.get('role');if(p.has('layers'))state.layers=new Set((p.get('layers')||'').split(',').filter(id=>overlays.some(o=>o.id===id)));else state.layers=new Set(defaults[state.aperture])}
  function buildControls(){
    $('#apertureRail').innerHTML=apertures.map(a=>`<button type="button" data-aperture="${a.id}" aria-pressed="${a.id===state.aperture}">${esc(a.label)}</button>`).join('');
    $('#overlayRail').innerHTML=overlays.map(o=>`<button type="button" data-overlay="${o.id}" aria-pressed="${state.layers.has(o.id)}">${esc(o.label)}</button>`).join('');
    $('#roleRail').innerHTML=roles.map(r=>`<button type="button" data-role="${r.id}" aria-pressed="${r.id===state.role}">${esc(r.label)}</button>`).join('');
  }
  function drawOverlays(){const datum=state.sceneData[state.aperture];const active=overlays.filter(o=>state.layers.has(o.id));const svg=$('#overlaySvg');svg.innerHTML=active.flatMap((overlay,index)=>{const paths=((datum&&datum.registration&&datum.registration[overlay.id])||[]);const labelY=28+index*24;return paths.map((d,pathIndex)=>`<path class="overlay-path ${overlay.cls}" data-overlay-shape="${overlay.id}" d="${d}" opacity="${pathIndex===0?'.94':'.63'}"></path>`).concat([`<text x="${760}" y="${labelY}" class="overlay-tag" fill="currentColor">${esc(overlay.label)}</text>`])}).join('');document.querySelectorAll('[data-overlay]').forEach(b=>b.setAttribute('aria-pressed',String(state.layers.has(b.dataset.overlay))))}
  function render(){
    const aperture=currentAperture();const role=currentRole();const datum=state.sceneData[aperture.id]||{};
    document.documentElement.dataset.aperture=aperture.id;document.documentElement.dataset.role=role.id;
    document.querySelectorAll('[data-aperture]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.aperture===aperture.id)));
    document.querySelectorAll('[data-role]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.role===role.id)));
    $('#sceneCode').textContent=aperture.code;$('#sceneClass').textContent=datum.classification||aperture.source;$('#sceneImage').src=datum.asset||`assets/${aperture.id}.webp`;$('#sceneImage').alt=`${aperture.label} aperture. ${aperture.caption}`;$('#sceneLabel').textContent=aperture.label;$('#sceneSource').textContent=aperture.source;$('#sceneCaption').textContent=aperture.caption;
    $('#apertureKicker').textContent=aperture.kicker;$('#apertureTitle').textContent=aperture.title;$('#apertureBody').textContent=aperture.body;$('#evidenceView').textContent=aperture.evidence;$('#whatMatters').textContent=aperture.matters;$('#nextAction').textContent=aperture.next;$('#authorityBoundary').textContent=aperture.authority;
    $('#roleCode').textContent=role.code;$('#roleTitle').textContent=role.label;$('#roleBody').textContent=role.body;$('#roleAction').textContent=role.action;$('#roleAcceptance').textContent=role.acceptance;$('#roleHandoff').textContent=role.handoff;
    $('#handoffMove').textContent=`${role.label}: ${role.handoff}`;
    $('#handoffLink').href=`../essential-attention/?from=manzanita-1.6.0&aperture=${encodeURIComponent(aperture.id)}&role=${encodeURIComponent(role.id)}&layers=${encodeURIComponent([...state.layers].join(','))}`;
    drawOverlays();syncUrl();
  }
  function selectAperture(id,{reset=true,notify=true}={}){if(!apertures.some(a=>a.id===id))return;state.aperture=id;if(reset)state.layers=new Set(defaults[id]);render();if(notify)announce(`${currentAperture().label} aperture selected. ${currentAperture().title}`)}
  function selectRole(id,{applyLayers=true,notify=true}={}){if(!roles.some(r=>r.id===id))return;state.role=id;if(applyLayers)state.layers=new Set(currentRole().layers);render();if(notify)announce(`${currentRole().label} seat selected. ${currentRole().action}`)}
  function toggleLayer(id){const item=overlays.find(o=>o.id===id);if(!item)return;const show=!state.layers.has(id);show?state.layers.add(id):state.layers.delete(id);render();announce(`${item.label} condition ${show?'shown':'hidden'}.`)}
  function bindGroup(container,selector,activate){container.addEventListener('keydown',event=>{if(!['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(event.key))return;const buttons=[...container.querySelectorAll(selector)];const current=buttons.indexOf(event.target.closest(selector));if(current<0)return;event.preventDefault();let next=current;if(event.key==='Home')next=0;else if(event.key==='End')next=buttons.length-1;else if(event.key==='ArrowRight'||event.key==='ArrowDown')next=(current+1)%buttons.length;else next=(current-1+buttons.length)%buttons.length;buttons[next].focus();if(activate)activate(buttons[next])})}
  function updateTheme(){const dark=document.documentElement.dataset.theme==='dark';$('#themeToggle').setAttribute('aria-pressed',String(dark));$('#themeLabel').textContent=dark?'Dark':'Light';document.querySelector('meta[name="theme-color"]').setAttribute('content',dark?'#151611':'#f1eee5')}
  async function boot(){
    state.sceneData=await fetch('assets/scene-data.json').then(r=>{if(!r.ok)throw new Error(`scene-data ${r.status}`);return r.json()});
    hydrateFromUrl();buildControls();render();updateTheme();
    $('#apertureRail').addEventListener('click',e=>{const b=e.target.closest('[data-aperture]');if(b)selectAperture(b.dataset.aperture)});
    $('#overlayRail').addEventListener('click',e=>{const b=e.target.closest('[data-overlay]');if(b)toggleLayer(b.dataset.overlay)});
    $('#roleRail').addEventListener('click',e=>{const b=e.target.closest('[data-role]');if(b)selectRole(b.dataset.role)});
    $('#nextAperture').addEventListener('click',()=>{const i=apertures.findIndex(a=>a.id===state.aperture);selectAperture(apertures[(i+1)%apertures.length].id);$('#scene').scrollIntoView({block:'center'})});
    $('#themeToggle').addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;localStorage.setItem('manzanita-theme',next);updateTheme()});
    $('#printSheet').addEventListener('click',()=>window.print());
    $('#exportState').addEventListener('click',()=>{const payload={schema:'manzanita-works/public-reading@1',release:'1.6.0',aperture:state.aperture,role:state.role,layers:overlays.filter(o=>state.layers.has(o.id)).map(o=>o.id),authority:{external_effect:'none',public_projection:true}};const blob=new Blob([JSON.stringify(payload,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`manzanita-${state.aperture}-${state.role}.json`;a.click();URL.revokeObjectURL(url);announce('The current public reading was exported locally.')});
    bindGroup($('#apertureRail'),'[data-aperture]',b=>selectAperture(b.dataset.aperture));bindGroup($('#roleRail'),'[data-role]',b=>selectRole(b.dataset.role));bindGroup($('#overlayRail'),'[data-overlay]',null);
  }
  boot().catch(error=>{console.error(error);announce('The place fabric could not load its retained scene registration.');document.documentElement.dataset.loadState='failed'});
})();
'''


THEME = r'''(() => {
  const stored = localStorage.getItem('manzanita-theme');
  const theme = stored === 'light' || stored === 'dark' ? stored : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;
})();
'''


README = f'''# Manzanita Works v{RELEASE} · Public Place Fabric

Manzanita Works is the public-safe photographic front door for the connected household-to-region estate. The release converges the retained v{PHOTO_RELEASE} photographic donor with the bounded operating law developed through the seven-aperture, Street Glide, eight-overlay, five-seat, whole-experience, resilience, parity, succession, and release-control program.

The site contains seven visually and semantically distinct apertures over one public demonstration place: useful plant, household, property, street, neighborhood, region, and stewardship. Household and property images are retained from exact commit `{PHOTO_COMMIT}`. Plant and street are deterministic crops. Neighborhood, region, and stewardship are deterministic analytical compositions. Every aperture states its asset class. Authored registration follows image-derived edge profiles but remains a demonstration treatment rather than survey, inspection, field observation, access, work, enforcement, coverage, or completed-remediation authority.

Eight independent conditions remain selectable: habitat, shade and heat, water, fire, air, access, labor and tools, and authority and programs. Five operating seats change the governed object rather than merely relabeling prose: resident, nursery or grower, crew or steward, planner or program, and successor. Each seat changes available action, acceptance, handoff, and recommended evidence layers.

The page is static and makes no application network request after its own files load. It has no account, telemetry, model call, payment, email, scheduling, assignment, coverage, enforcement, or source-system writeback adapter. Export creates a local JSON reading only. The Essential Attention link carries public-safe aperture and seat context into a separate local operating desk.

## Release boundary

This is a bounded public projection authorized as a replacement for the already public Manzanita route. It does not release the complete `manzanita-next` successor, perform any of its ten external campaigns, confer physical or private standing, reconstruct the missing canonical backlog, or change canonical task counts. v1.4.1 remains the exact public rollback donor at commit `{PREDECESSOR_COMMIT}` and route tree `{PREDECESSOR_TREE}`.
'''


CONSTITUTION = '''# Manzanita photographic place-fabric constitution

The public surface must begin with the place rather than a slogan, score, or control panel. Photographic and derived visual donors carry explicit classifications. Derived context may clarify relationships but may not impersonate observation.

Seven apertures must change the represented object, evidence class, next safe action, authority boundary, and handoff together. A crop alone is not a scale. Each aperture requires a distinct asset file and a distinct semantic contract.

Eight conditions remain independently selectable. Registration occupies the same normalized scene coordinate system as the image. Image and analytical marks must resize together. Marks follow edge profiles derived from retained visual bytes, but they remain authored demonstration geometry without survey, inspection, field, entry, work, enforcement, coverage, or completed-remediation standing.

Five operating seats change available action, acceptance, handoff, and recommended evidence layers. Role switching cannot be a paragraph substitution.

The purpose firewall is permanent. Prevention context may start assistance, grants, tools, nursery supply, crews, horticultural remediation, community support, and emergency triage. It may not silently become automatic insurance denial, unrelated property scoring, resident ranking, eligibility punishment, or enforcement.

Light and dark themes preserve one information hierarchy. Tablet and mobile retain aperture, overlay, and role operation. Controls remain at least 44 CSS pixels in compact layouts. Text must reflow at 200 percent without horizontal page overflow. Reduced motion preserves meaning. Print may suppress controls but must preserve the represented place, provenance, purpose boundary, authority, and release identity.

A release fails if exact public bytes differ from the qualification record, if any aperture loses its distinct asset, if image and registration separate under resizing, if a seat fails to change the governed object, if private data enters the public surface, or if a public maintenance transaction is misrepresented as successor completion.
'''


STATIC_TEST = r'''from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
q = json.loads((ROOT / 'QUALIFICATION.json').read_text(encoding='utf-8'))
r = json.loads((ROOT / 'RELEASE_RECEIPT.json').read_text(encoding='utf-8'))
assert q['schema'] == 'manzanita-works/pages-qualification@6'
assert q['release'] == '1.6.0'
assert q['visual_system'] == 'photographic-place-fabric'
assert q['apertures'] == 7 and q['overlays'] == 8 and q['operating_seats'] == 5
assert q['external_effect_adapters'] == 0
assert q['distinct_aperture_assets'] == 7
assert r['release'] == '1.6.0'
assert r['authority']['successor_program_effect'] == 'none'
assert r['authority']['external_campaign_effect'] == 'none'
assert r['authority']['canonical_task_count_effect'] == 'none'
for name, expected in q['files'].items():
    data = (ROOT / name).read_bytes()
    assert len(data) == expected['bytes'], (name, len(data), expected['bytes'])
    assert hashlib.sha256(data).hexdigest() == expected['sha256'], name
html = (ROOT / 'index.html').read_text(encoding='utf-8')
css = (ROOT / 'style.css').read_text(encoding='utf-8')
js = (ROOT / 'app.js').read_text(encoding='utf-8')
for phrase in ('data-release="1.6.0"','photographic-place-fabric','The place is the operating record.','Fresh catnip exposed the entire system.','Change the aperture. Keep the record.','Prevention data stays prevention data.','Automatic insurance denial','Essential Attention','Every image says what it is.'):
    assert phrase in html, phrase
assert len(re.findall(r"id:'(?:plant|household|property|street|neighborhood|region|stewardship)'", js)) == 7
assert len(re.findall(r"id:'(?:habitat|shade|water|fire|air|access|labor|authority)'", js)) == 8
assert len(re.findall(r"id:'(?:resident|nursery|crew|planner|successor)'", js)) == 5
assert 'history.replaceState' in js and 'URLSearchParams' in js
assert 'window.print()' in js and 'new Blob' in js
assert "'ArrowRight'" in js and "'Home'" in js and "'End'" in js
for forbidden in ('XMLHttpRequest','WebSocket','EventSource','navigator.sendBeacon'):
    assert forbidden not in js
assert "fetch('assets/scene-data.json')" in js
assert '@media print' in css and '@media(max-width:420px)' in css and '@media(prefers-reduced-motion:reduce)' in css
assert len(list((ROOT / 'assets').glob('*.webp'))) == 7
scene = json.loads((ROOT / 'assets/scene-data.json').read_text(encoding='utf-8'))
assert set(scene) == {'plant','household','property','street','neighborhood','region','stewardship'}
assert all(Path(ROOT / row['asset']).is_file() for row in scene.values())
assert all(set(row['registration']) == {'habitat','shade','water','fire','air','access','labor','authority'} for row in scene.values())
print('Manzanita Works v1.6.0 photographic public contract: PASS')
'''


BROWSER_TEST = r'''from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
LOCAL = 'http://127.0.0.1:8765/manzanita/'
TARGET = os.environ.get('MANZANITA_URL', LOCAL)
OUT = Path(os.environ.get('MANZANITA_SCREENSHOT_DIR', ROOT / 'manzanita' / 'test-output'))
OUT.mkdir(parents=True, exist_ok=True)


def exercise(page, label: str, font_scale: int = 100) -> None:
    errors=[]; outbound=[]
    page.on('pageerror', lambda exc: errors.append(f'pageerror: {exc}'))
    page.on('console', lambda msg: errors.append(f'console: {msg.text}') if msg.type == 'error' else None)
    parsed=urlparse(TARGET); origin=f'{parsed.scheme}://{parsed.netloc}'
    page.on('request', lambda req: outbound.append(req.url) if not req.url.startswith(origin) and not req.url.startswith('data:') and not req.url.startswith('blob:') else None)
    response=page.goto(TARGET, wait_until='networkidle', timeout=60000)
    assert response and response.status == 200
    if font_scale != 100:
        page.evaluate("scale => document.documentElement.style.fontSize = scale + '%'", font_scale)
    assert page.locator('html').get_attribute('data-release') == '1.6.0'
    assert page.locator('[data-aperture]').count() == 7
    assert page.locator('[data-overlay]').count() == 8
    assert page.locator('[data-role]').count() == 5
    assert page.locator('.estate-grid > article').count() == 6
    assets=[]
    for button in page.locator('[data-aperture]').all():
        button.click()
        page.wait_for_timeout(60)
        assert button.get_attribute('aria-pressed') == 'true'
        assets.append(page.locator('#sceneImage').get_attribute('src'))
        assert page.locator('#apertureTitle').text_content().strip()
        assert page.locator('#authorityBoundary').text_content().strip()
        assert page.locator('#sceneClass').text_content().strip()
    assert len(set(assets)) == 7, assets
    first=page.locator('[data-aperture="plant"]'); first.focus(); page.keyboard.press('End')
    assert page.locator(':focus').get_attribute('data-aperture') == 'stewardship'
    assert page.locator('[data-aperture="stewardship"]').get_attribute('aria-pressed') == 'true'
    before=page.locator('#roleAction').text_content(); page.locator('[data-role="planner"]').click(); after=page.locator('#roleAction').text_content(); assert before != after
    assert page.locator('#roleAcceptance').text_content().strip()
    assert page.locator('#roleHandoff').text_content().strip()
    role_url=parse_qs(urlparse(page.url).query); assert role_url['role'] == ['planner']
    overlay=page.locator('[data-overlay="water"]'); old=overlay.get_attribute('aria-pressed'); overlay.click(); assert overlay.get_attribute('aria-pressed') != old
    state=parse_qs(urlparse(page.url).query, keep_blank_values=True); assert 'aperture' in state and 'layers' in state
    page.evaluate("window.print=()=>document.documentElement.dataset.printed='yes'"); page.locator('#printSheet').click(); assert page.locator('html').get_attribute('data-printed') == 'yes'
    page.evaluate("URL.createObjectURL=()=>{document.documentElement.dataset.exported='yes';return 'blob:test'};URL.revokeObjectURL=()=>{};HTMLAnchorElement.prototype.click=()=>{}")
    page.locator('#exportState').click(); assert page.locator('html').get_attribute('data-exported') == 'yes'
    old_theme=page.locator('html').get_attribute('data-theme'); page.locator('#themeToggle').click(); assert page.locator('html').get_attribute('data-theme') != old_theme
    overflow=page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth'); assert overflow <= 1, overflow
    assert not outbound, outbound
    assert not errors, errors
    page.screenshot(path=str(OUT / f'{label}-full.png'), full_page=True)
    page.locator('.hero').screenshot(path=str(OUT / f'{label}-hero.png'))
    page.locator('#fabric').screenshot(path=str(OUT / f'{label}-fabric.png'))

server=None
if TARGET == LOCAL:
    server=subprocess.Popen([sys.executable,'-m','http.server','8765','--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(1)
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for label,width,height,scale in [('desktop-light',1440,1000,100),('tablet',1024,900,100),('mobile',390,844,100),('compact-200',320,720,200)]:
            context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
            exercise(context.new_page(),label,scale)
            context.close()
        browser.close()
finally:
    if server:
        server.terminate()
        with contextlib.suppress(Exception): server.wait(timeout=5)
print(f'Manzanita Works v1.6.0 browser contract: PASS ({TARGET})')
'''


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_assets()
    write_text(OUT / "index.html", INDEX)
    write_text(OUT / "style.css", STYLE)
    write_text(OUT / "app.js", APP)
    write_text(OUT / "theme-init.js", THEME)
    write_text(OUT / "README.md", README)
    write_text(OUT / "VISUAL_CONSTITUTION.md", CONSTITUTION)
    write_text(OUT / "tests" / "public_contract_test.py", STATIC_TEST)
    write_text(OUT / "tests" / "browser_test.py", BROWSER_TEST)

    receipt = {
        "schema": "manzanita-works/release-receipt@2",
        "release": RELEASE,
        "release_class": "bounded_public_photographic_convergence",
        "prepared_on": "2026-08-18",
        "public_route": "https://bigbirdreturns.github.io/axm-tools/manzanita/",
        "photographic_donor": {
            "release": PHOTO_RELEASE,
            "source_commit": PHOTO_COMMIT,
        },
        "predecessor": {
            "release": "1.4.1",
            "source_commit": PREDECESSOR_COMMIT,
            "route_tree": PREDECESSOR_TREE,
        },
        "admitted_successor_donors": {
            "seven_apertures": "f49421f26be443395f7bcc684a1ea932b5694c14",
            "street_glide": "b37a24859cf924ef71cf7f77300cfb1e30b31fb2",
            "eight_overlays": "8ca8f1bc1881f7cc89eff56a4b1cc25f546a26fc",
            "five_roles_fab": "4150caa3ecc2e4859adc5ab7b4a5e5932b23252f",
            "whole_experience": "0d91b30f5d5997d1649e3f1c0fb3093f3f577c27",
        },
        "authority": {
            "basis": "repository_owner_public_convergence_directive_2026-08-18",
            "successor_program_effect": "none",
            "external_campaign_effect": "none",
            "canonical_task_count_effect": "none",
        },
        "claim_boundary": "This public release converges retained visual and admitted operating donors into a bounded static projection. It does not release the complete manzanita-next successor, perform an external campaign, confer physical or private standing, or mutate canonical task counts.",
    }
    write_text(OUT / "RELEASE_RECEIPT.json", json.dumps(receipt, indent=2) + "\n")

    files: dict[str, Any] = {}
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "QUALIFICATION.json"):
        relative = path.relative_to(OUT).as_posix()
        payload = path.read_bytes()
        files[relative] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    qualification = {
        "schema": "manzanita-works/pages-qualification@6",
        "release": RELEASE,
        "release_class": "bounded_public_photographic_convergence",
        "visual_system": "photographic-place-fabric",
        "entrypoint": "manzanita/index.html",
        "public_route": "https://bigbirdreturns.github.io/axm-tools/manzanita/",
        "themes": ["light", "dark"],
        "files": files,
        "apertures": 7,
        "distinct_aperture_assets": 7,
        "overlays": 8,
        "operating_seats": 5,
        "instruments": 6,
        "shareable_url_state": True,
        "local_export": True,
        "print_save_sheet": True,
        "external_visual_dependencies": 0,
        "external_effect_adapters": 0,
        "photographic_donor_commit": PHOTO_COMMIT,
        "predecessor_release": {"release": "1.4.1", "source_commit": PREDECESSOR_COMMIT, "route_tree": PREDECESSOR_TREE},
        "authority_boundary": "photographic and derived context do not become survey, inspection, field finding, access, work, enforcement, coverage, or completed-remediation authority",
        "successor_program_effect": "none",
        "canonical_task_count_effect": "none",
    }
    write_text(OUT / "QUALIFICATION.json", json.dumps(qualification, indent=2) + "\n")
    print(json.dumps({"release": RELEASE, "route_files": len(files) + 1, "webp_assets": 7}, indent=2))


if __name__ == "__main__":
    build()
