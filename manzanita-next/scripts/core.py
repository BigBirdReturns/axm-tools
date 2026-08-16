from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

USER_AGENT = "ManzanitaWorksSourceFoundation/0.1 (+https://bigbirdreturns.github.io/axm-tools/manzanita/)"
TIMEOUT = 45
RETRIES = 3
SENSITIVE_PARAMETER_NAMES = {"key", "api_key", "apikey", "access_token", "token", "map_key"}


@dataclass
class SourceSpec:
    source_id: str
    attribution: str
    license: str | None
    storage_policy: str
    claim_scope: str
    max_age_seconds: int | None


class Acquisition:
    def __init__(self, out_dir: Path, registry: dict[str, Any]) -> None:
        self.out_dir = out_dir
        self.payload_dir = out_dir / "payloads"
        self.receipt_dir = out_dir / "receipts"
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        self.receipt_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        self.registry = {entry["id"]: entry for entry in registry["sources"]}
        self.manifest: list[dict[str, Any]] = []
        self.secret_values = {
            value
            for name in (
                "AIRNOW_API_KEY",
                "FIRMS_MAP_KEY",
                "GOOGLE_MAPS_API_KEY",
                "MAPILLARY_ACCESS_TOKEN",
                "USGS_API_KEY",
            )
            if (value := os.getenv(name))
        }

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def spec(self, source_id: str) -> SourceSpec:
        entry = self.registry[source_id]
        return SourceSpec(
            source_id=source_id,
            attribution=entry.get("attribution", entry["name"]),
            license=entry.get("license"),
            storage_policy=entry["cache_policy"],
            claim_scope=entry["claim_scope"],
            max_age_seconds=entry.get("freshness_seconds"),
        )

    def redact_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        redacted = str(value)
        for secret in sorted(self.secret_values, key=len, reverse=True):
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted

    def redact_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "[REDACTED]" if key.lower() in SENSITIVE_PARAMETER_NAMES else self.redact_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.redact_value(item) for item in value]
        if isinstance(value, str):
            return self.redact_text(value)
        return value

    def sanitize_url(self, url: str) -> str:
        sanitized = self.redact_text(url) or url
        try:
            parsed = urlsplit(sanitized)
            query = []
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                if key.lower() in SENSITIVE_PARAMETER_NAMES:
                    value = "[REDACTED]"
                query.append((key, value))
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
        except ValueError:
            return sanitized

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, RETRIES + 1):
            try:
                response = self.session.request(method, url, timeout=TIMEOUT, **kwargs)
                if response.status_code >= 500 and attempt < RETRIES:
                    time.sleep(2 ** (attempt - 1))
                    continue
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt < RETRIES:
                    time.sleep(2 ** (attempt - 1))
                    continue
        assert last_error is not None
        raise last_error

    def record(
        self,
        source_id: str,
        status: str,
        method: str,
        url: str,
        payload: bytes | None,
        suffix: str,
        response: requests.Response | None = None,
        parameters: dict[str, Any] | None = None,
        error: str | None = None,
        source_time: str | None = None,
        media_type: str | None = None,
        body_sha256: str | None = None,
        attribution_override: str | None = None,
        license_override: str | None = None,
    ) -> dict[str, Any]:
        spec = self.spec(source_id)
        payload_path: str | None = None
        digest: str | None = None
        byte_count = 0
        if payload is not None:
            payload_path = f"payloads/{source_id}{suffix}"
            path = self.out_dir / payload_path
            path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            byte_count = len(payload)
        receipt = {
            "source_id": source_id,
            "retrieval_id": f"{source_id}-{uuid.uuid4().hex[:12]}",
            "retrieved_at": self.now(),
            "status": status,
            "request": {
                "method": method,
                "url": self.sanitize_url(url),
                "parameters": self.redact_value(parameters or {}),
                "body_sha256": body_sha256,
            },
            "response": {
                "http_status": response.status_code if response is not None else None,
                "content_type": response.headers.get("content-type") if response is not None else None,
                "etag": response.headers.get("etag") if response is not None else None,
                "last_modified": response.headers.get("last-modified") if response is not None else None,
            },
            "payload": {
                "path": payload_path,
                "bytes": byte_count,
                "sha256": digest,
                "media_type": media_type or (response.headers.get("content-type") if response is not None else None),
            },
            "rights": {
                "source_attribution": attribution_override or spec.attribution,
                "license": license_override if license_override is not None else spec.license,
                "storage_policy": spec.storage_policy,
            },
            "claim_scope": spec.claim_scope,
            "freshness": {"max_age_seconds": spec.max_age_seconds, "source_time": source_time},
            "error": self.redact_text(error),
        }
        (self.receipt_dir / f"{source_id}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        self.manifest.append(receipt)
        return receipt

    def fetch_json(self, source_id: str, url: str, params: dict[str, Any] | None = None, required: bool = False) -> Any:
        try:
            response = self.request("GET", url, params=params, headers={"Accept": "application/geo+json, application/json"})
            response.raise_for_status()
            data = response.json()
            self.record(source_id, "ok", "GET", response.url, json.dumps(data, indent=2).encode(), ".json", response, params, media_type="application/json")
            return data
        except Exception as exc:  # noqa: BLE001
            self.record(source_id, "failed", "GET", url, None, ".json", error=str(exc), parameters=params)
            if required:
                raise
            return None

    def fetch_binary(self, source_id: str, url: str, params: dict[str, Any], suffix: str, required: bool = False) -> bytes | None:
        try:
            response = self.request("GET", url, params=params)
            response.raise_for_status()
            payload = response.content
            if len(payload) < 1024:
                raise RuntimeError(f"binary payload unexpectedly small: {len(payload)} bytes")
            self.record(source_id, "ok", "GET", response.url, payload, suffix, response, params)
            return payload
        except Exception as exc:  # noqa: BLE001
            self.record(source_id, "failed", "GET", url, None, suffix, error=str(exc), parameters=params)
            if required:
                raise
            return None


def parse_rdb(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    if len(lines) < 3:
        return []
    headers = lines[0].split("\t")
    records = []
    for line in lines[2:]:
        values = line.split("\t")
        if len(values) == len(headers):
            records.append(dict(zip(headers, values)))
    return records
