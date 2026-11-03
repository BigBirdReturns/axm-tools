"""Portable package acceptance. Runs locally without third-party modules."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent

def run_command(args):
    p=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,timeout=120)
    return p

def manifest_verify():
    m=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf8'))
    failures=[]
    for f in m['files']:
        p=ROOT/f['path']
        if not p.is_file():failures.append(f['path']+':missing');continue
        raw=p.read_bytes()
        if len(raw)!=f['bytes'] or hashlib.sha256(raw).hexdigest()!=f['sha256']:
            failures.append(f['path']+':modified')
    files={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('MANIFEST.json',) and not p.suffix=='.pyc' and not (set(p.parts) & {'local_customer','local_demo'})}
    # An extracted evaluation may have generated local_customer state after launch.
    unexpected=files-{f['path'] for f in m['files']}
    return {'status':'PASS' if not failures else 'FAIL','expected_files':len(m['files']),
            'failures':failures,'unmanifested':sorted(unexpected)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='qualification_result.json');p.add_argument('--cases',type=int,default=1000);p.add_argument('--seed',type=int,default=931527);a=p.parse_args()
    start=time.monotonic()
    baseline=run_command(['-m','unittest','discover','-s','tests','-v'])
    oracle=run_command(['tools/novel_case_oracle.py','--cases',str(a.cases),'--seed',str(a.seed)])
    try:synthetic=json.loads(oracle.stdout)
    except json.JSONDecodeError:synthetic={'outcome':'FAIL','detail':oracle.stderr[-2000:]}
    manifest=manifest_verify()
    status='PASS' if baseline.returncode==0 and oracle.returncode==0 and manifest['status']=='PASS' else 'FAIL'
    result={'build':'Decision Floor distribution 0.3.0 / engine 0.2','qualification':'local independent proof on this machine',
            'status':status,'manifest':manifest,'unit_test_exit_code':baseline.returncode,
            'unit_test_summary':baseline.stderr.strip().splitlines()[-4:],
            'synthetic':synthetic,'elapsed_seconds':round(time.monotonic()-start,2),
            'limitations':'No live ERP qualification, local browser HTTP navigation not guaranteed in managed test environments, external source authenticity not established'}
    output=Path(a.out).resolve();output.parent.mkdir(exist_ok=True,parents=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))
    sys.exit(0 if status=='PASS' else 2)
if __name__=='__main__':main()
