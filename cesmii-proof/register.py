#!/usr/bin/env python3
"""Idempotent, narrow registration in the existing AXM Tools directory."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
marker='<!-- cesmii-proof-card:start -->'
p=ROOT/'index.html';s=p.read_text()
if marker not in s:
    card='''\n<!-- cesmii-proof-card:start -->
<div class="tool">
  <div class="title"><a href="cesmii-proof/">AXM × i3X · Decision Continuity Proof</a></div>
  <div class="desc">Independent CESMII-aligned application lab: retain public i3X context, combine three teams’ synthetic evidence, correct a decision and replay the actual exported capsule on another client. Includes a sourced overlap map, seven-workflow heat map, six reusable recipes, adversarial tests and offline source.</div>
  <a class="open" href="cesmii-proof/">Run the manufacturing proof →</a>
</div>
<!-- cesmii-proof-card:end -->\n'''
    if '</header>' not in s:raise SystemExit('Directory anchor changed; review before registering.')
    p.write_text(s.replace('</header>','</header>\n'+card,1))
p=ROOT/'README.md';s=p.read_text()
if '[`cesmii-proof/`]' not in s:
    row='| [`cesmii-proof/`](cesmii-proof/) | Independent i3X application proof: public demo capture, source-bound three-team calculation, correction and fresh-client replay; sourced opportunity map and reusable synthetic recipes | [Run the proof](https://bigbirdreturns.github.io/axm-tools/cesmii-proof/) |\n'
    anchor='|------|--------------|-----------|\n'
    if anchor not in s:raise SystemExit('README table anchor changed; review before registering.')
    p.write_text(s.replace(anchor,anchor+row,1))
p=ROOT/'CONTINUITY.md';s=p.read_text();heading='## CESMII / i3X proof, 9 November 2026'
if heading not in s:
    p.write_text(s+'\n\n'+heading+'\n\n`cesmii-proof/` is an independent, self-contained application lab. Its owner README separates public demo evidence, synthetic organizational inputs and unqualified production behavior. The exact Team Commons core is copied and source-hashed at build time; there is no shared browser runtime. The bounded collector only discovers and reads the explicitly selected API. Retained source timestamps never become current observations by rebuilding. The dedicated CI preserves a one-time public capture, tests logic and actual browser transfer, and commits generated source assets before main publication. No private introductions or correspondence are public inputs.\n')
print('CESMII proof directory registration verified')
