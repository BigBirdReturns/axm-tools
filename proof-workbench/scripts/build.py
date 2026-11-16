#!/usr/bin/env python3
"""Deterministic source delivery; no network, model, credentials or execution."""
import hashlib,json,os,stat,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()
def source_paths():
 return [p for p in sorted(ROOT.rglob('*')) if p.is_file() and not p.is_symlink() and 'downloads' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.relative_to(ROOT).as_posix()!='MANIFEST.json']
def build():
 paths=source_paths()
 manifest={'schema':'axm-proof-package/1','version':'0.1.0','files':{p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in paths},'meaning':'Exact source inventory; authenticate an external digest separately.'}
 (ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 dest=ROOT/'downloads';dest.mkdir(exist_ok=True)
 archive=dest/'axm-proof-workbench-0.1.0.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(paths+[ROOT/'MANIFEST.json']):
   i=zipfile.ZipInfo('axm-proof-workbench/'+p.relative_to(ROOT).as_posix(),date_time=(2026,11,15,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|0o644)<<16;i.compress_type=zipfile.ZIP_DEFLATED
   z.writestr(i,p.read_bytes())
 result={'schema':'axm-proof-download/1','filename':archive.name,'sha256':digest(archive.read_bytes()),'bytes':archive.stat().st_size,'manifest_sha256':digest((ROOT/'MANIFEST.json').read_bytes()),'files':len(paths)+1}
 (dest/'SHA256SUMS').write_text(result['sha256']+'  '+archive.name+'\n',encoding='utf-8')
 (dest/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result));return result
if __name__=='__main__':build()
