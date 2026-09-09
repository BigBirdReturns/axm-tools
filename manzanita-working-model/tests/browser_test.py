#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import os
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("MW_WORKING_MODEL_SCREENSHOT_DIR", "/tmp/manzanita-working-model-v1.1-review"))
OUT.mkdir(parents=True, exist_ok=True)
RELEASE = "mw-working-model-v1.1.0"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@contextlib.contextmanager
def serve():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def assert_no_overflow(page: Page) -> None:
    result = page.evaluate("""() => ({
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth
    })""")
    assert result["document"] <= 1 and result["body"] <= 1, result


def assert_text_floor(page: Page, floor: float = 11.0) -> None:
    offenders = page.evaluate("""(floor) => {
      const rows = [];
      for (const element of document.querySelectorAll('body *')) {
        const style = getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        const ownText = [...element.childNodes]
          .filter(node => node.nodeType === Node.TEXT_NODE)
          .map(node => node.textContent || '')
          .join(' ')
          .trim();
        if (!ownText) continue;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        const size = parseFloat(style.fontSize);
        if (size < floor) rows.push({tag: element.tagName, className: element.className, size, text: ownText.slice(0, 90)});
      }
      return rows;
    }""", floor)
    assert not offenders, offenders[:20]


def assert_height_budget(page: Page, maximum: int) -> int:
    height = int(page.evaluate("document.documentElement.scrollHeight"))
    assert height <= maximum, {"height": height, "maximum": maximum}
    return height


def assert_control_targets(page: Page) -> None:
    offenders = page.evaluate("""() => {
      const selector = 'button, input, select, textarea, .button, .nav-cta';
      return [...document.querySelectorAll(selector)].flatMap(element => {
        const style = getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden') return [];
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0 || rect.height >= 44) return [];
        return [{tag: element.tagName, id: element.id, className: element.className, height: rect.height}];
      });
    }""")
    assert not offenders, offenders


def assert_desktop_composition(page: Page) -> None:
    geometry = page.evaluate("""() => {
      const rect = selector => {
        const r = document.querySelector(selector).getBoundingClientRect();
        return {x:r.x, y:r.y, width:r.width, height:r.height, right:r.right, bottom:r.bottom};
      };
      return {
        hero: rect('.hero'),
        copy: rect('.hero-copy'),
        runtime: rect('.case-runtime'),
        tabs: [...document.querySelectorAll('.scenario-tab')].map(el => {
          const r = el.getBoundingClientRect(); return {x:r.x, y:r.y, width:r.width, height:r.height};
        }),
        cards: [...document.querySelectorAll('.system-card')].map(el => {
          const r = el.getBoundingClientRect(); return {x:r.x, y:r.y, width:r.width, height:r.height};
        })
      };
    }""")
    assert geometry["runtime"]["x"] > geometry["copy"]["x"], geometry
    assert geometry["runtime"]["width"] >= 520, geometry
    assert max(abs(row["y"] - geometry["tabs"][0]["y"]) for row in geometry["tabs"]) <= 1, geometry["tabs"]
    assert min(row["width"] for row in geometry["tabs"]) >= 250, geometry["tabs"]
    assert len({round(row["y"]) for row in geometry["cards"]}) == 2, geometry["cards"]
    assert min(row["width"] for row in geometry["cards"]) >= 570, geometry["cards"]


def assert_skip_link_and_anchor_clearance(page: Page) -> None:
    hidden_top = page.locator('.skip-link').evaluate("element => element.getBoundingClientRect().top")
    assert hidden_top < 0, hidden_top
    page.locator('.skip-link').focus()
    visible_top = page.locator('.skip-link').evaluate("element => element.getBoundingClientRect().top")
    assert visible_top >= 0, visible_top
    page.evaluate("document.activeElement.blur()")
    page.locator('a[href="#systems"]').click()
    page.wait_for_timeout(120)
    clearance = page.evaluate("""() => ({
      headerBottom: document.querySelector('.site-header').getBoundingClientRect().bottom,
      headingTop: document.querySelector('#systems .section-header').getBoundingClientRect().top
    })""")
    assert clearance["headingTop"] >= clearance["headerBottom"] - 1, clearance
    page.evaluate("window.scrollTo(0, 0)")


def prepare_screenshot(page: Page) -> None:
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0, 0)")
    page.wait_for_timeout(80)


