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
3. Items collected out-of-band land in `data/observed.json` and merge in
   unfiltered. This is the escape hatch for sources that block datacenter
   IPs: the Action can never read a Simbli agenda through Incapsula, but a
   human can paste one in — or a local
   [ScreenGhost](https://github.com/BigBirdReturns/screenghost) observer can
   read it off a real device's screen, which bot protection cannot
   distinguish from the paying customer it must let through. Only `title`
   is required; everything else defaults sensibly (see the file's `note`).
4. Results are committed to `data/items.json`, along with a per-source
   health record — one dead feed keeps the run green, so the page says
   which sources went quiet instead of leaving an empty district section
   as the only tell (red warning if it's a district source).
5. `index.html` is a static page (GitHub Pages) with **All / Our district /
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

0. **Branches** -> if the default branch isn't `main` yet (repos bootstrapped
   from a working branch often aren't), rename it to `main` here first.
   GitHub retargets open PRs and redirects clones automatically; the nightly
   workflow follows the default branch whatever its name, but Pages, the
   badge URLs, and everyone's muscle memory expect `main`.
1. **Pages** -> Source **"Deploy from a branch"**, branch `main`, folder `/`
   (the site will live at
   `https://<user>.github.io/axm-tools/pta-tracker/`). This choice matters:
   the nightly job publishes by *committing* `data/items.json`, and
   branch-served Pages redeploys on every commit. If Pages is ever switched
   to the "GitHub Actions" source, the site freezes at its last deploy and
   the data stops updating even though the nightly run stays green. The
   `.nojekyll` file at the repo root keeps those redeploys fast and
   Jekyll-free.
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
