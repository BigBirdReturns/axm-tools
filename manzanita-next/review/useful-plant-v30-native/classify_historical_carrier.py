#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import hashlib
import io
import json
import string
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BASE64_ALPHABET = (
    string.ascii_uppercase + string.ascii_lowercase + string.digits + "+/"
).encode("ascii")
DEFAULT_ASSERTED_SHA256 = (
    "a1c4c12053066c1c579111c9bea16a6acd50e4a0c6cf21120afc944d46e43b46"
)
PART_TEMPLATE = ".github/bootstrap/manzanita-independent-archive-source-part-{part:02d}.b64"


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_text(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout.strip()


def safe_tar_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return bool(pure.parts) and not pure.is_absolute() and ".." not in pure.parts


def evaluate_candidate(
    method: str,
    symbol: str | None,
    normalized: bytes,
) -> tuple[dict, bytes]:
    try:
        decoded = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        return (
            {
                "method": method,
                "terminal_symbol": symbol,
                "normalized_bytes": len(normalized),
                "normalized_sha256": sha256(normalized),
                "decoded": False,
                "decode_error": str(exc),
                "gzip_valid": False,
                "tar_valid": False,
            },
            b"",
        )

    gzip_valid = False
    gzip_error: str | None = None
    uncompressed = b""
    try:
        uncompressed = gzip.decompress(decoded)
    except Exception as exc:
        gzip_error = f"{type(exc).__name__}: {exc}"
    else:
        gzip_valid = True

    tar_valid = False
    tar_error: str | None = None
    tar_members: list[str] = []
    unsafe_members: list[str] = []
    if gzip_valid:
        try:
            with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:gz") as archive:
                tar_members = [member.name for member in archive.getmembers()]
                unsafe_members = [name for name in tar_members if not safe_tar_name(name)]
                tar_valid = not unsafe_members
        except Exception as exc:
            tar_error = f"{type(exc).__name__}: {exc}"

    return (
        {
            "method": method,
            "terminal_symbol": symbol,
            "normalized_bytes": len(normalized),
            "normalized_sha256": sha256(normalized),
            "decoded": True,
            "decoded_bytes": len(decoded),
            "decoded_sha256": sha256(decoded),
            "gzip_valid": gzip_valid,
            "gzip_error": gzip_error,
            "gzip_uncompressed_bytes": len(uncompressed) if gzip_valid else None,
            "gzip_uncompressed_sha256": sha256(uncompressed) if gzip_valid else None,
            "tar_valid": tar_valid,
            "tar_error": tar_error,
            "tar_member_count": len(tar_members),
            "unsafe_tar_members": unsafe_members,
        },
        decoded,
    )


def candidate_specs(encoded: bytes) -> list[tuple[str, str | None, bytes]]:
    remainder = len(encoded) % 4
    if remainder == 1:
        return []
    if remainder == 0:
        return [("carrier_complete", None, encoded)]

    candidates: list[tuple[str, str | None, bytes]] = [
        ("padding_only", None, encoded + (b"=" * (4 - remainder)))
    ]
    if remainder == 3:
        candidates.extend(
            (
                "append_missing_terminal_symbol",
                chr(symbol),
                encoded + bytes([symbol]),
            )
            for symbol in BASE64_ALPHABET
        )
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asserted-sha256", default=DEFAULT_ASSERTED_SHA256)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    transport = args.output_dir / "transport"
    transport.mkdir(exist_ok=True)
    receipt_path = args.output_dir / "HISTORICAL_CARRIER_CLASSIFICATION_RECEIPT.json"
    recovered_archive = args.output_dir / "manzanita-independent-archive-source.tar.gz"

    observed_tree = git_text("show", "-s", "--format=%T", args.commit)
    if observed_tree != args.tree:
        raise SystemExit(
            f"historical tree mismatch: observed={observed_tree} expected={args.tree}"
        )

    part_receipts: list[dict[str, object]] = []
    raw_parts: list[bytes] = []
    for part in range(1, 10):
        repo_path = PART_TEMPLATE.format(part=part)
        payload = subprocess.run(
            ["git", "show", f"{args.commit}:{repo_path}"],
            check=True,
            capture_output=True,
        ).stdout
        target = transport / Path(repo_path).name
        target.write_bytes(payload)
        raw_parts.append(payload)
        part_receipts.append(
            {
                "part": part,
                "historical_path": repo_path,
                "git_blob_sha1": git_text("rev-parse", f"{args.commit}:{repo_path}"),
                "bytes": len(payload),
                "sha256": sha256(payload),
            }
        )

    raw = b"".join(raw_parts)
    combined = transport / "manzanita-independent-archive-source.b64"
    combined.write_bytes(raw)
    encoded = b"".join(raw.split())
    allowed = set(BASE64_ALPHABET + b"=")
    invalid_octets = sorted(set(encoded) - allowed)
    if invalid_octets:
        raise SystemExit(f"invalid non-whitespace base64 octets: {invalid_octets}")

    evaluations: list[dict] = []
    payloads: list[bytes] = []
    for method, symbol, normalized in candidate_specs(encoded):
        evaluation, decoded = evaluate_candidate(method, symbol, normalized)
        evaluations.append(evaluation)
        payloads.append(decoded)

    exact_indices = [
        index
        for index, row in enumerate(evaluations)
        if row.get("tar_valid") and row.get("decoded_sha256") == args.asserted_sha256
    ]
    valid_indices = [
        index for index, row in enumerate(evaluations) if row.get("tar_valid")
    ]

    selected: dict | None = None
    if len(exact_indices) == 1:
        index = exact_indices[0]
        selected = evaluations[index]
        recovered_archive.write_bytes(payloads[index])
        result = "PASS_ASSERTED_SOURCE_RECOVERED"
        admission_state = "QUALIFIED"
        exact_source_archive_admitted = True
        blocking_holds: list[str] = []
    elif len(exact_indices) > 1:
        raise SystemExit("ambiguous exact historical carrier recovery")
    elif len(valid_indices) == 1:
        index = valid_indices[0]
        selected = evaluations[index]
        recovered_archive.write_bytes(payloads[index])
        result = "HOLD_VALID_CARRIER_ASSERTION_DRIFT"
        admission_state = "HOLD"
        exact_source_archive_admitted = False
        blocking_holds = [
            "one valid archive carrier was recovered but its SHA-256 differs from the asserted source archive",
            "no byte-identical source archive at the asserted SHA-256 is mounted",
        ]
    else:
        result = "HOLD_HISTORICAL_CARRIER_UNRESOLVED"
        admission_state = "HOLD"
        exact_source_archive_admitted = False
        blocking_holds = [
            "the nine historical Git transport parts do not resolve to a valid gzip tar archive under bounded terminal recovery",
            "no byte-identical source archive at the asserted SHA-256 is mounted",
        ]

    receipt = {
        "schema": "manzanita/useful-plant-v30-historical-carrier-classification@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "admission_state": admission_state,
        "exact_source_archive_admitted": exact_source_archive_admitted,
        "blocking_holds": blocking_holds,
        "source_commit": args.commit,
        "source_tree": args.tree,
        "asserted_source_sha256": args.asserted_sha256,
        "transport_parts": part_receipts,
        "combined_transport": {
            "path": str(combined.relative_to(args.output_dir)),
            "raw_bytes": len(raw),
            "raw_sha256": sha256(raw),
            "whitespace_stripped_bytes": len(encoded),
            "whitespace_stripped_sha256": sha256(encoded),
            "base64_remainder": len(encoded) % 4,
        },
        "candidate_count_tested": len(evaluations),
        "valid_archive_candidate_count": len(valid_indices),
        "exact_archive_candidate_count": len(exact_indices),
        "selected": selected,
        "evaluated": evaluations,
        "recovered_archive": (
            {
                "path": recovered_archive.name,
                "bytes": recovered_archive.stat().st_size,
                "sha256": sha256(recovered_archive.read_bytes()),
            }
            if recovered_archive.exists()
            else None
        ),
        "normalization_rule": "concatenate parts 01 through 09 in historical path order, strip ASCII whitespace, reject all other non-base64 octets, test required RFC 4648 padding and each possible single missing terminal symbol, require a safe gzip tar archive, and admit only the asserted SHA-256",
        "operator_visual_acceptance": "ABSENT",
        "merge_authorized": False,
        "release_authorized": False,
        "public_route_effect": "none",
        "pages_deployment_effect": "none",
        "external_effect": "none",
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "result": result,
                "admission_state": admission_state,
                "candidate_count_tested": len(evaluations),
                "valid_archive_candidate_count": len(valid_indices),
                "exact_archive_candidate_count": len(exact_indices),
                "combined_transport_bytes": len(raw),
                "base64_remainder": len(encoded) % 4,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
