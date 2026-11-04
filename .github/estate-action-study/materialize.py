"""One-time public-safe authored study transfer, checksum locked. No private data access."""
from pathlib import Path
import gzip,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
PARTS=Path(__file__).resolve().parent
TARGET=ROOT/'decision-floor/estate'
compressed=b''.join((PARTS/n).read_bytes() for n in ('01.part','02.part','03.part'))
assert len(compressed)==18106
raw=gzip.decompress(compressed)
expected='372b0cd1ae5c081698639c803e17e5f2bcbbecf54fc74dc2639e22b4007b3df2'
assert len(raw)==53219 and hashlib.sha256(raw).hexdigest()==expected
text=raw.decode('utf-8')
for forbidden in ('C:/Users/','S:/Projects/','7YedJ32PgVAr5ZsU_','BEGIN PRIVATE KEY','recorder.sqlite3'):
    assert forbidden not in text, 'Private material in authored projection'
TARGET.mkdir(parents=True,exist_ok=True)
p=TARGET/'index.html'
if p.exists() and p.read_bytes()!=raw:raise RuntimeError('Existing study changed; review before replacing it')
p.write_bytes(raw)
m=re.search(r'<script type="application/json" id="study-data">(.*?)</script>',text,re.S)
assert m
case=json.loads(m.group(1))
assert case['schema']=='axm/estate-action-study@1' and len(case['cases'])==10
assert len(case['sources'])==19
for c in case['cases']:
    assert all(c.get(k) for k in ('intent','mechanism','measured','change','retain','action','accept','failure','refs'))
    assert all(k in case['sources'] for k in c['refs'])
for s in case['sources'].values():assert re.fullmatch('[a-f0-9]{64}',s['sha256']) and s['line']>0
assert case['metrics']['policy_before']-case['metrics']['policy_after']==40163
assert case['metrics']['prompt_later']-case['metrics']['prompt_applied']==2266
(TARGET/'case-data.json').write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
subprocess.run([sys.executable,str(TARGET/'verify_browser.py')],cwd=ROOT,check=True,timeout=120)
# Add an entrance inside the existing product without changing its reconciliation engine or archive.
p=ROOT/'decision-floor/index.html';main=p.read_text(encoding='utf8')
if 'id="estate-case"' not in main:
    anchor='<section class="local wrap" id="local">'
    assert anchor in main, 'Product insertion point changed'
    block='<section class="foundation wrap" id="estate-case"><p class="eyebrow">A REAL OPERATIONAL CASE</p><h2>Decisions that outlived their assumptions.</h2><p class="foundation-intro">The Estate records the same inherited-decision problem inside its own operating system. Follow ten source-linked histories, replay the measured consequences and export a proposed corrective action.</p><p><a class="button" href="estate/">Open the Estate action study ↗</a></p></section>\n'
    p.write_text(main.replace(anchor,block+anchor,1),encoding='utf8')
subprocess.run([sys.executable,str(ROOT/'decision-floor/scripts/build_release.py'),'--check'],cwd=ROOT,check=True,timeout=60)
print(json.dumps({'status':'PASS','html_sha256':expected,'authored_bytes':len(raw),'chains':10,'scope':'Public-safe derived case; original corpus remains in owner-controlled custody'}))
