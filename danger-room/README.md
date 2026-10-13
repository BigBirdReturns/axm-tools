# Danger Room: demo and camera-log format

Self-contained public handoff page for replaying the recorded Fly-0 baseline demonstration and obtaining optional camera-frame, decision and telemetry CSV headers plus a session JSON template. The page uses no network requests after navigation, dependencies, backend, account, upload endpoint or scheduled work.

## Provenance
The embedded receipt comes from the 2026-10-12T08:34:43.419135+00:00 W01 run of axm-embodied at 9f3df5c348449d09c7a83cd00e4bd030e075dc92. It includes 33 sampled snapshots from 260 ticks, the recorded rerun/TCP/tamper results, source hashes and full-ledger digest. The full original ledgers were temporary; this page does not claim to verify their bytes in the browser. It plays recorded samples, rather than executing the simulator. The separate camera CSV example is invented, labeled EXAMPLE-ONLY and has unrelated camera/Pi clocks.

## Operation and ownership
Open index.html or serve this directory from any static host. All UI, style, sample values and downloadable text are embedded. The existing main-branch Pages workflow publishes it. All files here are steward-owned; none are machine-owned. Runtime source remains in axm-embodied. Native logs are preferred; these optional templates are a proposed interchange, not a required wire protocol. No source logs are collected on this page.

## What can rot
Browser Blob-download support or the surrounding site's hosting route may change. The HTML and raw embedded JSON remain recoverable as text. Recorded experiment results are dated and do not become new results when the page is republished. Revise the interface or templates without silently changing the retained execution receipt.
