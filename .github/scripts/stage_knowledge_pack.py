"""Publish one qualified, pinned public reference without changing other tool owners."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--source-commit',required=True);a=p.parse_args()
    source=a.source.resolve();actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if actual!=a.source_commit:raise SystemExit('Source commit mismatch')
    ref=source/'examples/knowledge-pack';web=ref/'web';release=json.loads((web/'release.json').read_text())
    native=json.loads((ref/'build/native-conformance.json').read_text());browser=json.loads((ref/'build/browser/browser-acceptance.json').read_text());wasm=json.loads((ref/'build/browser/wasm-conformance.json').read_text())
    if native.get('status')!='PASS' or native.get('cases')!=26:raise SystemExit('Native conformance not accepted')
    if wasm.get('status')!='PASS' or len(wasm.get('results',[]))!=26 or not all(x.get('pass') for x in wasm['results']):raise SystemExit('WebAssembly conformance not accepted')
    if len(browser.get('results',[]))<16 or not all(x.get('status')=='PASS' for x in browser['results']) or browser.get('errors'):raise SystemExit('Browser interaction not accepted')
    for name,expected in release['artifacts'].items():
        target=(web/name).resolve()
        if not target.is_relative_to(web.resolve()) or digest(target)!=expected:raise SystemExit('Public artifact hash mismatch: '+name)
    for path in web.rglob('*'):
        if path.is_symlink() or (path.is_file() and (path.suffix=='.key' or 'identity' in path.parts)):raise SystemExit('Unsafe publication inventory')
    dest=ROOT/'knowledge-pack'
    if dest.exists():
        marker=dest/'PUBLICATION.json'
        if not marker.is_file():raise SystemExit('An existing tool owns the destination; refusing replacement')
        shutil.rmtree(dest)
    shutil.copytree(web,dest)
    receipt={'version':'0.2.0','profile':'axm-pack-preview/0.1','source_repository':'BigBirdReturns/axm-core','source_commit':actual,'workflow_run':os.environ.get('GITHUB_RUN_ID'),'native_conformance_cases':26,'wasm_conformance_cases':26,'browser_checks':len(browser['results']),'offline_verification_exercised':any('network offline' in x['name'] for x in browser['results']),'source_archive':release['artifacts']['downloads/axm-knowledge-pack-source-0.2.0.zip'],'runtime':'Static browser files; all package verification runs locally in a WebAssembly worker. No file-upload endpoint.','trust':'Demo public key is distributed with the example. Independent publisher authentication is not claimed.'}
    if not receipt['offline_verification_exercised']:raise SystemExit('Offline browser control absent')
    (dest/'PUBLICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (dest/'README.md').write_text('# AXM Knowledge Pack\n\nPublic, local-browser reference for opening and verifying portable Genesis knowledge packages. Read exact evidence, inspect signed predecessor history, run actual tamper checks, and obtain the package, source kit, native readers, transport profile, and conformance cases.\n\nSource owner: https://github.com/BigBirdReturns/axm-core/tree/'+actual+'/examples/knowledge-pack\n\nPublication receipt: PUBLICATION.json. Build instructions: REPRODUCE.md. This directory contains generated static public artifacts only. No account, live backend, private signing key, or recurring data fetch belongs here.\n')
    index=ROOT/'index.html';text=index.read_text();marker='<!-- knowledge-pack-card:start -->'
    card='''<!-- knowledge-pack-card:start -->
<div class="tool">
  <div class="title"><a href="knowledge-pack/">AXM Knowledge Pack · Keep what you learned</a></div>
  <div class="desc">Open a real portable knowledge package, follow its evidence, inspect signed history and run actual tamper checks entirely in your browser. Public source, native readers, format description and reproducible conformance tests. No account, installation or file upload.</div>
  <a class="open" href="knowledge-pack/">Open the pack and build on the reference →</a>
</div>
<!-- knowledge-pack-card:end -->'''
    if marker in text:
        start=text.index(marker);end=text.index('<!-- knowledge-pack-card:end -->',start)+len('<!-- knowledge-pack-card:end -->');text=text[:start]+card+text[end:]
    else:
        if text.count('</header>')!=1:raise SystemExit('Directory insertion anchor changed')
        text=text.replace('</header>','</header>\n\n'+card,1)
    index.write_text(text)
    for name,heading,body in [('README.md','## Knowledge Pack public reference','[Open the browser demo](https://bigbirdreturns.github.io/axm-tools/knowledge-pack/) or [inspect its source and tests](https://github.com/BigBirdReturns/axm-core/tree/main/examples/knowledge-pack). Real local WebAssembly verification, downloadable packages and native readers, and a reproducible transport reference.'),('CONTINUITY.md','## Knowledge Pack publication, November 2026','`knowledge-pack/` is generated from the pinned public AXM Core reference by `.github/workflows/knowledge-pack-release.yml`. The owning source, compiler, tests and transport proposal remain in AXM Core. The static tool runs cryptographic verification in the visitor’s browser, has no upload endpoint, and exposes the actual downloadable artifacts and public conformance vectors. Its demo-key trust scope remains explicit. Existing Pages release gates and other tools are unchanged.')]:
        path=ROOT/name;bodytext=path.read_text()
        if heading not in bodytext:path.write_text(bodytext.rstrip()+'\n\n'+heading+'\n\n'+body+'\n')
    (ROOT/'.github/knowledge-pack-release-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
