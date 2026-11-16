#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Convert two common vendor log exports to Incident Commons event JSONL.

Conservative mappings only; unsupported source events remain explicitly counted.
Never performs cloud API calls or authenticates to an organization.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from incident import read_events, canonical, sha, MAX_BYTES, IDENT_RE, Refusal

AWS_EVENT_MAP = {
    "ConsoleLogin": "auth_success",
    "CreateAccessKey": "token_created",
    "DisableMFADevice": "mfa_disabled",
    "PutUserPolicy": "role_granted",
    "AttachUserPolicy": "role_granted",
    "AttachRolePolicy": "role_granted",
    "PutRolePolicy": "role_granted",
    "CreatePolicyVersion": "role_granted",
    "GetSecretValue": "secret_read",
}


def parse_export(raw):
    if len(raw) > MAX_BYTES:
        raise Refusal("SIZE_LIMIT", "vendor export too large")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Refusal("INVALID_JSON", str(e)) from e
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("Records", "value", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise Refusal("VENDOR_SHAPE", "expected JSON array or Records/value envelope")


def convert_aws(record, tenant):
    name = record.get("eventName")
    if name not in AWS_EVENT_MAP:
        return None
    if not all(record.get(k) for k in ("eventTime", "eventID", "sourceIPAddress")):
        raise Refusal("SOURCE_MISSING", f"CloudTrail required eventID/time/IP missing for {name}")
    identity = record.get("userIdentity") or {}
    if not isinstance(identity, dict):
        raise Refusal("SOURCE_SHAPE", "userIdentity must be object")
    actor = identity.get("arn") or identity.get("principalId") or identity.get("userName")
    if not actor:
        raise Refusal("SOURCE_MISSING", f"CloudTrail actor missing for {name}")
    outcome = "failure" if record.get("errorCode") else "success"
    if name == "ConsoleLogin":
        login = (record.get("responseElements") or {}).get("ConsoleLogin")
        if login not in ("Success", "Failure"):
            raise Refusal("SOURCE_UNKNOWN", "ConsoleLogin outcome missing")
        outcome = "success" if login == "Success" else "failure"
    kind = "auth_failure" if name == "ConsoleLogin" and outcome == "failure" else AWS_EVENT_MAP[name]
    detail = record.get("requestParameters") or {}
    if not isinstance(detail, dict):
        detail = {}
    target = detail.get("userName") or detail.get("roleName") or detail.get("secretId") or record.get("eventSource") or name
    return {"id": "aws:"+str(record["eventID"]), "ts": str(record["eventTime"]),
            "tenant": tenant, "kind": kind, "actor": str(actor),
            "src": str(record["sourceIPAddress"]), "target": str(target),
            "outcome": outcome}


def convert_entra(record, tenant):
    # Input is exported Microsoft Entra sign-in log JSON. No Graph queries.
    if not all(record.get(k) for k in ("id", "createdDateTime", "ipAddress", "userPrincipalName")):
        raise Refusal("SOURCE_MISSING", "Entra sign-in event missing id/time/ip/principal")
    status = record.get("status")
    if not isinstance(status, dict) or type(status.get("errorCode")) is not int:
        raise Refusal("SOURCE_UNKNOWN", "Entra status.errorCode must be an integer")
    success = status["errorCode"] == 0
    return {"id": "entra:"+str(record["id"]), "ts": str(record["createdDateTime"]),
            "tenant": tenant, "kind": "auth_success" if success else "auth_failure",
            "actor": str(record["userPrincipalName"]),
            "src": str(record["ipAddress"]),
            "target": str(record.get("resourceDisplayName") or record.get("appDisplayName") or "sign-in"),
            "outcome": "success" if success else "failure"}


def convert(raw, provider, tenant):
    if provider not in ("aws-cloudtrail", "entra-signin"):
        raise Refusal("UNKNOWN_PROVIDER", provider)
    if not IDENT_RE.fullmatch(tenant):
        raise Refusal("BAD_TENANT", tenant)
    incoming = parse_export(raw)
    if len(incoming) > 20_000:
        raise Refusal("EVENT_COUNT", "vendor event count exceeds 20,000")
    if not incoming:
        raise Refusal("EMPTY_SOURCE", "no vendor events")
    outgoing, skipped = [], Counter()
    for i, rec in enumerate(incoming, 1):
        if not isinstance(rec, dict):
            raise Refusal("SOURCE_SHAPE", f"vendor event {i} not object")
        if provider == "aws-cloudtrail":
            event = convert_aws(rec, tenant)
            if event is None:
                skipped["UNMAPPED_EVENT_NAME"] += 1
                continue
        else:
            event = convert_entra(rec, tenant)
        outgoing.append(event)
    if not outgoing:
        raise Refusal("NO_MAPPED_EVENTS", "no events were safely mapped; check source schema")
    body = ("\n".join(canonical(e) for e in outgoing) + "\n").encode("utf-8")
    validated = read_events(body)
    receipt = {
        "schema": "axm/incident-commons-source-transform@1",
        "provider": provider, "tenant": tenant,
        "source_sha256": sha(raw), "source_count": len(incoming),
        "mapped_count": len(validated), "skipped": dict(skipped),
        "normalized_sha256": sha(body),
        "claim": "Shape mapping only. No credential, threat attribution, or incident declaration established.",
        "custody": "Original source must be retained separately under its owner and compared by source_sha256."
    }
    return body, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("aws-cloudtrail", "entra-signin"))
    parser.add_argument("source", type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.source.read_bytes()
        body, receipt = convert(raw, args.provider, args.tenant)
        if args.out.resolve() == args.source.resolve():
            raise Refusal("SOURCE_OVERWRITE", "never overwrite original vendor evidence")
        args.out.write_bytes(body)
        args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2)+"\n")
        print(canonical({"status": "TRANSFORMED_NOT_ATTESTED", "events": receipt["mapped_count"],
                         "skipped": receipt["skipped"],
                         "source_sha256": receipt["source_sha256"],
                         "normalized_sha256": receipt["normalized_sha256"]}))
        return 0
    except (Refusal, OSError, ValueError, TypeError, KeyError) as e:
        print(canonical({"status": "REFUSED",
                         "reason": getattr(e, "code", type(e).__name__),
                         "detail": str(e)[:230]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
