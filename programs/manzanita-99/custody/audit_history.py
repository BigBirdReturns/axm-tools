#!/usr/bin/env python3
"""Audit reachable Manzanita history without promoting reachable commits into releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "axm-tools/manzanita-history-audit@1"


class HistoryAuditError(ValueError):
    pass


def run(repo_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(repo_root), *args], check=False, capture_output=True, text=True, errors="replace")
    if check and result.returncode:
        raise HistoryAuditError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def audit(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    run(repo_root, "rev-parse", "--git-dir")
    commits = [line for line in run(repo_root, "log", "--all", "--format=%H", "--", "manzanita", "manzanita-next").splitlines() if line]
    unique_commits = []
    seen = set()
    for commit in commits:
        if commit not in seen:
            seen.add(commit)
            unique_commits.append(commit)
    route_trees = []
    seen_route_trees = set()
    for commit in unique_commits:
        tree = run(repo_root, "rev-parse", f"{commit}:manzanita", check=False).strip()
        if len(tree) != 40 or tree in seen_route_trees:
            continue
        seen_route_trees.add(tree)
        subject = run(repo_root, "show", "-s", "--format=%s", commit).strip()
        route_trees.append({"first_observed_commit": commit, "tree": tree, "subject": subject})
    tags = sorted(line for line in run(repo_root, "tag", "--list").splitlines() if "manzanita" in line.lower())
    branches = sorted(line.strip() for line in run(repo_root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes").splitlines() if "manzanita" in line.lower())
    audit: dict[str, Any] = {
        "schema": SCHEMA,
        "repository_head": run(repo_root, "rev-parse", "HEAD").strip(),
        "reachable_commit_count": len(unique_commits),
        "unique_historical_public_route_tree_count": len(route_trees),
        "historical_public_route_trees": route_trees,
        "manzanita_tags": tags,
        "manzanita_branch_refs": branches,
        "classification_boundary": "A reachable commit or unique tree is a custody candidate, not automatically an approved release, deployed artifact, visual golden, or public byte set.",
        "canonical_task_count_effect": "none",
    }
    audit["payload_sha256"] = sha256_bytes(canonical_bytes(audit))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.repo_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "reachable_commits": value["reachable_commit_count"], "unique_public_route_trees": value["unique_historical_public_route_tree_count"], "payload_sha256": value["payload_sha256"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except HistoryAuditError as exc:
        raise SystemExit(str(exc)) from exc
