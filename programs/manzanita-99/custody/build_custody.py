#!/usr/bin/env python3
"""Build a deterministic custody manifest for repo-resident Manzanita donors."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SCHEMA = "axm-tools/manzanita-99-custody-manifest@1"
REGISTER_SCHEMA = "axm-tools/manzanita-99-donor-register@1"
DEFAULT_REGISTER = Path(__file__).with_name("DONOR_REGISTER.json")
DEFAULT_OUTPUT = Path(__file__).with_name("CUSTODY_MANIFEST.json")


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def clean_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value in {"", "."}:
        fail(f"Unsafe repository-relative path: {value!r}")
    return path.as_posix()


def read_register(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Invalid donor register JSON: {exc}")
    if data.get("schema") != REGISTER_SCHEMA:
        fail(f"Unexpected donor register schema: {data.get('schema')!r}")
    if data.get("task") != "JDB99-001":
        fail("Donor register must govern JDB99-001")
    return data, raw


def resolve_repo_path(repo_root: Path, relative: str) -> Path:
    clean = clean_relative_path(relative)
    candidate = (repo_root / clean).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        fail(f"Path escapes repository root: {relative}")
    return candidate


def is_excluded(relative: str, excludes: set[str]) -> bool:
    for excluded in excludes:
        if relative == excluded or relative.startswith(excluded.rstrip("/") + "/"):
            return True
    return False


def iter_scope_files(
    repo_root: Path,
    scope_path: str,
    excludes: Iterable[str],
    output_path: Path,
) -> Iterable[Path]:
    target = resolve_repo_path(repo_root, scope_path)
    if not target.exists():
        fail(f"Registered archive scope does not exist: {scope_path}")

    clean_excludes = {clean_relative_path(item) for item in excludes}
    try:
        output_relative = output_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        output_relative = None

    candidates = [target] if target.is_file() else sorted(target.rglob("*"))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        relative = candidate.resolve().relative_to(repo_root).as_posix()
        if output_relative and relative == output_relative:
            continue
        if "__pycache__" in candidate.parts or candidate.suffix == ".pyc":
            continue
        if is_excluded(relative, clean_excludes):
            continue
        yield candidate


def current_commit(repo_root: Path, override: str | None) -> str:
    if override:
        return override
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if result.returncode == 0 and len(value) == 40:
        return value
    return "WORKTREE"


def build_manifest(
    repo_root: Path,
    register_path: Path,
    output_path: Path,
    git_commit: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    register_path = register_path.resolve()
    output_path = output_path.resolve()
    register, register_raw = read_register(register_path)

    files: dict[str, dict[str, Any]] = {}
    scope_rows: list[dict[str, Any]] = []
    seen_scope_ids: set[str] = set()

    for scope in register.get("archive_scopes", []):
        scope_id = scope.get("id")
        if not isinstance(scope_id, str) or not scope_id:
            fail("Every archive scope needs a non-empty id")
        if scope_id in seen_scope_ids:
            fail(f"Duplicate archive scope id: {scope_id}")
        seen_scope_ids.add(scope_id)

        scoped_paths: list[str] = []
        scoped_bytes = 0
        for file_path in iter_scope_files(
            repo_root,
            scope.get("path", ""),
            scope.get("exclude", []),
            output_path,
        ):
            relative = file_path.resolve().relative_to(repo_root).as_posix()
            payload = file_path.read_bytes()
            row = files.setdefault(
                relative,
                {
                    "path": relative,
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                    "git_blob_sha1": git_blob_sha1(payload),
                    "scopes": [],
                },
            )
            if row["bytes"] != len(payload) or row["sha256"] != sha256_bytes(payload):
                fail(f"File changed while manifest was being built: {relative}")
            row["scopes"].append(scope_id)
            scoped_paths.append(relative)
            scoped_bytes += len(payload)

        if scope.get("required") and not scoped_paths:
            fail(f"Required archive scope is empty: {scope_id}")

        digest_material = "".join(
            f"{path}\0{files[path]['sha256']}\0{files[path]['bytes']}\n"
            for path in sorted(scoped_paths)
        ).encode("utf-8")
        scope_rows.append(
            {
                "id": scope_id,
                "class": scope.get("class"),
                "path": clean_relative_path(scope.get("path", "")),
                "required": bool(scope.get("required")),
                "file_count": len(scoped_paths),
                "bytes": scoped_bytes,
                "sha256": sha256_bytes(digest_material),
            }
        )

    file_rows = []
    for path in sorted(files):
        row = files[path]
        row["scopes"] = sorted(set(row["scopes"]))
        file_rows.append(row)

    open_required_gaps = sorted(
        gap["id"]
        for gap in register.get("gaps", [])
        if gap.get("required_for_close") and gap.get("state") != "closed"
    )
    status = "COMPLETE" if not open_required_gaps else "PARTIAL"

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "task": "JDB99-001",
        "task_state": register.get("state"),
        "status": status,
        "generated_from": {
            "git_commit": current_commit(repo_root, git_commit),
            "register_path": register_path.relative_to(repo_root).as_posix(),
            "register_sha256": sha256_bytes(register_raw),
        },
        "scope_count": len(scope_rows),
        "source_file_count": len(file_rows),
        "source_bytes": sum(row["bytes"] for row in file_rows),
        "scopes": sorted(scope_rows, key=lambda row: row["id"]),
        "files": file_rows,
        "donor_anchors": [
            {
                "id": donor.get("id"),
                "class": donor.get("class"),
                "custody_state": donor.get("custody_state"),
                "anchors": donor.get("anchors", {}),
            }
            for donor in sorted(register.get("donors", []), key=lambda row: row.get("id", ""))
        ],
        "open_required_gaps": open_required_gaps,
        "qualification_boundary": register.get("qualification_boundary"),
    }
    manifest["payload_sha256"] = sha256_bytes(canonical_bytes(manifest))
    return manifest


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--git-commit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(
        args.repo_root,
        args.register,
        args.output,
        args.git_commit,
    )
    write_manifest(manifest, args.output)
    print(
        json.dumps(
            {
                "result": "PASS",
                "task": manifest["task"],
                "task_state": manifest["task_state"],
                "custody_status": manifest["status"],
                "files": manifest["source_file_count"],
                "bytes": manifest["source_bytes"],
                "open_required_gaps": len(manifest["open_required_gaps"]),
                "manifest_sha256": manifest["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
