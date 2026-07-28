# Scoped organ observation

An organ is a bounded estate function, not necessarily a repository. One repository may implement several organs, and one organ may span several repositories. The live census therefore supports a scoped repository mapping without equating repository ownership with organ identity or authority.

## Source declaration

A scoped source uses:

```json
{
  "fullName": "BigBirdReturns/tier-bench",
  "scopePath": "supplier_foundry",
  "workflowScope": "declared_only",
  "workflowPolicy": {
    "declarations": [
      {
        "matchName": "Supplier Foundry asset pilot",
        "role": "permanent_gate",
        "lifecycle": "current",
        "required": true,
        "basis": "The exact provider, conformance, fallback, and rip-out transaction."
      }
    ]
  }
}
```

`scopePath` is a bounded repository-relative path. Parent traversal, absolute paths, and duplicate repository-plus-scope identities are refused. The unscoped repository may remain mapped to a parent organ while the subdirectory is mapped to a distinct sub-organ.

`workflowScope: declared_only` admits only exact workflow names declared by the human-owned policy. The observation product retains the total number of repository workflows, the included number, and the omitted number. The parent organ may still observe the complete repository workflow surface.

## Failure law

A required current declared workflow with no observed run is critical. A red included workflow retains the role and lifecycle interpretation established by the workflow-role protocol. An unrelated workflow cannot silently become the sub-organ's gate merely because it shares a repository, and the scoped observer cannot delete the fact that other workflows were omitted.

Repository identity, default branch, exact head, tags, license, open pull requests, source URL, collection time, and source failures remain repository-level facts. README, continuity, file count, and other implementation signals are evaluated inside the declared path. A repository-level license may apply to the sub-organ even when the scoped directory contains no second license file; that inheritance remains visible rather than inferred from directory structure alone.

## Authority membrane

A scoped source changes observation granularity only. It cannot change:

```text
organ anatomy
health envelope
candidate fitness
hard gates
interest or motive claims
mandates
decisions
accepted authority
```

The source declaration is human-owned. The observation pack is machine-owned. The machine may report drift, missing workflow receipts, unavailable source, absent succession, and other attention conditions. It may not decide what the sub-organ should become.

## Supplier Foundry application

Supplier Foundry is implemented under `tier-bench/supplier_foundry` while Tier Bench remains the broader measurement organ. Supplier Foundry observes only its exact permanent gate, scoped README and continuity record, and repository-level custody facts. It owns supplier acquisition, isolation, qualification, packaging, substitution, and rip-out evidence. It does not acquire Tier Bench routing authority, domain capability authority, policy authority, or estate scheduling authority.

## Control question

Can a shared repository change maintainers, workflows, or internal structure while each organ retains its own function, succession, evidence, and authority record, and while omitted repository activity remains visible rather than silently discarded?
