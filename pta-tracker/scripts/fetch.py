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

State sources (context):
  4. EdSource RSS            - statewide K-12 policy journalism (403s from
                               datacenter IPs as of mid-2026; tolerated)
  5. LAist education RSS     - LA-county angle
  6. CDE "What's New" RSS    - Dept. of Education official announcements
  7. Google News RSS query   - CA K-12 law/legislation catch-all (also picks
                               up EdSource stories when their site blocks us)

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

AGENDA_PAGE = "https://www.ausd.net/apps/pages/agenda"
SIMBLI_MEETINGS = (
    "https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx"
    "?S=36030512"
)

# (source label, url, scope) - scope is "district" or "state"
FEEDS = [
    ("AUSD News", "https://www.ausd.net/apps/news/rss", "district"),
    (
        "Google News",
        "https://news.google.com/rss/search?"
        "q=%22Arcadia%20Unified%22%20OR%20%22Arcadia%20USD%22"
        "&hl=en-US&gl=US&ceid=US:en",
        "district",
    ),
    ("EdSource", "https://edsource.org/feed", "state"),
    ("LAist Education", "https://laist.com/education.rss", "state"),
    ("CA Dept of Education", "https://www.cde.ca.gov/rssfeed.asp", "state"),
    (
        "Google News",
        "https://news.google.com/rss/search?"
        "q=California%20K-12%20education%20law%20OR%20legislation"
        "%20OR%20%22school%20district%22&hl=en-US&gl=US&ceid=US:en",
        "state",
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
    if scope == "district":
        # low-volume feeds from our own district: keep what parents may need
        # to act on, drop the awards-and-celebrations firehose
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


def clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


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


def fetch_board_meetings() -> list[dict]:
    """Scrape the meeting schedule off the district agenda page.

    The page lists the school-year schedule as plain text under year
    headings ("2026 ... January 13 January 27 ..."). Emit an item for each
    meeting today through 21 days out, linking to the Simbli agenda listing.
    """
    try:
        text = re.sub(r"<[^>]+>", " ", _get(AGENDA_PAGE).decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
    except Exception as e:
        print(f"[warn] AUSD agenda page: {e}", file=sys.stderr)
        return []

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
                + date.strftime("%A, %B %-d")
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


def fetch_all() -> list[dict]:
    items = []
    feeds_ok = 0
    for source, url, scope in FEEDS:
        try:
            entries = parse_feed(_get(url))
            feeds_ok += 1
        except Exception as e:  # one broken feed shouldn't kill the run
            print(f"[warn] {source}: {e}", file=sys.stderr)
            continue
        for e in entries[:40]:
            if too_old(e["published"]):
                continue
            title = e["title"]
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
            items.append(
                {
                    "id": uid,
                    "source": e["via"] or source,
                    "title": title,
                    "summary": summary,
                    "link": e["link"],
                    "published": e["published"],
                    "priority": relevance,
                    "scope": scope,
                }
            )
    if feeds_ok == 0:
        # Every source down means our URLs rotted or the network is gone.
        # Fail the run so GitHub emails the owner instead of silently
        # serving stale data for months.
        sys.exit("all feeds failed - check FEEDS urls")
    items.extend(fetch_board_meetings())
    return items


def main() -> None:
    previous = {}
    if DATA.exists():
        for item in json.loads(DATA.read_text()).get("items", []):
            previous[item["id"]] = item

    fresh = fetch_all()
    for item in fresh:
        if item["id"] not in previous:
            item["first_seen"] = datetime.date.today().isoformat()
        else:
            item["first_seen"] = previous[item["id"]].get(
                "first_seen", datetime.date.today().isoformat()
            )
        previous[item["id"]] = item

    # keep 120 most recent by first_seen
    merged = sorted(
        previous.values(), key=lambda x: x.get("first_seen", ""), reverse=True
    )[:120]

    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(
        json.dumps(
            {
                "generated": datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "items": merged,
            },
            indent=2,
        )
    )
    hot = sum(1 for i in merged if i["priority"] == "hot")
    district = sum(1 for i in merged if i.get("scope") == "district")
    print(f"wrote {len(merged)} items ({hot} hot, {district} district)")


if __name__ == "__main__":
    main()
