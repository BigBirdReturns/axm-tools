# Decision Continuity

An independent AXM evaluation of the publicly described fiChains assess / decide / implement workflow. The browser replay makes the approved decision, original promises, ERP, procurement, floor and stock outcomes independently inspectable. Both bundled scenarios are synthetic. The page is not an Aankhen release and asserts no fiChains integration.

## Use

Open index.html or the hosted /axm-tools/decision-floor/ route. Switch histories, replay source-recorded-time snapshots, inspect exact sources, generate new quantities, export a view or open a locally generated decision_floor_report.json. Imported files stay in browser memory and are not uploaded. Browser inspection of a report does not authenticate the source bytes kept in its local vault.

The downloadable source distribution runs the investigator locally. Python 3.10+ is required; no runtime packages are required by the core. Extraction, mapping, reconciliation and portable tests live in offline/. Publication includes a downloadable ZIP and its hash record. The ZIP contains a copy of this viewer for fully offline use.

## Evidence and tests

Source excerpts and hashes in data.js are generated from the included synthetic inputs. data/sources.json records official public product references. The fiChains logo is a publicly sourced trademark used to identify the intended workflow; AXM authorship and independence remain visible.

Run python scripts/build_release.py --check after a release build. scripts/browser_test.py runs real native Chromium headless against the actual static files and records its checks; test execution never sends company data to an external service. Portable engine qualification uses offline/qualify.py; it is not proprietary integration or customer-data acceptance.

No scheduled work, telemetry, external fonts, external runtime fetch or business-system writeback exists. A restrictive CSP blocks network connections. The only network needed by the hosted page is the initial retrieval of its own static files. All files are steward-owned except reproducible downloads/ and data/package.json / data/qualification.json, produced by scripts/build_release.py. Never edit synthetic evidence to make a failing claim look true.

## Rot

Public product descriptions, source mappings, browser APIs and deployment services can change. Broken source links do not silently update the evidence. Report schema changes must be explicitly admitted; unsupported input fails visibly. Keep original release sources, source locators and distribution manifests. Rebuild and test before changing the published release.

## Sovereign recorder-to-recorder exchange (0.3.0)

The locally runnable evaluation now includes an optional contract-scoped Ed25519 witness exchange between two independent vaults. It preserves original signed statements and verifies them against manually enrolled peer keys; a conflicting PO record becomes a review rather than a rewritten fact. Run `python tools/peer_replay.py --output /private/synthetic-peer-receipt.json` from the extracted kit. Details, security boundaries, and human authority limitations are in `offline/PEER_EXCHANGE.md`. The public page and `data/peer-qualification.json` contain synthetic claims only. No source-system integration or legal determination is implied.
