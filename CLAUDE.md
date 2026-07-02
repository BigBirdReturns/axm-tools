# axm-tools — notes for Claude sessions

Read the root `README.md` first: it defines the repo's conventions (one
self-contained tool per directory, stdlib-only Python, committed-JSON state,
Pages deployed from the fetch workflow). Those conventions are deliberate —
don't add dependencies, build steps, or shared libraries to "improve" things.

## Ground rules

- **Python is stdlib-only.** No requirements.txt exists on purpose. If a
  task seems to need a package, it needs a different approach instead
  (`pta-tracker/scripts/fetch.py` parses RSS/Atom with `xml.etree` for this
  reason — `feedparser`'s sgmllib3k dependency doesn't even build on modern
  setuptools).
- **`main` is production.** Pages serves the repo root; every merge and
  every nightly data commit redeploys the live site. Don't leave scratch
  files anywhere in the tree — they get published.
- **Machine-owned files:** `*/data/items.json` is written by the nightly
  workflow; hand edits will be overwritten or merged away. The human-owned
  data files are `*/data/observed.json` (out-of-band drop-box) and
  `pta-tracker/data/parent.json` (curated parent-view cards).

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
  included). Expected warn-line noise, not a bug; its stories arrive via
  the Google News query instead.
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

## History worth knowing

Multiple sessions built this in parallel; `git log` on `main` is the
authoritative record. The v1 single-view page was archived, then removed —
recover it from history (`git log --all -- pta-tracker/index-v1-archive.html`)
rather than rewriting it.
