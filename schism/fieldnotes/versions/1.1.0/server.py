#!/usr/bin/env python3
"""Fieldnotes: a private notebook stored as portable UTF-8 JSON files."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import parse_qs, urlsplit
import uuid
import zipfile

VERSION = "1.1.0"
PINNING = True
PORT = 8787
ORIGIN = f"http://127.0.0.1:{PORT}"
TOKEN = secrets.token_urlsafe(32)
DATA = Path(os.environ["SCHISM_DATA"])
WORK = Path(os.environ["SCHISM_WORK"])
SOURCE = Path(__file__).resolve().parent
NOTES = DATA / "notes"
MAX_NOTE_BYTES = 262144
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_NOTES = 2000
MAX_TOTAL_BYTES = 32 * 1024 * 1024
LOCK = threading.RLock()
ID = re.compile(r"[a-f0-9]{32}")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    tmp = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        tmp.unlink(missing_ok=True)


def validate_fields(value):
    title, body, tags = value.get("title"), value.get("body"), value.get("tags")
    if not isinstance(title, str) or not title.strip() or len(title) > 180:
        raise ValueError("Give the note a title of 1 to 180 characters.")
    if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_NOTE_BYTES:
        raise ValueError("A note can contain up to 256 KiB of UTF-8 text.")
    if not isinstance(tags, list) or len(tags) > 10 or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 24 for tag in tags):
        raise ValueError("Use up to 10 tags, each 1 to 24 characters.")
    for flag in ("archived", "pinned"):
        if type(value.get(flag, False)) is not bool:
            raise ValueError("Note flags must be true or false.")
    return {"title": title.strip(), "body": body, "tags": list(dict.fromkeys(tag.strip() for tag in tags)),
            "archived": value.get("archived", False), "pinned": value.get("pinned", False)}


def read_note(note_id):
    if not isinstance(note_id, str) or not ID.fullmatch(note_id):
        raise ValueError("Invalid note identifier.")
    path = NOTES / (note_id + ".json")
    if path.is_symlink():
        raise ValueError("A notebook entry cannot be a symbolic link.")
    if not path.exists():
        raise FileNotFoundError("That note is no longer present.")
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError("Notebook entry exceeds its supported size.")
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_fields(value)
    if value.get("schema") != "fieldnotes.note/v1" or value.get("id") != note_id or type(value.get("revision")) is not int or value["revision"] < 1:
        raise ValueError("Notebook entry has an unsupported format.")
    return value


def all_notes():
    files = sorted(NOTES.glob("*.json"))
    if len(files) > MAX_NOTES:
        raise ValueError("Notebook exceeds the supported 2,000 notes.")
    return [read_note(path.stem) for path in files]


def save_note(value):
    fields = validate_fields(value)
    note_id = value.get("id")
    revision = value.get("revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("A note needs its observed revision.")
    with LOCK:
        if note_id is None:
            if revision != 0:
                raise ValueError("A new note starts at revision zero.")
            if len(list(NOTES.glob("*.json"))) >= MAX_NOTES:
                raise ValueError("This notebook supports 2,000 notes; export before starting another notebook.")
            note_id = uuid.uuid4().hex
            previous = {"created_at": now(), "revision": 0}
        else:
            previous = read_note(note_id)
            if previous["revision"] != revision:
                return None
        record = {"schema": "fieldnotes.note/v1", "id": note_id, **fields, "created_at": previous["created_at"],
                  "updated_at": now(), "revision": previous["revision"] + 1}
        path = NOTES / (note_id + ".json")
        size = len(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")) + 1
        total = sum(p.stat().st_size for p in NOTES.glob("*.json") if p != path)
        if total + size > MAX_TOTAL_BYTES:
            raise ValueError("This notebook supports 32 MiB of saved notes; export before starting another notebook.")
        atomic_json(path, record)
        return record


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        # Keep private note titles, bodies and search terms out of service logs.
        pass

    def send(self, status, content, mime="application/json; charset=utf-8", filename=None):
        raw = content if isinstance(content, bytes) else json.dumps(content, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="' + filename + '"')
        self.end_headers()
        self.wfile.write(raw)

    def safe_request(self, private=False):
        if self.headers.get("Host") != f"127.0.0.1:{PORT}":
            self.send(403, {"error": "Use the numeric-loopback Fieldnotes address."})
            return False
        if self.headers.get("Origin") not in (None, ORIGIN) or self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            self.send(403, {"error": "Fieldnotes accepts same-origin requests only."})
            return False
        if private and not hmac.compare_digest(self.headers.get("Authorization", "").encode("utf-8"), ("Bearer " + TOKEN).encode("ascii")):
            self.send(403, {"error": "Open the current private link printed by the Fieldnotes launcher."})
            return False
        return True

    def do_GET(self):
        try:
            parts = urlsplit(self.path)
            if not self.safe_request(private=parts.path.startswith("/api/")):
                return
            if parts.path == "/health":
                self.send(200, {"ok": True})
            elif parts.path in ("/", "/app.js", "/style.css"):
                name, mime = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                              "/style.css": ("style.css", "text/css; charset=utf-8")}[parts.path]
                self.send(200, (SOURCE / name).read_bytes(), mime)
            elif parts.path == "/api/notebook":
                with LOCK:
                    notes = all_notes()
                notes.sort(key=lambda note: (note.get("pinned", False) if PINNING else False, note["updated_at"]), reverse=True)
                self.send(200, {"application": "fieldnotes", "version": VERSION, "pinning": PINNING, "notes": notes})
            elif parts.path == "/api/export":
                with LOCK:
                    notes = all_notes()
                memory = io.BytesIO()
                with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("README.txt", "Fieldnotes portable export\n\nnotes/ contains each note as UTF-8 JSON, including its title, body, tags, timestamps, revision and archive/pin flags. text/ contains plain-text reading copies. The complete notebook needs no Fieldnotes account or SCHISM controller to read. Private browser tokens and operator keys are excluded.\n")
                    for note in notes:
                        archive.writestr("notes/" + note["id"] + ".json", json.dumps(note, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
                        archive.writestr("text/" + note["id"] + ".txt", note["title"] + "\n\n" + note["body"])
                self.send(200, memory.getvalue(), "application/zip", "fieldnotes-export.zip")
            elif parts.path == "/api/text":
                values = parse_qs(parts.query)
                with LOCK:
                    note = read_note(values.get("id", [None])[0])
                raw = (note["title"] + "\n\n" + note["body"]).encode("utf-8")
                self.send(200, raw, "text/plain; charset=utf-8", "fieldnote-" + note["id"] + ".txt")
            else:
                self.send(404, {"error": "Page not found."})
        except FileNotFoundError as exc:
            self.send(404, {"error": str(exc)})
        except (ValueError, UnicodeError) as exc:
            self.send(400, {"error": str(exc)})
        except OSError:
            self.send(500, {"error": "The notebook could not read its local files. Check available storage and account permissions."})

    def do_POST(self):
        if not self.safe_request(private=True):
            self.close_connection = True
            return
        if self.path != "/api/notes":
            self.send(404, {"error": "Page not found."})
            self.close_connection = True
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if self.headers.get("Transfer-Encoding") or length < 1 or length > MAX_RECORD_BYTES or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                self.close_connection = True
                self.send(400, {"error": "Send a bounded JSON note with Content-Length."})
                return
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("Send a note object.")
            note = save_note(value)
            if note is None:
                self.send(409, {"error": "Another tab saved a newer revision. Copy your draft before reopening the note."})
            else:
                self.send(200, {"note": note})
        except FileNotFoundError as exc:
            self.send(404, {"error": str(exc)})
        except (ValueError, UnicodeError) as exc:
            self.send(400, {"error": str(exc)})
        except OSError:
            self.send(500, {"error": "Fieldnotes could not confirm the save. Keep your draft and reopen the note to check its saved revision; check storage and account permissions."})

    def do_OPTIONS(self):
        self.send(403, {"error": "Cross-origin access is disabled."})


def main():
    if DATA.is_symlink() or NOTES.is_symlink() or WORK.is_symlink():
        raise SystemExit("Fieldnotes requires ordinary local data and work directories.")
    NOTES.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOCK:
        all_notes()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    atomic_json(WORK / "fieldnotes-open.json", {"application": "fieldnotes", "port": PORT, "token": TOKEN, "version": VERSION})
    print(f"Fieldnotes {VERSION}: {ORIGIN}/#token={TOKEN}", flush=True)
    print("Your notes remain in the recipient-owned application data directory. This private link changes after every start.", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
