#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys

def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

parser = argparse.ArgumentParser()
parser.add_argument('--data-root', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--receipt', type=pathlib.Path, required=True)
args = parser.parse_args()
root = args.data_root.resolve()
cmd = [sys.executable, str(root / 'verify_dispatch_data.py'), '--root', str(root), '--output', str(args.output)]
result = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
if result.returncode:
    sys.stdout.write(result.stdout)
    raise SystemExit(result.returncode)
receipt = {
    'format': 'axm-aperture-g3-observation-kit-v2-dispatch-adapter-verification/1',
    'source_archive': {'bytes': args.output.stat().st_size, 'sha256': sha(args.output)},
    'underlying_verifier': 'verify_dispatch_data.py',
    'underlying_output': result.stdout.strip(),
    'runtime_binding_present': False,
    'observed_platform_interactions': 0,
    'observed_platform_visuals': 0,
    'manual_reader_groups_passed': 0,
    'canonical_ap410_accepted': False,
    'canonical_g3_accepted': False,
    'hosted_repository_accepted': False,
    'accepted_gates': [],
    'status': 'PASS',
}
core = json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()
receipt['receipt_sha256'] = hashlib.sha256(core).hexdigest()
args.receipt.parent.mkdir(parents=True, exist_ok=True)
args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(receipt, sort_keys=True))
