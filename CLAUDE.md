# axm-tools — notes for Claude sessions

Read the root `README.md` first: it defines the repo's conventions (one
self-contained tool per directory, stdlib-only Python, committed-JSON state,
Pages deployed from the fetch workflow). Those conventions are deliberate —
don't add dependencies, build steps, or shared libraries to "improve" things.

Before any structural decision (new directory, changed convention, platform
work), read **`CONTINUITY.md`** — the long-horizon handoff document. It
separates the invariants from the parts that are allowed to rot, and it is
written for whoever maintains this repo next, human or model. This file is
the *quirks ledger* that CONTINUITY.md §8 refers to: when you verify a new
fact about the outside world, add it below and date it.

## Ground rules

- **Python is stdlib-only.** No requirements.txt exists on purpose. If a
  task seems to need a package, it needs a different approach instead
  (`pta-tracker/scripts/fetch.py` parses RSS/Atom with `xml.etree` for this
  reason — `feedparser`'s sgmllib3k dependency doesn't even build on modern
  setuptools).
- **`main` is production.** Pages serves the repo root; every merge and
  every nightly data commit redeploys the live site. Don't leave scratch
  files anywhere in the tree — they get published.
- **Machine-owned files:** `*/data/items.json` and
  `pta-tracker/data/archive.json` (append-only overflow of the live feed;
  the page's timeline search depends on it) are written by the nightly
  workflow; hand edits will be overwritten or merged away. The human-owned
  data files are `*/data/observed.json` (out-of-band drop-box) and
  `pta-tracker/data/parent.json` (curated parent-view cards + watchlist).
  The page is deliberately read-only — the owner rejected on-page edit
  buttons that bounce volunteers to a GitHub login; don't add them back.
  Curation = editing parent.json in the repo (web editor or a Claude
  session).

## Testing changes locally

```bash
# sandboxed environments: exports make the proxy CA visible to urllib
SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 pta-tracker/scripts/fetch.py
# then eyeball the site (fetch is relative, so serve the tool dir):
cd pta-tracker && python3 -m http.server 8899
```

Run `fetch.py` against a **copy** of the data dir if you don't want the run
merged into `data/items.json` — the script merges into whatever is on disk,
and `first_seen` stamps are permanent once committed.

## Known quirks (verified, not guesses)

- **EdSource 403s** every request from datacenter IPs (GitHub runners
  included), which is why it is NOT in `FEEDS` — its stories arrive via
  the Google News query instead. Don't re-add it without verifying the
  block is gone: a permanently-quiet source in the health line trains the
  owner to ignore real outages.
- **Simbli** (AUSD board agendas) is behind Incapsula and cannot be
  fetched by the Action, ever. The escape hatch is `observed.json` — see
  the root README's "hostile-source seam" section. Don't burn time trying
  to scrape it.
- **Google News search feeds return relevant-not-recent** — items can be
  a decade old, hence the `MAX_AGE_DAYS` window in fetch.py.
- **CA bill numbers recycle every 2-year session** (SB 760 = restrooms
  2023-24, behested payments 2025-26, highways 2021-22). Bill links must
  stay disambiguated by subject-vs-story overlap (`find_bills`); a
  "simplification" to newest-session-wins will link parents to the wrong
  law.
- **The AUSD meeting scraper** reads a human-written schedule page
  (`ausd.net/apps/pages/agenda`, refreshed each summer). If meeting items
  vanish during the school year, that page's format is the first suspect.
- **One dead feed is silent by design** (run stays green; the page's
  per-source health line is the tell). All feeds dead = exit nonzero so
  GitHub emails the owner.

## identity/ (reference area, not a tool — verified July 2026)

- **No workflow, no `data/`, deliberately.** Don't fit it into the tool
  layout. Its internal law is `identity/scg/SCG_MARK_CONSTITUTION.md` —
  read it before touching anything under `identity/`.
- **`releases/` folders are frozen.** Never edit one, even to fix an
  error; a change is a new `vX/` folder. `SCG-Identity-v3.0` is the
  ratified baseline; `v3.1` is the current deployment reference
  (application-layer only: the LinkedIn cover is wordmark-only because
  the avatar already carries the mark — never two dandelions at once).
- **The docs there name paths from the full axm.tools monorepo** (a
  root-level `scg-pixel-mark.js`, `/public/assets/scg/`) that don't exist
  in this repo. Already reconciled via "Deployment scope" notes in the
  living docs — don't "fix" the paths, and don't let a merge overwrite
  those notes (re-apply small edits by hand instead).
- **The mark renders live from `identity/scg/source/scg-pixel-mark.js`**
  (the showcase at `identity/index.html` draws all 79 cells from it).
  Never copy the file elsewhere in this repo, never redraw the mark.

## History worth knowing

Multiple sessions built this in parallel; `git log` on `main` is the
authoritative record. The v1 single-view page was archived, then removed —
recover it from history (`git log --all -- pta-tracker/index-v1-archive.html`)
rather than rewriting it. The `identity/` area landed across PRs #5 and #7
(July 2026); the second exists because a PR merged mid-session strands any
later commits on its branch — a merged PR never picks up new pushes, so
follow-ups need a fresh PR from a restarted branch.
