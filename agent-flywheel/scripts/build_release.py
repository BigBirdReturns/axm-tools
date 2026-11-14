#!/usr/bin/env python3
"""Build or verify a reproducible, source-only download using the stdlib."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {'index.html','styles.css','app.mjs','engine.mjs','providers.mjs','sample.mjs',
         'README.md','MODEL_GUIDE.md','SOURCES.json','PROMPT.txt','QUALIFICATION.json'}
DIRECTORIES = {'scripts','tests','examples','data'}
REQUIRED = {'index.html','styles.css','app.mjs','engine.mjs','providers.mjs','sample.mjs',
            'README.md','MODEL_GUIDE.md','SOURCES.json','scripts/run.mjs'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sources():
    result = {}
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink():
            continue
        if any(part.startswith('.') or part in {'__pycache__','node_modules'} for part in relative.parts):
            continue
        if path.suffix in {'.pyc','.log','.zip'}:
            continue
        if str(relative) in FILES or relative.parts[0] in DIRECTORIES:
            result[str(relative)] = path.read_bytes()
    missing = REQUIRED - result.keys()
    if missing:
        raise ValueError('Missing required source files: ' + ', '.join(sorted(missing)))
    return result


def build():
    items = sources()
    rows = [{'path':name,'sha256':sha(content),'bytes':len(content)} for name,content in items.items()]
    manifest = {'schema':'axm.agent-flywheel.release.v1','version':'1.0.0',
                'source_digest':sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()),
                'files':rows,'excludes':['manifest.json','agent-flywheel-kit.zip','visitor work and credentials']}
    encoded = (json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,content in [*items.items(),('manifest.json',encoded)]:
            info=zipfile.ZipInfo('agent-flywheel/'+name,date_time=(2026,11,14,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,content)
    return manifest,encoded,stream.getvalue()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    manifest,encoded,archive=build()
    outputs={'manifest.json':encoded,'agent-flywheel-kit.zip':archive}
    for name,content in outputs.items():
        path=ROOT/name
        if args.check:
            if not path.is_file() or path.read_bytes()!=content:
                raise SystemExit('Source package requires regeneration: '+name)
        else:
            path.write_bytes(content)
    print(json.dumps({'status':'PASS','mode':'check' if args.check else 'build',
                      'files':len(manifest['files']),'source_digest':manifest['source_digest'],
                      'archive_sha256':sha(archive),'archive_bytes':len(archive)}))


if __name__=='__main__':
    main()
