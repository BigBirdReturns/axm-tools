"""Wait boundedly for the existing Pages deployment, then verify exact release bytes."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib,json,os,time
root=Path(__file__).resolve().parents[1]
base='https://bigbirdreturns.github.io/axm-tools/procedure-reuse/'
manifest=json.loads((root/'v1/manifest.json').read_text())
files=['index.html','PROMPT.txt','landing.js','publication.json','v1/manifest.json']+['v1/'+name for name in manifest['sha256']]
expected={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
last='not attempted'
for attempt in range(48):
    try:
        observed={}
        for name in files:
            req=Request(base+name,headers={'Cache-Control':'no-cache','User-Agent':'AXM-procedure-reuse-release-check/1'})
            with urlopen(req,timeout=15) as response:
                if response.geturl()!=base+name: raise RuntimeError('Unexpected redirect')
                observed[name]=hashlib.sha256(response.read(2_000_000)).hexdigest()
        if observed!=expected: raise RuntimeError('Public bytes have not caught up with this release')
        result={'schema':'axm/procedure-reuse-public-readback@1','verified_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'base':base,'sha256':observed,'all_match':True}
        out=Path(os.environ.get('EVIDENCE_DIR','/tmp/axm-procedure-reuse-evidence'));out.mkdir(parents=True,exist_ok=True)
        (out/'public-readback.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2));break
    except Exception as e:
        last=str(e);print(f'Attempt {attempt+1}: {last}',flush=True)
        if attempt<47: time.sleep(5)
else:
    raise SystemExit('Public read-back did not verify within the bounded deployment window: '+last)
