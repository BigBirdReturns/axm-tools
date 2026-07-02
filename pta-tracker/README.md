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

## Operating manual (the human 10%)

Everything here is done by editing **`data/parent.json`** in GitHub's web
editor — the page's ✎ links open it directly. No local tools, works from a
phone. Every edit is a commit, so the whole curation history is inspectable
and the next officer inherits it.

**Who can edit what.** Reading is public: one URL, no accounts, no app.
Writing is GitHub repo permission — no shared password anywhere. Repo
collaborators edit directly (commit → the site redeploys itself, everyone
sees one truth); anyone else who clicks ✎ can only *propose* a change from
their own GitHub account, which sits in the pull-request queue until a
collaborator approves it — moderation for free. Succession is a grant, not
a secret: add the incoming officer as a collaborator, remove the outgoing
one. If more officers ever need durable shared ownership, create a free
GitHub organization and transfer the repo into it (all URLs redirect); the
repo being public means the full record is cloneable and survives any
single account.

**Acting on a watchlist flag.** A red "expected by … — not seen yet" line
means a scheduled obligation hasn't been verified. Click its check link
(usually Simbli minutes or a district page), confirm reality, then hit
**✎ mark done** and set that item's `"status"` to `"done"`. Done items show
a ✓ receipt for 45 days, then retire themselves.

**Writing a parent card.** A card is a *consequence with an owner*, not a
headline. It answers three questions in order: what changes for my kid
(`kid_impact`, one sentence), who decided it (`owner`), and what — if
anything — a parent can do (`action`, at most one). If you can't name the
owner, it isn't ready to be a card. The **→ parent card** link on any VP
Desk item copies a pre-filled draft (`WRITE ME` markers where a human
sentence is required) and opens the editor; paste it into `coming_up` or
`in_effect` and replace the markers.

**Calendars.** Give a `coming_up` card a `"when"` (`YYYY-MM-DDTHH:MM`, local
time; optional `"duration_min"` and `"location"`) and the card grows
add-to-calendar links — a Google Calendar template URL and a downloadable
`.ics` for iPhone/Apple Calendar/Outlook, generated entirely in the page.
Scraped board meetings on the VP Desk get the links automatically (7:00 p.m.,
boardroom).

**What falls off, and when.** Nothing is deleted; things retire on
schedule:

| Surface | Rule |
|---|---|
| VP Desk live feed | 120 most recent items; older move to `data/archive.json` |
| Timeline search | never forgets — searches live feed + archive together |
| `coming_up` cards | hidden the day after their `until` date |
| `in_effect` cards | stay until the officer retires them (laws don't expire on a timer; review at semester turnover) |
| Watchlist, open | red flag forever until marked done — a blank where a report should be is a finding |
| Watchlist, done | ✓ receipt for 45 days past its date, then hidden |

**Searching back.** The VP Desk search box covers every item ever tracked,
grouped by month — "what did we know about phones in March" is one query,
with the original links and statute citations intact.

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
