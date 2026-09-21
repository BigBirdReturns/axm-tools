"""Synthetic controller tests. No NVIDIA GPU, vLLM or model inference is performed."""
import contextlib, copy, hashlib, importlib.util, io, json, os, pathlib, struct
import subprocess, sys, tempfile, time, unittest, urllib.request, urllib.error
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'v1'))
import one_gpu as lab
from bridge import Bridge

S={'schema':'axm/one-gpu-settings@1','model_id':lab.MODEL_IDS[0],'model_revision':'a'*40,
   'model_path':'/tmp/EXPLICIT_SYNTHETIC_MODEL','image':'local-test-image','gpu_index':0,
   'context':2048,'prefill_chunk':512,'offload_gib':64,'ram_limit_gib':80,'reserve_gib':16,
   'cpus':2,'timeout_s':60,'max_requests':10}
HW={'schema':lab.VERSION,'ram':{'total_gib':256,'available_gib':240},'cpu_count':16,
    'gpus':[{'index':0,'uuid':'GPU-a123','name':'SYNTHETIC_GPU_NOT_A_MEASUREMENT','total_gib':96,'used_gib':0,'compute_busy':False,'driver':'synthetic'}], 'docker_available':True}
M={'tensor_payload_gib':120,'largest_file_gib':4,'model_type':'mimo_v2','quantization_config':{'store_dtype':'mxfp4'}}
REQ={'custom_id':'synthetic-test-only','method':'POST','url':'/v1/chat/completions',
     'body':{'model':lab.MODEL_IDS[0],'messages':[{'role':'user','content':'synthetic'}],'max_tokens':32,'temperature':0}}

def tensor(path, name='weight', shape=None, offsets=None, payload=b'abcd',dtype='F32'):
    h=json.dumps({name:{'dtype':dtype,'shape':shape or [1],'data_offsets':offsets or [0,4]}}).encode()
    path.write_bytes(struct.pack('<Q',len(h))+h+payload)

def model(root):
    root.mkdir();(root/'config.json').write_text(json.dumps({'model_type':'mimo_v2','architectures':['Synthetic_Not_MiMo']}))
    tensor(root/'model.safetensors')
    (root/'model.safetensors.index.json').write_text(json.dumps({'metadata':{'total_size':4},'weight_map':{'weight':'model.safetensors'}}))

