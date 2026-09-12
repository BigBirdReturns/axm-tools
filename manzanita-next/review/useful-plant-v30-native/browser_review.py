#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def wait_for_port(port: int, timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.12)
    raise RuntimeError(f"HTTP server did not open port {port}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    shots = args.output / "screenshots"
    shots.mkdir(exist_ok=True)

    checks: list[dict[str, object]] = []
    screenshots: list[dict[str, object]] = []
    console_errors: list[str] = []
    external_requests: list[str] = []

    def check(name: str, condition: bool, detail: object = "") -> None:
        checks.append({"name": name, "pass": bool(condition), "detail": detail})

    def capture(page, name: str, full_page: bool = False) -> None:
        target = shots / f"{name}.png"
        page.screenshot(path=str(target), full_page=full_page)
        payload = target.read_bytes()
        screenshots.append({
            "name": name,
            "path": str(target.relative_to(args.output)),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(args.port), "--bind", "127.0.0.1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_for_port(args.port)
        url = f"http://127.0.0.1:{args.port}/manzanita-next/review/useful-plant-v30-native/"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1100}, reduced_motion="reduce")
            page = context.new_page()

            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))

            def observe_request(request) -> None:
                parsed = urlparse(request.url)
                if parsed.hostname not in {"127.0.0.1", "localhost", None}:
                    external_requests.append(request.url)

            page.on("request", observe_request)
            response = page.goto(url, wait_until="networkidle")
            check("review route HTTP 200", response is not None and response.status == 200, response.status if response else None)
            check("bounded review marker", page.locator("html").get_attribute("data-review-state") == "bounded")
            check("operator acceptance absent", page.locator("html").get_attribute("data-operator-acceptance") == "absent")
            check("candidate title visible", page.get_by_role("heading", name="Useful Plant v30", exact=False).first.is_visible())
            page.wait_for_function("document.querySelector('#plant-image').complete && document.querySelector('#plant-image').naturalWidth > 0")
            dimensions = page.locator("#plant-image").evaluate("img => ({width: img.naturalWidth, height: img.naturalHeight})")
            check("photographic donor decoded", dimensions["width"] >= 1000 and dimensions["height"] >= 600, dimensions)
            page.wait_for_function("document.querySelector('#donor-digest').dataset.measured === 'true'")
            donor_text = page.locator("#donor-digest").inner_text()
            check("browser measured donor digest", donor_text.startswith("sha256:") and "bytes" in donor_text, donor_text)

            frame_box = page.locator(".scene-frame").bounding_box()
            image_box = page.locator("#plant-image").bounding_box()
            overlay_box = page.locator(".registration-layer").bounding_box()
            registration_delta = max(abs(frame_box[key] - overlay_box[key]) for key in ("x", "y", "width", "height"))
            check("registration overlay follows rendered frame", registration_delta <= 1.5, registration_delta)
            check("photograph fills rendered frame", abs(image_box["width"] - frame_box["width"]) <= 1.5 and abs(image_box["height"] - frame_box["height"]) <= 1.5, {"frame": frame_box, "image": image_box})
            capture(page, "01-desktop-recognize")

            expected_modes = ["recognize", "place", "tend", "observe", "use", "return"]
            for index, mode in enumerate(expected_modes, start=1):
                button = page.locator(f'button[data-mode="{mode}"]')
                button.click()
                check(f"mode {mode} selectable", button.get_attribute("aria-pressed") == "true")
                check(f"mode {mode} reaches loop", page.locator(f'li[data-loop="{mode}"]').evaluate("node => node.classList.contains('is-current')"))
                check(f"mode {mode} encoded in URL", f"mode={mode}" in page.url)
                if mode in {"place", "use", "return"}:
                    capture(page, f"0{index + 1}-desktop-{mode}")

            expected_seats = ["household", "grower", "neighbor", "ecologist", "responder"]
            for seat in expected_seats:
                button = page.locator(f'button[data-seat="{seat}"]')
                button.click()
                check(f"seat {seat} selectable", button.get_attribute("aria-pressed") == "true")
                check(f"seat {seat} changes authority", bool(page.locator("#seat-authority").inner_text().strip()))
            capture(page, "05-desktop-responder")

            expected_zones = ["identity", "placement", "care", "yield", "return"]
            for zone in expected_zones:
                button = page.locator(f'button[data-zone="{zone}"]')
                button.click()
                check(f"zone {zone} selectable", button.get_attribute("aria-pressed") == "true")
                check(f"zone {zone} exposes verification", len(page.locator("#object-verification").inner_text()) > 24)
                check(f"zone {zone} exposes stop condition", len(page.locator("#object-stop").inner_text()) > 12)

            page.locator("#evidence-toggle").click()
            check("evidence drawer opens", page.locator("#evidence-drawer").is_visible())
            check("evidence exposes source path", page.get_by_text("manzanita/assets/plant.webp", exact=True).is_visible())
            check("evidence preserves claim boundary", page.get_by_text("no v29 relabeling", exact=True).is_visible())
            capture(page, "06-desktop-evidence", full_page=True)
            page.locator("#evidence-close").click()
            check("evidence drawer closes", page.locator("#evidence-drawer").is_hidden())

            for stop, attribute, expected in (
                ("pause", "data-paused", "true"),
                ("private", "data-private", "true"),
                ("substitution", "data-substitution", "rejected"),
            ):
                button = page.locator(f'button[data-stop="{stop}"]')
                button.click()
                check(f"stop {stop} locally active", button.get_attribute("aria-pressed") == "true")
                check(f"stop {stop} reflected on root", page.locator("html").get_attribute(attribute) == expected)
            check("stop state declares local boundary", "local" in page.locator("#stop-state").inner_text().lower())
            capture(page, "07-desktop-stop-authority", full_page=True)

            persisted_url = page.url
            page.reload(wait_until="networkidle")
            check("URL state survives reload", page.url == persisted_url)
            check("substitution rejection survives reload", page.locator("html").get_attribute("data-substitution") == "rejected")

            page.set_viewport_size({"width": 390, "height": 844})
            page.reload(wait_until="networkidle")
            mobile_metrics = page.evaluate("({scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth})")
            check("390px mobile has no horizontal overflow", mobile_metrics["scrollWidth"] <= mobile_metrics["innerWidth"] + 2, mobile_metrics)
            check("mobile scene remains substantive", page.locator(".scene-frame").bounding_box()["height"] >= 500)
            check("mobile stop controls remain visible", page.locator("[data-stop='pause']").is_visible())
            capture(page, "08-mobile-390", full_page=True)

            page.set_viewport_size({"width": 700, "height": 960})
            page.reload(wait_until="networkidle")
            page.evaluate("document.documentElement.style.fontSize = '200%'")
            page.wait_for_timeout(150)
            zoom_metrics = page.evaluate("({scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth})")
            check("200 percent text reflows without horizontal overflow", zoom_metrics["scrollWidth"] <= zoom_metrics["innerWidth"] + 3, zoom_metrics)
            check("200 percent operator gate remains reachable", page.locator(".review-gate").is_visible())
            capture(page, "09-text-200-percent", full_page=True)

            button_names = page.locator("button").evaluate_all(
                "nodes => nodes.map(n => (n.getAttribute('aria-label') || n.innerText || '').trim()).filter(Boolean)"
            )
            check("all buttons have accessible names", len(button_names) == page.locator("button").count(), {"named": len(button_names), "total": page.locator("button").count()})
            check("no external network requests", not external_requests, external_requests)
            check("no console or page errors", not console_errors, console_errors)
            check("no acceptance control embedded", page.get_by_text("operator visual acceptance", exact=False).count() >= 1 and page.get_by_role("button", name="Accept", exact=True).count() == 0)
            browser.close()

    except Exception as error:
        check("browser campaign completed", False, repr(error))
    finally:
        server.terminate()
        try:
            server.wait(timeout=4)
        except subprocess.TimeoutExpired:
            server.kill()

    passed = sum(1 for item in checks if item["pass"])
    result = {
        "schema": "manzanita/useful-plant-v30-native-browser-review@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if passed == len(checks) else "FAIL",
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "screenshots": screenshots,
        "console_errors": console_errors,
        "external_requests": external_requests,
        "operator_visual_acceptance": "ABSENT",
        "release_authorized": False,
        "merge_authorized": False,
        "public_route_effect": "none",
        "pages_deployment_effect": "none",
        "external_effect": "none",
    }
    receipt = args.output / "BROWSER_REVIEW_RECEIPT.json"
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cards = "\n".join(
        f'<figure><img src="{html.escape(item["path"])}" alt="{html.escape(item["name"])}"><figcaption>{html.escape(item["name"])} · {item["bytes"]:,} bytes</figcaption></figure>'
        for item in screenshots
    )
    index = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Useful Plant v30 review evidence</title>
<style>body{{margin:0;background:#0d120f;color:#e8eee8;font:14px/1.45 system-ui}}main{{width:min(1600px,calc(100% - 2rem));margin:1rem auto}}h1{{font-weight:560}}p{{color:#aeb9b0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem}}figure{{margin:0;border:1px solid #364037;border-radius:12px;overflow:hidden;background:#121914}}img{{display:block;width:100%;height:auto}}figcaption{{padding:.7rem;color:#aeb9b0;font:12px ui-monospace,monospace}}</style></head>
<body><main><h1>Useful Plant v30 repository-native review evidence</h1><p>{passed} of {len(checks)} browser checks passed. Operator visual acceptance remains absent.</p><div class="grid">{cards}</div></main></body></html>"""
    (args.output / "index.html").write_text(index, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
