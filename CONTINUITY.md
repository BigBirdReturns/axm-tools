# CONTINUITY — the handoff document

**Audience:** whoever maintains this repo next — a human, or an AI agent of
any vendor, in any year. Sessions are ephemeral; this file is the memory
that survives them.

**Contract:** this file tells you what must survive, what is allowed to
rot, and how to change things legitimately. The rest of the repo tells you
how things currently work. When the two disagree, reality outranks prose —
see §8, rule 1.

**Read order for a fresh session:**
1. `README.md` — what this repo is, the tool conventions
2. this file — the invariants and change control
3. `CLAUDE.md` — the verified-quirks ledger (named for the tooling that
   started it; whatever model you are, treat it as the shared field notes)
4. the README of the tool you are touching
5. `git log` on `main` — the authoritative record of what actually happened

---

## 1. The bet this repo makes

A toolbox of small, self-contained tools: scheduled jobs for compute,
committed plain-text state, static pages for the interface. No servers,
no databases, no API keys, no bills.

The bet is **convention over dependency**. Anything shared is a
dependency; every dependency needs maintenance; this repo is designed for
years of zero attention. A tool must still work after being ignored for a
year. The repo must still be maintainable after being ignored for ten.
Every design choice below falls out of that bet — if you find yourself
"improving" one, first work out which part of the bet you are breaking.

## 2. The three layers

Everything here belongs to one of three layers. Knowing which layer you
are touching tells you how much care to take.

### Invariants — change only with the owner's explicit, recorded decision
1. **One directory per tool, fully self-contained.** Tools never import
   from each other and share no library. Convention is copyable and rots
   alone; shared code rots everything at once.
2. **Nothing that can bill, expire, or be revoked.** Compute is scheduled
   and disposable; state is committed plain text in the tool's own
   `data/`; the interface is static files. No package manifests, no keys.
3. **`main` is production.** Every commit to `main` must leave the tree
   publishable — the whole repo root is served. No scratch files, ever.
4. **Fail loud or show it.** Total failure exits nonzero so the platform
   alerts the owner; partial failure is visible on the tool's own page.
   Silent staleness is the only fatal failure mode a zero-maintenance
   tool has.
5. **The hostile-source seam.** Every fetcher honors an out-of-band
   drop-box (`<tool>/data/observed.json`) for sources that block
   automation. Route around blockades; never fight one from inside a
   datacenter — that is a war of attrition you lose.
6. **Machine-owned and human-owned files are never confused** (§4).
7. **Frozen records are never edited** (§6).
8. **Plain text wherever a human might one day recover state by hand.**

### Conventions — changeable, but a change must be documented where the convention is defined
- The tool layout: `README.md` + `index.html` + `scripts/` + `data/`
  (tools may grow extra self-contained files — a service worker, a
  manifest — as `pta-tracker/` has; that is growth, not violation).
- Workflows at the repo root, named `<tool>-<job>.yml`, touching only
  their own tool's `data/`.
- The site deploy runs in the same workflow as any data commit (CI-token
  pushes do not trigger other workflows — re-verify this property on any
  new platform before trusting a standalone deploy job).
- Python, stdlib only. The *language* is convention; the "no third-party
  packages" property behind it is invariant #2.

### Implementations — expected to rot; replace freely, keep the invariant
- GitHub itself: Actions, Pages, runner images, workflow syntax (§7).
- Every feed URL, scraper, page format, CSS trick, font CDN.
- Python-the-language and HTML-the-format. If the decade replaces them,
  migrate — the properties (stdlib-equivalent, no build step, one static
  artifact) are what must survive, not the file extensions.

## 3. Map (snapshot, July 2026 — trust the tree over this list)

- `acceptance.html` — the buyer-facing OSW equipment-evidence challenge:
  one offline page that exercises physical-availability findings against
  synthetic or sponsor-provided operational exports. Its real browser path is
  guarded by `tests/pages/verify_acceptance.mjs`.
- `pta-tracker/` — the living tool: nightly legislation fetch for a K-6
  PTA, relevance filter, board report, offline PWA. Its README is the
  operating manual.
- `identity/` — a **reference area, not a tool** (§6): the AXM/SCG
  identity system, its frozen releases, and the provenance law.
- `index.html` — the root directory page. Tools get cards; reference
  areas get a quieter link.
- `.github/workflows/pta-fetch.yml` — nightly fetch + data commit + site
  deploy, in one workflow, deliberately.

## 4. File ownership

- **Machine-owned** (workflow writes them; hand edits get overwritten or
  merged away): `*/data/items.json`, `pta-tracker/data/archive.json`.
- **Human-owned** (the machine only reads or merges them):
  `*/data/observed.json`, `pta-tracker/data/parent.json`.
- **Frozen** (nobody edits them, §6): `identity/scg/releases/*`.
- **Steward-owned** (you, subject to the layers above): everything else.

