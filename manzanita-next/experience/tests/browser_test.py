#!/usr/bin/env python3
"""Exercise the exact built Manzanita whole-experience candidate in Chromium."""

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

from playwright.sync_api import Browser, Page, sync_playwright

VIEWPORTS = {
    "desktop": {"width": 1600, "height": 1000},
    "laptop": {"width": 1024, "height": 900},
    "mobile": {"width": 390, "height": 844},
    "compact": {"width": 320, "height": 720},
}
THEMES = ("light", "dark")


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


def runtime_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const runtime = window.__MANZANITA_WHOLE_EXPERIENCE_RUNTIME__;
          const data = window.__MANZANITA_WHOLE_EXPERIENCE__;
          return {
            version: runtime.version,
            experienceId: runtime.experienceId,
            placeId: runtime.placeId,
            sourceRunId: runtime.sourceRunId,
            state: runtime.getState(),
            counts: {
              apertures: data.apertures.length,
              overlays: data.overlays.length,
              roles: data.roles.length,
              sources: data.source_summary.sources.length,
            },
            effects: {
              public: data.public_effect,
              constitutional: data.constitutional_count_effect,
              release: data.release_effect,
            },
            sceneMode: data.scene.selected_mode,
            registration: data.registration.admission_state,
            fabRelease: data.fab_handoff.release_state,
          };
        }
        """
    )


def visible_target_floor(page: Page) -> float:
    return page.evaluate(
        """
        () => Math.min(...[...document.querySelectorAll('button')]
          .filter((node) => {
            const style = getComputedStyle(node);
            const box = node.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
          })
          .map((node) => node.getBoundingClientRect().height))
        """
    )


def horizontal_overflow(page: Page) -> int:
    return page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth")


def exercise_primary_path(page: Page, output: Path) -> dict[str, Any]:
    initial = runtime_snapshot(page)
    require(initial["counts"] == {"apertures": 7, "overlays": 8, "roles": 5, "sources": 21}, "Runtime counts drifted")
    require(initial["effects"] == {"public": "none", "constitutional": "none", "release": "none"}, "Runtime effect boundary drifted")
    require(initial["sceneMode"] == "map_only", "The admitted run must preserve map-only Street Glide state")
    require(initial["registration"] == "registration_proposal", "Registration proposal state drifted")
    require(initial["fabRelease"] == "not_authorized", "FAB handoff release boundary drifted")
    require(initial["state"]["aperture"] == "household", "Initial aperture should fall back to household")
    require(initial["state"]["overlay"] == "care", "Initial overlay should be care")
    require(initial["state"]["role"] == "resident", "Initial role should be resident")

    require(page.locator("#rail-place").inner_text().strip() != "", "Source rail lacks place identity")
    require("MAP-ONLY" in page.locator("#map-mode").inner_text(), "Map-only state is not visible")
    require(page.locator("#degraded-ledger .ledger-row").count() >= 4, "Degraded evidence ledger is incomplete")

    aperture_before = page.locator("#aperture-ground").get_attribute("d")
    page.get_by_role("button", name="plant", exact=True).click()
    require(runtime_snapshot(page)["state"]["aperture"] == "plant", "Plant aperture did not activate")
    require(page.locator("#aperture-ground").get_attribute("d") != aperture_before, "Scale change did not change geometry")
    require("living" in page.locator("#operating-object").inner_text().lower(), "Scale change did not change the governed object")

    page.get_by_role("button", name="water", exact=True).click()
    require(runtime_snapshot(page)["state"]["overlay"] == "water", "Water overlay did not activate")
    require(page.locator("#overlay-geometry > *").count() > 0, "Overlay geometry did not render")
    require("water" in page.locator("#stage-title").inner_text().lower(), "Stage title did not change with overlay")

    page.locator('[data-role="planner_program"]').click()
    role_state = runtime_snapshot(page)["state"]
    require(role_state["role"] == "planner_program", "Planner role did not activate")
    require(page.locator("#role-action-list li").count() >= 2, "Role controls did not change")
    require("program" in page.locator("#operating-authority").inner_text().lower(), "Role authority did not change")

    page.locator('[data-section="fab_handoff"]').click()
    require(page.locator("#fab-record").is_visible(), "FAB handoff section did not open")
    fab_text = page.locator("#fab-record").inner_text().lower()
    require("not authorized" in fab_text, "FAB handoff does not expose its no-effect state")
    require("prohibited" in fab_text, "FAB firewall does not expose prohibited effects")
    require("refuse" in fab_text and "appeal" in fab_text, "Affected-actor refusal and appeal are missing")

    page.locator('[data-section="sources"]').click()
    page.locator('[data-source-filter="skipped_missing_credential"]').click()
    require(page.locator("#source-register .source-row").count() >= 4, "Credential-missing sources are not inspectable")
    require("missing credential" in page.locator("#source-register").inner_text().lower(), "Source state detail is missing")

    page.locator('[data-section="overview"]').click()
    household = page.locator('[data-aperture="household"]')
    household.focus()
    household.press("ArrowRight")
    require(runtime_snapshot(page)["state"]["aperture"] == "property", "Arrow-key group navigation failed")
    require(page.locator('[data-aperture="property"]').evaluate("node => node === document.activeElement"), "Keyboard focus did not follow selection")

    page.locator("#help-button").click()
    require(page.locator("#help-dialog").evaluate("node => node.open"), "Help dialog did not open")
    help_text = page.locator("#help-dialog").inner_text().lower()
    require("prohibited uses" in help_text and "release holds" in help_text, "Help omits consequence and release boundaries")
    page.get_by_role("button", name="Close help").click()
    require(not page.locator("#help-dialog").evaluate("node => node.open"), "Help dialog did not close")

    with page.expect_download() as download_info:
        page.locator("#export-button").click()
    download = download_info.value
    export_path = output / "exported-snapshot.json"
    download.save_as(export_path)
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    require(exported["schema"] == "axm-tools/manzanita-whole-experience-snapshot@1", "Export schema drifted")
    require(exported["public_effect"] == "none", "Export carries a public effect")
    require(exported["constitutional_count_effect"] == "none", "Export carries a task-count effect")
    require(exported["release_state"] == "not_authorized", "Export carries release authority")
    require(exported["export_law"]["private_record_transfer"] == "prohibited", "Export lost the private-record boundary")

    return {
        "initial": initial,
        "final": runtime_snapshot(page),
        "export": {
            "path": export_path.name,
            "bytes": export_path.stat().st_size,
            "sha256": sha256(export_path),
        },
    }


def run_campaign(site: Path, output: Path, browser: Browser, base_url: str) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    external_requests: list[str] = []

    context = browser.new_context(viewport=VIEWPORTS["desktop"], color_scheme="light", accept_downloads=True)
    page = context.new_page()
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("request", lambda request: external_requests.append(request.url) if not request.url.startswith(base_url.rsplit("/", 1)[0]) else None)
    page.goto(base_url, wait_until="networkidle")
    primary = exercise_primary_path(page, output)
    context.close()

    captures: list[dict[str, Any]] = []
    for viewport_id, viewport in VIEWPORTS.items():
        for theme in THEMES:
            context = browser.new_context(viewport=viewport, color_scheme=theme)
            page = context.new_page()
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("request", lambda request: external_requests.append(request.url) if not request.url.startswith(base_url.rsplit("/", 1)[0]) else None)
            page.goto(base_url, wait_until="networkidle")
            page.locator(f'[data-theme-choice="{theme}"]').click()
            page.locator('[data-overlay="fire"]').click()
            page.locator('[data-role="crew_steward"]').click()
            require(horizontal_overflow(page) <= 1, f"Horizontal overflow at {viewport_id}/{theme}")
            require(visible_target_floor(page) >= 43.5, f"Visible target floor below 44 CSS px at {viewport_id}/{theme}")
            require(page.locator("#source-rail, .source-rail").count() == 1, "Source rail disappeared")
            screenshot = output / f"whole-experience-{viewport_id}-{theme}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            captures.append({
                "viewport": viewport_id,
                "theme": theme,
                "width": viewport["width"],
                "height": viewport["height"],
                "horizontal_overflow": horizontal_overflow(page),
                "minimum_visible_target_height": visible_target_floor(page),
                "screenshot": screenshot.name,
                "screenshot_sha256": sha256(screenshot),
                "state": runtime_snapshot(page)["state"],
            })
            context.close()

    reduced_context = browser.new_context(viewport=VIEWPORTS["mobile"], reduced_motion="reduce", color_scheme="dark")
    reduced = reduced_context.new_page()
    reduced.goto(base_url, wait_until="networkidle")
    reduced.locator('[data-aperture="region"]').click()
    reduced.locator('[data-overlay="access"]').click()
    reduced.locator('[data-role="successor"]').click()
    reduced_motion = reduced.evaluate(
        """
        () => ({
          preference: matchMedia('(prefers-reduced-motion: reduce)').matches,
          transition: getComputedStyle(document.querySelector('#main')).transitionDuration,
          state: window.__MANZANITA_WHOLE_EXPERIENCE_RUNTIME__.getState(),
        })
        """
    )
    require(reduced_motion["preference"] is True, "Reduced-motion preference was not active")
    reduced_context.close()

    zoom_context = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="light")
    zoom = zoom_context.new_page()
    zoom.goto(base_url, wait_until="networkidle")
    zoom.evaluate("document.documentElement.style.fontSize = '200%'")
    zoom.wait_for_timeout(100)
    zoom_overflow = horizontal_overflow(zoom)
    require(zoom_overflow <= 2, "The 200 percent text-resize campaign introduced horizontal overflow")
    require(zoom.locator("#operating-action").is_visible(), "Next safe action disappeared at 200 percent text resize")
    require(zoom.locator("#export-button").is_visible(), "Export control disappeared at 200 percent text resize")
    zoom_context.close()

    require(not console_errors, f"Console errors: {console_errors}")
    require(not page_errors, f"Page errors: {page_errors}")
    require(not external_requests, f"External requests: {external_requests}")

    report = {
        "schema": "axm-tools/manzanita-whole-experience-browser-campaign@1",
        "result": "PASS",
        "site": str(site),
        "primary_path": primary,
        "captures": captures,
        "reduced_motion": reduced_motion,
        "zoom_200_percent": {"horizontal_overflow": zoom_overflow, "next_safe_action_visible": True},
        "console_errors": console_errors,
        "page_errors": page_errors,
        "external_requests": external_requests,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "qualification_boundary": "This campaign proves the exact internal site can operate across the declared viewports and themes with bounded keyboard, help, export, reduced-motion, and zoom behavior. It does not prove assistive technology, real devices, poor networks, private records, field use, public deployment, rollback, or cold succession.",
    }
    report_path = output / "BROWSER_CAMPAIGN.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["report_sha256"] = sha256(report_path)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    site = args.site.resolve()
    output = args.output.resolve()
    require((site / "index.html").is_file(), "Built site index is missing")
    with serve(site) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            report = run_campaign(site, output, browser, url)
        finally:
            browser.close()
    print(json.dumps({
        "result": report["result"],
        "captures": len(report["captures"]),
        "console_errors": len(report["console_errors"]),
        "page_errors": len(report["page_errors"]),
        "external_requests": len(report["external_requests"]),
        "report_sha256": report["report_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
