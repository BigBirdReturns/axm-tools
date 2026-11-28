#!/usr/bin/env python3
"""Independent, standard-library verifier for source-bound W0 replay results."""
import argparse
import hashlib
import json
import math
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifest_path, out):
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    receipt = json.loads((out / 'attempt.json').read_text())
    checks = []
    def check(name, value, detail=None):
        checks.append({'name': name, 'pass': bool(value), 'detail': detail})
    check('attempt_completed', receipt['state'] == 'simulation_completed')
    check('manifest_bound', receipt['manifest_sha256'] == sha(manifest_path))
    for name, item in manifest['source_files'].items():
        p = root / item['path']
        check('source:' + name, sha(p) == item['sha256'] and p.stat().st_size == item['bytes'])
    for name, item in receipt['outputs'].items():
        p = out / name
        check('output:' + name, sha(p) == item['sha256'] and p.stat().st_size == item['bytes'])
    scene = json.loads((out / 'simulation/scene.json').read_text())
    replay = json.loads((out / 'simulation/scene_with_camera.json').read_text())
    old = json.loads((root / manifest['source_files']['frozen_scene']['path']).read_text())
    expected = manifest['expected']
    balls = scene['balls']
    check('ball_count', len(balls) == expected['balls'], len(balls))
    check('frame_count', scene['frames'] == expected['frames'], scene['frames'])
    shape_ok = all(len(b['traj']) == expected['frames'] and all(len(p) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) for p in b['traj']) for b in balls)
    check('finite_trajectory_shape', shape_ok)
    check('radii', sorted(set(b['r'] for b in balls)) == expected['radii'])
    sites = {(b['traj'][0][0], b['traj'][0][1]) for b in balls}
    check('site_count', len(sites) == expected['sites'], len(sites))
    check('retained_ball_metadata', [(b['r'], b['kind'], b['held_out_match']) for b in balls] == [(b['r'], b['kind'], b['held_out_match']) for b in old['balls']])
    check('selected_starts_match_retained', [b['traj'][0] for b in balls] == [b['traj'][0] for b in old['balls']])
    exact = len(balls) == len(old['balls']) and all(b['traj'] == o['traj'] for b, o in zip(balls, old['balls']))
    max_error = None
    if shape_ok and len(balls) == len(old['balls']):
        max_error = max(abs(v - w) for b, o in zip(balls, old['balls']) for p, q in zip(b['traj'], o['traj']) for v, w in zip(p, q))
    check('rounded_trajectories_equal_retained', exact, {'max_coordinate_difference': max_error})
    check('surface_shape', [scene['ni'], scene['nk']] == expected['surface_shape'])
    surface_path = out / 'simulation/surface.bin'
    check('surface_byte_count', surface_path.stat().st_size == 4 * scene['ni'] * scene['nk'])
    check('surface_identity', sha(surface_path) == manifest['source_files']['frozen_surface']['sha256'])
    values = struct.unpack('<' + 'f' * (surface_path.stat().st_size // 4), surface_path.read_bytes())
    check('finite_surface', all(math.isfinite(v) for v in values))
    check('retained_geometry_metadata', all(scene[k] == old[k] for k in ('ni', 'nk', 'vox', 'x0', 'y0', 'zfloor', 'cx', 'cy', 'fps', 'frames', 'duration', 'holes_in_crop', 'walls_in_crop')))
    check('replay_camera_provenance', replay['cam'] == old['cam'] and replay['fog'] == old['fog'])
    check('replay_dynamics_unchanged', all(replay[k] == scene[k] for k in scene if k not in ('cam', 'fog')))
    discrepancy = scene['check']['rest_point_diff_vs_frozen_max_m']
    check('raw_rest_agreement', math.isfinite(discrepancy) and discrepancy <= manifest['acceptance']['raw_rest_discrepancy_max'], {'value': discrepancy, 'unit': 'assumed simulation metres'})
    result = {'schema': 'schism/benign-world-reproduction-verification@1', 'verified_utc': datetime.now(timezone.utc).isoformat(),
              'verifier_pid': os.getpid(), 'verifier_sha256': sha(Path(__file__)), 'manifest_sha256': sha(manifest_path),
              'attempt_sha256': sha(out / 'attempt.json'), 'attempt_path': str(out / 'attempt.json'),
              'pass': all(c['pass'] for c in checks), 'checks': checks, 'new_simulated_balls': len(balls),
              'new_frames': scene['frames'], 'simulation_horizon_s': expected['simulation_horizon_s'],
              'recorded_duration_s': scene['duration'], 'source_units': manifest['source_units'],
              'simulation_units': manifest['simulation_units'], 'scope': manifest['scope'],
              'full_v33_study_repeated': False, 'physical_room_validation': False,
              'fresh_process_identity': {'driver_pid': receipt['driver_pid'], 'simulation_pid': receipt['simulation_pid'], 'verifier_pid': os.getpid()}}
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, default=Path(__file__).with_name('source-manifest.json'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    a = ap.parse_args()
    if a.report.exists():
        raise SystemExit('Refusing to replace a verification report')
    result = verify(a.manifest.resolve(), a.out.resolve())
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'pass': result['pass'], 'checks': len(result['checks']), 'report': str(a.report.resolve()), 'failed': [c['name'] for c in result['checks'] if not c['pass']]}))
    sys.exit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
