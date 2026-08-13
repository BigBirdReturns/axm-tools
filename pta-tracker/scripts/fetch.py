#!/usr/bin/env python3
"""
PTA Legislative Tracker - nightly fetcher.

Pulls district and state education-policy sources, filters for what parents
at a K-6 Arcadia USD campus need to know (simple keyword rules, no API keys),
and writes data/items.json that the static site renders.

District sources (the actual job):
  1. AUSD News RSS           - the district's own announcements (Edlio CMS)
  2. Google News RSS query   - "Arcadia Unified" press coverage from any outlet
  3. AUSD board-meeting schedule scraped from ausd.net/apps/pages/agenda;
     upcoming meetings become tracker items linking to the Simbli agenda
     system (Simbli itself sits behind Incapsula bot protection, so agendas
     are for humans to click, not for us to scrape)

School sources (scope "school" - a single campus's own voice, not the
district's):
  3a. Holly Avenue News RSS  - ha.ausd.net's own announcements (same Edlio
                                CMS as the district feed). Its events feed
                                403s behind bot protection, same story as
                                Simbli, so it isn't in FEEDS.

State sources (context):
  4. LAist education RSS     - LA-county angle
  5. CDE "What's New" RSS    - Dept. of Education official announcements
  6. Google News RSS query   - CA K-12 law/legislation catch-all; this is
                               also how EdSource journalism arrives, since
                               edsource.org 403s all datacenter IPs and a
                               permanently-dead feed would just train the
                               owner to ignore the source-health warning

Out-of-band source:
  7. data/observed.json      - items collected where this Action cannot go
                               (bot-protected pages like Simbli), by a human
                               or a local ScreenGhost observer, and committed
                               to the repo; merged without keyword filtering

Deliberately boring technology: Python stdlib only. Handles both RSS 2.0 and
Atom, which covers every feed on the list.
"""

import json
import re
import sys
import hashlib
import datetime
import email.utils
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "items.json"
OBSERVED = ROOT / "data" / "observed.json"
ARCHIVE = ROOT / "data" / "archive.json"
PARENT = ROOT / "data" / "parent.json"
DERIVED = ROOT / "data" / "derived.json"
GAPS = ROOT / "data" / "gaps.json"
SCHOOLS = ROOT / "data" / "schools.json"

AGENDA_PAGE = "https://www.ausd.net/apps/pages/agenda"
SIMBLI_MEETINGS = (
    "https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx"
    "?S=36030512"
)

# (source label, url, scope, school) - scope is "district", "state", or
# "school"; school is the schools.json id a "school"-scope feed belongs to,
# and None for every district/state feed (there is exactly one school today,
# but the 4th slot is what lets a second campus's feed join without another
# schema change).
FEEDS = [
    ("AUSD News", "https://www.ausd.net/apps/news/rss", "district", None),
    (
        "Google News",
        "https://news.google.com/rss/search?"
        "q=%22Arcadia%20Unified%22%20OR%20%22Arcadia%20USD%22"
        "&hl=en-US&gl=US&ceid=US:en",
        "district",
        None,
    ),
    ("Holly Avenue News", "https://ha.ausd.net/apps/news/rss", "school", "ha"),
    ("LAist Education", "https://laist.com/education.rss", "state", None),
    ("CA Dept of Education", "https://www.cde.ca.gov/rssfeed.asp", "state", None),
    (
        "Google News",
        "https://news.google.com/rss/search?"
        "q=California%20K-12%20education%20law%20OR%20legislation"
        "%20OR%20%22school%20district%22&hl=en-US&gl=US&ceid=US:en",
        "state",
        None,
    ),
]

USER_AGENT = "Mozilla/5.0 (compatible; pta-tracker/1.0; +https://github.com/BigBirdReturns/axm-tools)"

# --- relevance rules -------------------------------------------------------
# State tier 1: elementary-school direct hits -> always keep, flag HOT
HOT = [
    r"\belementary\b", r"\bK-6\b", r"\bTK\b", r"\btransitional kindergarten\b",
    r"\bcellphone|cell phone|phone-free\b", r"\bscreen time\b",
    r"\bschool safety\b",
    r"\bbackground check\b", r"\babuse prevention\b", r"\bSB ?848\b",
    r"\bAB ?3216\b", r"\barcadia\b", r"\bclass size\b", r"\bschool meals?\b",
    r"\bafter-?school\b", r"\bspecial education\b", r"\bIEP\b",
]
# State tier 2: general K-12 policy -> keep, normal priority
WARM = [
    r"\bK-12\b", r"\bschool district\b", r"\bLCFF\b", r"\bschool funding\b",
    r"\bcurriculum\b", r"\bschool board\b", r"\bteacher\b", r"\battendance\b",
    r"\btruancy\b", r"\bstate budget\b.*\beducation\b", r"\bproposition\b",
    r"\bcharter school\b", r"\bimmigration\b.*\bschool\b", r"\brestroom\b",
]
# Exclusions: higher-ed only, sports-only, other states
COLD = [
    r"\buniversity\b(?!.*K-12)", r"\bCSU\b(?!.*K-12)", r"\bUC \b",
    r"\bcommunity college\b", r"\bNCAA\b",
]

