# Research Continuity 1.0.0

A working, local research-cycle workbench built from Cantos / Second Run. Its opening demonstration compares two retained sets of extraction responses, preserves the basis for the comparison, records failures, detects source/intent/method changes, checks reuse, and carries the working history to another operator.

Public route: https://bigbirdreturns.github.io/axm-tools/research-continuity/

## Use it

Open `index.html` and select **Run the working example**. The unchanged ResearchCore evaluator checks twelve original tasks per configuration, all attempts and timing, the full quoted cost, and the acceptance rule. Change the rule, correct a source version, introduce a failed attempt, or compute the sensitivity map. Source corrections hold dependent work until explicit readmission. New plans and human reviews remain separate. Export a full packet, an offline workbench, a frozen reviewed report, or a continuation note. The page supports native `second-run/task-run@1` imports with mandatory source metadata.

The opening input data and quotes are synthetic, not customer, provider, clinical or legal findings. A separate `data/native-witness.json` records actual execution of the existing Cantos native operations on the estate. It is retained evidence, not a live backend.

## Measurement ledger

Select **Measurement ledger** to admit any local JSON source (2 MB maximum), its instrument, dataset version, locator and a textual re-execution instruction. Extract a finite numeric value by JSON Pointer and declare its unit and scale. Derive a ratio, sum or difference from two current source-addressed claims; sums/differences require matching units and scales, and named scales refuse generic arithmetic. A retained-value cross-check measures disagreement under an explicit tolerance without inventing independent instrumentation.

The built-in measurement example uses 120 fictional specimens and 90 passes. Correcting the pass source to 96 leaves the old claim and its 0.75 yield stale. Explicit re-extraction changes the claim, and explicit recomputation produces 0.8. Earlier frozen editions remain intact. Your own sources use the same code path. The Node checker re-extracts every measurement and recomputes every derivation when it cold-opens an exported packet.

## Ownership

- `source/research-core.js` is an exact source projection of Cantos `research-desk/app.html#research-core`, pinned by commit and SHA-256 in `source/OWNER.json`. Native records, revisions, dependency states, grading, arithmetic, reviews, snapshots and verification remain owned there. Do not fork those operations into UI code.
- `source/continuity.js` owns this bounded workflow: source receipts, local plan/output sequencing, attempts, source readmission and sensitivity views.
- `source/measurements.js` owns JSON Pointer extraction, unit-checked arithmetic and retained cross-check observations, using the same native journal and dependency owner.
- `source/ui.js` and `source/measurement-ui.js` own presentation and explicit user actions.
- `scripts/build.py` embeds the pinned sources into one offline-capable page. No runtime cross-tool imports or third-party dependencies.
- `scripts/native_bridge.py` invokes the existing Cantos work owner in an explicitly supplied local checkout, in separate fresh processes, and records cold / warm / changed-price outcomes plus native tests. It makes no provider requests.
- All source files are steward-owned. `index.html`, `downloads/` and `data/qualification.json` are generated release artifacts. No scheduled content changes or user uploads exist.

## Scope

The browser actually evaluates retained responses, computes SHA-256 digests, verifies journals, preserves revisions and checked reviews, exports original bytes, and rejects altered packets. The command-line checker cold-replays the same native journal and recomputes the exact derived arithmetic. No shell, model output, or uploaded proof code is executed from a packet.

Local sealing is an ordering and identity check. This is already-visible exploratory evidence, not a blinded study. An exported anchor digest or entered locator does not authenticate a remote witness or establish an external timestamp. A rebuilt whole history can pass a self-consistency check unless compared against an independently retained trusted prior digest. The output is not secret before UI reveal. Proof attachments remain unverified until an appropriate checker actually runs. Human names are attributed, not identity-authenticated. No claim of Lean verification, source truth, population reliability, investment/medical/legal approval, insurance, or third-party integration is made.

Failed/held attempts remain in the native journal. A frozen report remains historical; later corrections make dependent current work stale rather than erasing old results. Full quote/bill scopes and every original task remain visible. Checked deterministic reuse is not zero-cost computation and is not a new model measurement.

## Verification

```sh
node --test research-continuity/tests/*.test.cjs
python research-continuity/scripts/validate.py
python research-continuity/scripts/build.py --check
# Test-only Playwright installation belongs outside this tool.
EVIDENCE_DIR=/your/scratch TEST_CHROME=/path/to/chrome python research-continuity/tests/browser.py
```

From an extracted kit:

```sh
node scripts/check_packet.cjs my-packet.json --recompute
python scripts/native_bridge.py --cantos /path/to/cantos --out /new/result-directory
```

Use Python 3.12+ and Node 22+. The native bridge requires the existing public Cantos source and retained inputs; it installs nothing. Its fresh result directory is outside both source checkouts. Source-identity differences and failures remain visible.

The local candidate passed 33 native/adversarial tests and 17 actual browser journey checks, including a generic measurement path, offline export, cold import, corruption refusal, mobile rendering and zero unexpected network requests. Exact source qualification lives in `data/qualification.json`; the browser receipt names its tested page hash. These checks are finite software qualification, not a formal proof.

## Privacy and recovery

The page has no server, account, telemetry, network computation or upload. Its CSP refuses network connections. User data is memory-only unless the user explicitly selects **Keep a copy in this browser**. Complete packets and offline exports include supplied source contents. Clear only this tool's storage with its own control. Export before browser/profile loss. A rejected import leaves the current workspace unchanged.

## What can rot

Browser Web Crypto, File/Blob download behavior, storage quotas, current Node/Python versions, native Cantos owner schemas, host availability, and GitHub Pages may change. Verification must expose a failure. A missing bill remains missing; a foreign proof artifact remains unverified. Changes to the upstream owner require an explicit source update and rerun of this tool's native and browser tests. No private counterpart's code, health details, credentials or private dashboard text belongs in the public tree.
