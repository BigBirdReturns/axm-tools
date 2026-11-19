#!/usr/bin/env python3
"""Retain read-only i3X HTTP evidence for an explicitly mapped asset and value IDs."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

PUBLIC = "https://api.i3x.dev/v1"
DEFAULT_ASSET = "pump-101"
DEFAULT_VALUES = ["pump-101-state"]
DEFAULT_HISTORY = "pump-101-measurements-bearing-temperature-value"
LIMIT = 2_000_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Endpoint redirects are not followed; select the final authorized base URL.")

def normalize_base(base):
    parsed = urllib.parse.urlsplit(base.strip().rstrip("/"))
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL must not contain credentials, a query, or a fragment.")
    if not parsed.hostname:
        raise ValueError("An absolute endpoint URL is required.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
    ):
        raise ValueError("Use HTTPS, or an explicitly selected loopback test server.")
    return urllib.parse.urlunsplit(parsed)

def capture(base=PUBLIC, asset_id=DEFAULT_ASSET, value_ids=None,
            history_id=DEFAULT_HISTORY, token=None, timeout=25,
            evidence_label=None, production_data=None):
    base = normalize_base(base)
    if not isinstance(asset_id, str) or not asset_id.strip() or len(asset_id) > 2048:
        raise ValueError("A nonempty asset element ID is required.")
    value_ids = list(DEFAULT_VALUES if value_ids is None else value_ids)
    if not value_ids or len(value_ids) > 64 or any(
        not isinstance(v, str) or not v.strip() or len(v) > 2048 for v in value_ids
    ) or len(set(value_ids)) != len(value_ids):
        raise ValueError("Supply 1 to 64 distinct nonempty value element IDs.")
    if history_id is not None and (
        not isinstance(history_id, str) or not history_id.strip() or len(history_id) > 2048
    ):
        raise ValueError("Invalid history element ID.")
    if not 1 <= timeout <= 120:
        raise ValueError("Timeout must be between 1 and 120 seconds.")
    now = dt.datetime.now(dt.timezone.utc)
    requests = [(name, "GET", "/" + name, None) for name in
                ("info", "namespaces", "objecttypes", "relationshiptypes", "objects")]
    requests += [
        ("related", "POST", "/objects/related", {"elementIds": [asset_id], "includeMetadata": True}),
        ("value", "POST", "/objects/value", {"elementIds": value_ids, "maxDepth": 1}),
    ]
    if history_id is not None:
        requests.append(("history", "POST", "/objects/history", {
            "elementIds": [history_id], "startTime": (now-dt.timedelta(minutes=2)).isoformat(),
            "endTime": now.isoformat(), "maxDepth": 1,
        }))
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "User-Agent": "AXM-i3X-read-only-capture/0.2"}
    if token:
        headers["Authorization"] = "Bearer " + token
    opener = urllib.request.build_opener(NoRedirect)
    records = []
    for name, method, route, body in requests:
        request = urllib.request.Request(
            base + route, data=None if body is None else json.dumps(body).encode("utf-8"),
            method=method, headers=headers,
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                raw, status = response.read(LIMIT + 1), response.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(LIMIT + 1), exc.code
        if len(raw) > LIMIT:
            raise ValueError("Response exceeds capture limit: " + name)
        text = raw.decode("utf-8")
        try:
            json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("Expected a JSON response for " + name) from None
        records.append({
            "id": name, "url": base + route, "method": method, "request": body,
            "status": status, "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "body": text, "sha256": hashlib.sha256(raw).hexdigest(),
        })
    mapping = {"asset_id": asset_id, "value_ids": value_ids}
    if history_id is not None:
        mapping["history_id"] = history_id
    return {
        "schema": "axm-i3x-capture/1",
        "evidence_class": "public-demo-api-capture" if base == PUBLIC else "operator-provided-read-only-capture",
        "base_url": base, "captured_at": now.isoformat(),
        "production_data": False if base == PUBLIC else production_data,
        "evidence_label": evidence_label or ("CESMII public simulated demo" if base == PUBLIC else "Operator-selected endpoint; source custody remains with the operator"),
        "remote_writes": False, "mapping": mapping, "records": records,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=PUBLIC)
    parser.add_argument("--asset-id", default=DEFAULT_ASSET)
    parser.add_argument("--value-id", action="append", dest="value_ids")
    history = parser.add_mutually_exclusive_group()
    history.add_argument("--history-id")
    history.add_argument("--no-history", action="store_true")
    parser.add_argument("--token-env", help="Read a bearer token from this environment variable; never retain it.")
    parser.add_argument("--evidence-label", help="Operator-declared source description, retained as such.")
    parser.add_argument("--synthetic-data", action="store_true", help="Declare that this endpoint contains simulated data.")
    parser.add_argument("--timeout", type=float, default=25)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    target = Path(args.out)
    if target.exists():
        parser.error("Refusing to overwrite a retained capture. Choose a new output path.")
    if args.asset_id != DEFAULT_ASSET and not args.value_ids:
        parser.error("A different asset requires explicit --value-id arguments.")
    token = os.environ.get(args.token_env) if args.token_env else None
    if args.token_env and not token:
        parser.error("The selected token environment variable is empty.")
    history_id = args.history_id
    if not args.no_history and history_id is None and args.asset_id == DEFAULT_ASSET and not args.value_ids:
        history_id = DEFAULT_HISTORY
    result = capture(
        args.base_url, args.asset_id, args.value_ids, history_id, token, args.timeout,
        args.evidence_label, False if args.synthetic_data else None,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(json.dumps({
        "path": str(target), "responses": len(result["records"]),
        "http200": sum(r["status"] == 200 for r in result["records"]),
        "mapping": result["mapping"], "remote_writes": False,
    }))

if __name__ == "__main__":
    main()
