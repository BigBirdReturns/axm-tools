#!/usr/bin/env python3
"""
PTA Legislative Tracker - per-school page builder.

AUSD has six elementary schools and nearly every card in this tracker is
district- or state-level, i.e. identical for all six - one corpus, six
front doors. index.html is BOTH the live default-school (Holly Avenue) page
and the build template: this script reads it once and, for every school
listed in data/schools.json (published or not - "published" only gates who
we may point at the page, never whether it gets built), writes a copy at
<slug>/index.html carrying that school's identity. The template itself is
never modified on disk; it stays the default page exactly as the root URL
already serves it.

School identity is injected, never inferred: the page resolves its data
directory as `window.SCHOOL_BASE || "data/"` and its school id as
`window.SCHOOL || (schools.json).default`. That indirection is the whole
mechanism - see the shared contract in the project handoff for the rest of
it (card "schools" scoping, the {{school_site}} action-url token). This
script's job stops at emitting correctly-tagged HTML/PWA files.

Naming is the other half of identity and is handled at build time rather
than at runtime: every literal mention of the default school's short name in
the template - <title>, <h1>, the meta/Open Graph tags, the no-JS fallback
prose, and the DEFAULT_SCHOOL_SHORT constant the first paint reads - becomes
this school's name. The translated strings do NOT work that way; they take
the name as a parameter so all five locales stay in step. That split is
enforced here (see IDENTITY_ANCHORS) so a page can never go out claiming to
be curated by a PTA that never agreed to speak.

Python 3 standard library only - same house rule as fetch.py.
"""

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS_JSON = ROOT / "data" / "schools.json"
TEMPLATE = ROOT / "index.html"

# Marker dropped inside every directory this script writes, so the stale-
# directory sweep at the end can tell "a school we used to publish and just
# removed" (safe to delete) apart from "some other directory a human or a
# different tool put here" (never touch). Content-free on purpose - its
# presence is the whole signal.
MARKER_NAME = ".generated-by-build_schools"

# Defense in depth for the sweep below: these top-level names are hand-
# maintained inputs, not build output, and must never be considered for
# deletion even in the (should-be-impossible) case one of them ever
# contained a stray marker file.
PROTECTED_NAMES = {"data", "scripts"}

# ---------------------------------------------------------------------------
# Anchor for the per-school <script> injection.
#
# The template has exactly two <script> tags: one inline in <head> that sets
# the theme/locale before first paint (has nothing to do with school
# identity), and the main logic block that fetches data/*.json and needs
# window.SCHOOL / window.SCHOOL_BASE defined before it runs. We anchor on
# the opening tag of the SECOND one by pairing it with the first line of the
# comment that only that block starts with - so a bare "<script>" search
# can't land on the head script, and there is no data: URI or quoted JS
# string anywhere in this file containing the literal text "<script>" for a
# looser match to misfire on (verified by grep before writing this).
#
# The line break in between is matched as \r?\n rather than a literal
# character: this repo's blobs are committed LF-only (verified against
# `git show HEAD:...`, not the working tree), but this machine's
# core.autocrlf=true rewrites the checkout to CRLF - so the anchor has to
# tolerate either, and whichever one is actually present gets echoed back
# when the school line is inserted (see inject_school_script) rather than
# silently mixing line-ending styles into the generated file.
# ---------------------------------------------------------------------------
SCRIPT_ANCHOR_RE = re.compile(
    r"<script>\r?\n"
    r"/\* ---------- i18n: chrome-only, en \+ zh-Hant ----------"
)

# ---------------------------------------------------------------------------
# PWA/offline decision: the service worker registration line.
#
# navigator.serviceWorker.register() takes a path relative to the page that
# calls it, but a worker's own default scope (which pages it's allowed to
# control) is the directory containing its OWN script URL - not the page
# that registered it. The template says register("sw.js"), correct only for
# a page that lives next to sw.js. One level down, in <slug>/index.html,
# that same literal string would request <slug>/sw.js - a 404 the existing
# .catch() swallows silently, quietly disabling offline support for every
# school but the default one.
#
# sw.js's own maximum default scope is the directory that contains it
# (pta-tracker/) plus everything below - which already covers every
# <slug>/ directory. So the fix needs no new sw.js, no per-school copy, no
# Service-Worker-Allowed header and no explicit {scope} option: pointing
# every school page at "../sw.js" hands them the same shared worker,
# already wide enough to control them, completely unduplicated.
# ---------------------------------------------------------------------------
SW_REGISTER_OLD = 'navigator.serviceWorker.register("sw.js")'
SW_REGISTER_NEW = 'navigator.serviceWorker.register("../sw.js")'


def fail(msg):
    print(f"build_schools: {msg}", file=sys.stderr)
    sys.exit(1)


