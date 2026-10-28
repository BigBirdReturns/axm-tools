"""Encrypted recovery through restic, with a bounded portable context archive.
No cryptographic primitive or encryption container is reimplemented here.
"""
from __future__ import annotations
import io,json,os,shutil,signal,sqlite3,subprocess,tarfile,tempfile,threading,time,uuid
from contextlib import ExitStack,closing
from pathlib import Path,PurePosixPath
from typing import Any
from .common import BoundaryError,Cancelled,atomic_json,canonical,check_cancel,contained,hash_file,init_home,local_path,lock,now,private_dir,read_json
from .tools import restic_path
from .process import clean_environment

MAX_BYTES=24*1024**3
MAX_FILES=200000

def environment(root:Path,password:str)->dict:
    if not isinstance(password,str) or not 12<=len(password)<=4096:raise BoundaryError('Use a recovery password of at least 12 characters and keep it independently.')
    env=clean_environment();env.update(RESTIC_PASSWORD=password,RESTIC_CACHE_DIR=str(private_dir(root/'runtime/restic-cache')),TMPDIR=str(private_dir(root/'runtime/restic-temp')),TMP=str(root/'runtime/restic-temp'),TEMP=str(root/'runtime/restic-temp'));return env

def repository_path(root:Path,repository:Path)->Path:
    repository=local_path(repository)
    if repository==Path(repository.anchor) or repository==Path.home().resolve() or repository.is_relative_to(root) or root.is_relative_to(repository):raise BoundaryError('Choose a separate dedicated backup repository, preferably on another physical device.')
    return repository

def command(binary:Path,repo:Path,args:list[str],env:dict,timeout:int=60)->dict|list:
    p=subprocess.run([str(binary),'-r',str(repo),*args],stdin=subprocess.DEVNULL,capture_output=True,env=env,timeout=timeout)
    if len(p.stdout)>8*1024*1024:raise BoundaryError('Recovery metadata exceeds its bound.')
    if p.returncode:raise BoundaryError('Recovery tool refused the operation: '+p.stderr.decode(errors='replace')[-500:])
    return json.loads(p.stdout or b'{}')

def stop(process):
    if process.poll() is not None:return
    try:
        if os.name=='posix':os.killpg(process.pid,signal.SIGTERM)
        else:process.terminate()
    except ProcessLookupError:return
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
        except ProcessLookupError:pass
        process.wait(timeout=3)

