#!/usr/bin/env python3
"""Verify the seed bundle against its own SHA256SUMS before collection.

Standard library only, and deliberately free of any import from this
repository: the seed must run on a host that has no clone of it.

The seed identity is the SHA-256 of the exact bytes of ``seed/sha256sums.txt``.
That file binds every other seed file, so one digest addresses the bundle
without any file needing to contain its own digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SUM_FILE = "seed/sha256sums.txt"


def sha256_file(path: Path) -> str:
    """Digest exact file bytes. Never a text-mode read: line endings count."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sums(path: Path) -> dict[str, str]:
    """Parse a sha256sum-format file from its exact bytes.

    Read as bytes and decoded strictly so a stray BOM or CRLF is a parse
    failure here rather than a digest mismatch three steps later.
    """
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path.name} carries a UTF-8 BOM; seed sums must be plain ASCII")
    if b"\r" in raw:
        raise ValueError(f"{path.name} carries CRLF line endings; seed sums must be LF")
    result: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator or not digest or not name:
            raise ValueError(f"{path.name}: unparsable line: {line!r}")
        result[name] = digest.lower()
    return result


def seed_id(root: Path) -> str:
    return sha256_file(root / SUM_FILE)


def verify(root: Path) -> list[str]:
    """Return the list of seed integrity failures. Empty means verified."""
    sum_path = root / SUM_FILE
    if not sum_path.is_file():
        return [f"seed sum file missing: {SUM_FILE}"]
    try:
        sums = load_sums(sum_path)
    except ValueError as exc:
        return [str(exc)]
    if not sums:
        return [f"{SUM_FILE} lists no files"]
    failures: list[str] = []
    for name, expected in sorted(sums.items()):
        target = root / name
        if not target.is_file():
            failures.append(f"seed file missing: {name}")
            continue
        observed = sha256_file(target)
        if observed != expected:
            failures.append(f"seed file digest mismatch: {name} expected {expected} observed {observed}")
    manifest_path = root / "seed" / "seed-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = set(manifest.get("files") or [])
        bound = set(sums)
        for name in sorted(declared - bound):
            failures.append(f"manifest file not bound by {SUM_FILE}: {name}")
        for name in sorted(bound - declared):
            failures.append(f"{SUM_FILE} binds a file the manifest does not declare: {name}")
    else:
        failures.append("seed/seed-manifest.json missing")
    return failures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Gradient Linux seed bundle")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Seed bundle root (the directory holding scripts/ and seed/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    failures = verify(root)
    if failures:
        print(json.dumps({"ok": False, "root": str(root), "failures": failures}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "root": str(root), "seed_id": seed_id(root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
