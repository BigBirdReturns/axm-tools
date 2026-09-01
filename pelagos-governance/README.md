# Pelagos Governance Layer v0.2.0

`pelagos-governance/` is a public-safe, local-first company-state workbench for Pelagos Frontier Technologies. It reconstructs the public relationship, instrument, claim, evidence, rights, and authority surfaces already visible around Vantage, then provides a private local intake and decision path without uploading source files or performing external actions.

The public release is **DDV-PEL-002**, prepared by Dependable DaVincis as a Robi Sen Collaboration. It is a candidate architecture, not a Pelagos-accepted system or engagement deliverable.

## What opens immediately

The committed cartridge contains:

- eighteen public counterparties or actor classes;
- fourteen instruments and relationship surfaces;
- fifty-four normalized claims with allowed language and prohibited upgrades;
- thirteen evidence records that state both what they prove and what they do not;
- ten rights surfaces;
- twenty-eight exceptions and ten founder decisions;
- forty invariants and separate relationship, capital, capability, claim, and authority state tracks;
- prospective qualification plans for every high-risk claim;
- ten built-in stress scenarios;
- a lineage ledger showing which mechanism was retained from each earlier AXM tool.

No private introduction email, source body, company instrument, customer identity, investor identity, or confidential technical artifact is committed.

## Five-minute operating route

1. Open **Today**. The page presents one recommended action and the highest-consequence safe secondary moves.
2. Open **Docket** and add each live investor, government, customer, partner, advisor, or in-kind object through local intake.
3. Open **Claims** and inspect the allowed language, prohibited upgrade, evidence boundary, owner, and qualification plan.
4. Open **Instruments** and make consideration, rights, authority, performance, expiry, and exit explicit.
5. Open **Evidence** and select local files. The browser computes SHA-256, refuses duplicates, and retains hash-only source receipts by default.
6. Open **Decisions** to record a local draft or an authority-attributed decision. The page creates a chained receipt but performs no outside act.
7. Run **Stress**, then open **Handoff** to verify the receipt chain, run cold succession, export public/diligence/counsel/full packets, and create an encrypted backup.

## Apertures and roles

The interface exposes internal, public-safe, diligence, and counsel-residue apertures over one immutable baseline. Founder, technical, communications, capital, counsel, successor, and public roles change emphasis and available preparation; they never change evidence or grant authority.

## Source intake and custody

Files stay in the browser. Every selected file receives name, media type, byte length, SHA-256, parser disposition, duplicate status, and optional object link. Source bytes are not retained. JSON, CSV/TSV, NDJSON, Markdown, and text receive bounded local inspection; unsupported formats remain valid hash-only source objects instead of disappearing.

Imported HTML is never executed. A complete workspace import uses an interruption journal, validates the schema before replacement, and preserves the prior workspace until acceptance succeeds.

## Decisions and receipts

The committed public cartridge is immutable. Corrections, decisions, source receipts, intake records, stress runs, imports, exports, and resets append to a local receipt chain. Each receipt binds the previous hash, actor role, object, action, time, and payload. Ledger verification recomputes the chain.

A local decision does not create company authority. Missing authority leaves the decision in draft state. No interface control sends, publishes, pays, schedules, signs, or writes back.

## Exports

- **Full workspace**: public baseline identity plus private local records, corrections, decisions, sources, stress runs, and receipts. No original source bytes.
- **Public projection**: immutable public cartridge plus explicitly public local amendments only.
- **Diligence projection**: claims, instruments, evidence, rights, exceptions, and source-receipt metadata without private narrative bodies.
- **Counsel residue**: concrete unresolved questions with actor, venue, source, proposed action, and consequence of yes, no, or unknown.
- **Encrypted backup**: PBKDF2-SHA-256 and AES-GCM envelope created entirely in the browser.
- **CSV extracts**: claims, instruments, exceptions, and source receipts.
- **Offline application bundle**: the committed `index.html`, `app.css`, `app/*.js`, and frozen `data/parts/*.js` cartridge segments. No build step or external service is required.

## Validation

```bash
python pelagos-governance/scripts/validate.py
for f in pelagos-governance/app/*.js pelagos-governance/data/parts/*.js; do node --check "$f"; done
```

The browser campaign is run in CI:

```bash
python pelagos-governance/tests/browser_test.py
```

It exercises the Today route, role and aperture projections, claim search, file hashing, duplicate refusal, intake, decision receipts, stress campaign, public export, encrypted backup/restore, cold succession, reduced motion, mobile rendering, and zero external or undeclared runtime requests.

## File ownership

- `index.html`, `app.css`, `app/*.js`, `README.md`, `CONSTITUTION.md`, `LINEAGE.md`, `scripts/`, and `tests/` are steward-owned.
- `data/parts/*.js` is the frozen, segmented public cartridge for release 0.2.0. Each segment contains one JSON-valued top-level object and no behavior beyond assignment. A factual correction creates a successor release rather than editing the released object after publication.
- `QUALIFICATION.json` is generated deterministically by `scripts/validate.py` and must match the committed release.
- No file is machine-owned at runtime. Private local workspaces remain with the operator and are never committed automatically.

## What can rot

Browser support for IndexedDB, Web Crypto, File System input, Blob downloads, `<dialog>`, PBKDF2/AES-GCM, and local storage can change. GitHub Pages and the disposable Playwright CI environment can change. A failure must remain visible, and portable JSON export must remain available whenever the browser can execute JavaScript.

The application must never respond to rot by adding a cloud dependency, silently dropping an unsupported source, fabricating missing private state, weakening the public/private boundary, or converting a local draft into external authority.
