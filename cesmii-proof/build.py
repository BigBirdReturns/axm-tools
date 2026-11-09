#!/usr/bin/env python3
"""Materialize a self-contained lab from retained inputs. No network at build time."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent

def build():
    upstream=ROOT.parent/'team-commons/core.js'
    if upstream.exists():
        source=upstream.read_bytes();(ROOT/'commons-core.js').write_bytes(source)
    else:
        source=(ROOT/'commons-core.js').read_bytes()
    engine=(ROOT/'engine.js').read_bytes()
    capture=json.loads((ROOT/'data/capture.json').read_text())
    identity=b'axm-i3x-engine/1\0'+engine+b'\0'+source
    engine_sha=hashlib.sha256(identity).hexdigest()
    meta={'schema':'axm-i3x-build/1','engine_sha256':engine_sha,'engine_file_sha256':hashlib.sha256(engine).hexdigest(),'team_commons_source_sha256':hashlib.sha256(source).hexdigest(),'identity_recipe':'SHA256(UTF8(axm-i3x-engine/1) + NUL + engine.js bytes + NUL + commons-core.js bytes)','team_commons_source':'../team-commons/core.js','capture_sha256':hashlib.sha256((ROOT/'data/capture.json').read_bytes()).hexdigest(),'scope':'Independent read-only demo; no physical or institutional acceptance.'}
    (ROOT/'build-meta.json').write_text(json.dumps(meta,indent=2)+'\n')
    q=ROOT/'data/qualification.json'
    qualification=json.loads(q.read_text()) if q.exists() else None
    if qualification and qualification.get('engine_sha256')!=engine_sha:qualification=None
    data={'capture':capture,'engine_sha256':engine_sha,'scenarios':json.loads((ROOT/'scenarios.json').read_text()),'research':json.loads((ROOT/'research.json').read_text()),'qualification':qualification}
    (ROOT/'data.js').write_text('globalThis.PROOF_DATA='+json.dumps(data,separators=(',',':')).replace('</','<\\/')+';\n')
    html=(ROOT/'index.html').read_text()
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(ROOT/'style.css').read_text()+'</style>')
    for name in ['data.js','commons-core.js','engine.js','app.js']:
        html=html.replace('<script src="'+name+'"></script>','<script>'+(ROOT/name).read_text().replace('</script','<\\/script')+'</script>')
    html=html.replace('href="favicon.svg"','href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 64 64\'%3E%3Crect width=\'64\' height=\'64\' rx=\'12\' fill=\'%2313216f\'/%3E%3Cpath d=\'M16 43L32 15l16 28M23 32h18\' stroke=\'%238cc63f\' stroke-width=\'5\' fill=\'none\'/%3E%3C/svg%3E"')
    (ROOT/'offline.html').write_text(html)
    (ROOT/'favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#13216f"/><path d="M16 43L32 15l16 28M23 32h18" stroke="#8cc63f" stroke-width="5" fill="none"/></svg>\n')
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.name not in ['source.zip','manifest.json'] and '__pycache__' not in p.parts and not p.name.endswith('.pyc')]
    manifest={'schema':'axm-i3x-file-manifest/1','files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(ROOT/'source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(files)+[ROOT/'manifest.json']:
            info=zipfile.ZipInfo('cesmii-proof/'+str(p.relative_to(ROOT)),date_time=(2026,11,9,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,p.read_bytes())
    print(json.dumps(meta))
if __name__=='__main__':build()
