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

The complete estate loop is:

```text
observe
→ reconcile
→ propose
→ stress
→ decide
→ execute
→ verify
→ migrate
→ observe again
```

Observation and evaluation are separate products. Machine observations may
identify current repository heads, workflow results, open pull requests,
release tags, succession files, local receipts, and collection failures. They
cannot change organ anatomy, health ratings, candidate dimensions, hard gates,
interest claims, mandates, or decisions.

## Views

### Anatomy

Shows the selected organ's mission, lifecycle stage, function coverage, health
envelope, authority membrane, dependencies, critical single-source seams, and
its position in the estate map.

The Anatomy view also renders the current `axm-organ-observations/1` row for the
selected organ. Repository facts, workflow conclusions, exact heads, tags,
open pull requests, structural attention findings, and attributed local
observations remain visually and semantically separate from the human-owned
health envelope.

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

## Estate observation compiler

`organ-evolution/scripts/observe.py` is a stdlib-only collector. Its human-owned
mapping is `data/sources.json`, using format `axm-organ-sources/1`. It observes
the configured repositories through the GitHub API and merges attributed
operator or device facts from `data/observed.json`, using format
`axm-organ-local-observations/1`.

It writes two byte-equivalent projections of one product:

```text
data/observations.json  axm-organ-observations/1
data/observations.js    local static-page projection
```

The source digest excludes collection time, so two runs over the same observed
state retain the same `organobs1_` identity. A missing repository, failed
workflow, stale draft, absent release tag, missing succession record, or
collector failure remains visible. The compiler never reuses an unavailable
source as though it were current.

The scheduled `Organ evolution observe + deploy` workflow qualifies the
compiler, generates the exact observation pack, commits only the two
machine-owned projections, rebuilds the established offline AXM Readiness
launcher, and deploys the complete static site. The same workflow is manually
runnable.

## Data handling

The page has no backend, API keys, analytics, account, or external runtime
request. The worked example is embedded in `index.html` and also stored as
`data/axm-estate.example.json` for inspection and reuse.

The current evaluation workspace is stored in the browser's local storage. It
is not a durable record. Export JSON before clearing browser state or moving
devices. Imports are accepted only when the root format is
`axm-organ-evolution/1` and the required organ and candidate collections exist.

The live observation pack is a committed static asset. The browser performs no
GitHub request. Collection occurs only in the scheduled or manually dispatched
workflow, and its exact facts remain independently inspectable as JSON.

### File ownership

- `index.html`, `styles.css`, `observations.css`, `core.js`, `views.js`,
  `observations-view.js`, and `app.js` are steward-owned production source.
- `data/axm-estate.example.json` and `data/seed.js` are steward-owned worked
  examples.
- `data/sources.json` is human-owned repository-to-organ mapping.
- `data/observed.json` is the human or on-device hostile-source seam. Automation
  reads it and never overwrites it.
- `data/observations.json` and `data/observations.js` are machine-owned. The
  observation workflow rewrites them together.
- `data/fixtures/` is steward-owned regression evidence and contains only
  synthetic repository responses.
- `scripts/observe.py`, `scripts/test_observe.py`, and `scripts/validate.py` are
  steward-owned, stdlib-only qualification code.
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
python organ-evolution/scripts/test_observe.py -v
```

Generate the deterministic synthetic observation pack:

```bash
python organ-evolution/scripts/observe.py \
  --sources organ-evolution/data/fixtures/sources.fixture.json \
  --observed organ-evolution/data/fixtures/observed.fixture.json \
  --fixture organ-evolution/data/fixtures/github.fixture.json \
  --now 2026-07-28T00:00:00Z \
  --output organ-evolution/data/observations.json \
  --js-output organ-evolution/data/observations.js
```

Drive the real page in Chromium or Edge:

```bash
node tests/pages/verify_organ_evolution.mjs
node tests/pages/verify_organ_observations.mjs
```

The GitHub Actions workflow installs Playwright only inside the disposable CI
runner. The shipped page itself has no runtime dependency.

## Boundary

This surface evaluates the structure of an evolution proposal. It does not
prove that an organ is alive, that a function is valuable, that an actor has a
particular motive, that a source is authentic, or that a decision is correct.
It makes unsupported transitions, authority transfers, missing migrations,
capture geometry, weak exit paths, stale observations, and collector failures
difficult to hide.
