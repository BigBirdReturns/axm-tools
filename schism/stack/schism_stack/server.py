"""Loopback-only operator console with origin and session-write checks."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser

from . import identity
from .common import Refusal, canonical
from .engine import Engine
from .evidence import export_evidence
from .transport import add_peer, peer_request, remove_peer


def make_server(engine, port=8371):
    token = secrets.token_urlsafe(32)
    web_root = Path(__file__).parent / "web"

    class Handler(BaseHTTPRequestHandler):
        server_version = "SCHISM"
        sys_version = ""

        def log_message(self, *args):
            pass

        def _origin(self):
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in allowed:
                raise Refusal("Request host is not the local console")
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + value for value in allowed}:
                raise Refusal("Cross-origin console request refused")
            if self.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
                raise Refusal("Cross-site console request refused")

        def _write(self):
            self._origin()
            if not secrets.compare_digest(self.headers.get("X-SCHISM-Token", ""), token):
                raise Refusal("Local session token is missing or expired; refresh the console")

        def _body(self, limit):
            if self.headers.get("Transfer-Encoding"):
                raise Refusal("Chunked uploads are not supported")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise Refusal("Invalid request length") from exc
            if length < 1 or length > limit:
                raise Refusal("Request exceeds the allowed size or is empty")
            self.connection.settimeout(30)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise Refusal("Request body is incomplete")
            return raw

        def _send(self, body, status=200, mime="application/json; charset=utf-8", download=None):
            if not isinstance(body, bytes):
                body = canonical(body)
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="' + download + '"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                self._origin()
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                if parsed.path.startswith("/api/"):
                    self._write()
                if parsed.path == "/api/token":
                    self._send({"token": token})
                elif parsed.path == "/api/state":
                    self._send(engine.snapshot())
                elif parsed.path == "/api/job":
                    self._send(engine.job(query.get("id", [None])[0]))
                elif parsed.path == "/api/export":
                    path = engine.root / "exports" / "schism-evidence.zip"
                    with engine.store.lock("evidence-export"):
                        export_evidence(engine, path)
                        raw = path.read_bytes()
                    self._send(raw, mime="application/zip", download="schism-evidence.zip")
                elif parsed.path == "/api/peer-state":
                    self._send(peer_request(engine, query.get("name", [None])[0], {"operation": "state"}))
                elif parsed.path in {"/", "/index.html", "/app.js", "/style.css", "/guide"}:
                    name = "index.html" if parsed.path in {"/", "/index.html"} else ("guide.html" if parsed.path == "/guide" else parsed.path[1:])
                    path = web_root / name
                    if not path.is_file():
                        self._send({"error": "Page is not present"}, 404)
                    else:
                        self._send(path.read_bytes(), mime=(mimetypes.guess_type(name)[0] or "application/octet-stream") + "; charset=utf-8")
                else:
                    self._send({"error": "Route not found"}, 404)
            except Refusal as exc:
                self._send({"error": str(exc)}, 403)
            except Exception as exc:
                self._send({"error": str(exc)}, 400)

        def do_POST(self):
            try:
                self._write()
                path = urlsplit(self.path).path
                if path == "/api/import":
                    raw = self._body(64 * 1024 * 1024)
                    fd, temporary = tempfile.mkstemp(suffix=".schism", dir=engine.root / "incoming")
                    try:
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(raw)
                        self._send(engine.import_package(temporary))
                    finally:
                        Path(temporary).unlink(missing_ok=True)
                elif path == "/api/action":
                    self._send(engine.submit(json.loads(self._body(1024 * 1024))), 202)
                elif path == "/api/peer":
                    self._send(add_peer(engine, json.loads(self._body(65536))))
                elif path == "/api/peer-action":
                    request = json.loads(self._body(1024 * 1024))
                    self._send(peer_request(engine, request["name"], {"operation": "action", "request": request["request"]}), 202)
                elif path == "/api/peer-remove":
                    self._send(remove_peer(engine, json.loads(self._body(65536))["name"]))
                else:
                    self._send({"error": "Route not found"}, 404)
            except Refusal as exc:
                self._send({"error": str(exc)}, 409)
            except Exception as exc:
                self._send({"error": str(exc)}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.session_token = token
    return server


def serve(engine, port=8371, open_browser=False):
    with make_server(engine, port) as server:
        url = f"http://127.0.0.1:{server.server_port}/#token={server.session_token}"
        print("SCHISM console: " + url, flush=True)
        print("State: " + str(engine.root), flush=True)
        print("Closing this console leaves detached application jobs and services running.", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0
