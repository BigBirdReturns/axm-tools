"""Finite, owned subprocesses. Process bounds are not a hostile-code sandbox."""
from __future__ import annotations
import json, os, signal, subprocess, sys, time, uuid
import psutil
from pathlib import Path
from typing import Any
from .common import BoundaryError, Cancelled, atomic_json, canonical, check_cancel, private_dir, read_json

def clean_environment() -> dict[str,str]:
    keep={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','TMPDIR','HOME','USERPROFILE','LOCALAPPDATA','APPDATA','LANG','LC_ALL','VIRTUAL_ENV','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','PYTHONUTF8','SSL_CERT_FILE','SSL_CERT_DIR'}
    env={k:v for k,v in os.environ.items() if k.upper() in keep}
    env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    return env

def run_worker(root:Path,operation:str,payload:dict,*,seconds:int=120,cancel:Any=None)->dict:
    folder=private_dir(Path(root)/'runtime'/('call-'+uuid.uuid4().hex))
    request=folder/'request.json';result=folder/'result.json'
    atomic_json(request,{'operation':operation,'payload':payload,'result':str(result),'memory_mib':4096,'cpu_seconds':max(20,seconds)})
    command=[sys.executable,'-B','-m','mary_workbench.worker',str(request)]
    logs=[];process=None;started=time.monotonic();failed=None
    try:
        logs=[(folder/'stdout.log').open('wb'),(folder/'stderr.log').open('wb')]
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=logs[0],stderr=logs[1],env=clean_environment(),start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        while process.poll() is None:
            check_cancel(cancel)
            try:
                monitored=psutil.Process(process.pid);members=[monitored,*monitored.children(recursive=True)]
                rss=sum(x.memory_info().rss for x in members if x.is_running())
                cpu=sum(sum(x.cpu_times()[:2]) for x in members if x.is_running())
                if rss>4096*1024**2:raise BoundaryError('Worker resident memory exceeded 4 GiB.')
                if cpu>max(20,seconds):raise BoundaryError('Worker CPU allowance exceeded.')
            except psutil.NoSuchProcess:pass
            except psutil.AccessDenied as exc:raise BoundaryError('Worker usage cannot be observed; execution stopped.') from exc
            if time.monotonic()-started>seconds:raise BoundaryError('Worker deadline exceeded; committed work remains available.')
            if any(p.stat().st_size>2*1024*1024 for p in [folder/'stdout.log',folder/'stderr.log']):raise BoundaryError('Worker output exceeded its bound.')
            time.sleep(.05)
        if process.returncode:
            err=(folder/'stderr.log').read_text(encoding='utf-8',errors='replace')[-1000:]
            raise BoundaryError('Worker failed: '+err)
        value=read_json(result,max_bytes=8*1024*1024)
        if not isinstance(value,dict):raise BoundaryError('Worker returned no complete result.')
        if not value.get('ok'):raise BoundaryError(str(value.get('error','Worker refused input.')))
        return value['result']
    finally:
        # Cleanup does not depend on successful statistics, JSON parsing or logging.
        if process is not None and process.poll() is None:
            try:
                if os.name=='posix':os.killpg(process.pid,signal.SIGTERM)
                else:process.terminate()
            except ProcessLookupError:pass
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
                    else:process.kill()
                except ProcessLookupError:pass
                process.wait(timeout=3)
        for f in logs:f.close()
        # Requests can contain private context. Retain only the result and short error;
        # task owner stores selected useful artifacts, not repeated prompts.
        request.unlink(missing_ok=True)
        if result.exists() and result.stat().st_size<8*1024*1024:result.unlink()
        for p in [folder/'stdout.log',folder/'stderr.log']:
            if p.exists() and p.stat().st_size==0:p.unlink()
        try:folder.rmdir()
        except OSError:pass
