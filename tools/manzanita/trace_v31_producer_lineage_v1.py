#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, io, json, os, re, subprocess, zipfile
from pathlib import Path, PurePosixPath

REPO=os.getenv('GH_REPO','BigBirdReturns/axm-tools')
OUT=Path(os.getenv('V31_LINEAGE_OUT','/tmp/v31-producer-lineage-v1'))
DATE_FROM=os.getenv('V31_LINEAGE_FROM','2026-08-22T00:00:00Z')
DATE_TO=os.getenv('V31_LINEAGE_TO','2026-09-01T23:59:59Z')
MAX_LOG_RUNS=int(os.getenv('V31_MAX_LOG_RUNS','260'))
MAX_LOG_BYTES=int(os.getenv('V31_MAX_LOG_BYTES','900000000'))
TARGETS={
 'accepted_parent_archive':{'names':['mw-habitat-live-photo-030-r1.zip'],'bytes':82813564,'sha256':'8a480a3bd05afb6cdcc007d98b0ef63e80576fb1912763c147a3739647299f91'},
 'v20_archive':{'names':['mw-habitat-live-photo-020.zip'],'bytes':146305044,'sha256':'98b81d0f3f56a8aa6a12613fe7ae06b8b9e860f82ddaa02aa48e6f66547c25bd'},
 'public_convergence':{'names':['PUBLIC_CONVERGENCE.json'],'bytes':127413,'sha256':'fd9dfd98532a21759754cb8969b2ad2d7a94fedce78ea8a428e584bf14aea1d9'},
 'admission_source':{'names':['admit_v31_exact_inputs.py'],'bytes':38969,'sha256':'c3eed78862ae53a975d13b94f2cf82eeea832466a46bdb3e771fd798bd12534a'},
 'neighborhood_reference':{'names':['neighborhood-reference.png','neighborhood-systems-ae49e0308b30.png'],'bytes':2797021,'sha256':'ae49e0308b302e5bdce1cdb5913b009c2743d1043ddcb8c2e29b6934e1353b9b'},
 'neighborhood_map':{'names':['neighborhood-map.svg','neighborhood-map-2d1d6abe3784.svg'],'bytes':2038,'sha256':'2d1d6abe37845ed2b65070a9198d301c3e6e4df779139003499eb8ff406d6e3b'},
}
TOKENS=[]
for k,v in TARGETS.items(): TOKENS += v['names']+[v['sha256'],str(v['bytes'])]
TOKENS += ['mw-habitat-live-photo-020','mw-habitat-live-photo-030','PUBLIC_CONVERGENCE','admit_v31_exact_inputs','neighborhood-reference','neighborhood-map','PARENT_DERIVED_V30_R1_ARCHIVE_RECEIPT','build_v30_parent_derived','finalize_v30_package','seal_and_validate_v30']
TOKENS=sorted(set(TOKENS),key=len,reverse=True)
LOW=[x.lower() for x in TOKENS]

