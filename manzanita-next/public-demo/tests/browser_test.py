#!/usr/bin/env python3
"""Qualify the generated public-safe place artifact across every declared mode."""

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
except ImportError as exc:  # pragma: no cover
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
VIEWS = ("place", "weather", "water", "fire")
ACTORS = ("visitor", "steward", "program_operator")


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


def context_for(
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


def observe(page: Page, base_url: str) -> dict[str, list[str]]:
    observations: dict[str, list[str]] = {
        "console_errors": [],
        "page_errors": [],
        "external_requests": [],
        "failed_requests": [],
    }
    expected = urlparse(base_url)

    def on_request(request: Any) -> None:
        parsed = urlparse(request.url)
        if parsed.scheme in {"about", "data", "blob"}:
            return
        if parsed.scheme not in {"http", "https"}:
            observations["external_requests"].append(request.url)
            return
        if parsed.hostname != expected.hostname or parsed.port != expected.port:
            observations["external_requests"].append(request.url)

    page.on(
        "console",
        lambda message: observations["console_errors"].append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: observations["page_errors"].append(str(error)))
    page.on("request", on_request)
    page.on(
        "requestfailed",
        lambda request: observations["failed_requests"].append(
            f"{request.method} {request.url}: {request.failure}"
        ),
    )
    return observations


def assert_clean(observations: dict[str, list[str]], label: str) -> None:
    if any(observations.values()):
        raise AssertionError(f"Browser errors or unexpected requests at {label}: {observations}")


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


def capture_theme(
    page: Page,
    out_dir: Path,
    viewport_name: str,
    theme: str,
) -> dict[str, Any]:
    control = page.locator(f'[data-theme-choice="{theme}"]')
    control.click()
    page.wait_for_timeout(25)
    if page.locator("html").get_attribute("data-theme") != theme:
        raise AssertionError(f"Theme did not change to {theme}")
    if page.locator("html").get_attribute("data-resolved-theme") != theme:
        raise AssertionError(f"Resolved theme did not change to {theme}")
    if control.get_attribute("aria-pressed") != "true":
        raise AssertionError(f"Theme control is not selected for {theme}")
    assert_no_overflow(page, f"{viewport_name}/{theme}")
    screenshot = out_dir / f"public-demo-{viewport_name}-{theme}.png"
    page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
    return {
        "viewport": viewport_name,
        "theme": theme,
        "screenshot": screenshot.name,
        "bytes": screenshot.stat().st_size,
        "sha256": sha256_file(screenshot),
        "body_text_sha256": hashlib.sha256(body_text(page).encode("utf-8")).hexdigest(),
    }


def exercise_views(page: Page) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view_id in VIEWS:
        control = page.locator(f'[data-view-choice="{view_id}"]')
        control.click()
        page.wait_for_timeout(20)
        if control.get_attribute("aria-pressed") != "true":
            raise AssertionError(f"View control did not select {view_id}")
        if page.locator("html").get_attribute("data-view") != view_id:
            raise AssertionError(f"Document view did not change to {view_id}")
        source_rows = page.locator("#source-rail-list > div")
        if source_rows.count() < 1:
            raise AssertionError(f"View {view_id} has no source rail rows")
        metric_rows = page.locator("#metric-list > article")
        if metric_rows.count() != 3:
            raise AssertionError(f"View {view_id} must expose exactly three bounded metrics")
        row = {
            "view": view_id,
            "ground": page.locator("#field-ground").get_attribute("d") or "",
            "overlay": page.locator("#field-overlay").get_attribute("d") or "",
            "overlay_class": page.locator("#field-overlay").get_attribute("class") or "",
            "reading": page.locator("#view-reading").inner_text(),
            "safe_action": page.locator("#view-safe-action").inner_text(),
            "authority": page.locator("#view-authority").inner_text(),
            "prohibited": page.locator("#view-prohibited").inner_text(),
            "metrics": [
                metric_rows.nth(index).inner_text()
                for index in range(metric_rows.count())
            ],
            "source_rows": source_rows.count(),
        }
        if view_id not in row["overlay_class"]:
            raise AssertionError(f"Overlay class does not expose {view_id}: {row}")
        rows.append(row)

    for field in ("ground", "overlay", "reading", "safe_action", "authority", "prohibited"):
        if len({row[field] for row in rows}) != len(VIEWS):
            raise AssertionError(f"Evidence views do not change {field}")
    return rows


def exercise_actors(page: Page) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for actor_id in ACTORS:
        control = page.locator(f'[data-actor-choice="{actor_id}"]')
        control.click()
        page.wait_for_timeout(10)
        if control.get_attribute("aria-pressed") != "true":
            raise AssertionError(f"Actor control did not select {actor_id}")
        if page.locator("html").get_attribute("data-actor") != actor_id:
            raise AssertionError(f"Document actor did not change to {actor_id}")
        rows.append(
            {
                "actor": actor_id,
                "title": page.locator("#actor-title").inner_text(),
                "evidence": page.locator("#actor-evidence").inner_text(),
                "action": page.locator("#actor-action").inner_text(),
                "authority": page.locator("#actor-authority").inner_text(),
                "acceptance": page.locator("#actor-acceptance").inner_text(),
                "handoff": page.locator("#actor-handoff").inner_text(),
            }
        )
    for field in ("title", "evidence", "action", "authority", "acceptance", "handoff"):
        if len({row[field] for row in rows}) != len(ACTORS):
            raise AssertionError(f"Actor switch does not change {field}")
    return rows


def exercise_controls(page: Page) -> dict[str, Any]:
    place = page.locator('[data-view-choice="place"]')
    place.focus()
    page.keyboard.press("ArrowRight")
    weather = page.locator('[data-view-choice="weather"]')
    if weather.get_attribute("aria-pressed") != "true":
        raise AssertionError("Arrow navigation did not activate the next evidence view")
    if page.evaluate("document.activeElement?.dataset.viewChoice") != "weather":
        raise AssertionError("Arrow navigation did not move focus")

    buttons = page.get_by_role("button")
    if buttons.count() != 10:
        raise AssertionError(f"Expected 10 buttons, found {buttons.count()}")
    names = [name.strip() for name in buttons.all_inner_texts()]
    if any(not name for name in names):
        raise AssertionError(f"A button lacks an accessible visible name: {names}")
    targets = []
    for index in range(buttons.count()):
        box = buttons.nth(index).bounding_box()
        if not box or box["width"] < 44 or box["height"] < 44:
            raise AssertionError(f"Control target is below 44 by 44 CSS pixels: {names[index]} {box}")
        targets.append(
            {
                "name": names[index],
                "width": round(box["width"], 2),
                "height": round(box["height"], 2),
            }
        )
    return {
        "keyboard_group_navigation": "PASS",
        "button_names": names,
        "control_targets": targets,
    }


def exercise_projection(page: Page) -> dict[str, Any]:
    runtime = page.evaluate("window.__MANZANITA_PUBLIC_DEMO_RUNTIME__")
    data = page.evaluate("window.__MANZANITA_PUBLIC_DEMO__")
    if runtime["version"] != data["contract_version"]:
        raise AssertionError("Runtime and generated public-data contracts disagree")
    if data["place"]["public_safe"] is not True:
        raise AssertionError("Built place is not explicitly public-safe")
    if data["place"]["coordinate_precision_decimals"] > 4:
        raise AssertionError("Public coordinate precision exceeds four decimals")
    if data["claim_boundary"].lower().find("public deployment") < 0:
        raise AssertionError("Public deployment hold is missing")
    if not data["adverse_action_boundary"]["prohibited_uses"]:
        raise AssertionError("Adverse-action boundary is empty")

    image_state = page.locator("#base-imagery").evaluate(
        "image => ({complete: image.complete, width: image.naturalWidth, height: image.naturalHeight, alt: image.alt})"
    )
    if not image_state["complete"] or image_state["width"] <= 0 or image_state["height"] <= 0:
        raise AssertionError(f"Base public image did not load: {image_state}")
    if "claim" not in image_state["alt"].lower() and "no " not in image_state["alt"].lower():
        raise AssertionError(f"Base image alternative text lacks a source boundary: {image_state['alt']}")

    failures = page.locator("#failure-list > article")
    if failures.count() != len(data["failures"]):
        raise AssertionError(
            f"Rendered failure count {failures.count()} does not match generated data {len(data['failures'])}"
        )
    failure_text = page.locator("#failure-list").inner_text().lower()
    for required in (
        "what failed",
        "what remains known",
        "what is unknown",
        "safe fallback",
        "rights and storage",
        "accountable next action",
    ):
        if required not in failure_text:
            raise AssertionError(f"Failure sheet lacks {required}")
    if "insurance" not in page.locator("#adverse-boundary").inner_text().lower():
        raise AssertionError("Visible adverse-action boundary lacks insurance prohibition")
    if "manifest" not in page.locator("#build-identity").inner_text().lower():
        raise AssertionError("Visible build identity lacks the source-manifest receipt")

    serialized = json.dumps(data).lower()
    for prohibited in (
        "street_address",
        "resident_name",
        "access_token",
        "api_key",
        "private key",
    ):
        if prohibited in serialized:
            raise AssertionError(f"Public projection contains prohibited material: {prohibited}")
    return {
        "runtime": runtime,
        "source_state_counts": data["source_state_counts"],
        "failure_count": len(data["failures"]),
        "image": image_state,
        "place": data["place"],
        "build_id": data["build_id"],
        "source_run_id": data["source_run_id"],
        "source_manifest_sha256": data["source_manifest_sha256"],
    }


def run_viewports(
    browser: Browser,
    url: str,
    out_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    captures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    mechanics: dict[str, Any] = {}

    for viewport_name, viewport in VIEWPORTS.items():
        context = context_for(browser, viewport)
        page = context.new_page()
        page_observations = observe(page, url)
        page.goto(url, wait_until="networkidle")
        page.locator("#opening-title").wait_for(state="visible")
        assert_visible(page.locator("#field-svg"), f"field SVG at {viewport_name}")
        assert_visible(page.locator(".source-rail"), f"source rail at {viewport_name}")
        assert_visible(page.locator("#failure-list"), f"failure ledger at {viewport_name}")
        assert_no_overflow(page, f"{viewport_name}/initial")

        texts = {}
        for theme in THEMES:
            captures.append(capture_theme(page, out_dir, viewport_name, theme))
            texts[theme] = body_text(page)
        if texts["light"] != texts["dark"]:
            raise AssertionError(f"Light and dark content diverged at {viewport_name}")

        if viewport_name == "desktop":
            mechanics["views"] = exercise_views(page)
            mechanics["actors"] = exercise_actors(page)
            mechanics.update(exercise_controls(page))
            mechanics["projection"] = exercise_projection(page)
            page.locator('[data-theme-choice="dark"]').click()
            page.reload(wait_until="networkidle")
            if page.locator("html").get_attribute("data-theme") != "dark":
                raise AssertionError("Explicit theme did not persist across reload")
            if page.locator("html").get_attribute("data-resolved-theme") != "dark":
                raise AssertionError("Persisted dark theme did not resolve to dark")
            mechanics["theme_persistence"] = "PASS"

        assert_clean(page_observations, viewport_name)
        observations.append({"viewport": viewport_name, **page_observations})
        context.close()

    return captures, mechanics, observations


def duration_seconds(value: str) -> float:
    value = value.strip()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000
    if value.endswith("s"):
        return float(value[:-1])
    raise AssertionError(f"Unknown duration unit: {value}")


def run_modes(browser: Browser, url: str) -> dict[str, Any]:
    report: dict[str, Any] = {}

    auto_context = context_for(browser, VIEWPORTS["mobile"], color_scheme="dark")
    auto_page = auto_context.new_page()
    auto_observations = observe(auto_page, url)
    auto_page.goto(url, wait_until="networkidle")
    auto_page.evaluate("localStorage.removeItem('m99-public-demo-theme')")
    auto_page.reload(wait_until="networkidle")
    if auto_page.locator("html").get_attribute("data-theme") != "auto":
        raise AssertionError("First-visit theme is not Auto")
    if auto_page.locator("html").get_attribute("data-resolved-theme") != "dark":
        raise AssertionError("Auto theme did not honor dark system preference")
    assert_clean(auto_observations, "auto-dark")
    report["auto_dark_system_preference"] = "PASS"
    auto_context.close()

    reduced_context = context_for(
        browser,
        VIEWPORTS["compact"],
        reduced_motion="reduce",
    )
    reduced_page = reduced_context.new_page()
    reduced_observations = observe(reduced_page, url)
    reduced_page.goto(url, wait_until="networkidle")
    if not reduced_page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"):
        raise AssertionError("Reduced-motion media query is not active")
    before = reduced_page.locator("#field-ground").get_attribute("d")
    reduced_page.locator('[data-view-choice="fire"]').click()
    after = reduced_page.locator("#field-ground").get_attribute("d")
    if before == after:
        raise AssertionError("Reduced motion lost the evidence-view state change")
    transition = reduced_page.locator("#field-ground").evaluate(
        "element => getComputedStyle(element).transitionDuration"
    )
    if any(duration_seconds(item) > 0.00001 for item in transition.split(",")):
        raise AssertionError(f"Reduced-motion transition remains material: {transition}")
    assert_no_overflow(reduced_page, "compact/reduced-motion")
    assert_clean(reduced_observations, "reduced-motion")
    report["reduced_motion"] = {
        "state_change": "PASS",
        "transition_duration": transition,
    }
    reduced_context.close()
    return report


def execute(url: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            captures, mechanics, observations = run_viewports(browser, url, out_dir)
            modes = run_modes(browser, url)
        finally:
            browser.close()

    report: dict[str, Any] = {
        "schema": "axm-tools/manzanita-public-demo-browser-report@1",
        "result": "PASS",
        "viewports": VIEWPORTS,
        "themes": list(THEMES),
        "captures": captures,
        "mechanics": mechanics,
        "mode_campaigns": modes,
        "observations": observations,
        "release_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": (
            "This browser report qualifies the generated public-safe demonstration artifact only. "
            "It does not qualify a public endpoint, live safety directive, field action, completed work, "
            "adverse decision, whole product, design score, or canonical task-count transition."
        ),
    }
    report["payload_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "out" / "site",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "out" / "qualification",
    )
    parser.add_argument("--base-url")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    out_dir = args.out.resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"Built public demo does not exist: {root / 'index.html'}")
    if not (root / "demo-data.js").is_file():
        raise SystemExit(f"Built public data does not exist: {root / 'demo-data.js'}")

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
                "views": len(report["mechanics"]["views"]),
                "actors": len(report["mechanics"]["actors"]),
                "failures": report["mechanics"]["projection"]["failure_count"],
                "external_requests": sum(
                    len(row["external_requests"]) for row in report["observations"]
                ),
                "console_errors": sum(
                    len(row["console_errors"]) for row in report["observations"]
                ),
                "horizontal_overflow": 0,
                "release_effect": report["release_effect"],
                "constitutional_count_effect": report["constitutional_count_effect"],
                "report_sha256": report["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
