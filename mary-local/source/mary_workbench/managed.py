"""An optional pinned CPU floor. ODS/private endpoints remain interchangeable suppliers.
No driver installation, GPU control, hosted inference, or persistent service.
"""
from __future__ import annotations
import json,os,platform,secrets,shutil,socket,stat,subprocess,sys,tarfile,threading,time,uuid,zipfile
from pathlib import Path,PurePosixPath
from typing import Any
import psutil
from filelock import FileLock,Timeout
from .common import BoundaryError,atomic_bytes,atomic_json,check_cancel,contained,hash_file,init_home,lock,now,private_dir,read_json,memory_budget
from .tools import download_verified
from .models import configure,http_json
from .process import clean_environment


def prepare(root:Path,*,cancel:Any=None)->dict:
    config=init_home(root);memory=memory_budget();arch={'x86_64':'x64','amd64':'x64','arm64':'arm64','aarch64':'arm64'}.get(platform.machine().lower());system={'Linux':'ubuntu','Darwin':'macos','Windows':'win-cpu'}.get(platform.system())
    if not arch or not system:raise BoundaryError('Use an existing ODS/local model endpoint on this platform; no pinned CPU binary is provided.')
    if memory['effective_available_bytes']<4*1024**3:raise BoundaryError('Less than 4 GiB memory is currently available; keep deterministic tasks usable and prepare the model when resources are free.')
    model_id='qwen3.5-4b-q4' if memory['effective_available_bytes']>=7*1024**3 else 'qwen3.5-2b-q4'
    vendor=Path(__file__).parent/'vendor/ods';catalog=read_json(vendor/'ods/config/model-library.json');model=next(m for m in catalog['models'] if m['id']==model_id)
    selector=[sys.executable,'-B',str(vendor/'ods/scripts/select-model.py'),'--catalog',str(vendor/'ods/config/model-library.json'),'--backend','cpu','--memory-type','none','--ram-gb',str(memory['effective_total_bytes']//1024**3),'--check-fit','--model-id',model_id,'--context','8192']
    estimate=subprocess.run(selector,capture_output=True,text=True,timeout=15)
    if estimate.returncode:raise BoundaryError('The pinned ODS exact-context memory estimate refused this candidate.')
    name=f'llama-b11429-bin-{system}-{arch}'+('.zip' if os.name=='nt' else '.tar.gz');pins=read_json(Path(__file__).with_name('binary-suppliers.json'));asset=pins['tools']['llama.cpp']['assets'][name]
    runtime=private_dir(root/'runtime');downloads=private_dir(runtime/'downloads');models=private_dir(runtime/'models');target=runtime/'llama-b11429'
    spec={'url':model['gguf_url'],'size':model['size_bytes'],'sha256':model['gguf_sha256']}
    needed=spec['size']+(0 if (downloads/name).exists() else asset['size'])+512*1024**2
    if not (models/model['gguf_file']).exists() and shutil.disk_usage(root).free<needed:raise BoundaryError('Insufficient free storage for the selected model and installation reserve.')
    with lock(root,'cpu-prepare',timeout=0):
        check_cancel(cancel);archive=download_verified(downloads/name,asset,cancel=cancel);check_cancel(cancel)
        weights=download_verified(models/model['gguf_file'],spec,cancel=cancel);check_cancel(cancel)
        receipt=read_json(runtime/'managed-profile.json')
        if target.exists():
            if not receipt:raise BoundaryError('An incomplete runtime generation exists; preserve it and inspect before replacing.')
            for relative,digest in receipt['runtime_files'].items():
                if hash_file(contained(target,relative))!=digest:raise BoundaryError('Installed runtime file changed: '+relative)
            return receipt
        stage=private_dir(runtime/('.llama-'+uuid.uuid4().hex))
        try:
            expanded=0;count=0
            if name.endswith('.zip'):
                with zipfile.ZipFile(archive) as z:
                    for member in z.infolist():
                        count+=1;expanded+=member.file_size
                        if count>1000 or expanded>256*1024**2 or member.is_dir():
                            if member.is_dir():continue
                            raise BoundaryError('Runtime archive exceeds its bound.')
                        if stat.S_ISLNK(member.external_attr>>16):raise BoundaryError('Runtime archive links are not permitted.')
                        destination=contained(stage,member.filename);private_dir(destination.parent)
                        with z.open(member) as source,destination.open('xb') as out:shutil.copyfileobj(source,out,1024*1024)
            else:
                with tarfile.open(archive,'r:gz') as tar:
                    members=tar.getmembers()
                    for member in members:
                        count+=1;expanded+=member.size
                        if count>1000 or expanded>256*1024**2:raise BoundaryError('Runtime archive exceeds its bound.')
                        if member.isdir():continue
                        if member.issym() or member.islnk():continue
                        if not member.isfile():raise BoundaryError('Runtime archive contains an unsupported member.')
                        destination=contained(stage,member.name.removeprefix('./'));private_dir(destination.parent)
                        with tar.extractfile(member) as source,destination.open('xb') as out:shutil.copyfileobj(source,out,1024*1024)
                        destination.chmod(0o700 if member.mode&0o111 else 0o600)
                    # Materialize archive-internal shared-library symlinks as copies.
                    pending=[m for m in members if m.issym() or m.islnk()]
                    while pending:
                        remaining=[];progress=False
                        for member in pending:
                            path=contained(stage,member.name.removeprefix('./'))
                            target_path=((path.parent/member.linkname) if member.issym() else (stage/member.linkname)).resolve()
                            if not target_path.is_relative_to(stage):raise BoundaryError('Runtime archive link escapes the staged artifact.')
                            if not target_path.is_file():remaining.append(member);continue
                            private_dir(path.parent);shutil.copyfile(target_path,path);progress=True
                        if remaining and not progress:raise BoundaryError('Runtime archive contains a missing or cyclic link target.')
                        pending=remaining
            executables=list(stage.rglob('llama-server.exe' if os.name=='nt' else 'llama-server'))
            if len(executables)!=1:raise BoundaryError('Runtime archive does not contain exactly one server.')
            executable=executables[0].relative_to(stage).as_posix();files={p.relative_to(stage).as_posix():hash_file(p) for p in stage.rglob('*') if p.is_file()}
            if os.name=='posix':executables[0].chmod(0o700)
            os.replace(stage,target)
            receipt={'status':'prepared-not-qualified','profile':'managed-cpu','supplier':'llama.cpp b11429','runtime_archive_sha256':asset['sha256'],'runtime_files':files,'executable':executable,'model_file':str(weights.relative_to(root)),'model_sha256':spec['sha256'],'model_id':model_id,'context_tokens':8192,'ods_fit':json.loads(estimate.stdout),'created_at':now(),'lifecycle':'starts with this MARY process; stops when it exits; no service installed'}
            atomic_json(runtime/'managed-profile.json',receipt);return receipt
        finally:
            if stage.exists():shutil.rmtree(stage)

class ManagedRuntime:
    def __init__(self,root:Path):self.root=root;self.process=None;self.guard=None;self.logs=[];self.stop_event=threading.Event();self.monitor=None
    def start(self)->dict:
        if self.process and self.process.poll() is None:return self.status()
        profile=read_json(self.root/'runtime/managed-profile.json')
        if not profile:raise BoundaryError('Prepare the pinned local CPU profile first.')
        binary=self.root/'runtime/llama-b11429';weights=contained(self.root,profile['model_file'])
        for name,digest in profile['runtime_files'].items():
            if hash_file(contained(binary,name))!=digest:raise BoundaryError('Runtime identity changed before execution.')
        if hash_file(weights)!=profile['model_sha256']:raise BoundaryError('Model weights changed before execution.')
        available=memory_budget()['effective_available_bytes']
        if available<4*1024**3:raise BoundaryError('Not enough current memory to start the local model.')
        self.guard=FileLock(str(self.root/'locks/managed-runtime.lock'),mode=0o600)
        try:self.guard.acquire(timeout=0)
        except Timeout as e:raise BoundaryError('Another process owns this workspace model runtime.') from e
        port=18465
        try:
            with socket.socket() as sock:sock.bind(('127.0.0.1',port))
            token=secrets.token_urlsafe(32);env=clean_environment();env.update(LLAMA_API_KEY=token,CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1')
            executable=contained(binary,profile['executable']);directory=private_dir(self.root/'runtime/model-log')
            self.logs=[(directory/'stdout.log').open('wb'),(directory/'stderr.log').open('wb')]
            args=[str(executable),'--model',str(weights),'--alias','mary-local','--ctx-size','8192','--parallel','1','--threads',str(min(4,os.cpu_count() or 1)),'--threads-batch',str(min(4,os.cpu_count() or 1)),'--host','127.0.0.1','--port',str(port),'--offline','--no-webui','--reasoning','off','--n-gpu-layers','0','--device','none','--cache-ram','0','--ctx-checkpoints','0','--fit','off','--jinja','--chat-template-kwargs','{"enable_thinking":false}']
            self.process=subprocess.Popen(args,cwd=executable.parent,stdin=subprocess.DEVNULL,stdout=self.logs[0],stderr=self.logs[1],env=env,start_new_session=os.name=='posix',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            start=time.monotonic()
            while time.monotonic()-start<90:
                if self.process.poll() is not None:raise BoundaryError('Local runtime stopped during startup. Its owned runtime/model-log records the missing dependency or error.')
                try:
                    connections=psutil.Process(self.process.pid).net_connections(kind='tcp')
                    if any(x.status=='LISTEN' and x.laddr.port==port and x.laddr.ip=='127.0.0.1' for x in connections):
                        value=http_json(f'http://127.0.0.1:{port}/health',key=token,timeout=2)
                        if value.get('status')=='ok':break
                except (psutil.Error,BoundaryError):pass
                time.sleep(.2)
            else:raise BoundaryError('Local model load exceeded 90 seconds.')
            configure(self.root,{'base_url':f'http://127.0.0.1:{port}/v1','model':'mary-local','transport':'openai-compatible','api_key':token,'allow_private_network':False})
            atomic_json(self.root/'runtime/managed-active.json',{'status':'running','pid':self.process.pid,'started_at':now(),'profile':profile['model_id'],'base_url':f'http://127.0.0.1:{port}/v1','model_sha256':profile['model_sha256']})
            def watch():
                while not self.stop_event.wait(1):
                    if self.process.poll() is not None:return
                    if any(p.stat().st_size>8*1024**2 for p in [directory/'stdout.log',directory/'stderr.log']):self.close();return
            self.monitor=threading.Thread(target=watch,daemon=True);self.monitor.start();return self.status()
        except BaseException:self.close();raise
    def status(self)->dict:return {'status':'running' if self.process and self.process.poll() is None else 'stopped','profile':'managed-cpu','port':18465,'no_gpu_controls':True}
    def close(self):
        from .recovery import stop
        self.stop_event.set()
        try:
            if self.process is not None:stop(self.process)
        finally:
            for f in self.logs:
                if not f.closed:f.close()
            if self.guard is not None:self.guard.release();self.guard=None
            if (self.root/'runtime/managed-active.json').exists():atomic_json(self.root/'runtime/managed-active.json',{'status':'stopped','at':now()})
