#!/usr/bin/env python3
"""Verify and reconstruct the exact AP-410 Kit v2 archive from overlapping Git blobs."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import pathlib
import tarfile
import tempfile
from typing import Any

EXPECTED_FORMAT = "axm-aperture-g3-observation-kit-v2-git-blob-dispatch/1"
EXPECTED_SOURCE_NAME = "AXM-Aperture-G3-Platform-Observation-Kit-v2.tar.gz"
EXPECTED_SOURCE_BYTES = 90028
EXPECTED_SOURCE_SHA256 = "71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74"
EXPECTED_MATRIX_CANONICAL_SHA256 = "aef281d81fae08bf350e700948405f98d49a770442a323189b16c9b9f005f657"
EXPECTED_UI_MATRIX_FILE_SHA256 = "effa2851e327b834bb233822b885fc3b17de7c234155404cf03d5ded572af675"
EXPECTED_SOURCE_MANIFEST_SHA256 = "014a5d9f0dc8803484333c7deb7dadc89f38f96667c69d8fc72699923f3ae6ca"
EXPECTED_PACKAGE_MANIFEST_SHA256 = "87218d601ff0d4f7d577d6c5bf476b2dbd073a7176d192cba24f3745c28030b7"
EXPECTED_KIT_ID = "g3observationkit2_6a0784236b71e0c78d22a6087aa837764eadddee17cc58e9522e909358eda9a1"
EXPECTED_QUALIFICATION_ID = "g3observationqualification2_14f759a2212a9119e6d9f0ae81e0e7f9a5937ceddcbe1e2b00864e51380bd4ec"
EXPECTED_PROGRESS_ID = "uiprogress2_6073d7e2855ec35fece231f86e0cc0aa94ed9499d1b7a44d7fdbd5d1f2837cf2"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(value: bytes) -> str:
    return hashlib.sha1(f"blob {len(value)}\0".encode("ascii") + value).hexdigest()


def refuse(message: str) -> None:
    raise SystemExit(f"REFUSED: {message}")


def scalar_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from scalar_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from scalar_values(item)
    else:
        yield value


def suffix_prefix_overlap(left: bytes, right: bytes) -> int:
    """Return the longest suffix of left equal to a prefix of right in O(n)."""
    limit = min(len(left), len(right))
    sequence = list(right[:limit]) + [256] + list(left[-limit:])
    prefix = [0] * len(sequence)
    for index in range(1, len(sequence)):
        cursor = prefix[index - 1]
        while cursor and sequence[index] != sequence[cursor]:
            cursor = prefix[cursor - 1]
        if sequence[index] == sequence[cursor]:
            cursor += 1
        prefix[index] = cursor
    return prefix[-1]


def assemble_order(parts: list[bytes], order: tuple[int, ...], overlaps: dict[tuple[int, int], int]) -> tuple[bytes, list[int]] | None:
    assembled = parts[order[0]]
    used: list[int] = []
    for previous, current in zip(order, order[1:]):
        raw = parts[current]
        overlap = overlaps[(previous, current)]
        if overlap == 0:
            location = assembled.find(raw)
            if location >= 0:
                overlap = len(raw)
            else:
                return None
        assembled += raw[overlap:]
        used.append(overlap)
    return assembled, used


def reconstruct(parts: list[bytes]) -> tuple[bytes, dict[str, Any]]:
    overlaps = {
        (left, right): suffix_prefix_overlap(parts[left], parts[right])
        for left in range(len(parts))
        for right in range(len(parts))
        if left != right
    }
    candidates: list[tuple[int, tuple[int, ...], bytes, list[int]]] = []
    gzip_starts = [index for index, raw in enumerate(parts) if raw.startswith(b"\x1f\x8b")]
    first_choices = gzip_starts or list(range(len(parts)))
    for first in first_choices:
        remainder = [index for index in range(len(parts)) if index != first]
        for tail in itertools.permutations(remainder):
            order = (first, *tail)
            result = assemble_order(parts, order, overlaps)
            if result is None:
                continue
            assembled, used = result
            candidates.append((len(assembled), order, assembled, used))
    if not candidates:
        refuse("transport parts have no complete ordered overlap path")
    candidates.sort(key=lambda item: (item[0], item[1]))
    seen: set[str] = set()
    diagnostics = []
    for length, order, assembled, used in candidates:
        candidate_id = sha256_bytes(assembled)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        offsets = [0]
        if len(assembled) > EXPECTED_SOURCE_BYTES:
            offsets.append(len(assembled) - EXPECTED_SOURCE_BYTES)
        for offset in dict.fromkeys(offsets):
            candidate = assembled[offset:offset + EXPECTED_SOURCE_BYTES]
            if len(candidate) == EXPECTED_SOURCE_BYTES and sha256_bytes(candidate) == EXPECTED_SOURCE_SHA256:
                return candidate, {
                    "method": "ordered_overlap",
                    "order": list(order),
                    "overlaps": used,
                    "assembled_bytes": len(assembled),
                    "window_offset": offset,
                    "part_bytes": [len(value) for value in parts],
                }
        diagnostics.append({"order": list(order), "overlaps": used, "assembled_bytes": length, "sha256": candidate_id})
        if len(diagnostics) >= 8:
            break
    # A bounded full-window scan is retained as a last resort for the shortest
    # candidate only. It accepts bytes solely by the sealed size and SHA-256.
    _, order, assembled, used = candidates[0]
    if len(assembled) >= EXPECTED_SOURCE_BYTES:
        for offset in range(len(assembled) - EXPECTED_SOURCE_BYTES + 1):
            candidate = assembled[offset:offset + EXPECTED_SOURCE_BYTES]
            if sha256_bytes(candidate) == EXPECTED_SOURCE_SHA256:
                return candidate, {
                    "method": "ordered_overlap_bounded_window",
                    "order": list(order),
                    "overlaps": used,
                    "assembled_bytes": len(assembled),
                    "window_offset": offset,
                    "part_bytes": [len(value) for value in parts],
                }
    refuse("no overlap reconstruction reproduced the sealed source coordinate: " + json.dumps(diagnostics, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--receipt", type=pathlib.Path, required=True)
    args = parser.parse_args()

    data_root = args.data_root.resolve()
    manifest_path = data_root / "MANIFEST.json"
    if not manifest_path.is_file():
        refuse("MANIFEST.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != EXPECTED_FORMAT:
        refuse("manifest format mismatch")
    if manifest.get("source_archive") != {
        "name": EXPECTED_SOURCE_NAME,
        "bytes": EXPECTED_SOURCE_BYTES,
        "sha256": EXPECTED_SOURCE_SHA256,
    }:
        refuse("source coordinate mismatch")

    authority = manifest.get("source_authority", {})
    required = {
        "source_matrix_canonical_sha256": EXPECTED_MATRIX_CANONICAL_SHA256,
        "ui_matrix_file_sha256": EXPECTED_UI_MATRIX_FILE_SHA256,
        "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
        "package_manifest_sha256": EXPECTED_PACKAGE_MANIFEST_SHA256,
        "kit_id": EXPECTED_KIT_ID,
        "qualification_id": EXPECTED_QUALIFICATION_ID,
        "blocked_progress_id": EXPECTED_PROGRESS_ID,
        "contracts_per_execution": 49,
    }
    for key, expected in required.items():
        if authority.get(key) != expected:
            refuse(f"authority mismatch at {key}")

    declared = manifest.get("parts")
    if not isinstance(declared, list) or len(declared) != 5:
        refuse("five-part ledger is missing")
    declared_paths = [item.get("path") for item in declared]
    actual_paths = [path.relative_to(data_root).as_posix() for path in sorted((data_root / "parts").glob("part-*.bin"))]
    if declared_paths != actual_paths:
        refuse("declared and actual part sets differ")

    parts: list[bytes] = []
    part_receipts = []
    for item in declared:
        path = data_root / item["path"]
        raw = path.read_bytes()
        observed_blob = git_blob_sha1(raw)
        if observed_blob != item.get("git_blob_sha1"):
            refuse(f"Git blob identity mismatch: {item['path']}")
        parts.append(raw)
        part_receipts.append({"path": item["path"], "bytes": len(raw), "git_blob_sha1": observed_blob, "sha256": sha256_bytes(raw)})

    decoded, reconstruction = reconstruct(parts)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(decoded)

    with tempfile.TemporaryDirectory(prefix="ap410-overlap-verify-") as temp_name:
        temp = pathlib.Path(temp_name)
        try:
            with tarfile.open(output, "r:gz") as archive:
                members = archive.getmembers()
                if not members:
                    refuse("source archive is empty")
                for member in members:
                    posix = pathlib.PurePosixPath(member.name)
                    if posix.is_absolute() or ".." in posix.parts:
                        refuse(f"unsafe archive member: {member.name}")
                roots = {pathlib.PurePosixPath(member.name).parts[0] for member in members if pathlib.PurePosixPath(member.name).parts}
                if len(roots) != 1:
                    refuse("source archive must have one top-level directory")
                archive.extractall(temp, filter="data")
        except tarfile.TarError as exc:
            refuse(f"invalid source archive: {exc}")
        package_root = temp / next(iter(roots))
        required_paths = [
            "SOURCE_MANIFEST.sha256", "PACKAGE_MANIFEST.sha256", "lib/ui-matrix.mjs",
            "qualification/PROGRESS.json", "qualification/RESULT.json", "receipts/KIT.json",
            "scripts/verify-package.mjs", "scripts/compile-progress.mjs",
            "tests/observation.test.mjs", "tests/runtime-binding.test.mjs",
        ]
        for relative in required_paths:
            if not (package_root / relative).is_file():
                refuse(f"required source path missing: {relative}")
        if any(path.name.lower() == "runtime_binding.json" for path in package_root.rglob("*") if path.is_file()):
            refuse("clean source unexpectedly contains RUNTIME_BINDING.json")
        if sha256_path(package_root / "SOURCE_MANIFEST.sha256") != EXPECTED_SOURCE_MANIFEST_SHA256:
            refuse("source manifest digest mismatch")
        if sha256_path(package_root / "PACKAGE_MANIFEST.sha256") != EXPECTED_PACKAGE_MANIFEST_SHA256:
            refuse("package manifest digest mismatch")
        if sha256_path(package_root / "lib/ui-matrix.mjs") != EXPECTED_UI_MATRIX_FILE_SHA256:
            refuse("ui-matrix source-file digest mismatch")
        result = json.loads((package_root / "qualification/RESULT.json").read_text(encoding="utf-8"))
        kit = json.loads((package_root / "receipts/KIT.json").read_text(encoding="utf-8"))
        for label, value in (("qualification result", result), ("kit receipt", kit)):
            if value.get("sourceMatrixSha256") != EXPECTED_MATRIX_CANONICAL_SHA256:
                refuse(f"{label} canonical source-matrix digest mismatch")
        json_text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.rglob("*.json"))
        for identity in (EXPECTED_KIT_ID, EXPECTED_QUALIFICATION_ID, EXPECTED_PROGRESS_ID):
            if identity not in json_text:
                refuse(f"source identity absent: {identity}")
        progress = json.loads((package_root / "qualification/PROGRESS.json").read_text(encoding="utf-8"))
        values = [str(value).lower() for value in scalar_values(progress)]
        if EXPECTED_PROGRESS_ID.lower() not in values or "blocked" not in values or "runtime_binding_missing" not in values:
            refuse("clean blocked state is absent")
        if progress.get("observedInteractions") != 0 or progress.get("observedVisuals") != 0 or progress.get("observedReaderGroups") != 0:
            refuse("clean evidence counts are nonzero")
        if progress.get("canonicalAp410Accepted") is not False or progress.get("canonicalG3Accepted") is not False:
            refuse("canonical gate inflation")
        if progress.get("hostedRepositoryAccepted") is not False:
            refuse("hosted repository inflation")

    receipt = {
        "format": "axm-aperture-g3-observation-kit-v2-overlap-verification/1",
        "manifest_sha256": sha256_path(manifest_path),
        "source_archive": {"name": EXPECTED_SOURCE_NAME, "bytes": len(decoded), "sha256": sha256_bytes(decoded)},
        "parts": part_receipts,
        "reconstruction": reconstruction,
        "internal_authority_verified": True,
        "runtime_binding_present": False,
        "observed_platform_interactions": 0,
        "observed_platform_visuals": 0,
        "manual_reader_groups_passed": 0,
        "canonical_ap410_accepted": False,
        "canonical_g3_accepted": False,
        "hosted_repository_accepted": False,
        "accepted_gates": [],
        "status": "PASS",
    }
    core = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receipt_sha256"] = hashlib.sha256(core).hexdigest()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
