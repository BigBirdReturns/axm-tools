# Owned Learning Loop

Public release: 20 September 2026.

A local-first operating playbook for getting ahead of the expected compression of frontier-class capability into smaller hardware. The page does not depend on the forecast being exactly right: its durable asset is a replayable correction loop built from real work.

## What it ships

- `index.html` + `app.js`: static public playbook and local plan generator.
- `OWNED-LOOP-SPEC.md`: plain-text implementation contract.
- `trace.schema.json`: minimum trace/outcome record.
- `promotion.schema.json`: minimum adaptation/promotion receipt.
- `example-plan.json`: one concrete first-week plan.
- `sources.json`: dated source ledger.
- `owned-loop-starter.zip`: portable copy of the non-UI starter artifacts.

## Operating rule

Quality and authority gates precede cost and latency optimization. Base models remain frozen by default; task-specific adaptations are versioned artifacts with an eval record and rollback target.

## File ownership

All files in this directory are steward-owned. There is no machine-owned state, workflow or scheduled fetch. The page stores checklist state only in the visitor's browser `localStorage` and exports JSON locally.

## What can rot

External source links, browser download APIs, model-serving interfaces, and the specific adaptation tools cited today. The architecture should survive replacement of every named model, GPU, runtime and training library.
