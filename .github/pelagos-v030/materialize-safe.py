from __future__ import annotations

import base64
import hashlib
import importlib.util
import pathlib
import re
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


def harden_csp_styles(release: pathlib.Path) -> None:
    """Move static HTML style attributes into the self-hosted stylesheet.

    The runtime CSP deliberately keeps ``style-src 'self'`` and does not grant
    ``unsafe-inline``. The staged source used a handful of static style
    attributes inside HTML template strings. Those are presentation only, so
    translate them deterministically into data attributes backed by app.css.
    Dynamic style expressions are refused rather than guessed.
    """

    targets = [release / "index.html", *sorted((release / "app").glob("*.js"))]
    double = re.compile(r'\sstyle="([^"]*)"')
    single = re.compile(r"\sstyle='([^']*)'")
    rules: dict[str, str] = {}

    def replacement(match: re.Match[str]) -> str:
        declaration = match.group(1).strip()
        if not declaration:
            return ""
        if "${" in declaration or "`" in declaration:
            raise SystemExit(f"dynamic inline style refused: {declaration}")
        key = "csp-" + hashlib.sha256(declaration.encode("utf-8")).hexdigest()[:12]
        prior = rules.get(key)
        if prior is not None and prior != declaration:
            raise SystemExit(f"CSP style digest collision for {key}")
        rules[key] = declaration
        return f' data-csp-style="{key}"'

    for path in targets:
        text = path.read_text(encoding="utf-8")
        text = double.sub(replacement, text)
        text = single.sub(replacement, text)
        if re.search(r"\sstyle\s*=", text, flags=re.IGNORECASE):
            raise SystemExit(f"unconverted inline style remains in {path.relative_to(release)}")
        path.write_text(text, encoding="utf-8")

    stylesheet = release / "app.css"
    css = stylesheet.read_text(encoding="utf-8").rstrip()
    if rules:
        css += "\n\n/* CSP-hardening: generated from static release presentation attributes. */\n"
        for key, declaration in sorted(rules.items()):
            css += f'[data-csp-style="{key}"]{{{declaration}}}\n'
        stylesheet.write_text(css, encoding="utf-8")

    print(f"CSP style hardening: {len(rules)} unique static declarations externalized")


def stage_reviewed_workflow_candidate(release: pathlib.Path) -> None:
    """Keep CI from granting itself workflow authority.

    register() writes the proposed long-lived qualification workflow. GitHub
    correctly refuses a normal Actions token that tries to install workflow
    authority. Move that exact reviewed YAML into the release as a candidate;
    the repository authority installs it separately after the bytes qualify.
    """

    generated = ROOT / ".github" / "workflows" / "pelagos-governance-check.yml"
    candidate_dir = release / "workflow-candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "pelagos-governance-check.yml"
    if not generated.exists():
        raise SystemExit("register() did not produce the expected qualification workflow candidate")
    shutil.move(str(generated), str(candidate))
    print("qualification workflow staged for separate repository-authority installation")


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

harden_csp_styles(release)
materializer.qualify(release)
materializer.register()
stage_reviewed_workflow_candidate(release)
# Deliberately do not call materializer.cleanup() here. CI owns release-byte
# generation only; repository authority cleans bootstrap and installs the
# long-lived workflow after the qualified bytes are committed.
print("Pelagos Governance Layer v0.3.0 safely materialized and qualified")
