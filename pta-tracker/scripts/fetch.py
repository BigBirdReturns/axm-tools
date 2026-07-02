#!/usr/bin/env python3
"""
PTA Legislative Tracker - nightly fetcher.

Pulls public education-policy sources, filters for K-6 / Arcadia USD relevance
with simple keyword rules (no API keys required), and writes data/items.json
that the static site renders.

Sources (v1):
  1. EdSource RSS            - statewide K-12 policy journalism
  2. LAist education RSS     - LA-county angle
  3. CDE "What's New" RSS    - Dept. of Education official announcements
  4. Google News RSS query   - CA K-12 law/legislation catch-all (also picks
                               up EdSource stories when their site blocks us)

Deliberately boring technology: Python stdlib only. Handles both RSS 2.0 and
Atom, which covers every feed on the list.
"""

import json
import re
import sys
import hashlib
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "items.json"

FEEDS = [
    # EdSource blocks datacenter IPs (403) as of mid-2026; kept in case that
    # changes, and its stories still arrive via the Google News query below.
    ("EdSource", "https://edsource.org/feed"),
    ("LAist Education", "https://laist.com/education.rss"),
    ("CA Dept of Education", "https://www.cde.ca.gov/rssfeed.asp"),
    (
        "Google News",
        "https://news.google.com/rss/search?"
        "q=California%20K-12%20education%20law%20OR%20legislation"
        "%20OR%20%22school%20district%22&hl=en-US&gl=US&ceid=US:en",
    ),
]

USER_AGENT = "pta-tracker/1.0 (+https://github.com/BigBirdReturns/axm-tools)"

# --- relevance rules -------------------------------------------------------
# Tier 1: elementary-school direct hits -> always keep, flag HOT
HOT = [
    r"\belementary\b", r"\bK-6\b", r"\bTK\b", r"\btransitional kindergarten\b",
    r"\bcellphone|cell phone|phone-free\b", r"\bschool safety\b",
    r"\bbackground check\b", r"\babuse prevention\b", r"\bSB ?848\b",
    r"\bAB ?3216\b", r"\barcadia\b", r"\bclass size\b", r"\bschool meals?\b",
    r"\bafter-?school\b", r"\bspecial education\b", r"\bIEP\b",
]
# Tier 2: general K-12 policy -> keep, normal priority
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

def score(text: str) -> str | None:
    t = text.lower()
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


def fetch_all() -> list[dict]:
    items = []
    for source, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                entries = parse_feed(resp.read())
        except Exception as e:  # network hiccups shouldn't kill the run
            print(f"[warn] {source}: {e}", file=sys.stderr)
            continue
        for e in entries[:40]:
            title = e["title"]
            if e["via"] and title.endswith(" - " + e["via"]):
                title = title[: -len(" - " + e["via"])]
            summary = clean(e["summary"])
            # Google News descriptions are just the linked headline again;
            # drop them so the report doesn't repeat every title twice.
            if summary and title and summary.startswith(title[:60]):
                summary = ""
            relevance = score(f"{title} {summary}")
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
                }
            )
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
    print(f"wrote {len(merged)} items ({hot} hot)")


if __name__ == "__main__":
    main()
