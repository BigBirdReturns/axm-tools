#!/usr/bin/env python3
from __future__ import annotations
import argparse,base64,datetime as dt,hashlib,io,json,lzma,shutil,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--receipt',type=Path);a=parser.parse_args()
expected=json.loads((root/'PAYLOAD_RECEIPT.json').read_text());part_paths=sorted(root.glob('SOURCE_PAYLOAD.tar.xz.b64.part*'));checks=[]
def check(n,c,d=''):checks.append({'name':n,'pass':bool(c),'detail':d})
def sh(b):return hashlib.sha256(b).hexdigest()
expected_parts=expected.get('carrier_parts',[]);check('carrier part count',len(part_paths)==expected.get('carrier_part_count'),len(part_paths))
for idx,p in enumerate(part_paths):
 e=expected_parts[idx] if idx<len(expected_parts) else {};raw=p.read_bytes();check(f'part {idx+1:02d} path',p.name==e.get('path'),p.name);check(f'part {idx+1:02d} bytes',len(raw)==e.get('bytes'),len(raw));check(f'part {idx+1:02d} sha256',sh(raw)==e.get('sha256'),sh(raw))
raw_b64=b''.join(p.read_bytes().strip() for p in part_paths);check('base64 bytes',len(raw_b64)==expected['base64_bytes'],len(raw_b64));check('base64 sha256',sh(raw_b64)==expected['base64_sha256'],sh(raw_b64))
try:xz=base64.b64decode(raw_b64,validate=True)
except Exception as e:xz=b'';check('base64 decode',False,str(e))
else:check('base64 decode',True)
check('xz bytes',len(xz)==expected['xz_bytes'],len(xz));check('xz sha256',sh(xz)==expected['xz_sha256'],sh(xz))
try:tar_raw=lzma.decompress(xz,format=lzma.FORMAT_XZ)
except Exception as e:tar_raw=b'';check('xz decode',False,str(e))
else:check('xz decode',True)
check('tar bytes',len(tar_raw)==expected['tar_bytes'],len(tar_raw));check('tar sha256',sh(tar_raw)==expected['tar_sha256'],sh(tar_raw))
unsafe=[];special=[];members=[]
if tar_raw:
 with tarfile.open(fileobj=io.BytesIO(tar_raw),mode='r:') as t:
  members=t.getmembers();seen=set()
  for m in members:
   p=Path(m.name);key=m.name.casefold()
   if p.is_absolute() or '..' in p.parts or ':' in p.parts[0]:unsafe.append(m.name)
   if key in seen:unsafe.append('duplicate:'+m.name)
   seen.add(key)
   if not m.isfile():special.append(m.name)
  check('member count',len(members)==expected['member_count'],len(members));check('safe paths',not unsafe,unsafe);check('regular files only',not special,special)
  if all(c['pass'] for c in checks):
   shutil.rmtree(a.destination,ignore_errors=True);a.destination.mkdir(parents=True)
   for m in members:
    target=a.destination/m.name;target.parent.mkdir(parents=True,exist_ok=True);f=t.extractfile(m);target.write_bytes(f.read() if f else b'');target.chmod(m.mode)
result={'schema':'manzanita/useful-plant-v30-source-replay-unpack@2','generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'result':'PASS' if all(c['pass'] for c in checks) else 'FAIL','checks_passed':sum(c['pass'] for c in checks),'checks_total':len(checks),'checks':checks,'destination':str(a.destination),'part_count':len(part_paths),'member_count':len(members),'public_route_effect':'none','release_authorized':False,'external_effect':'none'}
out=a.receipt or root/'UNPACK_RECEIPT.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(0 if result['result']=='PASS' else 1)
