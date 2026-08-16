#!/usr/bin/env python3
"""Forensically recover the Manzanita 497-task register without inventing records.

The program was merged with an invalid gzip/Base64 source and only two of five
later BZ2/Base64 repair chunks. This audit preserves every recoverable byte,
extracts complete task objects from truncated JSON prefixes, inventories all
historical source objects, and separates exact recovery from reconstruction.
"""

from __future__ import annotations

import argparse
import base64
import bz2
import hashlib
import json
import re
import subprocess
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
PROGRAM = REPO_ROOT / "programs" / "manzanita-99"
DEFAULT_OUT = REPO_ROOT / "recovery-out"

GZIP_SOURCE = PROGRAM / "MASTER_BACKLOG.json.gz.b64"
BZ2_PARTS = [
    PROGRAM / "MASTER_BACKLOG.json.bz2.b64.part01",
    PROGRAM / "MASTER_BACKLOG.json.bz2.b64.part02",
]
EXPECTED_BZ2_PARTS = 5
TASK_ID_RE = re.compile(r"\b(?:JDB99|CORE|UX|SG|ST|PL|HH|PR|NB|RG|OV|ROLE|SW|INF|CNT|QA|LEG|AXM-RES)-[A-Z0-9-]+\b")
JDB_RE = re.compile(r"\bJDB99-\d{3}\b")


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stderr}"
        )
    return result.stdout


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def file_receipt(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": sha256(payload),
        "starts_hex": payload[:24].hex(),
        "ends_hex": payload[-24:].hex(),
    }


def decode_base64_variants(encoded: str) -> list[dict[str, Any]]:
    clean = "".join(encoded.split())
    rows: list[dict[str, Any]] = []
    for drop in range(4):
        candidate = clean[drop:]
        padded = candidate + ("=" * ((-len(candidate)) % 4))
        row: dict[str, Any] = {
            "drop_leading_chars": drop,
            "encoded_chars": len(candidate),
            "padding_added": len(padded) - len(candidate),
        }
        try:
            raw = base64.b64decode(padded, validate=True)
            row.update(
                {
                    "status": "decoded",
                    "bytes": len(raw),
                    "sha256": sha256(raw),
                    "starts_hex": raw[:16].hex(),
                    "ends_hex": raw[-16:].hex(),
                }
            )
        except Exception as exc:  # noqa: BLE001
            row.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        rows.append(row)
    return rows


def partial_bz2_recovery(out_dir: Path) -> dict[str, Any]:
    present = [path for path in BZ2_PARTS if path.exists()]
    encoded = "".join(path.read_text(encoding="utf-8").strip() for path in present)
    report: dict[str, Any] = {
        "expected_parts": EXPECTED_BZ2_PARTS,
        "present_parts": [path.name for path in present],
        "missing_parts": [
            f"MASTER_BACKLOG.json.bz2.b64.part{index:02d}"
            for index in range(1, EXPECTED_BZ2_PARTS + 1)
            if not (PROGRAM / f"MASTER_BACKLOG.json.bz2.b64.part{index:02d}").exists()
        ],
        "encoded_chars": len(encoded),
        "encoded_sha256": sha256(encoded.encode("ascii")),
        "decode_variants": decode_base64_variants(encoded),
    }
    if not encoded:
        report["status"] = "missing"
        return report

    padded = encoded + ("=" * ((-len(encoded)) % 4))
    try:
        compressed = base64.b64decode(padded, validate=True)
    except Exception as exc:  # noqa: BLE001
        report["status"] = "base64_error"
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report

    (out_dir / "bz2-partial-compressed.bin").write_bytes(compressed)
    report["compressed_bytes"] = len(compressed)
    report["compressed_sha256"] = sha256(compressed)
    report["compressed_prefix_hex"] = compressed[:16].hex()
    report["is_bz2_header"] = compressed.startswith(b"BZh")

    decompressor = bz2.BZ2Decompressor()
    try:
        recovered = decompressor.decompress(compressed)
        error = None
    except Exception as exc:  # noqa: BLE001
        recovered = b""
        error = f"{type(exc).__name__}: {exc}"

    (out_dir / "bz2-recovered-prefix.bin").write_bytes(recovered)
    try:
        text = recovered.decode("utf-8")
        utf8_error = None
    except UnicodeDecodeError as exc:
        text = recovered.decode("utf-8", errors="replace")
        utf8_error = str(exc)
    (out_dir / "bz2-recovered-prefix.txt").write_text(text, encoding="utf-8")

    tasks = recover_complete_task_objects(text)
    write_json(out_dir / "bz2-recovered-complete-tasks.json", {"tasks": tasks})
    report.update(
        {
            "status": "partial" if not decompressor.eof else "complete",
            "decompress_error": error,
            "decompressor_eof": decompressor.eof,
            "unused_data_bytes": len(decompressor.unused_data),
            "recovered_bytes": len(recovered),
            "recovered_sha256": sha256(recovered),
            "utf8_error": utf8_error,
            "complete_task_objects": len(tasks),
            "task_id_first": tasks[0].get("id") if tasks else None,
            "task_id_last": tasks[-1].get("id") if tasks else None,
            "task_id_families": dict(
                sorted(Counter(str(task.get("id", "")).split("-")[0] for task in tasks).items())
            ),
            "jdb_ids": [task.get("id") for task in tasks if JDB_RE.fullmatch(str(task.get("id", "")))],
        }
    )
    return report


