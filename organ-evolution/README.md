# Organ Evolution Evaluation Surface

A local-only workbench for deciding how an estate organ should evolve without
confusing the organ's function with its current implementation, maintainer,
brand, supplier, or institutional owner.

The surface is built for questions such as:

- Should an organ be retained, hardened, specialized, generalized, split,
  merged, grafted, commoditized, replicated, federated, placed in dormancy,
  restored, forked, or retired?
- Which functions, authorities, outputs, obligations, and identities must
  survive the transition?
- Which claims are supported by independent evidence, which are self-attested,
  and which remain judgment or open questions?
- Do the same actors sponsor, validate, decide, maintain, and benefit from the
  proposal?
- Does the proposal survive steward exit, supplier loss, 10x load, capture,
  relicensing, network loss, and institutional fork?
- Can the new implementation be removed without losing canonical data,
  accepted receipts, or the ability to reconstruct the prior organ?

## Operating model

The working format is `axm-organ-evolution/1`. It contains:

```text
estate
actors and interest claims
organs and their authority membranes
function coverage
organ dependencies
candidate evolutions
migration ledgers
evidence records
stress scenarios
decision record
```

The surface keeps these objects separate:

```text
organ identity != implementation != supplier
function != repository != product label
actor != role != authority
claim != evidence != decision
self-declared interest != ascribed interest != inferred motive
review priority != probability != truth
authorship != maintenance != ownership != governance
```

## Views

### Anatomy

Shows the selected organ's mission, lifecycle stage, function coverage, health
envelope, authority membrane, dependencies, critical single-source seams, and
its position in the estate map.

### Evolution

Compares explicit candidates. Every candidate records:

- evolution action;
- preserved, altered, retired, and introduced objects;
- twelve non-collapsed fitness dimensions;
- five hard gates;
- sponsor, validator, decider, and beneficiary roles;
- evidence links;
- risks and preserved dissent.

The surface intentionally refuses a single total score. A hard function or
authority failure blocks a candidate. Open evidence or migration keeps it on
hold. Warning states permit only a bounded pilot. Passing every gate makes a
candidate admissible for a human decision, not automatically correct.

### Actors and interests

Records role assignments and interest claims as `self_declared`, `ascribed`, or
`inferred`. Role overlap and control concentration produce review findings, but
the software never converts them into hidden-motive truth.

### Evidence

Uses `confirmed`, `measured`, `reported`, `derived`, `judgment`, and `open`
evidence classes plus an explicit independence field. The displayed weighted
strength is a review-gap projection only. It is not a confidence probability.

### Stress tests

Applies selected scenarios to the candidate's declared fitness envelope. The
scenario table remains per-dimension and per-candidate so one strong dimension
cannot silently cancel a fatal weakness elsewhere.

### Decision record

Generates a normal analytical memorandum that classifies the organ and
candidate, names the actors, explains the mechanism, carries the receipts and
limits, widens the dependency map, preserves open questions, and ends with a
control question. A named authority still accepts, rejects, holds, supersedes,
or revokes the proposal.

## Data handling

The tool has no backend, API keys, analytics, account, or external runtime
request. The worked example is embedded in `index.html` and also stored as
`data/axm-estate.example.json` for inspection and reuse.

The current workspace is stored in the browser's local storage. It is not a
durable record. Export JSON before clearing browser state or moving devices.
Imports are accepted only when the root format is `axm-organ-evolution/1` and
the required organ and candidate collections exist.

### File ownership

- `index.html` is steward-owned source and the complete production interface.
- `data/axm-estate.example.json` is a steward-owned worked example.
- `scripts/validate.py` is steward-owned, stdlib-only validation.
- No file in this tool is machine-owned.
- Exported workspaces and reports remain with the operator and are never sent to
  this repository automatically.

## Local use

```bash
cd organ-evolution
python -m http.server 8899
```

Open `http://127.0.0.1:8899/`.

Validate the static estate and source contract:

```bash
python organ-evolution/scripts/validate.py
```

Drive the real page in Chromium or Edge:

```bash
node tests/pages/verify_organ_evolution.mjs
```

The GitHub Actions workflow installs Playwright only inside the disposable CI
runner. The shipped page itself has no runtime dependency.

## Boundary

This surface evaluates the structure of an evolution proposal. It does not
prove that an organ is alive, that a function is valuable, that an actor has a
particular motive, that a source is authentic, or that a decision is correct.
It makes unsupported transitions, authority transfers, missing migrations,
capture geometry, and weak exit paths difficult to hide.
