#!/usr/bin/env python3
"""Build the SCHISM public research edition using only the Python standard library."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content.json"
ORIGINAL_SHA256 = "9031a44f97fa877850010f994aabd93af17feb8ae47e47e26816054c2792c40e"
PUBLIC_URL = "https://bigbirdreturns.github.io/axm-tools/schism/"

CSS = r"""
:root{--bg:#090d12;--panel:#101820;--ink:#e9eef3;--steel:#c3ced9;--muted:#99a9b8;--accent:#9acbe9;--line:#293744;--faint:#718697;--warm:#d8b58a;color-scheme:dark;font-family:Arial,Helvetica,sans-serif;font-synthesis:none}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:100px}body{margin:0;background:var(--bg);color:var(--ink);font-size:17px;line-height:1.65}a{color:var(--accent);text-underline-offset:.22em}a:hover{color:#fff}a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:5px}img{display:block;max-width:100%;height:auto}button{font:inherit}.wrap{width:min(1192px,100% - 80px);margin-inline:auto}.mono,.eyebrow,.track-n,.source-n,.date,.tag,.edition,.credit-label{font-family:Consolas,'Liberation Mono',monospace}.eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--accent);font-weight:500}.skip{position:absolute;top:-100px;left:20px;z-index:50;background:var(--ink);color:var(--bg);padding:10px}.skip:focus{top:12px}.topbar{position:sticky;top:0;z-index:20;background:rgba(9,13,18,.97);border-bottom:1px solid var(--line)}.top-inner{min-height:66px;display:flex;align-items:center;justify-content:space-between;gap:24px}.home{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--steel);text-decoration:none;font-weight:700}.home small{display:block;margin-top:2px;font-size:9px;font-weight:400;color:var(--muted);letter-spacing:.08em}.topbar nav{display:flex;gap:22px;align-items:center}.topbar nav a{font-size:11px;text-transform:uppercase;letter-spacing:.08em;text-decoration:none;color:var(--muted)}.topbar nav a:hover{color:var(--ink)}.edition{font-size:10px;color:var(--accent);white-space:nowrap}.hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:64px;align-items:center;padding-top:68px;padding-bottom:68px}.cover{margin:0;position:relative}.cover img{border:1px solid var(--line);width:100%;box-shadow:0 24px 70px rgba(0,0,0,.3)}figcaption{font-size:10px;line-height:1.6;color:var(--faint);margin-top:12px}.kicker{margin:0 0 18px}.hero h1{font-weight:400;font-size:clamp(54px,6.6vw,90px);letter-spacing:.16em;line-height:1;margin:0 0 24px}.hero h2{font-size:clamp(28px,3vw,40px);line-height:1.15;font-weight:400;margin:0 0 24px;letter-spacing:-.025em}.hero-deck{font-size:19px;color:var(--steel);line-height:1.55;margin:0}.credits{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 24px;border-top:1px solid var(--line);padding-top:24px;margin-top:28px}.credit-label{display:block;color:var(--faint);font-size:9px;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}.credit-value{font-size:13px;color:var(--steel)}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:26px}.button{border:1px solid #426079;color:var(--ink);background:transparent;padding:10px 14px;font-size:11px;letter-spacing:.05em;text-decoration:none;line-height:1.45;display:inline-flex;align-items:center;gap:6px;cursor:pointer}.button.primary{background:var(--accent);border-color:var(--accent);color:#09121a}.button:hover{background:#1c2b38}.button.primary:hover{background:#c0e4fa;color:#09121a}.statement{padding:32px 0 46px;border-top:1px solid var(--line);display:grid;grid-template-columns:180px minmax(0,1fr);gap:40px}.statement p{margin:0 0 16px;font-size:20px;line-height:1.6;color:var(--steel);max-width:78ch}.statement p:last-child{margin-bottom:0}.statement .eyebrow{padding-top:6px}.section{padding:60px 0;border-top:1px solid var(--line);scroll-margin-top:86px}.section-head{display:grid;grid-template-columns:64px minmax(0,1fr);gap:20px;margin-bottom:24px;align-items:baseline}.section-head .track-n{font-size:12px;color:var(--accent);letter-spacing:.06em}.section-head h2{font-size:29px;font-weight:500;letter-spacing:-.025em;line-height:1.2;margin:0}.section-head .deck{font-size:15px;line-height:1.55;color:var(--muted);margin:12px 0 0}.section-content{margin-left:84px}.section-content p{max-width:83ch;color:var(--steel);margin:0 0 20px;font-size:17px;line-height:1.72}.section-content p:last-child{margin-bottom:0}.section-content strong{color:var(--ink)}.ref{font-family:Consolas,'Liberation Mono',monospace;white-space:nowrap;font-size:10px;margin-left:4px;font-weight:400}.ref a{text-decoration:none;color:var(--accent)}.tracklist{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:32px}.track{display:grid;grid-template-columns:32px minmax(0,1fr) 18px;gap:12px;align-items:center;text-decoration:none;padding:17px 0;border-top:1px solid var(--line);color:var(--steel);font-size:14px;line-height:1.35}.track .track-n{color:var(--accent);font-size:10px}.track span:last-child{color:var(--faint)}.track:hover{color:var(--ink)}.track:hover span:last-child{color:var(--accent)}.table-wrap{overflow-x:auto;border:1px solid var(--line);margin:28px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.6;text-align:left}th{background:#17232e;color:var(--accent);font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:500}td,th{padding:15px 17px;border-bottom:1px solid var(--line);vertical-align:top}td{color:var(--steel)}td:first-child{font-weight:600;color:var(--ink);width:20%}tr:last-child td{border-bottom:0}.timeline{display:grid;grid-template-columns:170px minmax(0,1fr);border-top:1px solid var(--line);padding:22px 0;column-gap:24px}.timeline .date{font-size:11px;color:var(--accent)}.timeline h3{font-size:16px;line-height:1.4;margin:0 0 6px;font-weight:600}.timeline p{font-size:14px;line-height:1.65;margin:0;color:var(--muted);max-width:80ch}.sources-intro{font-size:14px;color:var(--muted);max-width:82ch}.source{border-top:1px solid var(--line);padding:18px 0;scroll-margin-top:90px}.source summary{cursor:pointer;display:grid;grid-template-columns:40px minmax(0,1fr) 20px;gap:12px;list-style:none;align-items:baseline;line-height:1.4}.source summary::-webkit-details-marker{display:none}.source summary:after{content:'+';font-family:Consolas,monospace;color:var(--faint)}.source[open] summary:after{content:'−'}.source-n{font-size:10px;color:var(--accent)}.source-title{font-size:15px;color:var(--steel)}.source-body{margin-left:52px;margin-top:14px;font-size:13px;color:var(--muted);max-width:85ch}.source-body p{margin:0 0 10px}.tag{font-size:9px;text-transform:uppercase;letter-spacing:.05em;border:1px solid var(--line);padding:3px 6px;display:inline-block;margin-right:8px;color:var(--accent)}.source-body a{overflow-wrap:anywhere}.source-body strong{color:var(--steel);font-weight:600}.editorial{font-size:14px;color:var(--muted);max-width:89ch}.editorial p{margin:0 0 15px}.provenance{margin-top:24px;border-left:2px solid #426079;background:#0e161e;padding:20px 24px;font-size:12px;color:var(--muted)}.provenance p{margin:0 0 10px}.provenance p:last-child{margin-bottom:0}.hash{font-family:Consolas,'Liberation Mono',monospace;font-size:11px;overflow-wrap:anywhere;display:block;color:var(--steel);margin-top:6px}.footer{border-top:1px solid var(--line);padding:34px 0 52px;display:flex;justify-content:space-between;gap:30px;font-size:11px;color:var(--faint)}.footer a{color:var(--muted)}.footer p{margin:0}.back-top{font-size:12px;white-space:nowrap}.print-label{display:none}.section-content a,.editorial a{overflow-wrap:anywhere}.deck,.hero-deck{text-wrap:pretty}
@media(min-width:1500px){.hero{padding-top:84px;padding-bottom:84px}}
@media(max-width:1000px){.wrap{width:calc(100% - 48px)}.hero{gap:36px}.hero h1{font-size:60px}.hero h2{font-size:30px}.hero-deck{font-size:17px}.topbar nav{gap:14px}.statement{grid-template-columns:140px minmax(0,1fr);gap:24px}}
@media(max-width:760px){.wrap{width:calc(100% - 36px)}.top-inner{min-height:62px;gap:10px;flex-wrap:wrap;padding-top:12px;padding-bottom:10px}.topbar nav{order:3;width:100%;justify-content:space-between;gap:10px;padding-top:8px}.topbar nav a{font-size:10px}.edition{font-size:9px}.hero{grid-template-columns:1fr;gap:32px;padding:36px 0 42px}.cover{max-width:500px;margin-inline:auto}.hero h1{font-size:62px}.hero h2{font-size:34px;max-width:20ch}.hero-deck{font-size:18px}.credits{gap:16px}.hero-meta .kicker{font-size:9px}.statement{grid-template-columns:1fr;gap:18px;padding:30px 0}.statement p{font-size:18px}.section{padding:38px 0}.section-head{grid-template-columns:36px minmax(0,1fr);gap:10px;margin-bottom:24px}.section-head h2{font-size:25px}.section-content{margin-left:0}.section-content p{font-size:16px}.tracklist{grid-template-columns:1fr}.track{padding:14px 0}.table-wrap{border:0}table,thead,tbody,tr,th,td{display:block}thead{display:none}tbody{display:grid;gap:14px}tr{border:1px solid var(--line);padding:14px 16px;background:var(--panel)}td,th{padding:0;border:0}td{margin-top:10px;font-size:13px}td:first-child{width:auto;margin:0;font-size:15px}td:not(:first-child):before{content:attr(data-label);display:block;font-size:9px;line-height:1.6;text-transform:uppercase;color:var(--accent);letter-spacing:.06em;margin-bottom:3px}.timeline{grid-template-columns:1fr;gap:9px;padding:20px 0}.source-body{margin-left:0}.source summary{grid-template-columns:28px minmax(0,1fr) 16px;gap:10px}.source-title{font-size:14px}.footer{display:block;padding-bottom:32px}.back-top{display:block;margin-top:18px}.provenance{padding:16px}.actions .button{padding:10px 12px;font-size:10px}html{scroll-padding-top:125px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{ :root{color-scheme:light;--bg:#fff;--ink:#101820;--steel:#263442;--muted:#465b6c;--accent:#234f72;--line:#bcc8d1;--faint:#526777;--panel:#f4f7fa}body{font-size:11pt;background:#fff;color:#101820}.wrap{width:100%}.topbar,.actions,.skip,.back-top{display:none}.hero{padding:0 0 24px;gap:28px;grid-template-columns:.75fr 1.25fr}.hero h1{font-size:44px}.hero h2{font-size:24px}.hero-deck{font-size:12pt}.hero img{box-shadow:none}.credits{gap:12px;margin-top:16px;padding-top:12px}.credit-value{font-size:10pt}.statement{padding:22px 0;gap:22px;grid-template-columns:110px 1fr}.statement p{font-size:11pt}.section{padding:24px 0}.section-head{grid-template-columns:35px 1fr;margin-bottom:12px;gap:12px}.section-head h2{font-size:18pt}.section-head .deck{font-size:10pt}.section-content{margin-left:47px}.section-content p{font-size:10pt;line-height:1.55;margin-bottom:12px}table{font-size:9pt}th,td{padding:8px}.track{font-size:9pt;padding:9px 0}.timeline{padding:12px 0;grid-template-columns:120px 1fr}.timeline h3{font-size:11pt}.timeline p{font-size:9pt}.source-title{font-size:10pt}.source-body{font-size:9pt}.source{padding:10px 0}.source summary:after{display:none}.editorial{font-size:9pt}.provenance{background:#f4f7fa;font-size:9pt}.footer{font-size:8pt;padding:16px 0}.table-wrap,tr,.timeline,.source,.provenance{break-inside:avoid}.cover{break-inside:avoid}.source-body{display:block}.source:not([open]) .source-body{display:block}@page{size:A4;margin:16mm}}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def markup(value: str) -> str:
    safe = esc(value)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"\[(S\d+)\]", lambda m: f'<sup class="ref"><a href="#source-{m[1]}">{m[1]}</a></sup>', safe)
    return safe


def refs(ids: list[str]) -> str:
    if not ids:
        return ""
    return '<sup class="ref">' + " ".join(f'<a href="#source-{esc(i)}" aria-label="Source {esc(i)}">[{esc(i)}]</a>' for i in ids) + "</sup>"


def paragraph(value: dict) -> str:
    return f'<p>{markup(value["text"])}{refs(value.get("refs", []))}</p>'


def format_table(value: dict) -> str:
    headers = value["headers"]
    head = "".join(f'<th scope="col">{esc(h)}</th>' for h in headers)
    rows = "".join("<tr>" + "".join(f'<td data-label="{esc(headers[i])}">{markup(c)}</td>' for i, c in enumerate(row)) + "</tr>" for row in value["rows"])
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'


def build_html(data: dict, cover_src: str, offline: bool = False) -> str:
    resource_base = PUBLIC_URL if offline else ""
    tracklist = "".join(f'<a class="track" href="#{esc(s["id"])}"><span class="track-n">{esc(s["number"])}</span><span>{esc(s["title"])}</span><span aria-hidden="true">↗</span></a>' for s in data["sections"])
    sections = []
    for s in data["sections"]:
        body = "".join(paragraph(p) for p in s["paragraphs"])
        if s.get("table"):
            body += format_table(s["table"])
        sections.append(f'<section class="section" id="{esc(s["id"])}"><div class="section-head"><span class="track-n">{esc(s["number"])}</span><div><h2>{esc(s["title"])}</h2><p class="deck">{esc(s["deck"])}</p></div></div><div class="section-content">{body}</div></section>')
    timeline = "".join(f'<div class="timeline"><div class="date">{esc(t["date"])}</div><div><h3>{esc(t["label"])}</h3><p>{markup(t["text"])}{refs(t.get("refs", []))}</p></div></div>' for t in data["timeline"])
    source_blocks = []
    for source in data["sources"]:
        source_blocks.append(f'<details class="source" id="source-{esc(source["id"])}"><summary><span class="source-n">{esc(source["id"])}</span><span class="source-title">{esc(source["title"])}</span></summary><div class="source-body"><p><span class="tag">{esc(source["evidence_type"])}</span>{esc(source["publisher"])} · {esc(source["date"])}</p><p><strong>Supports:</strong> {esc(source["supports"])}</p><p><strong>Boundary:</strong> {esc(source["limits"])}</p><a href="{esc(source["url"])}" target="_blank" rel="noopener noreferrer">Read original source ↗</a></div></details>')
    actions = '<a class="button primary" href="#tracklist">Read the dossier ↓</a>'
    if offline:
        actions += f'<a class="button" href="{PUBLIC_URL}">Public edition ↗</a>'
    else:
        actions += '<a class="button" href="SCHISM-v1.2-offline.html" download>Download offline HTML ↓</a><a class="button" href="SCHISM-v1.2-public.zip" download>Release package ↓</a>'
    lead = "".join(paragraph(p) for p in data["lead"])
    notes = "".join(paragraph(p) for p in data["editorial_notes"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light">
<title>SCHISM | Darkhive Stack Sovereignty Dossier | Jonathan Sandhu</title>
<meta name="description" content="An independent, source-backed public edition of the June 2026 SCHISM dossier: FleetForge, supplier dependence, customer control, and the evidence required to establish sovereignty.">
<meta name="author" content="Jonathan Sandhu"><meta property="og:title" content="SCHISM: From Deployment Tool to Sovereign Stack"><meta property="og:description" content="The June 2026 thesis, the public record, and the customer-control question. Independent research by Jonathan Sandhu."><meta property="og:type" content="article"><meta property="og:url" content="{PUBLIC_URL}"><meta property="og:image" content="{PUBLIC_URL}assets/cover.png"><meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{PUBLIC_URL}"><style>{CSS}</style></head>
<body id="top"><a class="skip" href="#dossier">Skip to dossier</a>
<header class="topbar"><div class="wrap top-inner"><a class="home" href="https://bigbirdreturns.github.io/axm-tools/">Jonathan Sandhu<small>Independent research / SCG</small></a><nav aria-label="Dossier navigation"><a href="#tracklist">Tracklist</a><a href="#chronology">Chronology</a><a href="#sources">Sources</a><a href="#edition">Edition</a></nav><span class="edition">SCHISM / {esc(data['version'])}</span></div></header>
<main class="wrap" id="dossier"><div class="hero"><figure class="cover"><img src="{cover_src}" alt="Original SCHISM editorial cover: three figures in a dark architectural setting, with DARKHIVE and SCHISM lettering." width="1254" height="1254" fetchpriority="high"><figcaption>Original AI-generated editorial artwork, June 2026.</figcaption></figure>
<div class="hero-meta"><p class="eyebrow kicker">Darkhive / Stack Sovereignty Dossier</p><h1>SCHISM</h1><h2>From Deployment Tool<br>to Sovereign Stack</h2><p class="hero-deck">Customer control depends on the rights, records, and support paths that remain usable when a supplier changes.</p><div class="credits"><div><span class="credit-label">Original circulation</span><span class="credit-value">26 June 2026</span></div><div><span class="credit-label">Public edition</span><span class="credit-value">26 November 2026</span></div><div><span class="credit-label">Author</span><span class="credit-value">Jonathan Sandhu</span></div><div><span class="credit-label">Scope</span><span class="credit-value">Ownership &amp; procurement</span></div></div><div class="actions">{actions}</div></div></div>
<div class="statement"><div class="eyebrow">The argument</div><div>{lead}</div></div>
<section class="section" id="tracklist"><div class="section-head"><span class="track-n">A1–A10</span><div><h2>Ten tracks. One control question.</h2><p class="deck">Read the dossier in order, or open a specific part of the argument.</p></div></div><div class="tracklist">{tracklist}</div></section>
{''.join(sections)}
<section class="section" id="chronology"><div class="section-head"><span class="track-n">LOG</span><div><h2>The dated record</h2><p class="deck">Original analysis, prior public positioning, and subsequent announcements retain their separate dates.</p></div></div>{timeline}</section>
<section class="section" id="sources"><div class="section-head"><span class="track-n">REF</span><div><h2>Source register</h2><p class="deck">Open each entry for its source type, supported claim, and evidentiary limit.</p></div></div><p class="sources-intro">Links point to primary public records. A company announcement establishes what the company said; an award record establishes the recorded award. Interpretations in this dossier belong to the author. Sources checked 26 November 2026.</p>{''.join(source_blocks)}</section>
<section class="section" id="edition"><div class="section-head"><span class="track-n">EDN</span><div><h2>Edition and provenance</h2><p class="deck">A public research edition of the original privately circulated dossier.</p></div></div><div class="editorial">{notes}</div><div class="provenance"><p><strong>Original:</strong> 26 June 2026, 15:35:33 PDT. The author's sent-mail archive retains the original 3,120,400-byte HTML attachment and its circulation timestamp. This edition publishes the artifact identity; the underlying correspondence remains private.</p><p><strong>SHA-256 of the retained original:</strong><span class="hash">{ORIGINAL_SHA256}</span></p><p>The digest identifies the retained bytes. Independent confirmation of the original circulation date requires access to the original record. Public edition {esc(data['version'])} is dated 26 November 2026.</p></div><div class="actions"><a class="button" href="{resource_base}SCHISM.md">Readable text ↗</a><a class="button" href="{resource_base}sources.json">Sources JSON ↗</a><a class="button" href="{resource_base}provenance.json">Provenance JSON ↗</a></div></section>
</main><footer class="wrap footer"><div><p>SCHISM · Public edition {esc(data['version'])} · Jonathan Sandhu</p><p>Independent research. Editorial artwork and analysis are authored for this dossier.</p></div><a class="back-top" href="#top">Back to top ↑</a></footer>
<script>
document.addEventListener('click',function(e){{const a=e.target.closest('a[href^="#source-"]');if(a){{const target=document.getElementById(a.getAttribute('href').slice(1));if(target)target.open=true;}}}});
function openSourceHash(){{if(location.hash.startsWith('#source-')){{const e=document.getElementById(location.hash.slice(1));if(e)e.open=true;}}}}
window.addEventListener('hashchange',openSourceHash);openSourceHash();
window.addEventListener('beforeprint',function(){{document.querySelectorAll('details.source').forEach(function(e){{e.dataset.openBeforePrint=e.open?'1':'0';e.open=true;}});}});
window.addEventListener('afterprint',function(){{document.querySelectorAll('details.source').forEach(function(e){{e.open=e.dataset.openBeforePrint==='1';}});}});
</script></body></html>
'''


def markdown(data: dict) -> str:
    def ptext(p: dict) -> str:
        return p["text"] + (" " + " ".join(f'[{s}](#{s.lower()})' for s in p.get("refs", [])) if p.get("refs") else "")
    lines = ["# SCHISM", "", "## Darkhive Stack Sovereignty Dossier", "", f"Jonathan Sandhu · Public edition {data['version']} · {data['release_date']}", "", "Original privately circulated 2026-06-26. Public edition first published 2026-11-26.", ""]
    lines += [ptext(p) + "\n" for p in data["lead"]]
    for s in data["sections"]:
        lines += [f"## {s['number']}. {s['title']}", "", s["deck"], ""]
        lines += [ptext(p) + "\n" for p in s["paragraphs"]]
        if s.get("table"):
            t=s["table"]
            lines += ["| " + " | ".join(t["headers"]) + " |", "| " + " | ".join("---" for _ in t["headers"]) + " |"]
            lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in t["rows"]]
            lines.append("")
    lines += ["## Dated record", ""]
    for t in data["timeline"]:
        lines += [f"### {t['date']}: {t['label']}", "", ptext(t), ""]
    lines += ["## Sources", ""]
    for s in data["sources"]:
        lines += [f'<a id="{s["id"].lower()}"></a>',f"### {s['id']}","",f"[{s['title']}]({s['url']})", "",f"{s['publisher']} · {s['date']} · {s['evidence_type']}", "",f"Supports: {s['supports']}","",f"Boundary: {s['limits']}",""]
    lines += ["## Edition and provenance", ""] + [ptext(p) + "\n" for p in data["editorial_notes"]]
    lines += [f"Retained original SHA-256: `{ORIGINAL_SHA256}`", "", "The author's original sent-mail archive establishes a circulation timestamp of 2026-06-26T15:35:33-07:00. The correspondence remains private. The digest identifies the retained bytes, not an independently accessible public timestamp.", ""]
    return "\n".join(lines)


def main() -> None:
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    assert len(data["sections"]) == 10
    source_ids = {s["id"] for s in data["sources"]}
    for p in data["lead"] + data["editorial_notes"] + data["timeline"] + [p for s in data["sections"] for p in s["paragraphs"]]:
        assert set(p.get("refs", [])) <= source_ids, p
    assert "\u2014" not in json.dumps(data, ensure_ascii=False), "Remove em dashes from public copy"
    cover = (ROOT / "assets" / "cover.png").read_bytes()
    (ROOT / "index.html").write_text(build_html(data, "assets/cover.png"), encoding="utf-8")
    cover_data = "data:image/png;base64," + base64.b64encode(cover).decode("ascii")
    offline = build_html(data, cover_data, offline=True)
    (ROOT / "SCHISM-v1.2-offline.html").write_text(offline, encoding="utf-8")
    (ROOT / "SCHISM.md").write_text(markdown(data), encoding="utf-8")
    (ROOT / "sources.json").write_text(json.dumps({"checked_on":"2026-11-26","sources":data["sources"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    provenance = {"title":"SCHISM: Darkhive Stack Sovereignty Dossier","author":"Jonathan Sandhu","public_version":data["version"],"public_release_date":"2026-11-26","public_url":PUBLIC_URL,"timezone":"America/Los_Angeles","original":{"filename":"DARKHIVE - Schism Dossier (standalone).html","sha256":ORIGINAL_SHA256,"size_bytes":3120400,"private_circulation_timestamp":"2026-06-26T15:35:33-07:00","date_evidence":"Author's retained sent-mail record; correspondence not reproduced in this public edition","state":"Retained historical input, not publicly released as part of this edition"},"artwork":{"file":"assets/cover.png","origin":"AI-generated editorial artwork embedded in the June 2026 original","sha256":hashlib.sha256(cover).hexdigest(),"modified":False},"lead_time_claim":{"elapsed_days":153,"meaning":"Age of original privately circulated dossier on public release date","verified_predictive_lead":None},"public_edition_scope":"High-level independent ownership, sourcing, and procurement analysis; no confidential correspondence, customer data, or operational implementation plans.","editorial_changes":[p["text"] for p in data["editorial_notes"]]}
    (ROOT / "provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    readme = f'''# SCHISM public edition {data['version']}

Independent research by Jonathan Sandhu. Original privately circulated 26 June 2026; public edition dated 26 November 2026.

Live: {PUBLIC_URL}

## Read

Open `index.html` with its adjacent `assets/cover.png`, or open `SCHISM-v1.2-offline.html` as a single self-contained file. The dossier text, navigation, artwork, source register, and provenance are available offline; visiting external references requires a connection. `SCHISM.md` provides the same analytical content as readable text. `sources.json` and `provenance.json` retain source boundaries and artifact identity.

## Rebuild

Run `python3 build.py` in this directory. It uses the Python standard library and reads only `content.json` and `assets/cover.png`. The generated files contain the public analysis only. Private historical source material stays outside the publication tree.

## Edition

This release preserves the original ten-part organization and editorial artwork. It adds primary-source support, corrects unsupported categorical claims, and presents the high-level ownership and procurement analysis as an independent public edition. The original engineering schedules and operational implementation material are outside this publication's scope. Historical proposals are not represented as completed work.

## Rights

Authored analysis © 2026 Jonathan Sandhu. Sources retain their respective rights and are linked for attribution. The cover is identified as AI-generated editorial artwork. Darkhive is the subject of this independent analysis.

## Maintenance

External source URLs and living company pages can change. The source register records the review date and the boundary of each claim. Revise the analysis through a new public edition and preserve the original artifact identity. This directory performs no scheduled refresh, account access or remote computation.
'''
    (ROOT / "README.md").write_text(readme,encoding="utf-8")
    package = ROOT / "SCHISM-v1.2-public.zip"
    with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in ["index.html","SCHISM-v1.2-offline.html","SCHISM.md","sources.json","provenance.json","README.md","content.json","build.py","assets/cover.png"]:
            info = zipfile.ZipInfo("SCHISM-v1.2/"+name, date_time=(2026,11,26,0,0,0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT/name).read_bytes(), compresslevel=9)
    files=["index.html","SCHISM-v1.2-offline.html","SCHISM.md","sources.json","provenance.json","content.json","build.py","README.md","assets/cover.png","SCHISM-v1.2-public.zip"]
    sums="".join(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()+"  "+name+"\n" for name in files)
    (ROOT/"SHA256SUMS").write_text(sums,encoding="utf-8")
    print(json.dumps({"status":"built","version":data["version"],"section_count":len(data["sections"]),"source_count":len(data["sources"]),"files":[{"name":n,"bytes":(ROOT/n).stat().st_size} for n in files]},indent=2))


if __name__ == "__main__":
    main()
