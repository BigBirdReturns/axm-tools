# AXM × Polybolos Partition Authority Surface

This directory contains a self-contained browser surface for turning heterogeneous Standing Orders and communications-partition artifacts into a professional, evidence-bound presentation.

The worked fixture is the supplied `SO_CHROME_TEST` transaction from 2 August 2026. It contains a direct event log and a narrative HTML report. The surface preserves both files independently, computes SHA-256 over their bytes, normalizes the event sequence, and distinguishes direct observations from report assertions, derived values, open gates, and conflicts.

## What the page does

`index.html` reconstructs the validated standalone entirely in the browser from same-origin static payload parts. The resulting application makes no network requests. It accepts logs, text, JSON, JSONL, CSV, TSV, HTML, XML, XLSX, XLSM, DOCX, PPTX, PDFs, images, ZIP archives, and unfamiliar binary files. Known formats receive embedded local parsing. Unknown content is retained as a source object with filename, media type, byte count, magic bytes, parser disposition, and SHA-256 rather than being rejected or assigned invented meaning.

The surface generates five coordinated views:

- **Show** renders the professional authority-under-partition page.
- **Scenarios** separates exercised transitions from described but unwitnessed controls.
- **Evidence** exposes the source ledger, claim crosswalk, normalized events, and exact proof boundary.
- **Intake** replaces the worked fixture with a new source set without editing the HTML.
- **AXM** shows how the Polybolos adapter and the existing equipment-readiness adapter resolve to the same source-custody and claim-binding transaction.

The user can export normalized JSON, a new standalone HTML carrying the current evidence, or a portable ZIP containing the original sources, normalized evidence, manifest, checksum ledger, README, and reopening standalone.

## Evidence states

- `OBSERVED`: directly carried by the loaded source records.
- `ASSERTED`: present in narrative material but not in the direct event trace.
- `DERIVED`: computed from source values with the mechanism named.
- `OPEN`: a required witness or artifact has not been supplied.
- `CONFLICT`: the loaded sources contain incompatible closure statements.

## Worked-fixture boundary

The direct log supports an administrator-injected communications transition, Standing Orders activation, ten in-allowlist `SMALL_UAS` authorizations, five out-of-allowlist `MEDIUM_UAS` safe denials, explicit restoration, deactivation, and acknowledgment through sequence 15.

The supplied trace does not directly witness automatic Lattice detection, local-link state, operator presence, cryptographic authority, an issued and expired offline lease, process-restart retention, a node-signed journal, human disposition, operational deployment, targeting, engagement, or combat effectiveness. Narrative claims remain visible as assertions and do not overwrite that boundary.

## AXM boundary

This page is an intake, normalization, analysis, and presentation surface. It does not mint Genesis shards, issue command authority, actuate a system, write back to a source system, or convert a human-facing report into operational qualification. Accepted surfaces are candidates for promotion into AXM custody, sealing, detached verification, query, and replay.

## Deployment

The page has no build step, backend, account, API key, or third-party JavaScript dependency. GitHub Pages serves the local loader and payload parts; the reconstructed application makes no network requests. The Standalone control exports one HTML file for email, removable media, or authorized offline use.

The public page is intended for synthetic, unclassified, or de-identified evidence. Controlled operational data should use the exported standalone only inside an authorized environment.

Browser intake is bounded at 60 files, 128 MB per file, and 512 MB per batch to prevent a malformed or accidental source set from exhausting the tab.

## What can rot

Browser support for `DecompressionStream`, Office Open XML edge cases, new archive compression methods, and future Standing Orders event vocabularies may change. A parser failure must remain visible and fall back to source custody. It must never silently drop the file or promote an unsupported claim.
