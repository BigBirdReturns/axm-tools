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
OUT = Path(__import__("os").environ.get("MW_DREAMBOARD_SCREENSHOT_DIR", "/tmp/manzanita-works-dreamboard-screens"))
OUT.mkdir(parents=True, exist_ok=True)

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        pass

@contextlib.contextmanager
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def assert_no_overflow(page) -> None:
    overflow = page.evaluate("""() => ({
      doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth
    })""")
    assert overflow["doc"] <= 1 and overflow["body"] <= 1, overflow


def main() -> None:
    public_text = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "What Mila already has" not in public_text
    assert "What Jonathan is actually doing" not in public_text
    assert "Stu's dashboard" not in public_text

    url = (ROOT / "index.html").as_uri()
    with sync_playwright() as p:
        launch = {"headless": True}
        if os.environ.get("MW_CHROMIUM_EXECUTABLE"):
            launch["executable_path"] = os.environ["MW_CHROMIUM_EXECUTABLE"]
            launch["args"] = ["--no-sandbox"]
        browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1600, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors: list[str] = []
        requests: list[str] = []
        page.on("console", lambda msg: errors.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        page.on("request", lambda req: requests.append(req.url))
        page.goto(url, wait_until="networkidle")

        assert page.locator('meta[name="mw-release"]').get_attribute("content") == "mw-operating-dreamboard-v0.2.0"
        assert page.locator(".sticky").count() == 12
        assert page.locator(".cap").count() == 8
        assert page.locator(".job").count() == 4
        assert page.locator(".program").count() == 7
        assert page.locator(".rule").count() == 5
        assert page.locator(".receipt").count() == 4
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "dreamboard-desktop.png"), full_page=True)

        page.locator('[data-kind="input"][data-id="timebank"]').click()
        assert "time-bank sketch" in page.locator("#detail-title").inner_text()
        assert page.locator('[data-kind="capacity"][data-id="time"]').get_attribute("class").find("active") >= 0
        assert page.locator('[data-kind="program"][data-id="essential-time"]').get_attribute("class").find("active") >= 0

        page.locator('[data-kind="capacity"][data-id="pilotage"]').click()
        assert page.locator("#detail-kicker").inner_text().lower() == "capacity class"
        assert "Essential Pilotage" in page.locator("#detail-grid").inner_text()

        page.locator('[data-kind="program"][data-id="mobility"]').click()
        assert page.locator("#detail-title").inner_text() == "Mobility / E-bike"
        assert "Manzanita owns" in page.locator("#detail-grid").inner_text()
        assert "hardware" in page.locator("#detail-grid").inner_text().lower()

        page.locator('[data-kind="dashboard"]').click()
        assert page.locator("#detail-title").inner_text() == "Fundraising dashboard"
        detail = page.locator("#detail").inner_text()
        assert "Constituent" in detail and "processor" in detail.lower() and "may not do" in detail
        assert "focus=fundraising" in page.url
        page.screenshot(path=str(OUT / "dreamboard-fundraising.png"), full_page=True)

        page.locator('[data-kind="job"][data-id="prototype"]').click()
        assert "falsifiable prototype" in page.locator("#detail-title").inner_text()
        assert "adversarial" in page.locator("#detail").inner_text().lower()

        page.locator('[data-kind="rule"][data-id="authority"]').click()
        assert page.locator("#detail-title").inner_text() == "Authority"
        assert "manufacture" in page.locator("#detail").inner_text().lower()

        with page.expect_download() as di:
            page.locator("#export").click()
        download = di.value
        target = OUT / "dreamboard-export.json"
        download.save_as(str(target))
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["schema"] == "manzanita-works/operating-dreamboard@0.2"
        assert payload["release"] == "mw-operating-dreamboard-v0.2.0"
        serialized = json.dumps(payload)
        assert "What Mila already has" not in serialized and "Stu's dashboard" not in serialized

        page.locator("#theme").click()
        theme = page.locator("html").get_attribute("data-theme")
        assert theme in {"dark", "light"}
        page.reload(wait_until="networkidle")
        assert page.locator("html").get_attribute("data-theme") == theme

        page.goto(url + "?focus=fundraising", wait_until="networkidle")
        assert page.locator('[data-kind="dashboard"]').get_attribute("class").find("active") >= 0
        assert page.locator("#detail-title").inner_text() == "Fundraising dashboard"

        sticky = page.locator('[data-kind="input"][data-id="oss"]')
        sticky.focus()
        page.keyboard.press("Enter")
        assert page.locator("#detail-title").inner_text() == "OSS / community sweep"

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(url, wait_until="networkidle")
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "dreamboard-mobile.png"), full_page=True)

        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(url + "?focus=fundraising", wait_until="networkidle")
        page.evaluate("document.documentElement.style.fontSize='200%'")
        page.wait_for_timeout(100)
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "dreamboard-mobile-200pct.png"), full_page=True)

        reduced = browser.new_context(viewport={"width": 1024, "height": 768}, reduced_motion="reduce")
        rp = reduced.new_page()
        rp.goto(url, wait_until="networkidle")
        rp.locator('[data-kind="program"][data-id="essential-pilotage"]').click()
        assert rp.locator("#detail-title").inner_text() == "Essential Pilotage"
        reduced.close()

        standalone = context.new_page()
        standalone.goto((ROOT / "index.html").as_uri(), wait_until="load")
        standalone.locator('[data-kind="dashboard"]').click()
        assert standalone.locator("#detail-title").inner_text() == "Fundraising dashboard"
        standalone.screenshot(path=str(OUT / "dreamboard-standalone.png"), full_page=True)

        unexpected = [r for r in requests if urlparse(r).scheme in {"http", "https"}]
        assert not unexpected, unexpected
        assert not errors, errors
        browser.close()

    print("Manzanita Works Operating Fabric Dreamboard browser campaign: PASS")

if __name__ == "__main__":
    main()
