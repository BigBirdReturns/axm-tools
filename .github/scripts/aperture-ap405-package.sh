#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_root="$repo_root/aperture-carrier/source/aperture-target"
work="${RUNNER_TEMP:-/tmp}/aperture-ap405-package"
out="$work/out"
archive="$out/axm-aperture-ap405-selection-transactions-target-v1.tar.gz"
rebuilt="$work/rebuilt.tar.gz"
cold="$work/cold"
rm -rf "$work"
mkdir -p "$work/stage" "$out" "$cold"

bash "$repo_root/.github/scripts/aperture-ap405-qualify.sh" "$source_root" | tee "$out/qualification.log"
cp -a "$source_root" "$work/stage/aperture-target"
find "$work/stage/aperture-target" -type d -exec chmod 0755 {} +
find "$work/stage/aperture-target" -type f -exec chmod 0644 {} +
(
  cd "$work/stage"
  tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
    --mode='a-s,u+rwX,go+rX,go-w' -cf - aperture-target | gzip -n -9 > "$archive"
  tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
    --mode='a-s,u+rwX,go+rX,go-w' -cf - aperture-target | gzip -n -9 > "$rebuilt"
)
cmp "$archive" "$rebuilt"
observed_archive_sha="$(sha256sum "$archive" | cut -d' ' -f1)"
printf 'Observed deterministic source archive SHA-256: %s\n' "$observed_archive_sha"
test "$observed_archive_sha" = "$SOURCE_ARCHIVE_SHA256"

tar -xzf "$archive" -C "$cold"
bash "$repo_root/.github/scripts/aperture-ap405-qualify.sh" "$cold/aperture-target" | tee "$out/cold-reconstruction.log"

cp "$repo_root/aperture-carrier/SOURCE_ARCHIVE.sha256" "$out/"
cp "$repo_root/aperture-carrier/TARGET_SHA256SUMS" "$out/"
cp "$source_root/SOURCE_MANIFEST.sha256" "$out/"
cp "$source_root/PREDECESSOR_RECEIPT.json" "$out/"
cp "$source_root/receipts/AP-405.json" "$out/"

node - "$out/CARRIER_RECEIPT.json" <<'NODE'
import { writeFileSync } from 'node:fs';
const [output] = process.argv.slice(2);
const receipt = {
  accepted_gates: [],
  aperture_gate_accepted: false,
  canonical_ap405_accepted: false,
  canonical_g3_accepted: false,
  canonical_native_client_accepted: false,
  carrier_authority: 'transport_and_qualification_only',
  candidate_sha: process.env.CANDIDATE_SHA,
  base_sha: process.env.BASE_SHA,
  format: 'axm-aperture-ap405-source-carrier-receipt/1',
  hosted_repository_accepted: false,
  publication_status: 'source_candidate_unmerged',
  source_archive_sha256: process.env.SOURCE_ARCHIVE_SHA256,
  source_files: 9,
  source_manifest_sha256: process.env.TARGET_MANIFEST_SHA256,
  target_files: 11,
  target_receipt_sha256: process.env.TARGET_RECEIPT_SHA256,
  target_repository: 'BigBirdReturns/axm-aperture',
  target_repository_present: false,
  tests_passed_per_execution: 91,
  transaction: 'AP-405',
};
writeFileSync(output, `${JSON.stringify(receipt, null, 2)}\n`);
NODE
(
  cd "$out"
  sha256sum \
    axm-aperture-ap405-selection-transactions-target-v1.tar.gz \
    SOURCE_ARCHIVE.sha256 \
    TARGET_SHA256SUMS \
    SOURCE_MANIFEST.sha256 \
    PREDECESSOR_RECEIPT.json \
    AP-405.json \
    CARRIER_RECEIPT.json \
    qualification.log \
    cold-reconstruction.log \
    > SHA256SUMS
  sha256sum -c SHA256SUMS
)
printf '%s\n' "$out"
