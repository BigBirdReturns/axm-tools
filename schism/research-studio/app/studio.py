#!/usr/bin/env python3
"""Local retained-research catalog, source verification and read-only review.

This application records source identities and reviews existing experiments.
It does not execute imported code, train controllers, or issue device commands.
Canonical episode records remain experience@1 at their existing project owner.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCHEMA = "research-index@1"
CODE_ROOT = Path(__file__).resolve().parent
MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,150}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def parse_json(payload):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8-sig")
    return json.loads(payload,
                      object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def load_json(path):
    payload, _, _ = read_snapshot(path, retain=True, limit=MAX_JSON_BYTES)
    return parse_json(payload)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def read_snapshot(path, *, retain=False, limit=MAX_SOURCE_BYTES):
    """Hash and optionally retain the same bounded byte stream.

    Extraction must consume this stream rather than reopen a path that may
    already name a successor version. Metadata checks reject observed mutation
    during the read; the digest always describes the actual bytes read.
    """
    h = hashlib.sha256()
    size, parts = 0, []
    with Path(path).open("rb") as handle:
        before = os.fstat(handle.fileno())
        if before.st_size > limit:
            raise ValueError(f"source exceeds bounded verifier limit: {path}")
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(part)
            if size > limit:
                raise ValueError(f"source exceeds bounded verifier limit: {path}")
            h.update(part)
            if retain:
                parts.append(part)
        after = os.fstat(handle.fileno())
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size,
                             stat.st_mtime_ns, stat.st_ctime_ns)
    if identity(before) != identity(after) or size != after.st_size:
        raise ValueError(f"source changed during read: {path}")
    return b"".join(parts) if retain else None, h.hexdigest(), size


def sha256_file(path):
    _, digest, size = read_snapshot(path)
    return digest, size


def source_path(path, roots):
    p = Path(path)
    if not p.is_absolute():
        raise ValueError("native source path must be absolute")
    resolved = p.resolve(strict=True)
    allowed = [Path(root).resolve(strict=True) for root in roots]
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise ValueError(f"source outside declared read roots: {path}")
    if not resolved.is_file():
        raise ValueError(f"source is not a file: {path}")
    return resolved


def pointer(obj, address):
    if not isinstance(address, str):
        raise ValueError("JSON pointer must be a string")
    if address == "":
        return obj
    if not address.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    for raw in address[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", raw):
            raise ValueError("invalid JSON pointer escape")
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(obj, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", key):
                raise ValueError("invalid JSON pointer array index")
            obj = obj[int(key)]
        else:
            obj = obj[key]
    return obj


def validate_catalog(catalog):
    if not isinstance(catalog, dict):
        raise ValueError("catalog must be an object")
    if catalog.get("schema") != SCHEMA:
        raise ValueError("unsupported catalog schema")
    sections = ("sources", "components", "campaigns", "lineage", "gaps", "vendors")
    for section in sections:
        if not isinstance(catalog.get(section), list):
            raise ValueError(f"{section} must be a list")
    if "findings" in catalog and not isinstance(catalog["findings"], list):
        raise ValueError("findings must be a list")
    sources = {}
    for source in catalog["sources"]:
        if not isinstance(source, dict):
            raise ValueError("source must be an object")
        key = source["id"]
        if not isinstance(key, str) or not ID.fullmatch(key) or key in sources:
            raise ValueError(f"invalid or duplicate source id: {key}")
        sources[key] = source
        if source.get("status") == "verified":
            if not isinstance(source.get("sha256"), str) or not SHA256.fullmatch(source["sha256"]):
                raise ValueError(f"verified source requires SHA256: {key}")
            if not isinstance(source.get("bytes"), int) or isinstance(source["bytes"], bool) or source["bytes"] < 0:
                raise ValueError(f"verified source requires byte count: {key}")
            if not isinstance(source.get("path"), str) or not source["path"]:
                raise ValueError(f"verified source requires source path: {key}")
        if "extracted" in source:
            bindings = source.get("extract_bindings")
            if not isinstance(bindings, dict) or not isinstance(source["extracted"], dict) or set(bindings) != set(source["extracted"]):
                raise ValueError(f"extracted values require exact pointer bindings: {key}")
            if any(not isinstance(address, str) for address in bindings.values()):
                raise ValueError(f"invalid extraction pointer: {key}")
    for section in ("components", "campaigns", "gaps", "vendors", "lineage", "findings"):
        ids = set()
        for row in catalog.get(section, []):
            if not isinstance(row, dict):
                raise ValueError(f"{section} row must be an object")
            key = row.get("id")
            if key is not None:
                if not isinstance(key, str) or not ID.fullmatch(key) or key in ids:
                    raise ValueError(f"invalid/duplicate {section} id: {key}")
                ids.add(key)
            refs = []
            for field in ("evidence_refs", "source_refs"):
                values = row.get(field, [])
                if not isinstance(values, list):
                    raise ValueError(f"{field} must be a list")
                refs.extend(values)
            if row.get("source_ref"):
                refs.append(row["source_ref"])
            if row.get("replay") is not None:
                replay = row["replay"]
                context = row.get("replay_context", {})
                if not isinstance(replay, dict) or not isinstance(context, dict):
                    raise ValueError("recorded replay and context must be objects")
                for metadata in (replay, context):
                    replay_refs = metadata.get("source_refs", [])
                    if not isinstance(replay_refs, list):
                        raise ValueError("replay source_refs must be a list")
                    refs.extend(replay_refs)
                if isinstance(replay.get("frames"), list):
                    for frame in replay["frames"]:
                        if not isinstance(frame, dict) or not isinstance(frame.get("points"), list):
                            raise ValueError("recorded replay frame requires a points list")
                        for point in frame["points"]:
                            if not isinstance(point, dict) or any(not isinstance(point.get(axis), (int, float)) or isinstance(point[axis], bool) for axis in ("x", "y")):
                                raise ValueError("recorded replay points require numeric X and Y")
                else:
                    frame_count, fps, balls = replay.get("frames"), replay.get("fps"), replay.get("balls")
                    if not isinstance(frame_count, int) or isinstance(frame_count, bool) or frame_count <= 0:
                        raise ValueError("native recorded replay requires a positive frame count")
                    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0 or not isinstance(balls, list):
                        raise ValueError("native recorded replay requires positive FPS and ball records")
                    for ball in balls:
                        if not isinstance(ball, dict) or not isinstance(ball.get("traj"), list) or len(ball["traj"]) != frame_count:
                            raise ValueError("native recorded trajectory length differs from frame count")
                        for position in ball["traj"]:
                            if not isinstance(position, list) or len(position) != 3 or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in position):
                                raise ValueError("native recorded positions require numeric X, Y and Z")
            derived = row.get("derived_from", {})
            if not isinstance(derived, dict):
                raise ValueError("derived_from must be an object")
            for field, binding in derived.items():
                if not isinstance(binding, dict) or not binding.get("source_ref"):
                    raise ValueError("derived field lacks source identity")
                refs.append(binding["source_ref"])
                source = sources.get(binding["source_ref"])
                if source is not None:
                    if source.get("status") == "verified":
                        extracted = source.get("extracted", {})
                        if binding.get("field") not in extracted or row.get(field) != extracted[binding["field"]]:
                            raise ValueError("derived field differs from its source projection")
                    elif row.get(field) is not None:
                        raise ValueError("unverified source cannot supply a derived value")
            if any(not isinstance(ref, str) or ref not in sources for ref in refs):
                raise ValueError(f"unresolved source reference in {section}: {key}")
    for row in catalog["campaigns"]:
        if row.get("record_class") not in {
            "recorded_report", "recorded_trace", "rescoring", "source_only",
            "scene_reuse", "application_lifecycle", "episode_ledger"
        }:
            raise ValueError(f"campaign requires exact evidence class: {row.get('id')}")
        for key in ("attempted", "completed", "failed"):
            value = row.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ValueError(f"invalid campaign {key}")
        if row.get("attempted") is not None:
            for key in ("completed", "failed"):
                if row.get(key) is not None and row[key] > row["attempted"]:
                    raise ValueError(f"{key} exceeds attempted")
    for row in catalog["vendors"]:
        state = str(row.get("state", "")).strip().lower().replace("-", "_").replace(" ", "_")
        executed = state == "executed" or state.startswith("executed_") or state in {"local_execution", "vendor_executed"}
        if executed and not row.get("execution_source_ref"):
            raise ValueError("vendor execution needs a distinct execution record")
        if row.get("execution_source_ref") and row["execution_source_ref"] not in sources:
            raise ValueError("vendor execution source absent")
        if executed:
            source = sources[row["execution_source_ref"]]
            if source.get("status") != "verified" or source.get("kind") != "execution_record":
                raise ValueError("vendor execution requires a verified execution_record source")
            identity = source.get("extracted", {}).get("execution_identity")
            if not isinstance(identity, dict):
                raise ValueError("vendor execution requires source-derived execution identity")
            for field in ("vendor", "implementation", "version", "artifact_sha256", "invocation_id"):
                if not isinstance(identity.get(field), str) or not identity[field].strip():
                    raise ValueError(f"vendor execution identity missing {field}")
            if identity["vendor"] != row.get("name") or not SHA256.fullmatch(identity["artifact_sha256"]):
                raise ValueError("vendor execution identity does not match the claimed implementation")
    collection = catalog.get("collection", {})
    if not isinstance(collection, dict) or collection.get("aggregate_episode_count") is not None:
        raise ValueError("this catalog cannot aggregate potentially overlapping campaign episodes")
    gap_ids = {g["id"] for g in catalog["gaps"]}
    graph = {g["id"]: g.get("depends_on", []) for g in catalog["gaps"]}
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError("research dependency cycle")
        if key in visited:
            return
        visiting.add(key)
        for dependency in graph[key]:
            if dependency not in gap_ids:
                raise ValueError(f"unknown research dependency: {dependency}")
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
    for key in graph:
        visit(key)
    json.dumps(catalog, allow_nan=False)
    return sources


def collect(spec_path, output):
    spec = load_json(spec_path)
    roots = spec["read_roots"]
    catalog = copy.deepcopy(spec["catalog"])
    catalog["schema"] = SCHEMA
    catalog["generated_at"] = datetime.now(timezone.utc).isoformat()
    catalog["sources"] = []
    findings = []
    for declaration in spec["sources"]:
        entry = {k: v for k, v in declaration.items()
                 if k not in {"expected_sha256", "extract", "optional", "extracted",
                              "extract_bindings", "sha256", "bytes", "status",
                              "observed_sha256", "observed_bytes", "observed_at"}}
        entry["observed_at"] = catalog["generated_at"]
        try:
            p = source_path(declaration["path"], roots)
            extract = bool(declaration.get("extract"))
            payload, digest, size = read_snapshot(p, retain=extract,
                                                  limit=MAX_JSON_BYTES if extract else MAX_SOURCE_BYTES)
            expected = declaration.get("expected_sha256")
            if expected is not None:
                if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                    raise ValueError("source pin must be a SHA256 digest")
                entry["expected_sha256"] = expected
                if expected != digest:
                    entry.update(observed_sha256=digest, observed_bytes=size)
                    raise ValueError("pinned source hash changed")
            expected_size = declaration.get("expected_bytes")
            if expected_size is not None:
                if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
                    raise ValueError("source size pin must be a nonnegative integer")
                if expected_size != size:
                    entry.update(observed_sha256=digest, observed_bytes=size)
                    raise ValueError("pinned source byte count changed")
            entry.update(status="verified", sha256=digest, bytes=size)
            if declaration.get("extract"):
                doc = parse_json(payload)
                entry["extract_bindings"] = copy.deepcopy(declaration["extract"])
                entry["extracted"] = {name: pointer(doc, addr)
                                      for name, addr in declaration["extract"].items()}
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            entry.update(status="unverified", error=str(exc))
            if not declaration.get("optional", False):
                findings.append({"source_id": declaration["id"], "error": str(exc)})
        catalog["sources"].append(entry)
    by_id = {row["id"]: row for row in catalog["sources"]}
    for section in ("components", "campaigns", "lineage", "gaps", "vendors", "findings"):
        for row in catalog.get(section, []):
            bindings = row.pop("derive", {})
            if bindings:
                row["derived_from"] = copy.deepcopy(bindings)
            for field, binding in bindings.items():
                source = by_id[binding["source_ref"]]
                if source["status"] != "verified":
                    row[field] = None
                    row["status"] = "source-unverified"
                else:
                    row[field] = copy.deepcopy(source["extracted"][binding["field"]])
            if row.get("source_ref") and by_id[row["source_ref"]]["status"] != "verified":
                row["status"] = "source-unverified"
    catalog["collection"] = {
        "verified": sum(s["status"] == "verified" for s in catalog["sources"]),
        "unverified": sum(s["status"] != "verified" for s in catalog["sources"]),
        "findings": findings,
        "source_verification_scope": "This collection checks retained file identity and declared extraction. Execution, including a fresh reproduction, is attributed to its own campaign record.",
        "measurement_scope": "Collection operation only; campaign execution counts remain separately scoped.",
        "new_simulations": 0,
        "new_training_steps": 0,
        "aggregate_episode_count": None,
        "aggregate_reason": "Campaigns may overlap or supersede one another; source episode IDs are required before aggregation."
    }
    validate_catalog(catalog)
    write_json(output, catalog)
    return catalog["collection"]


def verify(catalog_path, roots):
    payload, catalog_digest, _ = read_snapshot(catalog_path, retain=True, limit=MAX_JSON_BYTES)
    catalog = parse_json(payload)
    validate_catalog(catalog)
    results = []
    for entry in catalog["sources"]:
        if entry.get("status") != "verified":
            results.append({"id": entry["id"], "status": "unverified"})
            continue
        try:
            extract = "extracted" in entry
            payload, actual, size = read_snapshot(source_path(entry["path"], roots), retain=extract,
                                                  limit=MAX_JSON_BYTES if extract else MAX_SOURCE_BYTES)
            ok = actual == entry["sha256"] and size == entry["bytes"]
            status = "match" if ok else "changed"
            if ok and extract:
                document = parse_json(payload)
                projected = {name: pointer(document, address)
                             for name, address in entry["extract_bindings"].items()}
                if projected != entry["extracted"]:
                    status = "derived-mismatch"
            results.append({"id": entry["id"], "status": status,
                            "observed_sha256": actual, "observed_bytes": size})
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            results.append({"id": entry["id"], "status": "unavailable", "error": str(exc)})
    return {"schema": "research-source-verification@1", "verified_at": datetime.now(timezone.utc).isoformat(),
            "catalog_sha256": catalog_digest,
            "passed": all(r["status"] == "match" for r in results), "results": results,
            "scope": "Source identity check only. No scientific rerun or capability promotion."}


def make_server(catalog_path, port=0):
    """Construct the loopback-only, read-only server without starting its loop."""
    catalog_path = Path(catalog_path).resolve()
    if catalog_path.exists():
        validate_catalog(load_json(catalog_path))
    web = CODE_ROOT / "web"
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond(send_body=True)
        def do_HEAD(self):
            self.respond(send_body=False)
        def method_not_allowed(self):
            self.send_response(405)
            self.send_header("Allow", "GET, HEAD")
            self.send_header("Content-Length", "0")
            self.end_headers()
        do_POST = do_PUT = do_PATCH = do_DELETE = method_not_allowed
        def respond(self, *, send_body):
            host = self.headers.get("Host", "").split(":")[0].lower()
            if host not in {"127.0.0.1", "localhost"}:
                self.send_error(403)
                return
            route = unquote(urlsplit(self.path).path)
            if route == "/health":
                payload = json.dumps({"ok": True, "mode": "retained-research",
                                      "catalog_present": catalog_path.is_file(),
                                      "scope": "HTTP reader readiness; catalog validity is checked on read"}).encode()
                mime = "application/json"
            elif route == "/api/catalog":
                try:
                    payload, _, _ = read_snapshot(catalog_path, retain=True, limit=MAX_JSON_BYTES)
                    validate_catalog(parse_json(payload))
                except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                    self.send_error(503, "Current catalog failed validation")
                    return
                mime = "application/json"
            elif route in {"/", "/index.html", "/app.js", "/style.css"}:
                filename = "index.html" if route == "/" else route[1:]
                p = (web / filename).resolve()
                if not p.is_relative_to(web.resolve()) or not p.is_file():
                    self.send_error(404)
                    return
                payload, mime = p.read_bytes(), mimetypes.guess_type(filename)[0] or "application/octet-stream"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            if send_body:
                self.wfile.write(payload)
        def log_message(self, fmt, *args):
            print(fmt % args, flush=True)
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(catalog_path, port):
    with make_server(catalog_path, port) as server:
        print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}/", "catalog": str(catalog_path)}), flush=True)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="op", required=True)
    c = commands.add_parser("collect")
    c.add_argument("--spec", required=True)
    c.add_argument("--output", required=True)
    v = commands.add_parser("verify")
    v.add_argument("--catalog", required=True)
    v.add_argument("--root", action="append", required=True)
    v.add_argument("--output")
    s = commands.add_parser("serve")
    s.add_argument("--catalog", default=str(Path(os.environ.get("SCHISM_DATA", ".")) / "catalog.json"))
    s.add_argument("--port", type=int, default=8374)
    args = parser.parse_args()
    try:
        if args.op == "collect":
            result = collect(args.spec, args.output)
            print(json.dumps(result, indent=2))
            return 0 if not result["findings"] else 2
        if args.op == "verify":
            result = verify(args.catalog, args.root)
            if args.output:
                write_json(args.output, result)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 2
        serve(args.catalog, args.port)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