def run(cmd,check=True,timeout=1200,text=True):
 return subprocess.run(cmd,check=check,timeout=timeout,text=text,capture_output=True)
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def dump(name,obj):
 OUT.mkdir(parents=True,exist_ok=True); (OUT/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def gh_json(endpoint): return json.loads(run(['gh','api',endpoint],timeout=300).stdout)
def gh_pages(endpoint): return json.loads(run(['gh','api','--paginate','--slurp',endpoint],timeout=1200).stdout)
def excerpts(text,needles,limit=8,width=260):
 out=[]; low=text.lower()
 for n in needles:
  p=low.find(n.lower())
  if p>=0:
   a=max(0,p-width); b=min(len(text),p+len(n)+width)
   out.append({'token':n,'excerpt':text[a:b].replace('\x00',' ')})
  if len(out)>=limit: break
 return out

def safe_member(name):
 p=PurePosixPath(name.replace('\\','/'))
 return bool(name) and not p.is_absolute() and all(x not in ('','.','..') for x in p.parts)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 errors=[]
 fetch=[]
 for cmd in [
  ['git','fetch','--force','--prune','--tags','origin','+refs/heads/*:refs/remotes/origin/*'],
  ['git','fetch','--force','origin','+refs/pull/*/head:refs/remotes/origin/pull/*']]:
  p=run(cmd,check=False,timeout=1200); fetch.append({'cmd':cmd,'returncode':p.returncode,'stderr':p.stderr[-4000:]})

 paths={}
 for line in run(['git','rev-list','--objects','--all'],timeout=1200).stdout.splitlines():
  a=line.split(' ',1)
  if len(a)==2: paths.setdefault(a[0],[]).append(a[1])
 rows=[]
 for line in run(['git','cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype) %(objectsize)'],timeout=1200).stdout.splitlines():
  a=line.split()
  if len(a)==3 and a[1]=='blob' and a[2].isdigit() and int(a[2])<=2_500_000: rows.append((a[0],int(a[2])))
 git_matches=[]
 for i,(oid,size) in enumerate(rows,1):
  try: raw=subprocess.run(['git','cat-file','blob',oid],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120).stdout
  except Exception as e: errors.append({'lane':'git_blob','source':oid,'error':str(e)}); continue
  try: text=raw.decode('utf-8')
  except UnicodeDecodeError: text=raw.decode('utf-8','ignore')
  low=text.lower(); matched=[TOKENS[j] for j,n in enumerate(LOW) if n in low]
  pths=paths.get(oid,[])
  path_match=any(any(n.lower() in p.lower() for n in ['020','030','convergence','neighborhood','exact_input','admission','parent_derived']) for p in pths)
  if matched or path_match:
   git_matches.append({'oid':oid,'bytes':size,'paths':pths[:30],'matched_tokens':matched[:30],'excerpts':excerpts(text,matched or TOKENS,10)})

 commit_matches=[]
 fmt='%H%x1f%aI%x1f%s%x1f%b%x1e'
 log=run(['git','log','--all','--date=iso-strict',f'--pretty=format:{fmt}'],timeout=1200).stdout
 for rec in log.split('\x1e'):
  if not rec.strip(): continue
  a=rec.strip().split('\x1f',3)
  if len(a)!=4: continue
  sha,date,subject,body=a; text=subject+'\n'+body; low=text.lower(); m=[TOKENS[j] for j,n in enumerate(LOW) if n in low]
  if m: commit_matches.append({'sha':sha,'date':date,'subject':subject,'matched_tokens':m[:30],'excerpts':excerpts(text,m,6)})

 artifacts=[]
 try:
  for pg in gh_pages(f'repos/{REPO}/actions/artifacts?per_page=100'):
   artifacts.extend(pg.get('artifacts',[]))
 except Exception as e: errors.append({'lane':'artifact_metadata','error':str(e)})
 artifact_matches=[]
 candidate_run_ids=set()
 for a in artifacts:
  text=' '.join(str(x or '') for x in [a.get('name'),(a.get('workflow_run') or {}).get('head_branch'),(a.get('workflow_run') or {}).get('head_sha')])
  low=text.lower(); m=[TOKENS[j] for j,n in enumerate(LOW) if n in low]
  broad=any(x in low for x in ['manzanita','habitat','convergence','neighborhood','live-photo','exact-input','materialization','parent'])
  if m or broad:
   r={'id':a.get('id'),'name':a.get('name'),'bytes':a.get('size_in_bytes'),'expired':a.get('expired'),'created_at':a.get('created_at'),'expires_at':a.get('expires_at'),'digest':a.get('digest'),'workflow_run':a.get('workflow_run'),'matched_tokens':m}
   artifact_matches.append(r)
   if (a.get('workflow_run') or {}).get('id'): candidate_run_ids.add((a['workflow_run']['id']))

 runs=[]
 try:
  for pg in gh_pages(f'repos/{REPO}/actions/runs?created={DATE_FROM}..{DATE_TO}&per_page=100'):
   runs.extend(pg.get('workflow_runs',[]))
 except Exception as e: errors.append({'lane':'run_metadata','error':str(e)})
 run_matches=[]
 for r in runs:
  text=' '.join(str(x or '') for x in [r.get('name'),r.get('display_title'),r.get('head_branch'),(r.get('head_commit') or {}).get('message'),r.get('path')])
  low=text.lower(); m=[TOKENS[j] for j,n in enumerate(LOW) if n in low]
  broad=any(x in low for x in ['manzanita','habitat','convergence','neighborhood','live-photo','exact input','materialization','parent'])
  if m or broad:
   rr={k:r.get(k) for k in ['id','name','display_title','head_branch','head_sha','path','event','status','conclusion','created_at','updated_at']}; rr['matched_tokens']=m
   run_matches.append(rr); candidate_run_ids.add(r['id'])

 log_matches=[]; log_bytes=0
 ordered=sorted(candidate_run_ids, reverse=True)
 for run_id in ordered[:MAX_LOG_RUNS]:
  if log_bytes>=MAX_LOG_BYTES: break
  try:
   raw=subprocess.run(['gh','api',f'repos/{REPO}/actions/runs/{run_id}/logs'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300).stdout
  except Exception as e:
   errors.append({'lane':'run_logs','source':run_id,'error':str(e)}); continue
  log_bytes += len(raw)
  try:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    for info in z.infolist():
     if info.is_dir() or not safe_member(info.filename) or info.file_size>50_000_000: continue
     data=z.read(info); text=data.decode('utf-8','ignore'); low=text.lower(); m=[TOKENS[j] for j,n in enumerate(LOW) if n in low]
     if m: log_matches.append({'run_id':run_id,'member':info.filename,'bytes':len(data),'matched_tokens':m[:30],'excerpts':excerpts(text,m,14)})
  except Exception as e: errors.append({'lane':'log_zip','source':run_id,'error':str(e)})

 # Classify target lineage from all exact-token observations.
 lineage={}
 for key,spec in TARGETS.items():
  needles=[*spec['names'],spec['sha256'],str(spec['bytes'])]
  gm=[x for x in git_matches if set(x['matched_tokens']) & set(needles)]
  cm=[x for x in commit_matches if set(x['matched_tokens']) & set(needles)]
  am=[x for x in artifact_matches if set(x['matched_tokens']) & set(needles)]
  lm=[x for x in log_matches if set(x['matched_tokens']) & set(needles)]
  lineage[key]={'target':spec,'git_blob_observations':gm,'commit_observations':cm,'artifact_metadata_observations':am,'run_log_observations':lm,'producer_recipe_located':bool(gm or lm),'exact_output_bytes_recovered':False,'regeneration_executed':False}

 result='PASS_PRODUCER_LINEAGE_OBSERVED_REGENERATION_CANDIDATES_EMITTED' if any(v['producer_recipe_located'] for v in lineage.values()) else 'HOLD_NO_PRODUCER_RECIPE_LOCATED_IN_REACHABLE_HISTORY_OR_RETAINED_LOGS'
 census={'schema':'manzanita/v31-producer-lineage-census@1','observed_at':now(),'result':result,'scope':{'date_from':DATE_FROM,'date_to':DATE_TO,'max_log_runs':MAX_LOG_RUNS,'max_log_bytes':MAX_LOG_BYTES},'counts':{'git_text_blobs_scanned':len(rows),'git_matches':len(git_matches),'commit_matches':len(commit_matches),'artifacts_listed':len(artifacts),'artifact_matches':len(artifact_matches),'runs_listed':len(runs),'run_matches':len(run_matches),'log_runs_attempted':min(len(ordered),MAX_LOG_RUNS),'log_bytes':log_bytes,'log_matches':len(log_matches),'errors':len(errors)},'fetch':fetch,'lineage':lineage,'git_matches':git_matches,'commit_matches':commit_matches,'artifact_matches':artifact_matches,'run_matches':run_matches,'log_matches':log_matches,'errors':errors,'authority':{'product_files_modified':0,'merge_authorized':False,'release_authorized':False,'pages_effect':'none','external_effect':'none'}}
 dump('V31_PRODUCER_LINEAGE_CENSUS_V1.json',census)
 dump('V31_PRODUCER_LINEAGE_EXECUTION_RECEIPT_V1.json',{'schema':'manzanita/v31-producer-lineage-receipt@1','observed_at':now(),'result':result,'targets_with_recipe':[k for k,v in lineage.items() if v['producer_recipe_located']],'targets_without_recipe':[k for k,v in lineage.items() if not v['producer_recipe_located']],'exact_outputs_recovered':[],'regeneration_executed':False,'v2_intake_invoked':False,'queue_advanced':False,'v15_created':False,'authority':census['authority']})
 md=['# V31 producer-lineage result','',f'`{result}`','',f"Git text blobs scanned: {len(rows)}",f"Artifacts listed: {len(artifacts)}",f"Runs in window: {len(runs)}",f"Run-log matches: {len(log_matches)}",'', '## Target disposition','']
 for k,v in lineage.items(): md.append(f"- `{k}`: recipe_located={str(v['producer_recipe_located']).lower()}, git={len(v['git_blob_observations'])}, logs={len(v['run_log_observations'])}, artifacts={len(v['artifact_metadata_observations'])}")
 md += ['','No historical workflow was executed by this census. Any regeneration must be isolated, deterministic, side-effect-free, and compared against the registered byte count and SHA-256 before V2 intake.','']
 (OUT/'V31_PRODUCER_LINEAGE_RELEASE_STATUS_V1.md').write_text('\n'.join(md),encoding='utf-8')
 print(json.dumps({'result':result,'counts':census['counts'],'targets_with_recipe':[k for k,v in lineage.items() if v['producer_recipe_located']]},indent=2))
if __name__=='__main__': main()
