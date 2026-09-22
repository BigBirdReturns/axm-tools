"""One-time, byte-checked installation of the tested Hot Aisle 2.0.0 files.

The transport is a compressed UTF-8 source map, not an executable archive.
Only the declared tool files and its existing catalogue entries are changed.
"""
from __future__ import annotations
import base64
import hashlib
import json
import lzma
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_SHA = 'b2150d4f31fe7fffdaf2a247f87f089950f84443d662647dc7a890134578c398'
INDEX_SHA = 'cd79dc1b81740c682e1529d55c9d76f91ae8750b97abab676d5dfdd52c917e57'
ALLOWED = {'index.html', 'README.md', 'FORMATS.md', 'FIRST_CAMPAIGN.md', 'LICENSE', 'QUALIFICATION.json', 'data/prices.json', 'scripts/price_math.py', 'scripts/test_price_math.py', 'scripts/test_workbench.cjs', 'scripts/recompute.cjs', 'examples/synthetic-a.json', 'examples/synthetic-b.json', 'MANIFEST.json'}
PREIMAGES = {'index.html':'ed28df6e7843ecfe1056cbef6987ba243cbe53dc', 'README.md':'0cdbec89969143c993b7b4d7e44755ea3a11e338', 'FIRST_CAMPAIGN.md':'874d09f9ce57e8639c9a26b171dbd6e32c59b6e6', 'LICENSE':'b467cbe7abb41393367d11a4737a43fa39a2f136', 'data/prices.json':'de8f9c78bea6992515f135588eb158d6200243a0', 'scripts/price_math.py':'d629119a40fb97634bf749aa467c4f9abbdf070a', 'scripts/test_price_math.py':'e98224756b426257f180c8af8abb149609c4dd15'}

def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()

def git_sha(body: bytes) -> str:
    return hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()

def main() -> None:
    encoded = ''.join((ROOT / f'.github/hot-aisle-v2/source-{i:02}.b64').read_text().strip() for i in range(4))
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) != 33872 or sha(raw) != TRANSPORT_SHA:
        raise ValueError('Source transport checksum differs from the tested release')
    decoded = lzma.decompress(raw, memlimit=512*1024*1024)
    if len(decoded) != 112016:
        raise ValueError('Source map length differs')
    source = json.loads(decoded)
    if set(source) != ALLOWED or not all(isinstance(s, str) for s in source.values()):
        raise ValueError('Unexpected source-map members')
    payload = {name:text.encode('utf-8') for name,text in source.items()}
    manifest = json.loads(source['MANIFEST.json'])
    if set(manifest['files']) != ALLOWED-{'MANIFEST.json'}:
        raise ValueError('Manifest membership mismatch')
    for name, record in manifest['files'].items():
        if sha(payload[name]) != record['sha256'] or len(payload[name]) != record['bytes']:
            raise ValueError('Manifest mismatch: '+name)
    if sha(payload['index.html']) != INDEX_SHA:
        raise ValueError('Unexpected page bytes')
    tool = ROOT/'hot-aisle'
    for name,body in payload.items():
        target = tool/name
        if any(p.is_symlink() for p in [target, *target.parents]):
            raise ValueError('Symlinks are outside this release')
        if target.exists() and target.read_bytes() != body:
            if name not in PREIMAGES or git_sha(target.read_bytes()) != PREIMAGES[name]:
                raise ValueError('Concurrent tool edit requires reconciliation: '+name)
        elif not target.exists() and name in PREIMAGES:
            raise ValueError('Expected baseline file is missing: '+name)
    catalogue = ROOT/'README.md'
    readme = catalogue.read_text(encoding='utf-8')
    row = '| [`hot-aisle/`](hot-aisle/) | Import vLLM results, account for the billable allocation, compare compatible trials and export a customer report with source-bound calculations | [Build a workload report](https://bigbirdreturns.github.io/axm-tools/hot-aisle/) |'
    readme, n = re.subn(r'^\| \[`hot-aisle/`\].*$',lambda _:row,readme,flags=re.M)
    if n != 1:
        raise ValueError('Expected exactly one existing Hot Aisle catalogue row')
    index_path = ROOT/'index.html'
    index = index_path.read_text(encoding='utf-8')
    pattern = r'(<div class="title"><a href="hot-aisle/">)[^<]*(</a></div>\s*<div class="desc">)[^<]*(</div>\s*<a class="open" href="hot-aisle/">)[^<]*(</a>)'
    def card(m):
        return m[1]+'Hot Aisle · Workload Report'+m[2]+'Drop existing vLLM results, set the billable allocation and export a customer report. Includes repeated trials, optional latency and evaluator gates, compatible-workload comparison, and source-file verification. Imported evidence, not an independently run GPU benchmark.'+m[3]+'Build a workload report →'+m[4]
    index, n = re.subn(pattern,card,index)
    if n != 1:
        raise ValueError('Expected exactly one existing Hot Aisle homepage card')
    continuity_path = ROOT/'CONTINUITY.md'
    continuity = continuity_path.read_text(encoding='utf-8')
    entry = '- `hot-aisle/` (updated 2026-09-22): v2 imports existing vLLM results, applies optional per-request gates and exports customer HTML plus source-bound calculation evidence. Repeats, compatibility holds and local recomputation are implemented; hardware benchmarks remain unexecuted. Standalone HTML, no uploads or scheduled work.'
    continuity, n = re.subn(r'^- `hot-aisle/`.*$', lambda _:entry, continuity, flags=re.M)
    if n != 1:
        raise ValueError('Expected one Hot Aisle continuity entry')
    for name,body in payload.items():
        target = tool/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(body)
    catalogue.write_text(readme,encoding='utf-8',newline='\n')
    index_path.write_text(index,encoding='utf-8',newline='\n')
    continuity_path.write_text(continuity,encoding='utf-8',newline='\n')
    archive = tool/'workload-report.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,body in sorted(payload.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,9,22,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,body,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or set(z.namelist()) != ALLOWED:
            raise ValueError('Distribution ZIP failed validation')
        for name,body in payload.items():
            if z.read(name) != body:
                raise ValueError('ZIP member differs: '+name)
    print(json.dumps({'version':'2.0.0','index_sha256':INDEX_SHA,'transport_sha256':TRANSPORT_SHA,'archive_sha256':sha(archive.read_bytes()),'files':len(payload)},indent=2))

if __name__ == '__main__':
    main()
