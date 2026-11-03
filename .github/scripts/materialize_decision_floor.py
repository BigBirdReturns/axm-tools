#!/usr/bin/env python3
"""Materialize the checksum-locked public source, then independently qualify it."""
from pathlib import Path, PurePosixPath
import hashlib, io, json, lzma, subprocess, sys, tarfile, urllib.request
ROOT=Path(__file__).resolve().parents[2]
CAP=ROOT/'.github/decision-floor-release'
META=json.loads((CAP/'manifest.json').read_text())
payload=b''.join((CAP/n).read_bytes() for n in META['parts'])
assert len(payload)==META['bytes'], 'Capsule length mismatch'
assert hashlib.sha256(payload).hexdigest()==META['sha256'], 'Capsule digest mismatch'
expanded=lzma.decompress(payload)
assert len(expanded)<2_000_000, 'Expansion limit exceeded'
seen=set()
with tarfile.open(fileobj=io.BytesIO(expanded),mode='r:') as archive:
    for member in archive:
        p=PurePosixPath(member.name)
        assert member.isfile() and not p.is_absolute() and '..' not in p.parts and p.parts[0]=='decision-floor', 'Unsafe capsule entry'
        assert str(p) not in seen, 'Duplicate capsule entry'
        seen.add(str(p))
        dest=ROOT.joinpath(*p.parts)
        assert not dest.is_symlink(), 'Refuse symlink destination'
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(archive.extractfile(member).read())
assert len(seen)==META['files'], 'Source coverage mismatch'
product=ROOT/'decision-floor'
asset=product/'assets/fichains-logo.png'
asset.parent.mkdir(exist_ok=True)
expected='fb138d4bb34189485452ec0c6d91760b41dbac294c106106e5e8cdaa34ad1126'
if not asset.exists():
    url='https://img1.wsimg.com/isteam/ip/634f50fc-7233-429a-bb9c-28aa903bad9f/blob-7dfc909.png/:/rs=w:415,h:98,cg:true,m/cr=w:415,h:98/qt=q:100/ll'
    req=urllib.request.Request(url,headers={'User-Agent':'AXM-public-evaluation-release'})
    with urllib.request.urlopen(req,timeout=30) as response: data=response.read(100000)
    assert len(data)==11042 and hashlib.sha256(data).hexdigest()==expected, 'Public product mark changed; review required'
    asset.write_bytes(data)
assert hashlib.sha256(asset.read_bytes()).hexdigest()==expected, 'Product mark integrity failed'
for script in ['build_fixture.py','build_release.py','browser_test.py']:
    subprocess.run([sys.executable,str(product/'scripts'/script)],cwd=ROOT,check=True,timeout=240)
subprocess.run([sys.executable,str(product/'scripts/build_release.py'),'--check'],cwd=ROOT,check=True,timeout=60)
card='''\n<div class="tool">\n  <div class="title"><a href="decision-floor/">Decision Continuity · fiChains workflow evaluation</a></div>\n  <div class="desc">Replay a demand revision through an approved decision, procurement, ERP, the production floor and a financial outcome. Inspect original statements, compare missed and verified execution, generate new synthetic cases and run the offline investigator on authorized local exports. Independent AXM evaluation; no customer records or live fiChains integration.</div>\n  <a class="open" href="decision-floor/">Open the decision workspace →</a>\n</div>\n'''
p=ROOT/'index.html';text=p.read_text()
if 'href="decision-floor/"' not in text:
    assert '</header>' in text, 'Index insertion point changed'
    p.write_text(text.replace('</header>','</header>\n'+card,1))
p=ROOT/'README.md';text=p.read_text()
if '[`decision-floor/`]' not in text:
    marker='|------|--------------|-----------|'
    assert marker in text, 'README tool table changed'
    row='| [`decision-floor/`](decision-floor/) | Source-recorded-time replay of decisions, promises, ERP/PO/floor receipts and outcomes; synthetic comparison, new cases, local report import and independently qualified offline source kit | [Open Decision Continuity](https://bigbirdreturns.github.io/axm-tools/decision-floor/) |'
    p.write_text(text.replace(marker,marker+'\n'+row,1))
p=ROOT/'CONTINUITY.md';text=p.read_text();heading='## Decision Continuity public evaluation (2026-11-03)'
if heading not in text:
    p.write_text(text+'\n\n'+heading+'\n\n`decision-floor/` is a self-contained independent AXM evaluation of the public fiChains workflow. Its synthetic histories are rebuilt from the shipped offline reconciliation engine. Read its README before changing evidence semantics. The browser preserves statements and separate event/source-record clocks, refuses conflicting approvals, and imports a local report without upload. The product mark is attributed, with no endorsement or live-integration claim. `scripts/build_release.py` freshly extracts and qualifies the source kit; `scripts/browser_test.py` exercises real Chromium, CSP, original-byte hashes, mobile layout and local File API import. The release capsule under `.github/decision-floor-release/` is the retained one-time source-transfer record, not a second runtime. Current source and generated artifacts live under the tool directory. Normal Pages publication retains the existing shared release gate and Cantos compatibility staging.\n')
print('DECISION_FLOOR_PUBLIC_CANDIDATE_PASS')
