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
OUT = Path(os.environ.get("EA_BROWSER_OUT", "/tmp/essential-attention-v1.2.1-browser"))
OUT.mkdir(parents=True, exist_ok=True)


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
    check("release title is operating desk", page.title() == "Essential Attention v1.2.1 · FAB Operating Desk")
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
    check("portable packet carries v1.2.1 build", packet["build"]["version"] == "1.2.1")
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

    page.screenshot(path=str(OUT / "operating-desk-mobile.png"), full_page=True)

    mila_context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    mila_page = mila_context.new_page()
    mila_errors: list[str] = []
    mila_console_errors: list[str] = []
    mila_page.on("pageerror", lambda error: mila_errors.append(str(error)))
    mila_page.on("console", lambda message: mila_console_errors.append(message.text) if message.type == "error" else None)
    if file_mode:
        mila_page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if not request.url.startswith(("data:", "blob:", "file:", "about:"))
            else None,
        )
        direct_mila_url = HTML.as_uri() + "?projection=mila&browser-test=1"
        ordinary_url = HTML.as_uri() + "?browser-test=1"
    else:
        mila_page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if not request.url.startswith(origin + "/")
            else None,
        )
        direct_mila_url = origin + "/essential-attention/?projection=mila&browser-test=1"
        ordinary_url = origin + "/essential-attention/?browser-test=1"

    mila_page.goto(direct_mila_url, wait_until="domcontentloaded")
    mila_page.wait_for_selector("#view-executive.active")
    check("Mila query route opens the decision projection", "mila-projection" in (mila_page.locator("body").get_attribute("class") or ""))
    check("Mila projection has a receiver-specific title", mila_page.title() == "Mila review · Essential Attention v1.2.1")
    check("Mila projection suppresses onboarding", not mila_page.locator("#helpDialog").evaluate("el => el.open"))
    check("Mila projection suppresses unrelated navigation", mila_page.locator('.seat-nav button:not([data-view="executive"])').evaluate_all("els => els.every(el => getComputedStyle(el).display === 'none')"))
    check("Mila projection shows three current queues", mila_page.locator("[data-mila-queue]").count() == 3)
    check("Mila projection preserves five decision cards", mila_page.locator(".decision-card").count() == 5)
    check("Mila projection exposes five explicit draft rows", mila_page.locator("[data-mila-draft]").count() == 5)
    check("Mila projection keeps silence unresolved", "silence remains unresolved" in mila_page.locator("#milaCommunicationState").inner_text().lower())
    mila_page.screenshot(path=str(OUT / "mila-review-desktop.png"), full_page=True)

    mila_page.locator("[data-decision]").first.click()
    check("Mila can draft one local disposition", mila_page.locator("#decisionDialog").evaluate("el => el.open"))
    mila_page.fill("#decisionDraftRationale", "Keep the meeting held until a named owner and evidence agenda exist.")
    mila_page.click('#decisionDraftForm button[type="submit"]')
    check("Mila draft ledger records one disposition", mila_page.locator(".mila-draft-row.is-drafted").count() == 1)
    with mila_page.expect_download() as mila_download:
        mila_page.click("#exportMilaPacketButton")
    mila_packet = json.loads(Path(mila_download.value.path()).read_text(encoding="utf-8"))
    check("Mila packet uses the dedicated schema", mila_packet["schema"] == "essential-attention/mila-review-packet@1")
    check("Mila packet carries the v1.2.1 build", mila_packet["release"] == "1.2.1" and mila_packet["build"]["version"] == "1.2.1")
    check("Mila packet carries all five decisions", len(mila_packet["decisions"]) == 5)
    check("Mila packet distinguishes one draft from four unresolved", mila_packet["decision_counts"]["local_drafts"] == 1 and mila_packet["decision_counts"]["unresolved"] == 4)
    check("Mila packet carries all three queues", set(mila_packet["queues"]) == {"authority_required", "accepted_obligations_at_risk", "evidence_ready_for_disposition"})
    check("Mila packet preserves unresolved recipient return", mila_packet["recipient_return_confirmation"]["status"] == "unresolved")
    check("Mila packet excludes participant and field records", mila_packet["privacy"]["participant_records"] == 0 and mila_packet["privacy"]["field_cases"] == 0)
    check("Mila packet excludes private source bytes", mila_packet["source_receipts"]["private_source_bytes_included"] is False and mila_packet["source_receipts"]["source_content_included"] is False and all(item["bytes_included"] is False for item in mila_packet["source_receipts"]["items"]))
    held_authority = ["institutional_acceptance", "participant_consent", "field_authority", "spend_authority", "assignment_authority", "calendar_authority", "payment_authority", "representation_authority", "publication_authority", "release_authority", "operator_acceptance"]
    check("Mila packet withholds every real-world authority", all(mila_packet["authority"][key] is False for key in held_authority) and mila_packet["authority"]["external_effect"] == "none")

    mila_page.reload(wait_until="domcontentloaded")
    mila_page.wait_for_selector("#view-executive.active")
    check("Mila direct route preserves the local draft", mila_page.locator(".mila-draft-row.is-drafted").count() == 1)
    mila_page.goto(ordinary_url, wait_until="domcontentloaded")
    mila_page.wait_for_selector("#view-overview.active")
    check("ordinary route remains unchanged", mila_page.title() == "Essential Attention v1.2.1 · FAB Operating Desk")
    check("direct Mila route did not consume first-use orientation", mila_page.locator("#helpDialog").evaluate("el => el.open"))
    mila_page.click("#helpCloseBottomButton")
    mila_page.goto(ordinary_url + "#mila", wait_until="domcontentloaded")
    mila_page.wait_for_selector("#view-executive.active")
    check("Mila hash alias opens the same projection", "mila-projection" in (mila_page.locator("body").get_attribute("class") or "") and not mila_page.locator("#helpDialog").evaluate("el => el.open"))

    mila_page.set_viewport_size({"width": 320, "height": 800})
    mila_page.evaluate("document.documentElement.style.fontSize='200%'")
    mila_page.wait_for_timeout(120)
    mila_geometry = mila_page.evaluate("""() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      exportWidth: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().width,
      exportHeight: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().height
    })""")
    check("Mila projection remains bounded at 320px and 200 percent text", mila_geometry["scrollWidth"] <= mila_geometry["clientWidth"], json.dumps(mila_geometry))
    check("Mila export remains operable at narrow text zoom", mila_geometry["exportWidth"] > 0 and mila_geometry["exportHeight"] >= 44, json.dumps(mila_geometry))
    mila_page.screenshot(path=str(OUT / "mila-review-320-200pct.png"), full_page=True)
    check("Mila projection has zero JavaScript errors", len(mila_errors) == 0, json.dumps(mila_errors))
    check("Mila projection has zero console errors", len(mila_console_errors) == 0, json.dumps(mila_console_errors))
    mila_context.close()

    reduced = browser.new_context(viewport={"width": 900, "height": 700}, reduced_motion="reduce").new_page()
    reduced.goto(origin + "/essential-attention/?reduced-motion=1", wait_until="domcontentloaded")
    reduced_animation = reduced.locator("#view-overview").evaluate("el => getComputedStyle(el).animationName")
    check("reduced-motion preference disables entrance animation", reduced_animation == "none", reduced_animation)
    reduced.context.close()

    check("zero outbound network requests", len(external_requests) == 0, json.dumps(external_requests))
    check("zero JavaScript errors", len(page_errors) == 0, json.dumps(page_errors))
    check("zero console errors", len(console_errors) == 0, json.dumps(console_errors))
    result = {
        "schema": "essential-attention/browser-qualification@5",
        "release": "1.2.1",
        "ordinary_operating_desk": "PASS",
        "mila_query_projection": "PASS",
        "mila_hash_projection": "PASS",
        "mila_review_packet": "PASS",
        "mila_silence_invariant": "PASS_UNRESOLVED_WITHOUT_MOTIVE_INFERENCE",
        "private_source_bytes_in_mila_packet": 0,
        "participant_records": 0,
        "field_cases": 0,
        "external_effect": "none",
        "screenshots": ["operating-desk-mobile.png", "mila-review-desktop.png", "mila-review-320-200pct.png"],
    }
    (OUT / "browser-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    browser.close()

print("\nEssential Attention v1.2.1 operating desk and Mila return projection: all assertions passed")
