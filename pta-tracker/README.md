# PTA Legislation Tracker

A zero-maintenance, district-first tracker for what parents at an Arcadia USD
K-6 campus need to know. Built by the Holly Avenue Elementary PTA and now
serving one page per AUSD elementary school off one shared corpus (see
"Multiple schools" below). It does the VP-Legislation job: watch the district
and the state, filter for relevance, and generate the monthly board report on
demand.

## How it works

1. A GitHub Action (`.github/workflows/pta-fetch.yml`) runs nightly. It can
   also be run on demand from the Actions tab. Sources, district first:
   - **AUSD News RSS** — the district's own announcements
   - **AUSD board-meeting schedule** — scraped from the district agenda page;
     meetings in the next 3 weeks become priority items linking to the Simbli
     agenda system (Simbli itself is behind bot protection, so agendas are
     linked for humans, not scraped)
   - **Holly Avenue's own news RSS** (`ha.ausd.net/apps/news/rss`) — the
     school's own Edlio announcements, scope `"school"` rather than
     `"district"`, so a card built from it is Holly Avenue's voice, not
     AUSD's. Its events feed 403s behind the exact same bot protection as
     Simbli, so it is not in the fetcher's source list either — school
     *events* still need a human or `data/observed.json`, the same escape
     hatch board-meeting agendas use
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
6. Every run also writes `data/gaps.json` — machine-written and rebuilt from
   scratch each time (nothing accumulates, nothing is appended), so it can
   never drift out of sync with the feed it's reporting on. It exists
   because the feed reliably finds things but nothing else signals when a
   hot item never got a parent card — silence on the parent page is
   indistinguishable from "nothing is happening" unless something checks.
   It looks for three shapes of that gap: an **uncovered_hot** item is a
   hot, *local* feed item less than 60 days old that appears in no parent
   card's `covers` list — local meaning district scope or a single school's
   own feed, the same two scopes `score()` reads with one vocabulary, since
   news from your own campus is not less parent-facing than news from the
   district (state-scope hot items are VP-desk context, not automatically
   parent-facing, so those stay exempt). A school-scope gap carries
   `"schools": ["<id>"]` naming the one campus whose page needs the card,
   and is satisfied outright by a card scoped to that campus — it is not
   measured against the whole roster, because news from Holly Avenue was
   never the other five schools' to cover; an **expired_card**
   is a `coming_up` card whose `until` date has already passed and needs
   archiving or replacing; **stale_curation** flags `parent.json` itself
   when its `updated` date is more than 45 days old — except between
   June 20 and August 5, when the district goes quiet for summer and an
   unedited page is the expected state, not a defect, so the check stands
   down for those weeks rather than crying wolf every night of break. The
   file also always records `checked` (this run's timestamp) and
   `reviewed` (how many live items it examined), so a clean run reads as
   "14 items reviewed today, zero gaps" instead of a bare, unfalsifiable
   "all clear" that a broken cron job could produce forever. Deliberately,
   the detector never drafts the missing sentence: it surfaces raw evidence
   (a verbatim snippet copied from the source, the source's own date, the
   URL) and stops there. Automated narrative summarization of policy is the
   documented failure mode this avoids — CNET's AI byline ran at a 53%
   correction rate, and the LA Times' Quakebot once auto-published a 1925
   earthquake as breaking news — and a fluent, ready-to-publish machine
   sentence gets rubber-stamped rather than checked, which is worse than
   no sentence at all. The report lands as one GitHub issue per run,
   opened or updated in place, rather than one alert per gap: a detector
   that pings once for every miss trains its own reader to stop looking,
   and the day it finds the one gap that actually matters is the day it
   gets ignored along with the noise.
7. Every run also writes `data/derived.json` — the fix for this project's
   other durability gap, sitting next to the gap detector rather than inside
   it. A board meeting's date, time, and location are **facts**; the
   scraper already has all of them the moment the agenda page updates. "What
   this means for your kid" is a **consequence**, and that judgment call
   stays human, every time, no exceptions. What moves is the boundary
   between the two: a curator writes a *reusable sentence* once, in
   `data/parent.json`'s `"templates"` key (`board_meeting` today — a title,
   a `kid_impact` line, an owner, a time-sensitivity note, with
   `{weekday}`/`{month}`/`{day}` placeholders), and every nightly run
   instantiates that same sentence with whichever meeting the scraper found,
   producing a `coming_up` card with no new prose written that night. The
   recurring obligation to hand-write a card for a routine, every-few-weeks
   board meeting goes away; the obligation to write and approve the sentence
   the *first* time does not, and never will — a template is still
   human-authored parent-facing text, just written once instead of monthly.
   This is deliberately narrow: it removes the human from the *typing*, not
   from the *interpreting*. Anything genuinely campus-specific, anything
   where "what this means" isn't a rewording of a fact pattern the curator
   already blessed, still gets a hand-written card the normal way — nothing
   about `data/derived.json` reaches into `parent.json` or edits it.
   `data/derived.json` itself is machine-written every run from scratch
   (same posture as `gaps.json`: nothing accumulates, nothing is hand-
   edited, deleting it costs nothing because the next run rebuilds it
   whole), and its cards carry `"derived": true` plus a `"source_item"`
   pointing back at the `items.json` id they were instantiated from, so the
   page can label them and a reader can trace one to its source. A
   hand-written card always wins over a derived one describing the same
   underlying item — the page matches a hand card's `covers` list against a
   derived card's `source_item` and drops the derived card if a human
   already wrote the real thing — so a curator who writes the human version
   early never sees a duplicate auto-card sitting next to it.
   What this does not do: it does not produce a second maintainer. Every
   interpretive card — the ones that are actually about a kid's school
   week, not a meeting's date — still depends on the one VP-Legislation
   officer noticing, judging, and writing. Automating the routine, factual
   cards buys that officer time and lowers the cost of a bad week; it does
   not create a backup for them, and it was never meant to.
