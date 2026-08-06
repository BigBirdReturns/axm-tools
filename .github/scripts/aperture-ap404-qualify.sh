#!/usr/bin/env bash
set -euo pipefail

source_root="${1:-aperture-carrier/source/aperture-target}"
repo_root="$(pwd)"
expected_archive="${SOURCE_ARCHIVE_SHA256:?SOURCE_ARCHIVE_SHA256 is required}"
expected_ledger="${TARGET_LEDGER_SHA256:?TARGET_LEDGER_SHA256 is required}"
expected_manifest="${TARGET_MANIFEST_SHA256:?TARGET_MANIFEST_SHA256 is required}"
expected_receipt="${TARGET_RECEIPT_SHA256:?TARGET_RECEIPT_SHA256 is required}"
expected_predecessor="${PREDECESSOR_RECEIPT_SHA256:?PREDECESSOR_RECEIPT_SHA256 is required}"

observed_archive="$(cut -d' ' -f1 aperture-carrier/SOURCE_ARCHIVE.sha256)"
observed_ledger="$(sha256sum aperture-carrier/TARGET_SHA256SUMS | cut -d' ' -f1)"
observed_manifest="$(sha256sum "$source_root/SOURCE_MANIFEST.sha256" | cut -d' ' -f1)"
observed_receipt="$(sha256sum "$source_root/receipts/AP-404.json" | cut -d' ' -f1)"
observed_predecessor="$(sha256sum "$source_root/PREDECESSOR_RECEIPT.json" | cut -d' ' -f1)"

printf 'Observed source archive ledger: %s\n' "$observed_archive"
printf 'Observed target ledger SHA-256: %s\n' "$observed_ledger"
printf 'Observed source manifest SHA-256: %s\n' "$observed_manifest"
printf 'Observed AP-404 receipt SHA-256: %s\n' "$observed_receipt"
printf 'Observed predecessor receipt SHA-256: %s\n' "$observed_predecessor"

test "$observed_archive" = "$expected_archive"
test "$observed_ledger" = "$expected_ledger"
test "$observed_manifest" = "$expected_manifest"
test "$observed_receipt" = "$expected_receipt"
test "$observed_predecessor" = "$expected_predecessor"

(
  cd "$source_root"
  sha256sum -c "$repo_root/aperture-carrier/TARGET_SHA256SUMS"
  node scripts/qualify.mjs .
)
