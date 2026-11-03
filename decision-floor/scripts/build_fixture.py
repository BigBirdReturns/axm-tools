#!/usr/bin/env python3
"""Derive browser examples from the real offline engine and preserve exact inputs."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1];ENGINE=ROOT/'offline'
data={'version':'0.3.0','engine':'0.2','evidence_class':'synthetic','cases':{}}
with tempfile.TemporaryDirectory(prefix='decision-floor-fixtures-') as td:
    tmp=Path(td)
    for key in ['missed','closed']:
        out=tmp/key/'report'
        r=subprocess.run([sys.executable,'-m','decision_floor','run','--input',str(ENGINE/'sample_inputs'/key),'--config',str(ENGINE/'config/sources.json'),'--workspace',str(tmp/key/'state'),'--out',str(out)],cwd=ENGINE,capture_output=True,text=True,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        report=json.loads((out/'decision_floor_report.json').read_text());sources={}
        for p in sorted((ENGINE/'sample_inputs'/key).iterdir()):
            b=p.read_bytes();h=hashlib.sha256(b).hexdigest();sources[h]={'name':p.name,'text':b.decode('utf-8'),'sha256':h}
        data['cases'][key]={'title':'Missed handoff' if key=='missed' else 'Verified execution','case':report['cases'][0],'sources':sources}
(ROOT/'data.js').write_text('window.DF_DATA='+json.dumps(data,separators=(',',':')).replace('</','<\\/')+';\n')
print('BROWSER_FIXTURES_FROM_ENGINE', {k:len(v['case']['events']) for k,v in data['cases'].items()})
