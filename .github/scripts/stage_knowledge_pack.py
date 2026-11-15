"""Publish one qualified, pinned public reference without changing other tool owners."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_NAME = re.compile(r'downloads/axm-knowledge-pack-source-[0-9]+\.[0-9]+\.[0-9]+\.zip\Z')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retained_sources(destination):
    """Preserve previously accepted, versioned downloads under their recorded hashes."""
    if not destination.exists():
        return {}
    if destination.is_symlink() or not (destination / 'PUBLICATION.json').is_file():
        raise SystemExit('An existing tool owns the destination; refusing replacement')
    old = json.loads((destination / 'PUBLICATION.json').read_text())
    inventory = dict(old.get('retained_source_archives', {}))
    if old.get('source_archive_path') and old.get('source_archive'):
        inventory[old['source_archive_path']] = old['source_archive']
    if len(inventory) > 64:
        raise SystemExit('Historical source archive inventory exceeds its bound')
    kept, total = {}, 0
    for name, expected in inventory.items():
        if not ARCHIVE_NAME.fullmatch(name) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise SystemExit('Invalid historical source archive receipt')
        source = destination / name
        if source.is_symlink() or source.parent.is_symlink() or not source.is_file():
            raise SystemExit('Historical source archive is missing or linked')
        total += source.stat().st_size
        if total > 64 * 1024 * 1024:
            raise SystemExit('Historical source retention exceeds 64 MiB')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit('Historical source archive hash mismatch: ' + name)
        kept[name] = data
    return kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != args.source_commit:
        raise SystemExit('Source commit mismatch')
    reference = source / 'examples/knowledge-pack'
    web = reference / 'web'
    release = json.loads((web / 'release.json').read_text())
    config = json.loads((ROOT / '.github/knowledge-pack-release.json').read_text())
    version = release.get('version', '')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or version != config['version'] or actual != config['source_commit']:
        raise SystemExit('Pinned source/version differs from the built release')
    source_archive = 'downloads/axm-knowledge-pack-source-' + version + '.zip'
    if source_archive not in release['artifacts']:
        raise SystemExit('Versioned source archive is absent')
    native = json.loads((reference / 'build/native-conformance.json').read_text())
    browser = json.loads((reference / 'build/browser/browser-acceptance.json').read_text())
    wasm = json.loads((reference / 'build/browser/wasm-conformance.json').read_text())
    workbench = json.loads((reference / 'build/workbench-browser/workbench-browser-acceptance.json').read_text())
    package = json.loads((reference / 'build/workbench-package.json').read_text())
    if native.get('status') != 'PASS' or native.get('cases') != 26:
        raise SystemExit('Native conformance not accepted')
    if wasm.get('status') != 'PASS' or len(wasm.get('results', [])) != 26 or not all(x.get('pass') for x in wasm['results']):
        raise SystemExit('WebAssembly conformance not accepted')
    if len(browser.get('results', [])) < 16 or not all(x.get('status') == 'PASS' for x in browser['results']) or browser.get('errors'):
        raise SystemExit('Browser interaction not accepted')
    if workbench.get('status') != 'PASS' or len(workbench.get('results', [])) < 20 or not all(x.get('status') == 'PASS' for x in workbench['results']) or workbench.get('errors'):
        raise SystemExit('Local workbench browser acceptance is incomplete')
    if package.get('status') != 'PASS' or not package.get('fresh_directory_runtime_imports') or package.get('private_key_or_wheel_included') is not False or package.get('archive_sha256') != release['artifacts'][source_archive]:
        raise SystemExit('Extracted source-kit qualification does not match this release')
    if not any('network offline' in x['name'] for x in browser['results']):
        raise SystemExit('Offline browser control absent')
    for name, expected in release['artifacts'].items():
        target = (web / name).resolve()
        if not target.is_relative_to(web.resolve()) or digest(target) != expected:
            raise SystemExit('Public artifact hash mismatch: ' + name)
    for path in web.rglob('*'):
        if path.is_symlink() or (path.is_file() and (path.suffix == '.key' or 'identity' in path.parts)):
            raise SystemExit('Unsafe publication inventory')
    destination = ROOT / 'knowledge-pack'
    retained = retained_sources(destination)
    retained.pop(source_archive, None)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(web, destination)
    retained_hashes = {}
    for name, data in retained.items():
        target = destination / name
        if target.exists() and target.read_bytes() != data:
            raise SystemExit('New build conflicts with a retained versioned archive')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        retained_hashes[name] = hashlib.sha256(data).hexdigest()
    receipt = {
        'version': version, 'profile': 'axm-pack-preview/0.1',
        'collection_profile': 'axm-vault-collection-archive/1',
        'source_repository': 'BigBirdReturns/axm-core', 'source_commit': actual,
        'workflow_run': os.environ.get('GITHUB_RUN_ID'),
        'native_conformance_cases': 26, 'wasm_conformance_cases': 26,
        'browser_checks': len(browser['results']), 'workbench_browser_checks': len(workbench['results']),
        'offline_verification_exercised': True, 'extracted_source_kit_qualified': True,
        'packaged_owner_files_checked': package['owner_files_checked'],
        'source_archive': release['artifacts'][source_archive], 'source_archive_path': source_archive,
        'retained_source_archives': retained_hashes,
        'runtime': 'Static browser verifier and downloadable local multi-vault workbench. The workbench runs on loopback on the vault host; this public website receives no source notes.',
        'trust': 'Demo keys authenticate test data only. Real collections require independently supplied publisher anchors. Semantic correctness is not established by signatures.'
    }
    (destination / 'PUBLICATION.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (destination / 'README.md').write_text('# AXM Knowledge Pack and Vault Workbench\n\nInspect portable signed knowledge in the local-browser verifier, or run the full multi-vault application from the source kit. WORKBENCH.md covers incremental collections, exact source review, selected claim approval, Forge extraction, Spectra retrieval, draft-only watching, native Obsidian views and portable collection verification. VAULT.md retains the smaller round-trip CLI.\n\nSource owner: https://github.com/BigBirdReturns/axm-core/tree/' + actual + '/examples/knowledge-pack\n\nPublication receipt: PUBLICATION.json. Build instructions: REPRODUCE.md. This public directory contains static artifacts only; no private signing key, personal vault or live model endpoint belongs here.\n')
    index = ROOT / 'index.html'
    text = index.read_text()
    marker = '<!-- knowledge-pack-card:start -->'
    card = '''<!-- knowledge-pack-card:start -->
<div class="tool">
  <div class="title"><a href="knowledge-pack/">AXM Knowledge Pack and Vault Workbench</a></div>
  <div class="desc">Verify portable evidence in your browser, or run the local multi-vault workbench: review source changes and model proposals, approve signed revisions, search accepted history and preserve your Obsidian notes. Public source, native readers and reproducible checks.</div>
  <a class="open" href="knowledge-pack/">Open the verifier and workbench source →</a>
</div>
<!-- knowledge-pack-card:end -->'''
    if marker in text:
        start = text.index(marker)
        end = text.index('<!-- knowledge-pack-card:end -->', start) + len('<!-- knowledge-pack-card:end -->')
        text = text[:start] + card + text[end:]
    else:
        if text.count('</header>') != 1:
            raise SystemExit('Directory insertion anchor changed')
        text = text.replace('</header>', '</header>\n\n' + card, 1)
    index.write_text(text)
    (ROOT / '.github/knowledge-pack-release-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
