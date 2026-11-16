#!/usr/bin/env python3
"""AXM Proof Workbench: bounded orchestration over unchanged native proof kits."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,html,json,math,os,platform,re,shutil,signal,stat,subprocess,sys,time,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
VERSION='0.1.0'
ADAPTERS=('i3x','decision-floor','receptionist')
MAX_JSON=4*1024*1024
class Refusal(ValueError): pass
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def reject_constant(value):raise Refusal('NONFINITE_JSON: '+value)
def object_pairs(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise Refusal('DUPLICATE_KEY: '+key)
  result[key]=value
 return result
def load(path):
 raw=Path(path).read_bytes()
 if len(raw)>MAX_JSON:raise Refusal('JSON_TOO_LARGE')
 return json.loads(raw,parse_constant=reject_constant,object_pairs_hook=object_pairs)
def dump(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 raw=json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
 tmp=path.with_name(path.name+'.tmp');tmp.write_text(raw,encoding='utf-8');os.replace(tmp,path)
def safe_relative(name):
 if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\x00' in name:raise Refusal('UNSAFE_PATH')
 p=PurePosixPath(name)
 if p.is_absolute() or any(x in ('','..','.') for x in name.split('/')):raise Refusal('UNSAFE_PATH')
 return p
def verify(root=ROOT,expected=None):
 root=Path(root);mp=root/'MANIFEST.json';raw=mp.read_bytes()
 if expected is not None and sha(raw)!=expected:raise Refusal('TRUSTED_MANIFEST_MISMATCH')
 m=load(mp)
 if m.get('schema')!='axm-proof-package/1' or not isinstance(m.get('files'),dict):raise Refusal('INVALID_PACKAGE_MANIFEST')
 failures=[]
 for name,record in m['files'].items():
  rel=safe_relative(name);p=root/rel
  if any(x.is_symlink() for x in [p,*p.parents] if x==root or root in x.parents):failures.append(name+':symlink');continue
  if not p.is_file():failures.append(name+':missing');continue
  data=p.read_bytes()
  if len(data)!=record.get('bytes') or sha(data)!=record.get('sha256'):failures.append(name+':changed')
 actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix()!='MANIFEST.json' and '__pycache__' not in p.parts and p.suffix!='.pyc' and 'downloads' not in p.relative_to(root).parts}
 extras=sorted(actual-set(m['files']))
 if failures or extras:raise Refusal('PACKAGE_INTEGRITY: '+json.dumps({'failures':failures,'unexpected':extras}))
 return {'status':'PASS','files':len(m['files']),'manifest_sha256':sha(raw),'trust':'external hash matched' if expected else 'internal byte consistency only; authenticate digest separately'}
def extract(archive,target):
 target=Path(target);target.mkdir(parents=True,exist_ok=False)
 with zipfile.ZipFile(archive) as z:
  infos=z.infolist()
  if len(infos)>2000 or sum(i.file_size for i in infos)>100*1024*1024:raise Refusal('ARCHIVE_LIMIT')
  names=set()
  for i in infos:
   name=i.filename.rstrip('/') if i.is_dir() else i.filename
   p=safe_relative(name)
   if name in names:raise Refusal('DUPLICATE_ARCHIVE_PATH')
   names.add(name)
   if stat.S_ISLNK(i.external_attr>>16):raise Refusal('ARCHIVE_SYMLINK')
   if i.flag_bits&1:raise Refusal('ENCRYPTED_ARCHIVE')
   dest=target/p
   if i.is_dir():dest.mkdir(parents=True,exist_ok=True)
   else:
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as out:out.write(z.read(i))
 return target

def command(argv,cwd,out,name,timeout=210):
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONHASHSEED']='0'
 start=time.perf_counter();stdout=Path(out)/(name+'.stdout.log');stderr=Path(out)/(name+'.stderr.log')
 record={'name':name,'argv':argv,'started_at':now(),'status':'RUNNING'}
 dump(Path(out)/(name+'.command.json'),record)
 with stdout.open('w',encoding='utf-8') as a,stderr.open('w',encoding='utf-8') as b:
  p=subprocess.Popen(argv,cwd=cwd,env=env,stdout=a,stderr=b,start_new_session=(os.name=='posix'))
  try:code=p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   if os.name=='posix':os.killpg(p.pid,signal.SIGKILL)
   else:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
   p.wait();code=124
 record.update(status='PASS' if code==0 else 'FAIL',exit_code=code,elapsed_seconds=round(time.perf_counter()-start,6),stdout_sha256=sha(stdout.read_bytes()),stderr_sha256=sha(stderr.read_bytes()))
 dump(Path(out)/(name+'.command.json'),record)
 return record

def i3x(suite,out):
 node=shutil.which('node')
 if not node:raise Refusal('NODE_REQUIRED: install Node 18+ independently; no automatic download')
 rec=command([node,'tests/verify.cjs'],suite,out,'native')
 result=load(suite/'data/qualification.json')
 # Test output alone does not establish replay of the exported native capsule.
 helper=ROOT/'adapters/i3x-replay.cjs'
 replay=command([node,str(helper),str(suite),str(out/'capsule.json')],suite,out,'cold-replay')
 return {'status':'PASS' if rec['exit_code']==0 and replay['exit_code']==0 and result.get('status')=='PASS' else 'FAIL','checks':{'algorithm_assertions':result.get('total',0),'native_capsule_cold_replay':replay['status']},'commands':[rec,replay],'native_reports':[str(suite/'data/qualification.json'),str(out/'capsule.json')]}
def decision_floor(suite,out):
 rec=command([sys.executable,'-B','qualify.py','--out',str(out/'native.json'),'--cases','1000','--seed','931527'],suite,out,'native',timeout=240)
 result=load(out/'native.json') if (out/'native.json').exists() else {}
 return {'status':'PASS' if rec['exit_code']==0 and result.get('status')=='PASS' else 'FAIL','checks':{'native_unit_summary':result.get('unit_test_summary',[]),'generated_case_result':result.get('synthetic',{})},'commands':[rec],'native_reports':[str(out/'native.json')]}
def receptionist(suite,out):
 records=[command([sys.executable,'-B','verify_public.py'],suite,out,'native-integrity')]
 records.append(command([sys.executable,'-B','run_lab.py','--output',str(out/'transactions')],suite,out,'transactions',timeout=240))
 records.append(command([sys.executable,'-B','model/confirmation_trial.py','--output',str(out/'confirmation')],suite,out,'confirmation'))
 a=load(out/'transactions/acceptance/report.json') if (out/'transactions/acceptance/report.json').exists() else {}
 b=load(out/'confirmation/report.json') if (out/'confirmation/report.json').exists() else {}
 return {'status':'PASS' if all(x['exit_code']==0 for x in records) and a.get('status')=='pass' and b.get('status')=='pass' else 'FAIL','checks':{'transaction_cases':a.get('case_count',0),'transaction_assertions':a.get('assertion_count',0),'confirmation_cases':b.get('passed',0),'confirmation_failures':b.get('failed'), 'new_model_calls':0},'commands':records,'native_reports':[str(out/'transactions/acceptance/report.json'),str(out/'confirmation/report.json')]}
RUNNERS={'i3x':i3x,'decision-floor':decision_floor,'receptionist':receptionist}
def qualify(output,selected=ADAPTERS,expected=None):
 verified=verify(expected=expected)
 output=Path(output).resolve()
 if output==ROOT or ROOT in output.parents:raise Refusal('OUTPUT_MUST_BE_OUTSIDE_PACKAGE')
 output.mkdir(parents=True,exist_ok=False)
 catalog=load(ROOT/'donor-map.json')
 report={'schema':'axm-proof-run/1','version':VERSION,'status':'RUNNING','observed_at':now(),'source_commit':catalog['source_commit'],'package':verified,'runtime':{'python':sys.version.split()[0],'platform':platform.platform(),'node':None},'suites':[],'customer_acceptance':'NOT_ESTABLISHED','external_effects':'synthetic loopback workers only; no production writes or messages','model_calls':0}
 if shutil.which('node'):report['runtime']['node']=subprocess.check_output(['node','--version'],text=True).strip()
 dump(output/'report.json',report);tick=time.perf_counter()
 for d in catalog['donors']:
  if d['id'] not in selected:continue
  item={k:d[k] for k in ('id','title','sha256','evidence_class','limits')};item['status']='RUNNING';report['suites'].append(item)
  stage=output/d['id'];stage.mkdir();dump(output/'report.json',report);started=time.perf_counter()
  try:
   archive=ROOT/safe_relative(d['path'])
   if sha(archive.read_bytes())!=d['sha256']:raise Refusal('DONOR_DIGEST_MISMATCH')
   work=extract(archive,stage/'source')/safe_relative(d['root'])
   item.update(RUNNERS[d['id']](work,stage))
  except Exception as e:item.update(status='FAIL',error=type(e).__name__+': '+str(e))
  item['elapsed_seconds']=round(time.perf_counter()-started,6);dump(output/'report.json',report)
 report['package_after']=verify(expected=verified['manifest_sha256'])
 report.update(status='PASS' if report['suites'] and all(s['status']=='PASS' for s in report['suites']) else 'FAIL',completed_at=now(),elapsed_seconds=round(time.perf_counter()-tick,6))
 dump(output/'report.json',report)
 # Evidence inventory binds native receipts and logs; it does not turn them into signatures.
 inventory={p.relative_to(output).as_posix():{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 dump(output/'evidence-manifest.json',{'schema':'axm-proof-run-files/1','files':inventory,'status':report['status'],'meaning':'Exact files from this local run; native formats and verdicts retained.'})
 return report

def number(value,name):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or abs(value)>1e12 or not math.isfinite(value) or value<0:raise Refusal('INVALID_ECONOMICS: '+name)
 return value
def economics(e):
 keys={'currency','price','engineering_hours','hourly_cost','compute_cost','support_reserve'}
 if not isinstance(e,dict) or set(e)!=keys or e['currency']!='USD':raise Refusal('ECONOMICS_SCHEMA')
 n={k:number(e[k],k) for k in keys-{'currency'}}
 cost=n['engineering_hours']*n['hourly_cost']+n['compute_cost']+n['support_reserve']
 if not math.isfinite(cost) or (n['price'] and not math.isfinite((n['price']-cost)*100/n['price'])):raise Refusal('ECONOMICS_OVERFLOW')
 return {**e,'estimated_delivery_cost':cost,'estimated_contribution':n['price']-cost,'estimated_margin_percent':(n['price']-cost)*100/n['price'] if n['price'] else None,'basis':'operator assumptions; excludes unspecified taxes, acquisition and overhead; not measured market rates or ROI'}
def plan(e):
 allowed={'schema','case_id','adapter','evidence_class','target_decision','receiving_owner','data_custodian','data_authorized','acceptance_criteria','disclosure','economics'}
 if not isinstance(e,dict) or set(e)!=allowed or e.get('schema')!='axm-proof-engagement/1':raise Refusal('ENGAGEMENT_SCHEMA')
 if not isinstance(e['case_id'],str) or not re.fullmatch('[A-Za-z0-9_-]{3,80}',e['case_id']):raise Refusal('INVALID_CASE_ID')
 if e['adapter'] not in ADAPTERS:raise Refusal('UNSUPPORTED_ADAPTER')
 if e['evidence_class'] not in ('customer-owned','synthetic'):raise Refusal('UNKNOWN_EVIDENCE_CLASS')
 if e['disclosure']!='private':raise Refusal('PUBLIC_RELEASE_REQUIRES_SEPARATE_REVIEW')
 if not isinstance(e['data_authorized'],bool):raise Refusal('AUTHORIZATION_TYPE')
 for k in ['target_decision','receiving_owner','data_custodian']:
  if not isinstance(e[k],str) or len(e[k])>4000:raise Refusal('INVALID_FIELD: '+k)
 criteria=e['acceptance_criteria']
 if not isinstance(criteria,list) or len(criteria)>100 or any(not isinstance(x,str) or not x.strip() or len(x)>2000 for x in criteria):raise Refusal('ACCEPTANCE_SCHEMA')
 holds=[k for k in ['target_decision','receiving_owner','data_custodian'] if not e[k].strip()]
 if not e['data_authorized']:holds.append('data_authorized')
 if not criteria:holds.append('acceptance_criteria')
 estimate=economics(e['economics'])
 return {'schema':'axm-proof-plan/1','case_id':e['case_id'],'engagement_sha256':sha(canonical(e)),'adapter':e['adapter'],'state':'HELD' if holds else 'READY_FOR_SCOPING','holds':holds,'criteria':criteria,'economics':estimate,'customer_acceptance':'NOT_ESTABLISHED','execute_allowed':False,'publish_allowed':False,'next_dependency':'Resolve named holds' if holds else 'Recipient reviews source mapping, test scope, access, budget and acceptance before customer execution','scope':['One named decision and one reviewed adapter mapping','Retain original evidence and explicit corrections','Reproduce original and corrected results in a clean recipient environment','Retain every failure and package the exact source, native records and verification commands'],'exclusions':['Production writes or account creation','Autonomous emails, calls or notifications','Unreviewed model calls or spend','Enterprise identity/compliance claims','Guaranteed savings or purchaser acceptance']}
def scope_markdown(p,e):
 # Plain text generation; no HTML or code evaluation of customer content.
 lines=['# Evaluation scope: '+e['case_id'],'','State: '+p['state'], 'Receiving owner: '+e['receiving_owner'],'Data custodian: '+e['data_custodian'],'','## Decision',e['target_decision'],'','## Agreed tests (proposed; recipient approval outstanding)']
 lines+=['- '+x for x in p['criteria']];lines+=['','## Deliverables']+['- '+x for x in p['scope']]
 lines+=['','## Exclusions']+['- '+x for x in p['exclusions']]
 lines+=['','## Commercial assumptions',json.dumps(p['economics'],indent=2),'','This is a scoping artifact, not an executed agreement. Payment, budget, data authority and acceptance remain with the named parties.']
 return '\n'.join(lines)+'\n'
def verify_receipt(path):
 root=Path(path);m=load(root/'evidence-manifest.json');fail=[]
 if m.get('schema')!='axm-proof-run-files/1' or not isinstance(m.get('files'),dict) or 'report.json' not in m['files']:raise Refusal('RECEIPT_SCHEMA')
 for name,v in m['files'].items():
  p=root/safe_relative(name)
  if p.is_symlink() or not p.is_file() or sha(p.read_bytes())!=v['sha256'] or p.stat().st_size!=v['bytes']:fail.append(name)
 if fail:raise Refusal('RECEIPT_CHANGED: '+','.join(fail))
 return {'status':'PASS','files':len(m['files']),'meaning':'Retained bytes match; independently execute qualify for a new observation. This is not customer acceptance.'}
def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 v=sub.add_parser('verify');v.add_argument('--expected-manifest-sha256')
 q=sub.add_parser('qualify');q.add_argument('--output',type=Path,required=True);q.add_argument('--adapter',choices=ADAPTERS,action='append');q.add_argument('--expected-manifest-sha256')
 p=sub.add_parser('plan');p.add_argument('engagement',type=Path);p.add_argument('--output',type=Path,required=True)
 r=sub.add_parser('verify-run');r.add_argument('directory',type=Path)
 args=parser.parse_args()
 try:
  if args.command=='verify':result=verify(expected=args.expected_manifest_sha256)
  elif args.command=='qualify':result=qualify(args.output,args.adapter or ADAPTERS,args.expected_manifest_sha256)
  elif args.command=='verify-run':result=verify_receipt(args.directory)
  else:
   verify();e=load(args.engagement);result=plan(e);args.output.resolve().mkdir(parents=True,exist_ok=False)
   dump(args.output/'engagement.json',e);dump(args.output/'plan.json',result)
   (args.output/'SCOPE.md').write_text(scope_markdown(result,e),encoding='utf-8')
  print(json.dumps(result,indent=2));return 0 if result.get('status','PASS')=='PASS' and result.get('state')!='HELD' else 2
 except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as e:
  print(json.dumps({'status':'REFUSED','reason':str(e)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