def main() -> None:
    with serve() as base_url, sync_playwright() as playwright:
        launch: dict[str, object] = {"headless": True}
        executable = os.environ.get("MW_CHROMIUM_EXECUTABLE")
        if executable:
            launch.update({"executable_path": executable, "args": ["--no-sandbox"]})
        browser = playwright.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1600, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors: list[str] = []
        requests: list[str] = []
        request_failures: list[str] = []
        http_errors: list[dict[str, object]] = []
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
        page.on("request", lambda request: requests.append(request.url))
        page.on("requestfailed", lambda request: request_failures.append(f"{request.url}: {request.failure}"))
        page.on("response", lambda response: http_errors.append({"url": response.url, "status": response.status}) if response.status >= 400 else None)

        page.goto(base_url + "#run-wildfire", wait_until="networkidle")
        assert page.locator('meta[name="mw-release"]').get_attribute("content") == RELEASE
        assert page.locator("main img").count() == 0
        assert page.locator(".scenario-tab").count() == 4
        assert page.locator(".stage-list li").count() == 7
        assert page.locator(".system-card").count() == 4
        assert page.locator(".guardrail-grid article").count() == 3
        assert page.locator(".gate-map li").count() == 5
        assert page.locator(".runtime-trace li").count() == 4
        assert page.locator(".capacity-instrument i").count() == 0
        assert page.locator(".capacity-instrument > div").count() == 6
        assert page.locator("#pilot-problem").count() == 1
        body = page.locator("body").inner_text()
        for stale in ["Not another architecture review", "public-safe", "If leadership returns tomorrow", "Do not schedule a scoping call", "N=0"]:
            assert stale not in body, stale
        assert_no_overflow(page)
        assert_text_floor(page)
        assert_control_targets(page)
        assert_skip_link_and_anchor_clearance(page)
        desktop_height = assert_height_budget(page, 7000)
        assert_desktop_composition(page)
        prepare_screenshot(page)
        page.screenshot(path=str(OUT / "working-model-v1.1-desktop.png"), full_page=True)

        expected = {
            "wildfire": ("wildfire exposure", "parcel score"),
            "tools": ("tool", "silent volunteer"),
            "mobility": ("transportation path", "availability"),
            "continuity": ("good idea", "silence into rejection"),
        }
        expected_stages = ["need", "evidence", "decision owner", "safe next step", "backup path", "outcome", "next improvement"]
        for scenario, (title_fragment, prohibited_fragment) in expected.items():
            page.locator(f'[data-scenario="{scenario}"]').click()
            assert title_fragment in page.locator("#scenario-title").inner_text().lower()
            assert prohibited_fragment in page.locator("#scenario-prohibited").inner_text().lower()
            assert [value.strip().lower() for value in page.locator(".stage-list h4").all_inner_texts()] == expected_stages
            assert page.locator(f'[data-scenario="{scenario}"]').get_attribute("aria-selected") == "true"
            assert page.url.endswith(f"#run-{scenario}")

        page.locator('[data-scenario="wildfire"]').focus()
        page.keyboard.press("ArrowRight")
        assert page.locator('[data-scenario="tools"]').get_attribute("aria-selected") == "true"
        page.evaluate("location.hash = '#run-mobility'")
        page.wait_for_function("document.querySelector('[data-scenario=\"mobility\"]').getAttribute('aria-selected') === 'true'")
        assert page.locator("#form-status").inner_text().startswith("0 of 5")

        page.locator("#pilot-problem").fill("Residents without reliable cars cannot reach evening appointments after the fixed-route service ends.")
        page.locator("#pilot-sponsor").fill("Accountable sponsor seat")
        assert page.locator("#form-status").inner_text().startswith("2 of 5")
        assert page.locator('[data-gate="problem"]').get_attribute("class").find("is-resolved") >= 0
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        incomplete_path = OUT / "pilot-v1.1-incomplete.json"
        download_info.value.save_as(str(incomplete_path))
        incomplete = json.loads(incomplete_path.read_text(encoding="utf-8"))
        assert incomplete["release"] == RELEASE
        assert incomplete["standing"] == "INCOMPLETE_PREPARATION_HELD"
        assert incomplete["organizational_gates"]["named_count"] == 2
        assert incomplete["organizational_gates"]["problem"]["complete"] is True
        assert "evening appointments" in incomplete["organizational_gates"]["problem"]["statement"]
        assert incomplete["organizational_gates"]["continuity_operator"] == "UNRESOLVED"
        assert incomplete["authority"]["institutional_acceptance"] is False
        assert incomplete["authority"]["external_effect"] == "none"

        page.locator("#pilot-operator").fill("Funded continuity operator")
        page.locator("#pilot-basis").fill("One venue, one participant class, defined resources, lawful access, and named partners.")
        page.locator("#pilot-stop").fill("Stop if authority, consent, source quality, or operator capacity is absent.")
        assert page.locator("#form-status").inner_text().startswith("5 of 5")
        assert page.locator(".gate-map li.is-resolved").count() == 5
        with page.expect_download() as download_info:
            page.locator("#export-pilot").click()
        complete_path = OUT / "pilot-v1.1-complete.json"
        download_info.value.save_as(str(complete_path))
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
        assert complete["standing"] == "PREPARED_FOR_ACCOUNTABLE_REVIEW_NOT_ACCEPTED"
        assert complete["organizational_gates"]["named_count"] == 5
        assert complete["organizational_gates"]["problem"]["case_type"]["id"] == "mobility"
        assert [stage["id"] for stage in complete["operating_case"]["grammar"]] == ['signal', 'source', 'authority', 'safe_action', 'fallback', 'closure', 'learning']
        assert [stage["name"].lower() for stage in complete["operating_case"]["grammar"]] == expected_stages
        for field in ["institutional_acceptance", "participant_consent", "field_authority", "spend_authority", "assignment_authority", "representation_authority", "publication_authority", "release_authority"]:
            assert complete["authority"][field] is False, field
        assert complete["authority"]["external_effect"] == "none"

        page.reload(wait_until="networkidle")
        assert "evening appointments" in page.locator("#pilot-problem").input_value()
        assert page.locator("#pilot-sponsor").input_value() == "Accountable sponsor seat"
        page.locator("#clear-pilot").click()
        assert page.locator("#pilot-scenario").input_value() == ""
        assert page.locator("#pilot-problem").input_value() == ""
        assert page.locator("#form-status").inner_text().startswith("0 of 5")
        assert page.locator(".gate-map li.is-resolved").count() == 0

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(base_url + "#run-mobility", wait_until="networkidle")
        assert page.locator('[data-scenario="mobility"]').get_attribute("aria-selected") == "true"
        assert page.locator('.site-header').evaluate("element => getComputedStyle(element).position") == "static"
        assert page.locator('.scenario-tabs').evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length") == 2
        assert page.locator('.stage-list').evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length") == 2
        assert page.locator('.gate-map ol').evaluate("element => getComputedStyle(element).display") == "none"
        assert_no_overflow(page)
        assert_text_floor(page)
        assert_control_targets(page)
        mobile_height = assert_height_budget(page, 9500)
        assert page.locator(".system-card").first.evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length") == 1
        prepare_screenshot(page)
        page.screenshot(path=str(OUT / "working-model-v1.1-mobile.png"), full_page=True)

        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(base_url + "#run-continuity", wait_until="networkidle")
        page.evaluate("document.documentElement.style.fontSize = '200%'")
        page.wait_for_timeout(150)
        assert page.locator('.scenario-tabs').evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length") == 1
        assert page.locator('.stage-list').evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length") == 1
        assert_no_overflow(page)
        assert_text_floor(page, 11.0)
        narrow_height = assert_height_budget(page, 14500)
        prepare_screenshot(page)
        page.evaluate("document.documentElement.style.fontSize = '200%'")
        page.screenshot(path=str(OUT / "working-model-v1.1-320-200pct.png"), full_page=True)

        reduced_context = browser.new_context(viewport={"width": 1024, "height": 768}, reduced_motion="reduce")
        reduced_page = reduced_context.new_page()
        reduced_page.goto(base_url + "#run-wildfire", wait_until="networkidle")
        reduced_page.locator('[data-scenario="mobility"]').click()
        assert "transportation path" in reduced_page.locator("#scenario-title").inner_text().lower()
        reduced_context.close()

        allowed_origin = base_url.rstrip("/")
        unexpected = [url for url in requests if urlparse(url).scheme in {"http", "https"} and not url.startswith(allowed_origin + "/")]
        assert not unexpected, unexpected
        assert not request_failures, request_failures
        assert not http_errors, http_errors
        assert not errors, errors
        browser.close()

    payload = {
        "schema": "manzanita-works/working-model-browser-qualification@5",
        "result": "PASS_WORKING_MODEL_CHROMIUM_RELEASE_CAMPAIGN",
        "release": RELEASE,
        "scenarios": 4,
        "stages_per_scenario": 7,
        "hero_state_rows": 4,
        "pilot_gates": 5,
        "concrete_problem_required": True,
        "receiver_stage_labels": "PASS",
        "stable_stage_ids_in_export": "PASS",
        "rendered_images": 0,
        "synthetic_capacity_metrics": 0,
        "desktop_height": desktop_height,
        "mobile_height": mobile_height,
        "narrow_320_200pct_height": narrow_height,
        "minimum_text_floor_css_px": 11,
        "minimum_control_height_css_px": 44,
        "desktop_composition": "PASS",
        "mobile_two_column_case_compression": "PASS",
        "mobile_duplicate_gate_map_hidden": "PASS",
        "sticky_header_anchor_clearance": "PASS",
        "skip_link_hidden_until_focus": "PASS",
        "keyboard_navigation": "PASS",
        "hash_navigation": "PASS",
        "local_persistence_and_clear": "PASS",
        "incomplete_packet": "PASS_HELD_WITH_PARTIAL_GATES_PRESERVED",
        "complete_packet": "PASS_REVIEW_NOT_ACCEPTANCE",
        "unexpected_cross_origin_requests": 0,
        "external_effect": "none",
        "screenshots": ["working-model-v1.1-desktop.png", "working-model-v1.1-mobile.png", "working-model-v1.1-320-200pct.png"],
    }
    (OUT / "browser-result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
