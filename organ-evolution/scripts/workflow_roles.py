#!/usr/bin/env python3
"""Workflow-role classification for neutral Organ Evolution observations.

A workflow result is an observed fact. Its architectural meaning is a separate,
human-owned declaration. This module joins those two records without allowing a
workflow, observer, or declaration to mutate organ health, gates, motives, or
decisions.
"""

from __future__ import annotations

from typing import Any

WORKFLOW_ROLES = {
    "permanent_gate",
    "release_gate",
    "publication_job",
    "scheduled_observer",
    "diagnostic",
    "bounded_repair_carrier",
    "repository_maintenance",
    "unknown",
}
WORKFLOW_LIFECYCLES = {"current", "superseded", "historical"}
MAX_DECLARATIONS = 256


class WorkflowRoleError(ValueError):
    pass


def validate_workflow_policy(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise WorkflowRoleError("workflowPolicy must be an object")
    declarations = value.get("declarations", [])
    if not isinstance(declarations, list):
        raise WorkflowRoleError("workflowPolicy.declarations must be an array")
    if len(declarations) > MAX_DECLARATIONS:
        raise WorkflowRoleError("workflowPolicy contains too many declarations")

    seen: set[str] = set()
    for index, row in enumerate(declarations):
        if not isinstance(row, dict):
            raise WorkflowRoleError(f"workflow declaration {index} must be an object")
        required = {"matchName", "role", "lifecycle", "required", "basis"}
        missing = required - set(row)
        if missing:
            raise WorkflowRoleError(
                f"workflow declaration {index} is missing {sorted(missing)}"
            )
        names = [row.get("matchName"), *(row.get("aliases") or [])]
        if not all(isinstance(name, str) and name.strip() for name in names):
            raise WorkflowRoleError(
                f"workflow declaration {index} requires non-empty exact names"
            )
        for name in names:
            if name in seen:
                raise WorkflowRoleError(f"workflow name declared more than once: {name}")
            seen.add(name)
        if row.get("role") not in WORKFLOW_ROLES - {"unknown"}:
            raise WorkflowRoleError(
                f"workflow declaration {index} has unsupported role {row.get('role')!r}"
            )
        if row.get("lifecycle") not in WORKFLOW_LIFECYCLES:
            raise WorkflowRoleError(
                f"workflow declaration {index} has unsupported lifecycle {row.get('lifecycle')!r}"
            )
        if not isinstance(row.get("required"), bool):
            raise WorkflowRoleError(
                f"workflow declaration {index} required must be boolean"
            )
        if not isinstance(row.get("basis"), str) or not row["basis"].strip():
            raise WorkflowRoleError(
                f"workflow declaration {index} requires a non-empty basis"
            )
        if row["lifecycle"] != "current" and row["required"]:
            raise WorkflowRoleError(
                f"workflow declaration {index} cannot require a non-current workflow"
            )


def _declaration_map(policy: Any) -> dict[str, dict[str, Any]]:
    validate_workflow_policy(policy)
    mapping: dict[str, dict[str, Any]] = {}
    for row in (policy or {}).get("declarations", []):
        clean = {
            "role": row["role"],
            "lifecycle": row["lifecycle"],
            "required": row["required"],
            "basis": row["basis"].strip(),
        }
        for name in [row["matchName"], *(row.get("aliases") or [])]:
            mapping[name] = clean
    return mapping


def apply_workflow_roles(
    workflows: list[dict[str, Any]], policy: Any
) -> list[dict[str, Any]]:
    mapping = _declaration_map(policy)
    annotated: list[dict[str, Any]] = []
    for workflow in workflows:
        name = str(workflow.get("name") or "")
        declaration = mapping.get(name)
        if declaration is None:
            role = {
                "role": "unknown",
                "lifecycle": "current",
                "required": False,
                "basis": "No exact human-owned workflow-role declaration matched this run name.",
            }
            source = "unclassified"
        else:
            role = declaration
            source = "declared"
        annotated.append(
            {
                **workflow,
                "role": role["role"],
                "lifecycle": role["lifecycle"],
                "required": role["required"],
                "roleBasis": role["basis"],
                "roleSource": source,
            }
        )
    return annotated


def workflow_finding(
    workflow: dict[str, Any],
    full_name: str,
    age_days: int | None,
    bad_conclusions: set[str],
    stale_workflow_days: int,
) -> dict[str, Any] | None:
    conclusion = workflow.get("conclusion")
    status = workflow.get("status")
    name = workflow.get("name")
    role = workflow.get("role", "unknown")
    lifecycle = workflow.get("lifecycle", "current")
    required = bool(workflow.get("required"))
    source = workflow.get("roleSource", "unclassified")
    refs = [workflow.get("url")] if workflow.get("url") else []
    role_text = str(role).replace("_", " ")

    if conclusion in bad_conclusions:
        if lifecycle != "current":
            return {
                "code": "workflow_historical_not_green",
                "severity": "context",
                "summary": (
                    f"{full_name}: {name} concluded {conclusion}, but it is declared "
                    f"{lifecycle} {role_text}; the red receipt remains visible without "
                    "being treated as a current organ gate."
                ),
                "sourceRefs": refs,
            }
        if source == "unclassified":
            return {
                "code": "workflow_unclassified_not_green",
                "severity": "critical",
                "summary": (
                    f"{full_name}: {name} concluded {conclusion} and has no exact "
                    "workflow-role declaration. It remains critical until classified."
                ),
                "sourceRefs": refs,
            }
        if required:
            return {
                "code": "workflow_required_not_green",
                "severity": "critical",
                "summary": (
                    f"{full_name}: required current {role_text} {name} concluded {conclusion}."
                ),
                "sourceRefs": refs,
            }
        return {
            "code": "workflow_advisory_not_green",
            "severity": "attention",
            "summary": (
                f"{full_name}: current advisory {role_text} {name} concluded {conclusion}."
            ),
            "sourceRefs": refs,
        }

    if status and status != "completed":
        if lifecycle != "current":
            severity = "context"
            code = "workflow_historical_pending"
        elif required:
            severity = "attention"
            code = "workflow_required_pending"
        elif source == "unclassified":
            severity = "attention"
            code = "workflow_unclassified_pending"
        else:
            severity = "context"
            code = "workflow_advisory_pending"
        return {
            "code": code,
            "severity": severity,
            "summary": (
                f"{full_name}: {lifecycle} {role_text} {name} is {status}."
            ),
            "sourceRefs": refs,
        }

    if isinstance(age_days, int) and age_days > stale_workflow_days:
        if lifecycle != "current":
            return None
        if required:
            severity = "attention"
            code = "workflow_required_stale"
        elif source == "unclassified":
            severity = "attention"
            code = "workflow_unclassified_stale"
        else:
            severity = "context"
            code = "workflow_advisory_stale"
        return {
            "code": code,
            "severity": severity,
            "summary": (
                f"{full_name}: latest {role_text} receipt for {name} is {age_days} days old."
            ),
            "sourceRefs": refs,
        }
    return None
