#!/usr/bin/env python3
"""Public release integrity and custody checks. Python standard library only."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(value,message):
    if not value:raise SystemExit('REFUSED: '+message)
class Page(HTMLParser):
    def __init__(self):super().__init__();self.scripts=[];self.csp=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script':self.scripts.append(a)
        if tag=='meta' and a.get('http-equiv','').lower()=='content-security-policy':self.csp=a.get('content','')
owner=json.loads((ROOT/'source/OWNER.json').read_text())
require(digest(ROOT/'source/research-core.js')==owner['sha256'],'Native ResearchCore bytes changed.')
subprocess.run([sys.executable,str(ROOT/'scripts/build.py'),'--check'],check=True)
html=(ROOT/'index.html').read_text();page=Page();page.feed(html)
require(page.csp and "connect-src 'none'" in page.csp,'Network-computation boundary missing.')
require(all('src' not in x for x in page.scripts),'Runtime scripts must remain self-contained.')
for name in ['source/continuity.js','source/ui.js','source/measurements.js','source/measurement-ui.js','source/judgment.js','source/judgment-ui.js']:
    source=(ROOT/name).read_text()
    for pattern in [r'\bfetch\s*\(',r'\bXMLHttpRequest\b',r'\bsendBeacon\s*\(',r'\bWebSocket\s*\(']:
        require(not re.search(pattern,source),name+' contains an unexpected network operation.')
require(not list(ROOT.rglob('package.json')),'A browser runtime package dependency was introduced.')
for p in ROOT.rglob('*'):
    if p.resolve()==Path(__file__).resolve():continue
    if not p.is_file() or p.suffix.lower() not in ['.html','.js','.cjs','.py','.json','.md']:continue
    s=p.read_text(encoding='utf-8')
    for pattern in [r'F8N-(?:[0-9A-F]{4}-){7}[0-9A-F]{4}',r'gh[pousr]_[A-Za-z0-9]{30,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'browser-vault/captures/']:
        require(not re.search(pattern,s),'Credential or private-capture reference in public source: '+str(p.relative_to(ROOT)))
q=json.loads((ROOT/'data/qualification.json').read_text())
require(q.get('status')=='PASS','Candidate lacks retained qualification.')
for name,want in q.get('source_sha256',{}).items():
    require('..' not in Path(name).parts and not Path(name).is_absolute(),'Unsafe qualification path.')
    require(digest(ROOT/name)==want,'Qualified source changed: '+name)
w=json.loads((ROOT/'data/native-witness.json').read_text())
require(w.get('status')=='PASS','Native witness is missing or failed.')
kit=ROOT/'downloads/research-continuity-kit.zip'
with zipfile.ZipFile(kit) as z:
    require(z.testzip() is None,'Download ZIP CRC failed.')
    for member in z.namelist():
        path=Path(member)
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0]=='research-continuity','Unsafe kit path.')
        local=ROOT.joinpath(*path.parts[1:]);require(local.is_file(),'Kit member no longer exists: '+member)
        require(z.read(member)==local.read_bytes(),'Kit differs from current source: '+member)
    for name in ['index.html','source/measurements.js','scripts/check_packet.cjs','scripts/native_bridge.py','tests/engine.test.cjs','tests/measurements.test.cjs','source/judgment.js','source/judgment-ui.js','scripts/genesis_judgment.py','scripts/judgment_packet.cjs','tests/genesis_roundtrip.py','tests/judgment_browser.py','downloads/retained-judgment-genesis.zip']:
        require('research-continuity/'+name in z.namelist(),'Incomplete runnable kit: '+name)
g=json.loads((ROOT/'data/genesis-witness.json').read_text())
x=json.loads((ROOT/'data/cross-machine.json').read_text())
require(g['status']=='PASS' and len(g['checks'])>=9 and all(c['pass'] for c in g['checks']),'Genesis witness is incomplete.')
require(x['status']=='PASS' and x['expected_shard']==g['successor_id'] and x['origin_process_or_private_key_transferred'] is False,'Separate-machine witness differs from the released artifact.')
for name,want in g['consumer_sources'].items():require(digest(ROOT/name)==want,'Genesis artifact consumer changed: '+name)
with zipfile.ZipFile(ROOT/'downloads/retained-judgment-genesis.zip') as z:
    require(z.testzip() is None,'Genesis artifact archive CRC failed.')
    for name in z.namelist():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe native artifact path.')
        require(not name.endswith(('.key','.pem')),'Private key-shaped artifact in public download.')
    artifact_receipt=json.loads(z.read('GENESIS-WITNESS.json'))
    require(artifact_receipt['successor_id']==g['successor_id'],'Native artifact identity differs from public receipt.')
    require(hashlib.sha256(z.read('fixture-publisher.pub')).hexdigest()==g['publisher_key_sha256'],'Public fixture key changed.')
print(json.dumps({'status':'PASS','native_owner_sha256':owner['sha256'],'page_sha256':digest(ROOT/'index.html'),'kit_sha256':digest(kit),'custody':'public-safe fixtures and independent code only; no private source copied','runtime_network':'none'},indent=2))
