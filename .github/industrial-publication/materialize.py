#!/usr/bin/env python3
"""One-time exact-source transfer into an isolated publication branch."""
import hashlib, io, json, os, pathlib, shutil, subprocess, tarfile
BASE='cd12f46a621b2986d8670342ddb8ca866f7d8cd1'
SEED='51d3c37d3bbe2dd960ac3bfb1f124d51559a77dba6e79f13459a003d92a135f6'
SOURCE='8a5369e55f755ca409b3a859043cde0b3747724f'
FILES={
 'industrial-continuity/README.md':'d337e2bb14c451f554accdd04396b07178e5af5b6929d96c8e1d63ddb57a15e3',
 'industrial-continuity/app.js':'70758280fe5a74dd8e1e6763caf25432909f169fb892ab981ec0d89aa82137ef',
 'industrial-continuity/build.py':'88301888ec3f51515e85dbac34c0ad2ca9d018a0d413c9307758c62a1b7aa088',
 'industrial-continuity/engine.js':'130471df834984b42a51719653d754a8ce28e3f24aa45da1dd58adbfb4e1e794',
 'industrial-continuity/index.html':'a56b2fab11b2929c89e1bad8b0a82eb9217cc7451234337bf7a1def621a595a8',
 'industrial-continuity/research/ASSESSMENT.md':'d781666c48aff3d3b5becc2c4e6aecdf86fa02f98260a5b8a4d4648c7340881a',
 'industrial-continuity/style.css':'d8f190625ebc2ff4ed1d2a47821f8db0bbae0e800b0625029ae6fb4dae418c85',
 'industrial-continuity/tests/browser.cjs':'53a6541a4fcc3f917c9db0d4bb334e0a6923ce91a255fb79a1099498d8fddf4c',
 'industrial-continuity/tests/verify.cjs':'5f96982ececcec12f07300ef77fa0e2b959b87e6651be7623c17b8d9f50a4ef0',
 'industrial-continuity/verify-handoff.cjs':'866b97c49722e2182255bc1e532b3040e1e21e76d7f45dfed92b4c6b47c2e28a'}
workspace=pathlib.Path(os.environ['GITHUB_WORKSPACE']); dest=pathlib.Path(os.environ['RUNNER_TEMP'])/'industrial-release'
blob=b''.join((workspace/'.github/industrial-publication'/('part'+str(i))).read_bytes() for i in range(4))
assert len(blob)==27140 and hashlib.sha256(blob).hexdigest()==SEED, 'Publication seed mismatch'
subprocess.run(['git','worktree','add','--detach',str(dest),BASE],cwd=workspace,check=True)
with tarfile.open(fileobj=io.BytesIO(blob),mode='r:xz') as archive:
 members=archive.getmembers(); assert {m.name for m in members}==set(FILES)
 for member in members:
  assert member.isfile() and member.size<1000000
  data=archive.extractfile(member).read(); assert hashlib.sha256(data).hexdigest()==FILES[member.name], member.name
  target=dest/member.name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
root=dest/'industrial-continuity'; donor=dest/'cesmii-proof/commons-core.js'
assert hashlib.sha256(donor.read_bytes()).hexdigest()=='0158ea96c0c99a4f479e37573bacf26916348318e2811b75196ce390cab36cdd'
shutil.copyfile(donor,root/'commons-core.js')
page=root/'index.html'; html=page.read_text()
url='https://bigbirdreturns.github.io/axm-tools/industrial-continuity/'
meta='<meta name="description" content="Run a source-bound industrial decision, change the economics, and independently replay its complete handoff. Working AXM example, source and tests included."><meta property="og:title" content="AXM | Industrial Continuity"><meta property="og:description" content="Change the input. Recompute the decision. Take the evidence with you."><meta property="og:type" content="website"><meta property="og:url" content="'+url+'"><meta property="og:image" content="'+url+'preview.png">'
assert html.count('<title>AXM | Industrial Continuity</title>')==1
html=html.replace('<title>AXM | Industrial Continuity</title>','<title>AXM | Industrial Continuity</title>'+meta)
anchor='<p id="export-detail" class="mono footnote"></p>'
links='<div class="inline-actions"><a class="file-button" href="'+url+'industrial-continuity-source.zip" download>Download source and tests</a><a href="'+url+'research/ASSESSMENT.md">Research and scope</a><a href="'+url+'data/qualification.json">Logic receipt</a><a href="'+url+'data/browser-qualification.json">Browser receipt</a></div>'
assert html.count(anchor)==1; html=html.replace(anchor,anchor+links); page.write_text(html)
index=dest/'index.html'; text=index.read_text(); marker='<!-- proof-workbench-card:start -->'; assert text.count(marker)==1 and 'industrial-continuity/' not in text
card='''<!-- industrial-continuity-card:start -->
<div class="tool">
  <div class="title"><a href="industrial-continuity/">Industrial Continuity · From bottleneck to next shift</a></div>
  <div class="desc">Run a six-source industrial decision, change the order economics, retain stale reviews and independently replay both decisions in a clean offline client. Synthetic operations, actual CSV intake, adversarial verification and downloadable source.</div>
  <a class="open" href="industrial-continuity/">Run the workbench and keep the evidence →</a>
</div>
<!-- industrial-continuity-card:end -->

'''
index.write_text(text.replace(marker,card+marker))
readme=dest/'README.md'; text=readme.read_text(); marker='|------|--------------|-----------|'; assert text.count(marker)==1
row='| [`industrial-continuity/`](industrial-continuity/) | Source-bound industrial planning, correction-induced stale decisions and reviews, actual local CSV intake, independently executable offline handoff, source and adversarial tests | [Run Industrial Continuity]('+url+') |'
readme.write_text(text.replace(marker,marker+'\n'+row))
continuity=dest/'CONTINUITY.md'
with continuity.open('a') as f:f.write('\n\n## Industrial Continuity publication, 17 November 2026\n\n`industrial-continuity/` is a self-contained, independently implemented six-source industrial decision and handoff workbench. Its bounded two-product/two-stage calculation, correction history, declared reviews and offline receiver have separate logic and browser qualification. Public-source research informs the workflow and original visual design; all operational inputs are synthetic. No vendor backend, real identities, production authority or measured customer outcome is claimed. The exact retained Team Commons donor is copied and hashed, with no cross-directory runtime dependency. The source kit, reports and original owner provenance remain inspectable; private correspondence and raw research captures are excluded. Existing shared publication gates and unrelated tools remain unchanged.\n')
(root/'SOURCE_PROVENANCE.json').write_text(json.dumps({'schema':'axm-industrial-publication-source/1','source_commit':SOURCE,'public_base_commit':BASE,'seed_sha256':SEED,'seed_files':FILES,'publication_edits':['Share metadata and direct source/report links','AXM Tools directory and continuity registration'],'engine_unchanged':True,'data':'Synthetic fixtures and fresh automated qualification; no private correspondence'},indent=2)+'\n')
print(json.dumps({'status':'EXACT_SOURCE_MATERIALIZED','directory':str(dest),'files':len(FILES),'source_commit':SOURCE}))
