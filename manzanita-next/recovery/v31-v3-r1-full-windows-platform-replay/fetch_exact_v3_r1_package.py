#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_NAME = "MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip"
EXPECTED_BYTES = 553_074
EXPECTED_SHA256 = "2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738"
EXPECTED_ROOT = "MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1"
REQUIRED_MEMBERS = {
    f"{EXPECTED_ROOT}/OPERATOR_EXECUTION_BOOTSTRAP_CONTRACT.json",
    f"{EXPECTED_ROOT}/bootstrap_v31_operator_v3_r1.py",
    f"{EXPECTED_ROOT}/resolve_and_run.cmd",
    f"{EXPECTED_ROOT}/RUN_WINDOWS_PLATFORM_REPLAY.cmd",
}
MAX_MEMBERS = 10_000
MAX_UNCOMPRESSED_BYTES = 1_000_000_000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(name: str) -> str:
    if not name or "\x00" in name or name.startswith(("/", "\\")) or "\\" in name:
        raise ValueError(f"unsafe ZIP member: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe ZIP member: {name!r}")
    if path.parts and ":" in path.parts[0]:
        raise ValueError(f"drive-qualified ZIP member: {name!r}")
    return path.as_posix()


def is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def inspect_zip(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("ZIP member limit exceeded")
        names: list[str] = []
        exact: set[str] = set()
        folded: set[str] = set()
        total = 0
        for info in infos:
            name = safe_name(info.filename)
            if name in exact or name.casefold() in folded:
                raise ValueError(f"duplicate or case-colliding ZIP member: {name}")
            if is_symlink(info):
                raise ValueError(f"symlink ZIP member refused: {name}")
            exact.add(name)
            folded.add(name.casefold())
            names.append(name)
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("ZIP expanded-byte limit exceeded")
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if roots != {EXPECTED_ROOT}:
            raise ValueError(f"unexpected release roots: {sorted(roots)}")
        missing = sorted(REQUIRED_MEMBERS - exact)
        if missing:
            raise ValueError(f"required members absent: {missing}")
        return {
            "members": len(names),
            "uncompressed_bytes": total,
            "release_roots": sorted(roots),
            "required_members_present": sorted(REQUIRED_MEMBERS),
            "crc": "PASS",
            "paths_safe": True,
            "paths_unique": True,
            "casefold_unique": True,
            "symlinks_absent": True,
        }


def download(url: str, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Manzanita-v31-exact-package-replay/1.0)",
            "Accept": "application/zip,application/octet-stream;q=0.9,*/*;q=0.1",
        },
    )
    received = 0
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as sink:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            received += len(chunk)
            if received > EXPECTED_BYTES:
                raise ValueError(
                    f"download exceeded exact byte count: {received} > {EXPECTED_BYTES}"
                )
            sink.write(chunk)
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type")
    if received != EXPECTED_BYTES:
        raise ValueError(f"wrong package byte count: {received} != {EXPECTED_BYTES}")
    observed_sha = sha256(temporary)
    if observed_sha != EXPECTED_SHA256:
        raise ValueError(f"wrong package SHA-256: {observed_sha}")
    os.replace(temporary, output)
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "bytes": received,
        "sha256": observed_sha,
    }


def extract(path: Path, destination: Path) -> dict[str, Any]:
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = safe_name(info.filename)
            target = temporary.joinpath(*PurePosixPath(name).parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    if destination.exists():
        shutil.rmtree(destination)
    os.replace(temporary, destination)
    package_root = destination / EXPECTED_ROOT
    if not package_root.is_dir():
        raise ValueError(f"extracted package root absent: {package_root}")
    return {
        "destination": str(destination),
        "package_root": str(package_root),
        "entrypoint": str(package_root / "RUN_WINDOWS_PLATFORM_REPLAY.cmd"),
    }


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    receipt: dict[str, Any] = {
        "schema": "manzanita/v31-v3-r1-exact-package-acquisition@1",
        "result": "FAIL_V31_V3_R1_EXACT_PACKAGE_ACQUISITION_NOT_COMPLETED",
        "observed_at": now_iso(),
        "expected": {
            "filename": EXPECTED_NAME,
            "bytes": EXPECTED_BYTES,
            "sha256": EXPECTED_SHA256,
            "release_root": EXPECTED_ROOT,
        },
        "download": None,
        "zip": None,
        "extraction": None,
        "authority": {
            "operator_storage_read": False,
            "production_inputs_materialized": 0,
            "production_admission_invoked": False,
            "accepted_parent_extracted": False,
            "product_mutation": False,
            "merge_authorized": False,
            "release_authorized": False,
            "public_route_effect": "none",
            "pages_effect": "none",
            "external_effect": "none",
        },
        "error": None,
    }
    try:
        if args.output.name != EXPECTED_NAME:
            raise ValueError(f"output filename must remain {EXPECTED_NAME}")
        receipt["download"] = download(args.url, args.output)
        receipt["zip"] = inspect_zip(args.output)
        receipt["extraction"] = extract(args.output, args.extract_root)
        receipt["result"] = "PASS_V31_V3_R1_EXACT_PACKAGE_ACQUIRED_VERIFIED_AND_ISOLATED"
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        atomic_json(args.receipt, receipt)
        raise
    atomic_json(args.receipt, receipt)
    print(receipt["result"])
    print(receipt["extraction"]["entrypoint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
