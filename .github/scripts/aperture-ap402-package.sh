#!/usr/bin/env bash
set -euo pipefail

carrier="aperture-carrier"
parts="$carrier/source-archive"
work="${RUNNER_TEMP:-/tmp}/ap402-package"
out="$work/out"
extracted="$work/extracted"
archive="$work/axm-aperture-ap402-desktop-overlay-target-v1.tar.gz"
rebuilt="$work/rebuilt.tar.gz"
rm -rf "$work"
mkdir -p "$out" "$extracted"

part_count="$(find "$parts" -maxdepth 1 -type f -name 'part-*.b64' | wc -l | tr -d '[:space:]')"
test "$part_count" = "16"
cat "$parts"/part-*.b64 | tr -d '\r\n' | base64 -d > "$archive"
test "$(sha256sum "$archive" | cut -d' ' -f1)" = "$SOURCE_ARCHIVE_SHA256"
test "$(cut -d' ' -f1 "$carrier/SOURCE_ARCHIVE.sha256")" = "$SOURCE_ARCHIVE_SHA256"
test "$(sha256sum "$carrier/TARGET_SHA256SUMS" | cut -d' ' -f1)" = "$TARGET_LEDGER_SHA256"
test "$(sha256sum "$carrier/PREDECESSOR_RECEIPT.json" | cut -d' ' -f1)" = "$PREDECESSOR_RECEIPT_SHA256"
test "$(sha256sum "$carrier/AP-402.json" | cut -d' ' -f1)" = "$TARGET_RECEIPT_SHA256"

tar -xzf "$archive" -C "$extracted"
(
  cd "$extracted"
  sha256sum -c "$OLDPWD/$carrier/TARGET_SHA256SUMS"
  test "$(sha256sum aperture-target/SOURCE_MANIFEST.sha256 | cut -d' ' -f1)" = "$TARGET_MANIFEST_SHA256"
  node aperture-target/scripts/qualify.mjs > "$out/AP402_QUALIFICATION.log"
  grep -F '27 tests passed' "$out/AP402_QUALIFICATION.log"
)

# The frozen source archive records directories as 02755 and files as 0644.
# A non-root extractor must clear set-group-ID when it cannot preserve the
# archived group, so restore the declared archive mode law before rebuilding.
find "$extracted/aperture-target" -type d -exec chmod 2755 {} +
find "$extracted/aperture-target" -type f -exec chmod 0644 {} +

tar --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner \
  --mode='u+rw,go+rX,go-w' \
  -C "$extracted" -cf - aperture-target \
  | gzip -n -9 > "$rebuilt"
cmp "$archive" "$rebuilt"

cold="$work/cold"
mkdir -p "$cold"
tar -xzf "$rebuilt" -C "$cold"
(
  cd "$cold"
  sha256sum -c "$OLDPWD/$carrier/TARGET_SHA256SUMS"
  node aperture-target/scripts/qualify.mjs > "$out/COLD_RECONSTRUCTION.log"
  grep -F '27 tests passed' "$out/COLD_RECONSTRUCTION.log"
)

cp "$archive" "$out/"
cp "$carrier/TARGET_SHA256SUMS" "$out/"
cp "$carrier/PREDECESSOR_RECEIPT.json" "$out/"
cp "$carrier/AP-402.json" "$out/"
cat > "$out/CARRIER_RECEIPT.json" <<RECEIPT
{
  "accepted_gates": [],
  "aperture_gate_accepted": false,
  "ap400_world_merge": "$AP400_WORLD_MERGE",
  "ap401_artifact_id": 8946278614,
  "base_sha": "$BASE_SHA",
  "candidate_sha": "$CANDIDATE_SHA",
  "canonical_ap402_accepted": false,
  "canonical_nfr_009_accepted": false,
  "carrier_authority": "transport_and_qualification_only",
  "carrier_repository": "${GITHUB_REPOSITORY:-BigBirdReturns/axm-tools}",
  "format": "axm-aperture-ap402-carrier-receipt/2",
  "hosted_repository_accepted": false,
  "publication_status": "source_candidate_unmerged",
  "source_archive_sha256": "$SOURCE_ARCHIVE_SHA256",
  "target_repository": "$TARGET_REPOSITORY",
  "target_repository_present": false,
  "transaction": "AP-402"
}
RECEIPT
(
  cd "$out"
  sha256sum \
    axm-aperture-ap402-desktop-overlay-target-v1.tar.gz \
    CARRIER_RECEIPT.json TARGET_SHA256SUMS PREDECESSOR_RECEIPT.json AP-402.json \
    AP402_QUALIFICATION.log COLD_RECONSTRUCTION.log > PACKAGE_SHA256SUMS
  sha256sum -c PACKAGE_SHA256SUMS
)
