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
    external_requests: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("request", lambda request: external_requests.append(request.url) if not request.url.startswith(origin + "/") else None)

    url = origin + "/essential-attention/?browser-test=1"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("#view-start.active")

    check("first visit opens the orientation dialog", page.locator("#helpDialog").evaluate("el => el.open"))
    check("first screen says what the case is", "working case file" in page.locator("#view-start").inner_text().lower())
    check("start view inventories seven objects", page.locator("#startInventory .inventory-card").count() == 7)
    check("start view exposes a practical route", page.locator("#view-start .journey-step").count() == 6)

    page.click("#helpStartTourButton")
    page.wait_for_selector("#tourBar:not([hidden])")
    check("tour starts on Start here", page.locator("#view-start").evaluate("el => el.classList.contains('active')"))
    check("tour announces step one", "1 OF 7" in page.locator("#tourCounter").inner_text())

    expected = [
        ("register", 7, ".offer-row"),
        ("executive", 5, ".decision-card"),
        ("runtime", 7, "#roleTableBody tr"),
        ("successor", 1, "#successorForm"),
        ("sources", 1, "#sourceFiles"),
        ("ledger", 1, "#exportLedgerButton"),
    ]
    for view, count, selector in expected:
        page.click("#tourNextButton")
        page.wait_for_selector(f"#view-{view}.active")
        check(f"tour reaches {view}", page.locator(selector).count() == count, f"count={page.locator(selector).count()}")
        if view == "runtime":
            page.click("#runSeatsButton")
            page.wait_for_timeout(400)
            check("contained run passes all seven seats", "7/7" in page.locator("#runSummary").inner_text())
            page.click("#testFirewallButton")
            page.wait_for_selector("#firewallResult .warning")
            check("external effect is visibly blocked", "external effect blocked" in page.locator("#firewallResult").inner_text().lower())
        if view == "successor":
            page.fill("#replayObject", "mw-ea-n0-fab-offers-001")
            page.fill("#replayAuthority", "Contained internal processing only; external organizational authority is outside the page")
            page.fill("#replayOpen", "Literal Meeting #1 offer sources and external authority receipts remain unresolved")
            page.fill("#replayNext", "Run source recovery, compile packets, verify, and export")
            page.click("#successorForm button[type='submit']")
            page.wait_for_selector("#replayResult .success")
            check("cold successor replay passes", "4/4" in page.locator("#replayResult").inner_text())
        if view == "sources":
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
                tmp.write("synthetic FAB source for local browser qualification\n")
                tmp_path = Path(tmp.name)
            try:
                page.set_input_files("#sourceFiles", str(tmp_path))
                page.click("#hashSourcesButton")
                for _ in range(20):
                    if "hashed locally" in page.locator("#hashStatus").inner_text().lower():
                        break
                    page.wait_for_timeout(100)
                check("source is hashed locally", page.locator("#localSources .receipt").count() >= 1)
            finally:
                tmp_path.unlink(missing_ok=True)

    check("tour reaches final step", "7 OF 7" in page.locator("#tourCounter").inner_text())
    page.click("#tourNextButton")
    page.wait_for_selector("#tourBar", state="hidden")
    check("tour exits cleanly", page.locator("#tourBar").is_hidden())

    with page.expect_download() as download_info:
        page.click("#exportPacketButton")
    download = download_info.value
    packet_path = Path(download.path())
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("portable packet exports the active case", packet["cartridge"]["cartridge_id"] == "mw-ea-n0-fab-offers-001")
    check("portable packet includes local state", len(packet["state"]["ledger"]) >= 3)

    page.reload(wait_until="domcontentloaded")
    check("orientation is not forced after completion", not page.locator("#helpDialog").evaluate("el => el.open"))
    page.click("#helpButton")
    check("help remains available on demand", page.locator("#helpDialog").evaluate("el => el.open"))
    page.click("#closeHelpButton")

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="domcontentloaded")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    check("mobile view has no horizontal overflow", not overflow)
    check("Help remains visible on mobile", page.locator("#helpButton").is_visible())

    check("zero outbound network requests", len(external_requests) == 0, json.dumps(external_requests))
    check("zero JavaScript errors", len(page_errors) == 0, json.dumps(page_errors))

    browser.close()

print("\nEssential Attention browser tutorial: all assertions passed")
