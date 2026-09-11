from __future__ import annotations

import json
import mimetypes
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("MW_RECEIVER_AUDIT_OUT", "/tmp/manzanita-receiver-journey-audit"))
OUT.mkdir(parents=True, exist_ok=True)

PRODUCTION_HOSTS = {"bigbirdreturns.github.io"}
REPO_PREFIX = "/axm-tools"

ROUTES = [
    {
        "id": "repository-root",
        "path": "/",
        "title": "axm-tools",
        "ready": ".tool",
        "purpose": "Repository discovery",
    },
    {
        "id": "working-model",
        "path": "/manzanita-working-model/",
        "title": "Manzanita Works · Working Model",
        "ready": "#stage-list li",
        "purpose": "Public explanation and pilot preparation",
    },
    {
        "id": "place-fabric",
        "path": "/manzanita/",
        "title": "Manzanita Works · The Place Fabric",
        "ready": "#apertureRail button",
        "purpose": "Place evidence and assistance path",
    },
    {
        "id": "essential-attention",
        "path": "/essential-attention/",
        "title": "Essential Attention v1.2.1 · FAB Operating Desk",
        "ready": "#view-overview.active",
        "purpose": "Case continuity and bounded decisions",
    },
    {
        "id": "mila-return",
        "path": "/essential-attention/?projection=mila",
        "title": "Mila review · Essential Attention v1.2.1",
        "ready": "#view-executive.active",
        "purpose": "Decision-only return projection",
    },
    {
        "id": "operating-fabric",
        "path": "/manzanita-works/",
        "title": "Manzanita Works · Operating Fabric Dreamboard v0.2.0",
        "ready": "#stickies .sticky",
        "purpose": "Shared capacity and institutional substrate",
    },
]

EXPECTED_JOURNEY_LINKS = {
    "repository-root": {"working-model", "place-fabric", "essential-attention", "operating-fabric"},
    "working-model": {"place-fabric", "essential-attention", "operating-fabric"},
    "place-fabric": {"essential-attention"},
    "operating-fabric": {"place-fabric", "essential-attention"},
}

PATH_TO_ROUTE = {
    "/": "repository-root",
    "/manzanita-working-model/": "working-model",
    "/manzanita/": "place-fabric",
    "/essential-attention/": "essential-attention",
    "/manzanita-works/": "operating-fabric",
}

