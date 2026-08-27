#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

EXPECTED_MEMBERS = {
    ".github/workflows/manzanita-independent-archive.yml",
    ".github/workflows/manzanita-release-control.yml",
    "manzanita-next/release-control/README.md",
    "manzanita-next/release-control/RELEASE_CONTRACT.json",
    "manzanita-next/release-control/EXTERNAL_CAMPAIGN_LEDGER.json",
    "manzanita-next/release-control/tests/test_release_control.py",
    "manzanita-next/release-control/review/M99-RB-PKT-012.json",
    "manzanita-next/release-control/review/M99-RB-DEC-012.json",
    "manzanita-next/release-control/archive-campaign/README.md",
    "manzanita-next/release-control/archive-campaign/M99-PHYS-ARCHIVE-001-RECEIPT.json",
    "manzanita-next/release-control/archive-campaign/verify_archive_campaign.py",
    "manzanita-next/release-control/archive-campaign/tests/test_archive_campaign.py",
}
RECEIPT_MEMBER = (
    "manzanita-next/release-control/archive-campaign/"
    "M99-PHYS-ARCHIVE-001-RECEIPT.json"
)
WORKFLOW_MEMBER = ".github/workflows/manzanita-independent-archive.yml"


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def digest_bytes(path: str, payload: bytes) -> dict:
    return {"path": path, "bytes": len(payload), "sha256": sha256(payload)}


def safe_member_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return bool(pure.parts) and not pure.is_absolute() and ".." not in pure.parts


