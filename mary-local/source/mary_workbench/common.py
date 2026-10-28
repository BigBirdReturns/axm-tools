"""Small local IO boundaries; cryptographic custody remains Genesis's."""
from __future__ import annotations
import hashlib, json, os, re, stat, sys, time, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from filelock import FileLock, Timeout

class BoundaryError(RuntimeError):
    pass
class Cancelled(BoundaryError):
    pass

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def canonical(value: Any) -> bytes:
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def hash_file(path: Path) -> str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def reparse(path: Path) -> bool:
    p=Path(path).absolute()
    while True:
        try:
            s=p.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:return True
        except FileNotFoundError: pass
        if p.parent==p:return False
        p=p.parent

def local_path(path: Path, *, exists: bool=False) -> Path:
    path=Path(path).expanduser().absolute()
    if reparse(path):raise BoundaryError('Symlink/reparse paths require a separately supported source adapter.')
    path=path.resolve(strict=exists)
    return path

def private_dir(path: Path) -> Path:
    path=local_path(path)
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.is_dir():raise BoundaryError('Expected an owned directory.')
    if os.name=='posix':
        if path.stat().st_uid!=os.getuid():raise BoundaryError('Workspace is owned by another operating-system user.')
        path.chmod(0o700)
    return path

def fsync_dir(path: Path) -> None:
    if os.name=='posix':
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

def atomic_bytes(path: Path,data: bytes,*,replace: bool=True) -> None:
    path=Path(path)
    private_dir(path.parent)
    if reparse(path):raise BoundaryError('Refusing a link at an output path.')
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.pending')
    try:
        with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if not replace and path.exists():raise FileExistsError(path)
        os.replace(tmp,path);fsync_dir(path.parent)
    finally:tmp.unlink(missing_ok=True)
def atomic_json(path:Path,value:Any,*,replace:bool=True)->None:
    atomic_bytes(path,canonical(value)+b'\n',replace=replace)
def read_json(path:Path,default:Any=None,max_bytes:int=16*1024*1024)->Any:
    path=Path(path)
    if not path.exists():return default
    if path.stat().st_size>max_bytes:raise BoundaryError('State exceeds its declared read bound.')
    try:
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d:raise ValueError('duplicate JSON key')
                d[k]=v
            return d
        return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (ValueError,UnicodeError) as e:raise BoundaryError('Malformed state: '+path.name) from e

@contextmanager
def lock(root:Path,name:str,timeout:float=1)->Iterator[None]:
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',name):raise BoundaryError('Invalid lock name.')
    directory=private_dir(Path(root)/'locks');p=directory/(name+'.lock')
    if reparse(p):raise BoundaryError('Invalid lock path.')
    owner=FileLock(str(p),mode=0o600)
    try:owner.acquire(timeout=timeout)
    except Timeout as e:raise BoundaryError('Another operation owns '+name+'. Retry that same operation after it finishes.') from e
    try:yield
    finally:owner.release()

def check_cancel(event:Any=None)->None:
    if event is not None and event.is_set():raise Cancelled('Stopped by the owner; committed work is retained.')

def default_home()->Path:
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'MARY'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/MARY'
    return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'mary'

def init_home(root:Path,owner:str|None=None)->dict:
    root=local_path(root)
    if root==Path(root.anchor) or root==Path.home().resolve():raise BoundaryError('Choose a dedicated workspace, not a drive or home directory.')
    root=private_dir(root)
    for d in ['keys','imports','shards','work','uploads','derived','runtime','recovery']:private_dir(root/d)
    with lock(root,'initialize'):
        config=read_json(root/'settings.json')
        if config is None:
            import getpass,secrets
            config={'schema':'mary/workspace-settings@1','workspace_id':uuid.uuid4().hex,'owner':owner or getpass.getuser(),'created_at':now(),'source_roots':[], 'model':None,'context_tokens':8192,'max_output_tokens':1536,'max_model_seconds':180,'max_source_bytes':64*1024*1024,'max_import_bytes':512*1024*1024,'max_workspace_bytes':20*1024**3,'max_import_files':3000,'history_policy':'current-by-default; explicit history or withdrawal','network_policy':'local model only unless owner explicitly configures a private-network endpoint'}
            atomic_json(root/'settings.json',config,replace=False)
            atomic_bytes(root/'keys/web.token',secrets.token_urlsafe(32).encode(),replace=False)
        if not isinstance(config,dict) or config.get('schema')!='mary/workspace-settings@1':raise BoundaryError('Unsupported workspace settings.')
        if owner and owner!=config['owner']:raise BoundaryError('Workspace already belongs to a different declared owner.')
    return config

def validate_id(value:str)->str:
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',value):raise BoundaryError('Invalid durable request identity.')
    return value

def contained(root:Path,relative:str)->Path:
    if not isinstance(relative,str) or '\\' in relative or ':' in relative or relative.startswith('/') or any(p in {'','..','.'} for p in relative.split('/')):raise BoundaryError('Unsafe relative artifact path.')
    result=local_path(Path(root)/relative)
    if not result.is_relative_to(Path(root).resolve()):raise BoundaryError('Artifact escaped its owner directory.')
    return result


def memory_budget()->dict:
    """Physical observations plus actual inherited cgroup memory limits."""
    import psutil
    mem=psutil.virtual_memory();total=mem.total;available=mem.available;limits=[]
    if sys.platform.startswith('linux'):
        try:
            relative=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
            base=Path('/sys/fs/cgroup');current=base/relative.lstrip('/')
            while current.is_relative_to(base):
                maximum=current/'memory.max';used=current/'memory.current'
                if maximum.exists() and used.exists():
                    raw=maximum.read_text().strip()
                    if raw!='max':
                        cap=int(raw);usage=int(used.read_text());limits.append({'bytes':cap,'current_bytes':usage});total=min(total,cap);available=min(available,max(0,cap-usage))
                if current==base:break
                current=current.parent
        except (OSError,ValueError,StopIteration):pass
    return {'physical_bytes':mem.total,'physical_available_bytes':mem.available,'effective_total_bytes':total,'effective_available_bytes':available,'inherited_limits':limits}
