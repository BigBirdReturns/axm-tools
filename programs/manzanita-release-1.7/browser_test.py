#!/usr/bin/env python3
"""Operate every admitted Manzanita v1.7.0 state and refusal in Chromium.

The campaign can serve a local site or operate an explicit URL. It verifies
exact asset-to-receipt binding, semantic feature identity, coordinate lock,
source failure, invalid-control refusal, five functional seats, keyboard
continuity, bounded export, responsive reflow, and zero unexpected requests.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageOps
from playwright.sync_api import Browser, Page, sync_playwright

RELEASE = "1.7.0"
VISUAL_SYSTEM = "semantic-source-adaptive-place-fabric"
SEMANTIC = {"access", "shade", "water"}
NON_GEOMETRIC = {"care", "heat", "air", "fire", "assistance"}
EXPECTED_RECEIPTS = {"access": 3, "shade": 5, "water": 2}
EXPECTED_FEATURES = {"access": 11, "shade": 11, "water": 10}
VIEWPORTS = {
    "desktop": {"width": 1600, "height": 1000},
    "tablet": {"width": 1024, "height": 900},
    "mobile": {"width": 390, "height": 844},
    "compact": {"width": 320, "height": 720},
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@contextlib.contextmanager
def serve(directory: Path) -> Iterator[str]:
    class BoundHandler(QuietHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def horizontal_overflow(page: Page) -> float:
    return float(page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth"))


def minimum_visible_target_height(page: Page) -> float:
    return float(page.evaluate(
        """
        () => {
          const rows = [...document.querySelectorAll('button, a[href], [role="button"], [role="tab"]')]
            .filter((node) => {
              const style = getComputedStyle(node);
              const box = node.getBoundingClientRect();
              return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
            })
            .map((node) => node.getBoundingClientRect().height);
          return rows.length ? Math.min(...rows) : 0;
        }
        """
    ))


def snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const data = window.__MANZANITA_V4__ || window.__MANZANITA_V5__ || (() => {
            const node = document.querySelector('script[type="application/json"]');
            return node ? JSON.parse(node.textContent) : {};
          })();
          const state = window.__MZ_V4_STATE__ || window.__MZ_V5_STATE__ || {};
          const visible = (node) => {
            const style = getComputedStyle(node);
            const box = node.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && box.width >= 0 && box.height >= 0;
          };
          const featureNodes = [...document.querySelectorAll('[data-feature-id]')].filter(visible);
          const features = featureNodes.map((node) => ({
            id: node.getAttribute('data-feature-id'),
            cls: node.getAttribute('data-feature-class'),
            tag: node.tagName.toLowerCase(),
            d: node.getAttribute('d'),
            points: node.getAttribute('points'),
          }));
          const uniqueFeatures = [...new Map(features.map((row) => [row.id, row])).values()];
          const scene = document.querySelector('#sceneImage');
          const href = scene?.getAttribute('href') || scene?.getAttribute('xlink:href') || scene?.getAttribute('src') || '';
          const geometryRoot = document.querySelector('#registeredGeometry') || document.querySelector('[data-semantic-geometry-root]') || featureNodes[0]?.closest('svg');
          const imageRect = scene?.getBoundingClientRect();
          const geometryRect = geometryRoot?.ownerSVGElement?.getBoundingClientRect() || geometryRoot?.getBoundingClientRect();
          const active = (selector, attribute) => document.querySelector(`${selector}[${attribute}="true"]`)?.dataset || null;
          const activeAperture = document.querySelector('[data-aperture][aria-selected="true"]')?.dataset.aperture || state.aperture;
          const activeInstrument = document.querySelector('[data-instrument][aria-pressed="true"]')?.dataset.instrument || state.instrument;
          const activeMode = document.querySelector('[data-mode][aria-pressed="true"]')?.dataset.mode || state.mode;
          const activeSeat = document.querySelector('[data-seat][aria-pressed="true"]')?.dataset.seat || state.seat;
          const activeDetail = document.querySelector('[data-detail][aria-pressed="true"]')?.dataset.detail || state.detail;
          const assetId = state.asset_id || Object.values(data.assets || {}).find((asset) => href.endsWith(asset.path) || href.includes(asset.path))?.asset_id || null;
          const instrument = activeInstrument;
          const registration = assetId && instrument ? data.registrations?.[`${assetId}:${instrument}`] || null : null;
          const texts = {};
          for (const id of ['seatQuestion','seatEvidence','seatAction','seatAcceptance','seatAuthority','seatHandoff','detailTitle','detailBody','objectTitle','evidenceText','actionText','authorityText','registrationState','sourceState']) {
            const node = document.getElementById(id);
            if (node) texts[id] = node.textContent.trim();
          }
          return {
            release: data.release,
            visualSystem: data.visual_system,
            active: {aperture: activeAperture, instrument: activeInstrument, mode: activeMode, seat: activeSeat, detail: activeDetail},
            state,
            assetId,
            href,
            registration,
            features: uniqueFeatures,
            featureSignature: uniqueFeatures.map((row) => `${row.id}:${row.cls}:${row.d || row.points || ''}`).join('|'),
            imageRect: imageRect ? {x:imageRect.x,y:imageRect.y,width:imageRect.width,height:imageRect.height} : null,
            geometryRect: geometryRect ? {x:geometryRect.x,y:geometryRect.y,width:geometryRect.width,height:geometryRect.height} : null,
            texts,
            counts: {
              apertures: Object.keys(data.apertures || {}).length,
              instruments: Object.keys(data.instruments || {}).length,
              modes: Object.keys(data.sourceModes || {}).length,
              seats: Object.keys(data.seats || {}).length,
              assets: Object.keys(data.assets || {}).length,
              registrations: Object.keys(data.registrations || {}).length,
            },
          };
        }
        """
    )