def regular_payload(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes | None:
    if not member.isfile():
        return None
    stream = archive.extractfile(member)
    return stream.read() if stream else b""


def resolve_link_payload(
    archive: tarfile.TarFile,
    by_name: dict[str, tarfile.TarInfo],
    member: tarfile.TarInfo,
) -> tuple[bytes | None, str | None]:
    if member.isfile():
        return regular_payload(archive, member), member.name
    if not (member.issym() or member.islnk()):
        return None, None

    parent = PurePosixPath(member.name).parent
    candidates = [
        PurePosixPath(member.linkname).as_posix(),
        (parent / member.linkname).as_posix(),
    ]
    for candidate in candidates:
        target = by_name.get(candidate)
        if target and target.isfile():
            return regular_payload(archive, target), candidate
    return None, None


def find_campaign_receipt(
    archive: tarfile.TarFile,
    by_name: dict[str, tarfile.TarInfo],
    payloads: dict[str, bytes],
) -> tuple[dict | None, dict]:
    member = by_name[RECEIPT_MEMBER]
    payload, resolved_from = resolve_link_payload(archive, by_name, member)
    provenance = {
        "member": RECEIPT_MEMBER,
        "member_type": member.type.decode("ascii", errors="replace")
        if isinstance(member.type, bytes)
        else str(member.type),
        "linkname": member.linkname or None,
        "resolved_from": resolved_from,
        "materialized": False,
    }

    if payload is not None:
        try:
            receipt = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            receipt = None
        else:
            provenance["materialized"] = True
            provenance["bytes"] = len(payload)
            provenance["sha256"] = sha256(payload)
            return receipt, provenance

    candidates: list[tuple[str, dict, bytes]] = []
    for name, candidate_payload in payloads.items():
        if not name.endswith(".json"):
            continue
        try:
            candidate = json.loads(candidate_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        marker = json.dumps(candidate, sort_keys=True)
        if "M99-PHYS-ARCHIVE-001" in marker:
            candidates.append((name, candidate, candidate_payload))

    if len(candidates) == 1:
        name, receipt, candidate_payload = candidates[0]
        provenance.update(
            {
                "materialized": True,
                "resolved_from": name,
                "bytes": len(candidate_payload),
                "sha256": sha256(candidate_payload),
                "resolution_method": "unique_campaign_marker_scan",
            }
        )
        return receipt, provenance

    provenance["candidate_matches"] = [name for name, _, _ in candidates]
    provenance["resolution_method"] = "unresolved_link_preserved"
    return None, provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--transport-dir", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--extracted-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.extracted_dir.mkdir(parents=True, exist_ok=True)
    observed_tree = subprocess.run(
        ["git", "show", "-s", "--format=%T", args.commit],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if observed_tree != args.tree:
        raise SystemExit(
            f"historical tree mismatch: observed={observed_tree} expected={args.tree}"
        )

    transport_parts = []
    for part in range(1, 10):
        path = args.transport_dir / f"manzanita-independent-archive-source-part-{part:02d}.b64"
        repo_path = f".github/bootstrap/{path.name}"
        blob = subprocess.run(
            ["git", "rev-parse", f"{args.commit}:{repo_path}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        payload = path.read_bytes()
        entry = digest_bytes(path.relative_to(args.output.parent).as_posix(), payload)
        entry["historical_path"] = repo_path
        entry["git_blob_sha1"] = blob
        transport_parts.append(entry)

    source_payload = args.source_archive.read_bytes()
    source_digest = digest_bytes(
        args.source_archive.relative_to(args.output.parent).as_posix(), source_payload
    )
    expected_source_sha = (
        "a1c4c12053066c1c579111c9bea16a6acd50e4a0c6cf21120afc944d46e43b46"
    )
    if source_digest["sha256"] != expected_source_sha:
        raise SystemExit(
            f"historical source archive mismatch: {source_digest['sha256']}"
        )

    with tarfile.open(args.source_archive, mode="r:gz") as archive:
        all_members = archive.getmembers()
        unsafe_names = sorted(
            member.name for member in all_members if not safe_member_name(member.name)
        )
        unsupported = [
            member.name
            for member in all_members
            if not (
                member.isdir()
                or member.isfile()
                or member.issym()
                or member.islnk()
            )
        ]
        payload_members = [
            member
            for member in all_members
            if member.isfile() or member.issym() or member.islnk()
        ]
        names = [member.name for member in payload_members]
        counts = Counter(names)
        duplicate_names = sorted(name for name, count in counts.items() if count > 1)
        observed_members = set(names)
        if (
            duplicate_names
            or unsafe_names
            or unsupported
            or observed_members != EXPECTED_MEMBERS
        ):
            raise SystemExit(
                "historical source member mismatch: "
                f"duplicates={duplicate_names} unsafe={unsafe_names} "
                f"unsupported={unsupported} "
                f"missing={sorted(EXPECTED_MEMBERS - observed_members)} "
                f"extra={sorted(observed_members - EXPECTED_MEMBERS)}"
            )

        directory_entries = [
            {
                "path": member.name,
                "mode": oct(member.mode),
            }
            for member in all_members
            if member.isdir()
        ]
        by_name = {member.name: member for member in payload_members}
        payloads: dict[str, bytes] = {}
        member_receipts: list[dict] = []
        link_receipts: list[dict] = []

        for member in payload_members:
            entry = {
                "path": member.name,
                "type": member.type.decode("ascii", errors="replace")
                if isinstance(member.type, bytes)
                else str(member.type),
                "mode": oct(member.mode),
                "linkname": member.linkname or None,
            }
            payload = regular_payload(archive, member)
            if payload is not None:
                payloads[member.name] = payload
                target = args.extracted_dir / Path(*PurePosixPath(member.name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                entry.update({"bytes": len(payload), "sha256": sha256(payload)})
                member_receipts.append(entry)
            elif member.issym() or member.islnk():
                link_receipts.append(entry)
                member_receipts.append(entry)
            else:
                raise SystemExit(
                    f"unsupported historical member type: {member.name} {entry['type']}"
                )

        workflow_payload = payloads.get(WORKFLOW_MEMBER)
        if workflow_payload is None:
            workflow_member = by_name[WORKFLOW_MEMBER]
            workflow_payload, _ = resolve_link_payload(archive, by_name, workflow_member)
        workflow_text = workflow_payload.decode("utf-8") if workflow_payload else ""
        discovery_terms = [
            line.strip()
            for line in workflow_text.splitlines()
            if any(
                term in line.casefold()
                for term in (
                    "drive",
                    "selector",
                    "folder",
                    "archive",
                    "file_id",
                    "provider",
                    "gdrive",
                    "rclone",
                    "google",
                )
            )
        ]

        campaign_receipt, campaign_receipt_provenance = find_campaign_receipt(
            archive, by_name, payloads
        )

    combined_b64 = args.transport_dir / "manzanita-independent-archive-source.b64"
    result = {
        "schema": "manzanita/useful-plant-v30-historical-archive-source-recovery@3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS_HISTORICAL_ARCHIVE_SOURCE_RECOVERED",
        "source_commit": args.commit,
        "source_tree": args.tree,
        "transport_parts": transport_parts,
        "combined_base64": digest_bytes(
            combined_b64.relative_to(args.output.parent).as_posix(),
            combined_b64.read_bytes(),
        ),
        "source_archive": source_digest,
        "source_archive_expected_sha256": expected_source_sha,
        "tar_member_count": len(all_members),
        "directory_count": len(directory_entries),
        "directories": directory_entries,
        "member_count": len(member_receipts),
        "members": member_receipts,
        "links": link_receipts,
        "campaign_receipt": campaign_receipt,
        "campaign_receipt_provenance": campaign_receipt_provenance,
        "workflow_discovery_lines": discovery_terms,
        "operator_visual_acceptance": "ABSENT",
        "merge_authorized": False,
        "release_authorized": False,
        "public_route_effect": "none",
        "pages_deployment_effect": "none",
        "external_effect": "none",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "result": result["result"],
                "source_commit": args.commit,
                "tar_member_count": result["tar_member_count"],
                "directory_count": result["directory_count"],
                "member_count": result["member_count"],
                "link_count": len(link_receipts),
                "campaign_receipt_materialized": campaign_receipt_provenance[
                    "materialized"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
