#!/usr/bin/env bash
set -euo pipefail

carrier="aperture-carrier"
parts="$carrier/source-archive"
work="${RUNNER_TEMP:-/tmp}/ap403-package"
out="$work/out"
extracted="$work/extracted"
cold="$work/cold"
archive="$work/axm-aperture-ap403-second-screen-target-v1.tar.gz"
rebuilt="$work/rebuilt.tar.gz"
rm -rf "$work"
mkdir -p "$out" "$extracted" "$cold"

cat "$parts"/part-*.b64 | tr -d '\r\n' | base64 -d > "$archive"
test "$(sha256sum "$archive" | cut -d' ' -f1)" = "$SOURCE_ARCHIVE_SHA256"
tar -xzf "$archive" -C "$extracted"
(
  cd "$extracted"
  sha256sum -c "$OLDPWD/$carrier/TARGET_SHA256SUMS"
  node aperture-target/scripts/qualify.mjs > "$out/AP403_QUALIFICATION.log"
  grep -F '52 tests passed' "$out/AP403_QUALIFICATION.log"
)

tar --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner \
  --mode='a-s,u+rw,go+rX,go-w' \
  -C "$extracted" -cf - aperture-target \
  | gzip -n -9 > "$rebuilt"
cmp "$archive" "$rebuilt"

tar -xzf "$rebuilt" -C "$cold"
(
  cd "$cold"
  sha256sum -c "$OLDPWD/$carrier/TARGET_SHA256SUMS"
  node aperture-target/scripts/qualify.mjs > "$out/COLD_RECONSTRUCTION.log"
  grep -F '52 tests passed' "$out/COLD_RECONSTRUCTION.log"
)

cp "$archive" "$out/"
cp "$carrier/TARGET_SHA256SUMS" "$out/"
cp "$carrier/PREDECESSOR_RECEIPT.json" "$out/"
cp "$carrier/AP-403.json" "$out/"
cat > "$out/CARRIER_RECEIPT.json" <<RECEIPT
{
  "accepted_gates": [],
  "aperture_gate_accepted": false,
  "ap219_accepted": false,
  "base_sha": "$BASE_SHA",
  "candidate_sha": "$CANDIDATE_SHA",
  "canonical_ap403_accepted": false,
  "canonical_g4_accepted": false,
  "canonical_native_client_accepted": false,
  "carrier_authority": "transport_and_qualification_only",
  "carrier_repository": "${GITHUB_REPOSITORY:-BigBirdReturns/axm-tools}",
  "format": "axm-aperture-ap403-carrier-receipt/1",
  "hosted_repository_accepted": false,
  "publication_status": "source_candidate_unmerged",
  "source_archive_sha256": "$SOURCE_ARCHIVE_SHA256",
  "target_repository": "$TARGET_REPOSITORY",
  "target_repository_present": false,
  "transaction": "AP-403"
}
RECEIPT
(
  cd "$out"
  sha256sum \
    axm-aperture-ap403-second-screen-target-v1.tar.gz \
    CARRIER_RECEIPT.json TARGET_SHA256SUMS PREDECESSOR_RECEIPT.json AP-403.json \
    AP403_QUALIFICATION.log COLD_RECONSTRUCTION.log > PACKAGE_SHA256SUMS
  sha256sum -c PACKAGE_SHA256SUMS
)
