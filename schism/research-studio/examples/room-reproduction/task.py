#!/usr/bin/env python3
"""SCHISM task adapter: existing ball physics -> retained result -> independent verifier."""
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    data = Path(os.environ['SCHISM_DATA']).resolve()
    deps = os.environ.get('WORLD_PHYSICS_DEPS')
    physics_python = os.environ.get('WORLD_PHYSICS_PYTHON')
    if not deps:
        raise SystemExit('Configure WORLD_PHYSICS_DEPS to the existing qualified NumPy/SciPy/MuJoCo package directory')
    if not physics_python:
        raise SystemExit('Configure WORLD_PHYSICS_PYTHON to the qualified Python interpreter with NumPy and SciPy')
    attempt_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]
    out = data / 'attempts' / attempt_id
    command = [physics_python, '-B', str(root / 'reproduce.py'), '--manifest', str(root / 'source-manifest.json'),
               '--out', str(out), '--deps', deps, '--timeout', '900']
    print(json.dumps({'phase': 'simulate', 'attempt_id': attempt_id, 'command': command}), flush=True)
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        return result.returncode
    report = out / 'verification.json'
    verify = [sys.executable, '-B', str(root / 'verify.py'), '--manifest', str(root / 'source-manifest.json'),
              '--out', str(out), '--report', str(report)]
    print(json.dumps({'phase': 'independent_verify', 'command': verify}), flush=True)
    result = subprocess.run(verify, cwd=root)
    terminal = {'schema': 'schism/benign-world-task-result@1', 'attempt_id': attempt_id,
                'state': 'verified' if result.returncode == 0 else 'verification_failed',
                'verification': str(report), 'attempt': str(out / 'attempt.json'),
                'replay_scene': str(out / 'simulation/scene_with_camera.json'),
                'replay_surface': str(out / 'simulation/surface.bin'),
                'new_simulation': True, 'full_v33_study_repeated': False,
                'source_units': 'undeclared', 'simulation_units': 'metres assumed by original frozen code'}
    (out / 'task-result.json').write_text(json.dumps(terminal, indent=2) + '\n')
    (data / 'latest-result.json').write_text(json.dumps(terminal, indent=2) + '\n')
    print(json.dumps(terminal), flush=True)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
