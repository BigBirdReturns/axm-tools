"""Run the portable recipient test in fresh, network-denied Python processes."""
from __future__ import annotations
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
BOOTSTRAP = r'''
import json,os,runpy,socket,sys
sys.dont_write_bytecode=True
attempts=[]
def deny(*args,**kwargs):
    attempts.append('socket API invocation')
    raise RuntimeError('SCHISM recipient test denies network APIs')
socket.socket=deny
socket.create_connection=deny
socket.getaddrinfo=deny
sys.argv=sys.argv[1:]
try:
    runpy.run_path(sys.argv[0],run_name='__main__')
finally:
    with open(os.environ['SCHISM_NETWORK_LOG'],'w',encoding='utf-8') as f:
        json.dump({'attempts':len(attempts)},f)
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='New result directory outside this installation')
    parser.add_argument('--with-node', action='store_true', help='Also accept the Python result in the original JavaScript implementation')
    args = parser.parse_args()
    out = args.out.resolve() if args.out else Path(tempfile.mkdtemp(prefix='schism-recipient-'))
    if out.is_relative_to(ROOT):
        raise ValueError('Keep results outside the immutable source package')
    if args.out:
        out.mkdir(parents=True, exist_ok=False)
    expected_manifest = ROOT / 'release-manifest.json'
    verify = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/verify_release.py')], capture_output=True, text=True, encoding='utf-8', timeout=60)
    (out/'release-check.json').write_text(verify.stdout, encoding='utf-8')
    if verify.returncode:
        raise ValueError('Source package verification failed: '+verify.stdout.strip())
    register = json.loads((ROOT/'data/case-register.json').read_text(encoding='utf-8'))
    rows=[]
    for index, case in enumerate(register['required']):
        name=case['file']; log=out/f'network-{index}.json'; receipt=out/f'case-{index}.json'
        env={**os.environ,'SCHISM_NETWORK_LOG':str(log)}
        cmd=[sys.executable,'-B','-c',BOOTSTRAP,str(ROOT/'runtime/receiver.py'),'verify',str(ROOT/'data/cases'/name),'--receipt',str(receipt)]
        result=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
        accepted=result.returncode==0
        if accepted != case['accept']:
            raise ValueError(f'{name}: unexpected disposition: {result.stdout} {result.stderr}')
        reason=None
        if accepted:
            declared=json.loads(receipt.read_text(encoding='utf-8'))
            if declared.get('schema')!='schism-independent-receiver-execution/1' or declared.get('status')!='PASS':
                raise ValueError(name+': missing structured acceptance receipt')
            if declared['contract']['engine_sha256']!=register['contract_sha256'] or declared['executor']['javascript_executed'] is not False:
                raise ValueError(name+': acceptance uses a different executor or contract')
        else:
            try:declared=json.loads(result.stderr)
            except (ValueError,TypeError):raise ValueError(name+': crash or unstructured failure is not a qualified refusal')
            if result.returncode!=1 or result.stdout.strip() or receipt.exists() or declared.get('schema')!='schism-independent-receiver-execution/1' or declared.get('status')!='FAIL' or declared.get('error')!=case['error']:
                raise ValueError(name+': failure did not establish the expected semantic refusal: '+result.stderr)
            reason=declared['error']
        network=json.loads(log.read_text(encoding='utf-8'))
        if network['attempts']:
            raise ValueError('A recipient attempted networking')
        rows.append({'file':name,'expected':'ACCEPT' if case['accept'] else 'REFUSE','observed':'ACCEPT' if accepted else 'REFUSE','return_code':result.returncode,'reason':reason,'network_attempts':0})
    log=out/'network-resume.json'; resumed=out/'python-resumed.json'; receipt=out/'python-execution.json'
    command=[sys.executable,'-B','-c',BOOTSTRAP,str(ROOT/'runtime/receiver.py'),'resume',str(ROOT/'data/cases'/register['resume']['input']),'--out',str(resumed),'--receipt',str(receipt)]
    result=subprocess.run(command,cwd=out,env={**os.environ,'SCHISM_NETWORK_LOG':str(log)},capture_output=True,text=True,encoding='utf-8',timeout=120)
    if result.returncode:
        raise ValueError('Python continuation failed: '+result.stdout+' '+result.stderr)
    packet=json.loads(resumed.read_text(encoding='utf-8'))
    if packet['sha256']!=register['resume']['expected_sha256']:
        raise ValueError('Python result differs from the fixed JavaScript reference result')
    if json.loads(log.read_text(encoding='utf-8'))['attempts']:
        raise ValueError('Continuation attempted networking')
    roundtrip={'status':'NOT_RUN','reason':'Select --with-node to invoke the original JavaScript receiver'}
    if args.with_node:
        executable=shutil.which('node')
        if not executable:
            raise ValueError('Node is required for the selected cross-language round trip')
        log=out/'network-node.json'
        result=subprocess.run([executable,'--require',str(ROOT/'scripts/network-deny.cjs'),str(ROOT/'scripts/check-roundtrip.cjs'),str(resumed)],
                              cwd=out,env={**os.environ,'SCHISM_NETWORK_LOG':str(log)},capture_output=True,text=True,encoding='utf-8',timeout=120)
        if result.returncode:
            raise ValueError('Original JavaScript receiver refused Python continuation: '+result.stdout+' '+result.stderr)
        roundtrip=json.loads(result.stdout)
        if json.loads(log.read_text(encoding='utf-8'))['attempts']:
            raise ValueError('JavaScript receiver attempted networking')
        (out/'roundtrip.json').write_text(json.dumps(roundtrip,indent=2)+'\n',encoding='utf-8')
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    report={'schema':'schism-recipient-qualification/2','status':'PASS','observed_at':datetime.now(timezone.utc).isoformat(),
            'environment':{'system':platform.system(),'architecture':platform.machine(),'python':platform.python_version()},
            'contract_sha256':register['contract_sha256'],'receiver_sha256':digest(ROOT/'runtime/receiver.py'),
            'case_register_sha256':digest(ROOT/'data/case-register.json'),'cases':rows,'case_count':len(rows),
            'network_policy':'Ordinary Python socket APIs denied; Node HTTP/TLS/socket/fetch denied when selected',
            'network_attempts':0,'origin_service_used':False,'fresh_process_per_case':True,
            'continued_packet_sha256':packet['sha256'],'roundtrip':roundtrip,
            'history':{'sources':len(packet['sources']),'decisions':len(packet['decisions']),'reviews':len(packet['reviews']),
                       'old_net_cents':packet['decisions'][0]['result']['plan']['net_cents'],'new_net_cents':packet['decisions'][-1]['result']['plan']['net_cents']},
            'scope':'Synthetic industrial record continuity and independent computation; no device operation or authenticated review authority.'}
    (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','receipt':str(out/'qualification.json'),'cases':len(rows),'roundtrip':roundtrip['status'],'continued_packet_sha256':packet['sha256']},indent=2))
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'FAIL','reason':str(error)}),file=sys.stderr)
        raise SystemExit(1)
