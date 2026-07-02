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
   - **State feeds** — LAist Education, the CDE "What's New" feed, EdSource
     (currently 403s from datacenter IPs, tolerated), and a Google News query
     for California K-12 legislation that catches everything else, including
     syndicated EdSource stories
2. `scripts/fetch.py` filters with keyword rules. District items keep
   anything actionable (policy, budget, boundaries, safety, calendar, board
   meetings — hot) and drop the awards-and-celebrations firehose. State items
   are tiered **hot** (elementary-school direct: cellphone policy, school
   safety, background checks, TK, special ed, Arcadia) and **normal** (general
   K-12 policy); higher-ed noise is dropped. Anything published more than 120
   days ago is skipped.
3. Results are committed to `data/items.json`.
4. `index.html` is a static page (GitHub Pages) with **All / Our district /
   Priority** filters and a **Generate PTA report** button producing a
   paste-ready monthly update — district section first.

No server, no database, no API keys, no dependencies (Python stdlib only).
Cost: zero.

## Deploy

```bash
# from the repo root
git add pta-tracker
git commit -m "add PTA legislation tracker"
git push
```

Then in the GitHub repo settings:

1. **Pages** -> deploy from branch `main`, folder `/` (the site will live at
   `https://<user>.github.io/axm-tools/pta-tracker/`).
2. **Actions** -> confirm the workflow is enabled. Run it once manually via
   *Run workflow* to verify.

`data/items.json` ships pre-seeded with the four education laws that took
effect July 1, 2026, so the page renders meaningfully before the first
nightly run.

## Tuning relevance

Edit the `HOT`, `WARM`, `COLD`, `DISTRICT_HOT`, and `DISTRICT_SKIP` regex
lists at the top of `scripts/fetch.py`. Everything is a plain regex against
title+summary.

## Roadmap (v2, optional)

- LegiScan API for direct bill-status tracking (free key) with status badges
- Simbli agenda-item scrape if their bot protection ever allows it (until
  then, meeting items deep-link to Simbli for a human skim)
- LLM summarization pass for plain-language rewrites (the rule-based v1
  intentionally avoids any API dependency)
- Email digest via Actions + a mailing step

## Provenance note

Rule-based filtering means false negatives are possible. Anything you plan to
report to parents, verify against the linked primary source. The tracker is a
net, not an oracle.
