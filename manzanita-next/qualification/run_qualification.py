#!/usr/bin/env python3
"""Run the automated P8 qualification matrix over the exact P7 site."""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
import re
import socket
import threading
import time
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, Route, sync_playwright

CONTRACT_SCHEMA = "axm-tools/manzanita-resilience-qualification-contract@1"
REPORT_SCHEMA = "axm-tools/manzanita-resilience-qualification@1"
DATA_SCHEMA = "axm-tools/manzanita-whole-experience-data@1"
SNAPSHOT_SCHEMA = "axm-tools/manzanita-whole-experience-snapshot@1"

REQUIRED_SITE_FILES = (
    "index.html",
    "style.css",
    "app.js",
    "experience-data.js",
    "assets/base-imagery.png",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("OpenAI-style secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("Bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._~-]{16,}", re.I)),
    ("private-key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

HOSTILE_MARKER = 'M99-HOSTILE-<img src=x onerror="window.__M99_XSS__=true">-END'


class QualificationError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualificationError(f"Cannot load {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def recursive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key).lower())
            found.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(recursive_keys(item))
    return found


def experience_script(data: dict[str, Any]) -> str:
    return (
        "window.__MANZANITA_WHOLE_EXPERIENCE__ = "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )


def file_manifest(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def static_integrity(
    site: Path,
    data_path: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    for relative in REQUIRED_SITE_FILES:
        require((site / relative).is_file(), f"Built site lacks {relative}")

    data = load_json(data_path)
    require(data.get("schema") == DATA_SCHEMA, "Experience data schema drifted")
    require(data.get("place", {}).get("public_safe") is True, "P8 requires a public-safe P7 place")
    require(data.get("public_effect") == "none", "P7 data carries a public effect")
    require(data.get("constitutional_count_effect") == "none", "P7 data carries a task-count effect")
    require(data.get("release_effect") == "none", "P7 data carries release effect")
    require(len(data.get("apertures", [])) == 7, "P7 aperture count drifted")
    require(len(data.get("overlays", [])) == 8, "P7 overlay count drifted")
    require(len(data.get("roles", [])) == 5, "P7 role count drifted")

    prohibited_keys = set(contract["privacy_and_secret_law"]["prohibited_keys"])
    findings = sorted(recursive_keys(data) & prohibited_keys)
    require(not findings, f"Experience data contains prohibited keys: {findings}")

    index = (site / "index.html").read_text(encoding="utf-8")
    style = (site / "style.css").read_text(encoding="utf-8")
    app = (site / "app.js").read_text(encoding="utf-8")
    data_script = (site / "experience-data.js").read_text(encoding="utf-8")

    for token in (
        "default-src 'self'",
        "connect-src 'none'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ):
        require(token in index, f"CSP omits {token}")
    for pattern in (
        r"<script[^>]+src=[\"']https?://",
        r"<link[^>]+href=[\"']https?://",
        r"url\(\s*[\"']?https?://",
    ):
        require(not re.search(pattern, index + "\n" + style, re.I), "Static shell references a remote runtime asset")
    for token in ("fetch(", "XMLHttpRequest", "WebSocket(", "EventSource("):
        require(token not in app, f"P7 runtime contains a network primitive: {token}")
    require("escapeHTML" in app, "P7 runtime lacks its hostile-text escaping function")
    require(data_script == experience_script(data), "Built experience-data.js does not match EXPERIENCE_DATA.json")

    scan_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(site.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".json", ".txt", ".md"}
    )
    secret_findings = [name for name, pattern in SECRET_PATTERNS if pattern.search(scan_text)]
    require(not secret_findings, f"High-confidence secret patterns found: {secret_findings}")

    manifest = file_manifest(site)
    budgets = contract["performance_budgets"]
    total_bytes = sum(row["bytes"] for row in manifest)
    js_bytes = sum(row["bytes"] for row in manifest if row["path"].endswith(".js"))
    css_bytes = sum(row["bytes"] for row in manifest if row["path"].endswith(".css"))
    image_bytes = sum(row["bytes"] for row in manifest if row["path"].lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")))
    require(total_bytes <= budgets["site_total_bytes"], "Site exceeds the total byte budget")
    require(js_bytes <= budgets["javascript_bytes"], "JavaScript and governed data exceed the byte budget")
    require(css_bytes <= budgets["css_bytes"], "CSS exceeds the byte budget")
    require(image_bytes <= budgets["image_bytes"], "Image bytes exceed the byte budget")

    return {
        "id": "static_integrity",
        "result": "PASS",
        "site_file_count": len(manifest),
        "site_total_bytes": total_bytes,
        "javascript_bytes": js_bytes,
        "css_bytes": css_bytes,
        "image_bytes": image_bytes,
        "manifest": manifest,
        "manifest_sha256": sha256_bytes(canonical_bytes(manifest)),
        "experience_data_sha256": sha256_file(data_path),
        "prohibited_key_findings": findings,
        "secret_findings": secret_findings,
    }


def privacy_secret_scan(
    site: Path,
    data: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    prohibited = set(contract["privacy_and_secret_law"]["prohibited_keys"])
    key_findings = sorted(recursive_keys(data) & prohibited)
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(site.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".json", ".txt", ".md"}
    )
    pattern_findings = [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]
    require(not key_findings, f"Private or credential keys found: {key_findings}")
    require(not pattern_findings, f"High-confidence secrets found: {pattern_findings}")
    require(data["place"]["public_safe"] is True, "Privacy scan requires public-safe place state")
    return {
        "id": "privacy_secret_scan",
        "result": "PASS",
        "key_findings": key_findings,
        "pattern_findings": pattern_findings,
        "private_projection": "not_admitted",
        "credential_operation": "not_admitted",
        "public_effect": data["public_effect"],
        "release_effect": data["release_effect"],
    }


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
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


def runtime_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const runtime = window.__MANZANITA_WHOLE_EXPERIENCE_RUNTIME__;
          const data = window.__MANZANITA_WHOLE_EXPERIENCE__;
          return {
            version: runtime.version,
            experienceId: runtime.experienceId,
            placeId: runtime.placeId,
            sourceRunId: runtime.sourceRunId,
            state: runtime.getState(),
            counts: {
              apertures: data.apertures.length,
              overlays: data.overlays.length,
              roles: data.roles.length,
              sources: data.source_summary.sources.length,
            },
            effects: {
              public: data.public_effect,
              constitutional: data.constitutional_count_effect,
              release: data.release_effect,
            },
            sceneMode: data.scene.selected_mode,
            registration: data.registration.admission_state,
            fabRelease: data.fab_handoff.release_state,
            sourceStates: data.source_summary.state_counts,
            dataPayload: data.payload_sha256,
          };
        }
        """
    )


def horizontal_overflow(page: Page) -> int:
    return int(page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth"))


def visible_target_floor(page: Page) -> float:
    return float(
        page.evaluate(
            """
            () => {
              const rows = [...document.querySelectorAll('button')]
                .filter((node) => {
                  const style = getComputedStyle(node);
                  const box = node.getBoundingClientRect();
                  return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
                })
                .map((node) => node.getBoundingClientRect().height);
              return rows.length ? Math.min(...rows) : 0;
            }
            """
        )
    )


def attach_observers(page: Page, base_url: str) -> dict[str, list[str]]:
    observed: dict[str, list[str]] = {
        "console_errors": [],
        "page_errors": [],
        "external_requests": [],
        "all_requests": [],
        "request_failures": [],
    }
    base = urlparse(base_url)

    def on_request(request: Any) -> None:
        observed["all_requests"].append(request.url)
        target = urlparse(request.url)
        if target.scheme not in {"http", "https", "data", "blob"}:
            return
        if target.scheme in {"data", "blob"}:
            return
        if (target.hostname, target.port) != (base.hostname, base.port):
            observed["external_requests"].append(request.url)

    page.on("console", lambda message: observed["console_errors"].append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: observed["page_errors"].append(str(error)))
    page.on("request", on_request)
    page.on("requestfailed", lambda request: observed["request_failures"].append(request.url))
    return observed


def assert_core(page: Page, data: dict[str, Any]) -> dict[str, Any]:
    page.locator("#rail-place").wait_for(state="visible")
    snapshot = runtime_snapshot(page)
    require(snapshot["counts"] == {
        "apertures": len(data["apertures"]),
        "overlays": len(data["overlays"]),
        "roles": len(data["roles"]),
        "sources": len(data["source_summary"]["sources"]),
    }, "Runtime counts drifted")
    require(snapshot["effects"] == {"public": "none", "constitutional": "none", "release": "none"}, "Runtime effect boundary drifted")
    require(snapshot["fabRelease"] == "not_authorized", "FAB release boundary drifted")
    require(page.locator("#source-rail, .source-rail").count() == 1, "Source rail disappeared")
    require(page.locator("#degraded-ledger").count() == 1, "Degraded evidence ledger disappeared")
    require(page.locator("#operating-action").inner_text().strip() != "", "Next safe action disappeared")
    require(page.locator("#operating-authority").inner_text().strip() != "", "Authority disappeared")
    require("prohibited" in page.locator("body").inner_text().lower(), "Prohibited consequences disappeared")
    return snapshot


def assert_no_unexpected_errors(
    observed: dict[str, list[str]],
    *,
    allowed_failed_suffixes: tuple[str, ...] = (),
) -> None:
    failures = [
        url for url in observed["request_failures"]
        if not any(url.endswith(suffix) for suffix in allowed_failed_suffixes)
    ]
    require(not observed["console_errors"], f"Console errors: {observed['console_errors']}")
    require(not observed["page_errors"], f"Page errors: {observed['page_errors']}")
    require(not observed["external_requests"], f"Unexpected external requests: {observed['external_requests']}")
    require(not failures, f"Unexpected request failures: {failures}")


def browser_profile(
    browser: Browser,
    base_url: str,
    data: dict[str, Any],
    profile: dict[str, Any],
    output: Path,
    budgets: dict[str, Any],
) -> dict[str, Any]:
    context = browser.new_context(
        viewport=profile["viewport"],
        color_scheme=profile["color_scheme"],
        reduced_motion=profile["reduced_motion"],
        forced_colors=profile["forced_colors"],
        has_touch=profile["has_touch"],
        is_mobile=profile["is_mobile"],
    )
    page = context.new_page()
    observed = attach_observers(page, base_url)
    started = time.monotonic()
    page.goto(base_url, wait_until="networkidle")
    snapshot = assert_core(page, data)
    interactive_ms = round((time.monotonic() - started) * 1000, 2)
    overflow = horizontal_overflow(page)
    target_floor = visible_target_floor(page)
    dom_nodes = int(page.locator("*").count())
    require(interactive_ms <= budgets["first_interactive_ms"], f"{profile['id']} exceeds the interactive budget")
    require(overflow <= budgets["maximum_horizontal_overflow_css_px"], f"{profile['id']} has horizontal overflow")
    require(target_floor >= budgets["minimum_visible_target_css_px"], f"{profile['id']} has controls below 44 CSS pixels")
    require(dom_nodes <= budgets["dom_nodes"], f"{profile['id']} exceeds the DOM budget")
    require(len(observed["all_requests"]) <= budgets["request_count"], f"{profile['id']} exceeds the request budget")
    if profile["reduced_motion"] == "reduce":
        require(page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") is True, "Reduced-motion preference is inactive")
    if profile["forced_colors"] == "active":
        require(page.evaluate("matchMedia('(forced-colors: active)').matches") is True, "Forced-colors preference is inactive")
    if profile["has_touch"]:
        require(page.evaluate("navigator.maxTouchPoints") > 0, "Touch profile does not expose touch points")
    screenshot = output / f"p8-{profile['id']}.png"
    page.screenshot(path=str(screenshot), full_page=True)
    assert_no_unexpected_errors(observed)
    context.close()
    return {
        "id": profile["id"],
        "result": "PASS",
        "viewport": profile["viewport"],
        "color_scheme": profile["color_scheme"],
        "reduced_motion": profile["reduced_motion"],
        "forced_colors": profile["forced_colors"],
        "has_touch": profile["has_touch"],
        "interactive_ms": interactive_ms,
        "horizontal_overflow": overflow,
        "minimum_visible_target_height": target_floor,
        "dom_nodes": dom_nodes,
        "request_count": len(observed["all_requests"]),
        "screenshot": screenshot.name,
        "screenshot_sha256": sha256_file(screenshot),
        "state": snapshot["state"],
    }


def semantic_accessibility(browser: Browser, base_url: str, data: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    audit = page.evaluate(
        """
        () => {
          const ids = [...document.querySelectorAll('[id]')].map((node) => node.id);
          const duplicates = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
          const unlabeledButtons = [...document.querySelectorAll('button')]
            .filter((node) => !(node.getAttribute('aria-label') || node.innerText.trim()))
            .map((node) => node.id || node.outerHTML.slice(0, 80));
          const navsWithoutLabel = [...document.querySelectorAll('nav')]
            .filter((node) => !(node.getAttribute('aria-label') || node.getAttribute('aria-labelledby')))
            .length;
          return {
            duplicates,
            unlabeledButtons,
            navsWithoutLabel,
            mainCount: document.querySelectorAll('main').length,
            asideCount: document.querySelectorAll('aside[aria-label]').length,
            liveRegions: document.querySelectorAll('[aria-live]').length,
            dialogCount: document.querySelectorAll('dialog').length,
            skipTarget: document.querySelector('.skip-link')?.getAttribute('href'),
            documentLanguage: document.documentElement.lang,
          };
        }
        """
    )
    require(audit["duplicates"] == [], f"Duplicate DOM ids: {audit['duplicates']}")
    require(audit["unlabeledButtons"] == [], f"Unlabeled buttons: {audit['unlabeledButtons']}")
    require(audit["navsWithoutLabel"] == 0, "A navigation landmark lacks an accessible name")
    require(audit["mainCount"] == 1, "The page must expose one main landmark")
    require(audit["asideCount"] >= 1, "The source rail lacks an accessible landmark name")
    require(audit["liveRegions"] >= 1, "The page lacks a live status region")
    require(audit["dialogCount"] >= 1, "The help dialog is absent")
    require(audit["skipTarget"] == "#main", "The skip link does not target the operating surface")
    require(audit["documentLanguage"] == "en", "Document language is not declared")
    page.locator("#help-button").click()
    require(page.locator("#help-dialog").evaluate("node => node.open"), "Help dialog did not open")
    page.get_by_role("button", name="Close help").click()
    assert_no_unexpected_errors(observed)
    context.close()
    return {"id": "semantic_accessibility", "result": "PASS", **audit}


def keyboard_only(browser: Browser, base_url: str, data: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    first_aperture = data["aperture_order"][0]
    last_aperture = data["aperture_order"][-1]
    page.locator(f'[data-aperture="{first_aperture}"]').focus()
    page.keyboard.press("End")
    require(runtime_snapshot(page)["state"]["aperture"] == last_aperture, "End did not select the last aperture")
    page.keyboard.press("ArrowLeft")
    require(runtime_snapshot(page)["state"]["aperture"] == data["aperture_order"][-2], "ArrowLeft did not move one aperture")
    page.locator("#help-button").focus()
    page.keyboard.press("Enter")
    require(page.locator("#help-dialog").evaluate("node => node.open"), "Keyboard did not open help")
    page.keyboard.press("Escape")
    require(not page.locator("#help-dialog").evaluate("node => node.open"), "Escape did not close help")
    assert_no_unexpected_errors(observed)
    context.close()
    return {"id": "keyboard_only", "result": "PASS", "last_aperture": last_aperture, "final_aperture": data["aperture_order"][-2]}


def zoom_200_percent(browser: Browser, base_url: str, data: dict[str, Any], budgets: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.goto(base_url, wait_until="networkidle")
    page.evaluate("document.documentElement.style.fontSize = '200%'")
    page.wait_for_timeout(100)
    assert_core(page, data)
    overflow = horizontal_overflow(page)
    require(overflow <= budgets["maximum_horizontal_overflow_css_px"], "200 percent text zoom introduced horizontal overflow")
    require(page.locator("#operating-action").is_visible(), "Next safe action disappeared at 200 percent text zoom")
    assert_no_unexpected_errors(observed)
    context.close()
    return {"id": "zoom_200_percent", "result": "PASS", "horizontal_overflow": overflow, "next_safe_action_visible": True}


def low_end_cpu(browser: Browser, base_url: str, data: dict[str, Any], budgets: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1024, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    session = context.new_cdp_session(page)
    session.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    started = time.monotonic()
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    interactive_ms = round((time.monotonic() - started) * 1000, 2)
    require(interactive_ms <= budgets["first_interactive_ms"], "Low-end CPU campaign exceeded the interactive budget")
    page.locator(f'[data-aperture="{data["aperture_order"][-1]}"]').click()
    page.locator(f'[data-role="{data["role_order"][-1]}"]').click()
    require(runtime_snapshot(page)["state"]["role"] == data["role_order"][-1], "Low-end CPU campaign lost role operation")
    assert_no_unexpected_errors(observed)
    context.close()
    return {"id": "low_end_cpu", "result": "PASS", "throttle_rate": 4, "interactive_ms": interactive_ms}


def delayed_resources(browser: Browser, base_url: str, data: dict[str, Any], budgets: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1024, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)

    def delay(route: Route) -> None:
        time.sleep(0.12)
        route.continue_()

    page.route("**/*", delay)
    started = time.monotonic()
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    interactive_ms = round((time.monotonic() - started) * 1000, 2)
    require(interactive_ms <= budgets["first_interactive_ms"], "Delayed-resource campaign exceeded the interactive budget")
    assert_no_unexpected_errors(observed)
    context.close()
    return {"id": "delayed_resources", "result": "PASS", "delay_per_request_ms": 120, "interactive_ms": interactive_ms, "request_count": len(observed["all_requests"])}


def offline_after_load(browser: Browser, base_url: str, data: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1024, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    requests_before = len(observed["all_requests"])
    context.set_offline(True)
    page.locator(f'[data-overlay="{data["overlay_order"][-1]}"]').click()
    page.locator(f'[data-role="{data["role_order"][-1]}"]').click()
    page.locator('[data-section="sources"]').click()
    state = runtime_snapshot(page)["state"]
    requests_after = len(observed["all_requests"])
    require(state["overlay"] == data["overlay_order"][-1], "Offline operation lost overlay selection")
    require(state["role"] == data["role_order"][-1], "Offline operation lost role selection")
    require(requests_after == requests_before, "Offline operation attempted another request")
    context.set_offline(False)
    assert_no_unexpected_errors(observed)
    context.close()
    return {"id": "offline_after_load", "result": "PASS", "requests_before": requests_before, "requests_after": requests_after, "state": state}


def missing_base_image(browser: Browser, base_url: str, data: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1024, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.route("**/assets/base-imagery.png", lambda route: route.abort("failed"))
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    require(page.locator("#rail-receipt").inner_text().strip() != "", "Missing imagery erased the experience receipt")
    require(page.locator("#stage-caption").inner_text().strip() != "", "Missing imagery erased the registration claim boundary")
    assert_no_unexpected_errors(observed, allowed_failed_suffixes=("/assets/base-imagery.png",))
    context.close()
    return {"id": "missing_base_image", "result": "PASS", "expected_failed_resource": "assets/base-imagery.png", "receipt_visible": True, "claim_boundary_visible": True}


def recompute_source_counts(data: dict[str, Any]) -> None:
    counts = Counter(str(row.get("state", "unknown")) for row in data["source_summary"]["sources"])
    data["source_summary"]["state_counts"] = dict(sorted(counts.items()))
    data["source_summary"]["source_count"] = len(data["source_summary"]["sources"])


def mutate_data(base_data: dict[str, Any], mode: str) -> dict[str, Any]:
    data = copy.deepcopy(base_data)
    sources = data["source_summary"]["sources"]
    require(bool(sources), "Experience data has no sources to qualify")
    if mode == "stale_source":
        sources[0]["state"] = "stale"
        sources[0]["error"] = "P8 qualification injection: the retained source is stale and cannot support a current condition."
        sources[0]["source_time"] = "2000-01-01T00:00:00Z"
    elif mode == "provider_outage":
        target = next((row for row in sources if row["id"] in {"google_street_view", "mapillary", "kartaview", "panoramax"}), sources[0])
        target["state"] = "unavailable"
        target["error"] = "P8 qualification injection: provider unavailable; no generated observation is admitted."
    elif mode == "contradictory_source":
        require(len(sources) >= 2, "Contradiction campaign requires two sources")
        for index in (0, 1):
            sources[index]["state"] = "contradictory"
            sources[index]["error"] = f"P8 qualification injection: source {index + 1} contradicts another retained source and remains separate."
    elif mode == "hostile_text":
        data["roles"][0]["label"] = HOSTILE_MARKER
        data["apertures"][0]["reading"] = HOSTILE_MARKER
        sources[0]["error"] = HOSTILE_MARKER
        if sources[0].get("state") == "ok":
            sources[0]["state"] = "unknown"
    else:
        raise QualificationError(f"Unknown mutation mode: {mode}")
    recompute_source_counts(data)
    data["qualification_injection"] = {
        "mode": mode,
        "authority": "automated_test_only",
        "public_effect": "none",
        "release_effect": "none",
    }
    data.pop("payload_sha256", None)
    data["payload_sha256"] = sha256_bytes(canonical_bytes(data))
    return data


def mutated_campaign(
    browser: Browser,
    base_url: str,
    base_data: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    data = mutate_data(base_data, mode)
    context = browser.new_context(viewport={"width": 1024, "height": 900})
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.route(
        "**/experience-data.js",
        lambda route: route.fulfill(
            status=200,
            content_type="application/javascript; charset=utf-8",
            body=experience_script(data),
        ),
    )
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    page.locator('[data-section="sources"]').click()
    source_text = page.locator("#source-register").inner_text()
    rail_text = page.locator("#rail-source-counts").inner_text()
    state_word = {
        "stale_source": "stale",
        "provider_outage": "unavailable",
        "contradictory_source": "contradictory",
        "hostile_text": HOSTILE_MARKER,
    }[mode]
    if mode == "hostile_text":
        page.locator(f'[data-role="{data["role_order"][0]}"]').click()
        literal = page.locator(f'[data-role="{data["role_order"][0]}"]').inner_text()
        require(HOSTILE_MARKER in literal, "Hostile role label did not survive as literal text")
        require(page.locator("img[src='x']").count() == 0, "Hostile text created an image element")
        require(page.evaluate("window.__M99_XSS__") is None, "Hostile text executed script")
    else:
        require(state_word in source_text.lower(), f"{mode} state is not visible in the source register")
        require(state_word in rail_text.lower(), f"{mode} state is not visible in the source rail")
    assert_no_unexpected_errors(observed)
    context.close()
    return {
        "id": mode,
        "result": "PASS",
        "injection": data["qualification_injection"],
        "visible_state": state_word,
        "hostile_script_executed": False if mode == "hostile_text" else None,
        "hostile_element_created": False if mode == "hostile_text" else None,
        "source_state_counts": data["source_summary"]["state_counts"],
    }


def verify_snapshot(snapshot: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    require(snapshot.get("schema") == SNAPSHOT_SCHEMA, "Snapshot schema drifted")
    require(snapshot.get("experience_id") == data["experience_id"], "Snapshot experience identity drifted")
    require(snapshot.get("place", {}).get("id") == data["place"]["id"], "Snapshot place identity drifted")
    require(snapshot.get("source_run_id") == data["source_run_id"], "Snapshot source-run identity drifted")
    selected = snapshot.get("selected", {})
    require(selected.get("aperture") in set(data["aperture_order"]), "Snapshot aperture is not in the governed data")
    require(selected.get("overlay") in set(data["overlay_order"]), "Snapshot overlay is not in the governed data")
    require(selected.get("role") in set(data["role_order"]), "Snapshot role is not in the governed data")
    require(snapshot.get("donor_digests") == data["donor_digests"], "Snapshot donor digests drifted")
    require(snapshot.get("public_effect") == "none", "Snapshot carries a public effect")
    require(snapshot.get("constitutional_count_effect") == "none", "Snapshot carries a count effect")
    require(snapshot.get("release_state") == "not_authorized" or data.get("release_effect") == "none", "Snapshot carries release authority")
    require(snapshot.get("export_law", {}).get("private_record_transfer") == "prohibited", "Snapshot lost the private-transfer boundary")
    return {
        "result": "PASS",
        "selected": selected,
        "snapshot_sha256": sha256_bytes(canonical_bytes(snapshot)),
        "experience_payload_sha256": data["payload_sha256"],
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_state": "not_authorized",
    }


def export_reimport(browser: Browser, base_url: str, data: dict[str, Any], output: Path) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    page = context.new_page()
    observed = attach_observers(page, base_url)
    page.goto(base_url, wait_until="networkidle")
    assert_core(page, data)
    page.locator(f'[data-aperture="{data["aperture_order"][-1]}"]').click()
    page.locator(f'[data-overlay="{data["overlay_order"][-1]}"]').click()
    page.locator(f'[data-role="{data["role_order"][-1]}"]').click()
    with page.expect_download() as download_info:
        page.locator("#export-button").click()
    download = download_info.value
    snapshot_path = output / "p8-exported-snapshot.json"
    download.save_as(snapshot_path)
    snapshot = load_json(snapshot_path)
    replay = verify_snapshot(snapshot, data)
    write_json(output / "P8_REIMPORT_RECEIPT.json", replay)
    assert_no_unexpected_errors(observed)
    context.close()
    return {
        "id": "export_reimport",
        "result": "PASS",
        "snapshot": snapshot_path.name,
        "snapshot_bytes": snapshot_path.stat().st_size,
        "snapshot_file_sha256": sha256_file(snapshot_path),
        "reimport_receipt": "P8_REIMPORT_RECEIPT.json",
        "replay": replay,
    }


def run_matrix(
    site: Path,
    data_path: Path,
    contract_path: Path,
    output: Path,
) -> dict[str, Any]:
    site = site.resolve()
    data_path = data_path.resolve()
    contract_path = contract_path.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    contract = load_json(contract_path)
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected qualification contract schema")
    data = load_json(data_path)

    campaigns: list[dict[str, Any]] = [
        static_integrity(site, data_path, contract),
        privacy_secret_scan(site, data, contract),
    ]

    base_context = (
        contextlib.nullcontext((site / "index.html").as_uri())
        if os.environ.get("P8_USE_FILE_URL")
        else serve(site)
    )
    with base_context as base_url, sync_playwright() as playwright:
        launch_kwargs: dict[str, Any] = {"headless": True}
        if os.environ.get("P8_CHROMIUM_EXECUTABLE"):
            launch_kwargs["executable_path"] = os.environ["P8_CHROMIUM_EXECUTABLE"]
            launch_kwargs["args"] = ["--no-sandbox", "--no-proxy-server", "--proxy-bypass-list=*"]
        browser = playwright.chromium.launch(**launch_kwargs)
        try:
            for profile in contract["browser_profiles"]:
                campaigns.append(browser_profile(browser, base_url, data, profile, output, contract["performance_budgets"]))
            campaigns.append(semantic_accessibility(browser, base_url, data))
            campaigns.append(keyboard_only(browser, base_url, data))
            campaigns.append(zoom_200_percent(browser, base_url, data, contract["performance_budgets"]))
            campaigns.append(low_end_cpu(browser, base_url, data, contract["performance_budgets"]))
            campaigns.append(delayed_resources(browser, base_url, data, contract["performance_budgets"]))
            campaigns.append(offline_after_load(browser, base_url, data))
            campaigns.append(missing_base_image(browser, base_url, data))
            for mode in ("stale_source", "provider_outage", "contradictory_source", "hostile_text"):
                campaigns.append(mutated_campaign(browser, base_url, data, mode))
            campaigns.append(export_reimport(browser, base_url, data, output))
        finally:
            browser.close()

    campaign_ids = [row["id"] for row in campaigns]
    require(len(campaign_ids) == len(set(campaign_ids)), "Qualification campaign ids are duplicated")
    require(set(campaign_ids) == set(contract["required_campaigns"]), f"Qualification campaign coverage drifted: {sorted(set(campaign_ids) ^ set(contract['required_campaigns']))}")
    require(all(row.get("result") == "PASS" for row in campaigns), "One or more P8 campaigns failed")

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "result": "PASS",
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "phase": contract["phase"],
        "experience_id": data["experience_id"],
        "experience_payload_sha256": data["payload_sha256"],
        "experience_data_sha256": sha256_file(data_path),
        "site_manifest_sha256": campaigns[0]["manifest_sha256"],
        "campaign_count": len(campaigns),
        "required_campaigns": contract["required_campaigns"],
        "campaigns": campaigns,
        "retained_holds": contract["retained_holds"],
        "physical_campaigns_performed": False,
        "real_assistive_technology_claim": False,
        "real_device_claim": False,
        "actual_network_claim": False,
        "private_projection_claim": False,
        "credentialed_provider_claim": False,
        "field_operation_claim": False,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    report["payload_sha256"] = sha256_bytes(canonical_bytes(report))
    write_json(output / "QUALIFICATION_REPORT.json", report)
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--experience-data", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=root / "QUALIFICATION_CONTRACT.json")
    parser.add_argument("--output", type=Path, default=root / "out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_matrix(args.site, args.experience_data, args.contract, args.output)
    print(json.dumps({
        "result": report["result"],
        "campaign_count": report["campaign_count"],
        "retained_hold_count": len(report["retained_holds"]),
        "physical_campaigns_performed": report["physical_campaigns_performed"],
        "public_effect": report["public_effect"],
        "constitutional_count_effect": report["constitutional_count_effect"],
        "release_effect": report["release_effect"],
        "report_sha256": report["payload_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
