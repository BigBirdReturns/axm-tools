#!/usr/bin/env python3
"""One GPU / same checkpoint: bounded, offline vLLM batch experiment.
Python standard library only. No installs, image pulls, weight downloads or cloud calls.
Inspect source and README before allowing a model load. Linux Docker + NVIDIA required.
"""
from __future__ import annotations
import argparse, csv, hashlib, html, json, math, os, pathlib, re, shutil, struct
import subprocess, sys, time, uuid

GIB = 1024 ** 3
VERSION = 'axm/mimo-one-gpu@1.0.0'
MODEL_IDS = ('XiaomiMiMo/MiMo-V2.6-Pro-RL', 'XiaomiMiMo/MiMo-V2.6-Flash-RL')
DTYPES = {'F64':8,'F32':4,'F16':2,'BF16':2,'I64':8,'I32':4,'I16':2,'I8':1,
          'U8':1,'BOOL':1,'F8_E4M3':1,'F8_E5M2':1,'F8_E4M3FN':1,'U32':4,'U64':8}

class Refusal(Exception):
    pass

def require(ok, reason):
    if not ok: raise Refusal(reason)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def json_read(path, limit=32*1024*1024):
    p = pathlib.Path(path)
    require(p.stat().st_size <= limit, f'Metadata exceeds {limit} bytes: {p.name}')
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            require(k not in obj, f'Duplicate JSON key: {k}')
            obj[k] = v
        return obj
    return json.loads(p.read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(Refusal('Nonfinite JSON')))

def save(path, value):
    p = pathlib.Path(path)
    require(not p.exists(), f'Output already exists: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')
    p.chmod(0o600)

def run(args, timeout=30, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                            stdin=subprocess.DEVNULL, check=False)
    if check: require(result.returncode == 0, 'Command refused/failed: '+args[0]+': '+result.stderr[-1200:])
    return result

def mem_available():
    require(sys.platform.startswith('linux'), 'Native Linux or Linux WSL2 required; no Mac/Windows inference claim')
    d = {line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2 and line.split()[1].isdigit()}
    available = d['MemAvailable']; total = d['MemTotal']
    # Respect a containing cgroup rather than reporting inaccessible host RAM as available.
    cg = pathlib.Path('/sys/fs/cgroup')
    try:
        maximum = (cg/'memory.max').read_text().strip()
        if maximum != 'max':
            cap = int(maximum); used = int((cg/'memory.current').read_text())
            available = min(available, max(0, cap-used)); total = min(total, cap)
    except (OSError, ValueError): pass
    return {'total_gib':total/GIB, 'available_gib':available/GIB}

def scan():
    require(shutil.which('nvidia-smi'), 'nvidia-smi unavailable: GPU NOT OBSERVED')
    q = run(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,driver_version','--format=csv,noheader,nounits'])
    gpus = []
    for row in csv.reader(q.stdout.splitlines(), skipinitialspace=True):
        require(len(row)==6, 'Unrecognized nvidia-smi GPU report')
        i, uid, name, total, used, driver = [x.strip() for x in row]
        require(re.fullmatch(r'GPU-[0-9a-fA-F-]+',uid), 'MIG/unknown GPU identity needs a separate adapter')
        gpus.append({'index':int(i),'uuid':uid,'name':name,'total_gib':float(total)/1024,
                     'used_gib':float(used)/1024,'driver':driver})
    cp = run(['nvidia-smi','--query-compute-apps=gpu_uuid','--format=csv,noheader'],check=False)
    require(cp.returncode == 0, 'Could not inspect existing GPU compute occupancy')
    busy = set(cp.stdout.split())
    for g in gpus: g['compute_busy'] = g['uuid'] in busy
    return {'schema':VERSION,'time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'ram':mem_available(),'gpus':gpus,'cpu_count':os.cpu_count(),
            'docker_available':bool(shutil.which('docker'))}

def fingerprint(p):
    p = pathlib.Path(p)
    st = p.stat()
    return {'size':st.st_size, 'mtime_ns':st.st_mtime_ns, 'resolved':str(p.resolve())}

def hash_file(path):
    before = fingerprint(path); h = hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(16*1024*1024),b''): h.update(block)
    require(fingerprint(path)==before, 'File changed during hashing')
    return h.hexdigest()