def runtime_data(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => JSON.parse(JSON.stringify(window.__MANZANITA_V4__ || window.__MANZANITA_V5__ || JSON.parse(document.querySelector('script[type="application/json"]').textContent)))
        """
    )


def click(page: Page, selector: str) -> None:
    locator = page.locator(selector)
    require(locator.count() == 1, f"Expected one control for {selector}, found {locator.count()}")
    require(not locator.is_disabled(), f"Attempted to click disabled control {selector}")
    locator.click()
    page.wait_for_timeout(20)


def set_state(page: Page, aperture: str, instrument: str, mode: str, seat: str = "resident") -> None:
    click(page, f'[data-aperture="{aperture}"]')
    click(page, f'[data-instrument="{instrument}"]')
    click(page, f'[data-mode="{mode}"]')
    click(page, f'[data-seat="{seat}"]')


def assert_coordinate_lock(row: dict[str, Any], label: str) -> None:
    image = row["imageRect"]
    geometry = row["geometryRect"]
    require(image is not None and geometry is not None, f"{label}: image or geometry frame is absent")
    for key in ("x", "y", "width", "height"):
        require(abs(float(image[key]) - float(geometry[key])) <= 1.5, f"{label}: image and geometry frame diverged on {key}: {image} vs {geometry}")


def assert_semantics(row: dict[str, Any], label: str) -> tuple[str | None, str]:
    instrument = row["active"]["instrument"]
    mode = row["active"]["mode"]
    registration = row["registration"]
    feature_ids = {item["id"] for item in row["features"]}
    if mode in {"map", "held"} or instrument in NON_GEOMETRIC or registration is None:
        require(not row["features"], f"{label}: local image geometry rendered without an admissible semantic receipt")
        return None, ""
    require(instrument in SEMANTIC, f"{label}: unknown geometric instrument {instrument}")
    expected = {item["feature_id"] for item in registration["features"]}
    require(feature_ids == expected, f"{label}: visible semantic features do not match exact receipt: {feature_ids} vs {expected}")
    require(len(row["features"]) == registration["feature_count"], f"{label}: visible feature count drifted")
    require(registration["asset_id"] == row["assetId"], f"{label}: registration borrowed another asset identity")
    require(registration["instrument"] == instrument, f"{label}: registration borrowed another instrument identity")
    assert_coordinate_lock(row, label)
    return f"{registration['asset_id']}:{instrument}", row["featureSignature"]


def invalid_refusals(page: Page) -> int:
    refused = 0
    for selector in ("[data-aperture]", "[data-instrument]", "[data-mode]", "[data-seat]", "[data-detail]", "[data-provider-scene]"):
        for index in range(page.locator(selector).count()):
            control = page.locator(selector).nth(index)
            if not control.is_disabled() and control.get_attribute("aria-disabled") != "true":
                continue
            before = snapshot(page)["active"]
            control.evaluate("node => node.click()")
            page.wait_for_timeout(10)
            after = snapshot(page)["active"]
            require(before == after, f"Disabled control mutated state: {selector}[{index}] {before} -> {after}")
            refused += 1
    return refused


def exercise_matrix(page: Page, data: dict[str, Any]) -> dict[str, Any]:
    valid_states = 0
    invalid_controls = 0
    receipt_signatures: dict[str, set[str]] = {key: set() for key in SEMANTIC}
    registration_keys: set[str] = set()
    state_rows: list[dict[str, Any]] = []
    apertures = list(data["apertures"])
    instruments = data["instruments"]
    modes = data["sourceModes"]

    for aperture in apertures:
        click(page, f'[data-aperture="{aperture}"]')
        invalid_controls += invalid_refusals(page)
        supported_instruments = [key for key, value in instruments.items() if aperture in value.get("apertures", [])]
        supported_modes = [key for key, value in modes.items() if aperture in value.get("apertures", [])]
        for instrument in supported_instruments:
            click(page, f'[data-instrument="{instrument}"]')
            for mode in supported_modes:
                click(page, f'[data-mode="{mode}"]')
                provider_scenes = page.locator('[data-provider-scene]:not([disabled]):not([aria-disabled="true"])')
                scene_indices = range(provider_scenes.count()) if mode == "provider" and provider_scenes.count() else (None,)
                for scene_index in scene_indices:
                    if scene_index is not None:
                        provider_scenes.nth(scene_index).click()
                        page.wait_for_timeout(20)
                    row = snapshot(page)
                    label = f"{aperture}/{instrument}/{mode}/{scene_index if scene_index is not None else '-'}"
                    require(row["active"]["aperture"] == aperture, f"{label}: aperture drifted")
                    require(row["active"]["instrument"] == instrument, f"{label}: instrument drifted")
                    require(row["active"]["mode"] == mode, f"{label}: source mode drifted")
                    key, signature = assert_semantics(row, label)
                    if key:
                        registration_keys.add(key)
                        receipt_signatures[instrument].add(signature)
                    valid_states += 1
                    state_rows.append({
                        "aperture": aperture,
                        "instrument": instrument,
                        "mode": mode,
                        "provider_scene_index": scene_index,
                        "asset_id": row["assetId"],
                        "registration_key": key,
                        "feature_count": len(row["features"]),
                    })

    require(valid_states == 117, f"Expected 117 admitted semantic states, exercised {valid_states}")
    require(invalid_controls >= 28, f"Expected at least 28 invalid controls to refuse, observed {invalid_controls}")
    expected_registration_keys = set(data["registrations"])
    require(registration_keys == expected_registration_keys, f"Not every exact semantic receipt rendered: missing={sorted(expected_registration_keys-registration_keys)} extra={sorted(registration_keys-expected_registration_keys)}")
    for instrument, expected in EXPECTED_RECEIPTS.items():
        require(len(receipt_signatures[instrument]) == expected, f"{instrument} did not render {expected} distinct exact-asset geometries")
    return {
        "valid_states": valid_states,
        "invalid_controls_refused": invalid_controls,
        "rendered_registration_keys": sorted(registration_keys),
        "distinct_geometry_signatures": {key: len(value) for key, value in sorted(receipt_signatures.items())},
        "states": state_rows,
    }


def exercise_seats_details_keyboard_export(page: Page, output: Path, data: dict[str, Any]) -> dict[str, Any]:
    set_state(page, "street", "access", "reference", "resident")
    seat_signatures: dict[str, str] = {}
    for seat in data["seats"]:
        click(page, f'[data-seat="{seat}"]')
        row = snapshot(page)
        require(row["active"]["seat"] == seat, f"Seat did not activate: {seat}")
        signature = json.dumps(row["texts"], sort_keys=True)
        require(signature.strip("{}") != "", f"Seat {seat} exposes no operating content")
        seat_signatures[seat] = signature
    require(len(set(seat_signatures.values())) == len(data["seats"]), "Functional seats do not produce distinct operating records")

    detail_states: dict[str, str] = {}
    for detail in data.get("details", {}):
        locator = page.locator(f'[data-detail="{detail}"]')
        if locator.count() != 1 or locator.is_disabled():
            continue
        locator.click()
        page.wait_for_timeout(15)
        row = snapshot(page)
        require(row["active"]["detail"] == detail, f"Detail did not activate: {detail}")
        detail_states[detail] = json.dumps(row["texts"], sort_keys=True)
    if detail_states:
        require(len(set(detail_states.values())) == len(detail_states), "Detail controls do not change the represented record")

    household = page.locator('[data-aperture="household"]')
    household.focus()
    household.press("ArrowRight")
    require(snapshot(page)["active"]["aperture"] == "property", "Aperture ArrowRight failed")
    require(page.locator('[data-aperture="property"]').evaluate("node => node === document.activeElement"), "Focus did not follow aperture ArrowRight")
    page.keyboard.press("End")
    require(snapshot(page)["active"]["aperture"] == "stewardship", "Aperture End failed")
    page.keyboard.press("Home")
    require(snapshot(page)["active"]["aperture"] == "plant", "Aperture Home failed")

    set_state(page, "street", "access", "reference", "successor")
    row = snapshot(page)
    export_control = page.locator("#exportBtn, #exportButton, [data-export]").first
    require(export_control.count() == 1 and export_control.is_visible(), "Bounded export control is unavailable")
    with page.expect_download() as download_info:
        export_control.click()
    target = output / "manzanita-v1.7.0-export.json"
    download_info.value.save_as(target)
    exported = json.loads(target.read_text(encoding="utf-8"))
    require(exported.get("release") == RELEASE, "Export release identity drifted")
    exported_text = json.dumps(exported)
    require(row["assetId"] in exported_text, "Export omitted exact asset identity")
    require(row["registration"]["receipt_sha256"] in exported_text, "Export omitted semantic receipt identity")
    require("successor" in exported_text, "Export omitted functional-seat identity")
    require(exported.get("public_effect", exported.get("effects", {}).get("public")) in {"none", None}, "Export grants a public effect")
    require("private" in exported_text.lower() and "prohibit" in exported_text.lower(), "Export lost the private-record boundary")
    return {
        "seat_count": len(seat_signatures),
        "seat_signatures_distinct": len(set(seat_signatures.values())),
        "detail_count": len(detail_states),
        "export": {"path": target.name, "bytes": target.stat().st_size, "sha256": sha256(target)},
    }


def capture_states(browser: Browser, base_url: str, output: Path, errors: dict[str, list[str]]) -> list[dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=True)
    states = [
        ("desktop-access-reference", "street", "access", "reference", "resident", "desktop", "dark"),
        ("desktop-access-provider", "street", "access", "provider", "crew_steward", "desktop", "dark"),
        ("desktop-shade-property", "property", "shade", "reference", "planner_program", "desktop", "light"),
        ("desktop-water-property", "property", "water", "reference", "crew_steward", "desktop", "dark"),
        ("tablet-fire-region-map", "region", "fire", "map", "planner_program", "tablet", "dark"),
        ("mobile-assistance-stewardship", "stewardship", "assistance", "reference", "successor", "mobile", "dark"),
        ("mobile-held-street", "street", "access", "held", "resident", "mobile", "light"),
    ]
    captures: list[dict[str, Any]] = []
    for name, aperture, instrument, mode, seat, viewport_id, theme in states:
        context = browser.new_context(viewport=VIEWPORTS[viewport_id], color_scheme=theme, reduced_motion="reduce" if viewport_id == "mobile" else "no-preference")
        page = context.new_page()
        page.on("console", lambda message: errors["console"].append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors["page"].append(str(error)))
        page.goto(base_url, wait_until="networkidle")
        set_state(page, aperture, instrument, mode, seat)
        if mode == "provider":
            provider = page.locator('[data-provider-scene]:not([disabled]):not([aria-disabled="true"])')
            if provider.count() > 1:
                provider.nth(1).click()
                page.wait_for_timeout(20)
        overflow = horizontal_overflow(page)
        require(overflow <= 1.5, f"Horizontal overflow in capture {name}: {overflow}")
        floor = minimum_visible_target_height(page)
        require(floor >= 43.5, f"Visible control floor below 44 CSS px in {name}: {floor}")
        row = snapshot(page)
        assert_semantics(row, name)
        path = output / f"{name}.png"
        page.screenshot(path=str(path), full_page=False)
        captures.append({
            "name": name,
            "viewport": viewport_id,
            "theme": theme,
            "state": row["active"],
            "asset_id": row["assetId"],
            "registration_id": row["registration"]["receipt_sha256"] if row["registration"] else None,
            "feature_count": len(row["features"]),
            "horizontal_overflow": overflow,
            "minimum_visible_target_height": floor,
            "screenshot": path.name,
            "screenshot_sha256": sha256(path),
        })
        context.close()

    contact = output / "contact-sheet.jpg"
    thumb_w, thumb_h, label_h = 800, 500, 68
    cols = 2
    rows = (len(captures) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "#111510")
    draw = ImageDraw.Draw(sheet)
    for index, capture in enumerate(captures):
        with Image.open(output / capture["screenshot"]) as source:
            image = ImageOps.fit(source.convert("RGB"), (thumb_w, thumb_h), method=Image.Resampling.LANCZOS)
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + label_h)
        sheet.paste(image, (x, y))
        draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label_h), fill="#efe9da")
        label = f"{capture['name'].upper()} · FEATURES {capture['feature_count']}"
        draw.text((x + 16, y + thumb_h + 22), label, fill="#151713")
    sheet.save(contact, quality=94)
    return captures


def run(base_url: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(base_url)
    allowed_origin = f"{parsed.scheme}://{parsed.netloc}"
    errors: dict[str, list[str]] = {"console": [], "page": [], "external": [], "failed": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=VIEWPORTS["desktop"], color_scheme="dark", accept_downloads=True)
        page = context.new_page()
        page.on("console", lambda message: errors["console"].append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors["page"].append(str(error)))
        page.on("request", lambda request: errors["external"].append(request.url) if not request.url.startswith(allowed_origin) else None)
        page.on("requestfailed", lambda request: errors["failed"].append(f"{request.url}: {request.failure}"))
        page.goto(base_url, wait_until="networkidle")
        require(page.locator(f'html[data-release="{RELEASE}"][data-visual-system="{VISUAL_SYSTEM}"]').count() == 1, "Public release markers are absent")
        data = runtime_data(page)
        initial = snapshot(page)
        require(initial["release"] == RELEASE, "Browser runtime release drifted")
        require(initial["visualSystem"] == VISUAL_SYSTEM, "Browser runtime visual system drifted")
        require(initial["counts"] == {"apertures": 7, "instruments": 8, "modes": 5, "seats": 5, "assets": 10, "registrations": 10}, f"Runtime counts drifted: {initial['counts']}")
        matrix = exercise_matrix(page, data)
        interactions = exercise_seats_details_keyboard_export(page, output, data)

        page.set_viewport_size(VIEWPORTS["compact"])
        page.evaluate("document.documentElement.style.fontSize = '200%'")
        page.wait_for_timeout(100)
        reflow_overflow = horizontal_overflow(page)
        require(reflow_overflow <= 2, f"200-percent text reflow introduced horizontal overflow: {reflow_overflow}")
        require(minimum_visible_target_height(page) >= 43.5, "200-percent text reflow reduced a visible target below 44 CSS px")
        page.evaluate("document.documentElement.style.fontSize = ''")
        context.close()

        captures = capture_states(browser, base_url, output, errors)
        browser.close()

    require(not errors["console"], f"Console errors: {errors['console']}")
    require(not errors["page"], f"Page errors: {errors['page']}")
    require(not errors["external"], f"Unexpected external requests: {errors['external']}")
    require(not errors["failed"], f"Failed resources: {errors['failed']}")

    report = {
        "schema": "manzanita-works/semantic-public-browser-campaign@1",
        "result": "PASS",
        "release": RELEASE,
        "visual_system": VISUAL_SYSTEM,
        "url": base_url,
        "matrix": matrix,
        "interactions": interactions,
        "reflow_200_percent": {"horizontal_overflow": reflow_overflow},
        "captures": captures,
        "maximum_horizontal_overflow": max([reflow_overflow] + [float(row["horizontal_overflow"]) for row in captures]),
        "minimum_visible_target_height": min(float(row["minimum_visible_target_height"]) for row in captures),
        "console_errors": errors["console"],
        "page_errors": errors["page"],
        "external_requests": errors["external"],
        "failed_requests": errors["failed"],
        "authority": {"external_effect": "none", "field_authority": "none", "adverse_action_authority": "none", "canonical_task_count_effect": "none"},
    }
    report_path = output / "BROWSER_CAMPAIGN.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(bool(args.site) ^ bool(args.url), "Supply exactly one of --site or --url")
    return args


def main() -> None:
    args = parse_args()
    if args.url:
        report = run(args.url, args.output)
    else:
        require(args.site.is_dir(), f"Site directory does not exist: {args.site}")
        with serve(args.site.resolve()) as url:
            report = run(url, args.output)
    print(json.dumps({
        "result": report["result"],
        "release": report["release"],
        "valid_states": report["matrix"]["valid_states"],
        "invalid_controls_refused": report["matrix"]["invalid_controls_refused"],
        "registration_keys": len(report["matrix"]["rendered_registration_keys"]),
        "captures": len(report["captures"]),
        "maximum_horizontal_overflow": report["maximum_horizontal_overflow"],
        "minimum_visible_target_height": report["minimum_visible_target_height"],
    }, indent=2))


if __name__ == "__main__":
    main()
