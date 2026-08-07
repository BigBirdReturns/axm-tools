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

node_version="$(node --version)"
[[ "$node_version" == "v22.16.0" ]]
printf '%s\n' "$node_version" > "$work/node-version.txt"

(
  cd "$root"
  find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "$work/source-inventory.sha256"
)

require_digest_once() {
  local digest="$1"
  local label="$2"
  local count
  count="$(awk -v d="$digest" 'tolower($1)==d {n++} END {print n+0}' "$work/source-inventory.sha256")"
  if [[ "$count" != "1" ]]; then
    echo "expected one $label file at $digest; observed $count" >&2
    exit 1
  fi
}

require_digest_once "$expected_matrix_sha256" "source matrix"
require_digest_once "$expected_source_manifest_sha256" "source manifest"
require_digest_once "$expected_package_manifest_sha256" "package manifest"

grep -R -Fq -- "$kit_id" "$root"
grep -R -Fq -- "$qualification_id" "$root"
grep -R -Fq -- "$blocked_progress_id" "$root"

if find "$root" -type f -iname 'RUNTIME_BINDING.json' -print -quit | grep -q .; then
  echo "clean carrier unexpectedly contains a runtime binding" >&2
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
)
(
  cd "$root"
  node scripts/compile-progress.mjs 2>&1 | tee "$work/logs/compile-progress.log"
)

python - "$root" "$blocked_progress_id" "$work/blocked-progress.json" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
expected_id = sys.argv[2]
out = pathlib.Path(sys.argv[3])

matches = []
for path in sorted(root.rglob("*.json")):
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except Exception:
        continue
    if expected_id in raw:
        matches.append((path, value, raw))

if len(matches) != 1:
    raise SystemExit(f"expected one blocked progress JSON, found {len(matches)}")
path, value, raw = matches[0]
flat = []
def walk(node, prefix=()):
    if isinstance(node, dict):
        for key, item in node.items():
            walk(item, prefix + (str(key),))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            walk(item, prefix + (str(index),))
    else:
        flat.append((".".join(prefix).lower(), node))
walk(value)

strings = [str(v).lower() for _, v in flat if isinstance(v, str)]
if "blocked" not in strings:
    raise SystemExit("blocked progress does not declare BLOCKED")
if "runtime_binding_missing" not in strings:
    raise SystemExit("blocked progress lacks runtime_binding_missing")

for path_key, item in flat:
    compact = path_key.replace("_", "").replace("-", "")
    if isinstance(item, bool) and ("canonicalap410accepted" in compact or "canonicalg3accepted" in compact):
        if item is not False:
            raise SystemExit(f"gate inflation at {path_key}")
    if isinstance(item, int) and any(token in compact for token in (
        "observedinteractions", "observedvisuals", "readergroups", "manualreadergroups"
    )):
        if item != 0:
            raise SystemExit(f"nonzero clean progress at {path_key}: {item}")

out.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"BLOCKED_PROGRESS_SOURCE={path.relative_to(root).as_posix()}")
PY

grep -Fq -- "$blocked_progress_id" "$work/blocked-progress.json"
grep -Fq -- 'runtime_binding_missing' "$work/blocked-progress.json"

printf '%s\n' \
  "archive_sha256=$observed_sha256" \
  "archive_bytes=$observed_bytes" \
  "kit=$kit_id" \
  "qualification=$qualification_id" \
  "blocked_progress=$blocked_progress_id" \
  "contracts=49" \
  "status=PASS" \
  > "$work/qualification.env"

printf 'AP-410 observation-kit v2 qualification PASS\n'
