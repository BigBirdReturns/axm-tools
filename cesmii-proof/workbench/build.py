#!/usr/bin/env python3
"""Build the self-contained AXM member workbench with source identities. Stdlib only."""
import hashlib, json, pathlib, re, sys
ROOT=pathlib.Path(__file__).resolve().parent
def write(name,text):
    (ROOT/name).write_text(text,encoding='utf-8',newline='\n')
def build():
    core=(ROOT/'core.js').read_bytes(); donor=(ROOT/'commons-core.js').read_bytes()
    digest=hashlib.sha256(core+b'\n'+donor).hexdigest()
    meta={'schema':'axm-member-build/1','version':'1.0.0','engine_sha256':digest,'source_sha256':{'core.js':hashlib.sha256(core).hexdigest(),'commons-core.js':hashlib.sha256(donor).hexdigest()},'identity':'sha256(core.js bytes + LF + commons-core.js bytes)'}
    write('build-meta.json',json.dumps(meta,indent=2)+'\n');write('meta.js','window.AXM_MEMBER_BUILD='+json.dumps(meta,separators=(',',':'))+';\n')
    capture=ROOT/'capture-example.json'
    if not capture.exists():
        capture.write_bytes((ROOT.parent/'data'/'capture.json').read_bytes())
    fixture=json.loads(capture.read_text(encoding='utf-8'))
    write('fixture.js','window.AXM_MEMBER_FIXTURE='+json.dumps(fixture,separators=(',',':')).replace('</',r'<\/')+';\n')
    html=(ROOT/'index.html').read_text(encoding='utf-8')
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(ROOT/'style.css').read_text(encoding='utf-8')+'</style>')
    for name in ['commons-core.js','core.js','meta.js','fixture.js','app.js']:
        js=(ROOT/name).read_text(encoding='utf-8').replace('</script',r'<\/script')
        html=html.replace('<script src="'+name+'"></script>','<script>'+js+'</script>')
    write('offline.html',html)
    print(json.dumps({'engine_sha256':digest,'offline_bytes':(ROOT/'offline.html').stat().st_size}))
if __name__=='__main__':build()
