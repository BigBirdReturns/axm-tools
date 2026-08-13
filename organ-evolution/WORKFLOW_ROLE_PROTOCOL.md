# Workflow Role Protocol

A workflow result is an observed fact. The architectural role of that workflow is a separate human-owned declaration. Organ Evolution joins those records without allowing either one to rewrite organ health, candidate fitness, hard gates, interests, mandates, or decisions.

## Declared fields

Each exact workflow-name declaration carries:

```text
role
lifecycle
required
basis
```

Supported roles are:

```text
permanent_gate
release_gate
publication_job
scheduled_observer
diagnostic
bounded_repair_carrier
repository_maintenance
```

Supported lifecycle states are:

```text
current
superseded
historical
```

A non-current workflow cannot be required. Names and aliases are exact. An unmatched run remains `unknown`, `current`, `advisory`, and `unclassified`; a red unclassified run fails visible until a steward declares its role.

## Interpretation

| Result and declaration | Observation finding |
| --- | --- |
| Current required workflow is red | Critical |
| Current unclassified workflow is red | Critical |
| Current advisory workflow is red | Attention |
| Superseded or historical workflow is red | Context, with the red receipt retained |
| Current required workflow is pending or stale | Attention |
| Current advisory workflow is pending or stale | Context |

Classification cannot turn a failure green, delete its source reference, or prove that a workflow is correctly classified. The declaration includes a basis so a reviewer can challenge its role or lifecycle. A one-shot carrier may become historical only when its bounded purpose and successor gate are named. A publication job may remain advisory only when product correctness is independently gated.

## Capture resistance

This protocol prevents two opposite failures:

1. treating every historical diagnostic or one-shot carrier as current organ failure;
2. relabeling a current required gate as historical merely to clear a dashboard.

The observer preserves the run, conclusion, head, URL, role, lifecycle, obligation, declaration source, and basis. Unknown red workflows remain critical by default.

## Control question

Can the estate explain why a workflow matters now, preserve its actual result, and change its role only through an explicit reviewable declaration rather than convenience, reputation, or dashboard pressure?
