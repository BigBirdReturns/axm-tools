"""One-use, hash-bound transfer of public Atmark source files. Feature branch only."""
import hashlib,json,lzma,os,shutil
from pathlib import Path
assert os.environ.get('GITHUB_REF') == 'refs/heads/feat/atmark-store-20261028'
root=Path('.github/atmark-stage')
b=b''.join((root/f'part-{i}').read_bytes() for i in range(4))
assert len(b)==38860
assert hashlib.sha256(b).hexdigest()=='afd78929ac34cb6fc94d67305d62890cbfd7c93de2cfaec612428386fe3bf7d2'
files=json.loads(lzma.decompress(b))
allowed={'atmark/README.md','atmark/index.html','atmark/style.css','atmark/UNDERCAST_ADAPTATION.md','atmark/app.js','atmark/LICENSE','atmark/tests/test_catalog.py','atmark/tests/browser_test.py','atmark/data/media.json','atmark/data/qualification.json','atmark/data/observed.json','atmark/scripts/package.py','atmark/scripts/catalog.py'}
assert set(files)==allowed
for name,text in files.items():
 assert isinstance(text,str) and len(text)<200000
 p=Path(name);assert not p.exists(),name
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
# Retain only the public sources; the transfer material never reaches main.
shutil.rmtree(root)
Path('.github/workflows/atmark-materialize.yml').unlink()
print('Materialized 13 hash-bound public source files; transfer artifacts removed.')
