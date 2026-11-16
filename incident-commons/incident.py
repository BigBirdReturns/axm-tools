#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Incident Commons: deterministic, evidence-bound incident response triage.

No cloud, model dependency, network calls, or containment side effects.
A case is a candidate for human-led response, not an automatic verdict.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "axm/incident-commons@1"
CASE_SCHEMA = "axm/incident-commons-case@1"
KINDS = frozenset({
    "auth_failure", "auth_success", "mfa_disabled",
    "token_created", "role_granted", "secret_read", "bulk_export",
    "tool_invocation", "service_changed", "suspicious_payload",
    "alert", "benign_activity"
})
KIND_LABELS = {
    "auth_failure": "Authentication failure",
    "auth_success": "Authentication success",
    "mfa_disabled": "MFA protection disabled",
    "token_created": "Credential/token issued",
    "role_granted": "Privilege assigned",
    "secret_read": "Sensitive material accessed",
    "bulk_export": "Bulk data exported",
    "tool_invocation": "Tool called",
    "service_changed": "Service configuration changed",
    "suspicious_payload": "Untrusted payload observed",
    "alert": "External alert",
    "benign_activity": "Benign control event",
}
MAX_BYTES = 6 * 1024 * 1024
MAX_EVENTS = 20_000
TIME_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$")
IDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")
REQUIRED = ("id", "ts", "tenant", "kind", "actor", "src", "target", "outcome")
SOURCE_LINKS = ("https://csrc.nist.gov/pubs/sp/800/61/r3/final",
                "https://www.cisa.gov/resources-tools/resources/federal-government-cybersecurity-incident-and-vulnerability-response-playbooks")


class Refusal(ValueError):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()


def timestamp(value):
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise Refusal("BAD_TIMESTAMP", str(value)[:80])
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise Refusal("BAD_TIMESTAMP", str(value)) from e
    return d.astimezone(timezone.utc)


def read_events(data: bytes):
    if len(data) > MAX_BYTES:
        raise Refusal("SIZE_LIMIT", f"input over {MAX_BYTES} bytes")
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise Refusal("UTF8_REQUIRED", str(e)) from e
    if raw.lstrip().startswith("["):
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as e:
            raise Refusal("INVALID_JSON", str(e)) from e
    else:
        entries = []
        for n, line in enumerate(raw.splitlines(), 1):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise Refusal("INVALID_JSONL", f"line {n}: {e}") from e
    if not isinstance(entries, list) or not entries or len(entries) > MAX_EVENTS:
        raise Refusal("EVENT_COUNT", f"require 1..{MAX_EVENTS} events")
    seen, out = set(), []
    for i, record in enumerate(entries, 1):
        if not isinstance(record, dict):
            raise Refusal("EVENT_SHAPE", f"record {i} must be object")
        for field in REQUIRED:
            if field not in record or not isinstance(record[field], str) or not record[field]:
                raise Refusal("REQUIRED_FIELD", f"record {i} missing {field}")
        idv = record["id"]
        if not IDENT_RE.fullmatch(idv) or idv in seen:
            raise Refusal("DUPLICATE_OR_INVALID_ID", idv[:100])
        seen.add(idv)
        if record["kind"] not in KINDS:
            raise Refusal("UNKNOWN_KIND", record["kind"][:80])
        if not IDENT_RE.fullmatch(record["tenant"]):
            raise Refusal("BAD_TENANT", record["tenant"][:80])
        if record["outcome"] not in ("success", "failure", "unknown"):
            raise Refusal("BAD_OUTCOME", record["outcome"][:80])
        at = timestamp(record["ts"])
        bytes_out = record.get("bytes_out", 0)
        if type(bytes_out) is not int or not 0 <= bytes_out <= 10**15:
            raise Refusal("BAD_BYTE_COUNT", f"record {i}")
        item = {key: record[key] for key in REQUIRED}
        item["ts"] = at.isoformat().replace("+00:00", "Z")
        item["bytes_out"] = bytes_out
        # Evidence text is untrusted data, never a command or privileged prompt.
        if "note" in record:
            if not isinstance(record["note"], str):
                raise Refusal("BAD_NOTE", f"record {i}")
            item["note"] = record["note"][:1000]
        out.append(item)
    return sorted(out, key=lambda x: (x["ts"], x["id"]))


