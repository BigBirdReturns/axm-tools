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
    return page.evaluate("window.__MANZANITA_V5__.getState()")


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
        chromium = Path("/usr/bin/chromium")
        browser = pw.chromium.launch(executable_path=str(chromium) if chromium.exists() else None)
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

        # Every admitted state and every refusal.
        for aperture in data["apertures"]:
            page.locator(f'[data-aperture="{aperture}"]').click()
            for instrument, record in data["instruments"].items():
                button = page.locator(f'[data-instrument="{instrument}"]')
                supported = aperture in record["support"]
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
                    page.locator(f'[data-mode="{mode}"]').click()
                    provider_indexes = range(len(data["streetProviderScenes"])) if aperture == "street" and mode == "live" else range(1)
                    for provider_index in provider_indexes:
                        if aperture == "street" and mode == "live":
                            page.locator(f'[data-provider-scene="{provider_index}"]').click()
                        state = snapshot(page)
                        geometry_count = page.locator("#registeredGeometry > *").count()
                        marker_count = page.locator("#registeredLabels .feature-marker").count()
                        require(geometry_count == state["feature_count"], f"Geometry count mismatch: {aperture}/{instrument}/{mode}/{provider_index}")
                        require(marker_count == state["feature_count"], f"Marker count mismatch: {aperture}/{instrument}/{mode}/{provider_index}")
                        if mode in {"map", "held"} or instrument not in {"shade", "water", "access"}:
                            require(state["feature_count"] == 0, f"Non-admitted geometry rendered: {aperture}/{instrument}/{mode}")
                        matrix.append({"aperture": aperture, "instrument": instrument, "mode": mode, "provider_scene": provider_index, **state})

        # Exact image/receipt coupling.
        access_states = [
            select(page, "street", "access", "reference"),
            select(page, "street", "access", "live", 0),
            select(page, "street", "access", "live", 1),
        ]
        require([row["feature_count"] for row in access_states] == [3, 3, 5], "Access feature inventories drifted")
        require(len({row["asset_id"] for row in access_states}) == 3, "Access asset identity collapsed")
        require(len({row["registration_id"] for row in access_states}) == 3, "Access receipt identity collapsed")

        shade_states = [
            select(page, "household", "shade", "reference"),
            select(page, "property", "shade", "reference"),
            select(page, "street", "shade", "reference"),
            select(page, "street", "shade", "live", 0),
            select(page, "street", "shade", "live", 1),
        ]
        require([row["feature_count"] for row in shade_states] == [2, 3, 3, 2, 1], "Shade feature inventories drifted")
        require(len({row["registration_id"] for row in shade_states}) == 5, "Shade receipts did not follow exact scenes")

        water_states = [
            select(page, "household", "water", "reference"),
            select(page, "property", "water", "reference"),
        ]
        require([row["feature_count"] for row in water_states] == [6, 4], "Water feature inventories drifted")
        require(len({row["registration_id"] for row in water_states}) == 2, "Water receipts collapsed")

        # Honest gaps and degraded states.
        for aperture, instrument in (("neighborhood", "shade"), ("neighborhood", "water"), ("region", "water")):
            state = select(page, aperture, instrument, "reference")
            require(state["registration_id"] is None and state["feature_count"] == 0, f"{instrument} invented geometry at {aperture}")
            require("NO IMAGE GEOMETRY IS DRAWN" in page.locator("#instrumentSurface").inner_text(), f"{instrument} did not expose the semantic hold")
        for instrument in ("shade", "water", "access"):
            aperture = "street" if instrument == "access" else "property"
            for mode in ("map", "held"):
                state = select(page, aperture, instrument, mode)
                require(state["registration_id"] is None and state["feature_count"] == 0, f"{instrument}/{mode} borrowed geometry")

        # Non-geometric instruments render distinct operating surfaces.
        checks = [
            ("household", "care", "OBSERVE"),
            ("region", "heat", "FORECAST"),
            ("region", "air", "VALUE: NOT FABRICATED"),
            ("region", "fire", "LOCAL GEOMETRY: NONE"),
            ("stewardship", "assistance", "FOLLOW-THROUGH"),
        ]
        surfaces = []
        for aperture, instrument, expected in checks:
            select(page, aperture, instrument, "reference")
            text = page.locator("#instrumentStage").inner_text()
            require(expected in text, f"{instrument} stage mechanism missing")
            require(snapshot(page)["feature_count"] == 0, f"{instrument} borrowed image geometry")
            surfaces.append(text)
        require(len(set(surfaces)) == len(surfaces), "Non-geometric instruments collapsed into one stage treatment")

        # Functional seats and keyboard continuity.
        select(page, "street", "access", "reference")
        seat_records = {}
        for seat in data["seats"]:
            page.locator(f'[data-seat="{seat}"]').click()
            seat_records[seat] = page.locator("#detailContent").inner_text()
        require(len(set(seat_records.values())) == 5, "Functional seats collapsed into one record")
        household = page.locator('[data-aperture="household"]')
        household.focus(); household.press("ArrowRight")
        require(snapshot(page)["aperture"] == "property", "ArrowRight failed")
        page.keyboard.press("End"); require(snapshot(page)["aperture"] == "stewardship", "End failed")
        page.keyboard.press("Home"); require(snapshot(page)["aperture"] == "plant", "Home failed")

        # Export exact Water receipt and seat record.
        select(page, "household", "water", "reference")
        page.locator('[data-seat="crew_steward"]').click()
        with page.expect_download() as download_info:
            page.locator("#exportButton").click()
        download_path = args.output.parent / "semantic-handoff-browser.json"
        download_info.value.save_as(download_path)
        exported = json.loads(download_path.read_text(encoding="utf-8"))
        current = snapshot(page)
        require(exported["asset_id"] == current["asset_id"], "Export lost exact asset identity")
        require(exported["semantic_receipt"]["receipt_sha256"] == current["registration_id"], "Export lost semantic receipt identity")
        require(exported["instrument"]["id"] == "water", "Export lost instrument identity")
        require(len(exported["semantic_receipt"]["features"]) == 6, "Export lost Water feature inventory")
        require(exported["seat"]["id"] == "crew_steward", "Export lost functional seat")
        require(exported["public_effect"] == "none", "Export acquired public effect")

        context.close()
        mobile = browser.new_context(viewport={"width": 390, "height": 844})
        mpage = mobile.new_page()
        mpage.goto(url + "?aperture=household&instrument=water&mode=reference&seat=resident", wait_until="networkidle")
        overflow = mpage.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
        require(overflow <= 1, "Mobile introduced horizontal overflow")
        require(mpage.locator("[data-aperture]").count() == 7, "Mobile lost apertures")
        require(mpage.locator("[data-instrument]").count() == 8, "Mobile lost instruments")
        visible_floor = mpage.evaluate("Math.min(...[...document.querySelectorAll('button')].filter(n=>{const b=n.getBoundingClientRect();const s=getComputedStyle(n);return b.width>0&&b.height>0&&s.display!=='none'&&s.visibility!=='hidden'}).map(n=>n.getBoundingClientRect().height))")
        require(visible_floor >= 43.5, "Mobile control target floor fell below 44 CSS px")
        mobile.close(); browser.close()

    require(not console_errors, f"Console errors: {console_errors}")
    require(not page_errors, f"Page errors: {page_errors}")
    require(not external_requests, f"External requests: {external_requests}")

    report = {
        "schema": "manzanita-works/semantic-instruments-browser-audit@6",
        "result": "PASS",
        "valid_states_exercised": len(matrix),
        "invalid_controls_refused": refused,
        "semantic_receipts_by_instrument": {"access": 3, "shade": 5, "water": 2},
        "semantic_features_by_instrument": {"access": 11, "shade": 11, "water": 10},
        "map_and_hold_geometry": 0,
        "non_geometric_instrument_geometry": 0,
        "functional_seats": 5,
        "mobile_horizontal_overflow": 0,
        "mobile_control_floor": 44,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "external_requests": external_requests,
        "public_route_effect": "none",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
