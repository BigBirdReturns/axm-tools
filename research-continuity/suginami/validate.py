#!/usr/bin/env python3
"""Check exact owners, public custody, installed consumer and downloadable copies."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent;PARENT=ROOT.parent;REPO=PARENT.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def need(x,message):
 if not x:raise SystemExit('REFUSED: '+message)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.scripts=[];self.csp=None
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='script':self.scripts.append(a)
  if t=='meta' and a.get('http-equiv','').lower()=='content-security-policy':self.csp=a.get('content')
subprocess.run([sys.executable,str(ROOT/'build.py'),'--check'],check=True)
owner=json.loads((PARENT/'source/OWNER.json').read_text());need(sha(PARENT/'source/research-core.js')==owner['sha256'],'ResearchCore owner changed')
models=json.loads((ROOT/'data/manzanita-owners.json').read_text())
for k in ['working_model','operating_fabric']:
 source=models[k];need(sha(REPO/source['path'])==source['sha256'],'Manzanita owner projection changed: '+k)
p=Parser();p.feed((ROOT/'index.html').read_text());need("connect-src 'none'" in (p.csp or ''),'Runtime network boundary missing');need(all('src' not in s for s in p.scripts),'Dynamic script introduced')
for name in ['municipal.js','fabric.js','assurance.js','workflow.js','app.js']:
 s=(ROOT/name).read_text();need(not re.search(r'\b(fetch|XMLHttpRequest|WebSocket|sendBeacon)\s*\(',s),'Unexpected network operation '+name)
for f in ROOT.rglob('*'):
 if f==Path(__file__).resolve() or not f.is_file() or f.suffix not in ['.js','.cjs','.py','.html','.json','.md']:continue
 s=f.read_text()
 for pattern in [r'F8N-(?:[0-9A-F]{4}-){7}[0-9A-F]{4}',r'gh[pousr]_[A-Za-z0-9]{30,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'browser-vault/' + r'captures/']:
  need(not re.search(pattern,s),'Credential/private capture in public file '+str(f.relative_to(ROOT)))
q=json.loads((ROOT/'data/qualification.json').read_text());need(q['status']=='PASS','Source candidate not qualified')
for path,h in q['source_sha256'].items():need(sha(ROOT/path)==h,'Qualified source differs '+path)
r=json.loads((ROOT/'data/native-witness.json').read_text());need(r['status']=='PASS' and len(r['checks'])>=9 and all(x['pass'] for x in r['checks']),'Actual native kernel evidence missing')
cross=json.loads((ROOT/'data/cross-machine.json').read_text());need(cross['status']=='PASS' and cross['shard_id']==r['successor_id'] and not cross['private_key_transferred'],'Physical successor receipt mismatch')
with zipfile.ZipFile(ROOT/'downloads/civil-genesis-artifacts.zip') as z:
 need(z.testzip() is None,'Artifact CRC mismatch')
 for name in z.namelist():need(not Path(name).is_absolute() and '..' not in Path(name).parts and not name.endswith(('.key','.pem')),'Unsafe native artifact member')
 need(hashlib.sha256(z.read('fixture-publisher.pub')).hexdigest()==r['fixture_key_sha256'],'Fixture public key changed')
 need(json.loads(z.read('NATIVE-WITNESS.json'))['successor_id']==r['successor_id'],'Artifact successor mismatch')
with zipfile.ZipFile(ROOT/'downloads/civil-continuity-kit.zip') as z:
 need(z.testzip() is None,'Kit CRC failed')
 for name in z.namelist():
  p=Path(name);need(p.parts[0]=='research-continuity' and '..' not in p.parts and not p.is_absolute(),'Unsafe kit path');local=PARENT.joinpath(*p.parts[1:]);need(local.is_file() and z.read(name)==local.read_bytes(),'Kit member differs from source '+name)
 for n in ['index.html','municipal.js','fabric.js','assurance.js','packet.cjs','seal.py','README.md','browser.py','downloads/civil-genesis-artifacts.zip']:need('research-continuity/suginami/'+n in z.namelist(),'Incomplete kit '+n)
print(json.dumps({'status':'PASS','page_sha256':sha(ROOT/'index.html'),'kit_sha256':sha(ROOT/'downloads/civil-continuity-kit.zip'),'native_artifacts_sha256':sha(ROOT/'downloads/civil-genesis-artifacts.zip'),'source_owners_preserved':True,'private_counterpart_material_published':False},indent=2))
