#!/usr/bin/env bash
set -euo pipefail

root="${1:-aperture-carrier/source/aperture-target}"
expected_archive_sha="${SOURCE_ARCHIVE_SHA256:?SOURCE_ARCHIVE_SHA256 is required}"
expected_ledger_sha="${TARGET_LEDGER_SHA256:?TARGET_LEDGER_SHA256 is required}"
expected_manifest_sha="${TARGET_MANIFEST_SHA256:?TARGET_MANIFEST_SHA256 is required}"
expected_receipt_sha="${TARGET_RECEIPT_SHA256:?TARGET_RECEIPT_SHA256 is required}"
expected_predecessor_sha="${PREDECESSOR_RECEIPT_SHA256:?PREDECESSOR_RECEIPT_SHA256 is required}"

ledger_path="$(pwd)/aperture-carrier/TARGET_SHA256SUMS"
observed_ledger_sha="$(sha256sum "$ledger_path" | cut -d' ' -f1)"
observed_manifest_sha="$(sha256sum "$root/SOURCE_MANIFEST.sha256" | cut -d' ' -f1)"
observed_receipt_sha="$(sha256sum "$root/receipts/AP-403.json" | cut -d' ' -f1)"
observed_predecessor_sha="$(sha256sum "$root/PREDECESSOR_RECEIPT.json" | cut -d' ' -f1)"
observed_archive_ledger="$(cut -d' ' -f1 aperture-carrier/SOURCE_ARCHIVE.sha256)"

printf 'Observed target ledger SHA-256: %s\n' "$observed_ledger_sha"
printf 'Observed source manifest SHA-256: %s\n' "$observed_manifest_sha"
printf 'Observed AP-403 receipt SHA-256: %s\n' "$observed_receipt_sha"
printf 'Observed predecessor receipt SHA-256: %s\n' "$observed_predecessor_sha"
printf 'Declared source archive SHA-256: %s\n' "$observed_archive_ledger"

test "$observed_ledger_sha" = "$expected_ledger_sha"
test "$observed_manifest_sha" = "$expected_manifest_sha"
test "$observed_receipt_sha" = "$expected_receipt_sha"
test "$observed_predecessor_sha" = "$expected_predecessor_sha"
test "$observed_archive_ledger" = "$expected_archive_sha"

(
  cd "$root"
  sha256sum -c "$ledger_path"
  node scripts/qualify.mjs
)