MIME_OVERRIDES = {
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def guess_type(self, path: str) -> str:
        suffix = Path(path).suffix.lower()
        return MIME_OVERRIDES.get(suffix, mimetypes.guess_type(path)[0] or "application/octet-stream")


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


def normalize_path(url: str, origin: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    origin_parsed = urllib.parse.urlparse(origin)
    if parsed.netloc and parsed.netloc not in {origin_parsed.netloc, *PRODUCTION_HOSTS}:
        return None
    path = parsed.path or "/"
    if path.startswith(REPO_PREFIX + "/"):
        path = path[len(REPO_PREFIX) :]
    if path == REPO_PREFIX:
        path = "/"
    if not path.endswith("/") and not Path(path).suffix:
        path += "/"
    return path


def route_from_url(url: str, origin: str) -> str | None:
    path = normalize_path(url, origin)
    return PATH_TO_ROUTE.get(path or "")


def request_status(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "mw-receiver-journey-audit/1"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)
    except Exception:
        return 0


def viewport_probe(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const visible = element => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
          };
          const directText = element => [...element.childNodes]
            .filter(node => node.nodeType === Node.TEXT_NODE)
            .map(node => node.textContent || '')
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
          const describe = element => ({
            tag: element.tagName.toLowerCase(),
            id: element.id || '',
            className: typeof element.className === 'string' ? element.className : '',
            text: (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
          });
          const textFloor = [...document.querySelectorAll('body *')].flatMap(element => {
            if (!visible(element) || !directText(element)) return [];
            if (element.matches('.sr-only,[aria-hidden="true"],script,style,noscript')) return [];
            const size = parseFloat(getComputedStyle(element).fontSize || '0');
            return size < 11 ? [{...describe(element), fontSize: size}] : [];
          });
          const controls = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[role="button"],[role="tab"]')].flatMap(element => {
            if (!visible(element)) return [];
            const rect = element.getBoundingClientRect();
            return rect.width < 44 || rect.height < 44
              ? [{...describe(element), width: Math.round(rect.width * 10) / 10, height: Math.round(rect.height * 10) / 10}]
              : [];
          });
          const headings = [...document.querySelectorAll('h1,h2,h3')].flatMap(element => {
            if (!visible(element)) return [];
            const style = getComputedStyle(element);
            const clippedX = element.scrollWidth > element.clientWidth + 1 && !['visible','clip'].includes(style.overflowX);
            const clippedY = element.scrollHeight > element.clientHeight + 1 && !['visible','clip'].includes(style.overflowY);
            return clippedX || clippedY ? [{...describe(element), scrollWidth: element.scrollWidth, clientWidth: element.clientWidth, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight}] : [];
          });
          const links = [...document.querySelectorAll('a[href]')].filter(visible).map(element => ({
            raw: element.getAttribute('href') || '',
            absolute: element.href,
            text: (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
          }));
          const main = document.querySelector('main') || document.body;
          const mainRect = main.getBoundingClientRect();
          return {
            title: document.title,
            heading: (document.querySelector('h1')?.innerText || document.querySelector('h2')?.innerText || '').replace(/\s+/g, ' ').trim(),
            documentWidth: document.documentElement.scrollWidth,
            viewportWidth: document.documentElement.clientWidth,
            documentHeight: document.documentElement.scrollHeight,
            viewportHeight: document.documentElement.clientHeight,
            horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
            mainVisible: mainRect.width > 0 && mainRect.height > 0,
            textFloor,
            controls,
            clippedHeadings: headings,
            links,
          };
        }"""
    )


def attach_observers(page: Page, origin: str) -> dict[str, list[str]]:
    state = {"page_errors": [], "console_errors": [], "failed_requests": [], "external_requests": []}
    page.on("pageerror", lambda error: state["page_errors"].append(str(error)))
    page.on(
        "console",
        lambda message: state["console_errors"].append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("requestfailed", lambda request: state["failed_requests"].append(f"{request.url} :: {request.failure}"))
    page.on(
        "request",
        lambda request: state["external_requests"].append(request.url)
        if not request.url.startswith((origin + "/", "data:", "blob:", "about:"))
        else None,
    )
    return state


def open_route(context: BrowserContext, origin: str, route: dict[str, str]) -> tuple[Page, dict[str, list[str]]]:
    page = context.new_page()
    observers = attach_observers(page, origin)
    page.goto(origin + route["path"], wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_selector(route["ready"], timeout=30_000)
    page.wait_for_timeout(250)
    return page, observers


def unique(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def write_report(audit: dict[str, Any]) -> None:
    lines = [
        "# Manzanita receiver-journey audit",
        "",
        f"**Classification:** `{audit['classification']}`  ",
        f"**Generated:** `{audit['generated_at']}`  ",
        f"**Branch SHA:** `{audit.get('source_sha', 'unknown')}`",
        "",
        "This audit drives the branch-local repository root, Working Model, Place Fabric, ordinary Essential Attention desk, Mila return projection, and Operating Fabric. It records observed browser behavior; it does not infer institutional adoption or authorize an external effect.",
        "",
        "## Route ledger",
        "",
        "| Route | Purpose | Desktop overflow | Mobile overflow | 320px/200% overflow | Small text | Small controls | Browser errors |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for route in audit["routes"]:
        desktop = route["views"]["desktop"]
        mobile = route["views"]["mobile"]
        zoom = route["views"]["zoom_320_200"]
        lines.append(
            f"| `{route['id']}` | {route['purpose']} | {int(desktop['horizontalOverflow'])} | {int(mobile['horizontalOverflow'])} | {int(zoom['horizontalOverflow'])} | {route['text_floor_count']} | {route['control_floor_count']} | {route['browser_error_count']} |"
        )
    lines.extend(["", "## Journey topology", ""])
    for route_id, result in audit["journey_topology"].items():
        lines.append(
            f"- **{route_id}:** expected `{', '.join(result['expected']) or 'none'}`; observed `{', '.join(result['observed']) or 'none'}`; missing `{', '.join(result['missing']) or 'none'}`."
        )
    lines.extend(["", "## Controlling findings", ""])
    if audit["findings"]:
        lines.extend(f"- {finding}" for finding in audit["findings"])
    else:
        lines.append("- No controlling finding remained.")
    lines.extend(["", "## Same-origin link checks", ""])
    if audit["broken_links"]:
        lines.extend(f"- `{item['url']}` returned `{item['status']}` from `{item['source_route']}`." for item in audit["broken_links"])
    else:
        lines.append("- All discovered branch-local links returned a successful status.")
    lines.extend(
        [
            "",
            "## Acceptance rule",
            "",
            "The journey passes only when every route loads with its expected identity, browser and console errors remain zero, runtime external requests remain zero, desktop/mobile/320px-at-200%-text horizontal overflow remains zero, headings remain unclipped, branch-local links resolve, and the declared receiver transitions exist. Text and control floors remain convergence findings until cleared or explicitly justified per surface.",
            "",
        ]
    )
    (OUT / "AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    source_sha = os.environ.get("GITHUB_SHA", "unknown")
    route_results: list[dict[str, Any]] = []
    all_link_rows: list[dict[str, str]] = []

    with serve_root() as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for route in ROUTES:
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
                page, observers = open_route(context, origin, route)
                desktop = viewport_probe(page)
                page.screenshot(path=str(OUT / f"{route['id']}-desktop.png"), full_page=True)

                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(150)
                mobile = viewport_probe(page)
                page.screenshot(path=str(OUT / f"{route['id']}-mobile.png"), full_page=True)

                page.set_viewport_size({"width": 320, "height": 800})
                page.evaluate("document.documentElement.style.fontSize='200%'")
                page.wait_for_timeout(150)
                zoom = viewport_probe(page)
                page.screenshot(path=str(OUT / f"{route['id']}-320-200pct.png"), full_page=True)

                links = unique(desktop["links"] + mobile["links"] + zoom["links"])
                journey_targets = sorted(
                    {
                        target
                        for link in links
                        if (target := route_from_url(link["absolute"], origin)) is not None
                    }
                )
                for link in links:
                    parsed = urllib.parse.urlparse(link["absolute"])
                    if parsed.netloc == urllib.parse.urlparse(origin).netloc:
                        all_link_rows.append({"source_route": route["id"], "url": link["absolute"]})

                text_floor = unique(desktop["textFloor"] + mobile["textFloor"])
                control_floor = unique(desktop["controls"] + mobile["controls"])
                clipped = unique(desktop["clippedHeadings"] + mobile["clippedHeadings"] + zoom["clippedHeadings"])
                route_results.append(
                    {
                        "id": route["id"],
                        "path": route["path"],
                        "purpose": route["purpose"],
                        "expected_title": route["title"],
                        "observed_title": desktop["title"],
                        "title_match": desktop["title"] == route["title"],
                        "heading": desktop["heading"],
                        "views": {
                            "desktop": desktop,
                            "mobile": mobile,
                            "zoom_320_200": zoom,
                        },
                        "journey_targets": journey_targets,
                        "text_floor_count": len(text_floor),
                        "text_floor_offenders": text_floor,
                        "control_floor_count": len(control_floor),
                        "control_floor_offenders": control_floor,
                        "clipped_heading_count": len(clipped),
                        "clipped_headings": clipped,
                        "browser_error_count": sum(len(value) for value in observers.values()),
                        "browser_errors": observers,
                    }
                )
                context.close()
        finally:
            browser.close()

        broken_links: list[dict[str, Any]] = []
        checked: set[str] = set()
        for row in all_link_rows:
            parsed = urllib.parse.urlparse(row["url"])
            target = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))
            if target in checked:
                continue
            checked.add(target)
            status = request_status(target)
            if status < 200 or status >= 400:
                broken_links.append({**row, "url": target, "status": status})

    journey_topology: dict[str, Any] = {}
    route_by_id = {route["id"]: route for route in route_results}
    for route_id, expected in EXPECTED_JOURNEY_LINKS.items():
        observed = set(route_by_id[route_id]["journey_targets"])
        journey_topology[route_id] = {
            "expected": sorted(expected),
            "observed": sorted(observed),
            "missing": sorted(expected - observed),
        }

    findings: list[str] = []
    for route in route_results:
        if not route["title_match"]:
            findings.append(f"{route['id']} title differs from its declared receiver identity.")
        if any(view["horizontalOverflow"] for view in route["views"].values()):
            findings.append(f"{route['id']} overflows horizontally in at least one qualified viewport.")
        if route["clipped_heading_count"]:
            findings.append(f"{route['id']} clips {route['clipped_heading_count']} visible heading state(s).")
        if route["browser_error_count"]:
            findings.append(f"{route['id']} emitted {route['browser_error_count']} browser, console, failed-request, or runtime external-request error(s).")
        if route["text_floor_count"]:
            findings.append(f"{route['id']} exposes {route['text_floor_count']} visible text state(s) below 11 CSS pixels.")
        if route["control_floor_count"]:
            findings.append(f"{route['id']} exposes {route['control_floor_count']} interactive control state(s) below the 44 CSS-pixel floor.")
    for route_id, topology in journey_topology.items():
        if topology["missing"]:
            findings.append(f"{route_id} lacks declared receiver transition(s): {', '.join(topology['missing'])}.")
    if broken_links:
        findings.append(f"{len(broken_links)} branch-local link target(s) failed HTTP resolution.")

    hard_fail = any(
        not route["title_match"]
        or any(view["horizontalOverflow"] for view in route["views"].values())
        or route["clipped_heading_count"]
        or route["browser_error_count"]
        for route in route_results
    ) or bool(broken_links) or any(item["missing"] for item in journey_topology.values())
    floor_fail = any(route["text_floor_count"] or route["control_floor_count"] for route in route_results)
    classification = (
        "PASS_MANZANITA_RECEIVER_JOURNEY_CONVERGED"
        if not hard_fail and not floor_fail
        else "HOLD_MANZANITA_RECEIVER_JOURNEY_CONVERGENCE_REQUIRED"
    )

    audit = {
        "schema": "manzanita-works/receiver-journey-audit@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sha": source_sha,
        "classification": classification,
        "routes": route_results,
        "journey_topology": journey_topology,
        "broken_links": broken_links,
        "findings": findings,
        "external_effect": "none",
    }
    (OUT / "AUDIT.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(audit)

    print(json.dumps({
        "classification": classification,
        "routes": len(route_results),
        "findings": len(findings),
        "broken_links": len(broken_links),
        "output": str(OUT),
    }, indent=2))
    return 0 if classification.startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