def within(ev, later, minutes):
    d = timestamp(later["ts"]) - timestamp(ev["ts"])
    return timedelta(0) <= d <= timedelta(minutes=minutes)


def finding(rule, severity, summary, rows, interpretation, next_step):
    ids = list(dict.fromkeys(e["id"] for e in rows))
    return {
        "id": rule + ":" + sha(canonical(ids).encode())[:12],
        "rule": rule, "severity": severity, "status": "EVIDENCE_SUPPORTED",
        "summary": summary, "evidence_ids": ids,
        "interpretation": interpretation, "proposed_action": next_step,
        "authority": "REQUIRES_ORGANIZATION_APPROVAL",
    }


def analyze_events(events):
    results = []
    produced = set()
    def add(item):
        if item["id"] not in produced:
            results.append(item)
            produced.add(item["id"])

    per_tenant = defaultdict(list)
    for e in events:
        per_tenant[e["tenant"]].append(e)

    for tenant, es in per_tenant.items():
        failures = [x for x in es if x["kind"] == "auth_failure"]
        for anchor in failures:
            cluster = [x for x in failures
                       if x["src"] == anchor["src"] and within(anchor, x, 10)]
            principals = {x["actor"] for x in cluster}
            if len(cluster) >= 5 and len(principals) >= 3:
                # Dedup overlapping sliding windows by shared source and evidence.
                selected = sorted(cluster, key=lambda x: (x["ts"], x["id"]))
                key = "SPRAY:" + tenant + ":" + anchor["src"]
                if key not in produced:
                    add(finding("PASSWORD_SPRAY", "HIGH",
                        f"Multiple accounts received failed logins from a common source in {tenant}",
                        selected, "Credential attack hypothesis supported by observed failures; attribution unproven",
                        "Scope affected accounts; preserve auth telemetry; review source controls"))
                    produced.add(key)

        successes = [x for x in es if x["kind"] == "auth_success"]
        for login in successes:
            prior = [e for e in failures if e["src"] == login["src"]
                     and within(e, login, 15)]
            if len(prior) >= 3:
                evidence = sorted(prior, key=lambda x: (x["ts"], x["id"]))[-8:] + [login]
                add(finding("LOGIN_AFTER_FAILURES", "HIGH",
                    f"Successful authentication followed repeated failures from the same source: {login['actor']}",
                    evidence, "Possible account compromise; login alone does not prove compromise",
                    "Verify device/session with identity owner; consider session revocation only after approval"))
            follow = [x for x in es if x["actor"] == login["actor"]
                      and within(login, x, 30)]
            risky = [x for x in follow if x["kind"] in ("mfa_disabled", "role_granted", "token_created")]
            if risky and (prior or any(x["kind"] == "mfa_disabled" for x in risky)):
                add(finding("IDENTITY_PERSISTENCE", "CRITICAL",
                    f"Identity security or access privileges changed following suspicious authentication: {login['actor']}",
                    [login] + risky, "Observed session and credential control changes need immediate authorization review",
                    "Prepare scoped token revocation and MFA restoration request; preserve audit trail"))

        tokens = [x for x in es if x["kind"] == "token_created"]
        reads = [x for x in es if x["kind"] == "secret_read"]
        exports = [x for x in es if x["kind"] == "bulk_export" and x["bytes_out"] >= 100_000_000]
        for e in exports:
            pred = [x for x in tokens + reads if x["actor"] == e["actor"] and within(x, e, 45)]
            if pred:
                add(finding("TOKEN_TO_EXPORT", "CRITICAL",
                    f"Sensitive access preceded an unusually large export by {e['actor']}",
                    sorted(pred, key=lambda x: (x["ts"], x["id"]))[-8:] + [e],
                    "Export volume and preceding access are observed; exfiltration destination and intent unproven",
                    "Preserve export/object-access evidence; assess egress; request scoped containment approval"))
            else:
                add(finding("LARGE_EXPORT", "MEDIUM",
                    f"Large data export observed: {e['actor']}",
                    [e], "Volume alone does not establish malicious activity",
                    "Confirm whether this export matches a preapproved business workflow"))

        for e in es:
            if e["kind"] == "suspicious_payload":
                add(finding("UNTRUSTED_PAYLOAD", "LOW",
                    f"Untrusted content encountered by a workflow in {tenant}",
                    [e], "Recorded text is untrusted evidence and may contain adversarial instructions",
                    "Quarantine untrusted content from agent tools; review provenance and task context"))

    priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(results, key=lambda x: (priority[x["severity"]], x["rule"], x["id"]))


