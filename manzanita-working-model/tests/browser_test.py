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
    observation = page.evaluate("""() => {
      const viewport = document.documentElement.clientWidth;
      const docOverflow = document.documentElement.scrollWidth - viewport;
      const bodyOverflow = document.body.scrollWidth - document.body.clientWidth;
      const offenders = [...document.querySelectorAll('*')].map((el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
          tag: el.tagName.toLowerCase(),
          id: el.id || null,
          cls: typeof el.className === 'string' ? el.className : null,
          text: (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 100),
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth,
          overflowX: style.overflowX,
          minWidth: style.minWidth,
          whiteSpace: style.whiteSpace
        };
      }).filter((row) => row.right > viewport + 1 || row.left < -1)
        .sort((a, b) => b.right - a.right)
        .slice(0, 25);
      return { viewport, docOverflow, bodyOverflow, offenders };
    }""")
    if observation["docOverflow"] > 1 or observation["bodyOverflow"] > 1:
        raise AssertionError(json.dumps(observation, indent=2))


def assert_local_only(requests: list[str]) -> None:
    unexpected = []
    for request in requests:
        parsed = urlparse(request)
        if parsed.scheme in {"http", "https"} and parsed.hostname not in {"127.0.0.1", "localhost"}:
            unexpected.append(request)
    assert not unexpected, unexpected


