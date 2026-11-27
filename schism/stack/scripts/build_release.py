#!/usr/bin/env python3
"""Build a deterministic source archive with a closed source inventory."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1"
ROOT_FILES = {"README.md", "LICENSE", "PROVENANCE.md", "CONTRACT.md", "QUALIFICATION.md", "QUALIFICATION.json", "pyproject.toml", "requirements.txt", "requirements.lock", "schism.py", "launch-schism.cmd", "launch-schism.sh", "NOTICE"}
DIRECTORIES = {"schism_stack", "tests", "examples", "scripts"}


def collect():
    entries = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if relative.parts[0] not in DIRECTORIES and relative.as_posix() not in ROOT_FILES:
            continue
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink():
            raise SystemExit("Source contains a symbolic link: " + str(relative))
        if path.is_file():
            entries.append((relative.as_posix(), path.read_bytes(), path.suffix == ".sh"))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    output.mkdir(parents=True, exist_ok=True)
    entries = collect()
    files = [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw, _ in entries]
    manifest = {"schema": "schism.source-release/v1", "version": VERSION, "files": files}
    manifest_raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    entries.append(("SOURCE-MANIFEST.json", manifest_raw, False))
    archive_path = output / ("schism-stack-" + VERSION + "-source.zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw, executable in sorted(entries):
            info = zipfile.ZipInfo("schism-stack/" + name, (2026, 11, 27, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((stat.S_IFREG | (0o755 if executable else 0o644)) << 16)
            archive.writestr(info, raw)
    (output / "SOURCE-MANIFEST.json").write_bytes(manifest_raw)
    result = {"file": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "files": len(files), "source_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest()}
    (output / "SOURCE-RELEASE.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
