import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(process.argv[2] ?? fileURLToPath(new URL('..', import.meta.url)));
const EXPECTED_SOURCE_FILES = Object.freeze([
  'PREDECESSOR_RECEIPT.json',
  'README.md',
  'clients/shared/selections/contract.mjs',
  'clients/shared/selections/index.mjs',
  'clients/shared/selections/reducer.mjs',
  'clients/shared/selections/view-model.mjs',
  'scripts/qualify.mjs',
  'tests/ui/selection-transactions/fixtures.mjs',
  'tests/ui/selection-transactions/selection-transactions.test.mjs',
]);
const EXPECTED_PREDECESSOR_SHA256 = '4a25b4becb360a7480d50ff82e17c205bc66db8731ca0b3b811cbd232272cbda';
const EXPECTED_RECEIPT_SHA256 = 'b455435bd15da01581fcde04a52fc5e24cfb0d2b2270b657e5d79658baffb8e7';
const EXPECTED_TESTS = 91;
const CANDIDATE_P95_MS = 5;

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

function fail(message) {
  throw new Error(message);
}

function walk(directory) {
  const rows = [];
  for (const name of readdirSync(directory).sort()) {
    const path = resolve(directory, name);
    if (statSync(path).isDirectory()) rows.push(...walk(path));
    else rows.push(relative(root, path).replaceAll('\\', '/'));
  }
  return rows;
}

const manifestRows = readFileSync(resolve(root, 'SOURCE_MANIFEST.sha256'), 'utf8')
  .trim()
  .split('\n')
  .filter(Boolean)
  .map((line) => {
    const match = /^([0-9a-f]{64})  (.+)$/.exec(line);
    if (!match) fail(`invalid source manifest row: ${line}`);
    return { digest: match[1], path: match[2] };
  });
const manifestPaths = manifestRows.map((row) => row.path);
if (JSON.stringify(manifestPaths) !== JSON.stringify(EXPECTED_SOURCE_FILES)) {
  fail(`source manifest path set drifted: ${JSON.stringify(manifestPaths)}`);
}
for (const row of manifestRows) {
  const observed = sha256(readFileSync(resolve(root, row.path)));
  if (observed !== row.digest) fail(`source manifest mismatch: ${row.path}`);
}

const targetFiles = walk(root).filter((path) => !path.startsWith('.git/'));
const expectedTargetFiles = [...EXPECTED_SOURCE_FILES, 'SOURCE_MANIFEST.sha256', 'receipts/AP-405.json'].sort();
if (JSON.stringify(targetFiles.sort()) !== JSON.stringify(expectedTargetFiles)) {
  fail(`target file set drifted: ${JSON.stringify(targetFiles)}`);
}
if (sha256(readFileSync(resolve(root, 'PREDECESSOR_RECEIPT.json'))) !== EXPECTED_PREDECESSOR_SHA256) {
  fail('predecessor receipt identity drifted');
}
if (sha256(readFileSync(resolve(root, 'receipts/AP-405.json'))) !== EXPECTED_RECEIPT_SHA256) {
  fail('AP-405 receipt identity drifted');
}

const sourceText = [
  'clients/shared/selections/contract.mjs',
  'clients/shared/selections/reducer.mjs',
  'clients/shared/selections/view-model.mjs',
].map((path) => readFileSync(resolve(root, path), 'utf8')).join('\n');
const forbidden = [
  ['network fetch', /\bfetch\s*\(/],
  ['websocket', /WebSocket/],
  ['xhr', /XMLHttpRequest/],
  ['local storage', /localStorage/],
  ['session storage', /sessionStorage/],
  ['indexed db', /indexedDB/],
  ['local timer', /setTimeout\s*\(/],
  ['local interval', /setInterval\s*\(/],
  ['local clock', /Date\.now\s*\(/],
  ['model scoring', /modelScore|engagementScore|engagement_metric/i],
  ['coordinate click', /coordinateClick|screen\.click|mouse\.click/i],
  ['playback play', /\.play\s*\(/],
  ['playback pause', /\.pause\s*\(/],
  ['playback seek', /\.seek\s*\(/],
];
for (const [label, pattern] of forbidden) {
  if (pattern.test(sourceText)) fail(`forbidden authority pattern: ${label}`);
}

const test = spawnSync(
  process.execPath,
  ['--test', 'tests/ui/selection-transactions/selection-transactions.test.mjs'],
  { cwd: root, encoding: 'utf8', env: { ...process.env, NO_COLOR: '1', TERM: 'dumb' } },
);
process.stdout.write(test.stdout);
process.stderr.write(test.stderr);
if (test.status !== 0) fail(`AP-405 tests failed with status ${test.status}`);
const testsMatch = /# tests (\d+)/.exec(test.stdout);
const passMatch = /# pass (\d+)/.exec(test.stdout);
const failMatch = /# fail (\d+)/.exec(test.stdout);
const p95Match = /SELECTION_TRANSACTION_WARM_P95_MS=([0-9.]+)/.exec(test.stdout);
if (!testsMatch || Number(testsMatch[1]) !== EXPECTED_TESTS) fail('test denominator drifted');
if (!passMatch || Number(passMatch[1]) !== EXPECTED_TESTS) fail('passing test denominator drifted');
if (!failMatch || Number(failMatch[1]) !== 0) fail('test failures observed');
if (!p95Match || Number(p95Match[1]) >= CANDIDATE_P95_MS) fail('warm projection budget exceeded');

const receipt = JSON.parse(readFileSync(resolve(root, 'receipts/AP-405.json'), 'utf8'));
if (
  receipt.transaction !== 'AP-405' ||
  receipt.canonical_ap405_accepted !== false ||
  receipt.canonical_g3_accepted !== false ||
  receipt.canonical_native_client_accepted !== false ||
  receipt.hosted_repository_accepted !== false ||
  receipt.target_repository_present !== false ||
  JSON.stringify(receipt.accepted_gates) !== '[]'
) fail('AP-405 authority receipt widened');

console.log(
  `AP-405 target qualified: ${EXPECTED_SOURCE_FILES.length} source files, ` +
  `${expectedTargetFiles.length} target files, ${EXPECTED_TESTS} tests passed, ` +
  `warm P95 ${Number(p95Match[1]).toFixed(6)}ms.`,
);
