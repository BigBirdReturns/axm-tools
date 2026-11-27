"""Recipient-owned state, transactional generations and signed event history."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import sqlite3
import threading

from . import __version__, identity
from .common import Refusal, atomic_json, canonical, digest, file_lock, now, private_root, read_json


class Store:
    def __init__(self, state, name="Local operator"):
        self.root = private_root(state)
        marker = self.root / "schism-state.json"
        if not marker.exists():
            if any(self.root.iterdir()):
                raise Refusal("State directory must be empty or an existing SCHISM state")
            atomic_json(marker, {"schema": "schism.state/v1", "created_at": now()})
        elif read_json(marker).get("schema") != "schism.state/v1":
            raise Refusal("Unsupported state format")
        for name_ in ("locks", "releases", "packages", "incoming", "data", "work", "logs", "config", "exports"):
            private_root(self.root / name_)
        self.identity = identity.ensure_identity(self.root, name)
        self.database = self.root / "state.sqlite"
        if self.database.is_symlink():
            raise Refusal("State database cannot be a symlink")
        with self.db() as con:
            con.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS trust(key_id TEXT PRIMARY KEY, publisher TEXT NOT NULL, apps TEXT NOT NULL, label TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS releases(release_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, path TEXT NOT NULL, imported_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS apps(id TEXT PRIMARY KEY, release_id TEXT NOT NULL, previous_release_id TEXT, generation INTEGER NOT NULL, status TEXT NOT NULL, run_id TEXT, data_schema TEXT NOT NULL, last_error TEXT);
            CREATE TABLE IF NOT EXISTS data_contracts(app_id TEXT PRIMARY KEY, data_schema TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL, request TEXT NOT NULL, operation TEXT NOT NULL, app_id TEXT, status TEXT NOT NULL, worker_pid INTEGER, worker_created REAL, created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT, result TEXT, error TEXT, cancel INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, app_id TEXT NOT NULL, release_id TEXT NOT NULL, kind TEXT NOT NULL, job_id TEXT, status TEXT NOT NULL, pid INTEGER, process_created REAL, runner_pid INTEGER, runner_created REAL, exit_code INTEGER, created_at TEXT NOT NULL, ended_at TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL, envelope TEXT NOT NULL, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS peers(name TEXT PRIMARY KEY, specification TEXT NOT NULL);
            """)
            con.execute("INSERT OR IGNORE INTO trust(key_id,publisher,apps,label) VALUES(?,?,?,?)",
                        (self.identity["key_id"], json.dumps(self.identity), '["*"]', "This operator"))
            con.execute("INSERT OR IGNORE INTO data_contracts SELECT id,data_schema FROM apps")
            run_columns = {row[1] for row in con.execute("PRAGMA table_info(runs)")}
            for column, declaration in (("launcher_pid", "INTEGER"), ("launcher_created", "REAL")):
                if column not in run_columns:
                    con.execute("ALTER TABLE runs ADD COLUMN " + column + " " + declaration)

    @contextlib.contextmanager
    def db(self):
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def lock(self, name, cancelled=lambda: False):
        return file_lock(self.root / "locks" / (digest(name.encode()) + ".lock"), cancelled)

    def event(self, kind, body, connection=None):
        def append(con):
            prior = con.execute("SELECT sequence,digest FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
            sequence = prior["sequence"] + 1 if prior else 1
            at = now()
            payload = {"sequence": sequence, "at": at, "kind": kind, "previous": prior["digest"] if prior else None, "body": body}
            envelope = identity.sign(self.root, payload, "schism.event/v1")
            con.execute("INSERT INTO events VALUES(?,?,?,?,?)", (sequence, at, kind, canonical(envelope).decode(), digest(envelope)))
            return payload
        if connection is not None:
            return append(connection)
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            return append(con)

    def one(self, query, parameters=()):
        with self.db() as con:
            row = con.execute(query, parameters).fetchone()
        return dict(row) if row else None

    def all(self, query, parameters=()):
        with self.db() as con:
            rows = con.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def release(self, release_id):
        row = self.one("SELECT * FROM releases WHERE release_id=?", (release_id,))
        if not row:
            raise Refusal("Release is not present on this recipient")
        return json.loads(row["metadata"])

    def trusted(self, metadata):
        key = metadata["publisher"]["key_id"]
        row = self.one("SELECT * FROM trust WHERE key_id=?", (key,))
        if not row or row["revoked"]:
            return False
        apps = json.loads(row["apps"])
        return metadata["application"]["id"] in apps or "*" in apps

    def check_trust(self, metadata):
        if not self.trusted(metadata):
            raise Refusal("Publisher is not authorized for this application on this recipient")

    def app(self, app_id, required=True):
        row = self.one("SELECT * FROM apps WHERE id=?", (app_id,))
        if not row and required:
            raise Refusal("Application is not deployed")
        return row

    def job(self, job_id):
        row = self.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            raise Refusal("Unknown job")
        row["result"] = json.loads(row["result"]) if row["result"] else None
        return row