def safe_name(name):
    p = pathlib.PurePosixPath(name)
    require(isinstance(name,str) and name and not p.is_absolute() and '..' not in p.parts
            and '\\' not in name and ',' not in name and '\n' not in name, 'Unsafe artifact path')
    return p

def header(path):
    with open(path,'rb') as f:
        b=f.read(8); require(len(b)==8,'Truncated safetensors prefix')
        n=struct.unpack('<Q',b)[0]; require(2<=n<=32*1024*1024,'Unsafe safetensors header length')
        raw=f.read(n); require(len(raw)==n,'Truncated safetensors header')
    pairs=json.loads(raw, object_pairs_hook=lambda x:x)
    require(isinstance(pairs,list), 'Malformed safetensors header')
    tensors={}; spans=[]; total=0
    for name, value in pairs:
        if name=='__metadata__': continue
        require(name not in tensors,'Duplicate tensor name')
        d=dict(value); off=d['data_offsets']; shape=d['shape']; typ=d['dtype']
        require(typ in DTYPES, 'Unknown tensor dtype: '+str(typ))
        require(len(off)==2 and all(type(x) is int for x in off) and 0<=off[0]<=off[1], 'Invalid tensor offsets')
        require(isinstance(shape,list) and all(type(x) is int and x>=0 for x in shape),'Invalid tensor shape')
        size=math.prod(shape)*DTYPES[typ]
        require(size==off[1]-off[0], 'Tensor shape / bytes disagree')
        require(8+n+off[1]<=pathlib.Path(path).stat().st_size, 'Truncated tensor data')
        tensors[name]={'dtype':typ,'bytes':size}; spans.append(off); total+=size
    cursor=0
    for start,end in sorted(spans):
        require(start==cursor,'Overlapping tensor or hole in payload'); cursor=end
    require(8+n+cursor==pathlib.Path(path).stat().st_size,'Unaccounted safetensors bytes')
    return tensors,total,hashlib.sha256(raw).hexdigest()

def inspect_model(root):
    root=pathlib.Path(root).expanduser().resolve(); require(root.is_dir(),'Choose an existing local checkpoint directory')
    cfg=json_read(root/'config.json'); idx=json_read(root/'model.safetensors.index.json')
    mapping=idx.get('weight_map'); require(isinstance(mapping,dict) and mapping,'Missing complete weight index')
    shard_names=set(mapping.values()); require(len(shard_names)<=1024,'Shard budget exceeded')
    names={}; byte_count=0; files={}
    for name in sorted(shard_names):
        safe_name(name); p=root/name; require(p.is_file(),'Missing shard: '+name)
        ts, bs, hs=header(p); byte_count+=bs
        for key in ts:
            require(key not in names,'Tensor duplicated between shards'); names[key]=name
        files[name]={**fingerprint(p),'header_sha256':hs}
    require(names==mapping,'Weight-index names / locations do not match complete shard headers')
    stated=idx.get('metadata',{}).get('total_size')
    require(stated is None or stated==byte_count,'Index total_size differs from actual tensor payload')
    # Include auxiliary weights, model code, tokenizer and templates in custody/mounts too.
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '.cache' in p.relative_to(root).parts or '.git' in p.relative_to(root).parts: continue
        name=p.relative_to(root).as_posix(); safe_name(name)
        require(len(files)<4096,'Artifact file budget exceeded')
        if name not in files: files[name]=fingerprint(p)
        if p.stat().st_size<=32*1024*1024: files[name]['sha256']=hash_file(p)
    return {'root':str(root),'model_type':cfg.get('model_type'), 'architectures':cfg.get('architectures'),
            'quantization_config':cfg.get('quantization_config'), 'tensor_payload_gib':byte_count/GIB,
            'total_artifact_gib':sum(x['size'] for x in files.values())/GIB,
            'largest_file_gib':max(x['size'] for x in files.values())/GIB,
            'tensor_count':len(names),'shard_count':len(shard_names),'files':files,
            'config_sha256':hash_file(root/'config.json'),'index_sha256':hash_file(root/'model.safetensors.index.json'),
            'custody':'HEADER_AND_SMALL_FILE_IDENTITY_ONLY; full hashing required before execution'}

