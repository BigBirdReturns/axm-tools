# Pelagos Governance Layer v0.3.0

`pelagos-governance/` is a public-safe, local-first company-state workbench for Pelagos Frontier Technologies. It reconstructs the public relationship, instrument, claim, evidence, rights, and authority surfaces already visible around Vantage, then provides a private local intake and decision path without uploading source files or performing external actions.

The release is **DDV-PEL-003**, prepared by Dependable DaVincis as a Robi Sen Collaboration. The public cartridge is operator-qualified. It becomes a Pelagos working copy only when an authorized Pelagos operator opens **Today → Admit working copy**, names the decision, technical, communications, and custody owners, and cites the exact authority source. Until that admission, the interface remains an outside-in candidate rather than Pelagos corporate state.

## Readiness boundary

The tool is ready for immediate founder-controlled use as a **single-writer local operating layer**. It can ingest live relationships and agreements, hash supporting files, preserve successor states, draft or authority-attribute decisions, test claims and rights, and export encrypted portable custody.

It is not yet:

- a Pelagos system of record before Pelagos admits a working copy;
- a shared multi-user service or cloud synchronization layer;
- legal advice, export-control classification, investment advice, technical certification, or procurement representation;
- an email, calendar, payment, signature, publication, CRM, or source-system writeback adapter;
- a substitute for the underlying signed instrument, source file, test evidence, or corporate authority.

One designated custodian should operate the working copy. Parallel edits in multiple browsers will diverge. Each meaningful session ends with a full workspace export and an encrypted backup.

## What opens immediately

The frozen public cartridge contains:

- eighteen public counterparties or actor classes;
- fourteen instruments and relationship surfaces;
- fifty-four normalized claims with allowed language and prohibited upgrades;
- thirteen evidence records that state both what they prove and what they do not;
- ten rights surfaces;
- twenty-eight exceptions and ten founder decisions;
- forty invariants and separate relationship, capital, capability, claim, and authority state tracks;
- prospective qualification plans for every high- or critical-risk claim;
- ten built-in stress scenarios;
- fourteen source records;
- seven role profiles and four aperture projections;
- a lineage ledger showing which mechanism was retained from earlier AXM tools.

No private introduction email, source body, company instrument, customer identity, investor identity, or confidential technical artifact is committed.

## First private operating session

Use `standalone.html` for private work. It contains the entire application, public cartridge, style, and runtime in one file and makes no network request.

1. Open **Today** and choose **Admit working copy**.
2. Name the company label, decision owner, technical owner, communications owner, single custodian, and exact authority source. Admission creates a local authority assertion and chained receipt. It does not alter the public release.
3. Open **Evidence** and select the current SAFE, MOUs, partner agreements, test reports, deck, and any source material needed for a live decision. The browser computes SHA-256. Source bytes are not retained. Duplicate bytes are refused.
4. Open **Docket → Local intake** and create one record for every live investor, government contact, customer, partner, advisor, in-kind offer, technical claim, and public statement. Attach the relevant local source receipts.
5. Record later changes as **successor states**. The effective view shows the latest successor while the earlier state remains in the workspace and receipt chain.
6. Open **Claims**, **Instruments**, and **Decisions** to correct public language, separate consideration and rights, and record the smallest number of authority-bearing decisions.
7. Run **Stress**, then open **Handoff**. Verify the receipt chain, run cold replay, export the full workspace, and create an encrypted backup.

The hosted GitHub Pages copy is suitable for inspection and public-safe demonstration. Private instruments and confidential records should be loaded only into a locally saved `standalone.html` copy or another operator-approved private device context.

## Daily operating loop

1. Capture the new object.
2. Identify the counterparty and every role it occupies.
3. Classify relationship, instrument, capital, capability, claim, evidence, rights, and authority states separately.
4. Attach source identity and exact evidence.
5. Name the owner, authority source, next decision, expiry, and external-effect boundary.
6. Record the authorized successor state; never overwrite the prior state.
7. Export custody before closing the session.

