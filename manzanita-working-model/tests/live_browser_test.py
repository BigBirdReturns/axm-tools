#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URL = os.environ["MW_WORKING_MODEL_URL"].rstrip("/") + "/"
SOURCE_SHA = os.environ.get("GITHUB_SHA", "UNRESOLVED")
OUT = Path(os.environ.get("MW_WORKING_MODEL_LIVE_SCREENSHOT_DIR", "/tmp/manzanita-working-model-live-review"))
RESULT = Path(os.environ.get("MW_WORKING_MODEL_LIVE_BROWSER_RESULT", OUT / "live-browser-result.json"))
OUT.mkdir(parents=True, exist_ok=True)
RELEASE = "mw-working-model-v1.0.0"


def target(fragment: str = "") -> str:
    return f"{URL}?release={RELEASE}&source={SOURCE_SHA}{fragment}"


def assert_no_overflow(page) -> None:
    overflow = page.evaluate("""() => ({
      doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth
    })""")
    assert overflow["doc"] <= 1 and overflow["body"] <= 1, overflow


def assert_http_clean(http_errors: list[dict[str, object]]) -> None:
    failures = []
    for item in http_errors:
        path = urlparse(str(item["url"])).path
        if path == "/favicon.ico" and item["status"] == 404:
            continue
        failures.append(item)
    assert not failures, failures


