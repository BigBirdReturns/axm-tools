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


def wait_for_count(page, selector: str, expected: int) -> None:
    page.wait_for_function(
        "([selector, expected]) => document.querySelectorAll(selector).length === expected",
        [selector, expected],
    )


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

    page.wait_for_selector("#view-start.active")

    check("release title is operating cockpit", page.title() == "Essential Attention v1.1.0 · FAB Operating Cockpit")
    check("first visit opens orientation", page.locator("#helpDialog").evaluate("el => el.open"))
    check("six-step setup assistant is visible", page.locator("#startSetupChecklist .setup-step").count() == 6)
    check("setup begins at zero of six", "0 of 6" in page.locator("#startSetupProgress").inner_text().lower())
    check("loaded case inventories seven objects", page.locator("#startInventory .inventory-card").count() == 7)

    page.click("#helpCloseBottomButton")
    page.wait_for_timeout(100)
    check("orientation completion advances setup", "1 of 6" in page.locator("#startSetupProgress").inner_text().lower())

    page.click('[data-view="overview"]')
    page.wait_for_selector("#view-overview.active")
    check("operations home renders attention assistant", page.locator("#assistantQueue .assistant-item").count() >= 3)
    check("operations home renders readiness drilldowns", page.locator("#readinessGrid .readiness-card").count() == 4)
    check("operations home renders quick actions", page.locator(".home-command-strip button").count() == 5)
    check("operations home renders activity timeline", page.locator("#activityTimeline .timeline-item").count() >= 1)
    check("operations home renders recent records", page.locator("#recentObjects .recent-record").count() >= 1)
    check("held effects remain visible", page.locator("#heldEffects .effect-list span").count() == 6)

    page.select_option("#homeRoleSelect", "source-custodian")
    page.wait_for_timeout(100)
    check("role home filters the queue", "source" in page.locator("#homeRoleCopy").inner_text().lower())
    check("source role queue remains actionable", page.locator("#assistantQueue .assistant-item").count() >= 1)

    page.click("#guidanceButton")
    page.wait_for_timeout(150)
    check("guidance center opens", "open" in (page.locator("#guidanceDrawer").get_attribute("class") or ""))
    check("guidance carries setup progress", page.locator("#guidanceChecklist .setup-step").count() == 6)
    page.click("#closeGuidanceButton")
    page.wait_for_timeout(100)
    check("guidance center closes", "open" not in (page.locator("#guidanceDrawer").get_attribute("class") or ""))

    page.click('[data-view="register"]')
    page.wait_for_selector("#view-register.active")
    check("register list has seven records", page.locator("#offerList .offer-row").count() == 7)
    check("register provides five saved views", page.locator("#savedViews .saved-view").count() == 5)

    offer_ids = page.locator("#offerList .offer-row").evaluate_all("rows => rows.map(row => row.dataset.offerId)")
    for offer_id in offer_ids:
        page.locator(f'[data-offer-id="{offer_id}"]').click()
        page.wait_for_timeout(40)
    check("opening all records advances setup", "7 opened" in page.locator("#startSetupChecklist").inner_text())

    page.click('[data-register-mode="board"]')
    page.wait_for_timeout(100)
    check("process board has five columns", page.locator("#offerBoard .board-column").count() == 5)
    page.locator("#offerBoard .board-card").first.click()
    check("guided record dialog opens", page.locator("#detailDialog").evaluate("el => el.open"))
    check("guided record exposes seven-stage path", page.locator("#detailDialog .path-step").count() == 7)
    check("guided record exposes success guidance", page.locator("#detailDialog .guidance-for-success").count() == 1)
    check("guided record exposes four key fields", page.locator("#detailDialog .key-field").count() == 4)
    check("guided record exposes three tabs", page.locator("#detailDialog [data-record-tab]").count() == 3)
    page.click('#detailDialog [data-record-tab="related"]')
    check("related tab drills into records", page.locator("#detailDialog .related-row").count() >= 1)
    page.click("#closeDialogButton")

    page.click('[data-view="executive"]')
    page.wait_for_selector("#view-executive.active")
    check("decision queue has five questions", page.locator(".decision-card").count() == 5)
    decision_ids = page.locator("[data-review-decision]").evaluate_all("buttons => buttons.map(button => button.dataset.reviewDecision)")
    for decision_id in decision_ids:
        page.locator(f'[data-review-decision="{decision_id}"]').click()
        page.wait_for_timeout(40)
    check("all decisions reviewed", "5" in page.locator("#decisionSummary").inner_text())

    first_disposition = page.locator("[data-decision]").first
    first_disposition.click()
    check("bounded decision draft dialog opens", page.locator("#decisionDialog").evaluate("el => el.open"))
    page.fill("#decisionDraftRationale", "Bounded local qualification rationale. No external effect authorized.")
    page.click('#decisionDraftForm button[type="submit"]')
    page.wait_for_timeout(100)
    check("local draft appears in decision summary", "1" in page.locator("#decisionSummary").inner_text())

    page.click('[data-view="runtime"]')
    page.wait_for_selector("#view-runtime.active")
    page.click("#runSeatsButton")
    page.wait_for_timeout(500)
    check("contained run passes all seven seats", "7/7" in page.locator("#runSummary").inner_text())
    check("administrative spine has seven functions", page.locator("#functionSpine .spine-node").count() == 7)
    page.click("#testFirewallButton")
    page.wait_for_selector("#firewallResult .warning")
    check("external effect is visibly blocked", "external effect blocked" in page.locator("#firewallResult").inner_text().lower())

    page.click('[data-view="successor"]')
    page.fill("#replayObject", "mw-ea-n0-fab-offers-001")
    page.fill("#replayAuthority", "Contained internal processing only; external organizational authority remains outside the page")
    page.fill("#replayOpen", "Literal Meeting #1 offer sources and effect-specific authority receipts remain unresolved")
    page.fill("#replayNext", "Run source recovery, compile bounded packets, verify internal state, and export")
    page.click('#successorForm button[type="submit"]')
    page.wait_for_selector("#replayResult .success")
    check("cold continuity replay passes", "4/4" in page.locator("#replayResult").inner_text())

    page.click('[data-view="sources"]')
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write("synthetic FAB source for local browser qualification\n")
        tmp_path = Path(tmp.name)
    try:
        page.set_input_files("#sourceFiles", str(tmp_path))
        page.click("#hashSourcesButton")
        page.locator("#localSources .receipt").first.wait_for(state="visible")
        check("private source is hashed locally", page.locator("#localSources .receipt").count() >= 1)
    finally:
        tmp_path.unlink(missing_ok=True)

    page.click('[data-view="ledger"]')
    with page.expect_download() as download_info:
        page.click("#exportPacketButton")
    packet_path = Path(download_info.value.path())
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("portable packet exports active case", packet["cartridge"]["cartridge_id"] == "mw-ea-n0-fab-offers-001")
    check("portable packet carries local-state v3", packet["state"]["schema"] == "essential-attention/local-state@3")
    for _ in range(30):
        if "portable-export" in page.locator("#ledgerList").inner_text().lower():
            break
        page.wait_for_timeout(100)
    else:
        raise AssertionError("portable export receipt did not render")

    page.click('[data-view="start"]')
    check("setup assistant reaches six of six", "6 of 6 complete" in page.locator("#startSetupProgress").inner_text().lower())

    page.click("#helpStartTourButton" if page.locator("#helpDialog").evaluate("el => el.open") else "#startTourButton")
    page.wait_for_selector("#tourBar:not([hidden])")
    check("tour now has eight steps", "1 of 8" in page.locator("#tourCounter").inner_text().lower())
    for _ in range(7):
        page.click("#tourNextButton")
        page.wait_for_timeout(30)
    check("tour reaches export step", "8 of 8" in page.locator("#tourCounter").inner_text().lower())
    page.click("#tourNextButton")
    page.wait_for_selector("#tourBar", state="hidden")

    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    check("orientation is not forced after completion", not page.locator("#helpDialog").evaluate("el => el.open"))
    check("setup progress persists", "6 of 6" in page.locator("#startSetupProgress").inner_text().lower())
    page.click("#helpButton")
    check("help remains available on demand", page.locator("#helpDialog").evaluate("el => el.open"))
    page.click("#closeHelpButton")

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    mobile = page.evaluate(
        """() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          offenders: [...document.querySelectorAll('*')]
            .map((element) => {
              const rect = element.getBoundingClientRect();
              return {tag: element.tagName, id: element.id || '', className: typeof element.className === 'string' ? element.className.slice(0, 80) : '', left: rect.left, right: rect.right, width: rect.width};
            })
            .filter((item) => item.right > document.documentElement.clientWidth + 0.5 || item.left < -0.5)
            .slice(0, 12)
        })"""
    )
    check("mobile view has no horizontal overflow", mobile["scrollWidth"] <= mobile["clientWidth"], json.dumps(mobile))
    check("guidance remains visible on mobile", page.locator("#guidanceButton").is_visible())

    check("zero outbound network requests", len(external_requests) == 0, json.dumps(external_requests))
    check("zero JavaScript errors", len(page_errors) == 0, json.dumps(page_errors))
    check("zero console errors", len(console_errors) == 0, json.dumps(console_errors))

    browser.close()

print("\nEssential Attention operating cockpit: all assertions passed")
