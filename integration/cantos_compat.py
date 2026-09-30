"""Stage byte-preserving routes removed by the Second Run move to Cantos.

Historical non-HTML routes are copied byte-for-byte from Git commit
``cd8817dfcdbd45a3323283bd2f27cc610b253ca8``. HTML routes redirect to the
same path in Cantos. The destination Git tree is checked before any write.

This is a publication staging operation, not a source restore: it writes only
missing historical paths plus the seven known root index aliases. It never
adds, commits, or pushes files.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SOURCE_COMMIT = "cd8817dfcdbd45a3323283bd2f27cc610b253ca8"
CANTOS_OWNER_REPO = "BigBirdReturns/cantos"
CANTOS_BASE = "https://bigbirdreturns.github.io/cantos/"
ROOTS = (
    "hot-aisle",
    "clustermax-challenge",
    "research-desk",
    "compute",
    "shelf",
    "circulate",
    "floor",
)
ROOT_ALIASES = tuple(f"{root}/index.html" for root in ROOTS)
PUBLISHERS = (
    "pta-fetch.yml",
    "organ-evolution-observe.yml",
    "axm-witness-0.9.2.yml",
    "axm-witness-live-readback-0.9.2.yml",
)
API = "https://api.github.com/repos/" + CANTOS_OWNER_REPO


class CompatError(RuntimeError):
    """A compatibility route cannot be staged without risking bad output."""


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: str
    kind: str
    sha: str
    size: int


@dataclass(frozen=True)
class DestinationSnapshot:
    commit: str
    tree_sha: str
    entries: dict[str, TreeEntry]
    source: str


def _git(repo: Path, *args: str, binary: bool = False):
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def _tree(repo: Path, ref: str, roots: Iterable[str]) -> dict[str, TreeEntry]:
    raw = _git(repo, "ls-tree", "-r", "-z", "-l", ref, "--", *roots, binary=True)
    result: dict[str, TreeEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise CompatError("Could not parse a Git tree entry.")
        fields = metadata.decode("ascii").split()
        if len(fields) != 4:
            raise CompatError("Could not parse Git tree metadata.")
        mode, kind, sha, raw_size = fields
        path = raw_path.decode("utf-8", "surrogateescape")
        validate_path(path)
        if raw_size == "-":
            continue
        result[path] = TreeEntry(path, mode, kind, sha, int(raw_size))
    return result


def validate_path(path: str) -> tuple[str, ...]:
    """Return safe path components, rejecting Git names unsafe for Pages output."""
    if not path or "\x00" in path or "\\" in path or path.startswith("/"):
        raise CompatError(f"Unsafe migration path: {path!r}")
    parts = tuple(path.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        raise CompatError(f"Unsafe migration path: {path!r}")
    if PurePosixPath(path).is_absolute() or re.match(r"^[A-Za-z]:", path):
        raise CompatError(f"Unsafe migration path: {path!r}")
    if not any(path.startswith(root + "/") for root in ROOTS):
        raise CompatError(f"Path is outside the seven migrated roots: {path!r}")
    return parts


def _parse_tree_response(body: dict, commit: str, source: str) -> DestinationSnapshot:
    if body.get("truncated"):
        raise CompatError("Cantos destination tree response was truncated.")
    entries: dict[str, TreeEntry] = {}
    for item in body.get("tree", []):
        path = item.get("path", "")
        if not any(path.startswith(root + "/") for root in ROOTS):
            continue
        validate_path(path)
        if item.get("type") == "blob":
            entries[path] = TreeEntry(
                path=path,
                mode=item.get("mode", "100644"),
                kind="blob",
                sha=item["sha"],
                size=int(item.get("size", 0)),
            )
    return DestinationSnapshot(commit, body.get("sha", ""), entries, source)


def destination_from_local_repo(cantos_repo: Path) -> DestinationSnapshot:
    if cantos_repo.is_symlink():
        raise CompatError("Refusing a symlink Cantos checkout path.")
    repo = cantos_repo.resolve(strict=True)
    commit = _git(repo, "rev-parse", "HEAD")
    remote = _git(repo, "config", "--get", "remote.origin.url")
    if "BigBirdReturns/cantos" not in remote:
        raise CompatError("--cantos-repo is not the BigBirdReturns/cantos checkout.")
    entries = _tree(repo, "HEAD", ROOTS)
    tree_sha = _git(repo, "rev-parse", "HEAD^{tree}")
    return DestinationSnapshot(commit, tree_sha, entries, "local Git tree at HEAD")


def destination_from_github() -> DestinationSnapshot:
    """Read Cantos main from GitHub's source API; never contacts GitHub Pages."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    def get(url: str) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "axm-tools-cantos-compat",
        }
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CompatError(f"Could not verify the Cantos source tree: {exc}") from exc

    commit_data = get(API + "/commits/main")
    commit = commit_data["sha"]
    tree_sha = commit_data["commit"]["tree"]["sha"]
    body = get(API + "/git/trees/" + tree_sha + "?recursive=1")
    return _parse_tree_response(body, commit, "GitHub source API main tree")


