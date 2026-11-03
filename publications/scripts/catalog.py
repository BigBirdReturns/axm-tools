#!/usr/bin/env python3
"""Import the explicit public publication catalog and render an offline index.

This consumer has no account, API key, runtime service or private-project import.
The source publication owner produces publication-catalog/0.1 after release.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
ASSET = re.compile(r"assets/([a-f0-9]{64})\.(png|jpg|jpeg|webp|gif)\Z")


class CatalogError(ValueError):
    pass


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def keys(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise CatalogError("unexpected_public_field")


def text(value, *, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()) or len(value) > 100000:
        raise CatalogError("invalid_public_text")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise CatalogError("control_character")
    decoded = html.unescape(value).replace("\\", "/")
    for _ in range(3):
        decoded = unquote(decoded)
    if re.search(r"(?<![A-Za-z0-9])[A-Za-z]:/", decoded) or re.search(r"(?:^|[\s\"'<(])/(?:home|mnt|Users|workspace)/", decoded):
        raise CatalogError("private_execution_path")
    return value


def url(value, *, https=False):
    text(value, nonempty=True)
    parsed = urlsplit(value)
    if parsed.scheme not in ({"https"} if https else {"http", "https"}) or not parsed.hostname or parsed.username or parsed.password:
        raise CatalogError("invalid_public_url")
    if any(char.isspace() for char in value) or "\\" in value:
        raise CatalogError("invalid_public_url")
    return value


def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise CatalogError("invalid_sha256")
    return value


def identity(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise CatalogError("invalid_identity")
    return value


def release(value, entry):
    keys(value, {"schema", "publication_id", "revision", "canonical_url", "readback", "evidence_kind"})
    if value.get("schema") != "publication-release/0.1":
        raise CatalogError("release_evidence_required")
    if value.get("evidence_kind", "PIPELINE_PUBLICATION") not in {"PIPELINE_PUBLICATION", "OBSERVED_EXISTING_PUBLICATION"}:
        raise CatalogError("unknown_release_evidence_kind")
    for key, match in (("publication_id", "id"), ("revision", "revision"), ("canonical_url", "canonical_url")):
        if value.get(key) != entry[match]:
            raise CatalogError("release_identity_mismatch")
    observed = value.get("readback")
    keys(observed, {"url", "http_status", "observed_at", "html_sha256"})
    if observed.get("url") != entry["canonical_url"] or type(observed.get("http_status")) is not int or observed["http_status"] != 200:
        raise CatalogError("canonical_readback_required")
    try:
        stamp = datetime.fromisoformat(observed["observed_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timezone missing")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise CatalogError("timestamp_requires_timezone") from exc
    sha(observed.get("html_sha256"))


def entry(value):
    keys(value, {"schema", "id", "revision", "state", "title", "excerpt", "canonical_url", "tags", "sources", "links", "feature_image", "release"})
    if value.get("schema") != "publication-catalog-entry/0.1" or value.get("state") != "published":
        raise CatalogError("published_entry_required")
    identity(value.get("id"))
    sha(value.get("revision"))
    text(value.get("title"), nonempty=True)
    text(value.get("excerpt", ""))
    url(value.get("canonical_url"), https=True)
    tags = value.get("tags", [])
    if not isinstance(tags, list) or len(tags) > 100:
        raise CatalogError("invalid_tags")
    for tag in tags:
        text(tag, nonempty=True)
    if len(set(tags)) != len(tags):
        raise CatalogError("duplicate_tags")
    for kind in ("links", "sources"):
        rows = value.get(kind, [])
        if not isinstance(rows, list) or len(rows) > 1000:
            raise CatalogError("invalid_" + kind)
        for row in rows:
            keys(row, {"title", "url", "relation", "release"} if kind == "links" else {"id", "title", "url", "sha256"})
            text(row.get("title"))
            url(row.get("url"))
            if kind == "links":
                if row.get("relation") not in {"tool", "evidence", "related"}:
                    raise CatalogError("invalid_link_relation")
                if "release" in row:
                    text(row["release"])
            else:
                identity(row.get("id"))
                sha(row.get("sha256"))
    if "feature_image" in value:
        feature = value["feature_image"]
        keys(feature, {"path", "alt"})
        if not isinstance(feature.get("path"), str) or not ASSET.fullmatch(feature["path"]):
            raise CatalogError("hash_named_raster_required")
        text(feature.get("alt", ""))
    release(value.get("release"), value)
    return value


def checked_file(path, *, max_bytes=64 * 1024 * 1024):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file() or path.stat().st_size > max_bytes:
        raise CatalogError("regular_bounded_file_required")
    return path.read_bytes()


def load_catalog(path):
    path = Path(path).absolute()
    raw = checked_file(path, max_bytes=8 * 1024 * 1024)
    value = json.loads(raw)
    keys(value, {"schema", "entries"})
    if value.get("schema") != "publication-catalog/0.1" or not isinstance(value.get("entries"), list) or len(value["entries"]) > 1000:
        raise CatalogError("invalid_public_catalog")
    entries = [entry(row) for row in value["entries"]]
    for field in ("id", "canonical_url"):
        if len({row[field] for row in entries}) != len(entries):
            raise CatalogError("duplicate_" + field)
    files = {"catalog.json": raw}
    for row in entries:
        if "feature_image" in row:
            name = row["feature_image"]["path"]
            body = checked_file(path.parent / name)
            if digest(body) != ASSET.fullmatch(name).group(1):
                raise CatalogError("asset_digest_mismatch")
            files[name] = body
    return {"schema": value["schema"], "entries": sorted(entries, key=lambda row: row["id"])}, files


def exact_files(directory):
    directory = Path(directory)
    if not directory.exists():
        return {}
    _, files = load_catalog(directory / "catalog.json")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(files):
        raise CatalogError("unexpected_file_outside_catalog_allowlist")
    return {name: digest(body) for name, body in files.items()}


def import_catalog(source, destination, *, expected_current_sha):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if any(part.is_symlink() for target in (source, destination) for part in (target, *target.parents)):
        raise CatalogError("symlink_catalog_path")
    if source == destination or source in destination.parents or destination in source.parents:
        raise CatalogError("source_and_destination_must_be_disjoint")
    incoming, files = load_catalog(source / "catalog.json")
    exact_files(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.parent / ("." + destination.name + "-import.lock")
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CatalogError("catalog_writer_active_or_uncertain") from exc
    try:
        os.close(handle)
        previous = exact_files(destination)
        current = previous.get("catalog.json", "absent")
        if current != expected_current_sha:
            raise CatalogError("catalog_changed_since_review")
        incoming_hashes = {name: digest(body) for name, body in files.items()}
        if previous == incoming_hashes:
            return {"state": "unchanged", "entries": len(incoming["entries"]), "catalog_sha256": current}
        temporary = Path(tempfile.mkdtemp(prefix=".publication-import-", dir=destination.parent))
        stage, backup = temporary / "next", temporary / "previous"
        cleanup = True
        try:
            stage.mkdir()
            for name, body in files.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            if exact_files(destination) != previous:
                raise CatalogError("catalog_changed_during_import")
            if destination.exists():
                destination.rename(backup)
            try:
                stage.rename(destination)
            except OSError:
                if backup.exists():
                    try:
                        backup.rename(destination)
                    except OSError:
                        cleanup = False
                        raise CatalogError("rollback_incomplete_previous_catalog_retained_at_" + str(backup))
                raise
        finally:
            if cleanup:
                import shutil
                shutil.rmtree(temporary)
        return {"state": "imported", "entries": len(incoming["entries"]), "catalog_sha256": incoming_hashes["catalog.json"]}
    finally:
        lock.unlink()


def render(catalog):
    esc = html.escape
    cards = []
    for row in sorted(catalog["entries"], key=lambda item: item["title"].casefold()):
        picture = row.get("feature_image")
        image = '<img src="data/' + esc(picture["path"], quote=True) + '" alt="' + esc(picture.get("alt", ""), quote=True) + '" loading="lazy">' if picture else ""
        links = "".join('<li><a href="' + esc(link["url"], quote=True) + '">' + esc(link["title"]) + '</a></li>' for link in row.get("links", []))
        references = '<ul class="links">' + links + '</ul>' if links else ""
        tags = '<p class="tags">' + esc(" · ".join(row.get("tags", []))) + '</p>' if row.get("tags") else ""
        excerpt = row.get("excerpt", "")
        if len(excerpt) > 280:
            excerpt = excerpt[:280].rsplit(" ", 1)[0].rstrip(" .,;:") + "…"
        imported = '<p class="tags">Archive import</p>' if row.get("release", {}).get("evidence_kind") == "OBSERVED_EXISTING_PUBLICATION" else ""
        cards.append('<article>' + image + '<div class="copy">' + imported + tags + '<h2><a href="' + esc(row["canonical_url"], quote=True) + '">' + esc(row["title"]) + '</a></h2><p>' + esc(excerpt) + '</p>' + references + '</div></article>')
    content = '\n'.join(cards) or '<div class="empty"><h2>Explore the essay archive</h2><p>Read <a href="https://fakesoap.com/">FakeSoap</a> for the current essays. Linked tools will appear here as new pieces are added.</p></div>'
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FakeSoap publications and tools · AXM</title><meta name="description" content="FakeSoap essays and the tools, demonstrations and evidence they connect.">\n'
        '<style>:root{color-scheme:light dark;--bg:#f6f4ef;--ink:#172332;--muted:#54616f;--card:#fff;--line:#d7d9d9;--link:#005d86}@media(prefers-color-scheme:dark){:root{--bg:#101923;--ink:#eff3f5;--muted:#a8b5c3;--card:#182432;--line:#354454;--link:#79c9ed}}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:clamp(24px,5vw,64px)}nav{display:flex;flex-wrap:wrap;gap:24px;font-size:15px}a{color:var(--link);text-underline-offset:.18em}h1{font-size:clamp(32px,5vw,52px);line-height:1.12;letter-spacing:-.035em;margin:50px 0 20px}header p{max-width:730px;color:var(--muted);margin-bottom:40px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:24px}article,.empty{min-width:0;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}article img{display:block;width:100%;aspect-ratio:1.6;object-fit:cover}.copy,.empty{padding:26px}h2{font-size:24px;line-height:1.25;margin:0 0 16px}p,li,a{overflow-wrap:anywhere}.tags{font-size:13px;color:var(--muted);margin:0 0 12px}.links{padding-left:22px}footer{border-top:1px solid var(--line);margin-top:44px;padding-top:24px;font-size:14px;color:var(--muted)}</style></head><body><main><nav aria-label="Site"><a href="../">AXM toolbox</a><a href="https://axm.tools/">AXM</a><a href="https://fakesoap.com/">FakeSoap</a></nav><header><h1>Ideas, evidence and working tools</h1><p>FakeSoap carries the essays. This index connects published pieces to their demonstrations, source material and tools.</p></header><section aria-label="Publications">' + content + '</section><footer>Articles open at their canonical FakeSoap address. Tools retain their own independent pages. <a href="data/catalog.json">Public catalog</a></footer></main></body></html>\n').encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        part = sub.add_parser(name)
        part.add_argument("--catalog", type=Path, default=ROOT / "data/catalog.json")
        part.add_argument("--output", type=Path, default=ROOT / "index.html")
    part = sub.add_parser("import")
    part.add_argument("--source", required=True, type=Path)
    part.add_argument("--destination", type=Path, default=ROOT / "data")
    part.add_argument("--expected-current-sha", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            result = import_catalog(args.source, args.destination, expected_current_sha=args.expected_current_sha)
        else:
            catalog, _ = load_catalog(args.catalog)
            exact_files(args.catalog.parent)
            body = render(catalog)
            if args.command == "check":
                if not args.output.exists() or args.output.read_bytes() != body:
                    raise CatalogError("rendered_index_drift")
            else:
                temporary = args.output.with_name("." + args.output.name + ".tmp")
                temporary.write_bytes(body)
                os.replace(temporary, args.output)
            result = {"state": "checked" if args.command == "check" else "built", "entries": len(catalog["entries"]), "index_sha256": digest(body)}
        print(json.dumps(result, indent=2))
        return 0
    except (CatalogError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error) if isinstance(error, CatalogError) else type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
