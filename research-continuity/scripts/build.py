#!/usr/bin/env python3
"""Build the self-contained public view from pinned owners. Standard library only."""
from pathlib import Path
import argparse, hashlib, json, sys, zipfile
ROOT=Path(__file__).resolve().parents[1]

def jsjson(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')

def render():
    owner=json.loads((ROOT/'source/OWNER.json').read_text())
    core=(ROOT/'source/research-core.js').read_bytes()
    if hashlib.sha256(core).hexdigest()!=owner['sha256']:raise SystemExit('Pinned ResearchCore drift; do not silently replace its owner.')
    template=(ROOT/'source/index.template.html').read_text()
    fields={
      '__OWNER_JSON__':jsjson(owner),
      '__GENESIS_WITNESS_JSON__':jsjson({**json.loads((ROOT/'data/genesis-witness.json').read_text()),'cross_machine':json.loads((ROOT/'data/cross-machine.json').read_text())}),
      '__JUDGMENT_ENGINE__':(ROOT/'source/judgment.js').read_text(),
      '__JUDGMENT_UI__':(ROOT/'source/judgment-ui.js').read_text(),
      '__WITNESS_JSON__':jsjson(json.loads((ROOT/'data/native-witness.json').read_text())),
      '__QUALIFICATION_JSON__':jsjson(json.loads((ROOT/'data/qualification.json').read_text())),
      '__RESEARCH_CORE__':core.decode(),
      '__CONTINUITY_ENGINE__':(ROOT/'source/continuity.js').read_text(),
      '__CONTINUITY_UI__':(ROOT/'source/ui.js').read_text(),
      '__MEASUREMENT_ENGINE__':(ROOT/'source/measurements.js').read_text(),
      '__MEASUREMENT_UI__':(ROOT/'source/measurement-ui.js').read_text(),
    }
    for key,value in fields.items():
        if template.count(key)!=1:raise SystemExit('Template marker missing or ambiguous: '+key)
        template=template.replace(key,value)
    return template

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
    html=render()
    if a.check:
        if not (ROOT/'index.html').is_file() or (ROOT/'index.html').read_text()!=html:raise SystemExit('Generated index.html differs from its source owners.')
        print('Source-to-page equality PASS');return
    (ROOT/'index.html').write_text(html)
    (ROOT/'downloads').mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT/'downloads/research-continuity-kit.zip','w',zipfile.ZIP_DEFLATED,9) as z:
        selected=['README.md','LICENSE','index.html','downloads/retained-judgment-genesis.zip']
        for directory in ['source','scripts','tests','data']:
            selected += [str(p.relative_to(ROOT)) for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.png']]
        for name in sorted(selected):
            p=ROOT/name
            if p.exists():
                info=zipfile.ZipInfo('research-continuity/'+name,date_time=(2026,10,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,p.read_bytes())
    print(json.dumps({'html_bytes':len(html.encode()),'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'kit_bytes':(ROOT/'downloads/research-continuity-kit.zip').stat().st_size}))
if __name__=='__main__':main()
