#!/usr/bin/env python3
"""Project existing exact owner code and local civil adapters into one offline page."""
from pathlib import Path
import json,hashlib,subprocess,zipfile,sys
ROOT=Path(__file__).resolve().parent;PARENT=ROOT.parent

def js(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 basis=json.loads((ROOT/'data/basis.json').read_text());basis['owners']=json.loads((ROOT/'data/manzanita-owners.json').read_text());basis['facilities']=json.loads((ROOT/'data/official-facilities.json').read_text())
 identity=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./create.cjs').runtime()))"],cwd=ROOT,text=True))
 nativepath=ROOT/'data/native-witness.json';native=json.loads(nativepath.read_text()) if nativepath.exists() else {'status':'PENDING'}
 if (ROOT/'data/cross-machine.json').exists():native['cross_machine']=json.loads((ROOT/'data/cross-machine.json').read_text())
 replaces={'__BASIS__':js(basis),'__IDENTITY__':js(identity),'__NATIVE__':js(native),'__CORE__':(PARENT/'source/research-core.js').read_text(),'__CONTINUITY__':(PARENT/'source/continuity.js').read_text(),'__MEASUREMENTS__':(PARENT/'source/measurements.js').read_text(),'__JUDGMENT__':(PARENT/'source/judgment.js').read_text(),'__MUNICIPAL__':(ROOT/'municipal.js').read_text(),'__FABRIC__':(ROOT/'fabric.js').read_text(),'__ASSURANCE__':(ROOT/'assurance.js').read_text(),'__WORKFLOW__':(ROOT/'workflow.js').read_text(),'__APP__':(ROOT/'app.js').read_text()}
 html=(ROOT/'index.template.html').read_text()
 for key,value in replaces.items():
  if html.count(key)!=1:raise ValueError('Ambiguous source marker '+key)
  html=html.replace(key,value)
 if '--check' in sys.argv:
  if (ROOT/'index.html').read_text()!=html:raise ValueError('Public page differs from its exact source projection')
  print('PAGE_SOURCE_MATCH');return
 (ROOT/'index.html').write_text(html,encoding='utf-8');(ROOT/'downloads').mkdir(exist_ok=True)
 selected=[PARENT/'source'/x for x in ['research-core.js','continuity.js','measurements.js','judgment.js']]+[PARENT/'scripts'/x for x in ['genesis_judgment.py','judgment_packet.cjs']]
 selected += [p for p in ROOT.rglob('*') if p.is_file() and p.name!='civil-continuity-kit.zip' and '__pycache__' not in p.parts and p.suffix not in ['.pyc']]
 with zipfile.ZipFile(ROOT/'downloads/civil-continuity-kit.zip','w',zipfile.ZIP_DEFLATED,9) as z:
  for p in sorted(selected):
   name='research-continuity/'+str(p.relative_to(PARENT));i=zipfile.ZipInfo(name,date_time=(2026,10,27,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16;z.writestr(i,p.read_bytes())
 print(json.dumps({'page_bytes':len(html.encode()),'page_sha256':sha(ROOT/'index.html'),'kit_sha256':sha(ROOT/'downloads/civil-continuity-kit.zip')}))
if __name__=='__main__':main()
