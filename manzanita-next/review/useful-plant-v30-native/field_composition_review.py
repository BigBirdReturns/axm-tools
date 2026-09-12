#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
ROUTE = "/manzanita-next/review/useful-plant-v30-native/field-composition.html"
MODES = ("recognize", "place", "tend", "observe", "use", "return")
SEATS = ("household", "grower", "neighbor", "ecologist", "responder")
ZONES = ("identity", "placement", "care", "yield", "return")
STOPS = ("pause", "private", "substitution")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = "") -> None:
    checks.append({"name": name, "pass": bool(passed), "detail": detail})


def visible_box(page: Page, selector: str) -> dict[str, float] | None:
    locator = page.locator(selector)
    if locator.count() != 1 or not locator.is_visible():
        return None
    return locator.bounding_box()


def attach_observers(
    page: Page,
    local_origin: str,
    external_requests: list[str],
    console_errors: list[str],
) -> None:
    def on_request(request: Any) -> None:
        parsed = urlparse(request.url)
        request_origin = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme in {"data", "blob"}:
            return
        if request_origin != local_origin:
            external_requests.append(request.url)

    page.on("request", on_request)
    page.on(
        "console",
        lambda message: console_errors.append(f"console:{message.text}")
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: console_errors.append(f"page:{error}"))


def wait_ready(page: Page) -> None:
    page.wait_for_selector("html[data-ready='true']", state="attached")
    page.locator(".field-photo").evaluate(
        "img => img.complete && img.naturalWidth ? true : new Promise(resolve => { img.addEventListener('load', () => resolve(true), {once:true}); img.addEventListener('error', () => resolve(false), {once:true}); })"
    )