def backup(root:Path,repository:Path,password:str,*,operation_id:str|None=None,cancel:Any=None)->dict:
    root=local_path(root,exists=True);config=init_home(root);repo=repository_path(root,repository);binary=restic_path(root);env=environment(root,password);operation_id=operation_id or uuid.uuid4().hex
    tag='mary-job:'+operation_id
    private_dir(repo)
    if not (repo/'config').exists():
        if any(repo.iterdir()):raise BoundaryError('Selected repository contains unrelated files; it was left intact.')
        command(binary,repo,['init','--json'],env)
    existing=command(binary,repo,['snapshots','--tag',tag,'--json'],env)
    if existing:return {'status':'accepted','snapshot_id':existing[-1]['id'],'repository':str(repo),'reused_existing_operation':True,'encrypted':True}
    staging=private_dir(root/'recovery'/('snapshot-'+uuid.uuid4().hex));source_db=staging/'sources.sqlite';process=None;thread=None;thread_errors=[]
    try:
        with ExitStack() as stack:
            stack.enter_context(lock(root,'recovery',timeout=1));stack.enter_context(lock(root,'source-writer',timeout=30));stack.enter_context(lock(root,'model-config',timeout=10))
            work_dirs=[]
            for folder in sorted((root/'work').iterdir()):
                if not folder.is_dir() or folder.name==operation_id:continue
                state=read_json(folder/'state.json')
                if state and state.get('status') in {'running','queued'}:raise BoundaryError('A work operation is active; backup waits for a stable checkpoint.')
                stack.enter_context(lock(root,'work-'+folder.name,timeout=0));work_dirs.append(folder)
            with closing(sqlite3.connect(root/'sources.sqlite')) as source,closing(sqlite3.connect(source_db)) as target:source.backup(target)
            files=[('sources.sqlite',source_db)]
            for name in ['settings.json']:
                p=root/name
                if p.exists():files.append((name,p))
            for subtree in ['keys','shards','imports']:
                for p in sorted((root/subtree).rglob('*')):
                    if p.is_symlink():raise BoundaryError('Link found inside workspace custody.')
                    if p.is_file() and not any(x.startswith('.stage-') for x in p.parts):files.append((p.relative_to(root).as_posix(),p))
            for folder in work_dirs:
                for p in sorted(folder.rglob('*')):
                    if p.is_symlink():raise BoundaryError('Link found in retained work.')
                    if p.is_file() and not p.name.startswith('.') and not p.name.endswith('.lock'):files.append((p.relative_to(root).as_posix(),p))
            size=sum(p.stat().st_size for _,p in files)
            if len(files)>MAX_FILES or size>MAX_BYTES:raise BoundaryError('Recovery set exceeds this profile; no partial success is claimed.')
            manifest={'schema':'mary/context-recovery@1','workspace_id':config['workspace_id'],'created_at':now(),'files':[{'path':n,'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for n,p in files],'includes':['originals','Genesis owner keys','source lifecycle','task intents and checkpoints','accepted artifacts','model endpoint credentials'],'excludes':['regenerable indexes','download caches','external model weights/runtime','in-flight task','qualification transferred as authority'],'qualification':'re-run on restored device'}
            log=staging/'restic.jsonl';errors=staging/'restic-error.log'
            with log.open('wb') as stdout,errors.open('wb') as stderr:
                process=subprocess.Popen([str(binary),'-r',str(repo),'backup','--stdin','--stdin-filename','mary-workspace.tar','--tag','mary:'+config['workspace_id'],'--tag',tag,'--json'],stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,env=env,start_new_session=os.name=='posix')
                def send():
                    try:
                        with tarfile.open(fileobj=process.stdin,mode='w|') as archive:
                            body=canonical(manifest);info=tarfile.TarInfo('BACKUP-MANIFEST.json');info.size=len(body);info.mode=0o600;archive.addfile(info,io.BytesIO(body))
                            for name,p in files:
                                check_cancel(cancel);info=tarfile.TarInfo(name);info.size=p.stat().st_size;info.mode=0o600;info.mtime=p.stat().st_mtime
                                with p.open('rb') as f:archive.addfile(info,f)
                    except BaseException as e:thread_errors.append(e)
                    finally:
                        try:process.stdin.close()
                        except OSError:pass
                thread=threading.Thread(target=send,daemon=True);thread.start();started=time.monotonic()
                while process.poll() is None:
                    check_cancel(cancel)
                    if time.monotonic()-started>1800:raise BoundaryError('Backup reached its finite deadline. A partial attempt is not a completed snapshot.')
                    if log.stat().st_size>8*1024*1024 or errors.stat().st_size>2*1024*1024:raise BoundaryError('Backup output exceeded its bound.')
                    time.sleep(.1)
                thread.join(timeout=3)
                if thread_errors:raise BoundaryError('Context archive failed: '+str(thread_errors[0]))
                if process.returncode:raise BoundaryError('Backup failed: '+errors.read_text(errors='replace')[-500:])
            snapshots=command(binary,repo,['snapshots','--tag',tag,'--json'],env)
            if len(snapshots)!=1:raise BoundaryError('Could not independently identify the completed backup snapshot.')
            receipt={'status':'accepted','snapshot_id':snapshots[0]['id'],'repository':str(repo),'files':len(files),'source_bytes':size,'encrypted':True,'independent_restore':'not inferred from successful backup','external_runtime':'retain the build kit and selected model weights separately for offline replacement-host operation'}
            atomic_json(root/'recovery'/('backup-'+operation_id+'.json'),receipt);return receipt
    finally:
        if process is not None:stop(process)
        if thread is not None:thread.join(timeout=3)
        shutil.rmtree(staging,ignore_errors=True)

def restore(root:Path,repository:Path,password:str,destination:Path,snapshot:str='latest',*,cancel:Any=None)->dict:
    root=local_path(root,exists=True);repo=repository_path(root,repository);destination=local_path(destination)
    if destination.exists():raise BoundaryError('Restore requires a new destination; no existing workspace will be overwritten.')
    if destination.is_relative_to(repo) or repo.is_relative_to(destination):raise BoundaryError('Restore destination must be outside the repository.')
    binary=restic_path(root);env=environment(root,password);destination.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.mary-restore-',dir=destination.parent));body=private_dir(stage/'workspace');process=None;watcher=None;finished=threading.Event();failures=[]
    try:
        with (stage/'error.log').open('wb') as stderr:
            process=subprocess.Popen([str(binary),'-r',str(repo),'dump',snapshot,'mary-workspace.tar'],stdout=subprocess.PIPE,stderr=stderr,stdin=subprocess.DEVNULL,env=env,start_new_session=os.name=='posix')
            def watch():
                started=time.monotonic()
                while not finished.wait(.2):
                    if cancel is not None and cancel.is_set() or time.monotonic()-started>1800:
                        failures.append('Restore cancelled or deadline exceeded.');stop(process);return
            watcher=threading.Thread(target=watch,daemon=True);watcher.start()
            with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
                first=archive.next()
                if first is None or first.name!='BACKUP-MANIFEST.json' or not first.isfile() or first.size>32*1024*1024:raise BoundaryError('Unknown recovery archive.')
                manifest=json.load(archive.extractfile(first))
                if manifest.get('schema')!='mary/context-recovery@1' or not isinstance(manifest.get('files'),list):raise BoundaryError('Unsupported recovery manifest.')
                declared={}
                for entry in manifest['files']:
                    name=entry['path'];contained(body,name)
                    if name in declared or type(entry['size']) is not int or entry['size']<0:raise BoundaryError('Invalid recovery entry.')
                    declared[name]=entry
                if len(declared)>MAX_FILES or sum(x['size'] for x in declared.values())>MAX_BYTES:raise BoundaryError('Recovery exceeds its declared size profile.')
                seen=set()
                while True:
                    member=archive.next()
                    if member is None:break
                    check_cancel(cancel)
                    if not member.isfile() or member.name not in declared or member.name in seen or member.size!=declared[member.name]['size']:raise BoundaryError('Archive member does not match the authenticated recovery inventory.')
                    target=contained(body,member.name);private_dir(target.parent)
                    with archive.extractfile(member) as src,os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out:
                        copied=0
                        while True:
                            check_cancel(cancel);data=src.read(1024*1024)
                            if not data:break
                            copied+=len(data)
                            if copied>member.size:raise BoundaryError('Recovered member exceeds its bound.')
                            out.write(data)
                        out.flush();os.fsync(out.fileno())
                    if copied!=member.size:raise BoundaryError('Truncated recovery member.')
                    seen.add(member.name)
                if seen!=set(declared):raise BoundaryError('Recovery archive omitted declared files.')
            process.wait(timeout=30);finished.set()
            if process.returncode or failures:raise BoundaryError('Recovery stream failed authentication or completed incompletely.')
        from .sources import Sources
        from mary.ledger import verify_ledger
        sources=Sources(body);rebuilt=sources.rebuild()
        for p in (body/'work').glob('*/outcomes.jsonl'):verify_ledger(p)
        for p in (body/'work').glob('*/state.json'):
            state=read_json(p)
            for item in state.get('artifacts',[]):
                artifact=contained(p.parent/'artifacts',item['name'])
                if hash_file(artifact)!=item['sha256']:raise BoundaryError('Recovered accepted artifact failed its content check.')
            if state.get('status') in {'running','queued'}:state['status']='interrupted';atomic_json(p,state)
        atomic_json(body/'qualification.json',{'status':'required','reason':'Restored environment: requalify its selected model route.'})
        if destination.exists():raise BoundaryError('Destination appeared during recovery; it was not overwritten.')
        os.replace(body,destination)
        return {'status':'accepted','destination':str(destination),'workspace_id':manifest['workspace_id'],'files':len(declared),'index':rebuilt,'qualification':'required on this device','restore_scope':'owned context, source custody, work and credentials; external model/build assets remain separate'}
    finally:
        finished.set()
        if process is not None:stop(process)
        if watcher is not None:watcher.join(timeout=3)
        shutil.rmtree(stage,ignore_errors=True)
