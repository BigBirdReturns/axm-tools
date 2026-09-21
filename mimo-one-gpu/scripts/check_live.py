"""Verify each deployed source/kit byte with a bounded publication wait."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib, json, os, time
root=Path(__file__).resolve().parents[1]
base='https://bigbirdreturns.github.io/axm-tools/mimo-one-gpu/'
manifest=json.loads((root/'SOURCE-MANIFEST.json').read_text())
expected={**manifest['sha256'],'SOURCE-MANIFEST.json':hashlib.sha256((root/'SOURCE-MANIFEST.json').read_bytes()).hexdigest(),'mimo-one-gpu-kit.zip':hashlib.sha256((root/'mimo-one-gpu-kit.zip').read_bytes()).hexdigest()}
last='No request yet'
for attempt in range(48):
    try:
        observed={}
        for name,want in expected.items():
            req=Request(base+name,headers={'Cache-Control':'no-cache','User-Agent':'AXM-MiMo-release-check/1'})
            with urlopen(req,timeout=15) as response:
                if response.geturl()!=base+name: raise RuntimeError('Unexpected redirect')
                body=response.read(2000000)
            got=hashlib.sha256(body).hexdigest()
            if got!=want: raise RuntimeError('Public byte mismatch: '+name)
            observed[name]=got
        record={'schema':'axm/mimo-public-readback@1','verified_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'base':base,'all_match':True,'sha256':observed,'native_mimo':'NOT_RUN'}
        out=Path(os.environ.get('EVIDENCE_DIR','/tmp/mimo-one-gpu-evidence'));out.mkdir(parents=True,exist_ok=True)
        (out/'public-readback.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));break
    except Exception as error:
        last=str(error);print(f'Attempt {attempt+1}: {last}',flush=True)
        if attempt<47: time.sleep(5)
else: raise SystemExit('Publication did not verify: '+last)
