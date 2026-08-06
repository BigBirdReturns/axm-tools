#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_root="${1:-$repo_root/aperture-carrier/source/aperture-target}"
ledger="$repo_root/aperture-carrier/TARGET_SHA256SUMS"

observed_ledger="$(sha256sum "$ledger" | cut -d' ' -f1)"
observed_manifest="$(sha256sum "$source_root/SOURCE_MANIFEST.sha256" | cut -d' ' -f1)"
observed_receipt="$(sha256sum "$source_root/receipts/AP-406.json" | cut -d' ' -f1)"
observed_predecessor="$(sha256sum "$source_root/PREDECESSOR_RECEIPT.json" | cut -d' ' -f1)"
printf 'Observed target ledger SHA-256: %s\n' "$observed_ledger"
printf 'Observed source manifest SHA-256: %s\n' "$observed_manifest"
printf 'Observed AP-406 receipt SHA-256: %s\n' "$observed_receipt"
printf 'Observed predecessor receipt SHA-256: %s\n' "$observed_predecessor"
test "$observed_ledger" = "$TARGET_LEDGER_SHA256"
test "$observed_manifest" = "$TARGET_MANIFEST_SHA256"
test "$observed_receipt" = "$TARGET_RECEIPT_SHA256"
test "$observed_predecessor" = "$PREDECESSOR_RECEIPT_SHA256"
(
  cd "$source_root"
  sha256sum -c "$ledger"
  node scripts/qualify.mjs
)
