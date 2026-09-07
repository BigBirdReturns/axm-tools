#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import http.server
import json
import os
import socket
import threading
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = Path(os.environ.get("MW_WORKING_MODEL_SCREENSHOT_DIR", "/tmp/manzanita-working-model-review"))
OUT.mkdir(parents=True, exist_ok=True)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        pass


@contextlib.contextmanager
def server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(REPO), **kwargs)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/manzanita-working-model/index.html"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def assert_no_overflow(page) -> None:
    overflow = page.evaluate("""() => ({
      doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth
    })""")
    assert overflow["doc"] <= 1 and overflow["body"] <= 1, overflow


def assert_local_only(requests: list[str]) -> None:
    unexpected = []
    for request in requests:
        parsed = urlparse(request)
        if parsed.scheme in {"http", "https"} and parsed.hostname not in {"127.0.0.1", "localhost"}:
            unexpected.append(request)
    assert not unexpected, unexpected


def main() -> None:
    with server() as url, sync_playwright() as playwright:
        launch: dict[str, object] = {"headless": True}
        if os.environ.get("MW_CHROMIUM_EXECUTABLE"):
            launch["executable_path"] = os.environ["MW_CHROMIUM_EXECUTABLE"]
            launch["args"] = ["--no-sandbox"]
        browser = playwright.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1600, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors: list[str] = []
        requests: list[str] = []
        page.on("console", lambda msg: errors.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        page.on("request", lambda request: requests.append(request.url))

        page.goto(url, wait_until="networkidle")
        assert page.locator('meta[name="mw-release"]').get_attribute("content") == "mw-working-model-v1.0.0-candidate"
        assert page.locator(".scenario-tab").count() == 4
        assert page.locator(".stage-card").count() == 7
        assert page.locator(".decision-number").count() == 5
        assert page.locator(".proof-card").count() == 4
        assert "Silence is not consent" in page.locator(".invariant").inner_text()
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-desktop.png"), full_page=True)

        # All four scenarios are real projections, not label swaps.
        expected = {
            "wildfire": ("wildfire exposure", "parcel score"),
            "tools": ("tool", "silent assignment"),
            "mobility": ("transportation path", "vehicle availability"),
            "continuity": ("good idea", "silence into rejection"),
        }
        for scenario, (title_fragment, prohibited_fragment) in expected.items():
            page.locator(f'[data-scenario="{scenario}"]').click()
            assert title_fragment.lower() in page.locator("#scenario-title").inner_text().lower()
            assert prohibited_fragment.lower() in page.locator("#scenario-prohibited").inner_text().lower()
            assert page.locator(".stage-card").count() == 7
            stages = page.locator(".stage-card h4").all_inner_texts()
            assert stages == ["Signal", "Source", "Authority", "Safe action", "Fallback", "Closure", "Learning"]

        # Keyboard tab navigation carries the projection with focus.
        first = page.locator('[data-scenario="wildfire"]')
        first.focus()
        page.keyboard.press("ArrowRight")
        assert page.locator('[data-scenario="tools"]').get_attribute("aria-selected") == "true"
        assert "tool" in page.locator("#scenario-title").inner_text().lower()

        # Incomplete packet preserves every blank rather than implying readiness.
        page.locator("#pilot-scenario").select_option("tools")
        page.locator("#pilot-sponsor").fill("Executive sponsor seat")
        assert "1 of 5" in page.locator("#form-status").inner_text()
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        first_download = download_info.value
        incomplete_path = OUT / "pilot-incomplete.json"
        first_download.save_as(str(incomplete_path))
        incomplete = json.loads(incomplete_path.read_text(encoding="utf-8"))
        assert incomplete["schema"] == "manzanita-works/bounded-pilot-preparation@1"
        assert incomplete["standing"] == "INCOMPLETE_PREPARATION_HELD"
        assert incomplete["organizational_gates"]["named_count"] == 1
        assert incomplete["organizational_gates"]["continuity_operator"] == "UNRESOLVED"
        assert incomplete["organizational_gates"]["venue_or_participant_class"] == "UNRESOLVED"
        assert incomplete["authority"]["institutional_acceptance"] is False
        assert incomplete["authority"]["field_authority"] is False
        assert incomplete["authority"]["external_effect"] == "none"
        assert "Do not schedule" in incomplete["next_safe_action"]

        # A fully filled preparation packet remains preparation, not acceptance or authority.
        page.locator("#pilot-operator").fill("Funded continuity operator seat")
        page.locator("#pilot-venue").fill("One bounded participant class")
        page.locator("#pilot-resources").fill("Defined pilot resource envelope")
        page.locator("#pilot-stop").fill("Stop if authority, consent, source quality, or operator capacity is absent.")
        assert "5 of 5" in page.locator("#form-status").inner_text()
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        complete_path = OUT / "pilot-complete.json"
        download_info.value.save_as(str(complete_path))
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
        assert complete["standing"] == "PREPARED_FOR_ACCOUNTABLE_REVIEW_NOT_ACCEPTED"
        assert complete["organizational_gates"]["named_count"] == 5
        assert complete["authority"]["institutional_acceptance"] is False
        assert complete["authority"]["participant_consent"] is False
        assert complete["authority"]["field_authority"] is False
        assert complete["authority"]["spend_authority"] is False
        assert complete["authority"]["publication_authority"] is False
        assert complete["authority"]["assignment_authority"] is False
        assert complete["authority"]["representation_authority"] is False
        assert complete["authority"]["release_authority"] is False
        assert complete["authority"]["external_effect"] == "none"
        assert complete["invariant"]["silence_law"].startswith("Silence is not consent")

        # Draft is local and persistent until deliberately cleared.
        page.reload(wait_until="networkidle")
        assert page.locator("#pilot-sponsor").input_value() == "Executive sponsor seat"
        assert page.locator("#pilot-operator").input_value() == "Funded continuity operator seat"
        page.locator("#clear-pilot").click()
        assert page.locator("#pilot-sponsor").input_value() == ""
        assert "0 of 5" in page.locator("#form-status").inner_text()
        page.reload(wait_until="networkidle")
        assert page.locator("#pilot-sponsor").input_value() == ""

        # Theme is local and persistent.
        original_theme = page.locator("html").get_attribute("data-theme")
        page.locator("#theme").click()
        changed_theme = page.locator("html").get_attribute("data-theme")
        assert changed_theme in {"light", "dark"} and changed_theme != original_theme
        page.reload(wait_until="networkidle")
        assert page.locator("html").get_attribute("data-theme") == changed_theme

        # Ordinary mobile.
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(url + "#run-wildfire", wait_until="networkidle")
        assert page.locator('[data-scenario="wildfire"]').get_attribute("aria-selected") == "true"
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-mobile.png"), full_page=True)

        # 320px at 200% root text must remain horizontally contained.
        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(url + "#run-continuity", wait_until="networkidle")
        page.evaluate("document.documentElement.style.fontSize='200%'")
        page.wait_for_timeout(150)
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-320-200pct.png"), full_page=True)

        # Reduced motion changes no meaning or operability.
        reduced = browser.new_context(viewport={"width": 1024, "height": 768}, reduced_motion="reduce")
        reduced_page = reduced.new_page()
        reduced_errors: list[str] = []
        reduced_page.on("pageerror", lambda exc: reduced_errors.append(str(exc)))
        reduced_page.goto(url, wait_until="networkidle")
        reduced_page.locator('[data-scenario="mobility"]').click()
        assert "transportation path" in reduced_page.locator("#scenario-title").inner_text().lower()
        assert not reduced_errors, reduced_errors
        reduced.close()

        assert_local_only(requests)
        assert not errors, errors
        browser.close()

    print(json.dumps({
        "result": "PASS_WORKING_MODEL_CHROMIUM_CAMPAIGN",
        "release": "mw-working-model-v1.0.0-candidate",
        "scenarios": 4,
        "stages_per_scenario": 7,
        "pilot_gates": 5,
        "external_effect": "none",
        "screenshots": [
            "working-model-desktop.png",
            "working-model-mobile.png",
            "working-model-320-200pct.png",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