# District items that demand parent attention -> HOT
DISTRICT_HOT = [
    r"\bpolic(y|ies)\b", r"\bcellphone|cell phone|phone-free\b",
    r"\bscreen time\b", r"\bsafety\b", r"\bboundar", r"\bbudget\b",
    r"\bclosure\b", r"\bstart time\b", r"\bcalendar\b", r"\bLCAP\b",
    r"\benroll", r"\bholly avenue\b", r"\bkindergarten\b", r"\bTK\b",
    r"\bspecial education\b", r"\bIEP\b", r"\bschool meals?\b",
    r"\bafter-?school\b", r"\bsuperintendent\b", r"\bbond\b",
    r"\bconstruction\b", r"\bfacilit",
]
# District fluff we drop (unless something above also matches):
# awards, rankings, sports, celebrations - lovely, but not legislation
DISTRICT_SKIP = [
    r"\bvaledictorian\b", r"\bathlet", r"\bsports?\b", r"\btournament\b",
    r"\bchampion", r"\balumn", r"\bscholarship\b", r"\bgala\b",
    r"\bconcert\b", r"\bart show\b", r"\bnational merit\b", r"\baward",
    r"\bhonor", r"\brank(ed|ing|s)?\b", r"\bcelebrat", r"\bshowcase\b",
    r"\bmagazine\b", r"\bgraduation rate\b", r"\bpodcast\b", r"\bmusic video\b",
    r"\bdistinguished school", r"\bteacher of the year\b", r"\bhiring\b",
    r"\bretire", r"\bfootball\b", r"\bbest school district", r"\bfirst ?day\b",
    r"\bstate of the district\b",
]

def score(text: str, scope: str) -> str | None:
    t = text.lower()
    if scope in ("district", "school"):
        # Low-volume feeds from our own district - and, same intent, a
        # single school's own feed - keep what parents may need to act on
        # and drop the awards-and-celebrations firehose. A school's feed is
        # lower-volume still and closer to its own parents by default, but
        # that's a difference of degree, not of vocabulary: reusing
        # DISTRICT_HOT/DISTRICT_SKIP unchanged means "almost everything from
        # our own school is relevant" falls out of the same "keep unless
        # it's fluff" rule already tuned for the district feed, rather than
        # a second wordlist to keep in sync with the first.
        if any(re.search(p, t, re.I) for p in DISTRICT_SKIP) and not any(
            re.search(p, t, re.I) for p in DISTRICT_HOT
        ):
            return None
        if any(re.search(p, t, re.I) for p in DISTRICT_HOT):
            return "hot"
        return "normal"
    if any(re.search(p, t, re.I) for p in COLD) and not any(
        re.search(p, t, re.I) for p in HOT
    ):
        return None
    if any(re.search(p, t, re.I) for p in HOT):
        return "hot"
    if any(re.search(p, t, re.I) for p in WARM):
        return "normal"
    return None


# Some feeds (CDE among them) serve cp1252 bytes under a latin-1 label, so
# the XML parser yields C1 control characters — 0x96 where an en-dash was
# meant — that render as tofu boxes on the page. Map the range back.
_CP1252_FIX = {
    c: bytes([c]).decode("cp1252", "ignore") or None for c in range(0x80, 0xA0)
}


def fix_mojibake(text: str) -> str:
    return text.translate(_CP1252_FIX)


def clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return fix_mojibake(text)[:400]


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(node: ET.Element, *names: str) -> str:
    for child in node:
        if _strip_ns(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def _entry_link(node: ET.Element) -> str:
    # RSS: <link>url</link>. Atom: <link href="url" rel="alternate"/>.
    fallback = ""
    for child in node:
        if _strip_ns(child.tag) != "link":
            continue
        if (child.text or "").strip():
            return child.text.strip()
        href = child.get("href", "")
        if href:
            if child.get("rel", "alternate") == "alternate":
                return href
            fallback = fallback or href
    return fallback


def parse_feed(xml_bytes: bytes) -> list[dict]:
    """Return a list of {title, summary, link, published} from RSS 2.0 or Atom."""
    root = ET.fromstring(xml_bytes)
    entries = [
        node
        for node in root.iter()
        if _strip_ns(node.tag) in ("item", "entry")
    ]
    out = []
    for node in entries:
        out.append(
            {
                "title": _child_text(node, "title"),
                "summary": _child_text(
                    node, "description", "summary", "content", "encoded"
                ),
                "link": _entry_link(node),
                "published": _child_text(node, "pubDate", "published", "updated"),
                # Google News wraps each item's real publisher in <source>
                "via": _child_text(node, "source"),
            }
        )
    return out


MAX_AGE_DAYS = 120

# --- black-letter law links ------------------------------------------------
# News coverage is someone's interpretation; link every bill reference to the
# actual statute text on leginfo.legislature.ca.gov. Bill numbers recycle
# every two-year session (the 2023-24 SB 848 is reproductive-loss leave; the
# 2025-26 SB 848 is pupil safety), so we probe sessions newest-first and
# verify against the page title, which also gives us the official subject.
BILL_RE = re.compile(r"\b(AB|SB|ACA|SCA|ACR|SCR|AJR|SJR)[-\s]?(\d{1,4})\b")
BILL_TITLE_RE = re.compile(r"<title>\s*Bill Text\s*-\s*([A-Z]+-\d+[^<]+?)\s*</title>")
MAX_BILL_LOOKUPS_PER_RUN = 20
_bill_cache: dict[str, dict | None] = {}
_bill_lookups = 0


def _sessions() -> list[str]:
    """Current and two prior two-year session ids, newest first."""
    year = datetime.date.today().year
    start = year if year % 2 else year - 1
    return [f"{s}{s + 1}0" for s in (start, start - 2, start - 4)]


def bill_candidates(house: str, num: str) -> tuple[list[dict], bool]:
    """All sessions where this bill number exists, newest first.

    Returns (candidates, definitive). definitive=False means budget
    exhausted or network trouble - the caller should retry on a later run
    rather than record "no such bill".
    """
    global _bill_lookups
    key = f"{house}{num}"
    if key in _bill_cache:
        return _bill_cache[key], True
    candidates, definitive = [], True
    for session in _sessions():
        if _bill_lookups >= MAX_BILL_LOOKUPS_PER_RUN:
            return candidates, False
        url = (
            "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml"
            f"?bill_id={session}{house}{num}"
        )
        _bill_lookups += 1
        try:
            m = BILL_TITLE_RE.search(_get(url).decode("utf-8", "replace"))
        except Exception as e:
            print(f"[warn] leginfo {house} {num}: {e}", file=sys.stderr)
            definitive = False
            continue
        if m:  # empty title means no such bill in this session
            candidates.append(
                {"ref": f"{house} {num}", "title": m.group(1), "url": url}
            )
    if definitive:
        _bill_cache[key] = candidates
    return candidates, definitive


def _tokens(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", text.lower())}


def find_bills(text: str) -> tuple[list[dict], bool]:
    """Resolve bill refs in text to statute links, disambiguating recycled
    numbers by overlap between the official subject and the story text
    (SB 760 is restrooms, behested payments, or highways depending on the
    session - the story decides which). Ties go to the newest session."""
    bills, definitive = [], True
    story = _tokens(text)
    for house, num in dict.fromkeys(BILL_RE.findall(text)):
        candidates, ok = bill_candidates(house, num)
        definitive = definitive and ok
        if candidates:
            bills.append(
                max(candidates, key=lambda c: len(_tokens(c["title"]) & story))
            )
    return bills, definitive


def too_old(published: str) -> bool:
    """True if the item's publish date is parseable and past the window.

    Google News search feeds return relevant-not-recent, so without this a
    2016 human-interest story lands next to this week's board vote.
    Unparseable/missing dates are kept and aged out by first_seen instead.
    """
    dt = None
    try:
        dt = email.utils.parsedate_to_datetime(published)  # RFC 822 (RSS)
    except (TypeError, ValueError):
        try:
            dt = datetime.datetime.fromisoformat(published)  # Atom / ISO
        except ValueError:
            return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=MAX_AGE_DAYS
    )
    return dt < cutoff


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "january february march april may june july august september "
        "october november december".split()
    )
}


def fetch_board_meetings() -> list[dict] | None:
    """Scrape the meeting schedule off the district agenda page.

    The page lists the school-year schedule as plain text under year
    headings ("2026 ... January 13 January 27 ..."). Emit an item for each
    meeting today through 21 days out, linking to the Simbli agenda listing.
    Returns None when the page itself is unreachable — an empty list just
    means no meetings in the window, which is normal over the summer.
    """
    try:
        text = re.sub(r"<[^>]+>", " ", _get(AGENDA_PAGE).decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
    except Exception as e:
        print(f"[warn] AUSD agenda page: {e}", file=sys.stderr)
        return None

    today = datetime.date.today()
    year = None
    items = []
    # walk the text in order; bare year tokens set context for month-day pairs
    for tok in re.finditer(
        r"\b(20\d\d)\b|\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December) (\d{1,2})\b",
        text,
    ):
        if tok.group(1):
            year = int(tok.group(1))
            continue
        if not year:
            continue
        try:
            date = datetime.date(year, MONTHS[tok.group(2).lower()], int(tok.group(3)))
        except ValueError:
            continue
        if not (today <= date <= today + datetime.timedelta(days=21)):
            continue
        items.append(
            {
                "id": f"ausd-mtg-{date.isoformat()}",
                "source": "AUSD Board of Education",
                "title": "AUSD board meeting — "
                + f"{date:%A, %B} {date.day}"
                + " at 7:00 p.m.",
                "summary": "Regular Board of Education meeting, Arcadia "
                "Education Center Board Room (unless the schedule notes "
                "otherwise). Agenda posts on Simbli the Friday before — "
                "worth a skim for anything parents will ask about.",
                "link": SIMBLI_MEETINGS,
                "published": date.isoformat(),
                "priority": "hot",
                "scope": "district",
            }
        )
    return items


def load_observed() -> list[dict]:
    """Merge items collected out-of-band from data/observed.json.

    Some sources block datacenter IPs outright (Simbli board agendas sit
    behind Incapsula), so this Action can never read them — but a human,
    or a local observer like ScreenGhost driving a physically attached
    device, always can. Whatever they collect goes in observed.json using
    the same schema as items.json entries (only "title" is required) and
    merges into the pipeline here. These were placed deliberately, so no
    keyword filtering; the age window still applies.
    """
    if not OBSERVED.exists():
        return []
    try:
        raw = json.loads(OBSERVED.read_text(encoding="utf-8")).get("items", [])
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] observed.json unreadable: {e}", file=sys.stderr)
        return []
    items = []
    for e in raw:
        title = (e.get("title") or "").strip()
        if not title or too_old(e.get("published", "")):
            continue
        items.append(
            {
                "id": e.get("id")
                or hashlib.sha1((e.get("link") or title).encode()).hexdigest()[:12],
                "source": e.get("source", "Observed"),
                "title": fix_mojibake(title),
                "summary": clean(e.get("summary", "")),
                "link": e.get("link", ""),
                "published": e.get("published", ""),
                "priority": e.get("priority", "normal"),
                "scope": e.get("scope", "district"),
            }
        )
    return items


