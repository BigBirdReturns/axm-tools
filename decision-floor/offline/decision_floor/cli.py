"""Offline CLI: run, watch, search, verify, investigate, status."""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback
from .core import make_db,load_rules,ingest_folder,reconcile,search,verify,iso_now,rows,sync_investigations
from .report import render


def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def execute(args):
    input_dir=Path(args.input).resolve();workspace=Path(args.workspace).resolve();out=Path(args.out).resolve()
    if workspace==input_dir or input_dir in workspace.parents:raise ValueError('Workspace must be outside the import directory to avoid self-ingestion')
    if out==input_dir or input_dir in out.parents:raise ValueError('Output must be outside the input directory')
    rules=load_rules(Path(args.config).resolve())
    db=make_db(workspace)
    info=ingest_folder(db,input_dir,rules,workspace)
    rep=reconcile(db,args.as_of)
    rep['last_run']=info
    # Do not embed sensitive host filesystem paths into a shareable report.
    if args.as_of is None:
        history=sync_investigations(db,rep)
    else:
        # Replaying an earlier as-of date must never close today's work items.
        history={'items':rows(db,'SELECT * FROM investigation_items ORDER BY first_seen,code'),
                 'transitions':rows(db,'SELECT * FROM investigation_transitions ORDER BY happened_at,rowid')}
    rep['finding_history_count']=len(history['transitions'])
    write_json(out/'investigation_history.json',history)
    write_json(out/'decision_floor_report.json',rep)
    write_json(out/'open_questions.json',[{'case_key':c['case_key'],**q} for c in rep['cases'] for q in c['questions']])
    render(rep,out/'index.html')
    quality=verify(db,workspace)
    write_json(out/'verification.json',quality)
    result={'processed':info,'case_count':len(rep['cases']),'questions':sum(len(c['questions']) for c in rep['cases']),
            'verification':quality,'report':str(out/'index.html'),'machine_report':str(out/'decision_floor_report.json')}
    db.close()
    return result


def main():
    p=argparse.ArgumentParser(prog='decision_floor',description='Local-only decision-to-floor evidence investigator')
    sp=p.add_subparsers(dest='op',required=True)
    for name in ('run','watch'):
        sub=sp.add_parser(name,help='Ingest files and recompute the local evidence report')
        sub.add_argument('--input',required=True,help='Directory containing authorized local exports')
        sub.add_argument('--config',required=True,help='Local declarative source mapping JSON')
        sub.add_argument('--workspace',required=True,help='Private evidence vault and SQLite database')
        sub.add_argument('--out',required=True,help='Standalone HTML and machine-readable findings')
        sub.add_argument('--as-of',default=None,help='ISO-8601 timestamp for historical replay (default current UTC)')
        if name=='watch':
            sub.add_argument('--interval',type=float,default=60.0,help='Seconds between scans')
            sub.add_argument('--cycles',type=int,default=0,help='Zero means until stopped; finite for acceptance tests')
    sub=sp.add_parser('search',help='Local full-text search, with source SHA-256 and file locator')
    sub.add_argument('--workspace',required=True);sub.add_argument('--query',required=True);sub.add_argument('--limit',type=int,default=20)
    sub=sp.add_parser('verify',help='Re-hash original evidence bytes and check linkage')
    sub.add_argument('--workspace',required=True)
    sub=sp.add_parser('status',help='Local evidence index and extraction issue counts')
    sub.add_argument('--workspace',required=True)
    sub=sp.add_parser('history',help='Preserved investigation state transitions including closed findings')
    sub.add_argument('--workspace',required=True)
    a=p.parse_args()
    if a.op=='run':
        result=execute(a);print(json.dumps(result,indent=2));sys.exit(0 if result['verification']['status']=='PASS' else 2)
    if a.op=='watch':
        if a.interval<0.1: p.error('--interval must be at least 0.1')
        if a.cycles<0:p.error('--cycles cannot be negative')
        number=0
        while True:
            number+=1
            try:
                result=execute(a)
                print(json.dumps({'cycle':number,'at':iso_now(),**result}),flush=True)
            except Exception as exc:
                print(json.dumps({'cycle':number,'at':iso_now(),'error':f'{type(exc).__name__}: {exc}'}),file=sys.stderr,flush=True)
            if a.cycles and number>=a.cycles:break
            try:time.sleep(a.interval)
            except KeyboardInterrupt:break
        return
    db=make_db(Path(a.workspace).resolve())
    if a.op=='search':output=search(db,a.query,max(1,min(a.limit,100)))
    elif a.op=='verify':output=verify(db,Path(a.workspace).resolve())
    elif a.op=='status':output={table:db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('sources','source_paths','fragments','events','issues','runs','investigation_items','investigation_transitions','skipped_files')}
    elif a.op=='history':output={'items':rows(db,'SELECT * FROM investigation_items ORDER BY first_seen,code'),
                                  'transitions':rows(db,'SELECT * FROM investigation_transitions ORDER BY happened_at,rowid')}
    else:output={}
    print(json.dumps(output,indent=2,ensure_ascii=False));db.close()
    if a.op=='verify' and output['status']!='PASS':sys.exit(2)