8. `index.html` is a static page (GitHub Pages) with **All / Our district /
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

## Multiple schools

Arcadia USD runs six elementary schools, and the tracker's actual job —
watch the district and the state, filter for relevance — doesn't change per
campus. A boundary item, a state cellphone law, a board meeting: the same
card is just as true at Baldwin Stocker, Camino Grove, Highland Oaks, Hugo
Reid, and Longley Way as it is at Holly Avenue. That overlap is the whole
reason one shared corpus can serve all six for close to the curation cost of
one — the rare campus-specific exception gets scoped, everything else is
free.

The real motive is durability, not reach. A tracker maintained by exactly
one PTA officer has exactly one point of failure: the day that officer stops
curating, the page goes stale and nobody notices until a "coming up" card is
quietly a month past its meeting. Six schools sharing a corpus means six
PTAs have a reason to keep it alive, and any one of them picking up the pen
keeps `parent.json` current for the other five. That's the fix for this
project's largest actual risk — which was never the scraper, it was
single-maintainer staleness.

`data/schools.json` is the registry: each school's `id`, `slug`, display
`name`/`short`, `site` (its ausd.net page — used for direct links and for
the `{{school_site}}` action-URL token below), and a `published` flag.
`default` names which school id renders when none is specified at all —
currently Holly Avenue, because that's what the live root URL already
promised, and adding five more schools must not break that promise.

**How school identity reaches the page.** `index.html` never infers a school
from its own URL — that would make every page a special case to maintain.
Instead it reads a `window.SCHOOL` / `window.SCHOOL_BASE` pair, falling back
to `schools.json`'s `default` and `data/` when neither is set. That fallback
is what lets one `index.html` serve as both the live default-school page
(opened directly, nothing injected) and the build template. `scripts/
build_schools.py` runs in CI and, for every **published** school in
`schools.json`, writes `pta-tracker/<slug>/index.html` with a one-line
`<script>` injected before the main script block to set that pair, and the
`<title>`, canonical link, and Open Graph tags rewritten for that school. No
`fetch()` call or route ever changes: the data directory is always resolved
as `window.SCHOOL_BASE || "data/"`, so a per-school page one directory
deeper just points back up at the one shared `data/`.

**Scoping a card to fewer than six schools.** A card in `parent.json` with no
`"schools"` key is district-wide and renders for every school — this will be
true of nearly every card, because nearly every card actually is about the
district or the state. Add `"schools": ["ha", "hr"]` to show a card only at
Holly Avenue and Hugo Reid, for the rare card that's genuinely
campus-specific (a Holly Avenue carnival, a Hugo Reid boundary change).
`"schools": ["*"]` also means district-wide, so a card copied in from
elsewhere with an explicit wildcard doesn't need editing. An action's `url`
can contain the literal token `{{school_site}}`, substituted at render time
with the current school's `site` — this is what lets one written card say
"ask the office where the policy is posted" and have it point at the actual
campus reading the page, instead of six near-duplicate cards differing only
in a URL. The live `parent-sb848` card in `data/parent.json` is exactly that
case: its action url is the literal `"{{school_site}}"`, so the Hugo Reid
page sends a Hugo Reid parent to hr.ausd.net.

**A school id you can't misspell quietly.** `"schools"` values are matched
against `schools.json`'s roster and nowhere else. A typo (`"hz"` for `"ha"`)
therefore matches no school and the card renders on no page — so
`fetch.py`'s gap detector treats that card as covering nothing, keeps the
underlying hot item flagged, *and* raises a separate `unknown_school_ref`
gap naming the card and the bad id. The one thing it deliberately does not
do is treat an unrecognised id as "district-wide": a scope nobody can read
must never silently widen into a scope everybody gets. The page and the gap
detector are held to one written contract for this — see
`SCOPE_CONTRACT_SHA256` in `scripts/fetch.py`.

