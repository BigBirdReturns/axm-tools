#!/usr/bin/env python3
"""One-pass Genesis sealing and cold consumption of native ResearchCore packets.

The optional installed axm-genesis kernel owns keys, signatures, manifests,
Merkle construction, identity and lineage. This adapter owns extraction only.
No source/extension mutation after compile. No key fallback. Imported source
code and recorded commands are never executed. A trusted public key is supplied
separately from the shard. Demo keys establish fixture integrity, not authority.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT=Path(__file__).resolve().parents[1]
KERNEL_COMMIT='5fcd472d6119afc0e9bb80ffc91f9ccc8adde705'
CODE=('research-core.js','continuity.js','measurements.js','judgment.js')

def cold(packet: Path, as_of: str|None=None) -> dict:
    cmd=['node',str(ROOT/'scripts/judgment_packet.cjs'),str(packet)]
    if as_of:cmd.append(as_of)
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
    if p.returncode:raise ValueError('Native judgment replay refused: '+p.stderr[-1500:])
    return json.loads(p.stdout)

def fingerprint() -> dict:
    paths=['source/'+name for name in CODE]+['scripts/genesis_judgment.py','scripts/judgment_packet.cjs']
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}

def seal(packet: Path, out: Path, secret: bytes, publisher_id: str, publisher_name: str,
         created_at: str, predecessors: tuple[str,...]=(), lineage_action='amend') -> str:
    from axm_build.common import normalize_source_text
    from axm_build.compiler_generic import CompilerConfig, compile_generic_shard
    from axm_verify.crypto import derive_shard_id
    if out.exists():raise ValueError('Refusing to replace a retained shard; choose a fresh output directory.')
    verdict=cold(packet)
    obj=json.loads(packet.read_text(encoding='utf-8'))
    events=obj['workspace']['events']
    records=[];candidates=[]
    # Each statement quotes one complete event and remains traceable to exact
    # source bytes. Exact original packet bytes are separately Merkle-covered.
    for event in events:
        if event['type'] not in ('record','review','freeze'):raise ValueError('Unknown native event kind.')
        line='Event '+str(event['seq'])+' '+json.dumps(event,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        records.append(line)
        candidates.append({'subject':'event-'+str(event['seq']),'predicate':'records','object':event['type'],'object_type':'literal:string','tier':0,'evidence':normalize_source_text(line).strip()})
    with tempfile.TemporaryDirectory(prefix='judgment-extract-') as tmp:
        tmp=Path(tmp);source=tmp/'source.txt';source.write_text('\n'.join(records)+'\n',encoding='utf-8')
        raw=tmp/'candidates.jsonl';raw.write_text('\n'.join(json.dumps(c,ensure_ascii=False) for c in candidates)+'\n',encoding='utf-8')
        contract=tmp/'consumer.json';contract.write_text(json.dumps({'schema':'research-continuity/judgment-consumer@1','kernel_version':importlib.metadata.version('axm-genesis'),'kernel_build_reference':KERNEL_COMMIT,'application_contract':'research-continuity/retained-judgment@1','source_sha256':fingerprint(),'execution':'Use the installed known consumer; never execute code from this shard.','authority':'Signatures prove artifact integrity under a supplied key, not the truth of evidence or legitimacy of named role holders.'},indent=2),encoding='utf-8')
        snapshot=tmp/'continuation.json';snapshot.write_text(json.dumps(verdict,indent=2),encoding='utf-8')
        cfg=CompilerConfig(source_path=source,candidates_path=raw,out_dir=out,private_key=secret,publisher_id=publisher_id,publisher_name=publisher_name,namespace='research/retained-judgment',created_at=created_at,title='Retained judgment: '+obj['workspace']['label'],license_spdx='MIT',extra_content=(('judgment-packet.json',packet),('consumer.json',contract),('continuation.json',snapshot)),supersedes=predecessors,lineage_action=lineage_action,lineage_note='Complete native judgment history, unresolved obligations and explicit successor; predecessor remains intact.' if predecessors else '')
        if not compile_generic_shard(cfg):raise RuntimeError('Genesis compiler rejected its own output.')
    return derive_shard_id((out/'manifest.json').read_bytes())

def consume(shard: Path, trusted_key: Path, as_of: str|None=None, expected_id: str|None=None, prior: Path|None=None) -> dict:
    from axm_verify.logic import verify_shard
    from axm_verify.crypto import derive_shard_id
    # Reject links before opening private/unexpected files, then delegate integrity.
    if any(p.is_symlink() for p in shard.rglob('*')):raise ValueError('Symbolic links are not admitted in a consumer shard.')
    checked=verify_shard(shard,trusted_key)
    if checked['status']!='PASS':raise ValueError('Genesis integrity gate refused: '+json.dumps(checked))
    if checked['profiles_unchecked']:raise ValueError('Unchecked profile claims require their named verifier.')
    sid=derive_shard_id((shard/'manifest.json').read_bytes())
    if expected_id and sid!=expected_id:raise ValueError('Artifact identity differs from the independently retained expected identity.')
    manifest=json.loads((shard/'manifest.json').read_text())
    predecessor='NOT_SUPPLIED'
    if prior is not None:
        if any(p.is_symlink() for p in prior.rglob('*')):raise ValueError('Symbolic links are not admitted in the predecessor.')
        pcheck=verify_shard(prior,trusted_key)
        if pcheck['status']!='PASS':raise ValueError('Predecessor integrity failed.')
        pid=derive_shard_id((prior/'manifest.json').read_bytes())
        if pid not in manifest.get('supersedes',[]):raise ValueError('Successor does not name the supplied predecessor.')
        old=json.loads((prior/'content/judgment-packet.json').read_text())['workspace']['events']
        new=json.loads((shard/'content/judgment-packet.json').read_text())['workspace']['events']
        if new[:len(old)]!=old:raise ValueError('Amendment omitted or rewrote predecessor history.')
        predecessor={'status':'PRESERVED_PREFIX','shard_id':pid,'events':len(old)}
    contract=json.loads((shard/'content/consumer.json').read_text())
    if contract.get('source_sha256')!=fingerprint():raise ValueError('Installed domain consumer differs from the sealed consumer identity.')
    report=cold(shard/'content/judgment-packet.json',as_of)
    return {'schema':'research-continuity/genesis-consumption@1','shard_id':sid,'kernel':checked,'consumer_identity':'MATCH','judgment':report,'predecessor':predecessor,'trusted_key_source':'explicit caller-supplied file; caller owns trust decision','origin_session_required':False,'external_action_authorized':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='op',required=True)
    s=sub.add_parser('seal');s.add_argument('packet',type=Path);s.add_argument('out',type=Path);s.add_argument('--private-key',type=Path,required=True);s.add_argument('--publisher-id',required=True);s.add_argument('--publisher-name',required=True);s.add_argument('--created-at',required=True);s.add_argument('--supersedes',action='append',default=[])
    v=sub.add_parser('consume');v.add_argument('shard',type=Path);v.add_argument('--trusted-key',required=True,type=Path);v.add_argument('--as-of');v.add_argument('--expected-id');v.add_argument('--predecessor',type=Path)
    args=p.parse_args()
    if args.op=='seal':
        sid=seal(args.packet.resolve(),args.out.resolve(),args.private_key.read_bytes(),args.publisher_id,args.publisher_name,args.created_at,tuple(args.supersedes));print(json.dumps({'status':'SEALED','shard_id':sid,'independent_verification':'Run consume with an explicitly supplied trusted public key.'}))
    else: print(json.dumps(consume(args.shard.resolve(),args.trusted_key.resolve(),args.as_of,args.expected_id,args.predecessor.resolve() if args.predecessor else None),indent=2))
if __name__=='__main__':
    try:main()
    except Exception as exc:print('REFUSED: '+str(exc),file=sys.stderr);raise SystemExit(1)