Rule for new tools: the tool's README must declare which of its files are
machine-owned. Undeclared means human/steward-owned.

## 5. Rot playbook

- **One source goes quiet** → visible in the tool's health line; the run
  stays green by design. Before re-adding or "fixing" a source, check the
  quirks ledger — some sources are excluded on purpose (verified blocks).
- **All sources die at once** → the job exits nonzero and the owner gets
  email. Usually a platform or network change, not a content change.
- **A scraped page changes shape** → most scrapers here read
  human-written pages that get rearranged on human schedules (school
  years, redesigns). Fix the parser; keep it stdlib.
- **A source starts blocking automation** → do not escalate. Move it
  behind the `observed.json` seam and let a human or an on-device
  observer feed it.
- **Platform deprecation** (workflow syntax, runner image, Pages config)
  → mechanical fix; verify with one manually-triggered run and read its
  logs end to end.
- **Platform death** → §7.
- **You are a new steward and nothing has been touched for years** → run
  the newest workflow manually, read its logs, diff `data/` before and
  after, open the site. The repo is designed to self-describe; distrust
  any doc older than the last format change you can see in `git log`.

## 6. Frozen records and reference areas

`identity/` is governed by its own internal law —
`identity/scg/SCG_MARK_CONSTITUTION.md` — which outranks taste, including
yours. Read it before touching anything there. The rules that generalize
to any future reference area:

- **A frozen release is never edited after freeze** — not even to fix
  errors. The frozen copy preserves the ratified state; a change is a new
  `vX/` folder. (Current: `SCG-Identity-v3.1` is the deployment
  reference; `v3.0` is the ratified baseline beneath it.)
- **When a living doc contradicts reality, fix the doc** with a dated,
  string-only note. **When reality outgrows a frozen record, cut a new
  frozen version.** Never the reverse in either case.
- The identity docs reference paths from a larger axm.tools monorepo
  (a root-level `scg-pixel-mark.js`, `/public/assets/scg/`) that do not
  exist in this repo. This is known and reconciled — see the "Deployment
  scope" sections. Do not "fix" those paths to match this repo.
- The mark is rendered live from
  `identity/scg/source/scg-pixel-mark.js`. Never copy it elsewhere in
  this repo, never redraw it, never center it, never tidy it.

## 7. Platform migration — when GitHub (or its successor) dies

The repo needs exactly three replaceable services:

1. **A git host.** History is the database, the audit log, and the
   archive (removed things are recovered from history, not from backups).
   Migrate with full history; never squash it away.
2. **A scheduler** that can run stdlib Python nightly and commit the
   result. Any CI system, any cron box with a deploy key.
3. **A static file server** pointed at the repo root.

Total coupling to GitHub today: workflow YAML syntax, the Pages deploy
steps, the CI-token commit pattern, and "a failed job emails the owner."
All four have equivalents everywhere. When migrating, wire the **alert
channel first** — fail-loud is an invariant, and a migration that loses
the owner's failure emails has silently broken the most important thing.

## 8. Rules for AI stewards

Written from experience in this repo, not theory:

1. **Verify before believing — including this file.** Docs here have
   confidently described deployments that did not exist. The tree, a live
   run, and `git log main` outrank any prose, and prose that disagrees
   with reality is a bug to fix, not an instruction to follow.
2. **Do not improve the constraints.** stdlib-only, no build step, no
   frameworks, read-only pages — each was chosen against the alternative
   you are about to suggest. The constraints are the product.
3. **Everything you commit to `main` is published, immediately.**
4. **Surgical diffs.** Sessions run in parallel here; re-apply small edits
   by hand on top of others' work rather than overwriting files
   wholesale. Wholesale overwrite is how one session clobbers another's
   fix.
5. **Extend the quirks ledger** (`CLAUDE.md`) whenever you *verify* a new
   fact about the outside world — a block, a format, a recycled
   identifier. Date it. Verified quirks are the most valuable thing a
   session can leave behind.
6. **Write commit messages for a reader ten years out:** what changed and
   why, in plain language, no session jargon.
7. **Reversible + in-scope → act and document. Destructive or
   outward-facing → leave a written recommendation instead.** When the
   owner has decided something before, do not relitigate it.
8. **Leave a trail when you leave.** If your session ends mid-work,
   commit what is coherent, push it, and state plainly in the message
   what is unfinished.

## 9. Changing this document

This file is living: edit it in place; git is its history. If you change
a Convention, update §2 in the same commit that changes the convention.
If you believe an Invariant is genuinely wrong, that is the owner's
decision — write the case down (commit message or issue), don't just do
it. Keep the §3 map honest whenever the top-level tree changes.

## 10. The spirit clause

When something arrives that this file did not anticipate — a new
platform, a new format, a new kind of tool, a new kind of steward —
choose the option that still works after ten years of nobody looking at
it. Fewer moving parts beats more features. Visible failure beats silent
cleverness. Convention beats dependency. Plain text beats everything.
