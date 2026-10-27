#!/usr/bin/env python3
"""Actual one-pass Genesis compilation and cold municipal consumption.
Disposable test identity only; the private half never reaches disk or another host.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys,zipfile
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import seal as S

def main():
 a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);x=a.parse_args();out=x.out.resolve();out.mkdir(exist_ok=False)
 p=subprocess.run(['node',str(HERE/'create.cjs'),str(out/'packets')],text=True,capture_output=True,timeout=60);(out/'create.log').write_text(p.stdout+p.stderr);p.check_returncode()
 from axm_build.sign import hybrid1_keygen
 from axm_verify.logic import verify_shard
 public,secret=hybrid1_keygen();pub=out/'fixture-publisher.pub';pub.write_bytes(public)
 results=[]
 for name,prior in [('origin',()),('successor',None)]:
  S.checked(out/'packets'/f'{name}.json');sid=S.G.seal(out/'packets'/f'{name}.json',out/name,secret,'@civil-fixture','Disposable civil software exercise','2026-10-27T00:00:00Z' if name=='origin' else '2026-10-27T04:00:00Z',() if name=='origin' else (origin,))
  if name=='origin':origin=sid
  else:successor=sid
 del secret
 def check(name,passed,detail=None):
  results.append({'name':name,'pass':bool(passed),'detail':detail});print(name,passed,flush=True)
  if not passed:raise AssertionError(name)
 def consume(name,extra=()):
  args=[sys.executable,'-B',str(HERE/'seal.py'),'consume',str(out/name),'--trusted-key',str(pub),'--expected-id',origin if name=='origin' else successor,*extra]
  p=subprocess.run(args,capture_output=True,text=True,timeout=60,cwd=out);(out/(name+'-consumer.log')).write_text(p.stdout+p.stderr);p.check_returncode();return json.loads(p.stdout)
 first=consume('origin');check('Original kernel artifact cold-opens with exact consumer',first['kernel']['status']=='PASS' and first['municipal']['consumer_identity']=='MATCH')
 last=consume('successor',('--predecessor',str(out/'origin')));d=last['municipal'];check('Successor preserves full predecessor event prefix',last['predecessor']['status']=='PRESERVED_PREFIX')
 check('Both unresolved delivery obligations survive',len(d['owed'])==2 and any(o['received']==350 for o in d['owed']) and any(o['received'] is None for o in d['owed']))
 check('Stock rights remain consumed after short delivery',sum(s['spent'] for s in d['stock_rights'])==660)
 check('Refused over-allocation remains visible',d['refusals']==1)
 check('Civil dependency and economic assessments recompute',len(d['civil_assessments'])==2 and all('result' in a for a in d['civil_assessments']))
 check('Physical field readiness remains unestablished',not d['operational_ready'] and d['field_verification']['open_obligations']==4)
 bad=out/'tampered';shutil.copytree(out/'successor',bad);p=bad/'content/judgment-packet.json';b=bytearray(p.read_bytes());b[8]^=1;p.write_bytes(b);v=verify_shard(bad,pub);check('Changed packet rejected by native kernel',v['status']=='FAIL');shutil.rmtree(bad)
 wrong,_=hybrid1_keygen();wrongpath=out/'wrong.pub';wrongpath.write_bytes(wrong);v=verify_shard(out/'successor',wrongpath);check('Wrong independent trust key rejected',v['status']=='FAIL');wrongpath.unlink()
 receipt={'status':'PASS','schema':'civil-continuity/native-witness@1','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'summary':'Actual Genesis origin and successor verified in separate processes. Two delivery obligations, four field-verification obligations and the rejected over-allocation remain visible.','origin_id':origin,'successor_id':successor,'fixture_key_sha256':hashlib.sha256(public).hexdigest(),'checks':results,'consumer':d,'key_class':'Disposable test identity. Private half never written and deleted before consumer runs. Not institutional authority.','scope':'Authored synthetic inputs and public source references; no physical deliveries, radio operation or municipal acceptance.'}
 # Public receipt excludes local file-system coordinates from the kernel diagnostics.
 (out/'NATIVE-WITNESS.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({'status':'PASS','checks':len(results),'origin_id':origin,'successor_id':successor}))
if __name__=='__main__':main()
