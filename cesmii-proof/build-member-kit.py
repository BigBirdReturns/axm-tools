#!/usr/bin/env python3
"""Build the CESMII member/reviewer delivery from its exact public source tree."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ARCHIVE = ROOT / 'cesmii-member-kit.zip'
MANIFEST = ROOT / 'MEMBER_MANIFEST.json'
STAMP = (2026, 11, 19, 0, 0, 0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text(path, value):
    path.write_text(value, encoding='utf-8', newline='\n')


def candidates():
    selected = {}
    for base, prefix in [(ROOT, 'cesmii-proof'), (REPO / 'industrial-continuity', 'industrial-continuity')]:
        for p in sorted(base.rglob('*')):
            if not p.is_file() or any(x in p.parts for x in ['__pycache__', 'node_modules', '.venv', '.git']):
                continue
            if p == ARCHIVE or p == MANIFEST or p.suffix.lower() in ['.pyc', '.wav', '.webm']:
                continue
            selected[prefix + '/' + p.relative_to(base).as_posix()] = p
    return selected


def build():
    required = [
        ROOT / 'workbench/index.html', ROOT / 'workbench/offline.html',
        ROOT / 'review/index.html', ROOT / 'review/TECHNICAL_REVIEW.md',
        ROOT / 'review/member-workflow-template.json', ROOT / 'review/demo.mp4',
        ROOT / 'review/demo.vtt', ROOT / 'review/transcript.html',
        ROOT / 'second-server/evidence.json', ROOT / 'second-server/setup.py',
        ROOT / 'second-server/capture-local-pump.json', ROOT / 'second-server/capture-local-tank.json',
        REPO / 'industrial-continuity/offline.html',
    ]
    missing = [str(p.relative_to(REPO)) for p in required if not p.is_file()]
    if missing:
        raise SystemExit('Delivery files are missing: ' + ', '.join(missing))
    files = candidates()
    manifest = {
        'schema': 'axm-cesmii-member-kit/1',
        'release_date': '2026-11-19',
        'entry': 'cesmii-proof/review/index.html',
        'application': 'cesmii-proof/workbench/index.html',
        'offline_application': 'cesmii-proof/workbench/offline.html',
        'additional_application': 'industrial-continuity/offline.html',
        'producer': {'name': 'Jonathan Sandhu', 'project': 'AXM', 'contact': 'jvssandhu@gmail.com'},
        'evidence': 'Public reference-server observations and declared synthetic examples; operator-supplied records remain local.',
        'files': {name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())} for name, p in files.items()},
    }
    text(MANIFEST, json.dumps(manifest, indent=2) + '\n')
    files['cesmii-proof/MEMBER_MANIFEST.json'] = MANIFEST
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, p in sorted(files.items()):
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, p.read_bytes())
    return {'archive': ARCHIVE.name, 'files': len(files), 'bytes': ARCHIVE.stat().st_size, 'sha256': digest(ARCHIVE.read_bytes())}


def verify():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    with zipfile.ZipFile(ARCHIVE) as z:
        expected = set(data['files']) | {'cesmii-proof/MEMBER_MANIFEST.json'}
        if len(z.namelist()) != len(set(z.namelist())):
            raise SystemExit('Archive contains duplicate entries')
        if set(z.namelist()) != expected:
            raise SystemExit('Archive and manifest entries differ')
        if z.read('cesmii-proof/MEMBER_MANIFEST.json') != MANIFEST.read_bytes():
            raise SystemExit('Embedded and external manifest bytes differ')
        for name, record in data['files'].items():
            content = z.read(name)
            if len(content) != record['bytes'] or digest(content) != record['sha256']:
                raise SystemExit('Manifest mismatch: ' + name)
            local = REPO / name
            if not local.is_file() or local.read_bytes() != content:
                raise SystemExit('Local source differs from archive: ' + name)
    return {'status': 'PASS', 'verified_files': len(data['files']), 'archive_sha256': digest(ARCHIVE.read_bytes())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify() if args.check else build(), indent=2))