def fetch_all() -> tuple[list[dict], list[dict]]:
    """Fetch every feed; return (items, per-source health records).

    Health goes into items.json so the page can show which sources are
    quiet — one dead feed keeps the run green, and without this it just
    silently stops contributing.
    """
    items = []
    health = []
    for source, url, scope, school in FEEDS:
        try:
            entries = parse_feed(_get(url))
        except Exception as e:  # one broken feed shouldn't kill the run
            print(f"[warn] {source}: {e}", file=sys.stderr)
            health.append(
                {"source": source, "scope": scope, "ok": False, "error": str(e)[:120]}
            )
            continue
        kept = 0
        for e in entries[:40]:
            if too_old(e["published"]):
                continue
            title = fix_mojibake(e["title"])
            if e["via"] and title.endswith(" - " + e["via"]):
                title = title[: -len(" - " + e["via"])]
            summary = clean(e["summary"])
            # Google News descriptions are just the linked headline again;
            # drop them so the report doesn't repeat every title twice.
            if summary and title and summary.startswith(title[:60]):
                summary = ""
            relevance = score(f"{title} {summary}", scope)
            if not relevance:
                continue
            uid = hashlib.sha1((e["link"] or title).encode()).hexdigest()[:12]
            item = {
                "id": uid,
                "source": e["via"] or source,
                "title": title,
                "summary": summary,
                "link": e["link"],
                "published": e["published"],
                "priority": relevance,
                "scope": scope,
            }
            if school:  # scope "school" items carry which campus they're for
                item["school"] = school
            items.append(item)
            kept += 1
        health.append({"source": source, "scope": scope, "ok": True, "kept": kept})
    if not any(h["ok"] for h in health):
        # Every source down means our URLs rotted or the network is gone.
        # Fail the run so GitHub emails the owner instead of silently
        # serving stale data for months.
        sys.exit("all feeds failed - check FEEDS urls")
    meetings = fetch_board_meetings()
    health.append(
        {
            "source": "AUSD board schedule",
            "scope": "district",
            "ok": meetings is not None,
            "kept": len(meetings or []),
        }
    )
    items.extend(meetings or [])
    return items, health


# --- derived cards -----------------------------------------------------------
# The recurring failure mode this repo is actually built to survive isn't a
# broken feed, it's a volunteer who stops writing the monthly card. A board
# meeting's date/time/location are FACTS the scraper already has in full;
# only "what this means for your kid" is a CONSEQUENCE, and that stays human.
# So a curator writes the sentence once (parent.json "templates"), and every
# run instantiates it with scraped facts into its own file - never into
# parent.json itself, which stays hand-curated and hand-owned.
DERIVED_NOTE = (
    "Machine-written every run, never hand-edited; facts scraped from the "
    "district, prose instantiated from human-written templates in "
    "parent.json. Delete it and the next run rebuilds it."
)


def _empty_derived() -> dict:
    return {
        "note": DERIVED_NOTE,
        "generated": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "coming_up": [],
    }


def build_derived(merged: list[dict], parent: dict, today: datetime.date) -> dict:
    """Instantiate parent.json's board_meeting template with scraped facts.

    Board-meeting items already carry a stable, purpose-built id
    ("ausd-mtg-YYYY-MM-DD") minted once, in fetch_board_meetings(), by
    reading the actual agenda-page schedule. Finding them here by that id
    prefix reuses that same output instead of re-deriving "is this item a
    board meeting" from a second regex over titles - which would just be a
    new place for the id format and the title wording to silently drift
    apart from each other.

    The one prohibition: if a curator hasn't written templates.board_meeting
    yet, this returns an EMPTY coming_up and warns - it never invents the
    missing sentence to fill the gap.
    """
    templates = parent.get("templates") or {}
    tmpl = templates.get("board_meeting")
    if not isinstance(tmpl, dict):
        print(
            "[warn] parent.json has no templates.board_meeting - "
            "derived.json will carry no cards",
            file=sys.stderr,
        )
        return _empty_derived()

    cards = []
    for item in merged:
        item_id = item.get("id", "")
        if not item_id.startswith("ausd-mtg-"):
            continue
        try:
            date = datetime.date.fromisoformat(item.get("published", ""))
        except (TypeError, ValueError):
            continue  # can't place it in time, so can't say "coming up"
        if date < today:
            continue  # never resurrect a meeting that's already happened
        try:
            title = tmpl["title"].format(
                weekday=f"{date:%A}", month=f"{date:%B}", day=str(date.day)
            )
            kid_impact = tmpl["kid_impact"]
            impact_area = tmpl["impact_area"]
            owner = tmpl["owner"]
            time_sensitivity = tmpl["time_sensitivity"]
        except (KeyError, IndexError, AttributeError) as e:
            # Malformed template - same prohibition applies: skip the card
            # rather than guess at the missing piece.
            print(f"[warn] templates.board_meeting malformed: {e}", file=sys.stderr)
            continue
        cards.append(
            {
                "id": f"derived-board-{date.isoformat()}",
                "kind": "meeting",
                "derived": True,
                "source_item": item_id,
                "until": date.isoformat(),
                "when": f"{date.isoformat()}T19:00",
                # Mirrors the hand-written coming_up meeting card in
                # parent.json field-for-field (location/source_url/action) -
                # this is a fact-only fill-in of that same shape, not a new one.
                "location": "Arcadia Education Center Board Room, "
                "150 S 3rd Ave, Arcadia, CA 91006",
                "title": title,
                "kid_impact": kid_impact,
                "impact_area": impact_area,
                "owner": owner,
                "time_sensitivity": time_sensitivity,
                "source_url": AGENDA_PAGE,
                "covers": [item_id],
                "action": {
                    "type": "read",
                    "label": "Check the agenda on Simbli",
                    "url": SIMBLI_MEETINGS,
                },
            }
        )
    cards.sort(key=lambda c: c["source_item"])
    out = _empty_derived()
    out["coming_up"] = cards
    return out


