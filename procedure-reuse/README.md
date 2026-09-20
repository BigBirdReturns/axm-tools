# Procedure reuse interoperability test

A disposable, public-safe browser fixture for testing whether a retained
procedure stops when its meaning changes. It is designed for a Hronaut
maintainer to run with their own already-connected local agent, without
sharing accounts, credentials, machine access or repository write access.

The static landing page keeps the original v1 prompt and links the additive v2 copy-ready prompt. The versioned capsule is
[`v1/PROCEDURE.md`](v1/PROCEDURE.md), with executable pure rules in
[`v1/contract.mjs`](v1/contract.mjs). The four cases are baseline PASS,
cosmetic drift PASS, semantic drift UNKNOWN before action, and a false
success message followed by FAIL with no retry. All four use the same
scratch browser workspace; a reload tests the fixture's storage continuity.

The additive [`v2/PROCEDURE.md`](v2/PROCEDURE.md) is the mirror test. It leaves the frozen v1 fixture unchanged, holds page semantics constant, creates a native Hronaut continuity checkpoint, reloads the same tab to stale Hronaut's lifetime evidence, and asks whether that independent boundary blocks the write until normal reconciliation and a fresh semantic read.

## Run and inspect

Open `index.html` through any static server or use the published site.
The public URL is
https://bigbirdreturns.github.io/axm-tools/procedure-reuse/.
The Hronaut path requires Hronaut to be connected already. It does not
install or configure Hronaut, discover a port or token, or open a tunnel.

To host the entire repo locally: `python3 -m http.server --bind 127.0.0.1 8899`.
Use that explicitly selected loopback origin when testing a local copy.
ES modules and persistent storage need an HTTP(S) origin; opening the files
with `file://` is not the supported route.

The tool uses native HTML, CSS and JavaScript, no package manifest, third-
party runtime dependency, backend, subscription, API key or scheduled work.
It writes only `axm.procedure-reuse.v1.<synthetic-run-id>` in localStorage.
There are no application telemetry requests; the static host still receives
ordinary file requests. All values are synthetic. Receipt export is a local
download, never an upload. Browser clipboard denial leaves the prompt
visible for manual copying.

## Verification

`python procedure-reuse/scripts/check.py` verifies the release manifest and
static boundaries. `node --test procedure-reuse/scripts/rules.test.mjs`
exercises the pure contract. The optional browser qualification lives in
`tests/pages/verify_procedure_reuse.py` and uses Playwright only as an external
test dependency. Its workflow installs the pinned test runtime outside this
site's runtime; no package manifest or browser dependency is deployed.

Yevhen Tienkaiev later reported a native Hronaut 2.4.28 v1 run with the same PASS, PASS, UNKNOWN/0-save, FAIL/1-save sequence, one scratch workspace/tab, reload continuity and no repairs. That public maintainer report is recorded at `data/hronaut-native-run-20260919.json` with its provenance boundary.

The reference runner is **not Hronaut**. Its browser-context checks do not
qualify Hronaut's MCP lifecycle or workspace-generation semantics. The site
shows that distinction. Neither a fixture PASS nor a receipt authorizes
production routing. Read the unclaimed boundaries in the capsule.

## Maintenance and file ownership

All files in this directory are steward-owned. There is no machine-owned
feed and no scheduled mutation. Once published, `v1/` is immutable; the additive `v2/` protocol reuses it without changing its bytes. Behavior
changes require a new version and manifest. The parent landing page may
change publication links or add separately attributed observations without
rewriting the pinned experiment. Receipts are evidence, never new authority.

What can rot: public hosting, browser semantics, clipboard permissions and
Hronaut's advertised tool schema. Keep the fixture usable locally; fail
visibly when storage is unavailable; revise the adapter for a changed tool
catalog instead of inventing unsupported arguments. Do not expand this into
a shared browser, hosted service or Hronaut core modification.

This is an independently authored interoperability proposal. Hronaut has not
endorsed it, and no upstream PR or outreach was sent. Source review used
Hronaut's public skill at commit
`24b713bcbfc6db621b4be2eec2a2ad06d549994d`.