def main() -> None:
    parsed = urlparse(URL)
    allowed_origin = f"{parsed.scheme}://{parsed.netloc}"
    with sync_playwright() as playwright:
        launch: dict[str, object] = {"headless": True}
        if os.environ.get("MW_CHROMIUM_EXECUTABLE"):
            launch["executable_path"] = os.environ["MW_CHROMIUM_EXECUTABLE"]
            launch["args"] = ["--no-sandbox"]
        browser = playwright.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1600, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors: list[str] = []
        requests: list[str] = []
        request_failures: list[str] = []
        http_errors: list[dict[str, object]] = []
        page.on(
            "console",
            lambda msg: errors.append(f"console:{msg.type}:{msg.text}")
            if msg.type == "error" and not msg.text.startswith("Failed to load resource:")
            else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        page.on("request", lambda request: requests.append(request.url))
        page.on("requestfailed", lambda request: request_failures.append(f"{request.url}: {request.failure}"))
        page.on(
            "response",
            lambda response: http_errors.append({"url": response.url, "status": response.status})
            if response.status >= 400
            else None,
        )

        page.goto(target("#run-wildfire"), wait_until="networkidle")
        assert page.locator('meta[name="mw-release"]').get_attribute("content") == RELEASE
        assert page.locator(".scenario-tab").count() == 4
        assert page.locator(".stage-card").count() == 7
        assert page.locator(".decision-number").count() == 5
        assert page.locator(".proof-card").count() == 4
        assert page.locator("main img").count() == 0
        assert page.locator(".hero-console").count() == 1
        assert page.locator(".console-grammar li").count() == 7
        assert page.locator(".console-ledger > div").count() == 4
        assert page.locator(".place-stack li").count() == 7
        assert "no adverse use" in page.locator(".instrument-foot").inner_text().lower()
        assert "Silence is not consent" in page.locator(".invariant").inner_text()
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-live-desktop.png"), full_page=True)

        expected = {
            "wildfire": ("wildfire exposure", "parcel score"),
            "tools": ("tool", "silent assignment"),
            "mobility": ("transportation path", "vehicle availability"),
            "continuity": ("good idea", "silence into rejection"),
        }
        expected_stages = ["signal", "source", "authority", "safe action", "fallback", "closure", "learning"]
        for scenario, (title_fragment, prohibited_fragment) in expected.items():
            page.locator(f'[data-scenario="{scenario}"]').click()
            assert title_fragment in page.locator("#scenario-title").inner_text().lower()
            assert prohibited_fragment in page.locator("#scenario-prohibited").inner_text().lower()
            stages = [value.strip().lower() for value in page.locator(".stage-card h4").all_inner_texts()]
            assert stages == expected_stages, stages

        page.locator('[data-scenario="wildfire"]').focus()
        page.keyboard.press("ArrowRight")
        assert page.locator('[data-scenario="tools"]').get_attribute("aria-selected") == "true"

        page.locator("#pilot-scenario").select_option("tools")
        page.locator("#pilot-sponsor").fill("Executive sponsor seat")
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        incomplete_path = OUT / "pilot-live-incomplete.json"
        download_info.value.save_as(str(incomplete_path))
        incomplete = json.loads(incomplete_path.read_text(encoding="utf-8"))
        assert incomplete["release"] == RELEASE
        assert incomplete["standing"] == "INCOMPLETE_PREPARATION_HELD"
        assert incomplete["organizational_gates"]["continuity_operator"] == "UNRESOLVED"
        assert incomplete["authority"]["institutional_acceptance"] is False
        assert incomplete["authority"]["external_effect"] == "none"

        page.locator("#pilot-operator").fill("Funded continuity operator seat")
        page.locator("#pilot-venue").fill("One bounded participant class")
        page.locator("#pilot-resources").fill("Defined pilot resource envelope")
        page.locator("#pilot-stop").fill("Stop if authority, consent, source quality, or operator capacity is absent.")
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        complete_path = OUT / "pilot-live-complete.json"
        download_info.value.save_as(str(complete_path))
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
        assert complete["release"] == RELEASE
        assert complete["standing"] == "PREPARED_FOR_ACCOUNTABLE_REVIEW_NOT_ACCEPTED"
        for field in [
            "institutional_acceptance", "participant_consent", "field_authority",
            "spend_authority", "publication_authority", "assignment_authority",
            "representation_authority", "release_authority",
        ]:
            assert complete["authority"][field] is False, field
        assert complete["authority"]["external_effect"] == "none"

        page.reload(wait_until="networkidle")
        assert page.locator("#pilot-sponsor").input_value() == "Executive sponsor seat"
        page.locator("#clear-pilot").click()
        assert page.locator("#pilot-sponsor").input_value() == ""

        original_theme = page.locator("html").get_attribute("data-theme")
        page.locator("#theme").click()
        changed_theme = page.locator("html").get_attribute("data-theme")
        assert changed_theme in {"light", "dark"} and changed_theme != original_theme
        page.reload(wait_until="networkidle")
        assert page.locator("html").get_attribute("data-theme") == changed_theme

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(target("#run-mobility"), wait_until="networkidle")
        page.wait_for_function("document.querySelector('[data-scenario=\"mobility\"]').getAttribute('aria-selected') === 'true'")
        assert page.locator('[data-scenario="mobility"]').get_attribute("aria-selected") == "true"
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-live-mobile.png"), full_page=True)

        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(target("#run-continuity"), wait_until="networkidle")
        page.wait_for_function("document.querySelector('[data-scenario=\"continuity\"]').getAttribute('aria-selected') === 'true'")
        page.evaluate("document.documentElement.style.fontSize='200%'")
        page.wait_for_timeout(150)
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-live-320-200pct.png"), full_page=True)

        reduced = browser.new_context(viewport={"width": 1024, "height": 768}, reduced_motion="reduce")
        reduced_page = reduced.new_page()
        reduced_errors: list[str] = []
        reduced_page.on("pageerror", lambda exc: reduced_errors.append(str(exc)))
        reduced_page.goto(target("#run-wildfire"), wait_until="networkidle")
        reduced_page.locator('[data-scenario="mobility"]').click()
        assert "transportation path" in reduced_page.locator("#scenario-title").inner_text().lower()
        assert not reduced_errors, reduced_errors
        reduced.close()

        unexpected = [
            request for request in requests
            if urlparse(request).scheme in {"http", "https"}
            and not request.startswith(allowed_origin + "/")
        ]
        assert not unexpected, unexpected
        assert not request_failures, request_failures
        assert_http_clean(http_errors)
        assert not errors, errors
        browser.close()

    payload = {
        "schema": "manzanita-works/working-model-live-browser@1",
        "result": "PASS_LIVE_WORKING_MODEL_CHROMIUM_RELEASE_CAMPAIGN",
        "release": RELEASE,
        "source_sha": SOURCE_SHA,
        "page_url": URL,
        "scenarios": 4,
        "stages_per_scenario": 7,
        "pilot_gates": 5,
        "desktop_layout": "PASS",
        "mobile_390_layout": "PASS",
        "narrow_320_200pct_layout": "PASS_NO_DOCUMENT_OVERFLOW",
        "keyboard_navigation": "PASS",
        "incomplete_packet": "PASS_HELD",
        "complete_packet": "PASS_PREPARATION_NOT_ACCEPTANCE",
        "unexpected_cross_origin_requests": 0,
        "program_external_effect": "none",
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
