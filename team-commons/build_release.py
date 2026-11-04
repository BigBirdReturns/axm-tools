#!/usr/bin/env python3
"""Rebuild committed public downloads from this tool's source, using only stdlib + Node.
The fixed timestamp belongs to synthetic fixtures, not measured execution.
"""
from pathlib import Path
from urllib.parse import quote
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent

def write_zip(path,files):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,body in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,body.encode('utf-8'),compresslevel=9)

def main():
    source={name:(ROOT/name).read_text(encoding='utf-8') for name in ['index.html','style.css','core.js','app.js','assets/favicon.svg']}
    offline=source['index.html'].replace("script-src 'self';style-src 'self';img-src 'self' data:","script-src 'unsafe-inline';style-src 'unsafe-inline';img-src data:")
    offline=offline.replace('<link rel="stylesheet" href="style.css">','<style>'+source['style.css']+'</style>')
    offline=offline.replace('<script src="core.js"></script>','<script>'+source['core.js']+'</script>')
    offline=offline.replace('<script src="app.js"></script>','<script>'+source['app.js']+'</script>')
    offline=offline.replace('<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">','<link rel="icon" href="data:image/svg+xml,'+quote(source['assets/favicon.svg'])+'">')
    offline=offline.replace('href="downloads/','href="https://bigbirdreturns.github.io/axm-tools/team-commons/downloads/')
    offline=offline.replace('href="../acceptance.html"','href="https://bigbirdreturns.github.io/axm-tools/acceptance.html"').replace('href="../"','href="https://bigbirdreturns.github.io/axm-tools/"')
    target=ROOT/'downloads';target.mkdir(exist_ok=True)
    (target/'MARY-Team-Commons.html').write_text(offline,encoding='utf-8')
    script="""const c=require('./core.js'); (async()=>{const packets=[];for(const role of ['inventory','maintenance','allocation']){const p=await c.makePacket(c.fragments[role],'Synthetic fixture author');p.release.at='2026-11-03T00:00:00.000Z';const {packet_sha256,...body}=p;p.packet_sha256=await c.sha(c.canonical(body));await c.verifyPacket(p);packets.push(p);}const lesson={schema:'mary-data-mapping/1',author:'inventory-team',reviewed_by:'Synthetic fixture reviewer',scope:'synthetic-exercise',mapping:{part:'sku',on_hand:'total_units',serviceable:'usable_units'},credit:'Inventory team field mapping; the recipient retains its own acceptance responsibility.',tests:['Explicit missing quantities','One fresh synthetic schema'],claim:'Field names only; no code, model weights, private prompts or supplier data.'};lesson.sha256=await c.sha(c.canonical(lesson));await c.verifyLesson(lesson);console.log(JSON.stringify({packets,lesson}));})().catch(e=>{console.error(e);process.exit(1)});"""
    result=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,timeout=30,check=True)
    fixtures=json.loads(result.stdout)
    for role in ['inventory','maintenance','allocation']:
        packet=next(p for p in fixtures['packets'] if p['role']==role)
        files={'OPEN-TEAM-COMMONS.html':offline,'team-contribution.json':json.dumps(packet,indent=2)+'\n','START-HERE.txt':f'MARY TEAM COMMONS / {role.upper()} BROWSER KIT\n\nOpen OPEN-TEAM-COMMONS.html in a modern browser. The complete synthetic exercise is included. Import team-contribution.json through Carry forward > Import a team contribution. Export the workspace before closing.\n\nNo account, Python, model download or terminal is required. All role recipes are synthetic and inspectable; this is not private tenant isolation. The full MARY assistant and its original portable core are separate products, not bundled here. Online navigation and download links require the Internet; the exercise itself does not.\n'}
        if role=='inventory':files['field-mapping-lesson.json']=json.dumps(fixtures['lesson'],indent=2)+'\n'
        write_zip(target/(role+'-browser-kit.zip'),files)
    # Register this tool once without replacing any unrelated authored content.
    p=REPO/'index.html';text=p.read_text(encoding='utf-8')
    if 'href="team-commons/"' not in text:
        anchor='<div class="tool">'
        if anchor not in text:raise ValueError('Tool index anchor changed; reconcile rather than replace.')
        entry='<div class="tool">\n  <div class="title"><a href="team-commons/">MARY Team Commons · Collective Intelligence Lab</a></div>\n  <div class="desc">Equip the room, combine three teams’ evidence, apply a linked correction, share a tested method and restore the work on another seat. A runnable local-browser exercise with offline copies and synthetic team kits. No account, model download or terminal required.</div>\n  <a class="open" href="team-commons/">Run the collective-intelligence lab →</a>\n</div>\n\n'
        p.write_text(text.replace(anchor,entry+anchor,1),encoding='utf-8')
    p=REPO/'README.md';text=p.read_text(encoding='utf-8')
    if '| [`team-commons/`]' not in text:
        rows=text.splitlines();i=rows.index('| Tool | What it does | Interface |')
        rows.insert(i+2,'| [`team-commons/`](team-commons/) | Runnable collective-intelligence lab: complementary team evidence, linked corrections, reviewed method transfer, verified workspace recovery and offline browser kits | [MARY Team Commons](https://bigbirdreturns.github.io/axm-tools/team-commons/) |')
        p.write_text('\n'.join(rows)+'\n',encoding='utf-8')
    p=REPO/'identity/axm/PROPERTY-FLAVORS.md';text=p.read_text(encoding='utf-8')
    if '## MARY Team Commons' not in text:
        anchor='## When you add or move a property'
        if anchor not in text:raise ValueError('Identity registry anchor changed.')
        entry='## MARY Team Commons\n\n`axm-tools/team-commons/` uses Cream Editorial for the working exercise and Dark Ecosystem for the team station section. Bone/paper, olive and pine identify collaborative state; ember remains reserved for findings and errors. Barlow Condensed / IBM Plex are named with local system fallbacks, with no downloaded font dependency. The contribution-diagram favicon is not the SCG mark.\n\n'
        p.write_text(text.replace(anchor,entry+anchor,1),encoding='utf-8')
    manifest={'release':'team-commons/0.2.0','files':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}for p in sorted(ROOT.rglob('*'))if p.is_file()and p.name!='manifest.json'and '__pycache__'not in p.parts]}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','public_downloads':4,'files':len(manifest['files']),'scope':'Synthetic browser assets only'}))
if __name__=='__main__':main()
