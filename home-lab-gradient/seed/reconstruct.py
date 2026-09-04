#!/usr/bin/env python3
"""Reconstruct the Gradient Linux seed bundle from committed source.

The seed is content-addressed, so reconstruction must be byte-deterministic:
this script rebuilds the bundle twice into two fresh directories, verifies each
rebuild against ``seed/sha256sums.txt``, and proves the two rebuilds are
byte-identical to each other and to the committed source.

Standard library only, and free of any import from this repository beyond the
seed's own ``verify.py``: the seed must be reconstructable on a host that has
no clone of it.

Usage::

    python seed/reconstruct.py                 # prove byte-identity, twice
    python seed/reconstruct.py --into DIR      # materialize a bundle for transfer
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parent
SUM_FILE = "seed/sha256sums.txt"


def load_verifier() -> Any:
    """Load the seed's own verifier by path, not by package import."""
    spec = importlib.util.spec_from_file_location("gradient_seed_verify", str(SEED_DIR / "verify.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("seed/verify.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    """Digest exact file bytes. Never a text-mode read: line endings count."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_files(root: Path) -> list[str]:
    manifest = json.loads((root / "seed" / "seed-manifest.json").read_text(encoding="utf-8"))
    files = list(manifest.get("files") or [])
    if not files:
        raise RuntimeError("seed-manifest.json declares no files")
    if SUM_FILE in files:
        raise RuntimeError(f"{SUM_FILE} must not list itself in manifest files")
    return files + [SUM_FILE]


def reconstruct(root: Path, destination: Path) -> dict[str, str]:
    """Copy exact bytes into destination; return {relative name: sha256}."""
    digests: dict[str, str] = {}
    for name in bundle_files(root):
        source = root / name
        if not source.is_file():
            raise FileNotFoundError(f"seed source file missing: {source}")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        digests[name] = sha256_file(target)
    return digests


def bundle_digest(digests: dict[str, str]) -> str:
    """One content address over the whole bundle, order-independent."""
    payload = json.dumps(digests, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct and verify the Gradient Linux seed")
    parser.add_argument(
        "--root",
        default=str(SEED_DIR.parent),
        help="Repository seed root (the directory holding scripts/ and seed/)",
    )
    parser.add_argument(
        "--into",
        default="",
        help="Materialize one verified bundle into this directory instead of a temporary one",
    )
    parser.add_argument(
        "--write-sums",
        action="store_true",
        help="Regenerate seed/sha256sums.txt from the manifest file list (build step, not verification)",
    )
    return parser.parse_args(argv)


def write_sums(root: Path) -> Path:
    """Regenerate the checksum file from the manifest's declared files.

    Written as LF bytes with no BOM: the digests are over exact bytes, so the
    checksum file's own encoding is part of the seed identity.
    """
    manifest = json.loads((root / "seed" / "seed-manifest.json").read_text(encoding="utf-8"))
    names = sorted(manifest.get("files") or [])
    if not names:
        raise RuntimeError("seed-manifest.json declares no files")
    body = "".join(f"{sha256_file(root / name)}  {name}\n" for name in names)
    target = root / SUM_FILE
    target.write_bytes(body.encode("ascii"))
    return target


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    verifier = load_verifier()

    if args.write_sums:
        target = write_sums(root)
        print(json.dumps({"ok": True, "wrote": str(target), "seed_id": sha256_file(target)}, indent=2))
        return 0

    source_failures = verifier.verify(root)
    if source_failures:
        print(json.dumps({"ok": False, "stage": "source", "failures": source_failures}, indent=2))
        return 1

    if args.into:
        destination = Path(args.into).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        digests = reconstruct(root, destination)
        failures = verifier.verify(destination)
        if failures:
            print(json.dumps({"ok": False, "stage": "materialize", "failures": failures}, indent=2))
            return 1
        print(
            json.dumps(
                {
                    "ok": True,
                    "destination": str(destination),
                    "seed_id": verifier.seed_id(destination),
                    "bundle_sha256": bundle_digest(digests),
                    "files": digests,
                },
                indent=2,
            )
        )
        return 0

    first = Path(tempfile.mkdtemp(prefix="gradient-seed-reconstruct-1-"))
    second = Path(tempfile.mkdtemp(prefix="gradient-seed-reconstruct-2-"))
    try:
        first_digests = reconstruct(root, first)
        second_digests = reconstruct(root, second)
        failures = verifier.verify(first) + verifier.verify(second)
        if failures:
            print(json.dumps({"ok": False, "stage": "reconstruct", "failures": failures}, indent=2))
            return 1
        first_bundle = bundle_digest(first_digests)
        second_bundle = bundle_digest(second_digests)
        source_bundle = bundle_digest({name: sha256_file(root / name) for name in bundle_files(root)})
        identical = first_digests == second_digests == {
            name: sha256_file(root / name) for name in bundle_files(root)
        }
        result = {
            "ok": identical and first_bundle == second_bundle == source_bundle,
            "seed_id": verifier.seed_id(root),
            "source_bundle_sha256": source_bundle,
            "runs": [
                {"run": 1, "bundle_sha256": first_bundle, "files": first_digests},
                {"run": 2, "bundle_sha256": second_bundle, "files": second_digests},
            ],
            "byte_identical": identical,
        }
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    finally:
        shutil.rmtree(first, ignore_errors=True)
        shutil.rmtree(second, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
