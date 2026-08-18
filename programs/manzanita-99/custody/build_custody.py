#!/usr/bin/env python3
"""Build a deterministic manifest over repo-resident Manzanita custody sources."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

CONTRACT_SCHEMA = "axm-tools/manzanita-donor-custody-contract@2"
REGISTER_SCHEMA = "axm-tools/manzanita-donor-register@2"
MANIFEST_SCHEMA = "axm-tools/manzanita-custody-manifest@2"
DEFAULT_ROOT = Path.cwd()
DEFAULT_DIR = Path(__file__).resolve().parent


class CustodyBuildError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CustodyBuildError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CustodyBuildError(f"Invalid JSON in {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value, raw


def clean_relative(value: str) -> str:
    path = PurePosixPath(value)
    require(value not in {"", "."} and not path.is_absolute() and ".." not in path.parts, f"Unsafe path: {value!r}")
    return path.as_posix()


def resolve_repo_path(repo_root: Path, value: str) -> Path:
    clean = clean_relative(value)
    unresolved = repo_root / clean
    require(
        unresolved.exists() or unresolved.is_symlink(),
        f"Archive path is missing: {value}",
    )
    require(
        not unresolved.is_symlink(),
        f"Archive path may not be a symbolic link: {value}",
    )
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise CustodyBuildError(f"Path escapes repository: {value}") from exc
    return candidate


def match_any(relative_to_scope: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    if "**" in patterns:
        return True
    return any(fnmatch.fnmatch(relative_to_scope, pattern) for pattern in patterns)


def excluded(relative_to_scope: str, repo_relative: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(relative_to_scope, pattern)
        or fnmatch.fnmatch(repo_relative, pattern)
        for pattern in patterns
    )


def iter_scope_files(repo_root: Path, scope: dict[str, Any], output_path: Path) -> Iterable[Path]:
    target = resolve_repo_path(repo_root, str(scope.get("path", "")))
    require(target.exists(), f"Archive scope does not exist: {scope.get('id')}")
    candidates = [target] if target.is_file() else sorted(target.rglob("*"))
    scope_root = target if target.is_dir() else target.parent
    output_resolved = output_path.resolve()
    for candidate in candidates:
        require(
            not candidate.is_symlink(),
            f"Custody source may not be a symbolic link: {candidate}",
        )
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved == output_resolved:
            continue
        if "__pycache__" in candidate.parts or candidate.suffix == ".pyc":
            continue
        repo_relative = resolved.relative_to(repo_root).as_posix()
        relative_to_scope = resolved.relative_to(scope_root).as_posix()
        if target.is_file():
            relative_to_scope = target.name
        if not match_any(relative_to_scope, list(scope.get("include", []))):
            continue
        if excluded(relative_to_scope, repo_relative, list(scope.get("exclude", []))):
            continue
        yield candidate


def git_identity(repo_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, args in (
        ("commit", ["rev-parse", "HEAD"]),
        ("tree", ["rev-parse", "HEAD^{tree}"]),
    ):
        process = subprocess.run(["git", "-C", str(repo_root), *args], check=False, capture_output=True, text=True)
        value = process.stdout.strip()
        result[key] = value if process.returncode == 0 and len(value) == 40 else "WORKTREE"
    return result


def build_manifest(repo_root: Path, contract_path: Path, register_path: Path, observed_path: Path, output_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract, contract_raw = load_json(contract_path)
    register, register_raw = load_json(register_path)
    observed, observed_raw = load_json(observed_path)
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected custody contract schema")
    require(register.get("schema") == REGISTER_SCHEMA, "Unexpected donor register schema")
    require(register.get("contract_id") == contract.get("contract_id"), "Contract identity drifted")
    require(observed.get("schema") == "axm-tools/manzanita-observed-execution-ledger@1", "Unexpected observed ledger schema")

    files: dict[str, dict[str, Any]] = {}
    scopes: list[dict[str, Any]] = []
    seen_scope_ids: set[str] = set()
    for scope in contract.get("archive_scopes", []):
        scope_id = scope.get("id")
        require(isinstance(scope_id, str) and scope_id, "Archive scope lacks id")
        require(scope_id not in seen_scope_ids, f"Duplicate archive scope: {scope_id}")
        seen_scope_ids.add(scope_id)
        scoped: list[str] = []
        for path in iter_scope_files(repo_root, scope, output_path):
            relative = path.resolve().relative_to(repo_root).as_posix()
            payload = path.read_bytes()
            row = files.setdefault(relative, {
                "path": relative,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_blob_sha1": git_blob_sha1(payload),
                "scopes": [],
            })
            require(row["sha256"] == sha256_bytes(payload), f"File changed while building: {relative}")
            row["scopes"].append(scope_id)
            scoped.append(relative)
        require(not scope.get("required") or scoped, f"Required scope is empty: {scope_id}")
        material = "".join(f"{path}\0{files[path]['sha256']}\0{files[path]['bytes']}\n" for path in sorted(scoped)).encode("utf-8")
        scopes.append({
            "id": scope_id,
            "class": scope.get("class"),
            "path": clean_relative(str(scope.get("path"))),
            "file_count": len(scoped),
            "bytes": sum(files[path]["bytes"] for path in scoped),
            "sha256": sha256_bytes(material),
            "required": bool(scope.get("required")),
        })

    file_rows = []
    for path in sorted(files):
        row = files[path]
        row["scopes"] = sorted(set(row["scopes"]))
        file_rows.append(row)

    open_gaps = sorted(
        row["id"]
        for row in register.get("gaps", [])
        if row.get("required_for_close") and row.get("state") != "closed"
    )
    status = "COMPLETE" if not open_gaps else "PARTIAL"
    identity = git_identity(repo_root)
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "contract_id": contract["contract_id"],
        "status": status,
        "task_state": register.get("state"),
        "generated_from": {
            "git_commit": identity["commit"],
            "git_tree": identity["tree"],
            "contract_path": contract_path.resolve().relative_to(repo_root).as_posix(),
            "contract_sha256": sha256_bytes(contract_raw),
            "register_path": register_path.resolve().relative_to(repo_root).as_posix(),
            "register_sha256": sha256_bytes(register_raw),
            "observed_ledger_path": observed_path.resolve().relative_to(repo_root).as_posix(),
            "observed_ledger_sha256": sha256_bytes(observed_raw),
        },
        "scope_count": len(scopes),
        "source_file_count": len(file_rows),
        "source_bytes": sum(row["bytes"] for row in file_rows),
        "scopes": sorted(scopes, key=lambda row: row["id"]),
        "files": file_rows,
        "donor_anchors": [
            {
                "id": row.get("id"),
                "class": row.get("class"),
                "custody_state": row.get("custody_state"),
                "anchors": row.get("anchors", {}),
            }
            for row in sorted(register.get("donors", []), key=lambda row: row.get("id", ""))
        ],
        "open_required_gaps": open_gaps,
        "canonical_task_count_effect": "none",
        "qualification_boundary": contract.get("qualification_boundary"),
    }
    manifest["payload_sha256"] = sha256_bytes(canonical_bytes(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_DIR / "CUSTODY_CONTRACT.json")
    parser.add_argument("--register", type=Path, default=DEFAULT_DIR / "DONOR_REGISTER.json")
    parser.add_argument("--observed-ledger", type=Path, default=DEFAULT_DIR / "OBSERVED_EXECUTION_LEDGER.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "CUSTODY_MANIFEST.json")
    args = parser.parse_args()
    manifest = build_manifest(args.repo_root, args.contract, args.register, args.observed_ledger, args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": "PASS",
        "custody_status": manifest["status"],
        "source_file_count": manifest["source_file_count"],
        "source_bytes": manifest["source_bytes"],
        "open_required_gaps": len(manifest["open_required_gaps"]),
        "manifest_sha256": manifest["payload_sha256"],
        "canonical_task_count_effect": manifest["canonical_task_count_effect"],
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except CustodyBuildError as exc:
        raise SystemExit(str(exc)) from exc
