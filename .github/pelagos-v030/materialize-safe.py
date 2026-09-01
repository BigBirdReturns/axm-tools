from __future__ import annotations

import base64
import hashlib
import importlib.util
import pathlib
import shutil
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
STAGE = ROOT / ".github" / "pelagos-v030"
ARCHIVE = pathlib.Path("/tmp/pelagos-v030-source.tar.gz")
EXPECTED_SHA256 = "4db9cc0391d33d69d2ebfb810ea97f7011c58ba5cf54e80be0cbf97e9a169eeb"

spec = importlib.util.spec_from_file_location("pelagos_materializer", STAGE / "materialize.py")
if spec is None or spec.loader is None:
    raise SystemExit("could not load staged materializer")
materializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(materializer)

parts = sorted(STAGE.glob("pelagos-v030-source-part-*.b64"))
if len(parts) != 8:
    raise SystemExit(f"expected 8 source parts, found {len(parts)}")
encoded = "".join(part.read_text(encoding="utf-8").strip() for part in parts)
payload = base64.b64decode(encoded, validate=True)
digest = hashlib.sha256(payload).hexdigest()
if digest != EXPECTED_SHA256:
    raise SystemExit(f"archive digest mismatch: {digest}")
ARCHIVE.write_bytes(payload)

unpack = pathlib.Path("/tmp/pelagos-v030")
if unpack.exists():
    shutil.rmtree(unpack)

with tarfile.open(ARCHIVE, "r:gz") as archive:
    admitted: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        posix = pathlib.PurePosixPath(member.name)
        # node_modules is disposable qualification scaffolding. It is never
        # part of the released runtime, so do not extract or evaluate its
        # package-manager symlinks. Links remain forbidden everywhere else.
        if len(posix.parts) >= 2 and posix.parts[0] == "pelagos-v030" and posix.parts[1] == "node_modules":
            continue
        target = (pathlib.Path("/tmp") / member.name).resolve()
        if pathlib.Path("/tmp") not in target.parents and target != pathlib.Path("/tmp"):
            raise SystemExit(f"unsafe archive member: {member.name}")
        if member.issym() or member.islnk():
            raise SystemExit(f"archive links are forbidden outside node_modules: {member.name}")
        admitted.append(member)
    archive.extractall("/tmp", members=admitted)

release = ROOT / "pelagos-governance"
if release.exists():
    shutil.rmtree(release)
shutil.move(str(unpack), str(release))
shutil.rmtree(release / "node_modules", ignore_errors=True)

materializer.qualify(release)
materializer.register()
materializer.cleanup()
print("Pelagos Governance Layer v0.3.0 safely materialized and qualified")
