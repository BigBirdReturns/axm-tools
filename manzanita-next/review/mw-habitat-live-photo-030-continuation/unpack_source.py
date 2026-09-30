#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import lzma
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
EXPECTED_PREFIX = PurePosixPath(
    "manzanita-next/review/mw-habitat-live-photo-030-continuation"
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    expected = json.loads((ROOT / "PAYLOAD_RECEIPT.json").read_text())
    expected_parts = expected.get("carrier_parts", [])
    part_paths = [ROOT / item["path"] for item in expected_parts]
    checks: list[dict] = []

    def check(name: str, condition: bool, detail="") -> None:
        checks.append({"name": name, "pass": bool(condition), "detail": detail})

    check(
        "carrier part count",
        len(part_paths) == expected.get("carrier_part_count"),
        len(part_paths),
    )
    on_disk = sorted(ROOT.glob("SOURCE_PAYLOAD.tar.xz.b64.part*"))
    check(
        "no undeclared payload parts",
        [path.name for path in on_disk] == [item["path"] for item in expected_parts],
        [path.name for path in on_disk],
    )

    chunks: list[bytes] = []
    for index, (path, item) in enumerate(zip(part_paths, expected_parts), start=1):
        exists = path.is_file()
        check(f"part {index:02d} exists", exists, path.name)
        raw = path.read_bytes() if exists else b""
        check(f"part {index:02d} bytes", len(raw) == item["bytes"], len(raw))
        check(f"part {index:02d} sha256", sha256(raw) == item["sha256"], sha256(raw))
        chunks.append(raw.strip())

    raw_b64 = b"".join(chunks)
    check("base64 bytes", len(raw_b64) == expected["base64_bytes"], len(raw_b64))
    check("base64 sha256", sha256(raw_b64) == expected["base64_sha256"], sha256(raw_b64))

    try:
        xz_raw = base64.b64decode(raw_b64, validate=True)
        check("base64 decode", True)
    except Exception as exc:
        xz_raw = b""
        check("base64 decode", False, str(exc))

    check("xz bytes", len(xz_raw) == expected["xz_bytes"], len(xz_raw))
    check("xz sha256", sha256(xz_raw) == expected["xz_sha256"], sha256(xz_raw))

    try:
        tar_raw = lzma.decompress(xz_raw, format=lzma.FORMAT_XZ)
        check("xz decode", True)
    except Exception as exc:
        tar_raw = b""
        check("xz decode", False, str(exc))

    check("tar bytes", len(tar_raw) == expected["tar_bytes"], len(tar_raw))
    check("tar sha256", sha256(tar_raw) == expected["tar_sha256"], sha256(tar_raw))

    members: list[tarfile.TarInfo] = []
    unsafe: list[str] = []
    special: list[str] = []
    duplicate: list[str] = []
    payloads: dict[str, bytes] = {}

    if tar_raw:
        try:
            with tarfile.open(fileobj=io.BytesIO(tar_raw), mode="r:") as archive:
                members = archive.getmembers()
                seen: set[str] = set()
                for member in members:
                    pure = PurePosixPath(member.name)
                    key = member.name.casefold()
                    if (
                        pure.is_absolute()
                        or ".." in pure.parts
                        or not pure.parts
                        or PurePosixPath(*pure.parts[: len(EXPECTED_PREFIX.parts)])
                        != EXPECTED_PREFIX
                    ):
                        unsafe.append(member.name)
                    if key in seen:
                        duplicate.append(member.name)
                    seen.add(key)
                    if not member.isfile():
                        special.append(member.name)
                    stream = archive.extractfile(member) if member.isfile() else None
                    payloads[member.name] = stream.read() if stream else b""
                check("tar parse", True)
        except Exception as exc:
            check("tar parse", False, str(exc))

    check("member count", len(members) == expected["member_count"], len(members))
    check("safe bounded paths", not unsafe, unsafe)
    check("regular files only", not special, special)
    check("no duplicate paths", not duplicate, duplicate)
    required_manifest = (EXPECTED_PREFIX / "SOURCE_MANIFEST.json").as_posix()
    check("source manifest present", required_manifest in payloads, required_manifest)

    passed = all(item["pass"] for item in checks)
    if passed:
        shutil.rmtree(args.destination, ignore_errors=True)
        args.destination.mkdir(parents=True)
        for name in sorted(payloads):
            target = args.destination / Path(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payloads[name])
            target.chmod(0o644)

    result = {
        "schema": "manzanita/useful-plant-v30-source-replay-unpack@3",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": "PASS" if passed else "FAIL",
        "checks_passed": sum(item["pass"] for item in checks),
        "checks_total": len(checks),
        "checks": checks,
        "destination": str(args.destination),
        "part_count": len(part_paths),
        "member_count": len(members),
        "operator_visual_acceptance": "ABSENT",
        "release_authorized": False,
        "public_route_effect": "none",
        "external_effect": "none",
    }
    receipt = args.receipt or ROOT / "UNPACK_RECEIPT.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
