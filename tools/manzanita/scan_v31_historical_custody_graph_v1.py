#!/usr/bin/env python3
"""Read-only V31 exact-byte scan across Git, LFS, Actions artifacts, and releases."""
import base64,binascii,datetime as dt,hashlib,io,json,os,re,shutil,subprocess,zipfile
from pathlib import Path,PurePosixPath

R=os.getenv('GH_REPO','BigBirdReturns/axm-tools'); O=Path(os.getenv('V31_OUTPUT_ROOT','/tmp/v31-historical-custody-graph-v1'))
S=os.getenv('V31_ARTIFACT_SINCE','2026-08-13T00:00:00Z'); KEEP=210*1024*1024; STREAM=550*1024*1024; DEPTH=8
AB=int(os.getenv('V31_MAX_ARTIFACT_DOWNLOAD_BYTES','3500000000')); RB=int(os.getenv('V31_MAX_RELEASE_DOWNLOAD_BYTES','1000000000'))
REMOTE=int(os.getenv('V31_MAX_SINGLE_REMOTE_BYTES','550000000')); AC=int(os.getenv('V31_MAX_ARTIFACT_COUNT','350')); RC=int(os.getenv('V31_MAX_RELEASE_ASSET_COUNT','100'))
T={
'accepted_parent_archive':(['mw-habitat-live-photo-030-r1.zip'],82813564,'8a480a3bd05afb6cdcc007d98b0ef63e80576fb1912763c147a3739647299f91'),
'v20_archive':(['mw-habitat-live-photo-020.zip'],146305044,'98b81d0f3f56a8aa6a12613fe7ae06b8b9e860f82ddaa02aa48e6f66547c25bd'),
'v20_standalone':(['mw-habitat-live-photo-020.STANDALONE.html'],17916146,'b20611b56fc64ed42eb8fcbc18f2909babb186289342abf0008b4a6bbfa908e4'),
'public_convergence':(['PUBLIC_CONVERGENCE.json'],127413,'fd9dfd98532a21759754cb8969b2ad2d7a94fedce78ea8a428e584bf14aea1d9'),
'admission_source':(['admit_v31_exact_inputs.py'],38969,'c3eed78862ae53a975d13b94f2cf82eeea832466a46bdb3e771fd798bd12534a'),
'neighborhood_reference':(['neighborhood-reference.png','neighborhood-systems-ae49e0308b30.png'],2797021,'ae49e0308b302e5bdce1cdb5913b009c2743d1043ddcb8c2e29b6934e1353b9b'),
'neighborhood_cached':(['neighborhood-cached.webp','neighborhood-reference-5ec9252f1615.webp'],500586,'5ec9252f1615e86a239384a76a508554b2bd9e9221d5e202abce109e804f29d8'),
'neighborhood_map':(['neighborhood-map.svg','neighborhood-map-2d1d6abe3784.svg'],2038,'2d1d6abe37845ed2b65070a9198d301c3e6e4df779139003499eb8ff406d6e3b')}
ID={(n,h):k for k,(_,n,h) in T.items()}; NM={n.lower():k for k,(ns,_,_) in T.items() for n in ns}
DU=re.compile(rb'data:[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+(?:;[A-Za-z0-9_.=:+-]+)*;base64,([A-Za-z0-9+/=\r\n]{16,})')
TOK=('v31','v30','v20','live-photo','habitat','parent','provenance','convergence','recovery','archive','exact','donor','manzanita','plant')

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def run(a,check=True,to=1200,text=True): return subprocess.run(a,check=check,timeout=to,text=text,capture_output=True)
def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''): h.update(c)
 return h.hexdigest()
def safe(n):
 q=n.replace('\\','/');p=PurePosixPath(q)
 return not p.is_absolute() and not re.match(r'^[A-Za-z]:',q) and all(x not in ('','.','..') for x in p.parts)
def pri(n,b=''):
 x=(n+' '+b).lower();return (-sum(len(TOK)-i for i,t in enumerate(TOK) if t in x),n.lower())

