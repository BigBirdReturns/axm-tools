#!/usr/bin/env python3
"""Exercise the Forkline Field specimen across state, viewport, theme, and input modes."""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except ImportError as exc:  # pragma: no cover - explicit workflow failure
    raise SystemExit(
        "Playwright is required. Install it with `python -m pip install playwright` "
        "and `python -m playwright install chromium`."
    ) from exc

VIEWPORTS = {
    "desktop": {"width": 1600, "height": 1000},
    "laptop": {"width": 1024, "height": 900},
    "mobile": {"width": 390, "height": 844},
    "compact": {"width": 320, "height": 720},
}
THEMES = ("light", "dark")
APERTURES = ("plant", "household", "street", "region")
OVERLAYS = ("habitat", "heat", "water", "fire")
ACTORS = ("resident", "steward", "planner")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def local_server(root: Path) -> Iterator[str]:
    handler = lambda *args, **kwargs: QuietHandler(  # noqa: E731
        *args,
        directory=str(root),
        **kwargs,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/index.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def create_context(
    browser: Browser,
    viewport: dict[str, int],
    *,
    color_scheme: str = "light",
    reduced_motion: str = "no-preference",
) -> BrowserContext:
    return browser.new_context(
        viewport=viewport,
        color_scheme=color_scheme,
        reduced_motion=reduced_motion,
        locale="en-US",
        timezone_id="America/Los_Angeles",
        device_scale_factor=1,
    )


def install_observers(page: Page, base_url: str) -> dict[str, list[str]]:
    observations: dict[str, list[str]] = {
        "console_errors": [],
        "page_errors": [],
        "external_requests": [],
        "failed_requests": [],
    }
    expected = urlparse(base_url)

    def on_console(message: Any) -> None:
        if message.type == "error":
            observations["console_errors"].append(message.text)

    def on_request(request: Any) -> None:
        parsed = urlparse(request.url)
        if parsed.scheme in {"data", "blob", "about"}:
            return
        if parsed.scheme not in {"http", "https"}:
            observations["external_requests"].append(request.url)
            return
        if parsed.hostname != expected.hostname or parsed.port != expected.port:
            observations["external_requests"].append(request.url)

    def on_failed(request: Any) -> None:
        observations["failed_requests"].append(
            f"{request.method} {request.url}: {request.failure}"
        )

    page.on("console", on_console)
    page.on("pageerror", lambda error: observations["page_errors"].append(str(error)))
    page.on("request", on_request)
    page.on("requestfailed", on_failed)
    return observations


def assert_no_overflow(page: Page, label: str) -> dict[str, float]:
    metrics = page.evaluate(
        """
        () => ({
          documentScrollWidth: document.documentElement.scrollWidth,
          documentClientWidth: document.documentElement.clientWidth,
          bodyScrollWidth: document.body.scrollWidth,
          bodyClientWidth: document.body.clientWidth,
        })
        """
    )
    if metrics["documentScrollWidth"] > metrics["documentClientWidth"] + 1:
        raise AssertionError(f"{label} has document horizontal overflow: {metrics}")
    if metrics["bodyScrollWidth"] > metrics["bodyClientWidth"] + 1:
        raise AssertionError(f"{label} has body horizontal overflow: {metrics}")
    return metrics


def assert_visible(locator: Any, label: str) -> None:
    if not locator.is_visible():
        raise AssertionError(f"Expected visible object: {label}")
    box = locator.bounding_box()
    if not box or box["width"] <= 0 or box["height"] <= 0:
        raise AssertionError(f"Expected positive geometry for {label}: {box}")


def body_text(page: Page) -> str:
    return "\n".join(
        line.strip()
        for line in page.locator("body").inner_text().splitlines()
        if line.strip()
    )


def theme_capture(
    page: Page,
    out_dir: Path,
    viewport_name: str,
    theme: str,
) -> dict[str, Any]:
    button = page.locator(f'[data-theme-choice="{theme}"]')
    button.click()
    page.wait_for_timeout(25)
    if page.locator("html").get_attribute("data-theme") != theme:
        raise AssertionError(f"Theme state did not change to {theme}")
    if page.locator("html").get_attribute("data-resolved-theme") != theme:
        raise AssertionError(f"Resolved theme did not change to {theme}")
    if button.get_attribute("aria-pressed") != "true":
        raise AssertionError(f"Theme control is not pressed for {theme}")

    screenshot = out_dir / f"forkline-{viewport_name}-{theme}.png"
    page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
    assert_no_overflow(page, f"{viewport_name}/{theme}")
    return {
        "viewport": viewport_name,
        "theme": theme,
        "screenshot": screenshot.name,
        "bytes": screenshot.stat().st_size,
        "sha256": sha256_file(screenshot),
        "body_text_sha256": hashlib.sha256(body_text(page).encode("utf-8")).hexdigest(),
    }


def exercise_state_mechanics(page: Page) -> dict[str, Any]:
    state_report: dict[str, Any] = {}

    geometry_rows: list[dict[str, str]] = []
    for aperture in APERTURES:
        control = page.locator(f'[data-aperture-choice="{aperture}"]')
        control.click()
        page.wait_for_timeout(20)
        if control.get_attribute("aria-pressed") != "true":
            raise AssertionError(f"Aperture control did not select {aperture}")
        if page.locator("html").get_attribute("data-aperture") != aperture:
            raise AssertionError(f"Document aperture did not change to {aperture}")
        assert_visible(page.locator(".source-rail"), f"source rail for {aperture}")
        row = {
            "aperture": aperture,
            "geometry": page.locator("#source-geometry").inner_text(),
            "ground": page.locator("#ground-contour").get_attribute("d") or "",
            "field": page.locator("#field-fill").get_attribute("d") or "",
            "reading": page.locator("#aperture-reading").inner_text(),
            "boundary": page.locator("#source-boundary").inner_text(),
        }
        geometry_rows.append(row)
    if len({row["geometry"] for row in geometry_rows}) != len(APERTURES):
        raise AssertionError("Apertures do not expose distinct geometry identities")
    if len({row["ground"] for row in geometry_rows}) != len(APERTURES):
        raise AssertionError("Apertures do not change the ground contour")
    if len({row["field"] for row in geometry_rows}) != len(APERTURES):
        raise AssertionError("Apertures do not change the authored field")
    if len({row["reading"] for row in geometry_rows}) != len(APERTURES):
        raise AssertionError("Apertures do not change the evidence reading")
    if len({row["boundary"] for row in geometry_rows}) != len(APERTURES):
        raise AssertionError("Apertures do not change their claim boundary")
    state_report["apertures"] = geometry_rows

    page.locator('[data-aperture-choice="plant"]').click()
    overlay_rows: list[dict[str, str]] = []
    for overlay in OVERLAYS:
        control = page.locator(f'[data-overlay-choice="{overlay}"]')
        control.click()
        page.wait_for_timeout(20)
        if control.get_attribute("aria-pressed") != "true":
            raise AssertionError(f"Overlay control did not select {overlay}")
        if page.locator("html").get_attribute("data-overlay") != overlay:
            raise AssertionError(f"Document overlay did not change to {overlay}")
        row = {
            "overlay": overlay,
            "path": page.locator("#overlay-area").get_attribute("d") or "",
            "class": page.locator("#overlay-area").get_attribute("class") or "",
            "label": (page.locator("#overlay-label").text_content() or "").strip(),
            "reading": page.locator("#overlay-reading").inner_text(),
        }
        if overlay not in row["class"]:
            raise AssertionError(f"Overlay class does not expose {overlay}: {row}")
        overlay_rows.append(row)
    if len({row["path"] for row in overlay_rows}) != len(OVERLAYS):
        raise AssertionError("Overlays do not expose distinct registered geometry")
    if len({row["reading"] for row in overlay_rows}) != len(OVERLAYS):
        raise AssertionError("Overlays do not expose distinct readings")
    state_report["overlays"] = overlay_rows

    actor_rows: list[dict[str, str]] = []
    for actor in ACTORS:
        control = page.locator(f'[data-actor-choice="{actor}"]')
        control.click()
        page.wait_for_timeout(10)
        if control.get_attribute("aria-pressed") != "true":
            raise AssertionError(f"Actor control did not select {actor}")
        if page.locator("html").get_attribute("data-actor") != actor:
            raise AssertionError(f"Document actor did not change to {actor}")
        actor_rows.append(
            {
                "actor": actor,
                "title": page.locator("#actor-title").inner_text(),
                "evidence": page.locator("#actor-evidence").inner_text(),
                "action": page.locator("#actor-action").inner_text(),
                "authority": page.locator("#actor-authority").inner_text(),
                "acceptance": page.locator("#actor-acceptance").inner_text(),
                "handoff": page.locator("#actor-handoff").inner_text(),
            }
        )
    for field in ("title", "evidence", "action", "authority", "acceptance", "handoff"):
        if len({row[field] for row in actor_rows}) != len(ACTORS):
            raise AssertionError(f"Actor switch does not change {field}")
    state_report["actors"] = actor_rows

    plant = page.locator('[data-aperture-choice="plant"]')
    plant.focus()
    page.keyboard.press("ArrowRight")
    household = page.locator('[data-aperture-choice="household"]')
    if household.get_attribute("aria-pressed") != "true":
        raise AssertionError("Arrow-key navigation did not activate the next aperture")
    if page.evaluate("document.activeElement?.dataset.apertureChoice") != "household":
        raise AssertionError("Arrow-key navigation did not move focus")
    state_report["keyboard_group_navigation"] = "PASS"

    all_buttons = page.get_by_role("button")
    if all_buttons.count() != 14:
        raise AssertionError(f"Expected 14 buttons, found {all_buttons.count()}")
    names = [value.strip() for value in all_buttons.all_inner_texts()]
    if any(not value for value in names):
        raise AssertionError(f"A button lacks an accessible visible name: {names}")
    target_boxes = []
    for index in range(all_buttons.count()):
        box = all_buttons.nth(index).bounding_box()
        if not box or box["width"] < 44 or box["height"] < 44:
            raise AssertionError(
                f"Control target is below 44 by 44 CSS pixels: {names[index]} {box}"
            )
        target_boxes.append(
            {
                "name": names[index],
                "width": round(box["width"], 2),
                "height": round(box["height"], 2),
            }
        )
    state_report["button_names"] = names
    state_report["control_targets"] = target_boxes
    return state_report


def run_viewport_campaign(
    browser: Browser,
    url: str,
    out_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    captures: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    mechanics: dict[str, Any] = {}

    for viewport_name, viewport in VIEWPORTS.items():
        context = create_context(browser, viewport)
        page = context.new_page()
        observations = install_observers(page, url)
        page.goto(url, wait_until="networkidle")
        page.locator("#opening-title").wait_for(state="visible")
        assert_visible(page.locator("#field-svg"), f"field SVG at {viewport_name}")
        assert_visible(page.locator(".source-rail"), f"source rail at {viewport_name}")
        assert_no_overflow(page, f"{viewport_name}/initial")

        theme_texts: dict[str, str] = {}
        for theme in THEMES:
            captures.append(theme_capture(page, out_dir, viewport_name, theme))
            theme_texts[theme] = body_text(page)
        if theme_texts["light"] != theme_texts["dark"]:
            raise AssertionError(f"Light and dark content diverged at {viewport_name}")

        if viewport_name == "desktop":
            mechanics = exercise_state_mechanics(page)
            page.locator('[data-theme-choice="dark"]').click()
            page.reload(wait_until="networkidle")
            if page.locator("html").get_attribute("data-theme") != "dark":
                raise AssertionError("Explicit theme did not persist across reload")
            if page.locator("html").get_attribute("data-resolved-theme") != "dark":
                raise AssertionError("Persisted dark theme did not resolve to dark")
            mechanics["theme_persistence"] = "PASS"

        observation_rows.append({"viewport": viewport_name, **observations})
        if any(observations.values()):
            raise AssertionError(f"Browser errors or unexpected requests at {viewport_name}: {observations}")
        context.close()

    return captures, mechanics, observation_rows


def run_auto_and_reduced_motion_campaign(
    browser: Browser,
    url: str,
) -> dict[str, Any]:
    report: dict[str, Any] = {}

    dark_context = create_context(browser, VIEWPORTS["mobile"], color_scheme="dark")
    dark_page = dark_context.new_page()
    dark_observations = install_observers(dark_page, url)
    dark_page.goto(url, wait_until="networkidle")
    dark_page.evaluate("localStorage.removeItem('m99-theme')")
    dark_page.reload(wait_until="networkidle")
    if dark_page.locator("html").get_attribute("data-theme") != "auto":
        raise AssertionError("First-visit theme is not Auto")
    if dark_page.locator("html").get_attribute("data-resolved-theme") != "dark":
        raise AssertionError("Auto theme did not honor a dark system preference")
    if any(dark_observations.values()):
        raise AssertionError(f"Auto-theme browser errors: {dark_observations}")
    report["auto_dark_system_preference"] = "PASS"
    dark_context.close()

    reduced_context = create_context(
        browser,
        VIEWPORTS["compact"],
        reduced_motion="reduce",
    )
    reduced_page = reduced_context.new_page()
    reduced_observations = install_observers(reduced_page, url)
    reduced_page.goto(url, wait_until="networkidle")
    if not reduced_page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"):
        raise AssertionError("Reduced-motion media query is not active")
    before = reduced_page.locator("#ground-contour").get_attribute("d")
    reduced_page.locator('[data-aperture-choice="region"]').click()
    after = reduced_page.locator("#ground-contour").get_attribute("d")
    if before == after:
        raise AssertionError("Reduced motion lost the aperture state change")
    transition = reduced_page.locator("#ground-contour").evaluate(
        "element => getComputedStyle(element).transitionDuration"
    )

    def duration_seconds(value: str) -> float:
        value = value.strip()
        if value.endswith("ms"):
            return float(value[:-2]) / 1000
        if value.endswith("s"):
            return float(value[:-1])
        raise AssertionError(f"Unknown transition duration unit: {value}")

    durations = [duration_seconds(value) for value in transition.split(",")]
    if any(value > 0.00001 for value in durations):
        raise AssertionError(f"Reduced-motion transition remains material: {transition}")
    assert_no_overflow(reduced_page, "compact/reduced-motion")
    if any(reduced_observations.values()):
        raise AssertionError(f"Reduced-motion browser errors: {reduced_observations}")
    report["reduced_motion"] = {
        "state_change": "PASS",
        "transition_duration": transition,
    }
    reduced_context.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "specimen",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "out",
    )
    parser.add_argument("--base-url")
    return parser.parse_args()


def execute(url: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            captures, mechanics, observations = run_viewport_campaign(
                browser,
                url,
                out_dir,
            )
            modes = run_auto_and_reduced_motion_campaign(browser, url)
        finally:
            browser.close()

    report: dict[str, Any] = {
        "schema": "axm-tools/manzanita-forkline-browser-report@1",
        "result": "PASS",
        "source_class": "authored_demonstration_geometry",
        "base_url": url,
        "viewports": VIEWPORTS,
        "themes": list(THEMES),
        "captures": captures,
        "mechanics": mechanics,
        "mode_campaigns": modes,
        "observations": observations,
        "claim_boundary": (
            "This report qualifies the internal design-system specimen only. "
            "It does not qualify a public Manzanita route, live provider, field action, "
            "whole product, release candidate, or external effect."
        ),
    }
    report["payload_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return report


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    out_dir = args.out.resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"Specimen entry does not exist: {root / 'index.html'}")

    if args.base_url:
        report = execute(args.base_url, out_dir)
    else:
        with local_server(root) as url:
            report = execute(url, out_dir)

    report_path = out_dir / "BROWSER_REPORT.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "result": report["result"],
                "captures": len(report["captures"]),
                "apertures": len(report["mechanics"]["apertures"]),
                "overlays": len(report["mechanics"]["overlays"]),
                "actors": len(report["mechanics"]["actors"]),
                "external_requests": sum(
                    len(row["external_requests"]) for row in report["observations"]
                ),
                "console_errors": sum(
                    len(row["console_errors"]) for row in report["observations"]
                ),
                "horizontal_overflow": 0,
                "report_sha256": report["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