def _load_derived() -> dict:
    """Read derived.json defensively, same posture as _load_parent().

    It's machine-written by this same run, so it's normally present and
    fresh - but a first run before it exists, a hand-deleted file, or a
    build step that failed and left nothing behind must not make the gap
    check fall over.
    """
    if not DERIVED.exists():
        return {}
    try:
        raw = json.loads(DERIVED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[warn] derived.json unreadable, skipping its coverage in gap checks: {e}",
            file=sys.stderr,
        )
        return {}
    return raw if isinstance(raw, dict) else {}


# --- gap detection ----------------------------------------------------------
# The feed reliably finds things; nothing used to signal when a hot item had
# no matching parent card, so silence on the parent page was indistinguishable
# from "nothing is happening." This never invents parent-facing prose (that's
# the documented failure mode - CNET's 53% AI-story error rate, Quakebot
# republishing a 1925 quake as breaking news): it only surfaces the item's own
# verbatim summary/title so a human decides what sentence to write, if any.
UNCOVERED_HOT_MAX_AGE_DAYS = 60
STALE_CURATION_DAYS = 45
# District staff and this page both go quiet over summer; a curator not
# touching parent.json in that window is the expected shape, not a defect.
DORMANT_START = (6, 20)
DORMANT_END = (8, 5)