class X:
 def __init__(s):
  s.start=now();s.d=O/'downloads';s.h=O/'exact-hits';s.d.mkdir(parents=True,exist_ok=True);s.h.mkdir(parents=True,exist_ok=True)
  s.c={k:0 for k in 'git_objects git_blobs git_blob_skips git_refs git_paths git_unreachable lfs_records lfs_scanned artifacts_listed artifacts_expired artifacts_old artifacts_large artifacts_eligible artifacts_count_skips artifacts_byte_skips artifacts_downloaded artifact_bytes releases_listed releases_large releases_eligible releases_count_skips releases_byte_skips releases_downloaded release_bytes blobs bytes zips members member_skips unsafe data_urls decoded exact name_candidates size_candidates errors'.split()}
  s.err=[];s.hit=[];s.cand=[];s.remote=[];s.git={};s.seen=set();s.targets=set()
 def e(s,l,src,e):
  s.c['errors']+=1
  if len(s.err)<2000:s.err.append({'lane':l,'source':src,'error':str(e)[:4000]})
 def cl(s,n,h,src,cls,b,data):
  s.c['blobs']+=1;s.c['bytes']+=n;k=ID.get((n,h))
  if k:
   if data is None:return s.e('retain',src,'exact hash without retained bytes')
   p=s.h/k/T[k][0];p.parent.mkdir(parents=True,exist_ok=True)
   if not p.exists():p.write_bytes(data)
   if shaf(p)!=h:raise RuntimeError('exact-hit collision')
   s.targets.add(k);s.c['exact']=len(s.targets);s.hit.append({'target':k,'source':src,'class':cls,'basename':b,'bytes':n,'sha256':h,'path':p.relative_to(O).as_posix()});return
  if b and b.lower() in NM:
   s.c['name_candidates']+=1
   if len(s.cand)<10000:s.cand.append({'kind':'name','target':NM[b.lower()],'source':src,'basename':b,'bytes':n,'sha256':h})
  z=[k for k,(_,q,_) in T.items() if q==n]
  if z:
   s.c['size_candidates']+=1
   if len(s.cand)<10000:s.cand.append({'kind':'size','targets':z,'source':src,'basename':b,'bytes':n,'sha256':h})
 def ins(s,data,src,cls,b=None,d=0):
  h=hashlib.sha256(data).hexdigest();s.cl(len(data),h,src,cls,b,data);key=(len(data),h)
  if key in s.seen:return
  s.seen.add(key)
  if d<=DEPTH and data[:4] in (b'PK\x03\x04',b'PK\x05\x06',b'PK\x07\x08'):s.zb(data,src,d)
  if len(data)<=KEEP:
   for i,m in enumerate(DU.finditer(data)):
    if i>=10000:s.e('data-cap',src,i);break
    s.c['data_urls']+=1
    try:q=base64.b64decode(re.sub(rb'\s+',b'',m.group(1)),validate=True)
    except (binascii.Error,ValueError) as e:s.e('data-decode',f'{src}#{i}',e);continue
    if len(q)<=KEEP:s.c['decoded']+=1;s.ins(q,f'{src}#data-{i}','data_url',None,d+1)
 def zb(s,data,src,d):
  try:
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    s.c['zips']+=1;bad=z.testzip()
    if bad:s.e('crc',src,bad)
    for i in z.infolist():
     if i.is_dir():continue
     s.c['members']+=1
     if not safe(i.filename):s.c['unsafe']+=1;continue
     if i.file_size>STREAM:s.c['member_skips']+=1;continue
     ms=f'{src}!/{i.filename}'
     try:s.ins(z.read(i),ms,'zip_member',PurePosixPath(i.filename.replace('\\','/')).name,d+1)
     except Exception as e:s.e('zip-member',ms,e)
  except Exception as e:s.e('zip-open',src,e)
 def fp(s,p,src):
  n=p.stat().st_size;h=shaf(p);data=p.read_bytes() if n<=KEEP else None;s.cl(n,h,src,'remote',p.name,data);before=len(s.targets);crc='NOT_ZIP'
  try:
   with zipfile.ZipFile(p) as z:
    s.c['zips']+=1;bad=z.testzip();crc='PASS' if bad is None else 'FAIL:'+bad
    for i in z.infolist():
     if i.is_dir():continue
     s.c['members']+=1
     if not safe(i.filename):s.c['unsafe']+=1;continue
     if i.file_size>STREAM:s.c['member_skips']+=1;continue
     ms=f'{src}!/{i.filename}'
     try:s.ins(z.read(i),ms,'zip_member',PurePosixPath(i.filename.replace('\\','/')).name,1)
     except Exception as e:s.e('remote-member',ms,e)
  except zipfile.BadZipFile:
   if data is not None:s.ins(data,src,'remote',p.name)
  return {'source':src,'bytes':n,'sha256':h,'zip_crc':crc,'new_exact_targets':len(s.targets)-before}
 def gitlane(s):
  f=[]
  for a in (['git','fetch','--force','--prune','--tags','origin','+refs/heads/*:refs/remotes/origin/*'],['git','fetch','--force','origin','+refs/pull/*/head:refs/remotes/origin/pull/*']):
   try:p=run(a,False,900);f.append({'command':a,'returncode':p.returncode,'stderr':p.stderr[-4000:]})
   except Exception as e:s.e('fetch',' '.join(a),e)
  try:refs=[x for x in run(['git','for-each-ref','--format=%(refname) %(objectname)'],to=300).stdout.splitlines() if x];s.c['git_refs']=len(refs)
  except Exception as e:refs=[];s.e('refs',R,e)
  paths={}
  try:
   for x in run(['git','rev-list','--objects','--all'],to=900).stdout.splitlines():
    a=x.split(' ',1)
    if len(a)==2:paths.setdefault(a[0],[]).append(a[1]);s.c['git_paths']+=1
  except Exception as e:s.e('rev-list',R,e)
  try:
   rows=[]
   for x in run(['git','cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype) %(objectsize)']).stdout.splitlines():
    a=x.split()
    if len(a)==3 and a[2].isdigit():rows.append((a[0],a[1],int(a[2])))
   s.c['git_objects']=len(rows);bl=[x for x in rows if x[1]=='blob'];s.c['git_blobs']=len(bl)
   for j,(oid,_,n) in enumerate(bl,1):
    if n>STREAM:s.c['git_blob_skips']+=1;continue
    try:
     q=subprocess.run(['git','cat-file','blob',oid],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300).stdout;ps=paths.get(oid,[]);s.ins(q,f'git:{oid} paths={ps[:5]}','git_blob',PurePosixPath(ps[0]).name if ps else None)
    except Exception as e:s.e('git-blob',oid,e)
    if j%500==0:print(f'git {j}/{len(bl)}',flush=True)
  except Exception as e:s.e('git-objects',R,e)
  try:
   p=run(['git','fsck','--full','--unreachable','--no-reflogs'],False);ls=[x for x in (p.stdout+'\n'+p.stderr).splitlines() if x];u=[x for x in ls if x.startswith('unreachable ')];s.c['git_unreachable']=len(u);fs={'returncode':p.returncode,'unreachable':len(u),'sample':ls[:100]}
  except Exception as e:fs={};s.e('fsck',R,e)
  l={'available':False,'fetch_attempted':False}
  try:
   p=run(['git','lfs','version'],False,60);l['available']=p.returncode==0
   if p.returncode==0:
    rs=[x for x in run(['git','lfs','ls-files','--all','-l'],False,300).stdout.splitlines() if x];s.c['lfs_records']=len(rs);l['records']=len(rs);l['sample']=rs[:100]
    if rs and len(rs)<=200:q=run(['git','lfs','fetch','--all'],False,1800);l.update(fetch_attempted=True,fetch_returncode=q.returncode,fetch_stderr=q.stderr[-4000:])
    root=Path('.git/lfs/objects')
    if root.exists():
     for p in sorted(x for x in root.rglob('*') if x.is_file() and x.stat().st_size<=STREAM):s.c['lfs_scanned']+=1;s.ins(p.read_bytes(),f'lfs:{p.relative_to(root)}','lfs',p.name)
  except Exception as e:s.e('lfs',R,e)
  s.git={'fetch_results':f,'ref_count':len(refs),'ref_sample':refs[:200],'path_objects':len(paths),'fsck':fs,'lfs':l}
 def gj(s,ep):return json.loads(run(['gh','api','--paginate','--slurp',ep]).stdout)
 def dl(s,ep,p,octet=False):
  a=['gh','api']+(['--header','Accept: application/octet-stream'] if octet else [])+[ep]
  try:
   with p.open('wb') as h:q=subprocess.run(a,stdout=h,stderr=subprocess.PIPE,timeout=1800)
   if q.returncode:p.unlink(missing_ok=True);return False,q.stderr.decode(errors='replace')[-4000:]
   return True,None
  except Exception as e:p.unlink(missing_ok=True);return False,str(e)
 def artifacts(s):
  try:aa=[a for pg in s.gj(f'repos/{R}/actions/artifacts?per_page=100') for a in pg.get('artifacts',[])]
  except Exception as e:return s.e('artifact-list',R,e)
  s.c['artifacts_listed']=len(aa);e=[]
  for a in aa:
   if a.get('expired'):s.c['artifacts_expired']+=1;continue
   if (a.get('created_at') or '')<S:s.c['artifacts_old']+=1;continue
   n=int(a.get('size_in_bytes') or 0)
   if n<=0 or n>REMOTE:s.c['artifacts_large']+=1;continue
   b=str((a.get('workflow_run') or {}).get('head_branch') or '');a['_p']=pri(str(a.get('name') or ''),b);e.append(a)
  e.sort(key=lambda a:(a['_p'],a.get('created_at','')));s.c['artifacts_eligible']=len(e);s.c['artifacts_count_skips']=max(0,len(e)-AC);total=0
  for a in e[:AC]:
   n=int(a.get('size_in_bytes') or 0)
   if total+n>AB:s.c['artifacts_byte_skips']+=1;continue
   aid=int(a['id']);p=s.d/f'a-{aid}.zip';ok,er=s.dl(f'repos/{R}/actions/artifacts/{aid}/zip',p)
   if not ok:s.e('artifact-download',str(aid),er);continue
   total+=p.stat().st_size;s.c['artifacts_downloaded']+=1;s.c['artifact_bytes']+=p.stat().st_size;src=f"artifact:{aid}:{a.get('name')}"
   try:r=s.fp(p,src);r.update(lane='artifact',id=aid,name=a.get('name'),listed=n,created=a.get('created_at'),run=a.get('workflow_run'));s.remote.append(r)
   except Exception as x:s.e('artifact-scan',src,x)
   p.unlink(missing_ok=True);print(f'artifacts {s.c["artifacts_downloaded"]} {total}',flush=True)
 def releases(s):
  try:rr=[r for pg in s.gj(f'repos/{R}/releases?per_page=100') for r in pg]
  except Exception as e:return s.e('release-list',R,e)
  aa=[]
  for r in rr:
   for a in r.get('assets',[]):
    s.c['releases_listed']+=1;n=int(a.get('size') or 0)
    if n<=0 or n>REMOTE:s.c['releases_large']+=1;continue
    a['_rn']=r.get('name');a['_tag']=r.get('tag_name');a['_p']=pri(str(a.get('name') or ''),str(a['_rn'])+' '+str(a['_tag']));aa.append(a)
  aa.sort(key=lambda a:a['_p']);s.c['releases_eligible']=len(aa);s.c['releases_count_skips']=max(0,len(aa)-RC);total=0
  for a in aa[:RC]:
   n=int(a.get('size') or 0)
   if total+n>RB:s.c['releases_byte_skips']+=1;continue
   aid=int(a['id']);p=s.d/f'r-{aid}';ok,er=s.dl(f'repos/{R}/releases/assets/{aid}',p,True)
   if not ok:s.e('release-download',str(aid),er);continue
   total+=p.stat().st_size;s.c['releases_downloaded']+=1;s.c['release_bytes']+=p.stat().st_size;src=f"release:{aid}:{a.get('name')}"
   try:r=s.fp(p,src);r.update(lane='release',id=aid,name=a.get('name'),listed=n,release=a['_rn'],tag=a['_tag']);s.remote.append(r)
   except Exception as x:s.e('release-scan',src,x)
   p.unlink(missing_ok=True)
 def finish(s):
  end=now();rec=sorted(s.targets);core={'accepted_parent_archive','v20_archive','public_convergence','admission_source','neighborhood_reference','neighborhood_cached','neighborhood_map'};complete=core<=s.targets
  ff=sum(x.get('returncode')!=0 for x in s.git.get('fetch_results',[]));l=s.git.get('lfs',{});lf=bool(l.get('fetch_attempted') and l.get('fetch_returncode') not in (0,None));sk=sum(s.c[k] for k in 'git_blob_skips member_skips artifacts_large artifacts_count_skips artifacts_byte_skips releases_large releases_count_skips releases_byte_skips'.split());cov=not(s.c['errors'] or ff or lf or sk)
  result='PASS_COMPLETE_TARGET_SET_RECOVERED_REQUIRES_EXISTING_V2_INTAKE' if complete else 'PARTIAL_EXACT_TARGET_BYTES_RECOVERED_V2_COMPLETE_SET_THRESHOLD_NOT_MET' if rec else 'PASS_DECLARED_HISTORICAL_GIT_ACTIONS_RELEASE_SCOPE_SCANNED_NO_EXACT_TARGET_BYTES' if cov else 'HOLD_NO_EXACT_TARGET_BYTES_RECOVERED_WITH_BOUNDED_COVERAGE_GAPS'
  coverage={'complete':cov,'fetch_failures':ff,'lfs_fetch_failed':lf,'bounded_skips':sk,'date_floor':S,'boundary':'Fetched refs and locally enumerable objects; unexpired Actions artifacts after the date floor and release assets within explicit limits. Excludes garbage-collected objects, expired artifacts, File Library bytes, and objects beyond limits.'}
  out={'schema':'manzanita/v31-historical-custody-graph-scan@1','repository':R,'started':s.start,'ended':end,'result':result,'targets':{k:{'names':v[0],'bytes':v[1],'sha256':v[2]} for k,v in T.items()},'counts':s.c,'exact_targets':rec,'hits':s.hit,'candidates':s.cand,'git':s.git,'remote':s.remote,'errors':s.err,'coverage':coverage,'limits':{'keep':KEEP,'stream':STREAM,'depth':DEPTH,'artifact_bytes':AB,'release_bytes':RB,'remote':REMOTE,'artifact_count':AC,'release_count':RC}}
  dump(O/'V31_HISTORICAL_CUSTODY_GRAPH_CENSUS_V1.json',out);dump(O/'V31_HISTORICAL_CUSTODY_GRAPH_EXACT_HITS_MANIFEST_V1.json',{'schema':'manzanita/v31-historical-custody-graph-exact-hits@1','result':result,'targets':rec,'complete':complete,'hits':s.hit,'v2_intake_invoked':False})
  dump(O/'V31_HISTORICAL_CUSTODY_GRAPH_EXECUTION_RECEIPT_V1.json',{'schema':'manzanita/v31-historical-custody-graph-receipt@1','observed':end,'result':result,'outcome':{'targets':rec,'complete':complete,'coverage':cov,'gap_count':s.c['errors']+ff+int(lf)+sk,'v2_intake':False,'terminal_pair':False,'product_files_modified':0,'merge':False,'release':False,'public_route':'none','pages':'none'},'required_passes':['PASS_V31_PUBLIC_CONVERGENCE_PROVENANCE_BOUND_AND_EXACT_INPUTS_MATERIALIZED_ADMITTED_AND_PARENT_EXTRACTED','PASS_V31_EXACT_INPUTS_MATERIALIZED_ADMITTED_AND_PARENT_EXTRACTED']})
  dump(O/'V31_HISTORICAL_CUSTODY_GRAPH_PUBLIC_SUMMARY_V1.json',{'schema':'manzanita/v31-historical-custody-graph-public-summary@1','observed':end,'result':result,'git_objects':s.c['git_objects'],'git_blobs':s.c['git_blobs'],'artifacts_downloaded':s.c['artifacts_downloaded'],'artifact_bytes':s.c['artifact_bytes'],'releases_downloaded':s.c['releases_downloaded'],'zips':s.c['zips'],'decoded_data_urls':s.c['decoded'],'exact_targets':rec,'complete':complete,'coverage':cov,'gap_count':s.c['errors']+ff+int(lf)+sk})
  rows=[{'path':p.relative_to(O).as_posix(),'bytes':p.stat().st_size,'sha256':shaf(p)} for p in sorted(x for x in O.rglob('*') if x.is_file() and 'downloads' not in x.parts)];dump(O/'V31_HISTORICAL_CUSTODY_GRAPH_ARTIFACT_MANIFEST_V1.json',{'schema':'manzanita/v31-historical-custody-graph-artifact-manifest@1','files':rows});shutil.rmtree(s.d,ignore_errors=True);print(json.dumps({'result':result,'targets':rec,'coverage':coverage,'counts':s.c},indent=2,sort_keys=True))

def main():
 O.mkdir(parents=True,exist_ok=True);x=X();x.gitlane();x.artifacts();x.releases();x.finish()
if __name__=='__main__':main()