def validate_settings(s):
    require(s.get('schema')=='axm/one-gpu-settings@1','Unrecognized settings schema')
    require(s.get('model_id') in MODEL_IDS,'Choose Pro-RL or Flash-RL explicitly; no substitution')
    require(re.fullmatch('[0-9a-f]{40}',s.get('model_revision','')),'Exact model repository revision required (40 lowercase hex)')
    require(isinstance(s.get('model_path'),str) and s['model_path'],'Select local checkpoint path')
    require(isinstance(s.get('image'),str) and s['image'] and not s['image'].startswith('-'),'Select an existing local Docker image')
    limits={'gpu_index':(0,255),'context':(128,1048576),'prefill_chunk':(128,1048576),
            'offload_gib':(1,8192),'ram_limit_gib':(4,16384),'reserve_gib':(8,4096),
            'cpus':(1,512),'timeout_s':(60,86400),'max_requests':(1,100000)}
    for k,(lo,hi) in limits.items():
        require(type(s.get(k)) is int and lo<=s[k]<=hi, 'Invalid bounded setting '+k)
    require(s['prefill_chunk']<=s['context'],'Prefill chunk exceeds context')
    require(s['ram_limit_gib']>s['offload_gib']+8,'RAM cap must leave at least 8 GiB above offload budget')
    return s

