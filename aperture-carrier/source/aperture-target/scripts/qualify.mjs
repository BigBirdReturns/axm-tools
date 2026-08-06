import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = resolve(process.argv[2] ?? new URL('..', import.meta.url).pathname);
const EXPECTED_SOURCE_FILES = Object.freeze([
  'PREDECESSOR_RECEIPT.json',
  'README.md',
  'clients/shared/queries/contract.mjs',
  'clients/shared/queries/index.mjs',
  'clients/shared/queries/reducer.mjs',
  'clients/shared/queries/view-model.mjs',
  'scripts/qualify.mjs',
  'tests/ui/query-transactions/fixtures.mjs',
  'tests/ui/query-transactions/query-transactions.test.mjs',
]);
const EXPECTED_PREDECESSOR_SHA256 = '76e3291b80c3f24de56c5bc52e702eac8008aaf95a974380815070ed461e5d70';
const EXPECTED_RECEIPT_SHA256 = 'b0b570c4dbfaf49f5d448dac3d62e4d025d0fa3cbcf41e3558ab5c2fd9a8d0ca';
const EXPECTED_TESTS = 82;
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

const manifestPath = resolve(root, 'SOURCE_MANIFEST.sha256');
const manifestRows = readFileSync(manifestPath, 'utf8')
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
const expectedTargetFiles = [...EXPECTED_SOURCE_FILES, 'SOURCE_MANIFEST.sha256', 'receipts/AP-404.json'].sort();
if (JSON.stringify(targetFiles.sort()) !== JSON.stringify(expectedTargetFiles)) {
  fail(`target file set drifted: ${JSON.stringify(targetFiles)}`);
}
if (sha256(readFileSync(resolve(root, 'PREDECESSOR_RECEIPT.json'))) !== EXPECTED_PREDECESSOR_SHA256) {
  fail('predecessor receipt identity drifted');
}
if (sha256(readFileSync(resolve(root, 'receipts/AP-404.json'))) !== EXPECTED_RECEIPT_SHA256) {
  fail('AP-404 receipt identity drifted');
}

const sourceText = [
  'clients/shared/queries/contract.mjs',
  'clients/shared/queries/reducer.mjs',
  'clients/shared/queries/view-model.mjs',
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
  ['model execution', /\.realize\s*\(/],
  ['knowledge application', /(?:apply|commit|write)Knowledge/i],
  ['playback play', /\.play\s*\(/],
  ['playback pause', /\.pause\s*\(/],
  ['playback seek', /\.seek\s*\(/],
];
for (const [label, pattern] of forbidden) {
  if (pattern.test(sourceText)) fail(`forbidden authority pattern: ${label}`);
}

const test = spawnSync(
  process.execPath,
  ['--test', 'tests/ui/query-transactions/query-transactions.test.mjs'],
  { cwd: root, encoding: 'utf8', env: { ...process.env, NO_COLOR: '1', TERM: 'dumb' } },
);
process.stdout.write(test.stdout);
process.stderr.write(test.stderr);
if (test.status !== 0) fail(`AP-404 tests failed with status ${test.status}`);
const testsMatch = /# tests (\d+)/.exec(test.stdout);
const passMatch = /# pass (\d+)/.exec(test.stdout);
const failMatch = /# fail (\d+)/.exec(test.stdout);
const p95Match = /QUERY_TRANSACTION_WARM_P95_MS=([0-9.]+)/.exec(test.stdout);
if (!testsMatch || Number(testsMatch[1]) !== EXPECTED_TESTS) fail('test denominator drifted');
if (!passMatch || Number(passMatch[1]) !== EXPECTED_TESTS) fail('passing test denominator drifted');
if (!failMatch || Number(failMatch[1]) !== 0) fail('test failures observed');
if (!p95Match || Number(p95Match[1]) >= CANDIDATE_P95_MS) fail('warm projection budget exceeded');

const receipt = JSON.parse(readFileSync(resolve(root, 'receipts/AP-404.json'), 'utf8'));
if (
  receipt.transaction !== 'AP-404' ||
  receipt.canonical_ap404_accepted !== false ||
  receipt.canonical_g3_accepted !== false ||
  receipt.hosted_repository_accepted !== false ||
  receipt.target_repository_present !== false ||
  JSON.stringify(receipt.accepted_gates) !== '[]'
) fail('AP-404 authority receipt widened');

console.log(
  `AP-404 target qualified: ${EXPECTED_SOURCE_FILES.length} source files, ` +
  `${expectedTargetFiles.length} target files, ${EXPECTED_TESTS} tests passed, ` +
  `warm P95 ${Number(p95Match[1]).toFixed(6)}ms.`,
);
