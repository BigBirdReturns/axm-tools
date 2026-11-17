#!/usr/bin/env python3
"""Deterministic dependency-free standalone build; no network and no secrets."""
import pathlib,hashlib,json,zipfile,io
R=pathlib.Path(__file__).parent
sha=lambda b:hashlib.sha256(b).hexdigest()
engine=sha(b'axm-industrial-engine/1\0'+(R/'engine.js').read_bytes()+b'\0'+(R/'commons-core.js').read_bytes())
meta={'schema':'axm-industrial-build/1','engine_sha256':engine,'donor_sha256':sha((R/'commons-core.js').read_bytes()),'donor':'AXM Team Commons, exact copy from cesmii-proof/commons-core.js','identity_recipe':'SHA256(UTF8(axm-industrial-engine/1) + NUL + engine.js + NUL + commons-core.js)','version':'0.1.0','scope':'Independent synthetic workflow proof; no vendor endpoint or plant control connection.'}
(R/'build-meta.json').write_text(json.dumps(meta,indent=2)+'\n')
(R/'build-meta.js').write_text('globalThis.AXM_META='+json.dumps(meta,separators=(',',':'))+';\n')
html=(R/'index.html').read_text().replace('<link rel="stylesheet" href="style.css">','<style>'+(R/'style.css').read_text()+'</style>')
for name in ['commons-core.js','engine.js','build-meta.js','app.js']:
 text=(R/name).read_text().replace('</script','<\\/script')
 if name=='build-meta.js':text+='\nglobalThis.AXM_STANDALONE=true;'
 html=html.replace('<script src="'+name+'"></script>','<script>'+text+'</script>')
(R/'offline.html').write_text(html)
files={str(p.relative_to(R)):sha(p.read_bytes()) for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in str(p) and p.suffix not in ['.zip','.png'] and p.name not in ['MANIFEST.json','package-receipt.json']}
(R/'MANIFEST.json').write_text(json.dumps({'schema':'axm-industrial-files/1','files':files},indent=2)+'\n')
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted([*files,'MANIFEST.json']):
  item=zipfile.ZipInfo('industrial-continuity/'+name,date_time=(2026,11,16,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o644<<16;z.writestr(item,(R/name).read_bytes())
archive=buf.getvalue();(R/'industrial-continuity-source.zip').write_bytes(archive)
receipt={'schema':'axm-industrial-package/1','bytes':len(archive),'sha256':sha(archive),'files':len(files)+1,'engine_sha256':engine}
(R/'package-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
