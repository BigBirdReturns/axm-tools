"""Release maintainer helper. Never reseal an already published version in place."""
from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
for junk in root.rglob('__pycache__'):
    import shutil
    shutil.rmtree(junk)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
v1={p.name:sha(p) for p in sorted((root/'v1').iterdir()) if p.is_file() and p.name!='manifest.json'}
(root/'v1/manifest.json').write_text(json.dumps({'version':'1.0.0','native_mimo':'NOT_RUN','sha256':v1},indent=2)+'\n')
files=[p for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ['SOURCE-MANIFEST.json','mimo-one-gpu-kit.zip']]
(root/'SOURCE-MANIFEST.json').write_text(json.dumps({'version':'1.0.0','sha256':{p.relative_to(root).as_posix():sha(p) for p in files}},indent=2)+'\n')
files.append(root/'SOURCE-MANIFEST.json')
with zipfile.ZipFile(root/'mimo-one-gpu-kit.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(files):
        info=zipfile.ZipInfo(p.relative_to(root).as_posix(),date_time=(2026,9,21,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        z.writestr(info,p.read_bytes())
print('KIT_SHA256',sha(root/'mimo-one-gpu-kit.zip'))
