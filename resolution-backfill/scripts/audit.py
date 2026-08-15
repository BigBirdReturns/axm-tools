#!/usr/bin/env python3
"""Compile and qualify the AXM resolution-backfill ledger.

A PASS means the estate has an internally complete, evidence-addressed record
of every reopened production surface. It does not mean those surfaces have
already passed their remediation gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GATE_KEYS = (
    "object_classification",
    "actors_authority",
    "source_custody",
    "mechanism_fidelity",
    "live_data_failure_states",
    "interaction_semantics",
    "visual_typography",
    "responsive_accessibility",
    "negative_stress_offline",
    "continuity_export_succession",
    "provenance_rights_privacy",
    "qualification_receipts",
)

GATE_VALUES = {"pass", "partial", "fail", "unknown", "not_applicable"}
STATUSES = {"reopened", "remediation_in_progress", "qualified", "retired"}
SEVERITIES = {"critical", "high", "medium", "low"}
EXPECTED_IDS = {
    "repository-shell",
    "acceptance",
    "breakout-parity",
    "clinical-site-fabric",
    "essential-attention",
    "identity",
    "manzanita",
    "organ-evolution",
    "polybolos",
    "pta-tracker",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def git_text(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def path_receipt(root: Path, relative: str) -> dict[str, Any]:
    target = root / relative
    if not target.exists():
        return {"path": relative, "exists": False}

    if target.is_file():
        return {
            "path": relative,
            "exists": True,
            "type": "file",
            "bytes": target.stat().st_size,
            "files": 1,
            "sha256": sha256_file(target),
        }

    if not target.is_dir():
        return {
            "path": relative,
            "exists": True,
            "type": "unsupported",
            "bytes": 0,
            "files": 0,
            "sha256": None,
        }

    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel.startswith("resolution-backfill/out/"):
            continue
        data = path.read_bytes()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        digest.update(b"\n")
        file_count += 1
        byte_count += len(data)

    return {
        "path": relative,
        "exists": True,
        "type": "directory",
        "bytes": byte_count,
        "files": file_count,
        "sha256": digest.hexdigest(),
    }


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_surface(
    root: Path,
    record_path: Path,
    surface: dict[str, Any],
    errors: list[str],
) -> None:
    sid = surface.get("id")
    prefix = f"{record_path.as_posix()}"
    required = {
        "id",
        "class",
        "paths",
        "current_claim",
        "claim_evidence",
        "resolution_status",
        "evidence_tier",
        "actors",
        "mechanism",
        "gates",
        "findings",
        "assets_required",
        "next_gate",
    }
    require(required <= set(surface), f"{prefix}: missing required keys", errors)
    require(isinstance(sid, str) and sid == record_path.stem, f"{prefix}: id must match filename", errors)
    require(surface.get("resolution_status") in STATUSES, f"{prefix}: invalid resolution_status", errors)
    require(isinstance(surface.get("current_claim"), str) and len(surface["current_claim"]) >= 20, f"{prefix}: current_claim is too short", errors)
    require(isinstance(surface.get("mechanism"), str) and len(surface["mechanism"]) >= 20, f"{prefix}: mechanism is too short", errors)
    require(isinstance(surface.get("next_gate"), str) and len(surface["next_gate"]) >= 20, f"{prefix}: next_gate is too short", errors)

    actors = surface.get("actors")
    require(isinstance(actors, list) and len(actors) >= 2 and len(actors) == len(set(actors)), f"{prefix}: actors must contain unique functional roles", errors)

    paths = surface.get("paths")
    require(isinstance(paths, list) and bool(paths), f"{prefix}: paths must be non-empty", errors)
    if isinstance(paths, list):
        for declared in paths:
            require(isinstance(declared, str) and (root / declared).exists(), f"{prefix}: declared path does not exist: {declared}", errors)

    evidence = surface.get("claim_evidence")
    require(isinstance(evidence, list) and bool(evidence), f"{prefix}: claim_evidence must be non-empty", errors)
    if isinstance(evidence, list):
        for declared in evidence:
            require(isinstance(declared, str) and (root / declared).exists(), f"{prefix}: claim evidence does not exist: {declared}", errors)

    gates = surface.get("gates")
    require(isinstance(gates, dict), f"{prefix}: gates must be an object", errors)
    if isinstance(gates, dict):
        require(set(gates) == set(GATE_KEYS), f"{prefix}: gates must match the twelve release gates exactly", errors)
        for key, value in gates.items():
            require(value in GATE_VALUES, f"{prefix}: invalid gate value {key}={value}", errors)

    findings = surface.get("findings")
    require(isinstance(findings, list) and bool(findings), f"{prefix}: findings must be non-empty", errors)
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            label = f"{prefix}: finding {index + 1}"
            require(isinstance(finding, dict), f"{label} must be an object", errors)
            if not isinstance(finding, dict):
                continue
            require(finding.get("severity") in SEVERITIES, f"{label} has invalid severity", errors)
            require(isinstance(finding.get("title"), str) and len(finding["title"]) >= 10, f"{label} title is too short", errors)
            require(isinstance(finding.get("mechanism"), str) and len(finding["mechanism"]) >= 20, f"{label} mechanism is too short", errors)
            require(isinstance(finding.get("evidence"), list) and bool(finding["evidence"]), f"{label} evidence is missing", errors)
            require(isinstance(finding.get("acceptance"), str) and len(finding["acceptance"]) >= 20, f"{label} acceptance is too short", errors)

    assets = surface.get("assets_required")
    require(isinstance(assets, list) and bool(assets) and len(assets) == len(set(assets)), f"{prefix}: assets_required must be a non-empty unique list", errors)

    if surface.get("resolution_status") == "qualified" and isinstance(gates, dict):
        unpassed = {key: value for key, value in gates.items() if value not in {"pass", "not_applicable"}}
        critical = [finding for finding in findings or [] if isinstance(finding, dict) and finding.get("severity") == "critical"]
        require(not unpassed, f"{prefix}: qualified surface has unpassed mandatory gates: {unpassed}", errors)
        require(not critical, f"{prefix}: qualified surface retains critical findings", errors)


def discover_legacy_records(root: Path) -> list[str]:
    names = {"QUALIFICATION.json", "RELEASE_RECORD.json", "VALIDATION.md", "FREEZE_MANIFEST.md"}
    found: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in names:
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel.startswith("resolution-backfill/out/"):
            continue
        found.append(rel)
    return sorted(found)


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# AXM resolution backfill audit",
        "",
        f"**Result:** {report['result']}",
        "",
        "A PASS means the reopening ledger is complete and evidence-addressed. It does not mean the underlying products have completed remediation.",
        "",
        f"- Audited head: `{report.get('head_sha') or 'unavailable'}`",
        f"- Baseline: `{report['base_sha']}`",
        f"- Surfaces: {report['summary']['surface_count']}",
        f"- Qualified surfaces: {report['summary']['status_counts'].get('qualified', 0)}",
        f"- Critical findings: {report['summary']['finding_counts'].get('critical', 0)}",
        f"- Failed gates: {report['summary']['gate_counts'].get('fail', 0)}",
        f"- Unknown gates: {report['summary']['gate_counts'].get('unknown', 0)}",
        "",
        "| Surface | Status | Critical | Failed gates | Partial | Unknown | Next gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for surface in report["surfaces"]:
        gate_counts = Counter(surface["gates"].values())
        critical = sum(1 for finding in surface["findings"] if finding["severity"] == "critical")
        lines.append(
            "| {id} | {status} | {critical} | {fail} | {partial} | {unknown} | {next_gate} |".format(
                id=surface["id"],
                status=surface["resolution_status"],
                critical=critical,
                fail=gate_counts.get("fail", 0),
                partial=gate_counts.get("partial", 0),
                unknown=gate_counts.get("unknown", 0),
                next_gate=surface["next_gate"].replace("|", "\\|"),
            )
        )

    for surface in report["surfaces"]:
        lines.extend(
            [
                "",
                f"## {surface['id']}",
                "",
                f"**Class:** `{surface['class']}`  ",
                f"**Status:** `{surface['resolution_status']}`  ",
                f"**Evidence tier:** `{surface['evidence_tier']}`",
                "",
                surface["current_claim"],
                "",
                "### Findings",
            ]
        )
        for finding in surface["findings"]:
            lines.extend(
                [
                    "",
                    f"**{finding['severity'].upper()}: {finding['title']}**",
                    "",
                    finding["mechanism"],
                    "",
                    f"Acceptance: {finding['acceptance']}",
                ]
            )
        lines.extend(["", "### Assets required"])
        for asset in surface["assets_required"]:
            lines.append(f"- {asset}")
        lines.extend(["", f"**Next gate:** {surface['next_gate']}"])

    if report["errors"]:
        lines.extend(["", "## Audit errors"])
        for error in report["errors"]:
            lines.append(f"- {error}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("resolution-backfill/out"))
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    inventory_path = root / "resolution-backfill" / "inventory.json"
    errors: list[str] = []

    try:
        inventory = load_json(inventory_path)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    require(inventory.get("schema") == "axm-tools/resolution-backfill-inventory@1", "inventory: invalid schema", errors)
    require(isinstance(inventory.get("base_sha"), str) and len(inventory["base_sha"]) == 40, "inventory: invalid base_sha", errors)
    surface_files = inventory.get("surface_files")
    require(isinstance(surface_files, list) and bool(surface_files), "inventory: surface_files must be non-empty", errors)

    surfaces: list[dict[str, Any]] = []
    if isinstance(surface_files, list):
        require(len(surface_files) == len(set(surface_files)), "inventory: surface_files contains duplicates", errors)
        for relative in surface_files:
            record_path = root / "resolution-backfill" / relative
            if not record_path.exists():
                errors.append(f"inventory: missing surface record {relative}")
                continue
            try:
                surface = load_json(record_path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            validate_surface(root, Path(relative), surface, errors)
            surfaces.append(surface)

    ids = {surface.get("id") for surface in surfaces}
    require(ids == EXPECTED_IDS, f"inventory: expected surfaces {sorted(EXPECTED_IDS)}, found {sorted(str(value) for value in ids)}", errors)

    head_sha = git_text(root, "rev-parse", "HEAD")
    if head_sha and inventory.get("base_sha"):
        try:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", inventory["base_sha"], head_sha],
                cwd=root,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            errors.append("inventory base_sha is not an ancestor of the audited head")

    evidence_paths: set[str] = {"resolution-backfill/inventory.json", "resolution-backfill/RESOLUTION_LAW.md"}
    for surface in surfaces:
        evidence_paths.update(surface.get("claim_evidence", []))
        evidence_paths.update(surface.get("paths", []))

    receipts = [path_receipt(root, relative) for relative in sorted(evidence_paths)]
    for receipt in receipts:
        require(receipt["exists"], f"evidence receipt missing path: {receipt['path']}", errors)

    legacy_paths = discover_legacy_records(root)
    legacy_receipts = [path_receipt(root, relative) for relative in legacy_paths]

    status_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    finding_counts: Counter[str] = Counter()
    asset_count = 0
    for surface in surfaces:
        status_counts[surface["resolution_status"]] += 1
        gate_counts.update(surface["gates"].values())
        finding_counts.update(finding["severity"] for finding in surface["findings"])
        asset_count += len(surface["assets_required"])

    report = {
        "schema": "axm-tools/resolution-backfill-report@1",
        "generated_at": now_iso(),
        "result": "FAIL" if errors else "PASS",
        "meaning": "PASS qualifies the completeness and honesty of the reopening ledger, not the remediation of the products it audits.",
        "base_ref": inventory.get("base_ref"),
        "base_sha": inventory.get("base_sha"),
        "head_sha": head_sha,
        "inventory_sha256": sha256_file(inventory_path),
        "summary": {
            "surface_count": len(surfaces),
            "status_counts": dict(sorted(status_counts.items())),
            "gate_counts": dict(sorted(gate_counts.items())),
            "finding_counts": dict(sorted(finding_counts.items())),
            "asset_requirements": asset_count,
            "evidence_receipts": len(receipts),
            "legacy_records": len(legacy_receipts),
        },
        "surfaces": sorted(surfaces, key=lambda value: value["id"]),
        "errors": errors,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = out_dir / "report.json"
    report_md_path = out_dir / "report.md"
    receipts_path = out_dir / "evidence-receipts.json"
    qualification_path = out_dir / "qualification.json"

    report_json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report_md_path.write_text(markdown_report(report), encoding="utf-8")
    receipts_payload = {
        "schema": "axm-tools/resolution-backfill-evidence-receipts@1",
        "generated_at": report["generated_at"],
        "head_sha": head_sha,
        "evidence": receipts,
        "legacy_completion_records": legacy_receipts,
    }
    receipts_path.write_text(json.dumps(receipts_payload, indent=2) + "\n", encoding="utf-8")

    qualification = {
        "schema": "axm-tools/resolution-backfill-qualification@1",
        "qualified_at": report["generated_at"],
        "result": report["result"],
        "qualification_scope": "completeness, evidence addressability, and honesty of the estate-wide reopening ledger",
        "explicit_exclusion": "This result does not qualify any underlying product as remediated or complete.",
        "base_sha": inventory.get("base_sha"),
        "head_sha": head_sha,
        "surface_count": len(surfaces),
        "qualified_surface_count": status_counts.get("qualified", 0),
        "critical_findings": finding_counts.get("critical", 0),
        "failed_gates": gate_counts.get("fail", 0),
        "unknown_gates": gate_counts.get("unknown", 0),
        "artifacts": {
            "inventory.json": sha256_file(inventory_path),
            "report.json": sha256_file(report_json_path),
            "report.md": sha256_file(report_md_path),
            "evidence-receipts.json": sha256_file(receipts_path),
        },
    }
    qualification_path.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(qualification, indent=2))
    if errors:
        print("\nAudit errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
