#!/usr/bin/env python3
"""Run existing Cantos operations; preserve fresh-process replay and mutation evidence.
No third-party Python packages, network calls, credential reads, model inference,
or commands from imported research packets. Requires a local Cantos checkout.
"""
from pathlib import Path
import argparse, datetime as dt, hashlib, json, os, shutil, subprocess, sys, time
HELPER=r'''
import copy,json,sys
from pathlib import Path
repo=Path(sys.argv[1]);out=Path(sys.argv[2]);mode=sys.argv[3]
sys.path.insert(0,str(repo/'integration'))
import work
base=repo/'integration/examples';request=json.loads((base/'work.json').read_bytes())
if mode=='changed-price':
 request=copy.deepcopy(request);request['tasks'][0]['price_scenario']={'rate_usd_per_gpu_hour':2.0}
for task in request['tasks']:task['actor']='Research Continuity native replay'
receipt=work.run(request,base,out/'store')
(out/(mode+'.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps({'summary':receipt['summary'],'model_calls':receipt.get('model_calls'),'gpu_runs':receipt.get('gpu_runs')}))
'''

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cantos',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if sys.version_info<(3,12):ap.error('Python 3.12+ required')
 if not shutil.which('node'):ap.error('Node 22+ must already be installed')
 repo=a.cantos.resolve();out=a.out.resolve()
 if not (repo/'integration/work.py').is_file():ap.error('Cantos owner is missing at this checkout')
 if out==repo or repo in out.parents:ap.error('Keep results outside the source checkout')
 if out.exists() and any(out.iterdir()):ap.error('Preserve the old results: choose an empty output directory')
 out.mkdir(parents=True,exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
 env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(out/'tmp'),TMP=str(out/'tmp'),TEMP=str(out/'tmp'))
 head=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True,text=True,timeout=10)
 witness={'status':'INCOMPLETE','observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'commit':head.stdout.strip() if head.returncode==0 else 'unavailable: non-Git source export','python':sys.version.split()[0],'node':subprocess.check_output(['node','--version'],text=True).strip(),'cases':[],'scope':'Native deterministic Cantos owner operations over retained historical data and labeled synthetic change cases. No new inference, GPU run, rental, or provider authorization.','code_sha256':hashlib.sha256((repo/'integration/work.py').read_bytes()).hexdigest()}
 expected={'cold':{'executed':6,'reused':0,'held':0},'warm':{'executed':0,'reused':6,'held':0},'changed-price':{'executed':1,'reused':5,'held':0}}
 for mode,want in expected.items():
  t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',HELPER,str(repo),str(out),mode],cwd=repo,env=env,capture_output=True,text=True,timeout=180)
  (out/(mode+'.log')).write_text(p.stdout+p.stderr)
  if p.returncode:raise RuntimeError(mode+' failed; inspect its retained log')
  result=json.loads(p.stdout.strip().splitlines()[-1]);ok=result['summary']==want and result['model_calls']==0 and result['gpu_runs']==0
  row={'name':mode,'summary':f"{result['summary']['executed']} executed / {result['summary']['reused']} reused / {result['summary']['held']} held",'observed':result,'pass':ok,'seconds':round(time.monotonic()-t,3)};witness['cases'].append(row)
  (out/'native-witness.json').write_text(json.dumps(witness,indent=2));print(json.dumps(row),flush=True)
  if not ok:raise RuntimeError('Observed outcome differs from the specified native expectation')
 for pattern in ['test_work.py','test_task_research_handoff.py']:
  p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','integration/tests','-p',pattern,'-v'],cwd=repo,env=env,capture_output=True,text=True,timeout=180)
  (out/(pattern+'.log')).write_text(p.stdout+p.stderr)
  row={'name':pattern,'summary':'PASS' if p.returncode==0 else 'FAIL','pass':p.returncode==0,'log_sha256':hashlib.sha256((p.stdout+p.stderr).encode()).hexdigest()};witness['cases'].append(row)
  if p.returncode:raise RuntimeError('Native conformance suite failed: '+pattern)
 witness['status']='PASS';(out/'native-witness.json').write_text(json.dumps(witness,indent=2));print('NATIVE WITNESS PASS',out/'native-witness.json')
if __name__=='__main__':
 try:main()
 except Exception as e:print('FAILED: '+str(e),file=sys.stderr);raise SystemExit(1)