def assert_http_clean(http_errors: list[dict[str, object]]) -> None:
    # Chromium may probe /favicon.ico when a document has no icon declaration.
    # Treat only that UA-originated, non-semantic request as ignorable. Every
    # candidate CSS, script, image, page, or other 4xx/5xx response remains fatal.
    failures = []
    for item in http_errors:
        path = urlparse(str(item["url"])).path
        if path == "/favicon.ico" and item["status"] == 404:
            continue
        failures.append(item)
    assert not failures, failures


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
        http_errors: list[dict[str, object]] = []
        page.on(
            "console",
            lambda msg: errors.append(f"console:{msg.type}:{msg.text}")
            if msg.type == "error" and not msg.text.startswith("Failed to load resource:")
            else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        page.on("request", lambda request: requests.append(request.url))
        page.on(
            "response",
            lambda response: http_errors.append({"url": response.url, "status": response.status})
            if response.status >= 400
            else None,
        )

        page.goto(url, wait_until="networkidle")
        assert page.locator('meta[name="mw-release"]').get_attribute("content") == "mw-working-model-v1.0.0"
        assert page.locator(".scenario-tab").count() == 4
        assert page.locator(".stage-card").count() == 7
        assert page.locator(".decision-number").count() == 5
        assert page.locator(".proof-card").count() == 4
        assert page.locator(".proof-instrument").count() == 4
        assert page.locator(".proof-symbol").count() == 0
        assert page.locator("main img").count() == 0
        assert page.locator("#theme").count() == 0
        assert page.locator(".compression-band").count() == 0
        assert page.locator(".capacity-section").count() == 0
        assert page.locator(".hero-console").count() == 1
        assert page.locator(".console-grammar li").count() == 7
        assert page.locator(".console-ledger > div").count() == 4
        assert page.locator(".place-stack li").count() == 7
        assert page.locator(".attention-stack li").count() == 5
        assert page.locator(".organ-grid span").count() == 6
        assert page.locator(".source-chain li").count() == 4
        assert page.locator(".role-strip span").count() == 5
        assert "no adverse use" in page.locator(".instrument-foot").all_inner_texts()[0].lower()
        assert "Silence creates no consent" in page.locator(".invariant").inner_text()
        assert "N=0" not in page.locator("body").inner_text()
        assert page.locator("html").get_attribute("data-theme") is None
        skip = page.locator(".skip")
        assert skip.evaluate("el => el.getBoundingClientRect().width <= 1")
        skip.focus()
        assert skip.evaluate("el => el.getBoundingClientRect().width > 1")
        page.evaluate("document.activeElement.blur()")
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-desktop.png"), full_page=True)

        expected = {
            "wildfire": ("wildfire exposure", "parcel score"),
            "tools": ("tool", "silent assignment"),
            "mobility": ("transportation path", "vehicle availability"),
            "continuity": ("good idea", "silence into rejection"),
        }
        expected_stages = ["signal", "source", "authority", "safe action", "fallback", "closure", "learning"]
        for scenario, (title_fragment, prohibited_fragment) in expected.items():
            page.locator(f'[data-scenario="{scenario}"]').click()
            assert title_fragment.lower() in page.locator("#scenario-title").inner_text().lower()
            assert prohibited_fragment.lower() in page.locator("#scenario-prohibited").inner_text().lower()
            assert page.locator(".stage-card").count() == 7
            stages = [value.strip().lower() for value in page.locator(".stage-card h4").all_inner_texts()]
            assert stages == expected_stages, stages

        first = page.locator('[data-scenario="wildfire"]')
        first.focus()
        page.keyboard.press("ArrowRight")
        assert page.locator('[data-scenario="tools"]').get_attribute("aria-selected") == "true"
        assert "tool" in page.locator("#scenario-title").inner_text().lower()

        page.locator("#pilot-scenario").select_option("tools")
        page.locator("#pilot-sponsor").fill("Executive sponsor seat")
        assert "1 of 5" in page.locator("#form-status").inner_text()
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        incomplete_path = OUT / "pilot-incomplete.json"
        download_info.value.save_as(str(incomplete_path))
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
        for field in [
            "institutional_acceptance", "participant_consent", "field_authority",
            "spend_authority", "publication_authority", "assignment_authority",
            "representation_authority", "release_authority",
        ]:
            assert complete["authority"][field] is False, field
        assert complete["authority"]["external_effect"] == "none"
        assert complete["invariant"]["silence_law"].startswith("Silence is not consent")

        page.reload(wait_until="networkidle")
        assert page.locator("#pilot-sponsor").input_value() == "Executive sponsor seat"
        assert page.locator("#pilot-operator").input_value() == "Funded continuity operator seat"
        page.locator("#clear-pilot").click()
        assert page.locator("#pilot-sponsor").input_value() == ""
        assert "0 of 5" in page.locator("#form-status").inner_text()
        page.reload(wait_until="networkidle")
        assert page.locator("#pilot-sponsor").input_value() == ""


        # Same-document fragment changes must update the governed scenario;
        # a cold-load-only deep link leaves ordinary in-tab navigation stale.
        page.evaluate("location.hash = '#run-mobility'")
        page.wait_for_function("document.querySelector('[data-scenario=\"mobility\"]').getAttribute('aria-selected') === 'true'")
        assert "transportation path" in page.locator("#scenario-title").inner_text().lower()

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(url + "#run-wildfire", wait_until="networkidle")
        assert page.locator('[data-scenario="wildfire"]').get_attribute("aria-selected") == "true"
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-mobile.png"), full_page=True)

        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(url + "#run-continuity", wait_until="networkidle")
        page.evaluate("document.documentElement.style.fontSize='200%'")
        page.wait_for_timeout(150)

        heading = page.locator(".handoff-box h2")
        assert heading.evaluate("""el => {
          const node = Array.from(el.childNodes).find(item => item.nodeType === Node.TEXT_NODE);
          if (!node) return false;
          const text = node.textContent || '';
          const words = [...text.matchAll(/\S+/g)];
          return words.every(match => {
            const range = document.createRange();
            range.setStart(node, match.index);
            range.setEnd(node, match.index + match[0].length);
            return range.getClientRects().length === 1;
          });
        }""")
        assert page.locator("#pilot-operator").get_attribute("placeholder") == "Operator unresolved"
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "working-model-320-200pct.png"), full_page=True)

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
        assert_http_clean(http_errors)
        assert not errors, errors
        browser.close()

    print(json.dumps({
        "result": "PASS_WORKING_MODEL_CHROMIUM_RELEASE_CAMPAIGN",
        "release": "mw-working-model-v1.0.0",
        "scenarios": 4,
        "stages_per_scenario": 7,
        "pilot_gates": 5,
        "external_effect": "none",
        "screenshots": [
            "working-model-desktop.png",
            "working-model-mobile.png",
            "working-model-320-200pct.png"
        ]
    }, indent=2))


if __name__ == "__main__":
    main()
