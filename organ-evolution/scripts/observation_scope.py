#!/usr/bin/env python3
"""Scoped repository observation for organs sharing one implementation repository.

The scope declaration narrows files and workflow receipts only. Repository identity,
head, license, open pull requests, tags, and source failures remain visible. A scope
cannot make an observed result authoritative or hide an undeclared required workflow.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

WORKFLOW_SCOPES = {"all", "declared_only"}
SUCCESSION_NAMES = {
    "CONTINUITY.MD",
    "AGENTS.MD",
    "CLAUDE.MD",
    "MAINTAINERS.MD",
    "CONTRIBUTING.MD",
}


class ObservationScopeError(ValueError):
    pass


def normalize_scope(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ObservationScopeError("scopePath must be a string")
    cleaned = value.replace("\\", "/").strip().strip("/")
    if not cleaned:
        return None
    parts = PurePosixPath(cleaned).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ObservationScopeError(f"scopePath is not a bounded relative path: {value!r}")
    return "/".join(parts)


def validate_repository_scope(repository: dict[str, Any]) -> tuple[str | None, str]:
    scope = normalize_scope(repository.get("scopePath"))
    workflow_scope = repository.get("workflowScope", "all")
    if workflow_scope not in WORKFLOW_SCOPES:
        raise ObservationScopeError(
            f"workflowScope must be one of {sorted(WORKFLOW_SCOPES)}"
        )
    declarations = ((repository.get("workflowPolicy") or {}).get("declarations") or [])
    if workflow_scope == "declared_only" and not declarations:
        raise ObservationScopeError(
            "declared_only workflow scope requires at least one workflow declaration"
        )
    return scope, workflow_scope


def mapping_identity(full_name: str, scope_path: str | None) -> str:
    return f"{full_name}#{scope_path or '/'}"


def declaration_names(policy: dict[str, Any] | None) -> set[str]:
    names: set[str] = set()
    for row in (policy or {}).get("declarations", []):
        names.add(str(row["matchName"]))
        names.update(str(alias) for alias in row.get("aliases") or [])
    return names


def select_workflows(
    workflows: list[dict[str, Any]],
    policy: dict[str, Any] | None,
    mode: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if mode == "all":
        return workflows, {
            "mode": "all",
            "observedCount": len(workflows),
            "includedCount": len(workflows),
            "omittedCount": 0,
        }
    names = declaration_names(policy)
    included = [row for row in workflows if str(row.get("name")) in names]
    return included, {
        "mode": "declared_only",
        "observedCount": len(workflows),
        "includedCount": len(included),
        "omittedCount": len(workflows) - len(included),
        "declaredNames": sorted(names),
        "basis": (
            "Only exact human-declared workflow names are projected into this sub-organ. "
            "The omitted count remains visible and the parent organ may observe the whole repository."
        ),
    }


def scope_paths(raw_tree: dict[str, Any], scope_path: str | None) -> tuple[set[str], set[str]]:
    rows = raw_tree.get("tree", []) if isinstance(raw_tree, dict) else []
    all_paths = {
        str(row.get("path"))
        for row in rows
        if isinstance(row, dict) and row.get("type") == "blob" and row.get("path")
    }
    if not scope_path:
        return all_paths, all_paths
    prefix = scope_path.rstrip("/") + "/"
    scoped = {path[len(prefix):] for path in all_paths if path.startswith(prefix)}
    return all_paths, scoped


def scoped_tree_signals(
    raw_tree: dict[str, Any],
    scope_path: str | None,
    workflow_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    all_paths, scoped = scope_paths(raw_tree, scope_path)
    upper = {path.upper(): path for path in scoped}
    has_readme = any(path == "README" or path.startswith("README.") for path in upper)
    has_license = any(
        path == "LICENSE" or path.startswith("LICENSE.") or path == "COPYING"
        for path in upper
    )
    succession = sorted(path for path in scoped if path.upper() in SUCCESSION_NAMES)
    all_workflows = sorted(
        path
        for path in all_paths
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    )
    return {
        "scopePath": scope_path,
        "scopedFileCount": len(scoped),
        "readme": has_readme,
        "license": has_license,
        "successionFiles": succession,
        "workflowFiles": all_workflows,
        "declaredWorkflowNames": sorted(declaration_names(workflow_policy)),
        "treeTruncated": bool(raw_tree.get("truncated")),
    }


def required_workflow_gaps(
    policy: dict[str, Any] | None,
    workflows: list[dict[str, Any]],
    full_name: str,
    scope_path: str | None,
) -> list[dict[str, Any]]:
    observed = {str(row.get("name")) for row in workflows}
    findings: list[dict[str, Any]] = []
    for declaration in (policy or {}).get("declarations", []):
        names = {str(declaration["matchName"]), *(str(x) for x in declaration.get("aliases") or [])}
        if (
            declaration.get("lifecycle") == "current"
            and declaration.get("required") is True
            and not (names & observed)
        ):
            scope = f" at {scope_path}" if scope_path else ""
            findings.append(
                {
                    "code": "workflow_required_unobserved",
                    "severity": "critical",
                    "summary": (
                        f"{full_name}{scope}: required current "
                        f"{str(declaration.get('role')).replace('_', ' ')} "
                        f"{declaration['matchName']} has no observed run."
                    ),
                    "sourceRefs": [],
                }
            )
    return findings


def scoped_label(full_name: str, scope_path: str | None) -> str:
    return f"{full_name}:{scope_path}" if scope_path else full_name