def load_schools():
    try:
        doc = json.loads(SCHOOLS_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing {SCHOOLS_JSON}")
    except json.JSONDecodeError as e:
        fail(f"{SCHOOLS_JSON} is not valid JSON: {e}")

    schools = doc.get("schools") or []
    if not schools:
        fail(f"{SCHOOLS_JSON} lists no schools")

    ids = [s["id"] for s in schools]
    if len(ids) != len(set(ids)):
        fail(f"duplicate school id in {SCHOOLS_JSON}")
    slugs = [s["slug"] for s in schools]
    if len(slugs) != len(set(slugs)):
        fail(f"duplicate school slug in {SCHOOLS_JSON}")
    if doc.get("default") not in ids:
        fail(f"default {doc.get('default')!r} is not a school id in {SCHOOLS_JSON}")

    return doc, schools


def read_template():
    # newline="" on both read and write throughout this script: we want the
    # exact bytes the template already has (this repo is checked out with
    # LF, and CI runs on ubuntu-latest) reproduced exactly, not re-translated
    # through Python's universal-newline handling - that's what "idempotent,
    # byte-identical output" actually requires on top of stable content.
    try:
        with open(TEMPLATE, "r", encoding="utf-8", newline="") as f:
            return f.read()
    except FileNotFoundError:
        fail(f"missing {TEMPLATE}")


def one_match(html, pattern, label):
    matches = re.findall(pattern, html, re.S)
    if len(matches) != 1:
        fail(f"expected exactly one {label} in {TEMPLATE}, found {len(matches)}")
    return matches[0]


# ---------------------------------------------------------------------------
# Identity anchors: the places the page names the school it speaks for.
#
# The rewrite below is a whole-file replacement of the default school's short
# name, not a list of fields, because the field list was the bug: the first
# version rewrote <title>/og:title only, and every generated page still said
# "Holly Avenue" in its <h1>, its footer and seven meta tags - a Hugo Reid
# page claiming to be curated by another school's PTA, which is exactly the
# thing schools.json's "published" flag exists to prevent. Enumerating fields
# means the next line of identity copy someone writes is silently missed
# again; replacing everywhere means it is handled the day it is written.
#
# That is only safe because the locale catalogs no longer contain the name at
# all (they take it as a parameter now) - so what's left in the file is
# identity copy and nothing else. Both halves of that are asserted before any
# replacement happens: every anchor here must still carry the name exactly
# once, and the MSG catalog must not carry it at all.
# ---------------------------------------------------------------------------
IDENTITY_ANCHORS = (
    (r"<title>(.*?)</title>", "<title>"),
    (r'<meta property="og:title" content="([^"]*)">', "og:title <meta>"),
    (r'<meta property="og:site_name" content="([^"]*)">', "og:site_name <meta>"),
    (r"<h1>(.*?)</h1>", "<h1>"),
    (r'(const DEFAULT_SCHOOL_SHORT="[^"]*";)', "DEFAULT_SCHOOL_SHORT constant"),
)

# The locale catalog, delimited so the no-hardcoded-name check below can look
# at exactly it. `const MSG={` opens it; `const SUPPORTED=` is the next
# statement after its closing brace.
MSG_TABLE_RE = re.compile(r"const MSG=\{.*?\nconst SUPPORTED=", re.S)


def extract_default_fields(html, default_short):
    """Validate that the template still names the default school where this
    script expects it, and pull the two URL fields that need per-school
    rewriting rather than name substitution.

    Keying everything off the DEFAULT school's own short name (rather than a
    hardcoded "Holly Avenue") keeps this script working if the copy is
    reworded or the default school changes, and makes it fail loudly instead
    of quietly shipping six pages with the wrong PTA's name on them."""
    canonical = one_match(
        html, r'<link rel="canonical" href="([^"]*)">', 'canonical <link>'
    )
    og_url = one_match(
        html, r'<meta property="og:url" content="([^"]*)">', "og:url <meta>"
    )

    for pattern, label in IDENTITY_ANCHORS:
        val = one_match(html, pattern, label)
        if val.count(default_short) != 1:
            fail(
                f"expected the default school's short name ({default_short!r}) "
                f"exactly once in {label}, found {val.count(default_short)} - "
                "wording changed under this script; update the anchor logic"
            )

    # A name hardcoded into one locale's string is a name four other locales
    # would still get wrong, and a string this script would rewrite blindly
    # inside translated prose. Catalog strings take the name as a parameter;
    # this is what keeps that true.
    catalog = MSG_TABLE_RE.search(html)
    if not catalog:
        fail("could not locate the MSG locale catalog in the template")
    if default_short in catalog.group(0):
        fail(
            f"the locale catalog hardcodes {default_short!r} - locale strings "
            "must take the school name as a parameter (see \"school.line\"), "
            "in all five tables, so no page shows another school's name"
        )

    return canonical, og_url


def build_school_html(base_html, defaults, school, default_short):
    canonical, og_url = defaults
    short = school["short"]

    new_canonical = canonical.rstrip("/") + f"/{school['slug']}/"
    new_og_url = og_url.rstrip("/") + f"/{school['slug']}/"

    # Identity first, then the two URLs - the URLs contain no school name, so
    # the order is only about keeping each rewrite's anchor text intact.
    html = base_html.replace(default_short, short)
    html = html.replace(
        f'<link rel="canonical" href="{canonical}">',
        f'<link rel="canonical" href="{new_canonical}">',
        1,
    )
    html = html.replace(
        f'<meta property="og:url" content="{og_url}">',
        f'<meta property="og:url" content="{new_og_url}">',
        1,
    )

    if html.count(SW_REGISTER_OLD) != 1:
        fail(
            f"expected exactly one {SW_REGISTER_OLD!r} in {TEMPLATE}, "
            f"found {html.count(SW_REGISTER_OLD)}"
        )
    html = html.replace(SW_REGISTER_OLD, SW_REGISTER_NEW, 1)

    matches = SCRIPT_ANCHOR_RE.findall(html)
    if len(matches) != 1:
        fail(
            f"expected exactly one script anchor in {TEMPLATE}, "
            f"found {len(matches)}"
        )
    nl = "\r\n" if "\r\n" in html else "\n"
    school_line = (
        f'<script>window.SCHOOL="{school["id"]}";'
        f'window.SCHOOL_BASE="../data/";</script>'
    )
    html, n = SCRIPT_ANCHOR_RE.subn(
        lambda m: school_line + nl + m.group(0), html, count=1
    )
    assert n == 1  # already checked above; guards against a future edit drifting

    return html


def build_manifest(school):
    # Per-school manifest, not a link rewrite: manifest.json's own "." values
    # (start_url, scope) resolve relative to the MANIFEST's URL, not the
    # page's. Pointing every school at the shared root manifest would make
    # every installed home-screen icon - Hugo Reid's included - launch back
    # into the Holly Avenue default page, which is exactly the kind of
    # "speaking for another school" this whole feature exists to avoid.
    # Icons are referenced back at the shared files (not copied) since they
    # aren't school-specific and manifest icon paths resolve the same way.
    return {
        "name": f'{school["short"]} PTA — Legislation Watch',
        "short_name": f'{school["short"]} PTA',
        "description": (
            "What district and state decisions mean for your kid's "
            f'school week at {school["name"]}.'
        ),
        "start_url": ".",
        "scope": ".",
        "display": "standalone",
        "background_color": "#faf8f4",
        "theme_color": "#8a4b2d",
        "icons": [
            {
                "src": "../icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "../icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
        ],
    }


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def sweep_stale(current_slugs):
    """Remove generated directories for schools no longer in schools.json.
    Only ever touches a directory that (a) is not a protected hand-
    maintained name and (b) actually carries our marker file - so a
    directory this script didn't create is never at risk, no matter its
    name."""
    removed = []
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir() or entry.name in PROTECTED_NAMES:
            continue
        if not (entry / MARKER_NAME).exists():
            continue
        if entry.name not in current_slugs:
            shutil.rmtree(entry)
            removed.append(entry.name)
    return removed


def main():
    doc, schools = load_schools()
    base_html = read_template()

    default_id = doc["default"]
    default_school = next(s for s in schools if s["id"] == default_id)
    defaults = extract_default_fields(base_html, default_school["short"])

    failures = []
    for school in schools:
        try:
            html = build_school_html(base_html, defaults, school, default_school["short"])
            out_dir = ROOT / school["slug"]
            write_text(out_dir / "index.html", html)
            write_text(
                out_dir / "manifest.json",
                json.dumps(build_manifest(school), indent=2) + "\n",
            )
            write_text(
                out_dir / MARKER_NAME,
                json.dumps({"id": school["id"], "slug": school["slug"]}) + "\n",
            )
            print(
                f"built {school['slug']}/  (id={school['id']}, "
                f"published={school.get('published', False)})"
            )
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 - report and keep going
            failures.append(school["slug"])
            print(f"FAILED {school['slug']}: {e}", file=sys.stderr)

    removed = sweep_stale({s["slug"] for s in schools})
    for slug in removed:
        print(f"removed stale {slug}/  (no longer in {SCHOOLS_JSON.name})")

    if failures:
        fail(f"failed to build: {', '.join(failures)}")


if __name__ == "__main__":
    main()
