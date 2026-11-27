"""Verify the delivered source set against an independently retained manifest."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTER = {'release-manifest.json', 'SHA256SUMS', 'SCHISM-v2.0-source.zip'}

def verify(root: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'schism-release-manifest/2':
        raise ValueError('Unsupported release manifest')
    entries = manifest['files']
    names = [r['path'] for r in entries]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate manifest member')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    extras = actual - set(names) - OUTER
    missing = set(names) - actual
    if extras or missing:
        raise ValueError('Closed source set mismatch: ' + json.dumps({'extra': sorted(extras), 'missing': sorted(missing)}))
    for entry in entries:
        path = root / entry['path']
        if path.resolve().is_relative_to(root.resolve()) is False or path.is_symlink():
            raise ValueError('Unsafe manifest member')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Changed release member: ' + entry['path'])
    material = '\n'.join(r['sha256'] + '  ' + r['path'] for r in entries).encode()
    if hashlib.sha256(material).hexdigest() != manifest['source_tree_sha256']:
        raise ValueError('Manifest tree identity mismatch')
    return {'status': 'PASS', 'checked_files': len(entries), 'source_tree_sha256': manifest['source_tree_sha256'],
            'trust_boundary': 'Comparison with the selected expected manifest; no publisher authentication is inferred.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.root, args.manifest or args.root / 'release-manifest.json')
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'reason': str(error)}))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
