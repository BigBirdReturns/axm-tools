# PTA Legislation Tracker

A zero-maintenance, district-first tracker for what parents at an Arcadia USD
K-6 campus need to know. Built for the Holly Avenue Elementary PTA. It does
the VP-Legislation job: watch the district and the state, filter for
relevance, and generate the monthly board report on demand.

## How it works

1. A GitHub Action (`.github/workflows/pta-fetch.yml`) runs nightly. It can
   also be run on demand from the Actions tab. Sources, district first:
   - **AUSD News RSS** — the district's own announcements
   - **AUSD board-meeting schedule** — scraped from the district agenda page;
     meetings in the next 3 weeks become priority items linking to the Simbli
     agenda system (Simbli itself is behind bot protection, so agendas are
     linked for humans, not scraped)
   - **Google News query for "Arcadia Unified"** — local press coverage
   - **State feeds** — LAist Education, the CDE "What's New" feed, and a
     Google News query for California K-12 legislation that catches
     everything else. EdSource journalism arrives through that query;
     edsource.org itself 403s all datacenter IPs, and keeping a
     permanently-dead feed in the list would only teach the owner to
     ignore the source-health warning
2. `scripts/fetch.py` filters with keyword rules. District items keep
   anything actionable (policy, budget, boundaries, safety, calendar, board
   meetings — hot) and drop the awards-and-celebrations firehose. State items
   are tiered **hot** (elementary-school direct: cellphone policy, school
   safety, background checks, TK, special ed, Arcadia) and **normal** (general
   K-12 policy); higher-ed noise is dropped. Anything published more than 120
   days ago is skipped.
3. Items collected out-of-band land in `data/observed.json` and merge in
   unfiltered. This is the escape hatch for sources that block datacenter
   IPs: the Action can never read a Simbli agenda through Incapsula, but a
   human can paste one in — or a local
   [ScreenGhost](https://github.com/BigBirdReturns/screenghost) observer can
   read it off a real device's screen, which bot protection cannot
   distinguish from the paying customer it must let through. Only `title`
   is required; everything else defaults sensibly (see the file's `note`).
4. Any bill reference (AB 3216, SB 848, ...) is resolved to the actual
   statute text on leginfo.legislature.ca.gov — news is someone's
   interpretation; the link goes to the black-letter law. Bill numbers are
   recycled every two-year session, so the fetcher probes recent sessions
   and matches the official subject against the story before linking.
   Resolved links are cached in the data file, one lookup per item ever.
5. Results are committed to `data/items.json`, along with a per-source
   health record — one dead feed keeps the run green, so the page says
   which sources went quiet instead of leaving an empty district section
   as the only tell (red warning if it's a district source).
6. `index.html` is a static page (GitHub Pages) with **All / Our district /
   Priority** filters and a **Generate PTA report** button producing a
   paste-ready monthly update — district section first, law-text links
   included.

No server, no database, no API keys, no dependencies (Python stdlib only).
Cost: zero.

## Deploy

Already live for this repo — the nightly workflow fetches, commits data, and
deploys Pages in one run. To stand up a fresh copy elsewhere:

1. Copy `pta-tracker/` and `.github/workflows/pta-fetch.yml` into a public
   repo.
2. **Settings -> Pages** -> Source **"GitHub Actions"**. The fetch workflow
   deploys the site itself — fetch, commit data, upload the repo root,
   deploy, all in one run — and the site lives at
   `https://<user>.github.io/<repo>/pta-tracker/`. The deploy step is
   inside the fetch workflow deliberately: the nightly data commit is
   pushed with the built-in `GITHUB_TOKEN`, and such pushes never trigger
   other workflows, so a separate on-push Pages workflow would deploy on
   human merges but silently skip every nightly refresh.
3. **Actions** -> run **"PTA tracker fetch + deploy"** once via
   *Run workflow*. That first run publishes the site; after that it
   redeploys nightly and on every push to the default branch.

`data/items.json` ships pre-seeded with the four education laws that took
effect July 1, 2026, so the page renders meaningfully before the first
nightly run.

## Tuning relevance

Edit the `HOT`, `WARM`, `COLD`, `DISTRICT_HOT`, and `DISTRICT_SKIP` regex
lists at the top of `scripts/fetch.py`. Everything is a plain regex against
title+summary.

## Roadmap (v2, optional)

- LegiScan API for direct bill-status tracking (free key) with status badges
- Automated Simbli agenda capture via a ScreenGhost observer on a locally
  attached device, writing `data/observed.json` (see
  [ScreenGhost's PTA example](https://github.com/BigBirdReturns/screenghost/blob/main/examples/pta_agenda_observer.md));
  until someone runs one, meeting items deep-link to Simbli for a human
  skim, and anything notable can be pasted into `observed.json` by hand
- LLM summarization pass for plain-language rewrites (the rule-based v1
  intentionally avoids any API dependency)
- Email digest via Actions + a mailing step

## Provenance note

Rule-based filtering means false negatives are possible. Anything you plan to
report to parents, verify against the linked primary source. The tracker is a
net, not an oracle.
