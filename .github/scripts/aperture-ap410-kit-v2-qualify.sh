#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <source-tar-gz> <work-root>" >&2
  exit 64
fi

archive="$1"
work="$2"
expected_archive_sha256="71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74"
expected_archive_bytes="90028"
expected_matrix_sha256="aef281d81fae08bf350e700948405f98d49a770442a323189b16c9b9f005f657"
expected_source_manifest_sha256="014a5d9f0dc8803484333c7deb7dadc89f38f96667c69d8fc72699923f3ae6ca"
expected_package_manifest_sha256="87218d601ff0d4f7d577d6c5bf476b2dbd073a7176d192cba24f3745c28030b7"
kit_id="g3observationkit2_6a0784236b71e0c78d22a6087aa837764eadddee17cc58e9522e909358eda9a1"
qualification_id="g3observationqualification2_14f759a2212a9119e6d9f0ae81e0e7f9a5937ceddcbe1e2b00864e51380bd4ec"
blocked_progress_id="uiprogress2_6073d7e2855ec35fece231f86e0cc0aa94ed9499d1b7a44d7fdbd5d1f2837cf2"

rm -rf "$work"
mkdir -p "$work/extract" "$work/logs"

observed_sha256="$(sha256sum "$archive" | awk '{print tolower($1)}')"
observed_bytes="$(wc -c < "$archive" | tr -d '[:space:]')"
[[ "$observed_sha256" == "$expected_archive_sha256" ]]
[[ "$observed_bytes" == "$expected_archive_bytes" ]]
printf '%s  %s\n' "$observed_sha256" "$(basename "$archive")" > "$work/archive.sha256"

tar -xzf "$archive" -C "$work/extract"
mapfile -t verifier_paths < <(find "$work/extract" -type f -path '*/scripts/verify-package.mjs' -print | LC_ALL=C sort)
[[ ${#verifier_paths[@]} -eq 1 ]]
root="$(dirname "$(dirname "${verifier_paths[0]}")")"
printf '%s\n' "$root" > "$work/source-root.txt"

[[ "$(node --version)" == "v22.16.0" ]]
printf '%s\n' "$(node --version)" > "$work/node-version.txt"

(
  cd "$root"
  find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "$work/source-inventory.sha256"
)

require_digest_once() {
  local digest="$1"
  local label="$2"
  local count
  count="$(awk -v d="$digest" 'tolower($1)==d {n++} END {print n+0}' "$work/source-inventory.sha256")"
  [[ "$count" == "1" ]] || {
    echo "expected one $label file at $digest; observed $count" >&2
    exit 1
  }
}

require_digest_once "$expected_source_manifest_sha256" "source manifest"
require_digest_once "$expected_package_manifest_sha256" "package manifest"

observed_matrix_sha256="$(
  cd "$root"
  node --input-type=module <<'NODE'
import { createHash } from 'node:crypto';
import { buildSourceMatrix } from './lib/ui-matrix.mjs';
import { canonicalJson } from './lib/ui-contract.mjs';
process.stdout.write(createHash('sha256').update(canonicalJson(buildSourceMatrix())).digest('hex'));
NODE
)"
[[ "$observed_matrix_sha256" == "$expected_matrix_sha256" ]]
printf '%s\n' "$observed_matrix_sha256" > "$work/source-matrix.sha256"

grep -R -Fq -- "$kit_id" "$root"
grep -R -Fq -- "$qualification_id" "$root"
grep -R -Fq -- "$blocked_progress_id" "$root"

if find "$root" -type f -iname 'RUNTIME_BINDING.json' -print -quit | grep -q .; then
  echo "clean source unexpectedly contains a runtime binding" >&2
  exit 1
fi

(
  cd "$root"
  node --test tests/*.test.mjs 2>&1 | tee "$work/logs/contracts.log"
)
grep -Eq '# tests[[:space:]]+49|tests[[:space:]]+49' "$work/logs/contracts.log"
grep -Eq '# pass[[:space:]]+49|pass[[:space:]]+49' "$work/logs/contracts.log"
grep -Eq '# fail[[:space:]]+0|fail[[:space:]]+0' "$work/logs/contracts.log"

(
  cd "$root"
  node scripts/verify-package.mjs 2>&1 | tee "$work/logs/verify-package.log"
  node scripts/compile-progress.mjs 2>&1 | tee "$work/logs/compile-progress.log"
)

python - "$root" "$blocked_progress_id" "$work/blocked-progress.json" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
expected_id = sys.argv[2]
out = pathlib.Path(sys.argv[3])
references = []
candidates = []
for path in sorted(root.rglob('*.json')):
    try:
        raw = path.read_text(encoding='utf-8')
        value = json.loads(raw)
    except Exception:
        continue
    if expected_id not in raw:
        continue
    references.append(path)
    if not isinstance(value, dict):
        continue
    if value.get('format') != 'axm-aperture-platform-observation-progress/2':
        continue
    if value.get('progressId') != expected_id:
        continue
    candidates.append((path, value))

if not references:
    raise SystemExit('blocked progress identity is absent from JSON custody')
if len(candidates) != 1:
    raise SystemExit(
        f'expected one progress receipt object, found {len(candidates)}; '
        f'identity references={len(references)}'
    )
path, value = candidates[0]
expected = {
    'bindingId': None,
    'runtimeBindingVerified': False,
    'matrixCells': 108,
    'observedInteractions': 0,
    'observedVisuals': 0,
    'observedReaderGroups': 0,
    'requiredReaderGroups': 5,
    'status': 'BLOCKED',
    'sourceCompilerAccepted': False,
    'canonicalAp410Accepted': False,
    'canonicalG3Accepted': False,
    'hostedRepositoryAccepted': False,
    'waivers': [],
    'authority': 'evidence_progress_only',
}
for key, expected_value in expected.items():
    if value.get(key) != expected_value:
        raise SystemExit(f'blocked progress mismatch at {key}: {value.get(key)!r}')
if value.get('reasonCodes') != ['runtime_binding_missing']:
    raise SystemExit(f"blocked progress reason mismatch: {value.get('reasonCodes')!r}")
out.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
print(f'BLOCKED_PROGRESS_SOURCE={path.relative_to(root).as_posix()}')
print(f'BLOCKED_PROGRESS_REFERENCES={len(references)}')
PY

grep -Fq -- "$blocked_progress_id" "$work/blocked-progress.json"
grep -Fq -- 'runtime_binding_missing' "$work/blocked-progress.json"
printf '%s\n' \
  "archive_sha256=$observed_sha256" \
  "archive_bytes=$observed_bytes" \
  "source_matrix_sha256=$observed_matrix_sha256" \
  "kit=$kit_id" \
  "qualification=$qualification_id" \
  "blocked_progress=$blocked_progress_id" \
  "contracts=49" \
  "status=PASS" \
  > "$work/qualification.env"
printf 'AP-410 observation-kit v2 qualification PASS\n'
