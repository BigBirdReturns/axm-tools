"""Execute the bundled, immutable Cantos retained-evidence recipient checker offline."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
EXPECTED='3c6d030d8215ad6a15175f2cd5550820adceb11705826dab6373bb2eecfff84a'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path,help='New result directory outside the installation')
    args=p.parse_args();out=args.out.resolve()
    if out.is_relative_to(ROOT):raise ValueError('Choose an output directory outside the release')
    out.mkdir(parents=True,exist_ok=False)
    archive=ROOT/'exhibits/cantos-maintainer-kit.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Cantos archive differs from the pinned public artifact')
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive entry')
        manifest=json.loads(z.read('cantos/MAINTAINER-MANIFEST.json'))
        if manifest.get('schema')!='cantos.maintainer-kit/1':raise ValueError('Unknown Cantos manifest')
        listed=manifest['files']
        expected={'cantos/'+name for name in listed}|{'cantos/MAINTAINER-MANIFEST.json'}
        actual={i.filename for i in z.infolist() if not i.is_dir()}
        if actual!=expected:raise ValueError('Cantos archive file set differs from its closed manifest')
        identity=hashlib.sha256(json.dumps(listed,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest()
        if identity!='4e4a0907184190d2c9ac6de65f9a02d70f4c45fb6d25e16cf4ec75d70194fd72':raise ValueError('Cantos source tree differs from the pinned manifest')
        for name,record in listed.items():
            data=z.read('cantos/'+name)
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Changed Cantos member: '+name)
        for n in names:
            path=PurePosixPath(n)
            if path.is_absolute() or '..' in path.parts or '\\' in n:raise ValueError('Unsafe archive path')
            if (z.getinfo(n).external_attr >> 16) & 0o170000 == 0o120000:raise ValueError('Archive symlinks are outside this release')
        z.extractall(out/'recipient')
    cwd=out/'recipient/cantos'
    result=subprocess.run([sys.executable,'-B','app/tests/check_maintainer_evidence.py'],cwd=cwd,capture_output=True,text=True,encoding='utf-8',timeout=600)
    (out/'checker.stdout.txt').write_text(result.stdout,encoding='utf-8')
    (out/'checker.stderr.txt').write_text(result.stderr,encoding='utf-8')
    receipt={'schema':'schism-cantos-recipient/2','status':'PASS' if result.returncode==0 else 'FAIL',
             'observed_at':datetime.now(timezone.utc).isoformat(),'source_commit':'98655f27c62083ac2cc3c860bb5fa58d7e5f29ad',
             'archive_sha256':EXPECTED,'checker_exit':result.returncode,
             'meaning':'Passing checker preserves the captured experiment refusal; it does not qualify either model.'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2));return result.returncode

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'FAIL','reason':str(error)}),file=sys.stderr);raise SystemExit(1)
