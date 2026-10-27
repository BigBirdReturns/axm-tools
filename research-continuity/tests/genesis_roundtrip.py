#!/usr/bin/env python3
"""Exercise the real Genesis kernel and a fresh consumer, including negative cases.
Requires an explicitly installed axm-genesis. Creates a throwaway fixture identity
in memory; only its public half leaves this process. Never uses an estate key.
"""
from __future__ import annotations
import argparse,datetime as dt,hashlib,importlib.metadata,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import genesis_judgment as G

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);args=p.parse_args();out=args.out.resolve()
 if out.exists():raise ValueError('Choose a new output directory; previous evidence stays intact.')
 out.mkdir(parents=True);env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
 fixture=subprocess.run(['node',str(ROOT/'scripts/make_judgment_packets.cjs'),str(out/'packets')],capture_output=True,text=True,env=env,timeout=90)
 (out/'packet-authoring.log').write_text(fixture.stdout+fixture.stderr);fixture.check_returncode()
 from axm_build.sign import hybrid1_keygen
 from axm_verify.logic import verify_shard
 from axm_verify.crypto import derive_shard_id
 pub,secret=hybrid1_keygen();public=out/'fixture-publisher.pub';public.write_bytes(pub)
 origin=out/'origin';successor=out/'successor'
 sid=G.seal(out/'packets/origin.json',origin,secret,'@retained-judgment-fixture','Disposable demonstration identity','2026-10-27T17:00:00Z')
 nxt=G.seal(out/'packets/successor.json',successor,secret,'@retained-judgment-fixture','Disposable demonstration identity','2026-10-27T17:01:00Z',(sid,))
 del secret
 checks=[];receipts={}
 def check(name,passed,details=None):
  checks.append({'name':name,'pass':bool(passed),'details':details});print(name+': '+('PASS' if passed else 'FAIL'),flush=True)
  if not passed:raise AssertionError(name)
 def cold(name,shard,at,extra=(),want=True):
  cmd=[sys.executable,'-B',str(ROOT/'scripts/genesis_judgment.py'),'consume',str(shard),'--trusted-key',str(public),'--as-of',at,*extra]
  r=subprocess.run(cmd,cwd=out,capture_output=True,text=True,env=env,timeout=90)
  (out/(name+'.log')).write_text(r.stdout+r.stderr)
  if want:r.check_returncode();receipts[name]=json.loads(r.stdout);return receipts[name]
  return r
 first=cold('origin-consumer',origin,'2026-10-27T09:00:00Z',('--expected-id',sid))
 check('Origin sealed by actual hybrid Genesis and cold-consumed',first['kernel']['status']=='PASS' and first['judgment']['current']['open_obligations']==2)
 second=cold('successor-consumer',successor,'2026-10-27T15:00:00Z',('--expected-id',nxt,'--predecessor',str(origin)))
 check('Successor has native amendment lineage and exact preserved event prefix',second['predecessor']['status']=='PRESERVED_PREFIX')
 a=second['judgment']['current'];check('Inspection discharged; restoration still owed',a['open_obligations']==1 and any(x['state']=='DISCHARGED' for x in a['obligations']) and a['status']=='APPLICABLE')
 expired=cold('expired-consumer',successor,'2026-10-30T10:00:00Z')
 check('Intact signed artifact does not renew expired permission',expired['kernel']['status']=='PASS' and expired['judgment']['current']['status']=='EXPIRED')
 mismatch=cold('wrong-identity',origin,'2026-10-27T09:00:00Z',('--expected-id','sh1_'+'0'*64),False)
 check('Wrong expected identity refused',mismatch.returncode!=0 and 'identity differs' in mismatch.stderr)
 otherpub,othersecret=hybrid1_keygen();del othersecret;wrong=out/'wrong.pub';wrong.write_bytes(otherpub)
 r=verify_shard(origin,wrong);check('Wrong supplied publisher key rejected',r['status']=='FAIL',r);wrong.unlink()
 damaged=out/'tampered';shutil.copytree(origin,damaged);q=damaged/'content/judgment-packet.json';raw=bytearray(q.read_bytes());raw[5]^=1;q.write_bytes(raw)
 r=verify_shard(damaged,public);check('Changed retained packet bytes rejected by native Merkle verification',r['status']=='FAIL' and any(e['code']=='E_MERKLE_MISMATCH' for e in r['errors']),r);shutil.rmtree(damaged)
 missing=out/'missing';shutil.copytree(origin,missing);(missing/'content/continuation.json').unlink();r=verify_shard(missing,public);check('Missing retained basis refused',r['status']!='PASS',r);shutil.rmtree(missing)
 badprior=cold('wrong-predecessor',origin,'2026-10-27T09:00:00Z',('--predecessor',str(successor)),False)
 check('Unrelated/reversed predecessor refused',badprior.returncode!=0 and 'does not name' in badprior.stderr)
 report={'schema':'research-continuity/genesis-witness@1','status':'PASS','at':dt.datetime.now(dt.timezone.utc).isoformat(),'kernel_version':importlib.metadata.version('axm-genesis'),'kernel_source_reference':G.KERNEL_COMMIT,'consumer_sources':G.fingerprint(),'origin_id':sid,'successor_id':nxt,'publisher_key_sha256':hashlib.sha256(pub).hexdigest(),'publisher_key_class':'Disposable fixture; private half never written, deleted before cold consumers. No institutional authority.','checks':checks,'receipts':receipts,'scope':'Actual kernel compilation, hybrid signature verification and separate-process application replay. Authored synthetic operational case, not a physical inspection or authenticated grant.','network_required_by_consumer':False,'private_material_included':False}
 (out/'GENESIS-WITNESS.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({'status':'PASS','checks':len(checks),'origin_id':sid,'successor_id':nxt,'out':str(out)}))
if __name__=='__main__':main()
