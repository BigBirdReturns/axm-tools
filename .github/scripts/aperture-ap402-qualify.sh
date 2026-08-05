#!/usr/bin/env bash
set -euo pipefail

carrier="aperture-carrier"
parts="$carrier/source-archive"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
archive="$work/axm-aperture-ap402-desktop-overlay-target-v1.tar.gz"

part_count="$(find "$parts" -maxdepth 1 -type f -name 'part-*.b64' | wc -l | tr -d '[:space:]')"
test "$part_count" = "16"
cat "$parts"/part-*.b64 | tr -d '\r\n' | base64 -d > "$archive"

observed_archive="$(sha256sum "$archive" | cut -d' ' -f1)"
observed_archive_ledger="$(cut -d' ' -f1 "$carrier/SOURCE_ARCHIVE.sha256")"
observed_manifest="$(sha256sum "$carrier/TARGET_SHA256SUMS" | cut -d' ' -f1)"
observed_predecessor="$(sha256sum "$carrier/PREDECESSOR_RECEIPT.json" | cut -d' ' -f1)"
observed_receipt="$(sha256sum "$carrier/AP-402.json" | cut -d' ' -f1)"
printf 'Observed source archive SHA-256: %s\n' "$observed_archive"
printf 'Observed source archive ledger: %s\n' "$observed_archive_ledger"
printf 'Observed target ledger SHA-256: %s\n' "$observed_manifest"
printf 'Observed predecessor receipt SHA-256: %s\n' "$observed_predecessor"
printf 'Observed AP-402 receipt SHA-256: %s\n' "$observed_receipt"

test "$observed_archive" = "$SOURCE_ARCHIVE_SHA256"
test "$observed_archive_ledger" = "$SOURCE_ARCHIVE_SHA256"
test "$observed_manifest" = "$TARGET_LEDGER_SHA256"
test "$observed_predecessor" = "$PREDECESSOR_RECEIPT_SHA256"
test "$observed_receipt" = "$TARGET_RECEIPT_SHA256"
tar -xzf "$archive" -C "$work"
test "$(find "$work/aperture-target" -type f | wc -l | tr -d '[:space:]')" = "11"
(
  cd "$work"
  sha256sum -c "$OLDPWD/$carrier/TARGET_SHA256SUMS"
  test "$(sha256sum aperture-target/SOURCE_MANIFEST.sha256 | cut -d' ' -f1)" = "$TARGET_MANIFEST_SHA256"
  test "$(sha256sum aperture-target/receipts/AP-402.json | cut -d' ' -f1)" = "$TARGET_RECEIPT_SHA256"
  cmp aperture-target/PREDECESSOR_RECEIPT.json "$OLDPWD/$carrier/PREDECESSOR_RECEIPT.json"
  cmp aperture-target/receipts/AP-402.json "$OLDPWD/$carrier/AP-402.json"
  node aperture-target/scripts/qualify.mjs | tee "$OLDPWD/ap402-${RUNNER_OS:-local}.log"
)
grep -F '27 tests passed' "ap402-${RUNNER_OS:-local}.log"
grep -F 'warm P95' "ap402-${RUNNER_OS:-local}.log"
git diff --exit-code
test -z "$(git status --porcelain --untracked-files=no 2>/dev/null || true)"