def screenshot(page: Page, output_dir: Path, name: str) -> dict[str, Any]:
    path = output_dir / "screenshots" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    return {
        "name": path.stem,
        "path": str(path.relative_to(output_dir)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def desktop_campaign(
    browser: Browser,
    url: str,
    origin: str,
    output_dir: Path,
    checks: list[dict[str, Any]],
    screenshots: list[dict[str, Any]],
    external_requests: list[str],
    console_errors: list[str],
) -> None:
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        device_scale_factor=1,
        reduced_motion="reduce",
    )
    page = context.new_page()
    attach_observers(page, origin, external_requests, console_errors)
    response = page.goto(url, wait_until="networkidle")
    add_check(checks, "field route HTTP 200", bool(response and response.status == 200), response.status if response else None)
    wait_ready(page)

    natural = page.locator(".field-photo").evaluate(
        "img => ({complete: img.complete, width: img.naturalWidth, height: img.naturalHeight})"
    )
    add_check(
        checks,
        "photographic donor decoded at declared dimensions",
        natural == {"complete": True, "width": 1600, "height": 1000},
        natural,
    )

    photo = visible_box(page, ".field-photo")
    add_check(checks, "desktop photo present", photo is not None, photo)
    if photo:
        area_ratio = (photo["width"] * photo["height"]) / (1600 * 1000)
        add_check(checks, "photo begins at viewport top", photo["y"] <= 1 and photo["x"] <= 1, photo)
        add_check(checks, "photo spans desktop width", photo["width"] >= 1598, photo)
        add_check(checks, "photo spans desktop height", photo["height"] >= 998, photo)
        add_check(checks, "photo owns first viewport area", area_ratio >= 0.70, area_ratio)

    expressed = page.locator(".utility-button:visible, .primary-action:visible, .household-control:visible").count()
    add_check(checks, "no more than three persistent expressed controls", expressed <= 3, expressed)

    initial_outlines = page.evaluate(
        """() => [...document.querySelectorAll('.zone')].filter(zone => Number.parseFloat(getComputedStyle(zone, '::before').opacity) > 0.01).length"""
    )
    add_check(checks, "registration outlines hidden before interaction", initial_outlines == 0, initial_outlines)

    detail = visible_box(page, ".field-detail")
    if detail:
        detail_ratio = (detail["width"] * detail["height"]) / (1600 * 1000)
        add_check(checks, "persistent detail overlay below area ceiling", detail_ratio <= 0.25, detail_ratio)
    else:
        add_check(checks, "persistent detail overlay present", False, detail)

    buttons = page.locator("button")
    button_names = buttons.evaluate_all(
        """items => items.map(item => ({text: item.innerText.trim(), aria: item.getAttribute('aria-label') || ''}))"""
    )
    unnamed = [item for item in button_names if not item["text"] and not item["aria"]]
    add_check(checks, "all buttons have accessible names", not unnamed, {"total": len(button_names), "unnamed": unnamed})

    acceptance_controls = buttons.evaluate_all(
        """items => items.filter(item => /(^|\\s)(accept|approve|release|merge)(\\s|$)/i.test((item.innerText + ' ' + (item.getAttribute('aria-label') || '')).trim())).map(item => item.innerText.trim() || item.getAttribute('aria-label'))"""
    )
    add_check(checks, "no acceptance, merge, or release control embedded", not acceptance_controls, acceptance_controls)

    state_contract = page.evaluate("() => window.__USEFUL_PLANT_FIELD__")
    add_check(
        checks,
        "field state contract denies authority",
        state_contract.get("operatorVisualAcceptance") == "ABSENT"
        and state_contract.get("mergeAuthorized") is False
        and state_contract.get("releaseAuthorized") is False
        and state_contract.get("publicRouteEffect") == "none"
        and state_contract.get("pagesDeploymentEffect") == "none"
        and state_contract.get("externalEffect") == "none",
        state_contract,
    )

    screenshots.append(screenshot(page, output_dir, "01-field-desktop-recognize.png"))

    page.locator("#field-menu-toggle").click()
    menu = visible_box(page, "#field-menu")
    add_check(checks, "field menu opens on demand", menu is not None, menu)
    if menu:
        menu_ratio = (menu["width"] * menu["height"]) / (1600 * 1000)
        add_check(checks, "desktop field menu retains most of place", menu_ratio <= 0.25, menu_ratio)
    screenshots.append(screenshot(page, output_dir, "02-field-desktop-menu.png"))

    for mode in MODES:
        page.locator(f"[data-mode='{mode}']").click()
        add_check(checks, f"mode {mode} changes field state", page.locator("body").get_attribute("data-mode") == mode)
        add_check(checks, f"mode {mode} encoded in URL", f"mode={mode}" in page.url, page.url)
        if mode != MODES[-1]:
            page.locator("#field-menu-toggle").click()

    page.locator("#field-menu-toggle").click()
    for seat in SEATS:
        page.locator(f"[data-seat='{seat}']").click()
        add_check(checks, f"seat {seat} changes field authority", page.locator("body").get_attribute("data-seat") == seat)
        add_check(checks, f"seat {seat} encoded in URL", f"seat={seat}" in page.url, page.url)

    page.locator("[data-close='field-menu']").click()

    for zone in ZONES:
        page.locator(f"[data-zone='{zone}']").click(force=True)
        add_check(checks, f"zone {zone} changes place state", page.locator("body").get_attribute("data-zone") == zone)
        add_check(checks, f"zone {zone} reveals one local mask", page.locator(f"[data-zone='{zone}']").get_attribute("data-revealed") == "true")
        revealed = page.evaluate(
            """() => [...document.querySelectorAll('.zone')].filter(zone => Number.parseFloat(getComputedStyle(zone, '::before').opacity) > 0.01).length"""
        )
        add_check(checks, f"zone {zone} keeps one revealed outline", revealed == 1, revealed)

    screenshots.append(screenshot(page, output_dir, "03-field-desktop-zone.png"))

    page.locator("#household-toggle").click()
    for stop in STOPS:
        page.locator(f"[data-stop='{stop}']").click()
        add_check(checks, f"household stop {stop} activates locally", page.locator(f"[data-stop='{stop}']").get_attribute("aria-pressed") == "true")
        dataset_name = {
            "pause": "data-stop-pause",
            "private": "data-stop-private",
            "substitution": "data-stop-substitution",
        }[stop]
        add_check(checks, f"household stop {stop} reflected on root", page.locator("body").get_attribute(dataset_name) == "true")

    screenshots.append(screenshot(page, output_dir, "04-field-desktop-household-stop.png"))

    page.reload(wait_until="networkidle")
    wait_ready(page)
    add_check(checks, "mode survives reload", page.locator("body").get_attribute("data-mode") == "return")
    add_check(checks, "seat survives reload", page.locator("body").get_attribute("data-seat") == "responder")
    add_check(checks, "zone survives reload", page.locator("body").get_attribute("data-zone") == "return")
    for stop in STOPS:
        dataset_name = {
            "pause": "data-stop-pause",
            "private": "data-stop-private",
            "substitution": "data-stop-substitution",
        }[stop]
        add_check(checks, f"household stop {stop} survives reload", page.locator("body").get_attribute(dataset_name) == "true")

    page.keyboard.press("Escape")
    add_check(checks, "Escape leaves contextual panels closed", page.locator("#field-menu").is_hidden() and page.locator("#household-panel").is_hidden())
    context.close()


def mobile_campaign(
    browser: Browser,
    url: str,
    origin: str,
    output_dir: Path,
    checks: list[dict[str, Any]],
    screenshots: list[dict[str, Any]],
    external_requests: list[str],
    console_errors: list[str],
) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=1,
        is_mobile=True,
        reduced_motion="reduce",
    )
    page = context.new_page()
    attach_observers(page, origin, external_requests, console_errors)
    page.goto(url, wait_until="networkidle")
    wait_ready(page)

    overflow = page.evaluate("() => ({innerWidth, scrollWidth: document.documentElement.scrollWidth})")
    add_check(checks, "390px field has no horizontal overflow", overflow["scrollWidth"] <= overflow["innerWidth"], overflow)

    photo = visible_box(page, ".field-photo")
    add_check(checks, "mobile photo present", photo is not None, photo)
    if photo:
        add_check(checks, "mobile photo owns at least 55 percent of viewport height", photo["height"] / 844 >= 0.55, photo["height"] / 844)

    detail = visible_box(page, ".field-detail")
    if detail:
        ratio = (detail["width"] * detail["height"]) / (390 * 844)
        add_check(checks, "mobile persistent overlay below area ceiling", ratio <= 0.25, ratio)

    expressed = page.locator(".utility-button:visible, .primary-action:visible, .household-control:visible").count()
    add_check(checks, "mobile retains no more than three persistent expressed controls", expressed <= 3, expressed)
    add_check(checks, "mobile primary action reachable", page.locator("#next-action").is_visible())
    add_check(checks, "mobile household control reachable", page.locator("#household-toggle").is_visible())
    screenshots.append(screenshot(page, output_dir, "05-field-mobile-390.png"))
    context.close()


