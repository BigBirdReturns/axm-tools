#!/usr/bin/env python3
"""Compose the existing Genesis adapter with the known municipal consumer.
No key generation for user operations, no crypto implementation, no network.
"""
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'scripts'))
import genesis_judgment as G

def checked(packet):
 p=subprocess.run(['node',str(HERE/'packet.cjs'),str(packet)],capture_output=True,text=True,timeout=90)
 if p.returncode:raise ValueError(p.stderr[-1200:])
 return json.loads(p.stdout)
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True)
 a=s.add_parser('seal');a.add_argument('packet',type=Path);a.add_argument('out',type=Path);a.add_argument('--private-key',type=Path,required=True);a.add_argument('--publisher-id',required=True);a.add_argument('--publisher-name',required=True);a.add_argument('--created-at',required=True);a.add_argument('--supersedes',action='append',default=[])
 a=s.add_parser('consume');a.add_argument('shard',type=Path);a.add_argument('--trusted-key',type=Path,required=True);a.add_argument('--predecessor',type=Path);a.add_argument('--expected-id');a.add_argument('--as-of')
 x=p.parse_args()
 if x.op=='seal':
  checked(x.packet);sid=G.seal(x.packet,x.out,x.private_key.read_bytes(),x.publisher_id,x.publisher_name,x.created_at,tuple(x.supersedes));print(json.dumps({'status':'SEALED','shard_id':sid}))
 else:
  kernel=G.consume(x.shard,x.trusted_key,x.as_of,x.expected_id,x.predecessor);domain=checked(x.shard/'content/judgment-packet.json');print(json.dumps({'status':'PASS','kernel':kernel['kernel'],'shard_id':kernel['shard_id'],'predecessor':kernel['predecessor'],'municipal':domain,'origin_session_required':False},indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:print('REFUSED: '+str(e),file=sys.stderr);raise SystemExit(1)
