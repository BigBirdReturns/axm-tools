"""Loopback personal workspace. Authenticated owner actions, no generic shell API."""
from __future__ import annotations
import asyncio,contextlib,hashlib,json,os,re,secrets,time,uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit,unquote
from fastapi import FastAPI,Request,HTTPException,Depends
from fastapi.responses import FileResponse,HTMLResponse,JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from . import __version__
from .common import BoundaryError,atomic_bytes,atomic_json,contained,default_home,init_home,local_path,now,private_dir,read_json,validate_id
from .jobs import Workbench
from . import models
from .hardware import observe

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class WorkRequest(Strict):
    request_id:str
    message:str=Field(min_length=1,max_length=8000)
    action:str='auto'
    source_ids:list[str]=[]
    options:dict={}
class ModelRequest(Strict):
    base_url:str
    model:str
    transport:str='openai-compatible'
    api_key:str=''
    allow_private_network:bool=False
class ImportRequest(Strict):
    request_id:str
    path:str
class IdRequest(Strict):
    request_id:str
class BackupRequest(Strict):
    request_id:str
    repository:str
    password:str=Field(min_length=12,max_length=4096)


def create_app(root:Path)->FastAPI:
    root=local_path(root);config=init_home(root);token=(root/'keys/web.token').read_text();workbench=Workbench(root)
    @asynccontextmanager
    async def lifespan(app):
        selected=read_json(root/'settings.json').get('model') or {}
        if selected.get('base_url')=='http://127.0.0.1:18465/v1' and (root/'runtime/managed-profile.json').exists():
            from .managed import ManagedRuntime
            workbench.managed_runtime=ManagedRuntime(root)
            try:await asyncio.to_thread(workbench.managed_runtime.start)
            except BoundaryError:pass
        yield
        await asyncio.to_thread(workbench.close)
    app=FastAPI(title='MARY local workspace',version=__version__,docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.workbench=workbench;app.state.workspace=root
    @app.exception_handler(BoundaryError)
    async def boundary_error(request:Request,exc:BoundaryError):return JSONResponse({'error':str(exc),'status':'refused'},status_code=409)
    @app.middleware('http')
    async def local_boundary(request:Request,call_next):
        host=request.url.hostname
        if host not in {'localhost','127.0.0.1','::1','testserver'}:return JSONResponse({'error':'This is a loopback-only personal workspace.'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return JSONResponse({'error':'Cross-origin actions are refused.'},status_code=403)
        length=request.headers.get('content-length')
        if length:
            try:
                if int(length)>64*1024**2:return JSONResponse({'error':'Upload exceeds 64 MiB.'},status_code=413)
            except ValueError:return JSONResponse({'error':'Invalid content length.'},status_code=400)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer';response.headers['Cache-Control']='no-store';response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response
    async def owner(request:Request):
        authorization=request.headers.get('authorization','')
        if not authorization.startswith('Bearer ') or not secrets.compare_digest(authorization[7:],token):raise HTTPException(401,'A valid local owner token is required.')
    secured=[Depends(owner)]
    @app.get('/',response_class=HTMLResponse)
    async def home():return HTMLResponse((Path(__file__).parent/'static/index.html').read_text(encoding='utf-8'))
    @app.get('/app.js')
    async def app_script():return FileResponse(Path(__file__).parent/'static/app.js',media_type='application/javascript')
    @app.get('/health')
    async def health():return {'status':'ok','version':__version__}
    @app.get('/api/status',dependencies=secured)
    async def status():
        cfg=read_json(root/'settings.json');selected=cfg.get('model');qualification=read_json(root/'qualification.json');cached=read_json(root/'hardware.json')
        return {'version':__version__,'owner':cfg['owner'],'workspace_id':cfg['workspace_id'],'source_count':len(workbench.sources.list()),'model':{'configured':bool(selected),'qualified':bool(qualification and qualification.get('status')=='passed'),'model':selected.get('model') if selected else None,'base_url':selected.get('base_url') if selected else None,'transport':selected.get('transport') if selected else None},'hardware':cached or {'status':'Use Scan hardware for a fresh read-only observation.'},'capabilities':[{'name':'Owned sources / Genesis verification / Spectra retrieval','state':'installed'},{'name':'Exact calculation and table analysis','state':'installed'},{'name':'Drafting, comparison and source-grounded answers','state':'requires qualified local model'},{'name':'Encrypted recovery','state':'requires prepared restic and owner password'},{'name':'Send, delete originals or change system settings','state':'not exposed'}],'jobs':workbench.list()}
    @app.get('/api/hardware',dependencies=secured)
    async def hardware():
        result=await asyncio.to_thread(observe);atomic_json(root/'hardware.json',result);return result
    @app.get('/api/models/discover',dependencies=secured)
    async def discover():return {'items':await asyncio.to_thread(models.discover_local)}
    @app.post('/api/model',dependencies=secured)
    async def model(settings:ModelRequest):return await asyncio.to_thread(models.configure,root,settings.model_dump())
    @app.post('/api/qualify',dependencies=secured)
    async def qualify(request:IdRequest):
        state=workbench.submit_operation('qualify',{},request.request_id);return {'job_id':state['id']}
    @app.post('/api/prepare-local',dependencies=secured)
    async def prepare_local(request:IdRequest):
        state=workbench.submit_operation('prepare-cpu',{},request.request_id);return {'job_id':state['id']}
    @app.post('/api/prepare-recovery',dependencies=secured)
    async def prepare_recovery(request:IdRequest):
        state=workbench.submit_operation('prepare-recovery',{},request.request_id);return {'job_id':state['id']}
    @app.get('/api/sources',dependencies=secured)
    async def sources():return {'items':workbench.sources.list()}
    @app.post('/api/source/{source_id}/withdraw',dependencies=secured)
    async def withdraw(source_id:str):return await asyncio.to_thread(workbench.sources.withdraw,source_id)
    @app.get('/api/source/{source_id}/original',dependencies=secured)
    async def original(source_id:str):
        item=workbench.sources.source(source_id);path=await asyncio.to_thread(workbench.sources.original,source_id)
        return FileResponse(path,media_type='application/octet-stream',filename=item['name'])
    @app.get('/api/search',dependencies=secured)
    async def search(q:str,history:bool=False):return {'items':await asyncio.to_thread(workbench.sources.search,q,history=history)}
    @app.post('/api/upload',dependencies=secured)
    async def upload(request:Request,name:str|None=None):
        name=unquote(request.headers.get('x-mary-filename','')) or name or ''
        if len(name)>180 or name in {'.','..'} or any(x in name for x in '/\\:\x00') or any(ord(x)<32 for x in name):raise HTTPException(400,'Use a plain filename.')
        operation=validate_id(request.headers.get('x-mary-request-id') or uuid.uuid4().hex)
        expected=request.headers.get('x-mary-sha256','')
        if expected and not re.fullmatch(r'[a-f0-9]{64}',expected):raise HTTPException(400,'Invalid upload digest.')
        prior=read_json(root/'work'/operation/'request.json')
        if prior:
            payload=prior['request'].get('payload',{})
            if payload.get('name')!=name or payload.get('sha256')!=expected:raise HTTPException(409,'Upload identity is already bound to different input.')
            return {'source_id':None,'job_id':operation}
        folder=private_dir(root/'uploads'/operation);path=folder/name;total=0;digest=hashlib.sha256()
        try:
            with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
                async for data in request.stream():
                    total+=len(data)
                    if total>64*1024**2:raise HTTPException(413,'File exceeds 64 MiB.')
                    f.write(data);digest.update(data)
                f.flush();os.fsync(f.fileno())
            if expected and digest.hexdigest()!=expected:raise HTTPException(409,'Received bytes differ from the selected file.')
            state=workbench.submit_operation('upload',{'path':str(path),'source_key':'uploaded:'+operation+':'+name,'name':name,'sha256':digest.hexdigest()},operation)
            return {'source_id':None,'job_id':state['id']}
        except BaseException:
            path.unlink(missing_ok=True)
            with contextlib.suppress(OSError):folder.rmdir()
            raise
    @app.post('/api/import',dependencies=secured)
    async def start_import(request:ImportRequest):
        # Authenticated selection is the owner's explicit read grant for this
        # specific directory. The source adapter still rejects roots and secrets.
        path=local_path(Path(request.path),exists=True)
        workbench.sources.begin_import(path,request.request_id)
        state=workbench.submit_operation('import',{'path':str(path)},request.request_id);return {'job_id':state['id']}
    @app.post('/api/import/{job_id}/resume',dependencies=secured)
    async def resume_import(job_id:str,request:IdRequest):
        if request.request_id!=job_id:raise HTTPException(409,'Resume the same durable import identity.')
        return workbench.resume(job_id)
    @app.post('/api/work',dependencies=secured)
    async def submit(request:WorkRequest):
        state=workbench.submit(request.model_dump());return {'job_id':state['id']}
    @app.get('/api/work',dependencies=secured)
    async def list_work():return {'items':workbench.list()}
    @app.get('/api/work/{job_id}',dependencies=secured)
    async def get_work(job_id:str):return workbench.get(job_id)
    @app.post('/api/work/{job_id}/cancel',dependencies=secured)
    async def cancel(job_id:str):return workbench.cancel(job_id)
    @app.post('/api/work/{job_id}/resume',dependencies=secured)
    async def resume(job_id:str):return workbench.resume(job_id)
    @app.get('/api/artifact/{job_id}/{name}',dependencies=secured)
    async def artifact(job_id:str,name:str):return FileResponse(workbench.artifact(job_id,name),media_type='application/octet-stream',filename=name)
    @app.post('/api/backup',dependencies=secured)
    async def backup(request:BackupRequest):
        state=workbench.submit_operation('backup',{'repository':request.repository},request.request_id,secret=request.password);return {'job_id':state['id']}
    return app
