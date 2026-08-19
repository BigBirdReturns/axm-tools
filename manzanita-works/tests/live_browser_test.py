#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URL = os.environ["MW_DREAMBOARD_URL"]
OUT = Path(os.environ.get("MW_DREAMBOARD_SCREENSHOT_DIR", "/tmp/manzanita-works-dreamboard-live-screens"))
OUT.mkdir(parents=True, exist_ok=True)


def assert_no_overflow(page) -> None:
    overflow = page.evaluate("""() => ({
      doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth
    })""")
    assert overflow["doc"] <= 1 and overflow["body"] <= 1, overflow


def main() -> None:
    parsed = urlparse(URL)
    allowed_origin = f"{parsed.scheme}://{parsed.netloc}"
    with sync_playwright() as p:
        launch: dict[str, object] = {"headless": True}
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

        target = URL + ("&" if "?" in URL else "?") + "focus=fundraising"
        page.goto(target, wait_until="networkidle")
        assert page.locator('meta[name="mw-release"]').get_attribute("content") == "mw-operating-dreamboard-v0.2.0"
        assert page.locator(".sticky").count() == 12
        assert page.locator(".cap").count() == 8
        assert page.locator(".program").count() == 7
        assert page.locator("#detail-title").inner_text() == "Fundraising dashboard"
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "dreamboard-live-desktop.png"), full_page=True)

        page.locator('[data-kind="input"][data-id="timebank"]').click()
        assert page.locator("#detail-title").inner_text() == "time-bank sketch"
        assert "Essential Time" in page.locator("#detail-grid").inner_text()

        page.locator('[data-kind="dashboard"]').click()
        detail = page.locator("#detail").inner_text()
        assert "Constituent" in detail and "It may not do" in detail

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(target, wait_until="networkidle")
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "dreamboard-live-mobile.png"), full_page=True)

        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(target, wait_until="networkidle")
        page.evaluate("document.documentElement.style.fontSize='200%'")
        page.wait_for_timeout(100)
        assert_no_overflow(page)
        page.screenshot(path=str(OUT / "dreamboard-live-mobile-200pct.png"), full_page=True)

        reduced = browser.new_context(viewport={"width": 1024, "height": 768}, reduced_motion="reduce")
        rp = reduced.new_page()
        rp.goto(URL, wait_until="networkidle")
        rp.locator('[data-kind="program"][data-id="essential-pilotage"]').click()
        assert rp.locator("#detail-title").inner_text() == "Essential Pilotage"
        reduced.close()

        unexpected = [r for r in requests if urlparse(r).scheme in {"http", "https"} and not r.startswith(allowed_origin + "/")]
        assert not unexpected, unexpected
        assert not errors, errors
        browser.close()

    print("Manzanita Works Operating Fabric Dreamboard live browser campaign: PASS")


if __name__ == "__main__":
    main()
