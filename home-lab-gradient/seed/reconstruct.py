#!/usr/bin/env python3
"""Reconstruct and verify the seed bundle deterministically."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, _, filename = line.strip().partition("  ")
        if digest and filename:
            result[filename] = digest.lower()
    return result


def copy_seed(root: Path, destination: Path, manifest: dict) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for file_name in manifest["files"]:
        src = root / file_name
        dst = destination / file_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not src.is_file():
            raise FileNotFoundError(f"seed file missing: {src}")
        shutil.copy2(src, dst)


def verify_copies(root: Path, destination: Path, manifest: dict) -> None:
    sums = load_sums(root / manifest["reconstruction"].get("sum_file", "seed/sha256sums.txt"))
    for file_name, expected in sums.items():
        copied = destination / file_name
        observed = sha256_file(copied)
        if observed != expected:
            raise RuntimeError(f"seed copy identity mismatch for {file_name}: expected {expected}, got {observed}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = load_manifest(root / "seed" / "seed-manifest.json")
    first = Path(tempfile.mkdtemp(prefix="seed-reconstruct-"))
    second = Path(tempfile.mkdtemp(prefix="seed-reconstruct-"))
    try:
        copy_seed(root, first, manifest)
        copy_seed(root, second, manifest)
        verify_copies(first, first, manifest)
        verify_copies(first, second, manifest)
    finally:
        shutil.rmtree(first, ignore_errors=True)
        shutil.rmtree(second, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