## Apertures and roles

The interface exposes internal, public-safe, diligence, and counsel-residue apertures over one immutable baseline. Founder, technical, communications, capital, counsel, successor, and public roles change emphasis and available preparation. They never change evidence or grant authority.

## Source intake and custody

Files stay in the browser. Every selected file receives name, media type, byte length, SHA-256, parser disposition, duplicate status, and optional object link. Source bytes are not retained. JSON, CSV/TSV, NDJSON, Markdown, and text receive bounded local inspection; unsupported formats remain valid hash-only source objects instead of disappearing.

Imported HTML is never executed. A complete workspace import uses an interruption journal, validates the schema before replacement, and preserves the prior workspace until acceptance succeeds. Version 0.2 workspace packets are migrated into the version 0.3 schema during validated import.

## Decisions, corrections, and receipts

The committed public cartridge is immutable. Workspace admission, corrections, decisions, source receipts, intake records, successor states, stress runs, imports, exports, and resets append to a local receipt chain. Each receipt binds the previous hash, actor role, object, action, time, and payload. Ledger verification recomputes the chain.

A local decision does not create company authority. Missing authority leaves the decision in draft state. A local object is authority-attributed only when it cites both an authority source and at least one source receipt. No interface control sends, publishes, pays, schedules, signs, accepts, represents, or writes back.

## Exports

- **Full workspace**: public baseline identity plus private local records, successor history, corrections, decisions, sources, stress runs, authority assertions, and receipts. No original source bytes.
- **Public projection**: immutable public cartridge plus explicitly public local amendments only.
- **Diligence projection**: claims, instruments, evidence, rights, exceptions, and source-receipt metadata without private narrative bodies.
- **Counsel residue**: concrete unresolved questions with actor, venue, source, proposed action, and consequence of yes, no, or unknown.
- **Encrypted backup**: PBKDF2-SHA-256 with 250,000 iterations and AES-GCM-256, created entirely in the browser.
- **CSV extracts**: claims, instruments, and effective local objects.
- **Standalone application**: `standalone.html`, the complete private-use application with no build step or external service.

## Validation

Run the static and data-contract validator:

```bash
python pelagos-governance/scripts/validate.py
```

Run JavaScript syntax checks:

```bash
for f in pelagos-governance/app/*.js pelagos-governance/data/parts/*.js; do node --check "$f"; done
```

Run the browser campaign after installing Playwright and Chromium:

```bash
node pelagos-governance/tests/verify.mjs
```

The browser campaign exercises startup, workspace admission, source hashing, duplicate refusal, local intake, successor-state preservation, draft-versus-authority decisions, claim correction, stress, export, encryption/decryption, receipt verification, cold succession, reduced motion, 320-pixel rendering, the standalone bundle, and zero unexpected external requests.

## File ownership

- `index.html`, `standalone.html`, `app.css`, `app/*.js`, `README.md`, `CONSTITUTION.md`, `LINEAGE.md`, `scripts/`, and `tests/` are steward-owned.
- `data/parts/*.js` is the frozen, segmented public cartridge for release 0.3.0. Each segment contains one JSON-valued top-level object and no behavior beyond assignment. A factual correction creates a successor release rather than editing the released object after publication.
- `QUALIFICATION.json` is generated deterministically by `scripts/validate.py` and must match the committed release.
- No file is machine-owned at runtime. Private local workspaces remain with the operator and are never committed automatically.

## What can rot

Browser support for IndexedDB, Web Crypto, File input, Blob downloads, `<dialog>`, PBKDF2/AES-GCM, and local storage can change. GitHub Pages and the disposable Playwright CI environment can change. A failure must remain visible, and portable JSON export must remain available whenever the browser can execute JavaScript.

The application must never respond to rot by adding a cloud dependency, silently dropping an unsupported source, fabricating missing private state, weakening the public/private boundary, replacing successor history with in-place mutation, or converting a local draft into external authority.
