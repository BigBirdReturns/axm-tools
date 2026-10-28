#!/usr/bin/env python3
"""Build the portable toolkit from an explicit public-file allowlist. Stdlib only."""
import argparse, hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['index.html','style.css','app.js','README.md','LICENSE','UNDERCAST_ADAPTATION.md','scripts/catalog.py','scripts/package.py','tests/test_catalog.py','tests/browser_test.py','data/observed.json','data/catalog.json','data/media.json','data/listing-review.csv','data/photo-queue.json','data/change-plan.json','data/qualification.json']
def pack(out):
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in FILES:
            f=ROOT/name
            if not f.is_file():raise FileNotFoundError(name)
            z.write(f,'atmark/'+name)
    with zipfile.ZipFile(p) as z:
        if z.testzip():raise ValueError('ZIP integrity failure')
    print(json.dumps({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'files':len(FILES)}))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);pack(a.parse_args().out)