def recover_complete_task_objects(text: str) -> list[dict[str, Any]]:
    """Extract complete JSON objects from a possibly truncated top-level tasks array."""
    match = re.search(r'"tasks"\s*:\s*\[', text)
    if not match:
        return []
    i = match.end()
    rows: list[dict[str, Any]] = []
    length = len(text)

    while i < length:
        while i < length and text[i] in " \r\n\t,":
            i += 1
        if i >= length or text[i] == "]":
            break
        if text[i] != "{":
            i += 1
            continue

        start = i
        depth = 0
        in_string = False
        escape = False
        while i < length:
            char = text[i]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1]
                        try:
                            value = json.loads(candidate)
                        except json.JSONDecodeError:
                            return rows
                        if isinstance(value, dict):
                            rows.append(value)
                        i += 1
                        break
            i += 1
        else:
            break
    return rows


def shift_lsb_stream(data: bytes, byte_offset: int, bit_offset: int) -> bytes:
    source = data[byte_offset:]
    if bit_offset == 0:
        return source
    if len(source) < 2:
        return b""
    shift = bit_offset
    return bytes(
        ((source[index] >> shift) | ((source[index + 1] << (8 - shift)) & 0xFF))
        for index in range(len(source) - 1)
    )


def score_salvage(payload: bytes) -> int:
    if not payload:
        return 0
    sample = payload[:2_000_000]
    score = min(len(sample), 200_000)
    for marker, weight in (
        (b'"id"', 5000),
        (b'"title"', 5000),
        (b'"priority"', 5000),
        (b'"phase"', 4000),
        (b'"acceptance"', 6000),
        (b"JDB99-", 10000),
        (b"CORE-", 8000),
        (b"AXM-RES-", 8000),
        (b'"tasks"', 10000),
    ):
        score += sample.count(marker) * weight
    printable = sum(byte in b"\t\n\r" or 32 <= byte <= 126 for byte in sample)
    score += int(50_000 * printable / max(1, len(sample)))
    return score


def salvage_gzip_tail(out_dir: Path, max_candidates: int = 12) -> dict[str, Any]:
    if not GZIP_SOURCE.exists():
        return {"status": "missing"}

    encoded = "".join(GZIP_SOURCE.read_text(encoding="utf-8").split())
    report: dict[str, Any] = {
        "encoded_chars": len(encoded),
        "encoded_sha256": sha256(encoded.encode("ascii")),
        "starts_with_gzip_base64": encoded.startswith("H4sI"),
        "decode_variants": decode_base64_variants(encoded),
    }

    candidates: list[dict[str, Any]] = []
    for drop in range(4):
        candidate = encoded[drop:]
        padded = candidate + ("=" * ((-len(candidate)) % 4))
        try:
            raw = base64.b64decode(padded, validate=True)
        except Exception:
            continue

        for byte_offset in range(len(raw)):
            for bit_offset in range(8):
                stream = shift_lsb_stream(raw, byte_offset, bit_offset)
                if len(stream) < 16:
                    continue
                try:
                    obj = zlib.decompressobj(wbits=-15)
                    payload = obj.decompress(stream, 4_000_000)
                except zlib.error:
                    continue
                score = score_salvage(payload)
                if score < 60_000:
                    continue
                row = {
                    "base64_drop": drop,
                    "byte_offset": byte_offset,
                    "bit_offset": bit_offset,
                    "output_bytes": len(payload),
                    "output_sha256": sha256(payload),
                    "unused_data_bytes": len(obj.unused_data),
                    "eof": obj.eof,
                    "score": score,
                    "jdb_ids": sorted(set(JDB_RE.findall(payload.decode("utf-8", errors="ignore")))),
                    "task_tokens": len(TASK_ID_RE.findall(payload.decode("utf-8", errors="ignore"))),
                    "payload": payload,
                }
                candidates.append(row)
                candidates.sort(key=lambda item: (item["score"], item["output_bytes"]), reverse=True)
                if len(candidates) > max_candidates:
                    candidates = candidates[:max_candidates]

    serializable = []
    for index, row in enumerate(candidates, start=1):
        payload = row.pop("payload")
        file_name = f"gzip-tail-salvage-{index:02d}.bin"
        (out_dir / file_name).write_bytes(payload)
        try:
            (out_dir / f"gzip-tail-salvage-{index:02d}.txt").write_text(
                payload.decode("utf-8"), encoding="utf-8"
            )
            text_status = "utf8"
        except UnicodeDecodeError:
            (out_dir / f"gzip-tail-salvage-{index:02d}.txt").write_text(
                payload.decode("utf-8", errors="replace"), encoding="utf-8"
            )
            text_status = "replacement"
        row["file"] = file_name
        row["text_status"] = text_status
        serializable.append(row)

    report["status"] = "candidates" if serializable else "no_salvage"
    report["candidates"] = serializable
    return report