def _load_parent() -> dict:
    """Read parent.json defensively.

    It's hand-edited, not machine-written, so it can be missing, briefly
    malformed mid-edit, or lacking keys we've since added (like "covers").
    The gap report matters far less than the nightly feed refresh, so any
    failure here degrades to "no cards known" instead of killing the run.
    """
    if not PARENT.exists():
        return {}
    try:
        # encoding is explicit on purpose, everywhere this repo touches a
        # file. Path.read_text() otherwise uses locale.getpreferredencoding(),
        # which is cp1252 on a stock Windows box: parent.json's UTF-8 em dash
        # (E2 80 94) then decodes as "â€”" WITHOUT raising, because cp1252 has
        # no invalid bytes, and json.loads() is perfectly happy with the
        # result. The corruption only becomes visible on the parent page,
        # inside a sentence a human wrote. A curator's words must survive the
        # trip byte-for-byte or not be shipped at all.
        raw = json.loads(PARENT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[warn] parent.json unreadable, skipping gap checks against it: {e}", file=sys.stderr)
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_school_ids() -> set[str]:
    """Known school ids from schools.json, or an empty set if unreadable.

    schools.json is also hand-maintained (a new campus is added by editing
    it), so it gets the same defensive treatment as parent.json. Without a
    roster we cannot tell which schools a school-specific card is still
    missing, nor which ids are typos - so an empty set degrades gap detection
    back to pre-schools, district-wide-only behavior rather than guessing.
    Note that card SCOPE never consults this (see _card_schools); only the
    two questions that genuinely need a roster do - "who is still missing?"
    in find_gaps(), and "is this id real?" in _unknown_school_refs().
    """
    if not SCHOOLS.exists():
        return set()
    try:
        raw = json.loads(SCHOOLS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[warn] schools.json unreadable, skipping school-aware gap checks: {e}", file=sys.stderr)
        return set()
    if not isinstance(raw, dict):
        return set()
    return {
        s["id"]
        for s in raw.get("schools") or []
        if isinstance(s, dict) and isinstance(s.get("id"), str)
    }


def _card_schools(card: dict) -> list[str] | None:
    """A card's explicit school scope, or None when it's district-wide.

    No "schools" key, an empty/malformed one, or the literal ["*"] all mean
    "every school" per the CONTRACT - that's the common case (nearly every
    card is district- or state-level) and it must stay a single gap, not
    fan out per school. Only a genuine list of specific ids narrows it.

    Deliberately does NOT filter against the roster, and takes no roster
    argument so it cannot start: an earlier version dropped unknown ids and
    returned None when nothing survived, which turned a one-character typo
    ("hz" for "ha") into "this card covers every school." The page has no such
    filter - it just asks whether the list contains the school it is rendering
    for - so that card in fact rendered on no page at all, while this function
    told the gap tracker the item was handled. Item invisible, alarm silent:
    the exact failure this tool exists to catch. Unrecognised ids therefore
    stay in the list, where they match nothing here for the same reason they
    match nothing there, and _unknown_school_refs() names the typo out loud.

    This is one half of a contract; the other half is cardSchools() in
    index.html, pinned by SCOPE_CONTRACT_SHA256 below. Change one, change both.
    """
    schools = card.get("schools")
    if isinstance(schools, str):  # hand-typed "ha" instead of ["ha"]
        schools = [schools]
    if not isinstance(schools, list):
        return None
    schools = [s for s in schools if isinstance(s, str)]
    if not schools or "*" in schools:
        return None
    return schools


# ---------------------------------------------------------------------------
# The scope contract, pinned.
#
# _card_schools() above and cardSchools()/inSchoolScope() in index.html must
# answer "which schools is this card for?" identically. Nothing in the
# language stops them from drifting apart, and drift is silent by
# construction: the page shows a card to nobody while this file reports it
# covered. So the JS half is fenced between two markers and its
# whitespace-stripped SHA-256 is pinned here. On mismatch we raise a
# scope_logic_drift gap - which the workflow turns into a GitHub issue, i.e.
# a human is asked whether the two still agree.
#
# A pin, not a lock: an intentional edit is fine, it just cannot be quiet.
# Update this constant with the hash the gap's "evidence" line reports.
# ---------------------------------------------------------------------------
INDEX_HTML = ROOT / "index.html"
SCOPE_CONTRACT_RE = re.compile(
    r"/\* SCOPE-CONTRACT-BEGIN(.*?)/\* SCOPE-CONTRACT-END \*/", re.S
)
SCOPE_CONTRACT_SHA256 = (
    "ee4513ebeb3b4761737d5939272bec9b273df62905a9be33cdb2beca0f7f86d5"
)


def _scope_contract_hash() -> str | None:
    """Whitespace-stripped SHA-256 of index.html's half of the scope contract,
    or None if the file or its markers are gone. Whitespace is stripped so
    reindenting the block is not treated as a semantic change; everything
    else - including the comment that states the contract - is in scope,
    because rewording what the contract SAYS is exactly as worth a second
    human look as rewording what it does."""
    try:
        html = INDEX_HTML.read_text(encoding="utf-8")
    except OSError:
        return None
    m = SCOPE_CONTRACT_RE.search(html)
    if not m:
        return None
    return hashlib.sha256("".join(m.group(0).split()).encode("utf-8")).hexdigest()


def _scope_contract_gap() -> dict | None:
    got = _scope_contract_hash()
    if got == SCOPE_CONTRACT_SHA256:
        return None
    if got is None:
        why = (
            "index.html's SCOPE-CONTRACT block is missing or unreadable - the "
            "page's card-scoping logic can no longer be checked against "
            "_card_schools() in fetch.py."
        )
    else:
        why = (
            "index.html's card-scoping logic changed. Confirm it still agrees "
            "with _card_schools() in scripts/fetch.py - if the two disagree, a "
            "card can render on no page while this tracker reports it covered "
            "- then update SCOPE_CONTRACT_SHA256 to the hash below."
        )
    return {
        "kind": "scope_logic_drift",
        "ref": "index.html:SCOPE-CONTRACT",
        "title": "Page and gap tracker may disagree about card school scope",
        "why": why,
        "source_url": "",
        "source_date": "",
        "evidence": f"expected {SCOPE_CONTRACT_SHA256}, found {got}",
    }


def _unknown_school_refs(parent: dict, known: set[str]) -> list[dict]:
    """One gap per card naming a school id no roster knows.

    Without this, an unrecognised id is a scope that matches nothing, which
    is safe (see _card_schools) but mute: the card just never appears and
    nobody is told why. Naming the card and the bad id is what turns a
    silent no-op back into a five-second fix. Needs a roster to compare
    against, so it says nothing when schools.json is unreadable."""
    if not known:
        return []
    gaps = []
    for bucket in ("coming_up", "in_effect", "actions"):
        for card in parent.get(bucket) or []:
            if not isinstance(card, dict):
                continue
            schools = _card_schools(card)
            if not schools:
                continue
            bad = [s for s in schools if s not in known]
            if not bad:
                continue
            gaps.append(
                {
                    "kind": "unknown_school_ref",
                    "ref": card.get("id", ""),
                    "title": card.get("title") or card.get("label", ""),
                    "why": "This card's \"schools\" names an id that is not in "
                    "schools.json, so the card shows on no school's page at all. "
                    "Fix the id or add the school.",
                    "source_url": card.get("source_url", ""),
                    "source_date": "",
                    "evidence": f"unknown: {', '.join(sorted(bad))}; "
                    f"known: {', '.join(sorted(known))}",
                }
            )
    return gaps


def _in_dormant_window(today: datetime.date) -> bool:
    return DORMANT_START <= (today.month, today.day) <= DORMANT_END


def _iso_day(published: str | None) -> str:
    """Normalize a feed publish date to YYYY-MM-DD, or "" if unparseable.

    Feed items carry RFC 822 dates ("Tue, 21 Jul 2026 21:03:51 GMT") while
    hand-seeded and board-meeting items carry ISO. Slicing the first ten
    characters works for one and produces "Tue, 21 Ju" for the other - and
    the gap report's whole job is to hand a curator a date they can trust.
    Same dual-format order as too_old().
    """
    if not published:
        return ""
    try:
        return email.utils.parsedate_to_datetime(published).date().isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.datetime.fromisoformat(published).date().isoformat()
        except (TypeError, ValueError):
            return ""


def find_gaps(merged: list[dict], today: datetime.date) -> dict:
    """Build the gaps.json payload per the GAPS CONTRACT.

    `merged` is this run's live item set (already deduped/aged by main()),
    so "reviewed" below is a real count of what was actually checked, not a
    guess - the "nothing found" case needs to be substantiated, not silent.
    """
    parent = _load_parent()
    known_schools = _load_school_ids()

    # Six schools share one corpus, so coverage has to stay keyed by item id,
    # not by (item id, school) - otherwise one district-wide card would need
    # writing six times, and one missing card would flag six gaps instead of
    # one. covered_all is the common case (a card with no "schools" key, or
    # ["*"]) - it satisfies every school outright. covered_by_school only
    # exists for cards that opted into a narrower scope; an item lands here
    # when it's covered for SOME schools but the roster shows others still
    # aren't - that's the one case school-awareness is meaningful for.
    covered_all = set()
    covered_by_school: dict[str, set[str]] = {}
    card_buckets = [parent.get(b) or [] for b in ("coming_up", "in_effect", "actions")]
    # A derived card satisfies this same "covers" contract, not a parallel
    # one - build_derived() gives each one exactly one covers entry, its own
    # source_item, so folding derived.json's coming_up cards into this same
    # loop can only account for the specific hot item that card instantiates.
    # It never widens into "derived cards cover whatever they resemble" -
    # that would let automation silently absorb judgment calls it has no
    # template for.
    card_buckets.append(_load_derived().get("coming_up") or [])
    for cards in card_buckets:
        for card in cards:
            if not isinstance(card, dict):
                continue
            # "covers" is hand-typed; a curator writing "covers": "seed-ab3216"
            # instead of ["seed-ab3216"] would otherwise have set.update()
            # iterate the string character by character, silently covering
            # nothing and flagging the item forever
            covers = card.get("covers")
            if isinstance(covers, str):
                covers = [covers]
            elif not isinstance(covers, list):
                covers = []
            covers = [c for c in covers if isinstance(c, str)]
            schools = _card_schools(card)
            if schools is None:
                covered_all.update(covers)
            else:
                for c in covers:
                    covered_by_school.setdefault(c, set()).update(schools)

    cutoff = (today - datetime.timedelta(days=UNCOVERED_HOT_MAX_AGE_DAYS)).isoformat()
    gaps = []
    for item in merged:
        # score() treats "district" and "school" as one vocabulary (see the
        # comment there), so a school's own feed can produce a hot item. It
        # has to be answerable to the same coverage rule, or adding the feed
        # just means hot Holly Avenue news is the one kind of local news
        # nobody is ever told is uncovered - the exact silence this detector
        # exists to break. Anything else ("state") stays out: that's VP-desk
        # context, not material for an auto-flagged parent card.
        scope = item.get("scope")
        if item.get("priority") != "hot" or scope not in ("district", "school"):
            continue
        item_id = item.get("id")
        if item_id in covered_all:
            continue
        # Who does this item's coverage have to satisfy? A district item
        # concerns every campus, so only the whole roster is full coverage.
        # An item from a single school's own feed concerns exactly that
        # campus, so a card scoped to that campus IS full coverage - checking
        # it against the roster instead would report five other schools
        # "missing" a card about news that was never theirs, and would
        # re-flag an item a curator had already handled. Same equivalence as
        # score()'s, applied to the coverage half.
        item_school = item.get("school") if scope == "school" else None
        if not isinstance(item_school, str) or not item_school:
            item_school = None
        audience = {item_school} if item_school else known_schools
        gap_schools = None
        if item_id in covered_by_school:
            if not audience:
                # a school-specific card exists but we can't tell which
                # schools it leaves out without a roster - that's still
                # human attention on this item, so don't re-flag it on a
                # guess (see _load_school_ids). Only reachable for district
                # items; a school item names its own audience.
                continue
            missing = sorted(audience - covered_by_school[item_id])
            if not missing:
                continue  # the school-specific cards add up to full coverage
            gap_schools = missing
        elif item_school:
            # Uncovered outright, and only one campus's page is affected -
            # say which, so the curator isn't left to infer it from the id.
            gap_schools = [item_school]
        if item.get("first_seen", "") < cutoff:
            continue  # don't resurrect ancient history on first run
        gap = {
            "kind": "uncovered_hot",
            "ref": item.get("id", ""),
            "title": item.get("title", ""),
            # Two fixed, human-written sentences picked by scope - not a
            # sentence assembled about the item. "district item" is simply
            # false for a school-feed item, and a gap report that misstates
            # what it looked at is worse than one that says less.
            "why": (
                "Hot district item with no parent card's \"covers\" listing it - "
                "a human needs to decide whether this needs a card."
                if scope == "district"
                else "Hot item from a school's own feed with no parent card's "
                "\"covers\" listing it - a human needs to decide whether this "
                "needs a card."
            ),
            "source_url": item.get("link", ""),
            "source_date": _iso_day(item.get("published")),
            "evidence": item.get("summary") or item.get("title", ""),
        }
        if gap_schools:
            gap["schools"] = gap_schools
        gaps.append(gap)

    for card in parent.get("coming_up") or []:
        if not isinstance(card, dict):
            continue
        until = card.get("until", "")
        # hand-typed field: a bare 20260728 is valid JSON but not a string,
        # and comparing int to str raises rather than just being wrong
        if isinstance(until, str) and until and until < today.isoformat():
            gap = {
                "kind": "expired_card",
                "ref": card.get("id", ""),
                "title": card.get("title", ""),
                "why": "This card's \"until\" date has passed - archive or replace it.",
                "source_url": card.get("source_url", ""),
                "source_date": until,
                "evidence": "",
            }
            # the card already declares its own scope; a school-specific
            # coming_up card expiring is that school's curator's business,
            # so pass the scope through rather than recomputing anything
            schools = _card_schools(card)
            if schools:
                gap["schools"] = schools
            gaps.append(gap)

    updated = parent.get("updated", "")
    if updated and not _in_dormant_window(today):
        try:
            stale_days = (today - datetime.date.fromisoformat(updated)).days
        except (ValueError, TypeError):
            stale_days = 0
        if stale_days > STALE_CURATION_DAYS:
            gaps.append(
                {
                    "kind": "stale_curation",
                    "ref": "parent.json",
                    "title": "Parent page curation",
                    "why": f"parent.json hasn't been updated in {stale_days} days "
                    "(outside the June 20 - Aug 5 dormant window).",
                    "source_url": "",
                    "source_date": updated,
                    "evidence": "",
                }
            )

    # Integrity gaps go last into the list and first out of the sort: a card
    # pointed at a school that doesn't exist, or a page whose scoping logic no
    # longer matches this file's, makes every "covered" verdict above it
    # suspect - so a human should read those before working the queue.
    gaps.extend(_unknown_school_refs(parent, known_schools))
    drift = _scope_contract_gap()
    if drift:
        gaps.append(drift)

    order = {
        "scope_logic_drift": 0,
        "unknown_school_ref": 1,
        "uncovered_hot": 2,
        "expired_card": 3,
        "stale_curation": 4,
    }
    # .get, not [] - an unranked new kind should sort last, not raise and take
    # the whole nightly fetch down with it
    gaps.sort(key=lambda g: order.get(g["kind"], 99))

    return {
        "note": "Machine-written, regenerated every run, append-nothing - this "
        "file flags MISSING HUMAN WORK on the parent page. It never writes "
        "parent-facing prose; each gap carries a verbatim source snippet so a "
        "human writes the sentence, not the script.",
        "checked": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "reviewed": len(merged),
        "gaps": gaps,
    }


def main() -> None:
    previous = {}
    if DATA.exists():
        for item in json.loads(DATA.read_text(encoding="utf-8")).get("items", []):
            previous[item["id"]] = item

    fresh, health = fetch_all()
    fresh.extend(load_observed())
    for item in fresh:
        if item["id"] not in previous:
            item["first_seen"] = datetime.date.today().isoformat()
        else:
            item["first_seen"] = previous[item["id"]].get(
                "first_seen", datetime.date.today().isoformat()
            )
        previous[item["id"]] = item

    # 120 most recent by first_seen stay live; the rest move to the archive,
    # which the page searches — the timeline forgets nothing
    ranked = sorted(
        previous.values(), key=lambda x: x.get("first_seen", ""), reverse=True
    )
    merged, aged_out = ranked[:120], ranked[120:]
    if aged_out:
        try:
            archived = json.loads(ARCHIVE.read_text(encoding="utf-8")).get("items", [])
        except (OSError, json.JSONDecodeError):
            archived = []
        by_id = {a["id"]: a for a in archived}
        for item in aged_out:
            by_id.setdefault(item["id"], item)
        ARCHIVE.write_text(
            json.dumps(
                {
                    "note": "Items aged off the live feed, kept forever so "
                    "the timeline stays searchable. Machine-written; append "
                    "only.",
                    "items": sorted(
                        by_id.values(),
                        key=lambda x: x.get("first_seen", ""),
                        reverse=True,
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    # link bill references to the statute text; resolved once per item,
    # then carried in the data file so leginfo isn't re-probed nightly
    for item in merged:
        if "bills" not in item:
            bills, definitive = find_bills(
                f"{item.get('title', '')} {item.get('summary', '')}"
            )
            if definitive:
                item["bills"] = bills

    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(
        json.dumps(
            {
                "generated": datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "sources": health,
                "items": merged,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Derived cards are a convenience layered on top of the feed, same as the
    # gap report below - the feed refresh is the district's actual service,
    # so a bad template or a malformed parent.json must never be able to
    # cost everyone the nightly data. Runs before the gap check (which reads
    # derived.json back off disk) so a hot board-meeting item that's already
    # automated doesn't also get flagged as uncovered.
    try:
        DERIVED.write_text(
            json.dumps(
                build_derived(merged, _load_parent(), datetime.date.today()), indent=2
            ),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001 - deliberately broad; see above
        print(f"[warn] derived-card build skipped: {e}", file=sys.stderr)

    # The gap report is a convenience for the curator; the feed refresh is the
    # district's actual service. A typo in hand-edited parent.json must never
    # be able to cost everyone the nightly data - so this can fail alone.
    gaps_report = None
    try:
        gaps_report = find_gaps(merged, datetime.date.today())
        GAPS.write_text(json.dumps(gaps_report, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - deliberately broad; see above
        print(f"[warn] gap check skipped: {e}", file=sys.stderr)

    hot = sum(1 for i in merged if i["priority"] == "hot")
    district = sum(1 for i in merged if i.get("scope") == "district")
    tail = (
        f"; {len(gaps_report['gaps'])} gaps found reviewing "
        f"{gaps_report['reviewed']} items"
        if gaps_report
        else "; gap check skipped"
    )
    print(f"wrote {len(merged)} items ({hot} hot, {district} district){tail}")


if __name__ == "__main__":
    main()
