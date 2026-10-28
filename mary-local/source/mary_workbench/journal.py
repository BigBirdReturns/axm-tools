"""Seal completed MARY occurrences and exact outputs through Genesis.
Sealing records what the software produced; it does not certify prose as world truth.
"""
from __future__ import annotations
import json,os,shutil,uuid
from pathlib import Path
from .common import BoundaryError,atomic_bytes,atomic_json,canonical,contained,hash_file,now,private_dir,read_json,sha

def seal_work(root:Path,directory:Path,state:dict)->dict:
    from axm_build.common import normalize_source_text
    from axm_build.compiler_generic import CompilerConfig,compile_generic_shard
    from axm_verify.logic import verify_shard
    from blake3 import blake3
    from mary.ledger import verify_ledger
    from .axm import initialize_keys
    initialize_keys(root);ledger=directory/'outcomes.jsonl';verify_ledger(ledger);ledger_sha=hash_file(ledger)
    prior=read_json(directory/'journal-receipt.json')
    if prior and prior['ledger_sha256']==ledger_sha:
        if verify_shard(directory/prior['directory'],root/'keys/publisher.pub').get('status')!='PASS':raise BoundaryError('Retained work journal failed independent verification.')
        return prior
    stage=private_dir(directory/('.journal-'+uuid.uuid4().hex));scratch=private_dir(root/'runtime'/('journal-'+uuid.uuid4().hex))
    try:
        lines=[];candidates=[]
        for i,line in enumerate(ledger.read_text(encoding='utf-8').splitlines()):
            quote=normalize_source_text(f'Occurrence {i:06d}: '+line).strip()
            lines.append(quote+'\n');candidates.append({'subject':'MARY work '+state['id'],'predicate':'records_occurrence','object':quote,'object_type':'literal:string','evidence':quote,'tier':0})
        text=''.join(lines);atomic_bytes(scratch/'source.txt',text.encode());atomic_bytes(scratch/'candidates.jsonl',b''.join(canonical(x)+b'\n' for x in candidates))
        extras=[('outcomes.jsonl',ledger),('request.json',directory/'request.json'),('plan.json',directory/'plan.json')]
        extras=[x for x in extras if x[1].is_file()]
        total=0
        for artifact in state['artifacts']:
            p=contained(directory/'artifacts',artifact['name']);total+=p.stat().st_size
            if total>32*1024**2 or hash_file(p)!=artifact['sha256']:raise BoundaryError('Work artifacts exceed journal bound or differ from their accepted bytes.')
            extras.append(('artifacts/'+artifact['name'],p))
        manifest={'evidence_class':'agent_record','scope':'exact task request, observed execution occurrences and returned artifacts','semantic_boundary':'Output preservation and tool checks do not make generated interpretation independently verified truth.','request_id':state['id'],'ledger_sha256':ledger_sha,'artifacts':state['artifacts']}
        atomic_json(scratch/'work-manifest.json',manifest);extras.append(('work-manifest.json',scratch/'work-manifest.json'))
        cfg=CompilerConfig(source_path=scratch/'source.txt',candidates_path=scratch/'candidates.jsonl',out_dir=stage,private_key=(root/'keys/publisher.secret').read_bytes(),publisher_id='@mary-local-owner',publisher_name='Local workspace owner',namespace='mary/work-journal',created_at=now(),title='MARY work '+state['id'],license_spdx='LicenseRef-Private-Work',extra_content=tuple(extras),supersedes=(prior['shard_id'],) if prior else ())
        if not compile_generic_shard(cfg):raise BoundaryError('Genesis rejected the work journal.')
        if verify_shard(stage,root/'keys/publisher.pub').get('status')!='PASS':raise BoundaryError('Completed-work journal did not pass independent verification.')
        sid='sh1_'+blake3((stage/'manifest.json').read_bytes()).hexdigest();target=directory/('journal-'+sid)
        os.replace(stage,target)
        result={'shard_id':sid,'directory':target.name,'ledger_sha256':ledger_sha,'evidence_class':'agent_record','sealed_at':now()};atomic_json(directory/'journal-receipt.json',result);return result
    finally:
        shutil.rmtree(scratch,ignore_errors=True)
        if stage.exists():shutil.rmtree(stage,ignore_errors=True)
