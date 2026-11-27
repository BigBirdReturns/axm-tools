"""Public verification records and explicit, quiesced application backups."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from . import bundle, identity
from .common import Refusal, canonical, digest, now, private_root, validate_id

MAX_BACKUP = 512 * 1024 * 1024


def export_evidence(engine, destination):
    store = engine.store
    snapshot = engine.snapshot()
    releases = []
    for item in snapshot["releases"]:
        path = store.root / "releases" / item["release_id"]
        bundle.verify_directory(path)
        releases.append({"release": json.loads((path / "release.json").read_text(encoding="utf-8")),
                         "signature": json.loads((path / "signature.json").read_text(encoding="utf-8"))})
    events = [json.loads(row["envelope"]) for row in store.all("SELECT envelope FROM events ORDER BY sequence")]
    # Runtime override values, process output, keys and application data never enter this export.
    applications = [{key: app.get(key) for key in ("id", "name", "version", "kind", "release_id", "previous_release_id", "generation", "status", "data_schema")} for app in snapshot["applications"]]
    jobs = [{key: row.get(key) for key in ("id", "request_id", "fingerprint", "operation", "app_id", "status", "created_at", "started_at", "ended_at")} for row in store.all("SELECT * FROM jobs ORDER BY created_at")]
    payload = {"schema": "schism.evidence/v1", "created_at": now(), "operator": store.identity,
               "releases": releases, "events": events, "applications": applications, "jobs": jobs,
               "scope": "Recipient-observed execution and selected versions; application correctness and physical hardware identity require independent acceptance."}
    envelope = identity.sign(store.root, payload, "schism.evidence/v1")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("evidence.json", canonical(envelope) + b"\n")
        archive.writestr("VERIFY.txt", "Verify with: schism verify-evidence evidence.zip --key-id <independently-known-operator-fingerprint>\nAn embedded key establishes self-consistency. An independently supplied fingerprint establishes whose record you accept.\n")
    return {"path": str(destination), "sha256": digest(destination.read_bytes()), "events": len(events), "releases": len(releases), "key_id": store.identity["key_id"]}


def verify_evidence(path, expected_key_id=None):
    path = Path(path)
    if path.stat().st_size > MAX_BACKUP:
        raise Refusal("Evidence file exceeds the supported size")
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.filename != info.orig_filename or info.is_dir() or info.flag_bits & 1 or stat.S_IFMT(info.external_attr >> 16) not in {0, stat.S_IFREG}:
                raise Refusal("Unsupported evidence archive entry")
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != {"evidence.json", "VERIFY.txt"}:
            raise Refusal("Unexpected evidence archive inventory")
        info = archive.getinfo("evidence.json")
        if info.file_size > 128 * 1024 * 1024:
            raise Refusal("Evidence document exceeds the supported size")
        envelope = json.loads(archive.read(info).decode("utf-8"))
    payload = identity.verify(envelope, "schism.evidence/v1", expected_key_id)
    key_id = envelope["key_id"]
    if set(payload) != {"schema", "created_at", "operator", "releases", "events", "applications", "jobs", "scope"} or payload.get("schema") != "schism.evidence/v1":
        raise Refusal("Unsupported evidence schema or fields")
    identity.validate_descriptor(payload["operator"])
    if payload["operator"]["key_id"] != key_id or payload["operator"]["public_key"] != envelope["public_key"]:
        raise Refusal("Evidence operator differs from its signer")
    if not all(isinstance(payload[key], list) for key in ("releases", "events", "applications", "jobs")):
        raise Refusal("Evidence collections must be arrays")
    previous = None
    for sequence, event in enumerate(payload["events"], 1):
        body = identity.verify(event, "schism.event/v1", key_id)
        if body["sequence"] != sequence or body["previous"] != previous:
            raise Refusal("Evidence event chain has a gap, reorder or changed predecessor")
        previous = digest(event)
    for item in payload["releases"]:
        bundle._metadata(item["release"], item["signature"])
    return {"valid": True, "key_id": key_id, "identity_pinned": expected_key_id is not None,
            "events": len(payload["events"]), "releases": len(payload["releases"]), "applications": len(payload["applications"]),
            "terminal_event_sha256": previous, "created_at": payload["created_at"]}


def _safe_path(text):
    bundle._path(text)
    if not isinstance(text, str) or "\\" in text or "\0" in text or ":" in text:
        raise Refusal("Unsafe backup path")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in text.split("/")):
        raise Refusal("Unsafe backup path")
    return path


def backup_application(engine, app_id, destination):
    app_id = validate_id(app_id)
    destination = Path(os.path.abspath(Path(destination).expanduser()))
    bundle._no_links(destination)
    if destination == engine.root or engine.root in destination.parents:
        raise Refusal("Write backups outside the live state directory")
    store = engine.store
    with store.lock("app:" + app_id):
        app = store.app(app_id)
        active_runs = store.all("SELECT * FROM runs WHERE app_id=? AND status IN ('starting','running')", (app_id,))
        from .common import process_alive
        if any(process_alive(r["pid"], r["process_created"]) or process_alive(r["runner_pid"], r["runner_created"]) or process_alive(r.get("launcher_pid"), r.get("launcher_created")) for r in active_runs):
            raise Refusal("Stop the application before creating a consistent data backup")
        records, files, total = [], [], 0
        for release_id in dict.fromkeys([app["release_id"], app["previous_release_id"]]):
            if not release_id:
                continue
            package = store.root / "packages" / (release_id + ".schism")
            bundle.inspect(package)
            files.append(("packages/" + package.name, package))
        data = store.root / "data" / app_id
        bundle._no_links(data)
        if data.exists():
            for path in sorted(data.rglob("*")):
                bundle._no_links(path)
                if path.is_file():
                    files.append(("data/" + path.relative_to(data).as_posix(), path))
                elif not path.is_dir():
                    raise Refusal("Backup refuses special files")
                if len(files) > 20000:
                    raise Refusal("Backup exceeds the 20,000 file bound")
        for name, path in files:
            _safe_path(name)
            raw, _ = bundle._regular_bytes(path, MAX_BACKUP)
            total += len(raw)
            if total > MAX_BACKUP or len(files) > 20000:
                raise Refusal("Backup exceeds the 512 MiB / 20,000 file bound")
            records.append({"path": name, "size": len(raw), "sha256": digest(raw)})
        bundle._paths_unique([row["path"] for row in records])
        payload = {"schema": "schism.backup/v1", "created_at": now(), "app_id": app_id,
                   "release_id": app["release_id"], "previous_release_id": app["previous_release_id"],
                   "data_schema": app["data_schema"], "files": records,
                   "excludes": ["private signing keys", "runtime configuration and secrets", "logs", "running processes"]}
        envelope = identity.sign(store.root, payload, "schism.backup/v1")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".partial")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("backup.json", canonical(envelope))
                for record, (name, path) in zip(records, files):
                    raw, _ = bundle._regular_bytes(path, MAX_BACKUP)
                    if digest(raw) != record["sha256"]:
                        raise Refusal("Application data changed during backup")
                    archive.writestr(name, raw)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        store.event("application.backed-up", {"app_id": app_id, "archive_sha256": digest(destination.read_bytes()), "files": len(files)})
        return {"path": str(destination), "app_id": app_id, "sha256": digest(destination.read_bytes()), "key_id": store.identity["key_id"], "files": len(files)}


def restore_application(engine, source, expected_key_id):
    if not expected_key_id:
        raise Refusal("Supply the independently known backup signer fingerprint")
    source = Path(source)
    if source.stat().st_size > MAX_BACKUP:
        raise Refusal("Backup exceeds the supported size")
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) > 20001 or len(set(name.casefold() for name in names)) != len(names):
            raise Refusal("Duplicate or case-colliding backup paths")
        bundle._paths_unique(names)
        for info in infos:
            _safe_path(info.filename)
            if info.filename != info.orig_filename or info.is_dir() or info.flag_bits & 1 or stat.S_IFMT(info.external_attr >> 16) not in {0, stat.S_IFREG}:
                raise Refusal("Encrypted, altered or special backup entry refused")
        if sum(i.file_size for i in infos) > MAX_BACKUP or archive.getinfo("backup.json").file_size > 8 * 1024 * 1024:
            raise Refusal("Expanded backup exceeds the supported size")
        payload = identity.verify(json.loads(archive.read("backup.json")), "schism.backup/v1", expected_key_id)
        if payload.get("schema") != "schism.backup/v1":
            raise Refusal("Unsupported backup format")
        app_id = validate_id(payload["app_id"])
        records = payload["files"]
        if not isinstance(records, list) or len(records) != len({row["path"] for row in records}):
            raise Refusal("Duplicate backup file records")
        if set(names) != {"backup.json", *[row["path"] for row in records]}:
            raise Refusal("Backup inventory is not closed")
        expected_packages = {"packages/" + release_id + ".schism" for release_id in (payload["release_id"], payload.get("previous_release_id")) if release_id}
        if {name for name in names if name.startswith("packages/")} != expected_packages:
            raise Refusal("Backup package inventory differs from selected and prior releases")
        with engine.store.lock("app:" + app_id):
            data_target = engine.root / "data" / app_id
            if engine.store.app(app_id, False) or data_target.exists() or engine.store.one("SELECT app_id FROM data_contracts WHERE app_id=?", (app_id,)):
                raise Refusal("Restore requires an application id with no existing deployment or data")
            staging = Path(tempfile.mkdtemp(prefix="restore-", dir=engine.root / "incoming"))
            try:
                for record in records:
                    name = record["path"]
                    _safe_path(name)
                    if not (name.startswith("packages/") or name.startswith("data/")):
                        raise Refusal("Unsupported backup entry")
                    raw = archive.read(name)
                    if len(raw) != record["size"] or digest(raw) != record["sha256"]:
                        raise Refusal("Backup content failed verification")
                    path = staging.joinpath(*PurePosixPath(name).parts)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                packages = sorted((staging / "packages").glob("*.schism"))
                verified = {}
                for package in packages:
                    item = bundle.inspect(package)
                    if package.stem != item["release_id"] or item["application"]["id"] != app_id or item["application"].get("data_schema", "1") != payload["data_schema"]:
                        raise Refusal("Backup contains a different application, data schema or package identity")
                    verified[item["release_id"]] = item
                required = {value for value in (payload["release_id"], payload.get("previous_release_id")) if value}
                if set(verified) != required:
                    raise Refusal("Backup lacks its selected or prior package identity")
                selected = verified[payload["release_id"]]
                if selected["application"]["id"] != app_id or selected["application"].get("data_schema", "1") != payload["data_schema"]:
                    raise Refusal("Backup application metadata disagrees with signed release")
                if payload.get("previous_release_id"):
                    previous = verified[payload["previous_release_id"]]
                    if previous["application"]["id"] != app_id or previous["application"].get("data_schema", "1") != payload["data_schema"]:
                        raise Refusal("Prior release disagrees with backup application and data contract")
                for package in packages:
                    engine.import_package(package)
                restored_data = staging / "data"
                restored_data.mkdir(exist_ok=True)
                os.replace(restored_data, data_target)
                with engine.store.db() as con:
                    con.execute("INSERT INTO data_contracts VALUES(?,?)", (app_id, payload["data_schema"]))
                    con.execute("INSERT INTO apps VALUES(?,?,?,?,?,?,?,?)", (app_id, payload["release_id"], payload.get("previous_release_id"), 1, "stopped", None, payload["data_schema"], None))
                engine.store.event("application.restored", {"app_id": app_id, "backup_key_id": expected_key_id, "archive_sha256": digest(source.read_bytes()), "execution_authorized": False})
            finally:
                shutil.rmtree(staging)
    return {"app_id": app_id, "status": "stopped", "generation": 1, "trusted": engine.store.trusted(selected), "requires": "Authorize the publisher scope and restore local configuration before starting"}
