#!/usr/bin/env python3
"""Network-free intake for one RedCat Case Zero engagement.

The runner inventories source files without copying source bodies or emitting
matched credential and PII values. It creates a source manifest, case state,
analysis queue, missing-evidence projection, and SHA-256 ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "redcat/case-zero-intake@0.1"
MAX_SCAN_BYTES = 2 * 1024 * 1024
TEXT_SUFFIXES = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
    ".xml", ".html", ".htm", ".eml", ".log", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".java", ".go", ".rs", ".sql", ".toml", ".ini", ".cfg", ".conf",
}
ROLE_RULES = [
    ("commercial", ("proposal", "sow", "statement-of-work", "quote", "contract", "msa", "nda")),
    ("economics", ("invoice", "estimate", "budget", "cost", "timesheet", "hours", "payment")),
    ("acceptance", ("acceptance", "uat", "signoff", "test", "qa", "definition-of-done", "dod")),
    ("change", ("change-request", "change_order", "scope-change", "variation", "amendment")),
    ("communication", ("email", "slack", "teams", "message", "chat", "meeting", "call", "notes")),
    ("delivery", ("ticket", "jira", "backlog", "sprint", "milestone", "roadmap", "release")),
    ("technical", ("architecture", "design", "api", "schema", "interface", "diagram", "adr")),
    ("source_code", ("src", "source", "repo", "commit", "diff", "patch")),
    ("outcome", ("postmortem", "retro", "retrospective", "outcome", "closure", "cancel", "failed")),
]
SECRET_PATTERNS = {
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github_token": re.compile(rb"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "bearer_token": re.compile(rb"(?i)\bAuthorization\s*:\s*Bearer\s+\S+"),
    "password_assignment": re.compile(rb"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[^\s,;]+"),
    "connection_string": re.compile(rb"(?i)\b(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^ \r\n]+"),
}
PII_PATTERNS = {
    "email": re.compile(rb"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone": re.compile(rb"(?<!\d)(?:\+?\d[\d .()/-]{7,}\d)(?!\d)"),
    "ssn_shape": re.compile(rb"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "ipv4": re.compile(rb"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"),
}
TASKS = [
    ("CZ-01", "Engagement timeline", [], "ENGAGEMENT_TIMELINE.json"),
    ("CZ-02", "Promise and scope ledger", ["CZ-01"], "PROMISE_SCOPE_LEDGER.json"),
    ("CZ-03", "Scope-change ledger", ["CZ-01", "CZ-02"], "SCOPE_CHANGE_LEDGER.json"),
    ("CZ-04", "Acceptance ledger", ["CZ-01", "CZ-02"], "ACCEPTANCE_LEDGER.json"),
    ("CZ-05", "Work and economics ledger", ["CZ-01", "CZ-03"], "WORK_ECONOMICS_LEDGER.json"),
    ("CZ-06", "Failure mechanism", ["CZ-02", "CZ-03", "CZ-04", "CZ-05"], "FAILURE_MECHANISM.md"),
    ("CZ-07", "Counterfactual PoC", ["CZ-06"], "COUNTERFACTUAL_POC.json"),
    ("CZ-08", "Implementation packages", ["CZ-07"], "IMPLEMENTATION_PACKAGES.json"),
    ("CZ-09", "Architect challenge", ["CZ-01", "CZ-06", "CZ-08"], "ARCHITECT_CHALLENGE_LEDGER.json"),
    ("CZ-10", "Shadow-pilot contract", ["CZ-05", "CZ-09"], "SHADOW_PILOT_CONTRACT.md"),
]


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def classify_role(relative_path: str) -> str:
    normalized = relative_path.lower().replace("\\", "/")
    for role, needles in ROLE_RULES:
        if any(needle in normalized for needle in needles):
            return role
    return "unknown"


def scan_signals(path: Path) -> tuple[dict[str, int], dict[str, int], bool]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return {}, {}, False
    with path.open("rb") as handle:
        data = handle.read(MAX_SCAN_BYTES + 1)
    truncated = len(data) > MAX_SCAN_BYTES
    data = data[:MAX_SCAN_BYTES]
    secrets = {name: len(pattern.findall(data)) for name, pattern in SECRET_PATTERNS.items()}
    pii = {name: len(pattern.findall(data)) for name, pattern in PII_PATTERNS.items()}
    return ({k: v for k, v in secrets.items() if v}, {k: v for k, v in pii.items() if v}, truncated)


def collect_sources(source_root: Path, output_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    output_resolved = output_root.resolve()
    for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file() or path.is_symlink():
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(output_resolved)
            continue
        except ValueError:
            pass
        relative = path.relative_to(source_root).as_posix()
        secrets, pii, truncated = scan_signals(path)
        rows.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "suffix": path.suffix.lower(),
            "source_class_guess": classify_role(relative),
            "secret_signal_counts": secrets,
            "pii_signal_counts": pii,
            "text_scan_truncated": truncated,
        })
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json(value))


def write_sha256s(output_root: Path) -> None:
    rows = []
    for path in sorted(output_root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append(f"{sha256_file(path)}  {path.name}")
    (output_root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def missing_evidence(rows: list[dict[str, Any]]) -> str:
    present = {row["source_class_guess"] for row in rows}
    required = ["commercial", "communication", "delivery", "technical", "economics", "acceptance", "outcome"]
    missing = [role for role in required if role not in present]
    lines = [
        "# Missing Evidence Projection", "",
        "This is a filename- and format-level intake projection, not a substantive finding.", "",
        "## Source classes observed", "",
        *(f"- {role}" for role in sorted(present)), "",
        "## Required source classes not observed", "",
        *(f"- {role}" for role in missing or ["none"]), "",
        "Absence from this projection does not prove the evidence never existed.",
        "It identifies which source classes need confirmation during reconstruction.", "",
    ]
    return "\n".join(lines)


def run_intake(args: argparse.Namespace) -> int:
    source_root = args.input.resolve()
    output_root = args.output.resolve()
    if not source_root.is_dir():
        raise ValueError("--input must be an existing directory")
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("--output must be absent or empty")
    output_root.mkdir(parents=True, exist_ok=True)

    rows = collect_sources(source_root, output_root)
    corpus_digest = hashlib.sha256(canonical_json(rows)).hexdigest()
    secret_files = [row["path"] for row in rows if row["secret_signal_counts"]]
    pii_files = [row["path"] for row in rows if row["pii_signal_counts"]]
    status = "HOLD_REDACTION_REQUIRED" if secret_files else "INTAKE_BOUND"

    manifest = {
        "schema": SCHEMA,
        "case_id": args.case_id,
        "as_of": args.as_of,
        "custody_mode": args.custody_mode,
        "source_root_disclosed": False,
        "source_count": len(rows),
        "source_bytes": sum(row["bytes"] for row in rows),
        "corpus_digest": corpus_digest,
        "sources": rows,
        "secret_signal_file_count": len(secret_files),
        "pii_signal_file_count": len(pii_files),
        "signal_values_disclosed": False,
        "source_files_copied": 0,
        "network_calls": 0,
    }
    case_state = {
        "schema": "redcat/case-zero-state@0.1",
        "case_id": args.case_id,
        "state": status,
        "candidate_only": True,
        "redcat_client_relationship": True,
        "tier_desk_client_relationship": False,
        "analysis_completed": False,
        "architect_review_completed": False,
        "shadow_pilot_authorized": False,
        "holds": ([{"code": "CREDENTIAL_SHAPED_SOURCE", "file_count": len(secret_files)}] if secret_files else []),
    }
    queue = {
        "schema": "redcat/case-zero-analysis-queue@0.1",
        "case_id": args.case_id,
        "authority": "candidate_analysis_only",
        "tasks": [
            {
                "id": task_id,
                "name": name,
                "predecessors": predecessors,
                "output": output,
                "acceptance": "source-addressed output satisfying OUTPUT_CONTRACT.json",
                "refusal": "missing or contradictory evidence remains explicit",
            }
            for task_id, name, predecessors, output in TASKS
        ],
    }

    write_json(output_root / "SOURCE_MANIFEST.json", manifest)
    write_json(output_root / "CASE_ZERO_STATE.json", case_state)
    write_json(output_root / "ANALYSIS_QUEUE.json", queue)
    (output_root / "MISSING_EVIDENCE.md").write_text(missing_evidence(rows), encoding="utf-8", newline="\n")
    write_sha256s(output_root)

    print(json.dumps({
        "status": status,
        "case_id": args.case_id,
        "source_count": len(rows),
        "corpus_digest": corpus_digest,
        "output": str(output_root),
    }, sort_keys=True))
    return 0 if status == "INTAKE_BOUND" else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="casezero")
    sub = parser.add_subparsers(dest="command", required=True)
    intake = sub.add_parser("intake", help="inventory one Case Zero source folder")
    intake.add_argument("--input", type=Path, required=True)
    intake.add_argument("--output", type=Path, required=True)
    intake.add_argument("--case-id", required=True)
    intake.add_argument("--custody-mode", choices=["redcat_local", "redacted_transfer", "supervised_readonly"], required=True)
    intake.add_argument("--as-of", required=True, help="fixed ISO-8601 timestamp supplied by the operator")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "intake":
            return run_intake(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"casezero: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
