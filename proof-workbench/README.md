# AXM Proof Workbench 0.1.0

One portable runner over three existing, byte-pinned implementations. This consolidates qualification and commercial scoping; it does not replace Genesis, Knowledge Pack, Team Commons, Decision Floor or their native evidence formats.

## Run locally

Extract the complete package. Python 3.10+ and Node 18+ are required for the combined suite. The Python cores use only the standard library. Optional signed Decision Floor peer exchange uses OpenSSL. No pip/npm install, model weights, cloud account or API key is needed. The receptionist experiments launch local fixture servers on loopback and terminate them; they send no external messages and write no production systems.

```
python -B proof.py verify
python -B proof.py qualify --output /private/new-run
python -B proof.py verify-run /private/new-run
python -B proof.py plan engagement.example.json --output /private/new-plan
```

Use a new output directory for each invocation, outside the extracted kit. The example intentionally remains HELD until the receiving owner, data custodian, permission, decision and acceptance criteria are supplied. READY_FOR_SCOPING is a proposed scope, not actual identity verification, production authorization, buyer acceptance or a signed contract. The plan command produces JSON and a scoped Markdown delivery brief with cost assumptions and exclusions. It executes no customer data.

Select one adapter with `--adapter i3x`, `--adapter decision-floor` or `--adapter receptionist`. Every native source ZIP is copied byte-for-byte from the source addresses in donor-map.json. Unpack happens into a fresh private run directory. The adapter launches a fixed local command, never commands supplied by an engagement record. Each observation retains stdout, stderr, exit code, elapsed time, source identity and the original native report. Failed and missing suites prevent PASS. Runtime reports can contain local paths and synthetic fixture credentials; keep raw runs private and review any disclosure.

## What is actually reused

The i3X source-bound capsule is exported and restored by a separate Node process, with the old 0-issuable-parts and corrected 1-part decisions both recomputed. Decision Floor executes its original regression suite and 1,000 generated cases with a retained seed. The receptionist executes its frozen transaction and explicit-approval suites, including the preserved M10 erroneous model proposal; replay makes no new inference calls. These are three different executable workflows, not three labels on one arithmetic example.

The web page reads dated, generated release evidence, builds an engagement JSON locally, calculates user-supplied delivery economics and inspects an imported report as an unverified claim. Python/Node tests run through the downloaded CLI, not inside the static browser. The browser never uploads selected content. The public demonstrations, original historical captures and native formats remain unchanged.

## Integrity and trust

`MANIFEST.json` binds every delivery file except its own digest. The externally published ZIP hash binds the complete distribution; authenticate that hash separately. `verify --expected-manifest-sha256 HEX` checks a separately trusted manifest. A manifest stored beside its contents is an internal consistency check, not an authenticated producer or proof of physical truth. `verify-run` checks stored evidence bytes; a new `qualify` run creates a separate execution observation. Do not execute an untrusted ZIP merely because it contains a manifest.

## Commercial packaging

A buyer purchases a bounded evaluation of one consequential decision against agreed evidence and acceptance criteria. Scope output makes ownership, disclosures, exclusions and estimated contribution visible. Prices and costs supplied in the form are hypotheses. No contract, invoice, buyer commitment, revenue, savings or market price is inferred. Source and verification remain portable after the engagement. Independent customer acceptance and production qualification remain outstanding.

## Maintenance and custody

This directory is self-contained: runtime never imports sibling tools. Frozen donor ZIPs are exact delivery snapshots, not forks silently patched by this runner. Refresh a donor only through a reviewed source revision, new release identity and full qualification. scripts/build.py stages deterministic distribution archives. tests/test_workbench.py owns orchestration and refusal checks. Generated data/release.json and release.js are allowlisted observations; downloads are reproducible build objects. All other files are steward-owned. Private outreach and customer materials remain outside this public repository.
