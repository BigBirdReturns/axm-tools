import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const EXPECTED_SOURCE_PATHS = [
  'PREDECESSOR_RECEIPT.json',
  'README.md',
  'clients/second-screen/contract.mjs',
  'clients/second-screen/index.mjs',
  'clients/second-screen/reducer.mjs',
  'clients/second-screen/view-model.mjs',
  'scripts/qualify.mjs',
  'tests/ui/second-screen/fixtures.mjs',
  'tests/ui/second-screen/second-screen.test.mjs',
].sort();
const EXPECTED_COMPLETE_PATHS = [
  ...EXPECTED_SOURCE_PATHS,
  'SOURCE_MANIFEST.sha256',
  'receipts/AP-403.json',
].sort();

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function walk(root, current = root) {
  const output = [];
  for (const name of readdirSync(current).sort()) {
    const path = resolve(current, name);
    if (statSync(path).isDirectory()) output.push(...walk(root, path));
    else output.push(relative(root, path).split(sep).join('/'));
  }
  return output;
}

const completePaths = walk(ROOT).sort();
assert.deepEqual(completePaths, EXPECTED_COMPLETE_PATHS, 'complete AP-403 target path set drifted');

const manifestLines = readFileSync(resolve(ROOT, 'SOURCE_MANIFEST.sha256'), 'utf8')
  .trimEnd()
  .split('\n')
  .filter(Boolean);
const manifest = new Map();
for (const line of manifestLines) {
  const match = /^([0-9a-f]{64})  (.+)$/.exec(line);
  assert.ok(match, `invalid manifest line: ${line}`);
  assert.equal(manifest.has(match[2]), false, `duplicate manifest path: ${match[2]}`);
  manifest.set(match[2], match[1]);
}
assert.deepEqual([...manifest.keys()].sort(), EXPECTED_SOURCE_PATHS, 'source manifest path set drifted');
for (const [path, expected] of manifest) {
  assert.equal(sha256(resolve(ROOT, path)), expected, `source digest drift: ${path}`);
}

const predecessor = JSON.parse(readFileSync(resolve(ROOT, 'PREDECESSOR_RECEIPT.json'), 'utf8'));
assert.equal(predecessor.format, 'axm-aperture-ap403-predecessor-receipt/2');
assert.equal(predecessor.transaction, 'AP-403');
assert.equal(predecessor.target_repository, 'BigBirdReturns/axm-aperture');
assert.equal(predecessor.target_repository_present, false);
assert.equal(predecessor.ap213.api_policy_sha256, 'bc52ce6faa3383340ee6e5ba19147ac6417225e351530a5336c4d6b4fe8130c0');
assert.equal(predecessor.ap214.profiles_source_sha256, 'ca37d5fa59448b8ae0acc475bc3c3602de81c682b0339ad1e8b93d487b482ad9');
assert.equal(predecessor.ap219.status, 'planned_unexecuted');
assert.equal(predecessor.ap401.canonical_transaction_accepted_here, false);
assert.deepEqual(predecessor.g2_local_authority.accepted_gates, ['G0', 'G1', 'G2']);
assert.equal(predecessor.g2_local_authority.hosted_repository_accepted, false);

const receipt = JSON.parse(readFileSync(resolve(ROOT, 'receipts/AP-403.json'), 'utf8'));
assert.equal(receipt.format, 'axm-aperture-program-transaction/1');
assert.equal(receipt.transaction, 'AP-403');
assert.equal(receipt.status, 'source_candidate');
assert.equal(receipt.source_files, 9);
assert.equal(receipt.tests_passed, 52);
assert.deepEqual(receipt.accepted_gates, []);
assert.equal(receipt.aperture_gate_accepted, false);
assert.equal(receipt.canonical_ap403_accepted, false);
assert.equal(receipt.ap219_accepted, false);
assert.equal(receipt.canonical_g4_accepted, false);
assert.equal(receipt.canonical_native_client_accepted, false);
assert.equal(receipt.hosted_repository_accepted, false);
assert.equal(receipt.target_repository_present, false);
assert.equal(receipt.predecessors.AP_219_status, 'planned_unexecuted');
assert.equal(receipt.source_manifest_sha256, sha256(resolve(ROOT, 'SOURCE_MANIFEST.sha256')));

const testPath = resolve(ROOT, 'tests/ui/second-screen/second-screen.test.mjs');
const run = spawnSync(process.execPath, ['--test', testPath], {
  cwd: ROOT,
  encoding: 'utf8',
  env: { ...process.env, NO_COLOR: '1', FORCE_COLOR: '0' },
});
process.stdout.write(run.stdout);
process.stderr.write(run.stderr);
assert.equal(run.status, 0, 'AP-403 contract denominator failed');
assert.match(run.stdout, /# tests 52(?:\r?\n)/);
assert.match(run.stdout, /# pass 52(?:\r?\n)/);
assert.match(run.stdout, /# fail 0(?:\r?\n)/);
const timing = /SECOND_SCREEN_WARM_P95_MS=([0-9.]+)/.exec(run.stdout);
assert.ok(timing, 'warm projection P95 was not emitted');
assert.ok(Number(timing[1]) < 5, 'warm projection exceeded five millisecond source budget');

console.log(`AP-403 target qualified: 9 source files, manifest exact, 52 tests passed, warm P95 ${timing[1]}ms.`);
