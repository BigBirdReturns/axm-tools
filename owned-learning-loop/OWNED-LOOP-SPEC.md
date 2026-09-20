# Owned Learning Loop 1.0

Dated: 2026-09-20

## Objective

Turn recurring AI-assisted work into a proprietary, replayable learning asset before smaller local models make the serving layer commonplace.

## Required objects

1. `workload`: a bounded recurring task with an observable terminal condition.
2. `trace`: model identity, prompt/config version, retrievals, tool calls, latency/cost metadata, and references to source/output artifacts.
3. `outcome`: the terminal evidence that says whether the work succeeded.
4. `eval_set`: frozen replay cases plus holdout cases unavailable to adaptation.
5. `route`: explicit rule for local, hosted, human-review, or refusal paths.
6. `candidate`: immutable model or adapter artifact under evaluation.
7. `promotion_receipt`: dataset/eval hashes, metrics, authority and rollback target.

## State machine

`OBSERVE -> LABEL -> REPLAY -> ROUTE -> ADAPT -> SHADOW -> PROMOTE | REJECT -> OBSERVE`

Promotion is reversible. Rejection preserves the failed candidate and its evidence so the same failure is not rediscovered later.

## Memory placement

Keep current task state in context or structured state. Keep mutable facts in authoritative stores or retrieval. Keep preferences in editable policy/profile state. Keep deterministic procedures in code or workflows. Promote a repeated, stable skill into a versioned adapter only after replay evidence demonstrates an improvement.

## Promotion law

A candidate reaches production only when all workload-specific quality, safety and authority gates pass. Cost and latency comparisons happen after those gates.

Minimum receipt fields:

- immutable base-model identity and quantization/configuration;
- candidate artifact hash;
- training-set hash and provenance boundary;
- replay-set and holdout-set hashes;
- terminal success rate and critical-failure count;
- p50/p95 latency and cost per accepted outcome where measurable;
- decision owner and timestamp;
- last known-good rollback target.

## Routing law

Local-first applies only to workload classes that have demonstrated the required quality. Novel, low-confidence, high-impact or authority-sensitive cases escalate to the stronger model or a human decision path. Every escalation is itself a labelled learning event.

## Adaptation law

Freeze the base model first. Prefer narrow, replaceable adapters or other bounded deltas. Training data comes from accepted outcomes and independently reviewed corrections, not from unfiltered model output. Keep training, evaluation and holdout sets separable by hash.

## Threat boundary

Treat adapters and model deltas as privileged deployment artifacts. Runtime loading endpoints are administrative surfaces, not end-user features. Preserve provenance, restrict write authority, and retain the exact previous artifact for rollback.

## 12-month acceptance test

By 2027-09-20, a team following this contract should be able to introduce a newly released model, replay its real workload corpus, compare it against the current route, and either reject it or promote it with a complete receipt without redesigning the application around the new vendor.