**`published` gates the build, and the other five schools are parked.**
`schools.json` keeps all six schools as data either way — that shared
roster is the whole reason one corpus can serve six campuses for close to
the curation cost of one — but `build_schools.py` only writes a directory
for a school with `"published": true`. Baldwin Stocker, Camino Grove,
Highland Oaks, Hugo Reid, and Longley Way are **parked**: still fully
described in `schools.json`, not built, not in the deployed tree, not
reachable at any URL. That's a deliberate tightening from this project's
earlier stance of building every school's page regardless of publication
and merely not linking to it — a built-but-unlinked page is still a page a
search engine, a stray link, or a mistyped URL can find, carrying another
PTA's name without that PTA having agreed to anything. Parking removes that
surface entirely instead of just declining to advertise it.
Unparking a school is exactly flipping its `published` flag to `true` and
rerunning `build_schools.py` — nothing else changes, because the corpus
behind it was already correct the whole time. The governance question is
unchanged by any of this: publishing still means that school's PTA
affirmatively said yes — record who, in `published_note` — and saying yes
isn't a free action even then, because every school added multiplies the
surface a factual error can reach while the number of people actually
reviewing `parent.json` before it ships does not grow to match. Add schools
because a PTA asked in, not because the marginal curation cost rounds to
zero — the exposure doesn't round to zero along with it. Re-parking works
the same way in reverse: flip the flag back to `false` and rerun, and the
next build sweeps that school's directory back out.

## Operating manual (the human 10%)

Everything here is done by editing **`data/parent.json`** — in GitHub's web
editor, or by telling a Claude session what changed and letting it make the
edit. No local tools required. Every edit is a commit, so the whole curation
history is inspectable and the next officer inherits it. The page itself is
deliberately read-only: no edit buttons that dead-end a volunteer at a
GitHub login screen.

**Who can edit what.** Reading is public: one URL, no accounts, no app.
Writing is GitHub repo permission — no shared password anywhere. Repo
collaborators edit directly (commit → the site redeploys itself, everyone
sees one truth); anyone else can only *propose* a change from their own
GitHub account, which sits in the pull-request queue until a collaborator
approves it — moderation for free. Succession is a grant, not
a secret: add the incoming officer as a collaborator, remove the outgoing
one. If more officers ever need durable shared ownership, create a free
GitHub organization and transfer the repo into it (all URLs redirect); the
repo being public means the full record is cloneable and survives any
single account.

**Acting on a watchlist flag.** A red "expected by … — not seen yet" line
means a scheduled obligation hasn't been verified. Click its check link
(usually Simbli minutes or a district page), confirm reality, then set that
item's `"status"` to `"done"` in `parent.json`. Done items show a ✓ receipt
for 45 days, then retire themselves.

**Writing a parent card.** A card is a *consequence with an owner*, not a
headline. It answers three questions in order: what changes for my kid
(`kid_impact`, one sentence), who decided it (`owner`), and what — if
anything — a parent can do (`action`, at most one). If you can't name the
owner, it isn't ready to be a card. To draft one, copy an existing card in
`coming_up` or `in_effect` as the template — or hand the source item to a
Claude session and review what it writes. Cards can carry a `law_url` /
`law_label` pointing at the statute text on leginfo, so parents see the
black-letter law, not just coverage. A card can also carry an optional
`"covers": ["<items.json id>", ...]` array — the feed item ids that card
accounts for. This is the only thing that tells the gap detector a hot
item already became a parent-facing decision instead of sitting unread:
add the id in the same edit you write the card. Leave `covers` off, or
leave an id out of it, and that feed item stays flagged as an
`uncovered_hot` gap indefinitely — the detector only trusts what's
written down, not what a human would obviously infer.

**Acting on a gap flag.** `data/gaps.json` (background above) surfaces as
one GitHub issue per run. Work it top to bottom — `uncovered_hot` first
(a parent-facing promise already broken), then `expired_card`, then
`stale_curation` — and treat the `evidence` field as a starting point to
verify against the linked source, never as a sentence to paste in: write
the card yourself, then add the item's id to that card's `covers` array so
it doesn't reflag tomorrow. An `expired_card` gap means archive or replace
the card; a `stale_curation` gap means walk the whole file and confirm
nothing's gone stale, then edit `updated`.

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
| `data/gaps.json` | rebuilt whole-cloth every run — no history of its own, so yesterday's gap list carries no weight once tonight's run replaces it |

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

## Languages

The page chrome is hand-translated in four locales — English, 中文 (zh-Hant),
한국어, Español — matching the district community's top home languages. It's a
small inline vanilla-JS catalog in `index.html` (`MSG`), no build step, choice
persisted as `pta-locale`. **Only chrome is translated**: curated card and
source content stays in its original language (translating civic content is a
curation job), and an on-page hint tells readers to use the browser's
translate-page feature for the rest. To add or change a string: edit `MSG`
in all four locales, or add the id to English only (missing translations fall
back to English by design). The monthly report generator deliberately stays
English — it's the officer's paste-ready board document. Family doctrine:
axm-genesis `docs/LOCALIZATION.md`.
