#!/usr/bin/env bash
set -euo pipefail

observed_manifest="$(sha256sum aperture-target/SOURCE_MANIFEST.sha256 | cut -d' ' -f1)"
observed_receipt="$(sha256sum aperture-target/receipts/AP-401.json | cut -d' ' -f1)"
observed_files="$(find aperture-target -type f | wc -l)"
printf 'Observed manifest SHA-256: %s\n' "$observed_manifest"
printf 'Observed receipt SHA-256: %s\n' "$observed_receipt"
printf 'Observed target files: %s\n' "$observed_files"
test "$observed_manifest" = "$TARGET_MANIFEST_SHA256"
test "$observed_receipt" = "$TARGET_RECEIPT_SHA256"
test "$observed_files" -eq 11
test ! -e aperture-target/.git
test ! -e aperture-target/node_modules

node aperture-target/scripts/qualify.mjs | tee "ap401-${RUNNER_OS}.log"
grep -F '17 tests passed' "ap401-${RUNNER_OS}.log"
git diff --exit-code
test -z "$(git status --porcelain --untracked-files=no)"
