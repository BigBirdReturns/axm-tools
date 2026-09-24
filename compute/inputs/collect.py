#!/usr/bin/env python3
"""Bounded input capture. Public metadata by default; explicit opt-in for account supply.
No credentials are discovered, no arbitrary URL is accepted, and no compute is created.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, hashlib, json, math, os, re, urllib.error, urllib.request
from pathlib import Path
MAX_BYTES = 2 * 1024 * 1024
PUBLIC = {
 'dstack-release': ('https://api.github.com/repos/dstackai/dstack/releases/latest', 'release'),
 'vllm-release': ('https://api.github.com/repos/vllm-project/vllm/releases/latest', 'release'),
 'sglang-release': ('https://api.github.com/repos/sgl-project/sglang/releases/latest', 'release'),
 'lmcache-release': ('https://api.github.com/repos/LMCache/LMCache/releases/latest', 'release'),
 'docling-release': ('https://api.github.com/repos/docling-project/docling/releases/latest', 'release'),
 'coding-model': ('https://huggingface.co/api/models/Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8', 'model'),
}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self, req, fp, code, msg, headers, newurl):
  raise ValueError('Redirect held; review the source explicitly')
def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def finite(x): return isinstance(x, (int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>=0
def bounded(s): return s[:250] if isinstance(s,str) else None
def get(url, headers=None):
 req=urllib.request.Request(url,headers={'User-Agent':'SecondRun-input-observer/0.1','Accept':'application/json',**(headers or {})},method='GET')
 with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as response:
  raw=response.read(MAX_BYTES+1)
  if len(raw)>MAX_BYTES: raise ValueError('Response exceeds capture limit')
  return raw,json.loads(raw)
def safe_error(exc):
 if isinstance(exc,urllib.error.HTTPError): return 'HTTP_'+str(exc.code)
 if isinstance(exc,urllib.error.URLError): return 'NETWORK_UNAVAILABLE'
 return 'UNREADABLE_OR_INVALID_SOURCE'
def summarize(kind,data):
 if not isinstance(data,dict): raise ValueError('Object required')
 if kind=='release':
  if not isinstance(data.get('tag_name'),str): raise ValueError('Missing release tag')
  return {'tag':bounded(data['tag_name']),'published_at':bounded(data.get('published_at')),'prerelease':data.get('prerelease'),'url':bounded(data.get('html_url')),'interpretation':'Upstream release metadata, not installation or compatibility approval.'}
 if kind=='model':
  return {'model':bounded(data.get('id')),'revision':bounded(data.get('sha')),'gated':data.get('gated'),'license':bounded((data.get('cardData') or {}).get('license')),'last_modified':bounded(data.get('lastModified')),'interpretation':'Repository metadata; no weights downloaded, license review and task qualification remain separate.'}
 raise ValueError('Unknown summary kind')
def observe(source_id):
 url,kind=PUBLIC[source_id]; when=stamp()
 try:
  raw,data=get(url)
  return {'id':source_id,'url':url,'observed_at':when,'status':'OBSERVED','source_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'value':summarize(kind,data)}
 except Exception as exc: return {'id':source_id,'url':url,'observed_at':when,'status':'UNAVAILABLE','reason':safe_error(exc)}
def normalize_hotaisle(data,when,source_sha):
 if isinstance(data,dict): data=data.get('results')
 if not isinstance(data,list): raise ValueError('HA response must be an array/results array')
 offers=[]; ids=set()
 for row in data:
  specs=row.get('Specs',row.get('specs',{})); gpus=specs.get('gpus',[])
  if not isinstance(gpus,list) or not gpus: continue
  if any(not isinstance(g,dict) or not isinstance(g.get('count'),int) or isinstance(g.get('count'),bool) or g['count']<1 for g in gpus): raise ValueError('Invalid GPU count')
  count=sum(g['count'] for g in gpus); models=sorted(set(' '.join(str(g.get(k,'')) for k in ['manufacturer','model']).strip() for g in gpus))
  # This identifies an offered type, not a tenant's deployment or an available host.
  oid='hotaisle:'+hashlib.sha256(json.dumps(specs,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
  if oid in ids: raise ValueError('Duplicate offered specification; cannot select uniquely')
  ids.add(oid); rate=row.get('OnDemandPrice'); minimum=row.get('MinimumReservationMinutes'); qty=row.get('Quantity')
  offers.append({'id':oid,'provider':'hotaisle','gpu_count':count,'models':models,'region':None,
   'allocation_hour_usd':rate/100 if finite(rate) else None,'minimum_charge_s':minimum*60 if finite(minimum) else None,
   'quantity':qty if finite(qty) else None,'availability':'available' if finite(qty) and qty>0 else 'unavailable' if finite(qty) and qty==0 else 'unknown',
   'binding_limit':'Offer observation, not successful reservation; region and billing quantum require explicit evidence.'})
 return {'schema':'second-run/supply-observation@1','provider':'hotaisle','observed_at':when,'expires_at':(dt.datetime.fromisoformat(when.replace('Z','+00:00'))+dt.timedelta(seconds=60)).isoformat(),'source_sha256':source_sha,'synthetic':False,'offers':offers}
def normalize_runpod(data,when,source_sha,count,cloud):
 if not isinstance(data,dict) or not isinstance(data.get('gpus'),list): raise ValueError('Missing gpus array')
 offers=[]
 for gpu in data['gpus']:
  rate=(gpu.get('price') or {}).get(cloud.lower()); identifier=gpu.get('id')
  if not isinstance(identifier,str): raise ValueError('GPU id missing')
  offers.append({'id':'runpod:'+identifier+':'+cloud+':'+str(count),'provider':'runpod','gpu_count':count,
   'models':[bounded(gpu.get('name',identifier))],'region':None,'cloud':cloud,'product':'POD',
   'allocation_hour_usd':rate*count if finite(rate) else None,'minimum_charge_s':None,'quantity':None,
   'availability':'listed','availability_band':bounded(gpu.get('availability')),
   'data_centers':[{'id':bounded(d.get('id')),'availability':bounded(d.get('availability'))} for d in gpu.get('dataCenters',[])],
   'binding_limit':'Catalog availability bands are not allocation receipts. Missing minimum terms remain unknown.'})
 return {'schema':'second-run/supply-observation@1','provider':'runpod','observed_at':when,'expires_at':(dt.datetime.fromisoformat(when.replace('Z','+00:00'))+dt.timedelta(seconds=60)).isoformat(),'source_sha256':source_sha,'synthetic':False,'offers':offers}
def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',required=True,type=Path); p.add_argument('--sources',nargs='+',choices=sorted(PUBLIC),default=sorted(PUBLIC))
 p.add_argument('--supply',choices=['hotaisle','runpod']); p.add_argument('--allow-account-read',action='store_true'); p.add_argument('--token-env'); p.add_argument('--team'); p.add_argument('--count',type=int,default=1); p.add_argument('--cloud',choices=['SECURE','COMMUNITY'],default='SECURE'); args=p.parse_args()
 if args.out.exists(): p.error('Output directory must be new; snapshots are immutable')
 if args.supply:
  if not args.allow_account_read or not args.token_env or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',args.token_env): p.error('Supply requires --allow-account-read and a named --token-env; no credential discovery')
  token=os.environ.get(args.token_env)
  if not token: p.error('Named credential is unavailable')
  if not 1<=args.count<=64: p.error('count must be 1..64')
  if args.supply=='hotaisle' and (not args.team or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.team)): p.error('HA requires a bounded team handle')
  url=('https://admin.hotaisle.app/api/teams/'+args.team+'/virtual_machines/available/') if args.supply=='hotaisle' else 'https://api.runpod.io/v2/catalog/gpus?include=AVAILABILITY&product=POD&count='+str(args.count)+'&cloud='+args.cloud
  when=stamp()
  try:
   raw,data=get(url,{'Authorization':('Token ' if args.supply=='hotaisle' else 'Bearer ')+token}); dig=hashlib.sha256(raw).hexdigest()
   output=normalize_hotaisle(data,when,dig) if args.supply=='hotaisle' else normalize_runpod(data,when,dig,args.count,args.cloud)
  except Exception as exc: output={'schema':'second-run/supply-observation@1','provider':args.supply,'observed_at':when,'status':'UNAVAILABLE','reason':safe_error(exc),'offers':[]}
 else:
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: observations=list(pool.map(observe,args.sources))
  output={'schema':'second-run/material-observations@1','observed_at':stamp(),'observations':observations,'scope':'Release/model metadata only; no price renewal, installation, compatibility certification or execution.'}
 args.out.mkdir(parents=True); target=args.out/'observation.json'; target.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 print(json.dumps({'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'status':output.get('status','CAPTURED')}))
 return 2 if output.get('status')=='UNAVAILABLE' or ('observations' in output and not any(x['status']=='OBSERVED' for x in output['observations'])) else 0
if __name__=='__main__': raise SystemExit(main())
