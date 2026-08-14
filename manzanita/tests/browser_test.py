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


def wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.4)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"server did not open port {port}")


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
        for viewport in ({"width": 1440, "height": 900}, {"width": 390, "height": 844}):
            page = browser.new_page(viewport=viewport)
            errors: list[str] = []
            outbound: list[str] = []
            page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
            page.on(
                "console",
                lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None,
            )
            parsed = urlparse(TARGET_URL)
            target_origin = f"{parsed.scheme}://{parsed.netloc}"
            page.on(
                "request",
                lambda req: outbound.append(req.url)
                if not req.url.startswith(target_origin) and not req.url.startswith("data:")
                else None,
            )

            response = page.goto(TARGET_URL, wait_until="networkidle", timeout=45_000)
            assert response is not None and response.status == 200, response.status if response else None
            assert page.title() == "Manzanita Works · One Place, Every Scale"
            page.locator("[data-scale]").first.wait_for(state="visible")
            assert page.locator("[data-scale]").count() == 7
            assert page.locator("[data-overlay-button]").count() == 8
            assert page.locator("[data-role]").count() == 5
            assert page.locator(".module").count() == 6
            assert "data:image/webp;base64," in page.locator("#hero").evaluate(
                "el => getComputedStyle(el).backgroundImage"
            )

            for button in page.locator("[data-scale]").all():
                label = button.inner_text().strip()
                button.click()
                assert page.locator("#visualTitle").inner_text().strip().lower() == label.lower()
                assert button.get_attribute("aria-pressed") == "true"

            for button in page.locator("[data-overlay-button]").all():
                button.click()
                assert button.get_attribute("aria-pressed") == "true"
                button.click()
                assert button.get_attribute("aria-pressed") == "false"

            for button in page.locator("[data-role]").all():
                button.click()
                assert button.get_attribute("aria-pressed") == "true"
                assert page.locator("#roleTitle").inner_text().strip()

            body_text = page.locator("body").inner_text()
            assert "Automatic insurance denial" in body_text
            assert "No email, payment, scheduling" in body_text
            handoff = page.locator('a[href*="essential-attention"]')
            assert handoff.count() == 1
            assert "bigbirdreturns.github.io/axm-tools/essential-attention/" in handoff.get_attribute("href")

            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 1, overflow
            assert not outbound, outbound
            assert not errors, errors
            page.close()
        browser.close()
finally:
    if server is not None:
        server.terminate()
        with contextlib.suppress(Exception):
            server.wait(timeout=5)

print(f"Manzanita Works browser contract: PASS ({TARGET_URL})")
