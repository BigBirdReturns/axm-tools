from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "essential-attention" / "index.html"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def check(name: str, condition: bool, detail: str = "") -> None:
    prefix = "  ok " if condition else "FAIL "
    print(f"{prefix} {name}{' — ' + detail if detail and not condition else ''}")
    if not condition:
        raise AssertionError(f"{name}: {detail}")


with serve_root() as origin, sync_playwright() as p:
    executable = os.environ.get("AXM_CHROMIUM_PATH")
    browser = p.chromium.launch(headless=True, executable_path=executable if executable else None)
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page = context.new_page()
    page_errors: list[str] = []
    console_errors: list[str] = []
    external_requests: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)

    file_mode = os.environ.get("EA_FILE_MODE") == "1"
    if file_mode:
        page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if not request.url.startswith(("data:", "blob:", "file:", "about:"))
            else None,
        )
        page.goto(HTML.as_uri() + "?browser-test=1", wait_until="domcontentloaded")
    else:
        page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if not request.url.startswith(origin + "/")
            else None,
        )
        page.goto(origin + "/essential-attention/?browser-test=1", wait_until="domcontentloaded")

    page.wait_for_selector("#view-overview.active")
    check("release title is operating desk", page.title() == "Essential Attention v1.2.0 · FAB Operating Desk")
    check("first visit opens compact orientation", page.locator("#helpDialog").evaluate("el => el.open"))
    check("primary navigation has five places", page.locator(".seat-nav button").count() == 5)
    check(
        "primary navigation uses ordinary labels",
        page.locator(".seat-nav button").all_inner_texts()
        == ["01\nTODAY", "02\nRECORDS", "03\nDECISIONS", "04\nEVIDENCE", "05\nHANDOFF"],
    )
    page.click("#helpCloseBottomButton")
    page.wait_for_timeout(100)

    check("Today renders four conditions", page.locator("#todayStatus .desk-status-item").count() == 4)
    check("Today renders one best action", page.locator("#primaryAction #openPrimaryAction").count() == 1)
    check("Today limits secondary work to three moves", page.locator("#assistantQueue .safe-move").count() == 3)
    check("Today keeps recent records visible", page.locator("#recentObjects .recent-record").count() >= 1)
    check("Today keeps six external effects held", page.locator("#heldEffects .effect-list span").count() == 6)

    page.click("#helpButton")
    page.click("#helpStartTourButton")
    page.wait_for_selector("#tourBar:not([hidden])")
    check("optional tour has five steps", "1 of 5" in page.locator("#tourCounter").inner_text().lower())
    for _ in range(4):
        page.click("#tourNextButton")
        page.wait_for_timeout(30)
    check("tour reaches Handoff", "5 of 5" in page.locator("#tourCounter").inner_text().lower())
    page.click("#tourNextButton")
    page.wait_for_selector("#tourBar", state="hidden")

    page.click('[data-view="register"]')
    check("Records has seven case files", page.locator("#offerList .offer-row").count() == 7)
    page.fill("#registerSearch", "catnip")
    check("Records search narrows in place", page.locator("#offerList .offer-row").count() == 1)
    page.click("#clearRegisterFilters")
    page.locator("#offerList .offer-row").first.click()
    page.locator("[data-open-offer]").click()
    check("record opens as a modal case file", page.locator("#detailDialog").evaluate("el => el.open"))
    check("record starts with what happened", page.locator("#detailDialog .record-summary").count() == 1)
    check("record exposes four ordinary facts", page.locator("#detailDialog .record-fact").count() == 4)
    check("record has three progressive tabs", page.locator("#detailDialog [data-record-tab]").count() == 3)
    check("record defaults to Summary", page.locator('#detailDialog [data-record-tab="summary"]').get_attribute("class") == "active")
    page.click('#detailDialog [data-record-tab="details"]')
    check("Evidence and authority details are available", page.locator("#detailDialog .details-grid .detail").count() == 8)
    page.click('#detailDialog [data-record-tab="activity"]')
    check("record activity travels with the case", page.locator("#detailDialog .timeline-item").count() >= 1)
    page.click("#closeDialogButton")

    page.click('[data-view="executive"]')
    check("Decisions has five bounded questions", page.locator(".decision-card").count() == 5)
    page.locator("[data-decision]").first.click()
    check("decision draft opens locally", page.locator("#decisionDialog").evaluate("el => el.open"))
    page.fill("#decisionDraftRationale", "Bounded local qualification rationale. No external effect authorized.")
    page.click('#decisionDraftForm button[type="submit"]')
    check("local draft is recorded", "1" in page.locator("#decisionSummary").inner_text())

    page.click('[data-view="sources"]')
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write("synthetic FAB source for local browser qualification\n")
        tmp_path = Path(tmp.name)
    try:
        page.set_input_files("#sourceFiles", str(tmp_path))
        page.click("#hashSourcesButton")
        page.locator("#localSources .receipt").first.wait_for(state="visible")
        check("Evidence hashes a private file locally", page.locator("#localSources .receipt").count() == 1)
    finally:
        tmp_path.unlink(missing_ok=True)

    page.click('[data-view="handoff"]')
    check("Handoff presents three ordinary steps", page.locator(".handoff-step").count() == 3)
    page.click("#handoffRunButton")
    check("Handoff internal check passes seven functions", "7/7" in page.locator("#handoffRunStatus").inner_text())
    page.click("#handoffReplayButton")
    page.fill("#replayObject", "mw-ea-n0-fab-offers-001")
    page.fill("#replayAuthority", "Contained internal processing only; external organizational authority remains outside the page")
    page.fill("#replayOpen", "Literal Meeting #1 offer sources and effect-specific authority receipts remain unresolved")
    page.fill("#replayNext", "Run source recovery, compile bounded packets, verify internal state, and export")
    page.click('#successorForm button[type="submit"]')
    page.wait_for_selector("#replayResult .success")
    page.click('[data-view="handoff"]')
    check("Handoff records cold continuity", "passed" in page.locator("#handoffReplayStatus").inner_text().lower())
    with page.expect_download() as download_info:
        page.click("#exportPacketButton")
    packet = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
    check("portable packet carries v1.2.0 build", packet["build"]["version"] == "1.2.0")
    for _ in range(30):
        if "recorded" in page.locator("#handoffExportStatus").inner_text().lower():
            break
        page.wait_for_timeout(100)
    check("Handoff records portable export", "recorded" in page.locator("#handoffExportStatus").inner_text().lower())

    page.locator(".advanced-tools summary").click()
    check("advanced machinery remains available", page.locator(".advanced-tool-grid button").count() == 8)
    page.click('.advanced-tool-grid [data-go="runtime"]')
    page.click("#testFirewallButton")
    page.wait_for_selector("#firewallResult .warning")
    check("effect firewall still blocks release", "external effect blocked" in page.locator("#firewallResult").inner_text().lower())

    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    check("orientation is not forced after completion", not page.locator("#helpDialog").evaluate("el => el.open"))
    check("local source receipt persists", page.locator("#localSources .receipt").count() == 1)

    page.set_viewport_size({"width": 390, "height": 844})
    page.click('[data-view="overview"]')
    mobile = page.evaluate(
        """() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          primaryWidth: document.querySelector('.primary-action-card').getBoundingClientRect().width,
          navVisible: [...document.querySelectorAll('.seat-nav button')].every(button => button.getBoundingClientRect().height > 0)
        })"""
    )
    check("mobile view has no page-level horizontal overflow", mobile["scrollWidth"] <= mobile["clientWidth"], json.dumps(mobile))
    check("mobile keeps the primary action within viewport", mobile["primaryWidth"] <= mobile["clientWidth"], json.dumps(mobile))
    check("mobile keeps all five places available", mobile["navVisible"], json.dumps(mobile))

    reduced = browser.new_context(viewport={"width": 900, "height": 700}, reduced_motion="reduce").new_page()
    reduced.goto(origin + "/essential-attention/?reduced-motion=1", wait_until="domcontentloaded")
    reduced_animation = reduced.locator("#view-overview").evaluate("el => getComputedStyle(el).animationName")
    check("reduced-motion preference disables entrance animation", reduced_animation == "none", reduced_animation)
    reduced.context.close()

    check("zero outbound network requests", len(external_requests) == 0, json.dumps(external_requests))
    check("zero JavaScript errors", len(page_errors) == 0, json.dumps(page_errors))
    check("zero console errors", len(console_errors) == 0, json.dumps(console_errors))
    browser.close()

print("\nEssential Attention operating desk: all assertions passed")
