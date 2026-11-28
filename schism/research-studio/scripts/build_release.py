#!/usr/bin/env python3
"""Build the deterministic Research Studio source and documentary-sample ZIP."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "LICENSE", "README.md", "QUALIFICATION.md", "supervise_service.py",
    "app/LICENSE", "app/schism.json", "app/studio.py", "app/web/README.md",
    "app/web/app.js", "app/web/index.html", "app/web/style.css",
    "tests/test_studio.py", "tests/test_supervisor.py",
    "examples/room-reproduction/README.md", "examples/room-reproduction/reproduce.py",
    "examples/room-reproduction/task.py", "examples/room-reproduction/verify.py",
    "examples/documentary/README.md", "examples/documentary/findings.json",
    "examples/documentary/SHA256SUMS", "examples/documentary/run.py",
    "scripts/build_release.py",
)


def main():
    version = json.loads((ROOT / "app/schism.json").read_text(encoding="utf-8"))["version"]
    prefix = f"research-studio-{version}"
    names = FILES + tuple("examples/documentary/records/" + vendor["id"] + ".json" for vendor in
                         json.loads((ROOT / "examples/documentary/findings.json").read_text(encoding="utf-8"))["vendors"])
    files = {name: (ROOT / name).read_bytes() for name in names}
    manifest = {"schema": "research-studio-source@1", "version": version,
                "scope": "Research reader source, focused tests and public documentary sample",
                "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files["SOURCE-MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + "/" + name, date_time=(2026, 11, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    destination = ROOT / "downloads"
    destination.mkdir(exist_ok=True)
    archive_path = destination / f"{prefix}-source.zip"
    payload = buffer.getvalue()
    archive_path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (destination / "SHA256SUMS").write_text(digest + "  " + archive_path.name + "\n", encoding="ascii")
    print(json.dumps({"archive": str(archive_path), "bytes": len(payload), "sha256": digest,
                      "source_files": len(names)}, indent=2))


if __name__ == "__main__":
    main()
