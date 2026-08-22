from __future__ import annotations

import base64
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNK_ROOT = ROOT / ".github" / "axm-witness-v0.9.1"
EXPECTED_ZIP_BYTES = 108_298
EXPECTED_ZIP_SHA256 = "b7c70b31e1756543aa2323f1361e0393db488fc4855a9341cc28932d6379412c"
EXPECTED_HTML_BYTES = 497_004
EXPECTED_HTML_SHA256 = "d5d1f33f6cb2981497489f24468939f752cc5de39e66ebcf4ff11838ad1843f7"
EXPECTED_CHUNKS = {
    "site.part-00.b64": "0bc54184ca08b45c8bc995b0eb2ef3eea306d1e17285d69f92c808dbbbfa14b2",
    "site.part-01.b64": "3d80112d2cceae97c982c7091113f746c7b11216c57d96730b1e07edbd67f80a",
    "site.part-02.b64": "2601605ad46854811032fe309fde74e4f5a4ab367fc4b7f609abcbb6fca19c3d",
    "site.part-03.b64": "c2b2df41970e096215b1d4870e3209388bbc6986baf81c23bdf8b3066bf025a3",
    "site.part-04.b64": "7497ae9c2d3c19b68ae41b51b172ef8a7f43d7ac0f5e9617d08ebd0611c8f044",
    "site.part-05.b64": "d33f0e9ff55ab658cf115f6a2a3b091afb5fc4f26e24d917df4cebe0bafbee6f",
    "site.part-06.b64": "d4bbd3cf45b8ace68aab6ecb76a72a6882f03f378bf803ab19d06400f1624c15",
    "site.part-07.b64": "54b86c30856b0b1e590054505467fee85a1af48eb64148b6f6ede8e5616efc36",
    "site.part-08.b64": "aec634585125b3f7590fb25ffe14a53a8d8729144bf9723d656244378b985597",
    "site.part-09.b64": "f4314fccee7e917e4f664495806454fabe16b7fd175b5e82808a16ef3a88e84c",
    "site.part-10.b64": "1c61269068e173d98ebba53f2d46cfe0e9a991ea05213ac320177fa0531fe6cc",
    "site.part-11.b64": "2006e1d2b1938c2b073e1668f966e904dcbefe887e5b20724cbfc97dc9b32c7f",
    "site.part-12.b64": "dab56e57af72d54fd61646e280c799a12f074f70c3ba291bae6af0305bda02cb",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reconstruct() -> tuple[bytes, bytes]:
    observed = sorted(path.name for path in CHUNK_ROOT.glob("site.part-*.b64"))
    assert observed == sorted(EXPECTED_CHUNKS), observed
    encoded: list[str] = []
    for name in sorted(EXPECTED_CHUNKS):
        body = (CHUNK_ROOT / name).read_bytes()
        assert sha256(body) == EXPECTED_CHUNKS[name], name
        encoded.append(body.decode("ascii"))
    package = base64.b64decode("".join(encoded), validate=True)
    assert len(package) == EXPECTED_ZIP_BYTES, len(package)
    assert sha256(package) == EXPECTED_ZIP_SHA256
    package_path = Path("/tmp/AXM_Witness_Department_Ledger_0.9.1_SITE.zip")
    package_path.write_bytes(package)
    with zipfile.ZipFile(package_path) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == ["index.html", ".nojekyll"], archive.namelist()
        html = archive.read("index.html")
        nojekyll = archive.read(".nojekyll")
    assert len(html) == EXPECTED_HTML_BYTES, len(html)
    assert sha256(html) == EXPECTED_HTML_SHA256
    assert nojekyll == b""
    return html, nojekyll


def integrate_docs() -> None:
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    row = "| [`axm-witness/`](axm-witness/) | Department-controlled local export-ledger pilot for authorized Flock-shaped exports: exact source custody, signed evidence and human-decision history, rationale-bearing review, tamper detection, encrypted backup and same-key restoration, interrupted-import recovery, duplicate refusal, and replacement lineage | [AXM Witness Department Ledger 0.9.1](https://bigbirdreturns.github.io/axm-tools/axm-witness/) — 30/30 native qualification; upstream delivery completeness remains outside the ledger |\n"
    if "AXM Witness Department Ledger 0.9.1" not in readme:
        marker = "| [`polybolos/`](polybolos/) |"
        assert marker in readme
        readme = readme.replace(marker, row + marker, 1)
    readme_path.write_text(readme, encoding="utf-8", newline="\n")

    directory_path = ROOT / "index.html"
    directory = directory_path.read_text(encoding="utf-8")
    card = '''<div class="tool">
  <div class="title"><a href="axm-witness/">AXM Witness Department Ledger 0.9.1</a></div>
  <div class="desc">A department-controlled local export-ledger pilot for authorized Flock-shaped exports. It preserves exact source bytes, signs evidence and rationale-bearing human decisions, detects source and state tampering, supports encrypted full-ledger backup and same-key restoration, recovers interrupted imports, refuses duplicates, and retains replacement lineage. The native release qualification passes 30 of 30 controls; upstream delivery completeness remains outside the ledger.</div>
  <a class="open" href="axm-witness/">Open AXM Witness →</a>
</div>

'''
    if "AXM Witness Department Ledger 0.9.1" not in directory:
        marker = '<div class="tool">\n  <div class="title"><a href="polybolos/">'
        assert marker in directory
        directory = directory.replace(marker, card + marker, 1)
    directory_path.write_text(directory, encoding="utf-8", newline="\n")

    continuity_path = ROOT / "CONTINUITY.md"
    continuity = continuity_path.read_text(encoding="utf-8")
    entry = "- `axm-witness/` — AXM Witness Department Ledger 0.9.1: an exact-byte, department-controlled local export-ledger pilot for authorized Flock-shaped exports, qualified 30/30 under native browser storage and WebCrypto. It proves department custody and decisions after receipt; vendor-declared completeness and pre-delivery origin remain external boundaries.\n"
    if "AXM Witness Department Ledger 0.9.1" not in continuity:
        marker = "- `pta-tracker/` — the living tool:"
        assert marker in continuity
        continuity = continuity.replace(marker, entry + marker, 1)
    continuity_path.write_text(continuity, encoding="utf-8", newline="\n")


def main() -> None:
    html, nojekyll = reconstruct()
    site = ROOT / "axm-witness"
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    (site / "index.html").write_bytes(html)
    (site / ".nojekyll").write_bytes(nojekyll)

    legacy = ROOT / "witness"
    if legacy.exists():
        shutil.rmtree(legacy)

    integrate_docs()
    shutil.rmtree(CHUNK_ROOT)
    for name in (
        "axm-witness-bootstrap-0.9.1.yml",
        "axm-witness-bootstrap-pr-0.9.1.yml",
    ):
        path = ROOT / ".github" / "workflows" / name
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    main()
