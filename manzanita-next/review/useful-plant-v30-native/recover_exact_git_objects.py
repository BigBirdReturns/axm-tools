#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_PARENT_CONTRACT = HERE / "V29_PARENT_ADMISSION_CONTRACT.json"
DEFAULT_PLANT_CONTRACT = HERE / "PLANT_DONOR_ADMISSION_CONTRACT.json"

TEXT_SUFFIXES = {
    ".b64",
    ".css",
    ".csv",
    ".htm",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".svg",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
DATA_URL_RE = re.compile(
    rb"data:(?P<media>[-+.A-Za-z0-9]+/[-+.A-Za-z0-9]+)"
    rb"(?P<params>(?:;[-+.A-Za-z0-9]+(?:=[-+.A-Za-z0-9]+)?)*)"
    rb";base64,(?P<data>[A-Za-z0-9+/=\r\n]+)"
)


@dataclass(frozen=True)
class Target:
    target_id: str
    filename: str
    bytes: int
    sha256: str
    media_type: str | None = None


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    return (
        bool(normalized)
        and "\\" not in name
        and not pure.is_absolute()
        and ".." not in pure.parts
        and not (pure.parts and ":" in pure.parts[0])
    )


def run_text(repo: Path, *args: str, input_text: str | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def load_targets(parent_contract: Path, plant_contract: Path) -> dict[str, Target]:
    parent = json.loads(parent_contract.read_text(encoding="utf-8"))
    plant = json.loads(plant_contract.read_text(encoding="utf-8"))
    required_archive = parent["required_archive"]
    required_donors = plant["required_donors"]
    targets = {
        "v29_archive": Target(
            target_id="v29_archive",
            filename=required_archive["filename"],
            bytes=int(required_archive["bytes"]),
            sha256=required_archive["sha256"],
            media_type="application/zip",
        ),
        "plant_origin": Target(
            target_id="plant_origin",
            filename=required_donors["origin"]["filename"],
            bytes=int(required_donors["origin"]["bytes"]),
            sha256=required_donors["origin"]["sha256"],
            media_type=required_donors["origin"].get("media_type"),
        ),
        "plant_cached": Target(
            target_id="plant_cached",
            filename=required_donors["cached"]["filename"],
            bytes=int(required_donors["cached"]["bytes"]),
            sha256=required_donors["cached"]["sha256"],
            media_type=required_donors["cached"].get("media_type"),
        ),
    }
    for target in targets.values():
        if not re.fullmatch(r"[0-9a-f]{64}", target.sha256):
            raise ValueError(f"invalid SHA-256 for {target.target_id}: {target.sha256}")
        if target.bytes < 1 or Path(target.filename).name != target.filename:
            raise ValueError(f"invalid target identity for {target.target_id}")
    return targets


class BatchObjectReader:
    def __init__(self, repo: Path) -> None:
        self.proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("unable to start git cat-file --batch")

    def read(self, oid: str) -> tuple[str, int, bytes]:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(oid.encode("ascii") + b"\n")
        self.proc.stdin.flush()
        header = self.proc.stdout.readline()
        if not header:
            stderr = (
                self.proc.stderr.read().decode("utf-8", errors="replace")
                if self.proc.stderr
                else ""
            )
            raise RuntimeError(f"git cat-file ended while reading {oid}: {stderr}")
        fields = header.decode("ascii", errors="replace").strip().split()
        if len(fields) == 2 and fields[1] == "missing":
            raise KeyError(f"missing Git object {oid}")
        if len(fields) != 3:
            raise RuntimeError(f"unexpected git cat-file header for {oid}: {header!r}")
        observed_oid, object_type, size_text = fields
        size = int(size_text)
        payload = self.proc.stdout.read(size)
        terminator = self.proc.stdout.read(1)
        if len(payload) != size or terminator != b"\n":
            raise RuntimeError(f"truncated git cat-file payload for {oid}")
        if observed_oid != oid:
            raise RuntimeError(f"git cat-file object mismatch: {observed_oid} != {oid}")
        return object_type, size, payload

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=10)

    def __enter__(self) -> "BatchObjectReader":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class RecoveryScanner:
    def __init__(
        self,
        targets: dict[str, Target],
        output_dir: Path,
        *,
        max_blob_bytes: int,
        max_zip_entry_bytes: int,
        max_zip_total_bytes: int,
        max_zip_depth: int,
    ) -> None:
        self.targets = targets
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.by_size: dict[int, list[Target]] = {}
        for target in targets.values():
            self.by_size.setdefault(target.bytes, []).append(target)
        self.max_blob_bytes = max_blob_bytes
        self.max_zip_entry_bytes = max_zip_entry_bytes
        self.max_zip_total_bytes = max_zip_total_bytes
        self.max_zip_depth = max_zip_depth
        self.matches: dict[str, list[dict[str, Any]]] = {
            target_id: [] for target_id in targets
        }
        self.size_collisions: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.seen_coordinates: set[str] = set()
        self.counts: dict[str, int] = {
            "git_objects_total": 0,
            "git_blobs_total": 0,
            "git_blobs_read": 0,
            "git_blob_bytes_read": 0,
            "data_urls_seen": 0,
            "data_urls_decoded": 0,
            "zip_carriers_seen": 0,
            "zip_members_seen": 0,
            "zip_member_bytes_read": 0,
        }

    def _coordinate_key(self, source: dict[str, Any]) -> str:
        return json.dumps(source, sort_keys=True, separators=(",", ":"))

    def consider(self, payload: bytes, source: dict[str, Any]) -> None:
        digest = sha256_bytes(payload)
        candidates = self.by_size.get(len(payload), [])
        if not candidates:
            return
        matched = False
        for target in candidates:
            if digest != target.sha256:
                continue
            matched = True
            destination = self.output_dir / target.filename
            if destination.exists() and destination.read_bytes() != payload:
                raise RuntimeError(
                    f"recovered target collision at {destination}: bytes differ"
                )
            destination.write_bytes(payload)
            coordinate_key = self._coordinate_key(source)
            row = {
                "target_id": target.target_id,
                "filename": target.filename,
                "bytes": len(payload),
                "sha256": digest,
                "recovered_path": str(destination),
                "source": source,
            }
            unique_key = f"{target.target_id}:{coordinate_key}"
            if unique_key not in self.seen_coordinates:
                self.matches[target.target_id].append(row)
                self.seen_coordinates.add(unique_key)
        if not matched and len(self.size_collisions) < 200:
            self.size_collisions.append(
                {
                    "bytes": len(payload),
                    "sha256": digest,
                    "candidate_target_ids": [target.target_id for target in candidates],
                    "source": source,
                }
            )

    def scan_data_urls(self, payload: bytes, source: dict[str, Any]) -> None:
        for ordinal, match in enumerate(DATA_URL_RE.finditer(payload)):
            self.counts["data_urls_seen"] += 1
            encoded = b"".join(match.group("data").split())
            if len(encoded) > ((self.max_blob_bytes + 2) // 3) * 4 + 8:
                continue
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                if len(self.errors) < 200:
                    self.errors.append(
                        {
                            "kind": "data_url_decode",
                            "error": str(exc),
                            "source": source,
                            "ordinal": ordinal,
                        }
                    )
                continue
            self.counts["data_urls_decoded"] += 1
            embedded_source = {
                **source,
                "carrier_kind": "embedded_data_url",
                "data_url_ordinal": ordinal,
                "media_type": match.group("media").decode(
                    "ascii", errors="replace"
                ),
                "encoded_bytes": len(encoded),
            }
            self.consider(decoded, embedded_source)
            if decoded.startswith(b"PK\x03\x04"):
                self.scan_zip(decoded, embedded_source, depth=1)

    def scan_zip(self, payload: bytes, source: dict[str, Any], depth: int = 0) -> None:
        if depth > self.max_zip_depth:
            return
        self.counts["zip_carriers_seen"] += 1
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as exc:
            if len(self.errors) < 200:
                self.errors.append(
                    {"kind": "bad_zip", "error": str(exc), "source": source}
                )
            return
        with archive:
            infos = archive.infolist()
            total_uncompressed = sum(
                info.file_size for info in infos if not info.is_dir()
            )
            if total_uncompressed > self.max_zip_total_bytes:
                if len(self.errors) < 200:
                    self.errors.append(
                        {
                            "kind": "zip_total_limit",
                            "observed": total_uncompressed,
                            "limit": self.max_zip_total_bytes,
                            "source": source,
                        }
                    )
                return
            for info in infos:
                if info.is_dir():
                    continue
                self.counts["zip_members_seen"] += 1
                member_source = {
                    **source,
                    "carrier_kind": "zip_member",
                    "zip_depth": depth,
                    "zip_member": info.filename,
                    "zip_member_bytes": info.file_size,
                    "zip_member_compressed_bytes": info.compress_size,
                }
                if not safe_member_name(info.filename):
                    if len(self.errors) < 200:
                        self.errors.append(
                            {"kind": "unsafe_zip_member", "source": member_source}
                        )
                    continue
                suffix = Path(info.filename).suffix.lower()
                needs_read = (
                    info.file_size in self.by_size
                    or suffix in TEXT_SUFFIXES
                    or suffix == ".zip"
                )
                if not needs_read or info.file_size > self.max_zip_entry_bytes:
                    continue
                try:
                    member = archive.read(info)
                except Exception as exc:
                    if len(self.errors) < 200:
                        self.errors.append(
                            {
                                "kind": "zip_member_read",
                                "error": f"{type(exc).__name__}: {exc}",
                                "source": member_source,
                            }
                        )
                    continue
                self.counts["zip_member_bytes_read"] += len(member)
                self.consider(member, member_source)
                if suffix in TEXT_SUFFIXES or b"data:" in member:
                    self.scan_data_urls(member, member_source)
                if member.startswith(b"PK\x03\x04"):
                    self.scan_zip(member, member_source, depth=depth + 1)

    def scan_blob(self, oid: str, paths: list[str], payload: bytes) -> None:
        source = {
            "source_type": "git_blob",
            "git_blob_sha1": oid,
            "reachable_paths": paths,
            "blob_bytes": len(payload),
        }
        self.consider(payload, source)
        suffixes = {Path(path).suffix.lower() for path in paths}
        if b"data:" in payload or bool(suffixes & TEXT_SUFFIXES):
            self.scan_data_urls(payload, source)
        if payload.startswith(b"PK\x03\x04") or ".zip" in suffixes:
            self.scan_zip(payload, source)


def parse_reachable_paths(repo: Path) -> dict[str, list[str]]:
    output = run_text(repo, "rev-list", "--objects", "--all")
    paths: dict[str, list[str]] = {}
    for line in output.splitlines():
        if not line:
            continue
        oid, separator, path = line.partition(" ")
        paths.setdefault(oid, [])
        if separator and path and path not in paths[oid]:
            paths[oid].append(path)
    return paths


def object_inventory(
    repo: Path, reachable: dict[str, list[str]]
) -> list[tuple[str, str, int]]:
    proc = subprocess.run(
        [
            "git",
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        lines = proc.stdout.splitlines()
    else:
        oids = sorted(reachable)
        lines = run_text(
            repo,
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
            input_text="\n".join(oids) + "\n",
        ).splitlines()
    inventory: list[tuple[str, str, int]] = []
    for line in lines:
        fields = line.split()
        if len(fields) != 3:
            continue
        oid, object_type, size_text = fields
        try:
            size = int(size_text)
        except ValueError:
            continue
        inventory.append((oid, object_type, size))
    return inventory


def build_receipt(
    scanner: RecoveryScanner,
    targets: dict[str, Target],
    repo: Path,
    inventory: list[tuple[str, str, int]],
    reachable: dict[str, list[str]],
) -> dict[str, Any]:
    target_rows: dict[str, Any] = {}
    for target_id, target in targets.items():
        recovered_path = scanner.output_dir / target.filename
        target_rows[target_id] = {
            "filename": target.filename,
            "expected_bytes": target.bytes,
            "expected_sha256": target.sha256,
            "media_type": target.media_type,
            "recovered": recovered_path.is_file(),
            "recovered_path": (
                str(recovered_path) if recovered_path.is_file() else None
            ),
            "matches": scanner.matches[target_id],
        }
    recovered = {key: row["recovered"] for key, row in target_rows.items()}
    return {
        "schema": "manzanita/useful-plant-v30-exact-git-object-recovery@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS_EXACT_GIT_OBJECT_SCAN_COMPLETE",
        "repository": str(repo),
        "head": run_text(repo, "rev-parse", "HEAD").strip(),
        "refs_scanned": len(
            run_text(repo, "for-each-ref", "--format=%(refname)").splitlines()
        ),
        "reachable_object_count": len(reachable),
        "local_object_count": len(inventory),
        "targets": target_rows,
        "recovered": recovered,
        "plant_pair_recovered": (
            recovered["plant_origin"] and recovered["plant_cached"]
        ),
        "v29_archive_recovered": recovered["v29_archive"],
        "counts": scanner.counts,
        "size_collisions": scanner.size_collisions,
        "errors": scanner.errors,
        "scope": {
            "reachable_refs": "all local refs, including fetched remote branches and tags",
            "local_objects": "all objects available to git cat-file --batch-all-objects",
            "embedded_carriers": "strict base64 data URLs and bounded ZIP members",
            "network": "none",
        },
        "operator_visual_acceptance": "ABSENT",
        "merge_authorized": False,
        "release_authorized": False,
        "public_route_effect": "none",
        "pages_deployment_effect": "none",
        "external_effect": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover exact v29 and Useful Plant objects from all local Git objects."
        )
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--parent-contract", type=Path, default=DEFAULT_PARENT_CONTRACT
    )
    parser.add_argument(
        "--plant-contract", type=Path, default=DEFAULT_PLANT_CONTRACT
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--max-blob-bytes", type=int, default=134_217_728)
    parser.add_argument("--max-zip-entry-bytes", type=int, default=134_217_728)
    parser.add_argument("--max-zip-total-bytes", type=int, default=1_073_741_824)
    parser.add_argument("--max-zip-depth", type=int, default=2)
    args = parser.parse_args()

    repo = args.repo.resolve()
    output_dir = args.output_dir.resolve()
    receipt_path = (
        args.receipt or output_dir / "EXACT_GIT_OBJECT_RECOVERY_RECEIPT.json"
    )
    targets = load_targets(args.parent_contract, args.plant_contract)
    reachable = parse_reachable_paths(repo)
    inventory = object_inventory(repo, reachable)
    scanner = RecoveryScanner(
        targets,
        output_dir,
        max_blob_bytes=args.max_blob_bytes,
        max_zip_entry_bytes=args.max_zip_entry_bytes,
        max_zip_total_bytes=args.max_zip_total_bytes,
        max_zip_depth=args.max_zip_depth,
    )
    scanner.counts["git_objects_total"] = len(inventory)

    with BatchObjectReader(repo) as reader:
        for oid, object_type, size in inventory:
            if object_type != "blob":
                continue
            scanner.counts["git_blobs_total"] += 1
            paths = reachable.get(oid, [])
            target_sized = size in scanner.by_size
            path_interesting = any(
                Path(path).suffix.lower() in TEXT_SUFFIXES | {".zip"}
                for path in paths
            )
            unnamed_local = not paths
            should_read = (
                target_sized
                or path_interesting
                or unnamed_local
                or size <= 2_000_000
            )
            if not should_read or size > args.max_blob_bytes:
                continue
            try:
                observed_type, observed_size, payload = reader.read(oid)
            except Exception as exc:
                if len(scanner.errors) < 200:
                    scanner.errors.append(
                        {
                            "kind": "git_blob_read",
                            "git_blob_sha1": oid,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                continue
            if observed_type != "blob" or observed_size != size:
                raise RuntimeError(f"Git object metadata drift for {oid}")
            scanner.counts["git_blobs_read"] += 1
            scanner.counts["git_blob_bytes_read"] += len(payload)
            scanner.scan_blob(oid, paths, payload)

    receipt = build_receipt(scanner, targets, repo, inventory, reachable)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "head": receipt["head"],
                "recovered": receipt["recovered"],
                "plant_pair_recovered": receipt["plant_pair_recovered"],
                "v29_archive_recovered": receipt["v29_archive_recovered"],
                "counts": receipt["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
