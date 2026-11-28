#!/usr/bin/env python3
"""Run the preserved inert-ball film program into a fresh output directory."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sources(root, manifest):
    for name, item in manifest['source_files'].items():
        path = root / item['path']
        actual = sha(path)
        if actual != item['sha256'] or path.stat().st_size != item['bytes']:
            raise RuntimeError(f'Source mismatch: {name}')


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, default=Path(__file__).with_name('source-manifest.json'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--deps', type=Path, help='Existing local Python package directory; no installation or download')
    ap.add_argument('--timeout', type=int, default=900)
    a = ap.parse_args()
    manifest_path = a.manifest.resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    check_sources(root, manifest)
    out = a.out.resolve()
    if out.exists():
        raise SystemExit('Output already exists; use a fresh directory to preserve every attempt')
    if a.deps:
        sys.path.insert(0, str(a.deps.resolve()))
    runtime = {'python': platform.python_version(), 'executable': sys.executable, 'platform': platform.platform()}
    for package in ('numpy', 'scipy', 'mujoco'):
        runtime[package] = importlib.metadata.version(package)
    expected = manifest['qualified_runtime']
    if any(runtime[k] != expected[k] for k in expected):
        raise SystemExit(f'Runtime differs from the qualified source contract: {runtime}')
    out.mkdir(parents=True)
    files = manifest['source_files']
    params = manifest['parameters']
    command = [sys.executable, '-B', '-u', str(root / files['film_sim']['path']),
               '--hfield', str(root / files['hfield']['path']),
               '--room', str(root / files['room']['path']),
               '--result', str(root / files['frozen_result']['path']),
               '--crop', *map(str, params['crop']), '--out', str(out / 'simulation'),
               '--duration', str(params['duration']), '--fps', str(params['fps']),
               '--margin', str(params['margin'])]
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if a.deps:
        env['PYTHONPATH'] = str(a.deps.resolve())
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        env[key] = '1'
    receipt = {'schema': 'schism/benign-world-reproduction-attempt@1', 'state': 'running',
               'started_utc': now(), 'driver_pid': os.getpid(), 'manifest_sha256': sha(manifest_path),
               'driver_sha256': sha(Path(__file__)), 'runtime': runtime, 'command': command,
               'output_directory': str(out), 'scope': manifest['scope'],
               'source_units': manifest['source_units'], 'simulation_units': manifest['simulation_units'],
               'new_simulation': True, 'full_v33_study_repeated': False, 'gpu_used': False}
    receipt_file = out / 'attempt.json'
    receipt_file.write_text(json.dumps(receipt, indent=2) + '\n')
    started = time.monotonic()
    try:
        with (out / 'simulation.log').open('w') as log:
            p = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            receipt['simulation_pid'] = p.pid
            receipt_file.write_text(json.dumps(receipt, indent=2) + '\n')
            try:
                exit_code = p.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
                raise RuntimeError(f'Bounded simulation exceeded {a.timeout} seconds')
        receipt['simulation_exit_code'] = exit_code
        if exit_code:
            raise RuntimeError(f'Frozen film program exited {exit_code}; retained simulation.log contains failure')
        check_sources(root, manifest)
        source_scene = json.loads((root / files['frozen_scene']['path']).read_text())
        scene_path = out / 'simulation/scene.json'
        scene = json.loads(scene_path.read_text())
        # The output dynamics remain untouched; only the retained presentation camera is joined.
        scene['cam'] = source_scene['cam']
        scene['fog'] = source_scene['fog']
        replay = out / 'simulation/scene_with_camera.json'
        replay.write_text(json.dumps(scene) + '\n')
        receipt['outputs'] = {str(f.relative_to(out)): {'sha256': sha(f), 'bytes': f.stat().st_size}
                              for f in (scene_path, replay, out / 'simulation/surface.bin', out / 'simulation.log')}
        receipt['state'] = 'simulation_completed'
    except Exception as exc:
        receipt['state'] = 'failed'
        receipt['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        receipt['ended_utc'] = now()
        receipt['wall_seconds'] = time.monotonic() - started
        receipt_file.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'state': receipt['state'], 'attempt': str(receipt_file), 'wall_seconds': receipt['wall_seconds']}))


if __name__ == '__main__':
    main()
