"""Explicit, hash-pinned acquisition of public build/recovery tools."""
from __future__ import annotations
import bz2,hashlib,os,platform,shutil,stat,time,urllib.request,zipfile
from pathlib import Path
from .common import BoundaryError,atomic_bytes,atomic_json,hash_file,lock,private_dir,read_json,check_cancel

def download_verified(path:Path,spec:dict,*,deadline_seconds:int=600,cancel=None)->Path:
    private_dir(path.parent)
    if path.exists():
        if path.stat().st_size==spec['size'] and hash_file(path)==spec['sha256']:return path
        raise BoundaryError('Existing asset differs from its pinned identity: '+path.name)
    partial=path.with_suffix(path.suffix+'.part');offset=partial.stat().st_size if partial.exists() else 0
    if offset>spec['size']:raise BoundaryError('Partial download exceeds its declared size.')
    headers={'User-Agent':'MARY-local-builder/0.3'}
    if offset:headers['Range']='bytes='+str(offset)+'-'
    request=urllib.request.Request(spec['url'],headers=headers);started=time.monotonic()
    with urllib.request.urlopen(request,timeout=45) as response:
        if offset and response.status!=206:offset=0
        mode='ab' if offset else 'wb'
        with partial.open(mode) as out:
            total=offset
            while True:
                check_cancel(cancel)
                if time.monotonic()-started>deadline_seconds:raise BoundaryError('Download deadline reached; its partial bytes are retained for resume.')
                data=response.read(1024*1024)
                if not data:break
                total+=len(data)
                if total>spec['size']:raise BoundaryError('Downloaded bytes exceed the supplier size.')
                out.write(data)
            out.flush();os.fsync(out.fileno())
    if partial.stat().st_size!=spec['size'] or hash_file(partial)!=spec['sha256']:raise BoundaryError('Download did not match the pinned artifact. No executable was activated.')
    os.replace(partial,path);return path

def restic_path(root:Path,*,install:bool=False)->Path:
    bin_dir=private_dir(root/'runtime/bin');target=bin_dir/('restic.exe' if os.name=='nt' else 'restic');receipt=bin_dir/'restic.json'
    known=read_json(receipt)
    if target.exists():
        if not known or hash_file(target)!=known['executable_sha256']:raise BoundaryError('Recovery executable identity changed.')
        return target
    if not install:raise BoundaryError('Prepare the recovery tool first: mary-workbench tools install. This is an explicit public download.')
    with lock(root,'restic-install'):
        platform_name={'Linux':'linux','Darwin':'darwin','Windows':'windows'}.get(platform.system());arch={'x86_64':'amd64','amd64':'amd64','aarch64':'arm64','arm64':'arm64'}.get(platform.machine().lower())
        if not platform_name or not arch:raise BoundaryError('No pinned recovery executable for this platform.')
        manifest=read_json(Path(__file__).with_name('binary-suppliers.json'));supplier=manifest['tools']['restic'];suffix='zip' if os.name=='nt' else 'bz2';name=f'restic_0.19.1_{platform_name}_{arch}.{suffix}'
        if name not in supplier['assets']:raise BoundaryError('This architecture needs a separately pinned restic binary.')
        asset=download_verified(root/'runtime/downloads'/name,supplier['assets'][name])
        if suffix=='bz2':
            with bz2.open(asset,'rb') as f:data=f.read(64*1024**2+1)
        else:
            with zipfile.ZipFile(asset) as z:
                candidates=[x for x in z.infolist() if Path(x.filename).name.lower().endswith('.exe')]
                if len(candidates)!=1 or candidates[0].file_size>64*1024**2:raise BoundaryError('Unexpected recovery archive layout.')
                data=z.read(candidates[0])
        if len(data)>64*1024**2:raise BoundaryError('Recovery executable exceeds its bound.')
        atomic_bytes(target,data,replace=False)
        if os.name=='posix':target.chmod(0o700)
        atomic_json(receipt,{'supplier':supplier['repository'],'version':supplier['version'],'archive':name,'archive_sha256':supplier['assets'][name]['sha256'],'executable_sha256':hash_file(target)})
        return target
