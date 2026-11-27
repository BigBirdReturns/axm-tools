"""Build SCHISM's self-contained application and exact recipient source package."""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
VERSION='2.0'
CONTRACT='f7cb1a8810a4a0c9af406c241fed7bfada2704c6f68ab9053f13af86cafc0e5d'
SOURCE='c8a35814556fe00f573485fef96848480d35f8b0'
LIVE='https://bigbirdreturns.github.io/axm-tools/schism/v2/'
sha=lambda b:hashlib.sha256(b).hexdigest()
def load(name):
    p=ROOT/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def write(name,body):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(body.encode('utf-8') if isinstance(body,str) else body)
def js(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
def package_files():
    excluded={'SCHISM-v2.0-source.zip','release-manifest.json','SHA256SUMS'}
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in excluded and '__pycache__' not in p.parts and p.suffix!='.pyc')

def build(preview=False):
    core=(ROOT/'vendor/commons-core.js').read_bytes();engine=(ROOT/'vendor/engine.js').read_bytes()
    assert sha(b'axm-industrial-engine/1\0'+engine+b'\0'+core)==CONTRACT
    receiver_sha=sha((ROOT/'runtime/receiver.py').read_bytes())
    binding=load('data/native-source-binding.json')
    bound=bool(binding) and all((ROOT/name).is_file() and sha((ROOT/name).read_bytes())==digest for name,digest in binding['runtime_files'].items())
    evidence={};native={}
    for key,label in [('linux','Linux'),('windows','Windows')]:
        r=load('data/'+key+'-qualification.json');native[key]=r
        status=r.get('status','PENDING') if r else 'PENDING'
        if r and (r.get('receiver_sha256')!=receiver_sha or r.get('contract_sha256')!=CONTRACT):status='STALE'
        if r and (r.get('case_register_sha256')!=sha((ROOT/'data/case-register.json').read_bytes()) or not bound or sha((ROOT/('data/'+key+'-qualification.json')).read_bytes())!=binding.get('receipts',{}).get(key)):status='STALE'
        evidence[key]={'status':status,'summary':f"{r['case_count']} acceptance/refusal cases; independent Python continuation; ordinary network APIs denied." if r else 'Native recipient qualification has not been recorded.',
                       'href':'data/'+key+'-qualification.json' if r else 'data/qualification.json',
                       'environment':r.get('environment') if r else None}
    paired=all(native.get(k) and evidence[k]['status']=='PASS' and native[k].get('roundtrip',{}).get('status')=='PASS' for k in ['linux','windows'])
    evidence['roundtrip']={'status':'PASS' if paired else 'PENDING','summary':'Both native recipients returned Python-authored work to the unmodified JavaScript receiver.' if paired else 'The cross-language round trip requires the two native recipient receipts.','href':'data/roundtrip-qualification.json'}
    roundtrip={'schema':'schism-paired-roundtrip/2','status':evidence['roundtrip']['status'],'contract_sha256':CONTRACT,'receiver_sha256':receiver_sha,
               'recipients':{k:v.get('roundtrip') if v else None for k,v in native.items()}}
    write('data/roundtrip-qualification.json',json.dumps(roundtrip,indent=2)+'\n')
    c=load('data/cantos-qualification.json')
    evidence['cantos']={'status':'PASS' if c and c.get('verification_status')=='passed' else 'PENDING',
       'summary':f"Retained result: {c['native_analyzer_verdict']}; {c['historical_accepted_per_arm']}/{c['historical_observations_per_arm']} accepted in each arm; {c['native_analysis_new_inference_requests']} new inference requests." if c else 'Retained empirical evidence has not been reproduced.',
       'href':'data/cantos-qualification.json'}
    qualification={'schema':'schism-public-qualification/2','status':'PASS' if all(v['status']=='PASS' for v in evidence.values()) else 'PENDING',
                   'contract_sha256':CONTRACT,'receiver_sha256':receiver_sha,'native_source_binding':'data/native-source-binding.json','evidence':evidence,
                   'new_implementation':'Independent Python interpretation, calculation, history verification and continuation of the pinned industrial capsule contract.',
                   'scope':'Synthetic industrial software continuity plus reanalysis of historical empirical compute evidence. No physical system qualification.'}
    write('data/qualification.json',json.dumps(qualification,indent=2)+'\n')
    build_data={'version':VERSION,'release_date':'2026-11-27','contract_sha256':CONTRACT,'receiver_sha256':receiver_sha,'source_commit':SOURCE,
                'evidence':evidence,'artifacts':{'offline':'SCHISM-v2.0-offline.html','source':'SCHISM-v2.0-source.zip','note':'TECHNICAL_NOTE.md'},
                'public_url':LIVE,'fixture_class':'synthetic-industrial-records'}
    template=(ROOT/'index.template.html').read_text(encoding='utf-8')
    replacements={'STYLES':(ROOT/'style.css').read_text(encoding='utf-8'),'BUILD_DATA':js(build_data),'VENDOR_CORE':core.decode(),
                  'VENDOR_ENGINE':engine.decode(),'CONTROLLER':(ROOT/'controller.js').read_text(encoding='utf-8'),'APP':(ROOT/'app.js').read_text(encoding='utf-8')}
    for key,value in replacements.items():
        assert template.count('{{'+key+'}}')==1,key
        template=template.replace('{{'+key+'}}',value)
    assert '{{' not in template
    write('index.html',template)
    offline=template
    for target in ['SCHISM-v2.0-offline.html','SCHISM-v2.0-source.zip','TECHNICAL_NOTE.md','data/qualification.json']:
        offline=offline.replace('href="'+target,'href="'+LIVE+target)
    # Retained evidence cards need absolute review links in a single downloaded HTML file.
    offline=offline.replace('"href":"data/','"href":"'+LIVE+'data/')
    write('SCHISM-v2.0-offline.html',offline)
    if preview:
        print(json.dumps({'state':'PREVIEW_BUILT','qualification':qualification['status'],'receiver_sha256':receiver_sha}));return
    exhibit=ROOT/'exhibits/cantos-maintainer-kit.zip'
    assert exhibit.exists() and sha(exhibit.read_bytes())=='3c6d030d8215ad6a15175f2cd5550820adceb11705826dab6373bb2eecfff84a','Pinned Cantos exhibit is required in the complete package'
    entries=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in package_files()]
    tree=sha('\n'.join(r['sha256']+'  '+r['path'] for r in entries).encode())
    manifest={'schema':'schism-release-manifest/2','version':VERSION,'source_tree_sha256':tree,'files':entries}
    write('release-manifest.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(ROOT/'SCHISM-v2.0-source.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in [*package_files(),ROOT/'release-manifest.json']:
            rel=p.relative_to(ROOT).as_posix();info=zipfile.ZipInfo('SCHISM-2.0/'+rel,date_time=(2026,11,27,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,p.read_bytes())
    checks=[*entries,{'path':'release-manifest.json','sha256':sha((ROOT/'release-manifest.json').read_bytes())},
            {'path':'SCHISM-v2.0-source.zip','sha256':sha((ROOT/'SCHISM-v2.0-source.zip').read_bytes())}]
    write('SHA256SUMS','\n'.join(r['sha256']+'  '+r['path'] for r in checks)+'\n')
    print(json.dumps({'state':'BUILT','qualification':qualification['status'],'source_files':len(entries),'source_tree_sha256':tree,
                      'archive_bytes':(ROOT/'SCHISM-v2.0-source.zip').stat().st_size,'archive_sha256':checks[-1]['sha256'],'receiver_sha256':receiver_sha},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preview',action='store_true');build(p.parse_args().preview)
