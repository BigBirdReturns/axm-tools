#!/usr/bin/env python3
"""Build and independently qualify the self-contained local source distribution."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, re, shutil, subprocess, sys, tempfile, zipfile
ROOT=Path(__file__).resolve().parents[1]
NAME='AXM_Decision_Floor_Evaluation_v0.2.1.zip'
TOP='Decision_Floor_Evaluation_0.2.1'
def digest(b): return hashlib.sha256(b).hexdigest()
def viewer_files():
    names=['index.html','style.css','app.js','data.js','assets/fichains-logo.png','data/sources.json']
    return {name:(ROOT/name).read_bytes() for name in names}
def build():
    source=ROOT/'offline'
    files={p.relative_to(source).as_posix():p.read_bytes() for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='MANIFEST.json'}
    for name,data in viewer_files().items():files['workflow/'+name]=data
    # The offline viewer already accompanies the investigator; it must not offer a broken nested ZIP.
    html=files['workflow/index.html'].decode()
    html=html.replace('href="downloads/'+NAME+'" download','href="../START_HERE.html"')
    html=html.replace('Download the local investigator','Open the local start guide')
    html=html.replace('A direct download from this page. Nothing to send through email.','This workflow is already inside your local evaluation kit.')
    html=html.replace('href="data/package.json"','href="../MANIFEST.json"').replace('href="data/qualification.json"','href="../ACCEPTANCE.md"')
    files['workflow/index.html']=html.encode()
    manifest={'distribution':'0.2.1','engine':'0.2','classification':'independent AXM evaluation; synthetic fixtures','files':[{'path':n,'bytes':len(b),'sha256':digest(b)} for n,b in sorted(files.items())]}
    files['MANIFEST.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    out=ROOT/'downloads'/NAME;out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,b in sorted(files.items()):
            zi=zipfile.ZipInfo(TOP+'/'+name,(2026,11,3,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=(0o755 if name.endswith('.sh') else 0o644)<<16;z.writestr(zi,b)
    # Qualification runs from fresh archived bytes, never the source checkout.
    with tempfile.TemporaryDirectory(prefix='decision-floor-release-') as td:
        base=Path(td)
        with zipfile.ZipFile(out) as z:z.extractall(base)
        r=subprocess.run([sys.executable,'qualify.py','--out',str(base/'qualification.json')],cwd=base/TOP,text=True,capture_output=True,timeout=180)
        if r.returncode:raise RuntimeError('Extracted package failed qualification: '+r.stdout[-5000:]+r.stderr[-2000:])
        receipt=json.loads((base/'qualification.json').read_text())
        if receipt['manifest']['unmanifested']:raise RuntimeError('Unexpected archived files: '+str(receipt['manifest']['unmanifested']))
    metadata={'distribution':'0.2.1','engine':'0.2','filename':NAME,'bytes':out.stat().st_size,'sha256':digest(out.read_bytes()),'archive_root':TOP,'source_file_count':len(files),'manifested_files':len(manifest['files']),'source':'offline/ in this repository; no customer records','runtime':'Python 3.10+ standard library; no source-system writeback','qualification':'data/qualification.json'}
    (ROOT/'data/package.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (ROOT/'data/qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(metadata,indent=2));print('EXTRACTED_QUALIFICATION',receipt['status'],receipt['unit_test_summary'],receipt['synthetic']['assertions'])
def check():
    metadata=json.loads((ROOT/'data/package.json').read_text());p=ROOT/'downloads'/metadata['filename'];assert digest(p.read_bytes())==metadata['sha256'],'ZIP hash'
    data=json.loads((ROOT/'data.js').read_text().removeprefix('window.DF_DATA=').strip().removesuffix(';'))
    for case in data['cases'].values():
        for h,s in case['sources'].items():assert h==s['sha256']==digest(s['text'].encode()),s['name']
    html=(ROOT/'index.html').read_text()
    for href in re.findall(r'(?:href|src)="([^"]+)"',html):
        if href.startswith(('https:','http:','data:','#','../')):continue
        assert (ROOT/href.split('#')[0]).exists(),href
    assert "connect-src 'none'" in html and "font-src 'none'" in html,'CSP'
    assert 'INDEPENDENT AXM EVALUATION' in html and 'simulated' in html,'Source boundary'
    assert not list(ROOT.rglob('*.woff*')) and not list(ROOT.rglob('*.ttf')),'No font distribution'
    receipt=json.loads((ROOT/'data/qualification.json').read_text());assert receipt['status']=='PASS';assert receipt['synthetic']['network_attempts']==0
    print('RELEASE_CHECK_PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    if not a.check:build()
    check()
