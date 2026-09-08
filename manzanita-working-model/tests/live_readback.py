#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ["MW_WORKING_MODEL_URL"].rstrip("/") + "/"
ROOT_URL = os.environ.get("MW_ROOT_URL", urllib.parse.urljoin(BASE_URL, "../"))
SOURCE_SHA = os.environ.get("GITHUB_SHA", "UNRESOLVED")
OUTPUT = Path(os.environ.get("MW_WORKING_MODEL_LIVE_MANIFEST", "/tmp/manzanita-working-model-live-manifest.json"))
RELEASE = "mw-working-model-v1.0.0"
FILES = [
    "index.html",
    "app.js",
    "style-base.css",
    "style.css",
    "WORKING_MODEL_CONTRACT.json",
    "RELEASE_CONTRACT.json",
    "README.md",
]
REMOVED_FILES = ["assets/property.webp", "assets/household.webp"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Accept-Encoding": "identity",
            "User-Agent": "axm-tools-manzanita-working-model-live-readback/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(), response.headers.get("Content-Type", "")


def cache_busted(url: str, attempt: int) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}release={urllib.parse.quote(RELEASE)}&source={urllib.parse.quote(SOURCE_SHA)}&attempt={attempt}"


def main() -> None:
    expected = {}
    for relative in FILES:
        data = (ROOT / relative).read_bytes()
        expected[relative] = {"bytes": len(data), "sha256": digest(data)}

    last_observation: dict[str, object] = {}
    for attempt in range(1, 121):
        observed: dict[str, object] = {}
        mismatches: list[dict[str, object]] = []
        for relative in FILES:
            url = urllib.parse.urljoin(BASE_URL, urllib.parse.quote(relative, safe="/"))
            try:
                data, content_type = fetch(cache_busted(url, attempt))
                row = {
                    "url": url,
                    "bytes": len(data),
                    "sha256": digest(data),
                    "content_type": content_type,
                }
                observed[relative] = row
                if row["bytes"] != expected[relative]["bytes"] or row["sha256"] != expected[relative]["sha256"]:
                    mismatches.append({"path": relative, "expected": expected[relative], "observed": row})
            except (urllib.error.URLError, TimeoutError) as exc:
                mismatches.append({"path": relative, "error": str(exc)})


        removed_observed: dict[str, object] = {}
        for relative in REMOVED_FILES:
            url = urllib.parse.urljoin(BASE_URL, urllib.parse.quote(relative, safe="/"))
            try:
                data, content_type = fetch(cache_busted(url, attempt))
                row = {
                    "url": url,
                    "bytes": len(data),
                    "sha256": digest(data),
                    "content_type": content_type,
                    "status": "UNEXPECTEDLY_PRESENT",
                }
                removed_observed[relative] = row
                mismatches.append({"path": relative, "expected": "REMOVED", "observed": row})
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    removed_observed[relative] = {"url": url, "status": "PASS_REMOVED", "http_status": 404}
                else:
                    mismatches.append({"path": relative, "expected": "REMOVED", "http_status": exc.code})
            except (urllib.error.URLError, TimeoutError) as exc:
                mismatches.append({"path": relative, "expected": "REMOVED", "error": str(exc)})

        root_ok = False
        root_error = None
        try:
            root_data, _ = fetch(cache_busted(ROOT_URL, attempt))
            root_ok = b'href="manzanita-working-model/"' in root_data
            if not root_ok:
                root_error = "root directory does not expose manzanita-working-model/"
        except (urllib.error.URLError, TimeoutError) as exc:
            root_error = str(exc)

        last_observation = {
            "attempt": attempt,
            "mismatches": mismatches,
            "root_directory_link": root_ok,
            "root_error": root_error,
        }
        if not mismatches and root_ok:
            index_text = (ROOT / "index.html").read_text(encoding="utf-8")
            app_text = (ROOT / "app.js").read_text(encoding="utf-8")
            if f'content="{RELEASE}"' not in index_text or f"const RELEASE = '{RELEASE}';" not in app_text:
                raise AssertionError("local release identity differs from the live-readback contract")
            payload = {
                "schema": "manzanita-works/working-model-live-byte-readback@1",
                "result": "PASS_EXACT_LIVE_RELEASE_BYTES",
                "release": RELEASE,
                "source_sha": SOURCE_SHA,
                "page_url": BASE_URL,
                "root_url": ROOT_URL,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "attempt": attempt,
                "root_directory_link": True,
                "removed_files": removed_observed,
                "files": {
                    relative: {"expected": expected[relative], "observed": observed[relative]}
                    for relative in FILES
                },
                "public_effect": "static_route_observed",
                "institutional_acceptance": False,
                "program_external_effect": "none",
            }
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(payload, indent=2))
            return

        print(json.dumps(last_observation, separators=(",", ":")), flush=True)
        time.sleep(5)

    raise AssertionError(json.dumps(last_observation, indent=2))


if __name__ == "__main__":
    main()