def git_history_inventory(out_dir: Path) -> dict[str, Any]:
    paths = [
        "programs/manzanita-99/MASTER_BACKLOG.json.gz.b64",
        "programs/manzanita-99/MASTER_BACKLOG.json.bz2.b64.part01",
        "programs/manzanita-99/MASTER_BACKLOG.json.bz2.b64.part02",
        "programs/manzanita-99/MASTER_BACKLOG.json.bz2.b64.part03",
        "programs/manzanita-99/MASTER_BACKLOG.json.bz2.b64.part04",
        "programs/manzanita-99/MASTER_BACKLOG.json.bz2.b64.part05",
        "programs/manzanita-99/MASTER_BACKLOG.json",
        "programs/manzanita-99/MASTER_BACKLOG.csv",
    ]
    rows: list[dict[str, Any]] = []
    for path in paths:
        commits = run("git", "log", "--all", "--format=%H", "--", path).splitlines()
        seen_blobs: set[str] = set()
        for commit in commits:
            spec = f"{commit}:{path}"
            blob = run("git", "rev-parse", spec, check=False).strip()
            if not re.fullmatch(r"[0-9a-f]{40}", blob) or blob in seen_blobs:
                continue
            seen_blobs.add(blob)
            payload = subprocess.run(
                ["git", "cat-file", "blob", blob],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            ).stdout
            rows.append(
                {
                    "path": path,
                    "commit": commit,
                    "blob": blob,
                    "bytes": len(payload),
                    "sha256": sha256(payload),
                    "starts_hex": payload[:24].hex(),
                    "ends_hex": payload[-24:].hex(),
                }
            )
    write_json(out_dir / "historical-backlog-blobs.json", {"objects": rows})

    commit_log = run(
        "git",
        "log",
        "--all",
        "--date=iso-strict",
        "--pretty=format:%H%x09%P%x09%aI%x09%s",
        "--",
        "programs/manzanita-99",
    )
    (out_dir / "program-history.tsv").write_text(commit_log + "\n", encoding="utf-8")

    patches = run(
        "git",
        "log",
        "--all",
        "--full-history",
        "--find-renames",
        "-p",
        "-G",
        "JDB99-[0-9]{3}",
        "--",
        "programs/manzanita-99",
        "resolution-backfill",
        "manzanita",
        check=False,
    )
    (out_dir / "jdb-history-patches.txt").write_text(patches, encoding="utf-8")

    return {
        "historical_objects": len(rows),
        "paths_with_objects": sorted({row["path"] for row in rows}),
        "history_commits": len(commit_log.splitlines()),
        "jdb_patch_bytes": len(patches.encode("utf-8")),
    }


