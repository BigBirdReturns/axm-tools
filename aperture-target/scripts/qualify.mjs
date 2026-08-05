import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifestPath = join(root, 'SOURCE_MANIFEST.sha256');
const receiptPath = join(root, 'receipts', 'AP-401.json');
const expectedSourcePaths = [
  'DONOR_RECEIPT.json',
  'README.md',
  'clients/shared/coach/contract.mjs',
  'clients/shared/coach/index.mjs',
  'clients/shared/coach/reducer.mjs',
  'clients/shared/coach/view-model.mjs',
  'scripts/qualify.mjs',
  'tests/ui/coach/coach.test.mjs',
  'tests/ui/coach/fixtures.mjs',
];

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) paths.push(...(await walk(path)));
    else paths.push(path);
  }
  return paths;
}

function portableRelative(path) {
  return relative(root, path).replaceAll('\\', '/');
}

const files = (await walk(root)).filter((path) => {
  const portablePath = portableRelative(path);
  return portablePath !== 'SOURCE_MANIFEST.sha256' && portablePath !== 'receipts/AP-401.json';
});
const observed = [];
for (const path of files) {
  const digest = createHash('sha256').update(await readFile(path)).digest('hex');
  observed.push(`${digest}  ${portableRelative(path)}`);
}
observed.sort((left, right) => {
  const leftPath = left.slice(66);
  const rightPath = right.slice(66);
  return leftPath < rightPath ? -1 : leftPath > rightPath ? 1 : 0;
});
const expected = (await readFile(manifestPath, 'utf8')).trim().split(/\r?\n/);
const expectedPaths = expected.map((line) => line.slice(66));
if (JSON.stringify(expectedPaths) !== JSON.stringify(expectedSourcePaths)) {
  throw new Error('source_manifest_path_set_invalid');
}
if (JSON.stringify(observed) !== JSON.stringify(expected)) {
  console.error('SOURCE_MANIFEST.sha256 does not match the exact target tree.');
  console.error('EXPECTED\n' + expected.join('\n'));
  console.error('OBSERVED\n' + observed.join('\n'));
  process.exit(1);
}

const receipt = JSON.parse(await readFile(receiptPath, 'utf8'));
if (receipt.transaction !== 'AP-401') throw new Error('receipt_transaction_mismatch');
if (receipt.status !== 'source_candidate') throw new Error('receipt_status_mismatch');
if (receipt.carrier_authority !== 'transport_and_qualification_only') {
  throw new Error('receipt_carrier_authority_invalid');
}
if (receipt.aperture_gate_accepted !== false || receipt.hosted_repository_accepted !== false) {
  throw new Error('receipt_gate_inflation');
}
if (receipt.source_files !== 9 || receipt.tests_passed !== 17) {
  throw new Error('receipt_denominator_mismatch');
}
const donor = JSON.parse(await readFile(join(root, 'DONOR_RECEIPT.json'), 'utf8'));
if (
  donor.transaction !== 'AP-401' ||
  donor.donor?.version !== '1.1.0' ||
  donor.donor?.authority !== 'qualified_behavioral_donor_only' ||
  donor.donor?.source_tests_passed !== 62 ||
  donor.donor?.mutations_killed !== 20 ||
  donor.donor?.mutations_survived !== 0 ||
  donor.donor?.embedded_player_script_sha256 !==
    'bc18dc52878a5907c0feb966f4c7b62d5c49b36267ae0ad9a9d2aa62384747f9' ||
  donor.manual_specific_phase_semantics_copied !== false ||
  donor.manual_dom_or_player_code_copied !== false ||
  donor.carrier_authority !== 'transport_and_qualification_only'
) {
  throw new Error('donor_receipt_invalid');
}
const donorEvidence = new Map(donor.evidence.map((entry) => [entry.name, entry.sha256]));
for (const [name, digest] of [
  ['standalone.html', 'cec1e58a9d9c639725ad6fbaf40d2b83debb328529ac233c5503f7366abfe083'],
  ['QA_REPORT_V1.1.0.md', 'b6f0fa867432b95b3b88b7b5b14787a83ee4c4f57bf01758ae8acc24edf1bb67'],
  ['mutation-test.json', 'c402f5bdb7e0e0a86f7119e82acb5cb731b4af21b140bc78c0050eecec5622a7'],
]) {
  if (donorEvidence.get(name) !== digest) throw new Error(`donor_evidence_digest_mismatch:${name}`);
}
if (receipt.source_manifest_sha256 !== createHash('sha256').update((await readFile(manifestPath))).digest('hex')) {
  throw new Error('receipt_manifest_digest_mismatch');
}

const forbidden = [
  /setInterval\s*\(/,
  /setTimeout\s*\(/,
  /requestAnimationFrame\s*\(/,
  /Date\.now\s*\(/,
  /performance\.now\s*\(/,
  /new Date\s*\(/,
  /currentTime\s*=/,
  /\.play\s*\(/,
  /\.pause\s*\(/,
  /\bfetch\s*\(/,
  /WebSocket\s*\(/,
  /localStorage/,
  /sessionStorage/,
  /HTMLMediaElement/,
  /\bdocument\./,
  /\bwindow\./,
  /\bnavigator\./,
  /\bSTART\b/,
  /\bMOVE\b/,
  /\bCHECK\b/,
];
const sourceDirectory = join(root, 'clients', 'shared', 'coach');
for (const path of await walk(sourceDirectory)) {
  const text = await readFile(path, 'utf8');
  for (const pattern of forbidden) {
    if (pattern.test(text)) throw new Error(`forbidden_authority_pattern:${relative(root, path)}:${pattern}`);
  }
}

const tests = spawnSync(
  process.execPath,
  ['--test', join(root, 'tests', 'ui', 'coach', 'coach.test.mjs')],
  { encoding: 'utf8' },
);
process.stdout.write(tests.stdout ?? '');
process.stderr.write(tests.stderr ?? '');
if (tests.status !== 0) process.exit(tests.status ?? 1);
if (!/# tests 17(?:\r?\n)/.test(tests.stdout ?? '') || !/# pass 17(?:\r?\n)/.test(tests.stdout ?? '')) {
  throw new Error('test_denominator_mismatch');
}
if (!/# fail 0(?:\r?\n)/.test(tests.stdout ?? '')) throw new Error('test_failure_denominator_mismatch');
console.log(`AP-401 target qualified: ${files.length} source files, manifest exact, 17 tests passed.`);
