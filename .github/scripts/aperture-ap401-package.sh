#!/usr/bin/env bash
set -euo pipefail

work="$RUNNER_TEMP/ap401-package"
out="$work/out"
root="$work/root"
reconstructed="$work/reconstructed"
rm -rf "$work"
mkdir -p "$out" "$root/aperture-target" "$reconstructed"
cp -a aperture-target/. "$root/aperture-target/"

cat > "$root/CARRIER_RECEIPT.json" <<RECEIPT
{
  "accepted_gates": [],
  "aperture_gate_accepted": false,
  "ap400_world_merge": "$AP400_WORLD_MERGE",
  "base_sha": "$BASE_SHA",
  "candidate_sha": "$CANDIDATE_SHA",
  "carrier_authority": "transport_and_qualification_only",
  "carrier_repository": "$GITHUB_REPOSITORY",
  "format": "axm-aperture-ap401-carrier-receipt/1",
  "hosted_repository_accepted": false,
  "publication_status": "source_candidate_unmerged",
  "target_repository": "$TARGET_REPOSITORY",
  "target_repository_present": false,
  "transaction": "AP-401"
}
RECEIPT

(
  cd "$root"
  find aperture-target -type f -printf '%P\0' | sort -z | xargs -0 -I{} sha256sum "aperture-target/{}" > TARGET_SHA256SUMS
  sha256sum -c TARGET_SHA256SUMS
  test "$(sha256sum aperture-target/SOURCE_MANIFEST.sha256 | cut -d' ' -f1)" = "$TARGET_MANIFEST_SHA256"
  test "$(sha256sum aperture-target/receipts/AP-401.json | cut -d' ' -f1)" = "$TARGET_RECEIPT_SHA256"
  node aperture-target/scripts/qualify.mjs > AP401_QUALIFICATION.log
  grep -F '17 tests passed' AP401_QUALIFICATION.log
)

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -C "$root" -cf - . | gzip -n -9 > "$out/axm-aperture-ap401-coach-target-v1.tar.gz"
(
  cd "$out"
  sha256sum axm-aperture-ap401-coach-target-v1.tar.gz > PACKAGE_SHA256SUMS
)
cp "$root/CARRIER_RECEIPT.json" "$out/"
cp "$root/TARGET_SHA256SUMS" "$out/"
cp "$root/AP401_QUALIFICATION.log" "$out/"

tar -xzf "$out/axm-aperture-ap401-coach-target-v1.tar.gz" -C "$reconstructed"
(
  cd "$reconstructed"
  sha256sum -c TARGET_SHA256SUMS
  test "$(sha256sum aperture-target/SOURCE_MANIFEST.sha256 | cut -d' ' -f1)" = "$TARGET_MANIFEST_SHA256"
  test "$(sha256sum aperture-target/receipts/AP-401.json | cut -d' ' -f1)" = "$TARGET_RECEIPT_SHA256"
  node aperture-target/scripts/qualify.mjs > COLD_RECONSTRUCTION.log
  grep -F '17 tests passed' COLD_RECONSTRUCTION.log
)
cp "$reconstructed/COLD_RECONSTRUCTION.log" "$out/"
(
  cd "$out"
  sha256sum CARRIER_RECEIPT.json TARGET_SHA256SUMS AP401_QUALIFICATION.log COLD_RECONSTRUCTION.log >> PACKAGE_SHA256SUMS
  sha256sum -c PACKAGE_SHA256SUMS
)
