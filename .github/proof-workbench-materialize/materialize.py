"""One-time exact release transport. No private data or credential material."""
from pathlib import Path
import base64,hashlib,json,lzma,os,shutil,subprocess,sys
ROOT=Path.cwd(); D=ROOT/'.github/proof-workbench-materialize'; T=Path(os.environ['RUNNER_TEMP'])/'proof-exact-release';T.mkdir(exist_ok=False)
BASE='a6ceeea75c6ae1d20c7fae0acab27f7ab53663e6'
COMMIT='75ec3f92a0c1032ec9e319bf788f43f5aa440dad'
TREE='cad14d70d7b1da450ec648be23e98b24ce92cba7'
def sha(x):return hashlib.sha256(x).hexdigest()
def blobsha(x):return hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest()
def run(*a,**kw):return subprocess.run(list(a),check=True,**kw)
p0=(D/'part0.bin').read_bytes()
# Recorded transport normalization: remove one extraneous base64 S and restore padding.
# Original part, full compressed payload, patch, tree and commit hashes are all checked.
s=base64.b64encode((D/'part1.transport.bin').read_bytes()).decode();assert len(s)==10924 and s[625]=='S'
p1=base64.b64decode(s[:625]+s[626:]+'=',validate=True)
p2=b''.join((D/('part2'+c+'.bin')).read_bytes() for c in 'abcd');p3=(D/'part3.bin').read_bytes()
for data,expected in [(p0,'a87f4717e2b15ee460151a9a73941c640c04d16e'),(p1,'fcffbcdbb9a97a0a39d11a1a7aa28c52ee779dcb'),(p2,'f8960607b601fe9ffac945ca4c94425ffe88fd37'),(p3,'f1db3f42fd02222b1a043eb2a68e0774e62b577f')]:assert blobsha(data)==expected
packed=p0+p1+p2+p3;assert sha(packed)=='38eae8beadaef892f2fd95727f9c5afa977d2b7be7cacff4262c1ba2f6a8e663'
patch=lzma.decompress(packed);assert len(patch)==99910 and sha(patch)=='3e90ea0a66a25596690459833556da1f3ca4d37e8eec6b119a9f08302acca58d'
patchfile=T/'exact.patch';patchfile.write_bytes(patch)
body=base64.b64decode('dHJlZSBjYWQxNGQ3MGQ3YjFkYTQ1MGVjNjQ4YmUyM2U5OGIyNGNlOTJjYmE3CnBhcmVudCBhNmNlZWVhNzVjNmFlMWQyMGM3ZmFlMGFjYWIyN2Y3YWI1MzY2M2U2CmF1dGhvciBCaWdCaXJkUmV0dXJucyA8YmlnYmlyZHJldHVybnNAcHJvdG9uLm1lPiAxNzk0Nzg3NTMxICswMDAwCmNvbW1pdHRlciBCaWdCaXJkUmV0dXJucyA8YmlnYmlyZHJldHVybnNAcHJvdG9uLm1lPiAxNzk0Nzg3NTMxICswMDAwCgpQYWNrYWdlIHRocmVlIG5hdGl2ZSBwcm9vZiB3b3JrZmxvd3Mgd2l0aCBsb2NhbCBidXllciBzY29waW5nIGFuZCBldmlkZW5jZS1nYXRlZCBvdXRyZWFjaAo=')
assert hashlib.sha1(b'commit '+str(len(body)).encode()+b'\0'+body).hexdigest()==COMMIT
run('git','checkout','--detach',BASE)
run('git','apply','--index',str(patchfile))
P=ROOT/'proof-workbench';(P/'sources').mkdir(exist_ok=True)
for src,dest in [('cesmii-proof/source.zip','i3x.zip'),('decision-floor/downloads/AXM_Decision_Floor_Evaluation_v0.3.0.zip','decision-floor.zip'),('bosc-delivery-lab/downloads/AXM-BOSC-Replay.zip','receptionist.zip')]:shutil.copyfile(ROOT/src,P/'sources'/dest)
run(sys.executable,'-B',str(P/'scripts/build.py'))
archive=P/'downloads/axm-proof-workbench-0.1.0.zip'
assert sha(archive.read_bytes())=='3a5c7eb46d5a375126f9a0933e71c84ff2fe8d96a03f3237d671fc27edca2a4f','Distribution byte mismatch'
assert sha((P/'MANIFEST.json').read_bytes())=='321c078814275dd85ee3e4055dc08e28febb69062a49a00edebff5698a194c65'
run(sys.executable,'-B',str(P/'proof.py'),'verify')
run(sys.executable,'-B','-m','unittest','discover','-s',str(P/'tests'),'-v')
run(sys.executable,'-B',str(P/'proof.py'),'qualify','--output',str(T/'native-run'))
run('git','add','proof-workbench','index.html','README.md','CONTINUITY.md','.github/workflows/proof-workbench.yml','.github/receipts/proof-workbench-20261115.json')
assert subprocess.check_output(['git','write-tree'],text=True).strip()==TREE,'Source tree changed'
assert subprocess.check_output(['git','hash-object','-t','commit','-w','--stdin'],input=body).decode().strip()==COMMIT
run('git','push','origin',COMMIT+':refs/heads/publish/proof-workbench-20261115')
print(json.dumps({'status':'PASS','commit':COMMIT,'tree':TREE,'zip_sha256':sha(archive.read_bytes()),'main_updated':False}))
