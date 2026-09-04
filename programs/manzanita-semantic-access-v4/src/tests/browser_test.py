#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@contextlib.contextmanager
def serve(directory: Path) -> Iterator[str]:
    class BoundHandler(QuietHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def snapshot(page: Page) -> dict:
    return page.evaluate("window.__MANZANITA_V4__.getState()")


def select(page: Page, aperture: str, instrument: str, mode: str, provider_scene: int = 0) -> dict:
    page.locator(f'[data-aperture="{aperture}"]').click()
    page.locator(f'[data-instrument="{instrument}"]').click()
    page.locator(f'[data-mode="{mode}"]').click()
    if aperture == "street" and mode == "live":
        page.locator(f'[data-provider-scene="{provider_scene}"]').click()
    return snapshot(page)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "browser-audit.json")
    args = parser.parse_args()

    data = json.loads((args.site / "data.json").read_text(encoding="utf-8"))
    console_errors: list[str] = []
    page_errors: list[str] = []
    external_requests: list[str] = []
    matrix: list[dict] = []
    refused = 0

    url = (args.site / "index.html").resolve().as_uri()
    with sync_playwright() as pw:
        system_chromium = Path("/usr/bin/chromium")
        browser = pw.chromium.launch(executable_path=str(system_chromium) if system_chromium.exists() else None)
        context = browser.new_context(viewport={"width": 1600, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        origin = url.rsplit("/", 1)[0]
        page.on("request", lambda request: external_requests.append(request.url) if not request.url.startswith(origin) else None)
        page.goto(url, wait_until="networkidle")

        require(page.locator("[data-aperture]").count() == 7, "Aperture controls drifted")
        require(page.locator("[data-instrument]").count() == 8, "Instrument controls drifted")
        require(page.locator("[data-mode]").count() == 5, "Mode controls drifted")
        require(page.locator("[data-seat]").count() == 5, "Seat controls drifted")

        # Every admitted aperture / instrument / source-mode state must be reachable.
        for aperture, aperture_record in data["apertures"].items():
            page.locator(f'[data-aperture="{aperture}"]').click()
            for instrument, instrument_record in data["instruments"].items():
                button = page.locator(f'[data-instrument="{instrument}"]')
                supported = aperture in instrument_record["support"]
                require(button.is_disabled() is (not supported), f"Instrument enablement drifted: {aperture}/{instrument}")
                before = snapshot(page)
                button.click(force=True)
                after = snapshot(page)
                if not supported:
                    refused += 1
                    require(after["instrument"] == before["instrument"], f"Unsupported instrument changed state: {aperture}/{instrument}")
                    continue
                require(after["instrument"] == instrument, f"Supported instrument did not activate: {aperture}/{instrument}")
                for mode in data["modeAvailability"][aperture]:
                    mode_button = page.locator(f'[data-mode="{mode}"]')
                    require(not mode_button.is_disabled(), f"Admitted mode disabled: {aperture}/{mode}")
                    mode_button.click()
                    provider_indexes = range(len(data["streetProviderScenes"])) if aperture == "street" and mode == "live" else range(1)
                    for provider_index in provider_indexes:
                        if aperture == "street" and mode == "live":
                            page.locator(f'[data-provider-scene="{provider_index}"]').click()
                        state = snapshot(page)
                        geometry_count = page.locator("#registeredGeometry > *").count()
                        marker_count = page.locator("#registeredLabels .feature-marker").count()
                        expected_geometry = state["feature_count"]
                        require(geometry_count == expected_geometry, f"Geometry count mismatch: {aperture}/{instrument}/{mode}/{provider_index}")
                        require(marker_count == expected_geometry, f"Marker count mismatch: {aperture}/{instrument}/{mode}/{provider_index}")
                        if instrument != "access" or aperture != "street" or mode in {"map", "held"}:
                            require(expected_geometry == 0, f"Non-admitted image geometry rendered: {aperture}/{instrument}/{mode}")
                        matrix.append({
                            "aperture": aperture,
                            "instrument": instrument,
                            "mode": mode,
                            "provider_scene": provider_index,
                            "asset_id": state["asset_id"],
                            "registration_id": state["registration_id"],
                            "feature_count": state["feature_count"],
                            "feature_classes": state["feature_classes"],
                        })

        # Exact Street Access receipts must change with the exact image.
        reference = select(page, "street", "access", "reference")
        live_a = select(page, "street", "access", "live", 0)
        live_b = select(page, "street", "access", "live", 1)
        require(len({reference["asset_id"], live_a["asset_id"], live_b["asset_id"]}) == 3, "Street scene identity did not change")
        require(len({reference["registration_id"], live_a["registration_id"], live_b["registration_id"]}) == 3, "Semantic receipt did not follow the exact image")
        require([reference["feature_count"], live_a["feature_count"], live_b["feature_count"]] == [3, 3, 5], "Semantic feature inventory drifted")

        # Map and hold must remove all local image geometry.
        for mode in ("map", "held"):
            held = select(page, "street", "access", mode)
            require(held["registration_id"] is None and held["feature_count"] == 0, f"{mode} borrowed image geometry")
            require(page.locator("#registeredGeometry > *").count() == 0, f"{mode} left geometry in the DOM")

        # Shade and water are explicit source questions, never invented polygons.
        for aperture, instrument in (("property", "shade"), ("neighborhood", "water")):
            state = select(page, aperture, instrument, "reference")
            require(state["registration_id"] is None and state["feature_count"] == 0, f"{instrument} invented geometry at {aperture}")
            require("NO IMAGE GEOMETRY IS DRAWN" in page.locator("#instrumentSurface").inner_text(), f"{instrument} did not expose its hold")

        # Functional seats must change the operating record.
        seat_records: dict[str, str] = {}
        select(page, "street", "access", "reference")
        for seat in data["seats"]:
            page.locator(f'[data-seat="{seat}"]').click()
            seat_records[seat] = page.locator("#detailContent").inner_text()
        require(len(set(seat_records.values())) == 5, "Functional seats collapsed into one record")

        # Keyboard continuity across the aperture rail.
        household = page.locator('[data-aperture="household"]')
        household.focus()
        household.press("ArrowRight")
        require(snapshot(page)["aperture"] == "property", "ArrowRight failed")
        page.keyboard.press("End")
        require(snapshot(page)["aperture"] == "stewardship", "End failed")
        page.keyboard.press("Home")
        require(snapshot(page)["aperture"] == "plant", "Home failed")

        # Export must retain the exact asset-bound semantic receipt.
        select(page, "street", "access", "live", 1)
        with page.expect_download() as download_info:
            page.locator("#exportButton").click()
        download_path = args.output.parent / "semantic-handoff-browser.json"
        download_info.value.save_as(download_path)
        exported = json.loads(download_path.read_text(encoding="utf-8"))
        current = snapshot(page)
        require(exported["asset_id"] == current["asset_id"], "Export lost exact asset identity")
        require(exported["semantic_receipt"]["receipt_sha256"] == current["registration_id"], "Export lost semantic receipt identity")
        require(len(exported["semantic_receipt"]["features"]) == 5, "Export lost feature inventory")
        require(exported["public_effect"] == "none", "Export acquired a public effect")

        # Mobile must remain usable without page-level overflow.
        context.close()
        mobile = browser.new_context(viewport={"width": 390, "height": 844})
        mpage = mobile.new_page()
        mpage.goto(url + "?aperture=street&instrument=access&mode=live&providerScene=1", wait_until="networkidle")
        overflow = mpage.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
        require(overflow <= 1, "Mobile introduced horizontal overflow")
        require(mpage.locator("[data-aperture]").count() == 7, "Mobile lost apertures")
        require(mpage.locator("[data-instrument]").count() == 8, "Mobile lost instruments")
        mobile.close()
        browser.close()

    require(not console_errors, f"Console errors: {console_errors}")
    require(not page_errors, f"Page errors: {page_errors}")
    require(not external_requests, f"External requests: {external_requests}")

    report = {
        "schema": "manzanita-works/semantic-access-browser-audit@5",
        "result": "PASS",
        "valid_states_exercised": len(matrix),
        "invalid_controls_refused": refused,
        "street_access_feature_counts": [3, 3, 5],
        "map_and_hold_geometry": 0,
        "shade_and_water_image_geometry": 0,
        "functional_seats": 5,
        "mobile_horizontal_overflow": 0,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "external_requests": external_requests,
        "public_route_effect": "none",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
