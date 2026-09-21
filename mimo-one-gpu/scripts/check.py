"""Check frozen release and archive correspondence, without loading a model."""
from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
for base,manifest_name in [(root/'v1','manifest.json'),(root,'SOURCE-MANIFEST.json')]:
    manifest=json.loads((base/manifest_name).read_text())
    for name,sha in manifest['sha256'].items():
        p=Path(name)
        assert not p.is_absolute() and '..' not in p.parts,name
        assert hashlib.sha256((base/p).read_bytes()).hexdigest()==sha,name
kit=root/'mimo-one-gpu-kit.zip'
if kit.exists():
    with zipfile.ZipFile(kit) as z:
        assert len(z.namelist())==len(set(z.namelist()))
        assert len(z.namelist())<50
        for item in z.infolist():
            p=Path(item.filename)
            assert not p.is_absolute() and '..' not in p.parts and item.file_size<500000
            assert z.read(item)==(root/p).read_bytes(),item.filename
html=(root/'index.html').read_text()
assert "connect-src 'self'" in html
assert "form-action 'none'" in html
assert 'NOT YET RUN' in html
assert not list(root.rglob('package.json'))
print('Exact source / release / kit checks PASS; native MiMo inference NOT RUN')
