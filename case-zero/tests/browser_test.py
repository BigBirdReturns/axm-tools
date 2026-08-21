#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import http.server
import json
import socket
import tempfile
import threading
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def serve_root():
    port = free_port()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/case-zero/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def main() -> None:
    with tempfile.TemporaryDirectory() as raw, serve_root() as url, sync_playwright() as pw:
        temporary = Path(raw)
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        external_requests: list[str] = []
        console_errors: list[str] = []

        def guard(route):
            request_url = route.request.url
            if not request_url.startswith(url.rsplit("/case-zero/", 1)[0]):
                external_requests.append(request_url)
                route.abort()
            else:
                route.continue_()

        page.route("**/*", guard)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto(url, wait_until="networkidle")
        page.get_by_text("Local only. Network disabled.").wait_for()
        assert page.locator("#run").is_disabled()

        page.locator("#sample").click()
        assert "7 files selected" in page.locator("#selection").inner_text()
        page.locator("#run").click()
        page.locator("#results.visible").wait_for()
        assert page.locator("#caseStatus").inner_text() == "INTAKE_BOUND_PREVIEW"
        assert page.locator("#taskRows tr").count() == 10
        assert page.locator("#sourceRows tr").count() == 7
        assert page.locator("#mFiles").inner_text() == "7"

        with page.expect_download() as runner_download:
            page.locator("#downloadRunner").click()
        runner_path = Path(runner_download.value.path())
        runner_text = runner_path.read_text(encoding="utf-8")
        assert "redcat/case-zero-intake@0.1" in runner_text
        assert "network_calls" in runner_text

        with page.expect_download() as pre_read_download:
            page.locator("#downloadPreRead").click()
        pre_read = Path(pre_read_download.value.path()).read_text(encoding="utf-8")
        assert "RedCat retains the client relationship" in pre_read

        with page.expect_download() as local_download:
            page.locator("#exportLocal").click()
        local_packet = json.loads(Path(local_download.value.path()).read_text(encoding="utf-8"))
        assert local_packet["manifest"]["source_count"] == 7
        assert local_packet["manifest"]["network_calls"] == 0
        assert local_packet["manifest"]["source_contents_exported"] == 0

        with page.expect_download() as safe_download:
            page.locator("#exportSafe").click()
        safe_packet = json.loads(Path(safe_download.value.path()).read_text(encoding="utf-8"))
        safe_sources = safe_packet["manifest"]["sources"]
        assert len(safe_sources) == 7
        assert all("source_alias" in row and "path" not in row for row in safe_sources)

        secret = "AKIAABCDEFGHIJKLMNOP"
        secret_path = temporary / "environment.txt"
        secret_path.write_text(f"AWS_KEY={secret}\n", encoding="utf-8")
        page.locator("#fileInput").set_input_files(str(secret_path))
        page.locator("#run").click()
        page.locator("#caseStatus").wait_for()
        assert page.locator("#caseStatus").inner_text() == "HOLD_REDACTION_REQUIRED"
        with page.expect_download() as held_download:
            page.locator("#exportSafe").click()
        held_text = Path(held_download.value.path()).read_text(encoding="utf-8")
        assert secret not in held_text
        assert "aws_access_key" in held_text

        page.set_viewport_size({"width": 390, "height": 844})
        page.reload(wait_until="networkidle")
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 1
        page.evaluate("document.documentElement.style.fontSize='200%'")
        overflow_200 = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow_200 <= 1

        assert not external_requests, external_requests
        assert not console_errors, console_errors
        context.close()
        browser.close()
        print("CASE_ZERO_BROWSER_PASS")


if __name__ == "__main__":
    main()
