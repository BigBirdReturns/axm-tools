#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def load_manifest(carrier: Path) -> dict[str, Any]:
    path = carrier / "CARRIER_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("format") != "axm-aperture-g1-hosted-carrier/1":
        raise SystemExit("unsupported carrier manifest")
    if value.get("authority") != "transport-only":
        raise SystemExit("carrier authority must remain transport-only")
    return value


def verify_file(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"missing regular carrier file: {path}")
    size = path.stat().st_size
    if size != expected_bytes:
        raise SystemExit(f"carrier size mismatch for {path.name}: {size} != {expected_bytes}")
    actual = digest(path)
    if actual != expected_sha256:
        raise SystemExit(f"carrier digest mismatch for {path.name}: {actual} != {expected_sha256}")


def safe_members(archive: Path, manifest: dict[str, Any]) -> list[tarfile.TarInfo]:
    limits = manifest["limits"]
    top_level = manifest["archive"]["top_level"]
    with tarfile.open(archive, mode="r:xz") as bundle:
        members = bundle.getmembers()
    if len(members) > int(limits["maximum_members"]):
        raise SystemExit("carrier member ceiling exceeded")
    expanded = 0
    regular_files = 0
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or not name.parts or name.parts[0] != top_level or ".." in name.parts:
            raise SystemExit(f"unsafe carrier path: {member.name}")
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise SystemExit(f"unsupported carrier member type: {member.name}")
        if not member.isdir() and not member.isfile():
            raise SystemExit(f"unsupported carrier member: {member.name}")
        if member.isfile():
            regular_files += 1
            expanded += int(member.size)
    if regular_files != int(manifest["archive"]["file_count"]):
        raise SystemExit(f"carrier file denominator mismatch: {regular_files}")
    if expanded > int(limits["maximum_expanded_bytes"]):
        raise SystemExit("carrier expansion ceiling exceeded")
    return members


def materialize(carrier: Path, workspace: Path) -> Path:
    manifest = load_manifest(carrier)
    declared = [entry["path"] for entry in manifest["parts"]]
    actual = sorted(path.name for path in carrier.glob("part-*.bin"))
    if actual != sorted(declared):
        raise SystemExit(f"carrier part set mismatch: {actual} != {sorted(declared)}")

    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / manifest["archive"]["top_level"]
    if target.exists():
        raise SystemExit(f"refusing to overwrite materialized target: {target}")

    with tempfile.TemporaryDirectory(prefix="aperture-g1-carrier-", dir=workspace) as temporary:
        temp = Path(temporary)
        archive = temp / manifest["archive"]["path"]
        with archive.open("wb") as output:
            for entry in manifest["parts"]:
                part = carrier / entry["path"]
                verify_file(part, int(entry["bytes"]), str(entry["sha256"]))
                with part.open("rb") as source:
                    shutil.copyfileobj(source, output, length=1 << 20)
            output.flush()
            os.fsync(output.fileno())
        verify_file(
            archive,
            int(manifest["archive"]["bytes"]),
            str(manifest["archive"]["sha256"]),
        )
        members = safe_members(archive, manifest)
        extraction = temp / "expanded"
        extraction.mkdir()
        with tarfile.open(archive, mode="r:xz") as bundle:
            bundle.extractall(extraction, members=members, filter="data")
        source = extraction / manifest["archive"]["top_level"]
        if not source.is_dir():
            raise SystemExit("carrier did not contain the declared top-level directory")
        os.replace(source, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--carrier", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    target = materialize(args.carrier.resolve(), args.workspace.resolve())
    print(json.dumps({
        "format": "axm-aperture-g1-materialization-receipt/1",
        "status": "PASS",
        "target": str(target),
        "authority": "none",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