def case_for(raw: bytes, case_id: str):
    if not IDENT_RE.fullmatch(case_id):
        raise Refusal("BAD_CASE_ID", case_id)
    events = read_events(raw)
    findings = analyze_events(events)
    scope = sorted({e["tenant"] for e in events})
    body = {
        "schema": CASE_SCHEMA, "case_id": case_id, "source_sha256": sha(raw),
        "event_count": len(events), "tenants": scope,
        "events": events, "findings": findings,
        "ruleset": "incident-commons-r1", "sources": list(SOURCE_LINKS),
        "state": "TRIAGED_CANDIDATE",
        "decision_ledger": [],
        "limitations": [
            "Rules detect correlations, not attacker identity or incident confirmation",
            "No host/network action is executed; org-approved containment remains external",
            "No AI output is elevated to fact without source event IDs",
            "Source file SHA-256 preserves bytes but is not independent signature or custody chain",
            "Customer IAM, lawful authority, disclosure, retention and incident declaration are external",
        ],
    }
    return {**body, "sha256": sha(canonical(body).encode())}


def verify_case(payload):
    if not isinstance(payload, dict) or payload.get("schema") != CASE_SCHEMA:
        raise Refusal("CASE_SCHEMA", "wrong or absent schema")
    given = payload.get("sha256")
    body = {key: value for key, value in payload.items() if key != "sha256"}
    if given != sha(canonical(body).encode()):
        raise Refusal("CASE_TAMPER", "case contents changed")
    ids = {e["id"] for e in body["events"]}
    for f in body["findings"]:
        if not f["evidence_ids"] or not set(f["evidence_ids"]).issubset(ids):
            raise Refusal("ORPHAN_EVIDENCE", f["id"])
    return {"status": "PASS", "case_id": body["case_id"],
            "events": len(body["events"]), "findings": len(body["findings"]),
            "sha256": given}


def public_preview(case):
    verify_case(case)
    counts = Counter(e["kind"] for e in case["events"])
    return {
        "schema": "axm/incident-commons-share-preview@1",
        "case_fingerprint": case["sha256"][:16],
        "event_count": case["event_count"],
        "tenant_count": len(case["tenants"]),
        "activity_counts": dict(sorted(counts.items())),
        "finding_counts": dict(Counter(f["severity"] for f in case["findings"])),
        "source_attested": False,
        "warning": "Share-safe by default: no raw evidence, actors, IP addresses, event IDs, or targets. Human disclosure review still required."
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("analyze", help="analyze JSONL/JSON events without network access")
    a.add_argument("source", type=Path)
    a.add_argument("--case-id", required=True)
    a.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("verify", help="verify case fingerprint and evidence references")
    v.add_argument("case", type=Path)
    s = sub.add_parser("share", help="emit aggregate-only public preview")
    s.add_argument("case", type=Path)
    s.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.mode == "analyze":
            case = case_for(args.source.read_bytes(), args.case_id)
            args.out.write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            result = {"status": "TRIAGED_CANDIDATE", "case_id": case["case_id"],
                      "findings": len(case["findings"]), "sha256": case["sha256"]}
        elif args.mode == "verify":
            result = verify_case(json.loads(args.case.read_text(encoding="utf-8")))
        else:
            case = json.loads(args.case.read_text(encoding="utf-8"))
            preview = public_preview(case)
            args.out.write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")
            result = {"status": "SHARE_PREVIEW_GENERATED", "path": str(args.out)}
        print(canonical(result))
        return 0
    except (Refusal, OSError, ValueError, KeyError, TypeError) as e:
        code = e.code if isinstance(e, Refusal) else type(e).__name__
        print(canonical({"status": "REFUSED", "reason": code, "detail": str(e)[:300]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
