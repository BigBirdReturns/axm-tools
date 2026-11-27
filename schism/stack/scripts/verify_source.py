#!/usr/bin/env python3
"""Verify an extracted source release without importing its application code."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "SOURCE-MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "schism.source-release/v1":
        raise SystemExit("Unknown source manifest")
    expected = {row["path"]: row for row in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise SystemExit("Duplicate source inventory")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SystemExit("Symbolic link inside source tree")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if "__pycache__" in path.relative_to(root).parts and path.suffix in {".pyc", ".pyo"}:
                continue
            if name == "SOURCE-MANIFEST.json":
                continue
            actual.add(name)
            if name not in expected:
                raise SystemExit("Unexpected source file: " + name)
            raw = path.read_bytes()
            if len(raw) != expected[name]["bytes"] or hashlib.sha256(raw).hexdigest() != expected[name]["sha256"]:
                raise SystemExit("Source integrity failure: " + name)
    if actual != set(expected):
        raise SystemExit("Source inventory has missing files")
    print(json.dumps({"valid": True, "version": manifest["version"], "files": len(actual)}))


if __name__ == "__main__":
    main()
