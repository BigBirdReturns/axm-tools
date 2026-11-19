# AXM × i3X application and technical review package

Release: 19 November 2026. Producer: Jonathan Sandhu, AXM, jvssandhu@gmail.com.

[Open the member workbench](workbench/) · [Read the complete review](review/) · [Download the complete kit](cesmii-member-kit.zip) · [Watch the demonstration](review/demo.mp4).

The member workbench connects a selected i3X asset to operator-defined evidence and rules. It retains source revisions, marks dependent conclusions stale after corrections, records reviews against exact decisions, saves workspaces locally and exports a handoff that a separate browser or Node process independently recomputes. The standalone application includes its calculation source and retained example context. Its three editable examples cover maintenance readiness, batch review and energy intensity; the import contract supports additional named source families and arithmetic/comparison rules without executing imported code.

The complete kit includes the member application, the retained reference lab, the six-source Industrial Continuity application, editable member workflow JSON, technical architecture guide, captioned demonstration, exact official second-server source and runnable setup, observed HTTP captures, conformance results, independent receiving checks and source manifests. Open `cesmii-proof/review/index.html` after extracting the two application directories, or open either application's `offline.html` directly.

## Reproduce the member release

From the repository or extracted kit root:

```text
python cesmii-proof/workbench/build.py
node cesmii-proof/workbench/qualification.cjs
node cesmii-proof/workbench/verify-capsule.cjs cesmii-proof/workbench/sample-handoff.json
```

The optional browser campaign is documented in [workbench/README.md](workbench/README.md). The actual second-server setup and verifier are documented in [second-server/README.md](second-server/README.md). Its server uses the official CESMII implementation with simulated equipment data. The preserved reference API capture remains a historical observation. Team records in the included examples are synthetic; imported member records remain local and keep their declared evidence class.

The application carries source and calculation integrity. Source authenticity, responsible identities, real plant observations and authority to operate remain with the contributing organization. Hosted and downloaded applications are available for use, with source included for inspection and reproduction; the repository carries no blanket software license. Contact the producer for distribution or integration terms.

`build-member-kit.py` creates a deterministic combined archive and `--check` verifies each archived file against its manifest and current source bytes. `build.py` maintains the original reference lab's offline and source distribution, excludes recursive delivery archives and media, and writes exact UTF-8 bytes across native and CI hosts. `MEMBER_MANIFEST.json` describes the complete member kit.

# Retained reference lab, 9 November 2026

Independent application-level proof using CESMII's published i3X customer journey and visual vocabulary. CESMII has not commissioned, accepted, certified or endorsed this work. Private introductions, correspondence and allegations are excluded.

## The test

Discover pump-101 in the public demo, retain its source context, compose three synthetic teams' evidence, correct an allocation, preserve the obsolete decision, recompute the changed one, export a capsule and reconstruct both conclusions in a fresh client. Missing inputs and uncertain quality remain unknown. A recorded parts conclusion never grants maintenance or production authority.

The exact existing Team Commons core is copied into commons-core.js. build-meta.json records its byte identity. The additional engine binds i3X source evidence, detects stale decisions and verifies cold replay. This is a bounded implementation of retained work, not a new claim that all of AXM is qualified in manufacturing.

## Reproduce

The published folder contains a retained data/capture.json and generated files. Open index.html through an HTTP server, or open offline.html directly. Run the UI steps, export the actual JSON, and import it into a different browser or clean tab. Run the local adversarial suite. The source archive is self-contained.

From the repository root: `node cesmii-proof/tests/verify.cjs`. To rebuild within axm-tools: `python3 cesmii-proof/build.py`. The build reads the existing `team-commons/core.js`; a downloaded standalone archive already contains that pinned copy and can run the Node tests directly.

To acquire a NEW observation without overwriting history: `python3 cesmii-proof/capture.py --out /your/local/path/new-capture.json`. The collector performs five discovery GETs and three read-only query POSTs. It sends no writes, creates no subscriptions, and records no authentication credentials. An explicitly selected `--base-url` supports another authorized endpoint, but the pump-specific selection must be adapted to its discovered model. Nothing is silently certified by API reachability.

Do not publish a customer capture without its owner's release. The build workflow collects only the public CESMII demo, once if the retained capture is absent. Existing capture timestamps remain visible; a saved observation is not current plant state.

## Acceptance boundary

Pass: exact source-body integrity, explicit quality handling, contributor lineage, missing-evidence refusal, correction-induced staleness, separate re-evaluation, source-pinned export, fresh-client recomputation, rejection of byte tampering and rehashed false saved conclusions. The six expansion fixtures exercise balance, ratio and completion recipes; their tests are synthetic software tests, not manufacturing results.

Not established: actual organization identities or tenant isolation; physical truth; production freshness requirements; binding regulatory or work authority; remote writes or subscription behavior; cross-vendor portability beyond the one public reference endpoint; commercial demand; measured throughput, quality or energy improvement; independent customer acceptance. Hashes establish byte integrity under the supplied record, not an authenticated producer or an external trust anchor.

The official i3X conformance suite remains the authority for API compliance testing. This lab does not award Full Compliance or any other CESMII status. Existing platforms may already offer audit, provenance or orchestration. The falsifiable added-value question is whether a separate recipient can retain and replay the decision outside the original platform with the full recipe and evidence.

## Heat map

research.json carries public sources, claim boundaries and the scoring rule. Each opportunity receives 0–3 on demo fit, evidence reuse, correction value, handoff value and readiness, weighted 2,2,3,3,3 (maximum 39). These are analyst prioritization scores, never measured ROI. The pump path is selected because both the official demo object and the existing three-team logic already exist. scenarios.json retains six alternate fixtures and their expected transitions.

## Design provenance

CESMII's public ProveIt 2026 presentation uses navy #13216f, cyan #00ABEE, teal #009A9A and violet #5338D3, with Bitter and Open Sans. This original page uses that color vocabulary and system-font fallbacks, its own AXM identity, and a visible independent-lab declaration. No portrait or trademark logo is reused. No analytics, third-party runtime assets, logins, paid APIs or device-control connection is present.

## Files

engine.js and commons-core.js perform computation; app.js renders; index.html and style.css are the customer-facing surface. capture.py is the read-only adapter. build.py retains source hashes and makes the offline page and source ZIP. research.json, scenarios.json, build-meta.json, data/capture.json, data/qualification.json and manifest.json hold the inspectable record.