def working_tree_token_inventory(out_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.stat().st_size > 8_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        tokens = sorted(set(TASK_ID_RE.findall(text)))
        if tokens:
            rows.append(
                {
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "tokens": tokens,
                }
            )
    write_json(out_dir / "working-tree-task-tokens.json", {"files": rows})
    return {
        "files": len(rows),
        "unique_tokens": len({token for row in rows for token in row["tokens"]}),
        "jdb_ids": sorted(
            {token for row in rows for token in row["tokens"] if JDB_RE.fullmatch(token)}
        ),
    }


def resolution_backfill_inventory(out_dir: Path) -> dict[str, Any]:
    inventory_path = REPO_ROOT / "resolution-backfill" / "inventory.json"
    if not inventory_path.exists():
        return {"status": "missing"}
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    surface_rows: list[dict[str, Any]] = []
    exact_components: list[dict[str, Any]] = []
    for relative in inventory.get("surface_files", []):
        path = inventory_path.parent / relative
        surface = json.loads(path.read_text(encoding="utf-8"))
        findings = surface.get("findings", [])
        assets = surface.get("assets_required", [])
        surface_rows.append(
            {
                "surface": surface.get("id"),
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "findings": len(findings),
                "assets_required": len(assets),
                "component_total": 1 + len(findings) + len(assets),
            }
        )
        exact_components.append(
            {
                "kind": "surface_epic",
                "surface": surface.get("id"),
                "source_path": path.relative_to(REPO_ROOT).as_posix(),
                "source_index": 0,
                "record": {
                    "class": surface.get("class"),
                    "paths": surface.get("paths"),
                    "current_claim": surface.get("current_claim"),
                    "claim_evidence": surface.get("claim_evidence"),
                    "resolution_status": surface.get("resolution_status"),
                    "evidence_tier": surface.get("evidence_tier"),
                    "actors": surface.get("actors"),
                    "mechanism": surface.get("mechanism"),
                    "gates": surface.get("gates"),
                    "next_gate": surface.get("next_gate"),
                },
            }
        )
        for finding_index, finding in enumerate(findings, start=1):
            exact_components.append(
                {
                    "kind": "finding",
                    "surface": surface.get("id"),
                    "source_path": path.relative_to(REPO_ROOT).as_posix(),
                    "source_index": finding_index,
                    "record": finding,
                }
            )
        for asset_index, asset in enumerate(assets, start=1):
            exact_components.append(
                {
                    "kind": "required_asset",
                    "surface": surface.get("id"),
                    "source_path": path.relative_to(REPO_ROOT).as_posix(),
                    "source_index": asset_index,
                    "record": asset,
                }
            )

    write_json(
        out_dir / "resolution-backfill-exact-components.json",
        {
            "qualification_boundary": (
                "These are exact source components from the ten governed surface records. "
                "They are not assigned canonical backlog IDs, priorities, phases, owners, or "
                "dependencies unless those fields are recovered from the original register."
            ),
            "components": exact_components,
        },
    )
    return {
        "status": "inventoried",
        "surface_count": len(surface_rows),
        "surface_rows": surface_rows,
        "component_total": len(exact_components),
        "kind_counts": dict(Counter(row["kind"] for row in exact_components)),
        "matches_declared_104": len(exact_components) == 104,
    }


def source_receipts() -> dict[str, Any]:
    paths = [GZIP_SOURCE, *BZ2_PARTS]
    return {
        "files": [file_receipt(path) for path in paths if path.exists()],
        "missing": [path.relative_to(REPO_ROOT).as_posix() for path in paths if not path.exists()],
    }


def final_report(out_dir: Path, *, skip_deflate_scan: bool) -> dict[str, Any]:
    report = {
        "schema": "axm-tools/manzanita-backlog-forensic-recovery@1",
        "head": run("git", "rev-parse", "HEAD").strip(),
        "repository": "BigBirdReturns/axm-tools",
        "qualification_boundary": (
            "Recovered bytes and exact source components are evidence. A task becomes canonical "
            "only when every required field, source identity, amendment, count, and dependency "
            "is reproduced without inference."
        ),
        "source_receipts": source_receipts(),
        "bz2_prefix": partial_bz2_recovery(out_dir),
        "git_history": git_history_inventory(out_dir),
        "working_tree_tokens": working_tree_token_inventory(out_dir),
        "resolution_backfill": resolution_backfill_inventory(out_dir),
    }
    if skip_deflate_scan:
        report["gzip_tail_salvage"] = {"status": "skipped"}
    else:
        report["gzip_tail_salvage"] = salvage_gzip_tail(out_dir)

    exact_task_count = report["bz2_prefix"].get("complete_task_objects", 0)
    report["recovery_state"] = {
        "exact_complete_task_objects_from_bz2_prefix": exact_task_count,
        "exact_resolution_components": report["resolution_backfill"].get("component_total", 0),
        "canonical_497_recovered": False,
        "reason": (
            "The repository contains an invalid gzip/Base64 object and only two of five BZ2/Base64 "
            "repair chunks. This audit does not synthesize missing canonical records."
        ),
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--skip-deflate-scan",
        action="store_true",
        help="Skip the expensive bit-aligned raw-deflate salvage scan.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = final_report(out_dir, skip_deflate_scan=args.skip_deflate_scan)
    write_json(out_dir / "RECOVERY_REPORT.json", report)

    print(
        json.dumps(
            {
                "result": "PARTIAL",
                "head": report["head"],
                "bz2_complete_tasks": report["bz2_prefix"].get("complete_task_objects", 0),
                "resolution_components": report["resolution_backfill"].get("component_total", 0),
                "resolution_matches_104": report["resolution_backfill"].get(
                    "matches_declared_104", False
                ),
                "gzip_salvage": report["gzip_tail_salvage"].get("status"),
                "canonical_497_recovered": False,
                "out": str(out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