def text_resize_campaign(
    browser: Browser,
    url: str,
    origin: str,
    output_dir: Path,
    checks: list[dict[str, Any]],
    screenshots: list[dict[str, Any]],
    external_requests: list[str],
    console_errors: list[str],
) -> None:
    context = browser.new_context(viewport={"width": 700, "height": 900}, device_scale_factor=1, reduced_motion="reduce")
    page = context.new_page()
    attach_observers(page, origin, external_requests, console_errors)
    page.goto(url, wait_until="networkidle")
    wait_ready(page)
    page.evaluate("() => { document.documentElement.style.fontSize = '200%'; }")
    page.wait_for_timeout(200)
    overflow = page.evaluate("() => ({innerWidth, scrollWidth: document.documentElement.scrollWidth})")
    add_check(checks, "200 percent text has no horizontal overflow", overflow["scrollWidth"] <= overflow["innerWidth"], overflow)
    add_check(checks, "200 percent primary action remains reachable", page.locator("#next-action").is_visible())
    add_check(checks, "200 percent household control remains reachable", page.locator("#household-toggle").is_visible())
    screenshots.append(screenshot(page, output_dir, "06-field-text-200-percent.png"))
    context.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    handler = functools.partial(QuietHandler, directory=str(REPO_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    url = f"{origin}{ROUTE}"

    checks: list[dict[str, Any]] = []
    screenshots: list[dict[str, Any]] = []
    external_requests: list[str] = []
    console_errors: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                desktop_campaign(browser, url, origin, args.output, checks, screenshots, external_requests, console_errors)
                mobile_campaign(browser, url, origin, args.output, checks, screenshots, external_requests, console_errors)
                text_resize_campaign(browser, url, origin, args.output, checks, screenshots, external_requests, console_errors)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    add_check(checks, "no external network requests", not external_requests, sorted(set(external_requests)))
    add_check(checks, "no console or page errors", not console_errors, console_errors)

    passed = sum(1 for check in checks if check["pass"])
    result = "PASS" if passed == len(checks) else "FAIL"
    receipt = {
        "schema": "manzanita/useful-plant-v30-field-composition-browser-review@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "screenshots": screenshots,
        "external_requests": sorted(set(external_requests)),
        "console_errors": console_errors,
        "operator_visual_acceptance": "ABSENT",
        "merge_authorized": False,
        "release_authorized": False,
        "public_route_effect": "none",
        "pages_deployment_effect": "none",
        "external_effect": "none",
    }
    receipt_path = args.output / "FIELD_COMPOSITION_BROWSER_REVIEW_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": result, "checks_passed": passed, "checks_total": len(checks)}, indent=2))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