def redirect_document(path: str) -> bytes:
    """Make a standalone redirect that preserves the browser query and fragment."""
    validate_path(path)
    if path in ROOT_ALIASES:
        route = path.removesuffix("/index.html") + "/"
    else:
        route = path
    url = CANTOS_BASE + quote(route, safe="/!$&'()*+,;=:@-._~")
    escaped_url = html.escape(url, quote=True)
    script_url = json.dumps(url, ensure_ascii=True)
    page = (
        "<!doctype html>\n"
        "<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Moved to Cantos</title>\n"
        f"<link rel=\"canonical\" href=\"{escaped_url}\">\n"
        f"<meta http-equiv=\"refresh\" content=\"0; url={escaped_url}\">\n"
        f"<script>location.replace({script_url} + window.location.search + window.location.hash);</script>\n"
        "</head><body>\n"
        "<p>This page moved to Cantos. If you are not redirected, open "
        f"<a href=\"{escaped_url}\">{html.escape(url)}</a>.</p>\n"
        "</body></html>\n"
    )
    return page.encode("utf-8")


def _same_file(path: Path, expected_sha256: str) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def _resolve_output(root: Path, components: tuple[str, ...]) -> Path:
    root = root.resolve(strict=True)
    cursor = root
    for part in components[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise CompatError(f"Refusing symlink directory in output path: {cursor}")
        if cursor.exists() and not cursor.is_dir():
            raise CompatError(f"Output parent is not a directory: {cursor}")
    target = cursor / components[-1]
    if target.is_symlink():
        raise CompatError(f"Refusing symlink output path: {target}")
    return target


def _ensure_output_root(root: Path) -> Path:
    if root.exists() and root.is_symlink():
        raise CompatError(f"Refusing symlink output root: {root}")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve(strict=True)


def _known_existing_root_alias(path: Path, route: str) -> bool:
    """Permit replacing only the six historical Cantos aliases (not user pages)."""
    try:
        data = path.read_bytes()
    except OSError:
        return False
    canonical_target = CANTOS_BASE + route.removesuffix("/index.html") + "/"
    explicit_index_target = CANTOS_BASE + route
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return (
        "Moved to Cantos" in text
        and (canonical_target in text or explicit_index_target in text)
    )


def _install_root_alias(target: Path, route: str) -> tuple[bool, str]:
    expected = redirect_document(route)
    expected_sha = hashlib.sha256(expected).hexdigest()
    if target.exists():
        if _same_file(target, expected_sha):
            return False, expected_sha
        if not _known_existing_root_alias(target, route):
            raise CompatError(f"Refusing to overwrite non-owned root alias: {target}")
        if target.is_symlink() or not _known_existing_root_alias(target, route):
            raise CompatError(f"Refusing to replace changed root alias: {target}")
        with target.open("wb") as stream:
            stream.write(expected)
        return True, expected_sha
    return _write_bytes(target, expected)


def _write_bytes(target: Path, payload: bytes) -> tuple[bool, str]:
    expected = hashlib.sha256(payload).hexdigest()
    if target.exists():
        if _same_file(target, expected):
            return False, expected
        raise CompatError(f"Refusing to overwrite an existing path: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Recheck after directory creation in case an unexpected link appeared.
    if target.is_symlink() or target.exists():
        if target.exists() and _same_file(target, expected):
            return False, expected
        raise CompatError(f"Refusing to overwrite an existing path: {target}")
    try:
        with target.open("xb") as output:
            output.write(payload)
    except FileExistsError as exc:
        if _same_file(target, expected):
            return False, expected
        raise CompatError(f"Refusing to overwrite an existing path: {target}") from exc
    return True, expected


def _copy_historical_blob(repo: Path, entry: TreeEntry, target: Path) -> tuple[bool, str, str]:
    if target.exists():
        if not target.is_file() or target.is_symlink():
            raise CompatError(f"Refusing non-file output path: {target}")
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        size = target.stat().st_size
        sha1.update(f"blob {size}\0".encode("ascii"))
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha1.update(chunk)
                sha256.update(chunk)
        if size == entry.size and sha1.hexdigest() == entry.sha:
            return False, entry.sha, sha256.hexdigest()
        raise CompatError(f"Refusing to overwrite an existing path: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        return _copy_historical_blob(repo, entry, target)

    process = subprocess.Popen(
        ["git", "cat-file", "blob", entry.sha], cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    git_hash = hashlib.sha1()
    sha256 = hashlib.sha256()
    git_hash.update(f"blob {entry.size}\0".encode("ascii"))
    size = 0
    created = False
    try:
        with target.open("xb") as output:
            created = True
            while True:
                chunk = process.stdout.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                git_hash.update(chunk)
                sha256.update(chunk)
                output.write(chunk)
        stderr = process.communicate()[1]
        if process.returncode != 0:
            raise CompatError("git cat-file failed: " + stderr.decode("utf-8", "replace"))
        if size != entry.size or git_hash.hexdigest() != entry.sha:
            raise CompatError(f"Historical blob verification failed for {entry.path}.")
    except Exception:
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    return True, entry.sha, sha256.hexdigest()


def _write_manifest(path: Path, payload: dict) -> None:
    # Keep the manifest byte-stable across a first stage and an idempotent
    # rerun. Per-invocation new/already-written counts remain in stdout only.
    stable = {
        key: value for key, value in payload.items()
        if key not in ("newly_written_path_count", "already_staged_path_count")
    }
    encoded = (json.dumps(stable, indent=2, sort_keys=True) + "\n").encode("utf-8")
    expected = hashlib.sha256(encoded).hexdigest()
    if path.exists():
        if _same_file(path, expected):
            return
        raise CompatError(f"Refusing to overwrite manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(encoded)
    except FileExistsError as exc:
        if _same_file(path, expected):
            return
        raise CompatError(f"Refusing to overwrite manifest: {path}") from exc


def stage_compat(
    repo: Path,
    output: Path,
    source_commit: str,
    destination: DestinationSnapshot,
    manifest_path: Path | None = None,
) -> dict:
    """Verify the historical mapping, then stage only eligible paths."""
    if repo.is_symlink():
        raise CompatError("Refusing a symlink source checkout path.")
    repo = repo.resolve(strict=True)
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise CompatError("Source must be a full Git commit SHA.")
    _git(repo, "cat-file", "-e", source_commit + "^{commit}")
    old = _tree(repo, source_commit, ROOTS)
    live = _tree(repo, "HEAD", ROOTS)
    old_tree = _git(repo, "rev-parse", source_commit + "^{tree}")
    current_commit = _git(repo, "rev-parse", "HEAD")
    current_tree = _git(repo, "rev-parse", "HEAD^{tree}")

    for path, entry in old.items():
        if entry.kind != "blob":
            raise CompatError(f"Historical route is not a file: {path}")
        if entry.mode == "120000":
            raise CompatError(f"Historical route is a symlink and cannot be frozen: {path}")
        if path not in destination.entries:
            raise CompatError(f"Cantos destination is missing historical route: {path}")
        if destination.entries[path].mode == "120000":
            raise CompatError(f"Cantos destination route is a symlink: {path}")
    for path in ROOT_ALIASES:
        if path not in old:
            raise CompatError(f"Historical root page is missing: {path}")
        if path not in destination.entries:
            raise CompatError(f"Cantos root page is missing: {path}")

    out_root = _ensure_output_root(output)
    staged = 0
    unchanged = 0
    redirects = 0
    frozen_copies = 0
    manifest_entries: list[dict] = []
    for path in sorted(old):
        entry = old[path]
        is_root_alias = path in ROOT_ALIASES
        removed_from_live = path not in live
        should_stage = is_root_alias or removed_from_live
        kind = "redirect" if path.lower().endswith(".html") else "frozen-legacy-copy"
        target_entry = destination.entries[path]
        record = {
            "path": path,
            "historical_blob_sha": entry.sha,
            "historical_size": entry.size,
            "destination_path": path,
            "destination_blob_sha_at_verification": target_entry.sha,
            "destination_size_at_verification": target_entry.size,
            "route_kind": kind,
            "removed_from_current_source_tree": removed_from_live,
            "staged": False,
        }
        if should_stage:
            components = validate_path(path)
            target = _resolve_output(out_root, components)
            if is_root_alias and target.exists():
                # Replace only the seven known root aliases. Never touch a
                # nested page or any other pre-existing path.
                changed, stage_sha = _install_root_alias(target, path)
                redirects += 1
                record.update(staged=True, staged_sha256=stage_sha)
                if changed:
                    staged += 1
                else:
                    unchanged += 1
            elif kind == "redirect":
                changed, stage_sha = _write_bytes(target, redirect_document(path))
                redirects += 1
                record.update(staged=True, staged_sha256=stage_sha)
                if changed:
                    staged += 1
                else:
                    unchanged += 1
            else:
                changed, source_sha, stage_sha = _copy_historical_blob(repo, entry, target)
                frozen_copies += 1
                record.update(staged=True, staged_blob_sha=source_sha, staged_sha256=stage_sha)
                if changed:
                    staged += 1
                else:
                    unchanged += 1
        manifest_entries.append(record)

    result = {
        "schema": "axm-tools/cantos-compat-manifest@1",
        "source_commit": source_commit,
        "source_tree_sha": old_tree,
        "deployment_commit": current_commit,
        "deployment_tree_sha": current_tree,
        "destination_repository": CANTOS_OWNER_REPO,
        "destination_commit": destination.commit,
        "destination_tree_sha": destination.tree_sha,
        "destination_verified_against": destination.source,
        "destination_verification_scope": "Git path and blob identity existence only; no content equivalence is claimed.",
        "roots": list(ROOTS),
        "historical_route_count": len(old),
        "staged_path_count": sum(1 for item in manifest_entries if item["staged"]),
        "newly_written_path_count": staged,
        "already_staged_path_count": unchanged,
        "redirect_count": redirects,
        "frozen_legacy_copy_count": frozen_copies,
        "routes": manifest_entries,
    }
    if manifest_path:
        _write_manifest(manifest_path, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage", help="verify and stage legacy routes for Pages")
    stage.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    stage.add_argument("--out", type=Path, help="output root; defaults to the repository root")
    stage.add_argument("--source-commit", default=SOURCE_COMMIT)
    stage.add_argument("--cantos-repo", type=Path, help="verify against a local Cantos checkout")
    stage.add_argument("--manifest-out", type=Path, help="write the verified route manifest to a new file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repo = args.repo.resolve(strict=True)
        destination = (
            destination_from_local_repo(args.cantos_repo)
            if args.cantos_repo
            else destination_from_github()
        )
        output = args.out or repo
        result = stage_compat(repo, output, args.source_commit, destination, args.manifest_out)
        print(json.dumps({key: value for key, value in result.items() if key != "routes"}, indent=2))
        return 0
    except (CompatError, OSError, subprocess.CalledProcessError) as exc:
        print(f"CANTOS COMPATIBILITY STAGING HELD: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
