from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
LOCAL_URL = "http://127.0.0.1:8765/manzanita/"
TARGET_URL = os.environ.get("MANZANITA_URL", LOCAL_URL)
SCREENSHOT_DIR = Path(os.environ.get("MANZANITA_SCREENSHOT_DIR", ROOT / "manzanita" / "test-output"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.4)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"server did not open port {port}")


def exercise(page, theme: str, label: str) -> None:
    errors: list[str] = []
    outbound: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)

    parsed = urlparse(TARGET_URL)
    target_origin = f"{parsed.scheme}://{parsed.netloc}"
    page.on(
        "request",
        lambda req: outbound.append(req.url)
        if not req.url.startswith(target_origin) and not req.url.startswith("data:")
        else None,
    )

    response = page.goto(TARGET_URL, wait_until="networkidle", timeout=60_000)
    assert response is not None and response.status == 200, response.status if response else None
    page.evaluate("theme => localStorage.setItem('manzanita-theme', theme)", theme)
    response = page.reload(wait_until="networkidle")
    assert response is not None and response.status == 200, response.status if response else None
    assert page.title() == "Manzanita Works · One Place, Every Scale"
    assert page.locator("html").get_attribute("data-release") == "1.4.0"
    assert page.locator("html").get_attribute("data-visual-system") == "signal-sheet"
    assert page.locator("html").get_attribute("data-theme") == theme

    page.locator("[data-scale]").first.wait_for(state="visible")
    assert page.locator("[data-scale]").count() == 7
    assert page.locator("[data-overlay-button]").count() == 8
    assert page.locator("[data-role]").count() == 5
    assert page.locator(".instrument-ledger > article").count() == 6
    assert page.locator(".sequence > li").count() == 6
    assert page.locator(".hero-plate svg").count() == 1
    assert page.locator("#placeSvg").count() == 1
    assert page.locator("img").count() == 0

    for button in page.locator("[data-scale]").all():
        label_text = button.inner_text().strip()
        button.click()
        assert page.locator("#visualTitle").text_content().strip().lower() == label_text.lower()
        assert button.get_attribute("aria-pressed") == "true"
        assert page.locator("#scaleTitle").inner_text().strip()
        assert page.locator("#scaleAuthority").inner_text().strip()
        assert page.locator("#scaleScene > g").count() == 1

    for button in page.locator("[data-overlay-button]").all():
        before = button.get_attribute("aria-pressed")
        button.click()
        assert button.get_attribute("aria-pressed") != before
        button.click()
        assert button.get_attribute("aria-pressed") == before

    for button in page.locator("[data-role]").all():
        button.click()
        assert button.get_attribute("aria-pressed") == "true"
        assert page.locator("#roleTitle").inner_text().strip()
        assert page.locator("#roleNeed").inner_text().strip().startswith("Needs:")

    body_text = page.locator("body").inner_text()
    assert "Automatic insurance denial" in body_text
    assert "no backend · no external-effect adapters" in body_text.lower()
    assert page.locator('a[href*="essential-attention"]').count() == 1

    toggle = page.locator("#themeToggle")
    old_theme = page.locator("html").get_attribute("data-theme")
    toggle.click()
    new_theme = page.locator("html").get_attribute("data-theme")
    assert new_theme != old_theme
    page.reload(wait_until="networkidle")
    assert page.locator("html").get_attribute("data-theme") == new_theme
    toggle.click()
    assert page.locator("html").get_attribute("data-theme") == old_theme

    computed = page.locator(".hero h1").evaluate("el => ({fontWeight:getComputedStyle(el).fontWeight,textTransform:getComputedStyle(el).textTransform})")
    assert int(float(computed["fontWeight"])) >= 800
    assert computed["textTransform"] == "uppercase"
    assert page.locator(".hero-plate").evaluate("el => getComputedStyle(el).boxShadow") == "none"
    assert page.locator(".theme-toggle").evaluate("el => getComputedStyle(el).borderRadius") == "0px"

    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, overflow
    assert not outbound, outbound
    assert not errors, errors

    page.screenshot(path=str(SCREENSHOT_DIR / f"{label}-full.png"), full_page=True)
    page.locator(".hero").screenshot(path=str(SCREENSHOT_DIR / f"{label}-hero.png"))
    page.locator("#place").screenshot(path=str(SCREENSHOT_DIR / f"{label}-atlas.png"))


server = None
if TARGET_URL == LOCAL_URL:
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_port(8765)

try:
    with sync_playwright() as p:
        launch_kwargs = {"headless": True}
        if Path("/usr/bin/chromium").exists():
            launch_kwargs["executable_path"] = "/usr/bin/chromium"
            launch_kwargs["args"] = ["--no-sandbox"]
        browser = p.chromium.launch(**launch_kwargs)

        desktop = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        exercise(desktop.new_page(), "light", "desktop-light")
        desktop.close()

        dark = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        exercise(dark.new_page(), "dark", "desktop-dark")
        dark.close()

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        exercise(mobile.new_page(), "light", "mobile-light")
        mobile.close()

        browser.close()
finally:
    if server is not None:
        server.terminate()
        with contextlib.suppress(Exception):
            server.wait(timeout=5)

print(f"Manzanita Works v1.4.0 browser contract: PASS ({TARGET_URL})")
