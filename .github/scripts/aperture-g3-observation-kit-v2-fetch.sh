#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <output-tar-gz>" >&2
  exit 64
fi

output="$1"
expected_sha256="71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74"
expected_bytes="90028"
ledger="aperture-kit-v2-carrier/CANDIDATE_BLOBS.txt"

[[ -n "${GH_TOKEN:-}" ]]
[[ -f "$ledger" ]]
mapfile -t shas < <(grep -E '^[0-9a-f]{40}$' "$ledger")
[[ ${#shas[@]} -eq 5 ]]
[[ "$(printf '%s\n' "${shas[@]}" | LC_ALL=C sort -u | wc -l | tr -d '[:space:]')" == "5" ]]

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

python - "$work" "${shas[@]}" <<'PY'
import base64
import json
import os
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
shas = sys.argv[2:]
repo = os.environ['GITHUB_REPOSITORY']
token = os.environ['GH_TOKEN']
for index, sha in enumerate(shas):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/git/blobs/{sha}',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'AXM-Aperture-Kit-V2-Fetch/1',
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        value = json.load(response)
    if value.get('sha') != sha or value.get('encoding') != 'base64':
        raise SystemExit(f'invalid Git blob response for {sha}')
    raw = base64.b64decode(value['content'], validate=False)
    (out / f'{index:02d}-{sha}.blob').write_bytes(raw)
PY

matches=()
while IFS= read -r -d '' path; do
  digest="$(sha256sum "$path" | cut -d' ' -f1)"
  bytes="$(wc -c < "$path" | tr -d '[:space:]')"
  printf '%s %s %s\n' "$digest" "$bytes" "$(basename "$path")"
  if [[ "$digest" == "$expected_sha256" && "$bytes" == "$expected_bytes" ]]; then
    matches+=("$path")
  fi
done < <(find "$work" -type f -print0 | LC_ALL=C sort -z)

[[ ${#matches[@]} -eq 1 ]]
mkdir -p "$(dirname "$output")"
cp "${matches[0]}" "$output"
[[ "$(sha256sum "$output" | cut -d' ' -f1)" == "$expected_sha256" ]]
[[ "$(wc -c < "$output" | tr -d '[:space:]')" == "$expected_bytes" ]]
tar -tzf "$output" >/dev/null
printf 'FETCHED_SOURCE_SHA256=%s\n' "$expected_sha256"
