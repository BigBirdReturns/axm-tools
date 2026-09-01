from __future__ import annotations

import base64
import hashlib
import pathlib
import shutil
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
STAGE = ROOT / ".github" / "pelagos-v030"
ARCHIVE = pathlib.Path("/tmp/pelagos-v030-source.tar.gz")
EXPECTED_SHA256 = "4db9cc0391d33d69d2ebfb810ea97f7011c58ba5cf54e80be0cbf97e9a169eeb"
BRANCH = "feat/pelagos-governance-layer"


def run(*args: str, cwd: pathlib.Path | None = None) -> None:
    subprocess.run(list(args), cwd=cwd or ROOT, check=True)


def reconstruct() -> pathlib.Path:
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
        for member in archive.getmembers():
            target = (pathlib.Path("/tmp") / member.name).resolve()
            if pathlib.Path("/tmp") not in target.parents and target != pathlib.Path("/tmp"):
                raise SystemExit(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk():
                raise SystemExit(f"archive links are forbidden: {member.name}")
        archive.extractall("/tmp")

    target = ROOT / "pelagos-governance"
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(unpack), str(target))
    shutil.rmtree(target / "node_modules", ignore_errors=True)
    return target


def qualify(tool: pathlib.Path) -> None:
    run("python", "scripts/build_standalone.py", cwd=tool)
    run("python", "scripts/validate.py", cwd=tool)
    for source in sorted((tool / "app").glob("*.js")) + sorted((tool / "data" / "parts").glob("*.js")):
        run("node", "--check", str(source))

    run("npm", "install", "--no-save", "--package-lock=false", "playwright@1.55.0", cwd=tool)
    run("npx", "playwright", "install", "--with-deps", "chromium", cwd=tool)
    run("node", "tests/verify.mjs", cwd=tool)
    shutil.rmtree(tool / "node_modules", ignore_errors=True)


def register() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    row = (
        "| [`pelagos-governance/`](pelagos-governance/) | Founder-controlled local-first company-state runtime for hard-tech relationships, instruments, claims, evidence, rights, authority, decisions, receipts, and succession. The embedded Pelagos cartridge is public-safe; private files remain local in the browser. | [Pelagos Governance Layer v0.3.0](https://bigbirdreturns.github.io/axm-tools/pelagos-governance/) — public-safe inspection; save `standalone.html` for private company state |\n"
    )
    if "[`pelagos-governance/`]" not in text:
        marker = "| [`acceptance.html`](acceptance.html) |"
        readme.write_text(text.replace(marker, row + marker, 1), encoding="utf-8")

    index = ROOT / "index.html"
    text = index.read_text(encoding="utf-8")
    card = "\n".join(
        [
            '<div class="tool">',
            '  <div class="title"><a href="pelagos-governance/">Pelagos Governance Layer 0.3.0</a></div>',
            '  <div class="desc">A founder-controlled local-first company-state runtime for Pelagos. It reconstructs the public relationship, instrument, claim, evidence, rights, and authority surfaces already in motion, then admits private source hashes and successor states under one named custodian. No source upload, shared-cloud dependency, or external-effect adapter.</div>',
            '  <a class="open" href="pelagos-governance/">Open the governance layer →</a>',
            '</div>',
            '',
            '',
        ]
    )
    if 'href="pelagos-governance/"' not in text:
        marker = '<div class="tool">\n  <div class="title"><a href="acceptance.html">'
        index.write_text(text.replace(marker, card + marker, 1), encoding="utf-8")

    continuity = ROOT / "CONTINUITY.md"
    text = continuity.read_text(encoding="utf-8")
    bullet = (
        "- `pelagos-governance/` — founder-controlled local-first company-state runtime. The public cartridge is inspectable; private operation starts only after a named Pelagos decision owner, technical owner, communications owner, and custodian admit the working copy. It has no external-effect adapter and preserves successor state rather than overwriting prior records.\n"
    )
    if "`pelagos-governance/`" not in text:
        continuity.write_text(text.replace("- `axm-witness/`", bullet + "- `axm-witness/`", 1), encoding="utf-8")

    check = ROOT / ".github" / "workflows" / "pelagos-governance-check.yml"
    check.write_text(
        """name: Pelagos Governance Layer qualification

on:
  push:
    paths:
      - 'pelagos-governance/**'
      - '.github/workflows/pelagos-governance-check.yml'
  pull_request:
    paths:
      - 'pelagos-governance/**'
      - '.github/workflows/pelagos-governance-check.yml'
  workflow_dispatch: {}

permissions:
  contents: read

jobs:
  qualify:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Rebuild and verify frozen release
        run: |
          python pelagos-governance/scripts/build_standalone.py
          git diff --exit-code -- pelagos-governance/standalone.html
          python pelagos-governance/scripts/validate.py
          git diff --exit-code -- pelagos-governance/QUALIFICATION.json
          for f in pelagos-governance/app/*.js pelagos-governance/data/parts/*.js; do node --check "$f"; done
      - name: Install disposable browser harness
        working-directory: pelagos-governance
        run: |
          npm install --no-save --package-lock=false playwright@1.55.0
          npx playwright install --with-deps chromium
      - name: Run browser campaign
        working-directory: pelagos-governance
        run: node tests/verify.mjs
""",
        encoding="utf-8",
    )


def cleanup() -> None:
    shutil.rmtree(STAGE)
    for path in (
        ROOT / ".github" / "workflows" / "pelagos-governance-capture.yml",
        ROOT / ".github" / "workflows" / "pelagos-governance-materialize.yml",
    ):
        path.unlink(missing_ok=True)


def main() -> None:
    tool = reconstruct()
    qualify(tool)
    register()
    cleanup()
    print("Pelagos Governance Layer v0.3.0 materialized and qualified")


if __name__ == "__main__":
    main()