class Rules(unittest.TestCase):
    def test_settings(self):self.assertEqual(lab.validate_settings(S),S)
    def test_invalid_fields_refuse(self):
        for field,value in [('model_revision','main'),('model_id','smaller-substitute'),('gpu_index',True),('context',0),('image','--privileged'),('cpus',0),('ram_limit_gib',65),('prefill_chunk',10000)]:
            with self.subTest(field=field), self.assertRaises(lab.Refusal):lab.validate_settings({**S,field:value})
    def test_admits_candidate_not_claim(self):
        errors,warnings=lab.admission(S,HW,M);self.assertFalse(errors);self.assertTrue(warnings)
    def test_ram_reject(self):
        h=copy.deepcopy(HW);h['ram']['available_gib']=32;self.assertTrue(lab.admission(S,h,M)[0])
    def test_busy_reject(self):
        h=copy.deepcopy(HW);h['gpus'][0]['compute_busy']=True;self.assertTrue(lab.admission(S,h,M)[0])
    def test_gpu_missing(self):self.assertTrue(lab.admission({**S,'gpu_index':3},HW,M)[0])
    def test_raw_capacity_reject(self):self.assertTrue(lab.admission(S,HW,{**M,'tensor_payload_gib':900})[0])
    def test_staging_reject(self):self.assertTrue(lab.admission(S,HW,{**M,'largest_file_gib':50})[0])
    def test_architecture_reject(self):self.assertTrue(lab.admission(S,HW,{**M,'model_type':'other'})[0])
    def test_cpu_headroom_reject(self):self.assertTrue(lab.admission({**S,'cpus':16},HW,M)[0])
    def test_paths(self):
        for name in ['/etc/passwd','../../credentials','x,y','a\\b','x\ny']:
            with self.subTest(name=name), self.assertRaises(lab.Refusal):lab.safe_name(name)
    def test_header_and_exact_index(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'model';model(p);m=lab.inspect_model(p)
            self.assertEqual(m['tensor_count'],1);self.assertEqual(m['shard_count'],1)
            self.assertEqual(m['tensor_payload_gib'],4/lab.GIB)
    def test_truncated_tensor(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'model';model(p);f=p/'model.safetensors';f.write_bytes(f.read_bytes()[:-1])
            with self.assertRaises(lab.Refusal):lab.inspect_model(p)
    def test_mismatched_index(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'model';model(p);(p/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'wrong':'model.safetensors'}}))
            with self.assertRaises(lab.Refusal):lab.inspect_model(p)
    def test_no_output_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x.json';lab.save(p,{'ok':True})
            with self.assertRaises(lab.Refusal):lab.save(p,{'destroy':True})
    def test_unknown_dtype(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x';tensor(p,dtype='mystery')
            with self.assertRaises(lab.Refusal):lab.header(p)
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x';p.write_text('{"x":1,"x":2}')
            with self.assertRaises(lab.Refusal):lab.json_read(p)
    def test_requests_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x';p.write_text(json.dumps(REQ)+'\n');before=p.read_bytes()
            self.assertEqual(lab.validate_requests(p,S,'canary'),[REQ]);self.assertEqual(p.read_bytes(),before)
    def test_request_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x'
            for change in [{'body':{**REQ['body'],'model':'fallback'}},{'url':'/v1/responses'},{'body':{**REQ['body'],'max_tokens':5000}},{'body':{**REQ['body'],'stream':True}},{'body':{**REQ['body'],'n':2}}]:
                p.write_text(json.dumps({**REQ,**change})+'\n')
                with self.subTest(change=change),self.assertRaises(lab.Refusal):lab.validate_requests(p,S,'canary')
    def test_duplicate_requests(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x';p.write_text((json.dumps(REQ)+'\n')*2)
            with self.assertRaises(lab.Refusal):lab.validate_requests(p,S,'benchmark')
    def test_response_not_score(self):
        r={'custom_id':REQ['custom_id'],'response':{'status_code':200,'body':{'choices':[{'finish_reason':'length','message':{'content':'synthetic'}}]}},'error':None}
        result=lab.response_summary([r],{REQ['custom_id']});self.assertTrue(result['transport_complete']);self.assertIsNone(result['quality_score']);self.assertEqual(result['length_limited_choices'],1)
    def test_missing_not_success(self):self.assertFalse(lab.response_summary([],{'a'})['transport_complete'])
    def test_response_error_not_success(self):self.assertFalse(lab.response_summary([{'custom_id':'a','error':'load-failed'}],{'a'})['transport_complete'])
    def test_duplicate_response_reject(self):
        with self.assertRaises(lab.Refusal):lab.response_summary([{'custom_id':'a'},{'custom_id':'a'}],{'a'})
    def test_unexpected_response_reject(self):
        with self.assertRaises(lab.Refusal):lab.response_summary([{'custom_id':'x'}],{'a'})
    def test_protocol_binding(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);r=p/'r';r.write_text(json.dumps(REQ))
            protocol={'schema':'axm/frozen-benchmark-requests@1','benchmark_id':'synthetic','harness_revision':'fixture-test','dataset_revision':'synthetic','scorer_revision':'NONE-test','context':2048,'interaction':'independent_requests','timing_policy':'offline-no-per-request-deadline','requests_sha256':lab.hash_file(r)}
            f=p/'protocol.json';f.write_text(json.dumps(protocol));self.assertEqual(lab.validate_protocol(f,r,S),protocol)
            for field,value in [('context',1024),('requests_sha256','0'*64),('interaction','interactive'),('timing_policy','deadline'),('scorer_revision','')]:
                f.write_text(json.dumps({**protocol,field:value}))
                with self.subTest(field=field),self.assertRaises(lab.Refusal):lab.validate_protocol(f,r,S)
    def test_no_execution_without_approval(self):
        with self.assertRaises(lab.Refusal):lab.execute('missing','missing','missing','canary',False)
    def test_mocked_process_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);mp=root/'model';model(mp);s={**S,'model_path':str(mp)}
            calls=[]
            def command(args,timeout=30,check=True):
                calls.append(args)
                if args[:3]==['docker','image','inspect']:text=json.dumps([{'Id':'sha256:'+'a'*64,'RepoDigests':[]}])
                elif '-c' in args:text=json.dumps({'cuda_count':1,'vllm':'SYNTHETIC-NOT-RUN','torch':'SYNTHETIC'})
                elif '--help=all' in args:text='--cpu-offload-gb --model --served-model-name'
                elif '--detach' in args:
                    dest=next(x[18:-10] for x in args if x.startswith('type=bind,src=') and x.endswith(',dst=/work')) if False else root/'run'
                    (dest/'responses.jsonl').write_text(json.dumps({'custom_id':REQ['custom_id'],'response':{'status_code':200,'body':{'choices':[{'finish_reason':'stop','message':{'content':'SIMULATED'}}]}}})+'\n')
                    text='container-id'
                elif args[:2]==['docker','inspect']:text=json.dumps({'Running':False,'ExitCode':0,'OOMKilled':False})
                else:text=''
                return subprocess.CompletedProcess(args,0,text,'')
            with patch.object(lab,'scan',return_value=copy.deepcopy(HW)),patch.object(lab,'run',side_effect=command),patch.object(lab.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'')):
                plan=lab.make_plan(s);f=root/'p.json';lab.save(f,plan);r=root/'requests';r.write_text(json.dumps(REQ)+'\n')
                with contextlib.redirect_stdout(io.StringIO()):rc=lab.execute(f,r,root/'run','canary',True)
            self.assertEqual(rc,0)
            actual=lab.json_read(root/'run/receipt.json');self.assertIsNone(actual['quality_score']);self.assertEqual(actual['status'],'CANARY_COMPLETED_UNSCORED')
            argv=lab.json_read(root/'run/launch-argv.json');self.assertEqual(argv[argv.index('--network')+1],'none');self.assertEqual(argv[argv.index('--gpus')+1],'device=GPU-a123')
            self.assertEqual(argv[argv.index('--tensor-parallel-size')+1],'1')
            self.assertEqual(argv[argv.index('--memory')+1],argv[argv.index('--memory-swap')+1])
            self.assertTrue(any(x[:2]==['docker','stop'] for x in calls));self.assertTrue(any(x[:2]==['docker','rm'] for x in calls))
    def test_changed_plan_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'plan.json';p.write_text(json.dumps({'settings':S,'plan_sha256':'forged'}))
            with self.assertRaises(lab.Refusal):lab.execute(p,'unused',pathlib.Path(d)/'out','canary',True)
    def test_missing_protocol_refuses(self):
        with self.assertRaises(lab.Refusal):lab.validate_protocol(None,'unused',S)
    def test_no_body_budget_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'r';r=copy.deepcopy(REQ);del r['body']['max_tokens'];p.write_text(json.dumps(r))
            with self.assertRaises(lab.Refusal):lab.validate_requests(p,S,'canary')
    def test_index_total_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'m';model(p);f=p/'model.safetensors.index.json';x=json.loads(f.read_text());x['metadata']['total_size']=999;f.write_text(json.dumps(x))
            with self.assertRaises(lab.Refusal):lab.inspect_model(p)
    def test_tensor_shape_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x';tensor(p,shape=[2])
            with self.assertRaises(lab.Refusal):lab.header(p)
    def test_bodyless_success_is_not_generation(self):
        r={'custom_id':'a','response':{'status_code':200,'body':{'choices':[{'message':{'content':''},'finish_reason':'stop'}]}}}
        self.assertFalse(lab.response_summary([r],{'a'})['transport_complete'])
    def test_bridge_forwarding_is_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            directory=pathlib.Path(d)
            real_popen=subprocess.Popen
            # A tiny local Python process substitutes ONLY docker exec, never claims MiMo.
            script="import sys,json; data=sys.stdin.buffer.read();sys.stdout.write('200\\n');sys.stdout.flush();sys.stdout.write(json.dumps({'observed_sha':__import__('hashlib').sha256(data).hexdigest(),'synthetic_only':True}));sys.stdout.flush()"
            def fake(args,**kwargs):
                self.assertEqual(args[:2],['docker','exec'])
                return real_popen([sys.executable,'-c',script],**kwargs)
            b=Bridge('synthetic-container',lab.MODEL_IDS[0],3,directory)
            try:
                body=json.dumps(REQ['body']).encode()
                q=urllib.request.Request(f'http://127.0.0.1:{b.port}/v1/chat/completions',data=body,headers={'Authorization':'Bearer '+b.token,'Content-Type':'application/json'})
                with patch('bridge.subprocess.Popen',side_effect=fake):
                    value=json.loads(urllib.request.urlopen(q,timeout=5).read())
                self.assertEqual(value['observed_sha'],hashlib.sha256(body).hexdigest());self.assertTrue(value['synthetic_only'])
                time.sleep(.05)
                lines=[json.loads(x) for x in (directory/'native-transport.jsonl').read_text().splitlines()]
                self.assertEqual(lines[-1]['request_sha256'],hashlib.sha256(body).hexdigest())
            finally:b.close()
    def test_bridge_denies_unauthenticated(self):
        with tempfile.TemporaryDirectory() as d:
            b=Bridge('synthetic',lab.MODEL_IDS[0],1,pathlib.Path(d))
            try:
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(f'http://127.0.0.1:{b.port}/health')
                self.assertEqual(e.exception.code,401)
            finally:b.close()
    def test_bridge_rejects_unknown_endpoint(self):
        with tempfile.TemporaryDirectory() as d:
            b=Bridge('synthetic',lab.MODEL_IDS[0],1,pathlib.Path(d))
            try:
                q=urllib.request.Request(f'http://127.0.0.1:{b.port}/other',headers={'Authorization':'Bearer '+b.token})
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(q)
                self.assertEqual(e.exception.code,404)
            finally:b.close()
    def test_bridge_rejects_origin(self):
        with tempfile.TemporaryDirectory() as d:
            b=Bridge('synthetic',lab.MODEL_IDS[0],1,pathlib.Path(d))
            try:
                q=urllib.request.Request(f'http://127.0.0.1:{b.port}/health',headers={'Authorization':'Bearer '+b.token,'Origin':'https://example.test'})
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(q)
                self.assertEqual(e.exception.code,403)
            finally:b.close()

if __name__=='__main__':unittest.main()
