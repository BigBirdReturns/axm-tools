"""A small persistent application that survives code updates and rollback."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sqlite3

database = Path(os.environ["SCHISM_DATA"]) / "counter.sqlite"
with sqlite3.connect(database) as con:
    con.execute("CREATE TABLE IF NOT EXISTS counter(id INTEGER PRIMARY KEY,value INTEGER NOT NULL)")
    con.execute("INSERT OR IGNORE INTO counter VALUES(1,0)")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/", "/health"}:
            self.send_error(404)
            return
        with sqlite3.connect(database) as con:
            if self.path == "/":
                con.execute("UPDATE counter SET value=value+1 WHERE id=1")
            value = con.execute("SELECT value FROM counter WHERE id=1").fetchone()[0]
        payload = json.dumps({"healthy": True, "release": os.environ.get("RELEASE_LABEL", "Version 1"), "visits": value}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


print("Counter service listening on loopback port " + os.environ["PORT"], flush=True)
HTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