def admission(s,hw,m):
    errors=[]; warnings=[]
    gpu=next((g for g in hw['gpus'] if g['index']==s['gpu_index']),None)
    if not gpu: return ['Selected GPU missing'],warnings
    if gpu['compute_busy'] or gpu['used_gib']>2: errors.append('Selected GPU is occupied. Do not stop its other jobs; choose an idle GPU.')
    if s['ram_limit_gib']+s['reserve_gib']>hw['ram']['available_gib']: errors.append('RAM cap plus reserved headroom exceeds currently available host/cgroup RAM.')
    if s['cpus']>max(1,hw['cpu_count']//2): errors.append('CPU cap exceeds half of observed logical CPUs.')
    if m['model_type']!='mimo_v2': errors.append('Selected checkpoint is not the inspected MiMo architecture.')
    gpu_budget=gpu['total_gib']*0.85
    if m['tensor_payload_gib']>gpu_budget+s['offload_gib']: errors.append('Even stored target tensor bytes exceed GPU budget plus CPU-offload budget.')
    if s['ram_limit_gib']<s['offload_gib']+m['largest_file_gib']+8: errors.append('RAM cap lacks the conservative largest-shard staging allowance plus 8 GiB.')
    quant=m.get('quantization_config') or {}
    if quant.get('store_dtype')=='mxfp4': warnings.append('MXFP4 storage under an FP8 runtime config: loaded representation and staging can exceed disk bytes. TP=1/load/offload support remains unqualified until the real canary.')
    warnings.append('Header fit is not native allocation fit or quality parity. CUDA kernels, context/KV, quantization expansion and temporary buffers remain runtime checks.')
    return errors,warnings

def make_plan(settings):
    s=validate_settings(settings); hw=scan(); m=inspect_model(s['model_path'])
    require(hw['docker_available'],'Docker is not available; nothing was installed')
    image=json.loads(run(['docker','image','inspect',s['image']]).stdout)[0]
    iid=image['Id']; require(re.fullmatch('sha256:[0-9a-f]{64}',iid),'Unpinnable local image')
    errors,warnings=admission(s,hw,m)
    p={'schema':VERSION,'settings':s,'hardware':hw,'checkpoint':m,'image_id':iid,
       'image_repo_digests':image.get('RepoDigests',[]),'state':'BLOCKED' if errors else 'CANDIDATE',
       'blockers':errors,'warnings':warnings,'native_model_canary':'NOT_RUN','benchmark_score':None,
       'source_revision_attribution':'operator-supplied; local byte identity is measured, upstream identity is not independently authenticated'}
    p['plan_sha256']=digest(p); return p

def validate_requests(path,s,kind):
    p=pathlib.Path(path); require(p.stat().st_size<=256*1024*1024,'Request file exceeds 256 MiB')
    rows=[]; ids=set()
    for line in p.read_text().splitlines():
        require(len(line)<=16*1024*1024,'Request line exceeds 16 MiB')
        x=json.loads(line); ident=x.get('custom_id'); b=x.get('body',{})
        require(isinstance(ident,str) and ident and ident not in ids,'Missing or duplicate request identity');ids.add(ident)
        require(x.get('method')=='POST' and x.get('url') in ['/v1/chat/completions','/v1/completions'],'Only frozen completion requests are supported by the offline runner')
        require(b.get('model')==s['model_id'],'Request model differs; payload is not silently rewritten')
        require(b.get('stream',False) is False,'Streaming belongs to a live native harness')
        require('max_tokens' in b or 'max_completion_tokens' in b,'Explicit original output-token budget required')
        for k in ['max_tokens','max_completion_tokens']:
            if k in b: require(type(b[k]) is int and 1<=b[k]<=s['context'],'Output budget invalid/exceeds declared context')
        require(b.get('n',1)==1,'This single-sequence lane requires n=1; preserve other protocols in their native harness')
        canonical(x); rows.append(x)
    require(0<len(rows)<=s['max_requests'],'Request count outside declared budget')
    if kind=='canary': require(len(rows)==1,'Canary is exactly one request, not a benchmark score')
    return rows

def response_summary(rows,request_ids):
    found={}; errors=[]; lengths=0
    for row in rows:
        ident=row.get('custom_id')
        require(ident in request_ids and ident not in found,'Duplicate/unexpected response identity')
        found[ident]=row
        response=row.get('response') or {}; body=response.get('body') or {}
        choices=body.get('choices') or []
        has_generation=(body.get('usage') or {}).get('completion_tokens',0)>0 or any(
            c.get('text') or (c.get('message') or {}).get('content') or (c.get('message') or {}).get('reasoning') or
            (c.get('message') or {}).get('reasoning_content') or (c.get('message') or {}).get('tool_calls') for c in choices)
        if row.get('error') or response.get('status_code')!=200 or not choices or not has_generation:
            errors.append(ident)
        for choice in choices:
            if choice.get('finish_reason')=='length': lengths+=1
    missing=sorted(set(request_ids)-set(found))
    return {'expected':len(request_ids),'received':len(found),'missing':missing,'error_ids':errors,
            'length_limited_choices':lengths,'transport_complete':not missing and not errors,
            'quality_score':None,'native_scorer':'NOT_RUN','official_comparability':'NOT_ESTABLISHED'}

def validate_protocol(path, request_file, settings):
    require(path, 'A benchmark run requires --protocol; a canary is not an evaluation')
    value = json_read(path)
    require(value.get('schema') == 'axm/frozen-benchmark-requests@1', 'Unknown benchmark protocol')
    for field in ['benchmark_id', 'harness_revision', 'dataset_revision', 'scorer_revision']:
        require(isinstance(value.get(field), str) and len(value[field].strip()) > 2, 'Pin '+field)
    require(value.get('interaction') == 'independent_requests', 'Interactive benchmarks need their native live harness; batch replay cannot replace it')
    require(value.get('timing_policy') == 'offline-no-per-request-deadline', 'Per-turn deadline benchmarks require native timing enforcement')
    require(value.get('context') == settings['context'], 'Context differs from the frozen protocol')
    require(value.get('requests_sha256') == hash_file(request_file), 'Requests differ from the frozen benchmark file')
    return value

def execute(plan_file, requests, out, kind, approved, protocol=None):
    require(approved,'Execution requires --approve-load; plan/inspect are the default safe path')
    p=json_read(plan_file); sig=p.pop('plan_sha256',None); require(sig==digest(p),'Plan was modified; regenerate it')
    s=validate_settings(p['settings']); require(p['state']=='CANDIDATE','Blocked plan cannot run')
    hw=scan(); errors,_=admission(s,hw,p['checkpoint']);require(not errors,'; '.join(errors))
    expected=next(g for g in p['hardware']['gpus'] if g['index']==s['gpu_index'])
    chosen=next(g for g in hw['gpus'] if g['index']==s['gpu_index'])
    require(chosen['uuid']==expected['uuid'],'GPU ordinal changed; regenerate the plan')
    rows=validate_requests(requests,s,kind) if kind!='serve' else []; frozen=validate_protocol(protocol,requests,s) if kind=='benchmark' else None
    folder=pathlib.Path(out).resolve()
    require(not folder.exists(),'Use a new run directory; failed runs stay preserved')
    folder.mkdir(mode=0o700,parents=True); started=time.monotonic(); name='axm-one-gpu-'+uuid.uuid4().hex[:12]
    receipt={'schema':VERSION,'plan_sha256':sig,'kind':kind,'status':'PREPARING','runtime_model_calls':None,
             'target_model':s['model_id'],'model_revision':s['model_revision'],'image_id':p['image_id'],
             'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gpu_name':chosen['name'],
             'visible_gpu_count':None,'tensor_parallel':1,'pipeline_parallel':1,'max_sequences':1,
             'request_sha256':hash_file(requests) if requests else None,'request_count':len(rows),'quality_score':None,
             'native_scorer':'NOT_RUN','benchmark_protocol':frozen,'model_source_authentication':p['source_revision_attribution'],
             'ram_cap_gib':s['ram_limit_gib'],'cpu_offload_gib':s['offload_gib'],
             'disk_backed_weight_streaming':'NOT_IMPLEMENTED; this lane uses host-RAM offload',
             'private_logs':'Model prompts, outputs and local paths remain in this private run folder.'}
    launched=False; bridge=None
    try:
        gpuargs=['--gpus','device='+chosen['uuid']]
        # Separate tiny probe: imports the existing image runtime, loads no checkpoint.
        probe_code="import json,torch,importlib.metadata as m; print(json.dumps({'cuda_count':torch.cuda.device_count(),'vllm':m.version('vllm'),'torch':torch.__version__})); assert torch.cuda.device_count()==1"
        probe=run(['docker','run','--rm','--pull=never','--network','none',*gpuargs,
                   '--entrypoint','python3',p['image_id'],'-c',probe_code],timeout=120)
        (folder/'runtime-probe.txt').write_text(probe.stdout)
        observed_probe=json.loads(next(line for line in reversed(probe.stdout.splitlines()) if line.startswith('{')))
        require(type(observed_probe.get('cuda_count')) is int and observed_probe['cuda_count']==1,'Runtime sees a different GPU denominator')
        receipt['runtime_probe']=observed_probe;receipt['visible_gpu_count']=1
        help_result=run(['docker','run','--rm','--pull=never','--network','none','--entrypoint','vllm',p['image_id'],'run-batch','--help=all'],timeout=120,check=False)
        (folder/'runtime-help.txt').write_text(help_result.stdout+help_result.stderr)
        require(help_result.returncode==0 and '--cpu-offload-gb' in help_result.stdout,'Existing image does not expose the inspected run-batch/offload CLI; preserve failure, do not auto-install')
        root=pathlib.Path(p['checkpoint']['root']); custody={}; mounts=[]
        for rel, old in p['checkpoint']['files'].items():
            safe_name(rel); f=root/rel
            require(fingerprint(f)=={k:old[k] for k in ['size','mtime_ns','resolved']},'Checkpoint changed after planning: '+rel)
            custody[rel]=hash_file(f)
            require(',' not in str(f.resolve()) and '\n' not in str(f.resolve()),'Docker mount path contains delimiter')
            mounts+=['--mount',f'type=bind,src={f.resolve()},dst=/model/{rel},readonly']
        receipt['checkpoint_content_root']=digest(custody)
        save(folder/'custody.json',custody)
        if requests:
            shutil.copyfile(requests,folder/'requests.jsonl');os.chmod(folder/'requests.jsonl',0o600)
        # Recheck headroom and source stats after the potentially lengthy full-content hash.
        now=scan(); errors,_=admission(s,now,p['checkpoint']);require(not errors,'; '.join(errors))
        for rel,old in p['checkpoint']['files'].items():
            require(fingerprint(root/rel)=={k:old[k] for k in ['size','mtime_ns','resolved']},'Checkpoint changed before launch')
        docker=['docker','run','--detach','--pull=never','--name',name,'--network','none',*gpuargs,
                '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','2048',
                '--log-opt','max-size=10m','--log-opt','max-file=2',
                '--memory',str(s['ram_limit_gib'])+'g','--memory-swap',str(s['ram_limit_gib'])+'g',
                '--cpus',str(s['cpus']),'--shm-size','1g',
                '--mount',f'type=bind,src={folder},dst=/work',*mounts,
                '-e','HF_HUB_OFFLINE=1','-e','TRANSFORMERS_OFFLINE=1','-e','HF_HUB_DISABLE_TELEMETRY=1',
                '-e','VLLM_NO_USAGE_STATS=1','-e','HF_HOME=/work/.cache',
                '--entrypoint','vllm',p['image_id'],'run-batch','-i','/work/requests.jsonl','-o','/work/responses.jsonl',
                '--model','/model','--served-model-name',s['model_id'],'--trust-remote-code',
                '--tensor-parallel-size','1','--pipeline-parallel-size','1','--max-num-seqs','1',
                '--max-model-len',str(s['context']),'--max-num-batched-tokens',str(s['prefill_chunk']),
                '--enable-chunked-prefill','--gpu-memory-utilization','0.85',
                '--cpu-offload-gb',str(s['offload_gib']),'--enforce-eager',
                '--reasoning-parser','mimo','--tool-call-parser','mimo','--enable-auto-tool-choice',
                '--generation-config','vllm']
        if kind=='serve':
            batch_at=docker.index('run-batch')
            engine_at=docker.index('--model',batch_at)
            docker=docker[:batch_at]+['serve','/model','--host','127.0.0.1','--port','8000']+docker[engine_at+2:]
        save(folder/'launch-argv.json',docker)
        launched=True;run(docker,timeout=45);receipt['status']='RUNNING'; active=time.monotonic()
        if kind=='serve':
            from bridge import Bridge
            bridge=Bridge(name,s['model_id'],s['timeout_s'],folder)
            connection={'base_url':f'http://127.0.0.1:{bridge.port}/v1','api_key':bridge.token,'model':s['model_id'],
                        'status':'STARTING; call /health before launching the native harness',
                        'expires_after_s':s['timeout_s'],'no_automatic_retry':True}
            save(folder/'connection-private.json',connection)
            print('Local native-harness connection saved to '+str(folder/'connection-private.json'),flush=True)
        maximum_gpu=0.;min_host=float('inf');samples=0
        with (folder/'telemetry.jsonl').open('x') as telemetry:
            while True:
                state=json.loads(run(['docker','inspect','--format','{{json .State}}',name]).stdout)
                measured=scan(); g=next(g for g in measured['gpus'] if g['uuid']==chosen['uuid'])
                maximum_gpu=max(maximum_gpu,g['used_gib']);min_host=min(min_host,measured['ram']['available_gib'])
                sample={'seconds_since_launch':round(time.monotonic()-active,3),'gpu_used_gib':g['used_gib'],
                        'host_available_gib':measured['ram']['available_gib'],'running':state['Running']}
                telemetry.write(json.dumps(sample)+'\n');telemetry.flush();samples+=1
                if not state['Running']:
                    receipt['exit_code']=state['ExitCode'];receipt['oom_killed']=state.get('OOMKilled');break
                require(shutil.disk_usage(folder).free>=8*GIB,'Disk headroom below 8 GiB; owned container stopped')
                if kind=='serve' and ((folder/'STOP').exists() or time.monotonic()-active>=s['timeout_s']):
                    receipt['status']='SERVING_WINDOW_CLOSED_UNSCORED';break
                require(time.monotonic()-active<s['timeout_s'],'Run deadline exceeded; owned container stopped without retry')
                require(measured['ram']['available_gib']>=s['reserve_gib'],'Host headroom gate tripped; owned container stopped')
                time.sleep(2)
        receipt.update({'load_and_batch_wall_s':time.monotonic()-active,'max_observed_gpu_gib':maximum_gpu,
                        'minimum_observed_host_available_gib':min_host,'telemetry_samples':samples})
        if kind=='serve':
            require(receipt['status']=='SERVING_WINDOW_CLOSED_UNSCORED','Runtime exited before serving window closed; inspect logs')
            receipt['native_transport_requests']=bridge.count
            receipt['benchmark_protocol']='Owned by the caller native harness; no score or protocol equivalence inferred here'
            return 0
        require(receipt['exit_code']==0 and not receipt['oom_killed'],'Runtime/load failure; no lower model, truncation or second GPU fallback')
        response_file=folder/'responses.jsonl'; require(response_file.is_file(),'Runtime produced no response file')
        answers=[json.loads(x) for x in response_file.read_text().splitlines() if x.strip()]
        receipt['responses_sha256']=hash_file(response_file)
        receipt['request_result']=response_summary(answers,{x['custom_id'] for x in rows})
        require(receipt['request_result']['transport_complete'],'Missing or error responses; quality is unscored')
        receipt['status']='CANARY_COMPLETED_UNSCORED' if kind=='canary' else 'BATCH_COMPLETED_UNSCORED'
    except (Exception,KeyboardInterrupt) as e:
        receipt['status']='STOPPED';receipt['reason']=str(e)[:1600]
    finally:
        if bridge:bridge.close()
        if launched:
            run(['docker','stop','--time','10',name],timeout=25,check=False)
            with (folder/'runtime.log').open('w') as log:
                subprocess.run(['docker','logs',name],stdout=log,stderr=subprocess.STDOUT,timeout=30,check=False)
            run(['docker','rm',name],timeout=30,check=False)
        receipt['total_wall_s_including_hashing']=time.monotonic()-started
        receipt['automatic_retry']=False;receipt['automatic_upload']=False
        receipt['one_gpu_claim_scope']='Docker device allowlist and runtime probe; not device-level remote attestation'
        save(folder/'receipt.json',receipt);write_report(folder,receipt)
    print(json.dumps(receipt,indent=2));return 0 if receipt['status'].endswith('COMPLETED_UNSCORED') else 2

def write_report(folder, receipt):
    fields=['status','target_model','model_revision','visible_gpu_count','gpu_name','cpu_offload_gib',
            'ram_cap_gib','max_observed_gpu_gib','minimum_observed_host_available_gib',
            'total_wall_s_including_hashing','load_and_batch_wall_s','native_transport_requests',
            'quality_score','native_scorer','reason']
    rows=''.join('<tr><th>'+html.escape(k.replace('_',' '))+'</th><td>'+html.escape(str(receipt.get(k,'NOT OBSERVED')))+'</td></tr>' for k in fields)
    page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>One GPU test receipt</title><style>body{max-width:900px;margin:40px auto;padding:20px;font:16px/1.6 system-ui;color:#17262b;background:#f5f6f3}h1{font-size:36px}table{width:100%;border-collapse:collapse;background:white}th,td{padding:12px;text-align:left;border-bottom:1px solid #ddd;overflow-wrap:anywhere}th{width:44%;font-weight:500}p{max-width:80ch}a{color:#175c4b}</style><h1>One GPU test receipt</h1><p>This is the observed execution record. A completed request is not a benchmark grade; use the original native scorer and report its exact denominator.</p><table>'+rows+'</table><p><a href="receipt.json">Full local receipt</a> · <a href="launch-argv.json">Exact launch</a> · <a href="runtime.log">Runtime log</a> · <a href="telemetry.jsonl">Resource samples</a></p><p>Private local files may contain prompts, paths or benchmark data. Review before sharing. No automatic upload occurred.</p>'
    (folder/'report.html').write_text(page)

def cli():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('inspect');a.add_argument('--out',default='hardware-private.json')
    a=sub.add_parser('plan');a.add_argument('settings');a.add_argument('--out',default='plan-private.json')
    a=sub.add_parser('run');a.add_argument('plan');a.add_argument('requests');a.add_argument('--out',required=True)
    a.add_argument('--kind',choices=['canary','benchmark'],default='canary');a.add_argument('--approve-load',action='store_true');a.add_argument('--protocol')
    a=sub.add_parser('serve');a.add_argument('plan');a.add_argument('--out',required=True);a.add_argument('--approve-load',action='store_true')
    args=parser.parse_args()
    if args.command=='inspect':
        report=scan();save(args.out,report)
        print(json.dumps({**report,'gpus':[{k:v for k,v in g.items() if k!='uuid'} for g in report['gpus']]},indent=2))
    elif args.command=='plan':
        p=make_plan(json_read(args.settings));save(args.out,p)
        print(json.dumps({k:p[k] for k in ['state','blockers','warnings','plan_sha256']},indent=2))
    elif args.command=='serve': return execute(args.plan,None,args.out,'serve',args.approve_load)
    else: return execute(args.plan,args.requests,args.out,args.kind,args.approve_load,args.protocol)
    return 0
if __name__=='__main__':
    try: sys.exit(cli())
    except (Refusal, OSError, ValueError, subprocess.SubprocessError, KeyError) as e:
        print('STOPPED: '+str(e),file=sys.stderr);sys.exit(2)
