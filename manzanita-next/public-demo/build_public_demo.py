#!/usr/bin/env python3
"""Build a self-contained public-safe Manzanita place demonstration.

The builder consumes the governed public place configuration, source registry,
source-foundation acquisition bundle, and Forkline Field constitution. It emits
only a bounded public projection, retained failure states, copied public-safe
media, deterministic file receipts, and no credential or private household data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - explicit workflow dependency
    raise SystemExit("Pillow is required to build the public demo media fallback") from exc

SCHEMA = "axm-tools/manzanita-public-demo-build@1"
DATA_SCHEMA = "axm-tools/manzanita-public-demo-data@1"
PROJECTION_SCHEMA = "axm-tools/manzanita-public-projection-receipt@1"
CONTRACT_SCHEMA = "axm-tools/manzanita-public-demo-contract@1"
CONSTITUTION_SCHEMA = "axm-tools/manzanita-design-constitution@1"
SOURCE_MANIFEST_SCHEMA = "manzanita-works/source-acquisition-manifest@1"

SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[1]
DEFAULT_CONTRACT = SCRIPT_ROOT / "PLACE_DEMO_CONTRACT.json"
DEFAULT_PLACE = REPO_ROOT / "manzanita-next" / "config" / "place-demo.json"
DEFAULT_REGISTRY = REPO_ROOT / "manzanita-next" / "config" / "source-registry.json"
DEFAULT_CONSTITUTION = REPO_ROOT / "manzanita-next" / "design-system" / "CONSTITUTION.json"
DEFAULT_TEMPLATE = SCRIPT_ROOT / "template"
DEFAULT_ACQUISITION = REPO_ROOT / "manzanita-next" / "out"
DEFAULT_OUTPUT = SCRIPT_ROOT / "out"

HIGH_CONFIDENCE_SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
}
PROHIBITED_PUBLIC_KEYS = {
    "address",
    "street_address",
    "mailing_address",
    "resident",
    "resident_name",
    "owner",
    "owner_name",
    "email",
    "phone",
    "account",
    "account_id",
    "token",
    "access_token",
    "api_key",
    "secret",
    "credential",
    "password",
}

VIEW_GEOMETRY = {
    "place": {
        "ground": "M45 530 C128 476 189 452 274 397 C365 338 438 297 528 272 C620 247 700 277 790 249 C884 219 951 153 1042 129 C1097 114 1142 118 1170 94",
        "register": "M92 575 C195 496 278 431 371 376 C469 319 565 296 659 269 C753 242 843 211 927 170 C1014 128 1091 111 1153 95",
        "overlay": "M170 526 C264 468 347 409 438 365 C523 324 608 299 695 290 C783 281 855 247 925 203 C983 167 1038 153 1084 166 C1068 235 1002 286 929 318 C841 357 751 364 661 395 C560 430 474 506 370 544 C292 572 218 561 170 526 Z",
        "label": "PUBLIC PLACE · SOURCE COVERAGE",
    },
    "weather": {
        "ground": "M30 551 C114 509 176 446 258 414 C353 377 421 309 513 279 C611 247 690 270 785 235 C884 199 957 132 1054 115 C1105 106 1143 113 1180 83",
        "register": "M78 581 C168 499 247 438 342 389 C438 340 536 315 628 278 C723 240 814 208 901 166 C994 121 1082 103 1158 88",
        "overlay": "M292 507 C320 404 383 330 465 280 C555 225 642 190 735 190 C826 190 904 230 942 296 C975 354 946 421 883 459 C809 505 719 501 629 516 C510 536 394 570 292 507 Z",
        "label": "WEATHER · TIME AND ALERT STATE",
    },
    "water": {
        "ground": "M34 571 C128 528 214 492 296 446 C388 395 467 346 557 309 C658 268 744 250 833 208 C929 163 1018 132 1105 124 C1140 120 1165 112 1186 98",
        "register": "M72 600 C164 547 254 502 341 450 C431 396 513 350 602 314 C694 276 771 233 852 190 C939 144 1025 126 1110 115",
        "overlay": "M82 577 C181 535 269 476 346 418 C430 355 511 324 594 294 C681 263 752 203 821 184 C884 166 938 192 948 238 C958 288 910 343 852 376 C783 415 701 427 625 467 C528 518 443 580 341 607 C243 633 139 624 82 577 Z",
        "label": "WATER · NEARBY MONITORING CONTEXT",
    },
    "fire": {
        "ground": "M20 566 C111 506 175 435 262 397 C352 357 416 287 506 242 C596 197 681 194 764 147 C852 97 932 59 1016 86 C1086 108 1135 94 1184 61",
        "register": "M66 590 C157 508 237 440 331 387 C428 332 523 300 616 258 C711 215 794 155 880 120 C970 84 1054 82 1142 66",
        "overlay": "M533 515 C566 410 631 329 714 274 C801 217 875 141 961 118 C1031 99 1094 113 1122 159 C1153 211 1124 279 1063 327 C994 382 909 404 829 442 C727 490 631 554 533 515 Z",
        "label": "FIRE · ATTENTION, NOT ADVERSE SCORING",
    },
}


class BuildError(ValueError):
    """Raised when the public projection contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
        raise BuildError(f"Cannot read valid JSON from {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    require(value not in {"", "."}, f"Invalid relative path: {value!r}")
    require(not path.is_absolute(), f"Absolute path is prohibited: {value}")
    require(".." not in path.parts, f"Path escapes its root: {value}")
    return path.as_posix()


def resolve_within(root: Path, value: str) -> Path:
    clean = clean_relative_path(value)
    candidate = (root / clean).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise BuildError(f"Path escapes acquisition root: {value}") from exc
    return candidate


def nested_values(value: Any, key: str) -> Iterable[Any]:
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                yield current_value
            yield from nested_values(current_value, key)
    elif isinstance(value, list):
        for item in value:
            yield from nested_values(item, key)


def first_string(value: dict[str, Any], keys: Iterable[str], fallback: str) -> str:
    for key in keys:
        for candidate in nested_values(value, key):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return fallback


def find_public_safe(value: Any) -> bool:
    for candidate in nested_values(value, "public_safe"):
        if candidate is True:
            return True
    for candidate in nested_values(value, "projection"):
        if isinstance(candidate, str) and candidate.lower() in {"public", "public_safe"}:
            return True
    return False


def find_coordinates(value: Any) -> tuple[float, float]:
    if isinstance(value, dict):
        latitude = None
        longitude = None
        for key in ("lat", "latitude"):
            candidate = value.get(key)
            if isinstance(candidate, (int, float)):
                latitude = float(candidate)
                break
        for key in ("lon", "lng", "longitude"):
            candidate = value.get(key)
            if isinstance(candidate, (int, float)):
                longitude = float(candidate)
                break
        if latitude is not None and longitude is not None:
            return latitude, longitude
        coordinates = value.get("coordinates")
        if (
            isinstance(coordinates, list)
            and len(coordinates) >= 2
            and all(isinstance(item, (int, float)) for item in coordinates[:2])
        ):
            first, second = float(coordinates[0]), float(coordinates[1])
            if abs(first) <= 90 and abs(second) <= 180:
                return first, second
            if abs(second) <= 90 and abs(first) <= 180:
                return second, first
        for candidate in value.values():
            try:
                return find_coordinates(candidate)
            except BuildError:
                pass
    elif isinstance(value, list):
        for candidate in value:
            try:
                return find_coordinates(candidate)
            except BuildError:
                pass
    raise BuildError("Public place configuration lacks recoverable coordinates")


def find_manifest(acquisition_root: Path) -> Path:
    direct = acquisition_root / "manifest.json"
    if direct.is_file():
        return direct
    candidates = sorted(acquisition_root.rglob("manifest.json"))
    require(bool(candidates), f"No source acquisition manifest exists under {acquisition_root}")
    return candidates[0]


def find_registry_sources(registry: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = registry.get("sources")
    if isinstance(candidates, list):
        return [row for row in candidates if isinstance(row, dict)]
    if isinstance(candidates, dict):
        rows = []
        for source_id, row in candidates.items():
            if isinstance(row, dict):
                rows.append({"id": source_id, **row})
        return rows
    for value in registry.values():
        if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
            if any("source_id" in row or "id" in row for row in value):
                return value
    return []


def receipt_source_id(receipt: dict[str, Any], fallback: str) -> str:
    for key in ("source_id", "id", "source"):
        value = receipt.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def load_receipts(acquisition_root: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    receipts_dir = acquisition_root / "receipts"
    candidates = sorted(receipts_dir.glob("*.json")) if receipts_dir.is_dir() else []
    if not candidates:
        candidates = [
            path
            for path in sorted(acquisition_root.rglob("*.json"))
            if path.parent.name == "receipts"
        ]
    for path in candidates:
        receipt = load_json(path)
        source_id = receipt_source_id(receipt, path.stem)
        receipt["_receipt_path"] = path.relative_to(acquisition_root).as_posix()
        rows[source_id] = receipt

    manifest_rows = manifest.get("receipts")
    if isinstance(manifest_rows, list):
        for index, row in enumerate(manifest_rows):
            if not isinstance(row, dict):
                continue
            source_id = receipt_source_id(row, f"manifest-source-{index:02d}")
            rows.setdefault(source_id, row)
    return rows


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def source_state(receipt: dict[str, Any], reference_time: datetime | None) -> str:
    raw = str(receipt.get("status", "unknown")).strip().lower()
    aliases = {
        "success": "ok",
        "passed": "ok",
        "no_coverage": "empty",
        "skipped": "unavailable",
        "skipped_missing_key": "skipped_missing_credential",
        "missing_credential": "skipped_missing_credential",
        "error": "unavailable",
        "failed": "unavailable",
        "degraded": "unavailable",
    }
    state = aliases.get(raw, raw)
    error = str(receipt.get("error", "")).lower()
    http_status = receipt.get("http_status")
    if http_status == 429 or "rate limit" in error or "quota" in error:
        state = "rate_limited"
    elif any(term in error for term in ("terms", "license", "redistribution")):
        state = "terms_blocked"
    allowed = {
        "ok",
        "empty",
        "stale",
        "skipped_missing_credential",
        "rate_limited",
        "unavailable",
        "terms_blocked",
        "unknown",
    }
    if state not in allowed:
        state = "unknown"

    source_time = parse_time(receipt.get("source_time"))
    max_age = receipt.get("max_age_seconds")
    if (
        state == "ok"
        and source_time is not None
        and reference_time is not None
        and isinstance(max_age, (int, float))
        and max_age >= 0
        and (reference_time - source_time).total_seconds() > float(max_age)
    ):
        return "stale"
    return state


def request_host(receipt: dict[str, Any]) -> str | None:
    value = receipt.get("request_url")
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    return parsed.hostname


def public_source_row(
    source_id: str,
    receipt: dict[str, Any] | None,
    registry_row: dict[str, Any] | None,
    reference_time: datetime | None,
) -> dict[str, Any]:
    receipt = receipt or {}
    registry_row = registry_row or {}
    state = source_state(receipt, reference_time) if receipt else "unknown"
    attribution = (
        receipt.get("source_attribution")
        or registry_row.get("attribution")
        or registry_row.get("source_attribution")
        or source_id.replace("_", " ").upper()
    )
    rights = (
        receipt.get("license")
        or registry_row.get("license")
        or registry_row.get("rights")
        or "Rights not present in retained public receipt"
    )
    claim_scope = (
        receipt.get("claim_scope")
        or registry_row.get("claim_scope")
        or "Source scope requires review before a substantive claim"
    )
    raw_error = receipt.get("error") if state != "ok" else None
    public_errors = {
        "empty": "The provider returned no qualifying item or coverage for this request.",
        "stale": "The retained source exceeds its admitted freshness window.",
        "skipped_missing_credential": "An approved provider credential is not configured; the request was not attempted.",
        "rate_limited": "The provider deferred or refused the request under a rate or quota limit.",
        "unavailable": "The provider, network, transform, or required artifact was unavailable.",
        "terms_blocked": "Provider rights or redistribution terms prohibit inclusion in this public artifact.",
        "unknown": "The retained receipt does not support a more specific public failure classification.",
    }
    error = public_errors.get(state) if state != "ok" else None
    if raw_error and state == "unknown":
        error = public_errors["unknown"]
    return {
        "id": source_id,
        "label": str(registry_row.get("label") or registry_row.get("name") or source_id.replace("_", " ").title()),
        "state": state,
        "source_time": receipt.get("source_time"),
        "retrieved_at": receipt.get("retrieved_at"),
        "max_age_seconds": receipt.get("max_age_seconds"),
        "http_status": receipt.get("http_status"),
        "payload_bytes": receipt.get("payload_bytes", 0),
        "payload_sha256": receipt.get("payload_sha256"),
        "attribution": str(attribution),
        "rights": str(rights),
        "storage_policy": str(receipt.get("storage_policy") or registry_row.get("storage_policy") or "Retain public metadata only until reviewed"),
        "claim_scope": str(claim_scope),
        "request_host": request_host(receipt),
        "error": error,
        "receipt_path": receipt.get("_receipt_path"),
    }


def receipt_payload_path(acquisition_root: Path, receipt: dict[str, Any]) -> Path | None:
    value = receipt.get("payload_path")
    if not isinstance(value, str) or not value:
        return None
    try:
        path = resolve_within(acquisition_root, value)
    except BuildError:
        return None
    return path if path.is_file() else None


def load_payload(acquisition_root: Path, receipt: dict[str, Any] | None) -> Any:
    if not receipt:
        return None
    path = receipt_payload_path(acquisition_root, receipt)
    if path is None:
        return None
    if path.suffix.lower() in {".json", ".geojson"}:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
    return None


def count_records(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0
    for key in ("features", "elements", "records", "sites", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    value = payload.get("value")
    if isinstance(value, dict):
        time_series = value.get("timeSeries")
        if isinstance(time_series, list):
            return len(time_series)
    properties = payload.get("properties")
    if isinstance(properties, dict):
        periods = properties.get("periods")
        if isinstance(periods, list):
            return len(periods)
    return 0


def safe_get(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def celsius_to_fahrenheit(value: Any) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    return round(float(value) * 9 / 5 + 32)


def weather_summary(payloads: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    observation = payloads.get("nws_observation")
    observation_props = safe_get(observation, "properties") or {}
    forecast = payloads.get("nws_forecast")
    forecast_periods = safe_get(forecast, "properties", "periods") or []
    first_period = forecast_periods[0] if isinstance(forecast_periods, list) and forecast_periods else {}
    alerts = payloads.get("nws_alerts")
    alert_features = alerts.get("features", []) if isinstance(alerts, dict) else []
    active_titles = []
    for feature in alert_features[:5] if isinstance(alert_features, list) else []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties", {})
        title = props.get("headline") or props.get("event")
        if isinstance(title, str) and title:
            active_titles.append(title)

    temperature_f = celsius_to_fahrenheit(safe_get(observation_props, "temperature", "value"))
    description = observation_props.get("textDescription") if isinstance(observation_props, dict) else None
    if not isinstance(description, str) or not description:
        description = "Observation description unavailable"
    forecast_name = first_period.get("name") if isinstance(first_period, dict) else None
    forecast_text = (
        first_period.get("detailedForecast")
        or first_period.get("shortForecast")
        if isinstance(first_period, dict)
        else None
    )
    forecast_temperature = first_period.get("temperature") if isinstance(first_period, dict) else None
    forecast_unit = first_period.get("temperatureUnit") if isinstance(first_period, dict) else None

    metrics = [
        {
            "label": "Observation",
            "value": f"{temperature_f} °F" if temperature_f is not None else "Unavailable",
            "detail": description,
        },
        {
            "label": "Forecast",
            "value": str(forecast_name or "Unavailable"),
            "detail": (
                f"{forecast_temperature} °{forecast_unit} · {forecast_text}"
                if forecast_temperature is not None and forecast_unit and forecast_text
                else str(forecast_text or "No admitted forecast period")
            ),
        },
        {
            "label": "Active alerts",
            "value": str(len(alert_features) if isinstance(alert_features, list) else 0),
            "detail": "; ".join(active_titles) if active_titles else "No alert headline returned in the retained response",
        },
    ]
    return {
        "headline": "Official weather context with time and alert boundaries",
        "reading": "Observation, forecast, hourly, station, and alert sources remain separate. No single row is presented as a safety guarantee at the demonstration point.",
        "metrics": metrics,
        "source_ids": [
            source_id
            for source_id in (
                "nws_points",
                "nws_forecast",
                "nws_forecast_hourly",
                "nws_stations",
                "nws_observation",
                "nws_alerts",
                "airnow",
            )
            if source_id in sources
        ],
    }


def place_summary(payloads: dict[str, Any], sources: dict[str, dict[str, Any]], media: dict[str, Any]) -> dict[str, Any]:
    osm_count = count_records(payloads.get("osm_overpass"))
    street_states = [
        sources[source_id]["state"]
        for source_id in (
            "google_street_view",
            "mapillary",
            "kartaview",
            "panoramax",
        )
        if source_id in sources
    ]
    available_street = sum(state == "ok" for state in street_states)
    metrics = [
        {
            "label": "Public map features",
            "value": str(osm_count),
            "detail": "OpenStreetMap features returned in the configured public demonstration extent",
        },
        {
            "label": "Base imagery",
            "value": "Available" if media["base_state"] == "ok" else "Unavailable",
            "detail": media["base_label"],
        },
        {
            "label": "Street imagery providers",
            "value": f"{available_street} available",
            "detail": "Missing credential and empty coverage remain visible rather than being filled with generated streets",
        },
    ]
    return {
        "headline": "One public place identity with bounded source coverage",
        "reading": "Public imagery, terrain, community geometry, and street coverage are presented as separate sources. Authored Forkline marks explain registration but do not become map evidence.",
        "metrics": metrics,
        "source_ids": [
            source_id
            for source_id in (
                "usgs_imagery",
                "usgs_3dep_hillshade",
                "osm_overpass",
                "kartaview_coverage",
                "kartaview",
                "panoramax",
                "google_street_view",
                "mapillary",
            )
            if source_id in sources
        ],
    }


def water_summary(payloads: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sites = count_records(payloads.get("usgs_water_sites"))
    series = count_records(payloads.get("usgs_water_iv"))
    metrics = [
        {
            "label": "Returned monitoring sites",
            "value": str(sites),
            "detail": "Public monitoring-location records in the configured regional query, not measurements at the demonstration point",
        },
        {
            "label": "Returned value series",
            "value": str(series),
            "detail": "Named USGS time series whose site, parameter, qualifier, and time require source review",
        },
        {
            "label": "Household inference",
            "value": "Prohibited",
            "detail": "No potable-water, irrigation, pot moisture, drainage, or household condition follows from nearby monitoring data",
        },
    ]
    return {
        "headline": "Nearby monitoring context without household inference",
        "reading": "USGS site availability and instantaneous values remain tied to their named monitoring locations. Distance and public availability do not transfer the measurement to this place.",
        "metrics": metrics,
        "source_ids": [
            source_id
            for source_id in ("usgs_water_sites", "usgs_water_iv")
            if source_id in sources
        ],
    }


def fire_summary(payloads: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    perimeters = count_records(payloads.get("calfire_incidents"))
    normalized = count_records(payloads.get("calfire_incidents_normalized"))
    firms_state = sources.get("firms", {}).get("state", "unknown")
    metrics = [
        {
            "label": "Returned active perimeter features",
            "value": str(perimeters),
            "detail": "CAL FIRE/NIFC/FIRIS public-view features in the provider response, not a local threat count",
        },
        {
            "label": "Normalized features",
            "value": str(normalized),
            "detail": "Machine-readable derived features that retain provider identities and do not invent containment, evacuation, or loss state",
        },
        {
            "label": "FIRMS thermal detections",
            "value": firms_state.replace("_", " ").title(),
            "detail": "Satellite thermal detection source state; thermal detection is not a confirmed incident perimeter or parcel determination",
        },
    ]
    return {
        "headline": "Fire attention routes to verification and assistance",
        "reading": "Incident perimeters, normalized features, and satellite thermal detections remain separate. The dossier cannot produce an insurance, evacuation, enforcement, damage, or parcel-risk decision.",
        "metrics": metrics,
        "source_ids": [
            source_id
            for source_id in ("calfire_incidents", "calfire_incidents_normalized", "firms")
            if source_id in sources
        ],
    }


def create_placeholder(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 1000), "#d8d2c4")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for index in range(-500, 2000, 80):
        draw.line((index, 1000, index + 700, 0), fill="#aaa394", width=2)
    draw.rectangle((60, 60, 1540, 940), outline="#171a16", width=5)
    draw.rectangle((90, 90, 1510, 910), outline="#9f3f2f", width=3)
    draw.text((120, 120), "SOURCE IMAGE UNAVAILABLE", fill="#171a16", font=font)
    draw.text((120, 155), label, fill="#555b50", font=font)
    draw.text((120, 190), "Authored fallback plate. No observation claim.", fill="#7d2431", font=font)
    image.save(path, format="PNG")


def copy_public_media(
    acquisition_root: Path,
    receipts: dict[str, dict[str, Any]],
    site_root: Path,
) -> dict[str, Any]:
    assets = site_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    base_output = assets / "base-imagery.png"
    hillshade_output = assets / "hillshade.png"

    base_receipt = receipts.get("usgs_imagery", {})
    base_source = receipt_payload_path(acquisition_root, base_receipt)
    if base_source and base_source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        shutil.copyfile(base_source, base_output)
        base_state = "ok"
        base_label = "USGS The National Map public imagery projection"
        base_source_sha = sha256_file(base_source)
    else:
        create_placeholder(base_output, "USGS imagery payload was not admitted to this build")
        base_state = "unavailable"
        base_label = "Authored fallback because public base imagery is unavailable"
        base_source_sha = None

    hillshade_receipt = receipts.get("usgs_3dep_hillshade", {})
    hillshade_source = receipt_payload_path(acquisition_root, hillshade_receipt)
    if hillshade_source and hillshade_source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        shutil.copyfile(hillshade_source, hillshade_output)
        hillshade_state = "ok"
        hillshade_label = "USGS 3DEP hillshade public projection"
        hillshade_source_sha = sha256_file(hillshade_source)
    else:
        create_placeholder(hillshade_output, "USGS hillshade payload was not admitted to this build")
        hillshade_state = "unavailable"
        hillshade_label = "Authored fallback because public hillshade is unavailable"
        hillshade_source_sha = None

    return {
        "base_path": "assets/base-imagery.png",
        "base_state": base_state,
        "base_label": base_label,
        "base_source_sha256": base_source_sha,
        "base_output_sha256": sha256_file(base_output),
        "hillshade_path": "assets/hillshade.png",
        "hillshade_state": hillshade_state,
        "hillshade_label": hillshade_label,
        "hillshade_source_sha256": hillshade_source_sha,
        "hillshade_output_sha256": sha256_file(hillshade_output),
        "claim_boundary": "Public provider imagery when admitted; otherwise an explicitly authored unavailable-source plate. No survey, street, private, or current-condition claim.",
    }


def generate_tokens_css(constitution: dict[str, Any]) -> str:
    token_rows = constitution.get("materials", {}).get("semantic_tokens", [])
    require(isinstance(token_rows, list) and token_rows, "Design constitution has no semantic materials")
    light_lines = []
    dark_lines = []
    for row in token_rows:
        require(isinstance(row, dict), "Semantic material row must be an object")
        token_id = row.get("id")
        light = row.get("light")
        dark = row.get("dark")
        require(isinstance(token_id, str) and re.fullmatch(r"[a-z_]+", token_id), f"Invalid material id: {token_id}")
        require(isinstance(light, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", light), f"Invalid light token: {token_id}")
        require(isinstance(dark, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", dark), f"Invalid dark token: {token_id}")
        css_name = token_id.replace("_", "-")
        light_lines.append(f"  --{css_name}: {light};")
        dark_lines.append(f"  --{css_name}: {dark};")
    return (
        ":root {\n"
        + "\n".join(light_lines)
        + "\n}\n\nhtml[data-resolved-theme=\"dark\"] {\n"
        + "\n".join(dark_lines)
        + "\n}\n"
    )


def recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(recursive_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def secret_scan(paths: Iterable[Path]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    scanned: list[str] = []
    for path in sorted(paths):
        if not path.is_file() or path.suffix.lower() not in {".json", ".js", ".html", ".css", ".md", ".txt"}:
            continue
        payload = path.read_text(encoding="utf-8", errors="replace")
        scanned.append(path.name)
        for pattern_id, pattern in HIGH_CONFIDENCE_SECRET_PATTERNS.items():
            if pattern.search(payload):
                findings.append({"path": path.name, "pattern": pattern_id})
    return {
        "result": "PASS" if not findings else "FAIL",
        "files_scanned": len(scanned),
        "high_confidence_findings": findings,
        "patterns": sorted(HIGH_CONFIDENCE_SECRET_PATTERNS),
        "claim_boundary": "Bounded pattern scan for common credential forms; not proof that all semantically sensitive content is absent.",
    }


def output_manifest(site_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(site_root.rglob("*")):
        if not path.is_file():
            continue
        rows.append(
            {
                "path": path.relative_to(site_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def build(
    repo_root: Path,
    contract_path: Path,
    place_path: Path,
    registry_path: Path,
    constitution_path: Path,
    template_root: Path,
    acquisition_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    acquisition_root = acquisition_root.resolve()
    output_root = output_root.resolve()
    site_root = output_root / "site"
    if output_root.exists():
        shutil.rmtree(output_root)
    site_root.mkdir(parents=True, exist_ok=True)

    contract = load_json(contract_path)
    place_config = load_json(place_path)
    registry = load_json(registry_path)
    constitution = load_json(constitution_path)
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected public-demo contract schema")
    require(constitution.get("schema") == CONSTITUTION_SCHEMA, "Forkline design constitution is not admitted to this branch")
    require(contract.get("object", {}).get("public_effect") == "none", "Build contract requests a public effect")
    require(contract.get("object", {}).get("constitutional_count_effect") == "none", "Build contract requests a constitutional count effect")
    require(find_public_safe(place_config), "Place configuration is not explicitly public-safe")

    latitude, longitude = find_coordinates(place_config)
    precision = int(contract.get("projection", {}).get("coordinate_precision_decimals", 4))
    require(0 <= precision <= 5, "Public coordinate precision is outside the admitted range")
    place_id = first_string(place_config, ("place_id", "id"), "mw-public-demo-unknown")
    place_label = first_string(
        place_config,
        ("public_label", "display_name", "name", "label"),
        "Public Manzanita demonstration place",
    )

    manifest_path = find_manifest(acquisition_root)
    manifest = load_json(manifest_path)
    manifest_schema = manifest.get("schema")
    require(
        manifest_schema in {SOURCE_MANIFEST_SCHEMA, None} or str(manifest_schema).startswith("manzanita-works/"),
        f"Unexpected acquisition manifest schema: {manifest_schema!r}",
    )
    reference_time = (
        parse_time(manifest.get("generated_at"))
        or parse_time(manifest.get("completed_at"))
        or parse_time(manifest.get("retrieved_at"))
    )
    receipts = load_receipts(acquisition_root, manifest)
    registry_rows = find_registry_sources(registry)
    registry_by_id = {
        str(row.get("source_id") or row.get("id")): row
        for row in registry_rows
        if row.get("source_id") or row.get("id")
    }
    ordered_ids = list(registry_by_id)
    for source_id in receipts:
        if source_id not in ordered_ids:
            ordered_ids.append(source_id)
    source_rows = [
        public_source_row(
            source_id,
            receipts.get(source_id),
            registry_by_id.get(source_id),
            reference_time,
        )
        for source_id in ordered_ids
    ]
    sources = {row["id"]: row for row in source_rows}
    payloads = {
        source_id: load_payload(acquisition_root, receipt)
        for source_id, receipt in receipts.items()
    }

    for source_id in (
        "usgs_imagery",
        "usgs_3dep_hillshade",
        "osm_overpass",
        "nws_points",
        "nws_forecast",
        "nws_forecast_hourly",
        "nws_stations",
        "nws_observation",
        "nws_alerts",
        "usgs_water_sites",
        "usgs_water_iv",
        "calfire_incidents",
        "calfire_incidents_normalized",
        "firms",
    ):
        sources.setdefault(
            source_id,
            public_source_row(source_id, receipts.get(source_id), registry_by_id.get(source_id), reference_time),
        )

    media = copy_public_media(acquisition_root, receipts, site_root)
    contract_views = {row["id"]: row for row in contract.get("views", []) if isinstance(row, dict)}
    summaries = {
        "place": place_summary(payloads, sources, media),
        "weather": weather_summary(payloads, sources),
        "water": water_summary(payloads, sources),
        "fire": fire_summary(payloads, sources),
    }
    views: dict[str, dict[str, Any]] = {}
    for view_id in ("place", "weather", "water", "fire"):
        contract_view = contract_views[view_id]
        summary = summaries[view_id]
        views[view_id] = {
            "id": view_id,
            "title": view_id.title(),
            "object": contract_view["object"],
            "headline": summary["headline"],
            "reading": summary["reading"],
            "metrics": summary["metrics"],
            "source_ids": summary["source_ids"],
            "safe_action": contract_view["safe_action"],
            "authority": contract_view["authority"],
            "prohibited_consequence": contract_view["prohibited_consequence"],
            "geometry": VIEW_GEOMETRY[view_id],
        }

    actor_rows = {row["id"]: row for row in contract.get("actors", []) if isinstance(row, dict)}
    failure_rows = [row for row in source_rows if row["state"] != "ok"]
    status_counts = Counter(row["state"] for row in source_rows)
    run_id = str(
        manifest.get("run_id")
        or manifest.get("retrieval_id")
        or manifest.get("id")
        or sha256_file(manifest_path)[:16]
    )
    generated_at = (
        manifest.get("generated_at")
        or manifest.get("completed_at")
        or manifest.get("retrieved_at")
        or "source-time-unavailable"
    )

    data: dict[str, Any] = {
        "schema": DATA_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "build_id": f"{place_id}-{run_id}",
        "source_run_id": run_id,
        "source_manifest_sha256": sha256_file(manifest_path),
        "generated_at": generated_at,
        "source_reference_time": reference_time.isoformat().replace("+00:00", "Z") if reference_time else None,
        "place": {
            "id": place_id,
            "label": place_label,
            "latitude": round(latitude, precision),
            "longitude": round(longitude, precision),
            "coordinate_precision_decimals": precision,
            "public_safe": True,
            "projection": "public_safe",
        },
        "views": views,
        "actors": actor_rows,
        "sources": source_rows,
        "source_state_counts": dict(sorted(status_counts.items())),
        "failures": failure_rows,
        "media": media,
        "themes": ["auto", "light", "dark"],
        "default_view": "place",
        "default_actor": "visitor",
        "adverse_action_boundary": contract["adverse_action_boundary"],
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }

    prohibited_keys = recursive_keys(data) & PROHIBITED_PUBLIC_KEYS
    require(not prohibited_keys, f"Public projection contains prohibited keys: {sorted(prohibited_keys)}")

    for file_name in ("index.html", "style.css", "app.js"):
        source = template_root / file_name
        require(source.is_file(), f"Public demo template is missing {file_name}")
        shutil.copyfile(source, site_root / file_name)
    (site_root / "tokens.css").write_text(generate_tokens_css(constitution), encoding="utf-8")
    (site_root / "demo-data.js").write_text(
        "window.__MANZANITA_PUBLIC_DEMO__ = Object.freeze("
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + ");\n",
        encoding="utf-8",
    )
    write_json(output_root / "PUBLIC_DATA.json", data)

    scan_paths = list(site_root.rglob("*")) + [output_root / "PUBLIC_DATA.json"]
    scan = secret_scan(scan_paths)
    require(scan["result"] == "PASS", f"High-confidence secret findings: {scan['high_confidence_findings']}")
    projection_receipt: dict[str, Any] = {
        "schema": PROJECTION_SCHEMA,
        "result": "PASS",
        "contract_id": contract["contract_id"],
        "place_id": place_id,
        "public_safe_config": True,
        "coordinate_precision_decimals": precision,
        "source_run_id": run_id,
        "source_manifest_sha256": sha256_file(manifest_path),
        "source_count": len(source_rows),
        "source_state_counts": dict(sorted(status_counts.items())),
        "failure_count": len(failure_rows),
        "prohibited_public_keys": sorted(PROHIBITED_PUBLIC_KEYS),
        "prohibited_keys_found": [],
        "secret_scan": scan,
        "media": media,
        "omitted_classes": contract["projection"]["prohibited_fields"],
        "claim_boundary": contract["object"]["claim_boundary"],
        "adverse_action_boundary": contract["adverse_action_boundary"],
    }
    projection_receipt["payload_sha256"] = sha256_bytes(canonical_bytes(projection_receipt))
    write_json(output_root / "PUBLIC_PROJECTION_RECEIPT.json", projection_receipt)

    manifest_rows = output_manifest(site_root)
    build_receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "result": "PASS",
        "contract": {
            "path": contract_path.relative_to(repo_root).as_posix(),
            "sha256": sha256_file(contract_path),
        },
        "place_config": {
            "path": place_path.relative_to(repo_root).as_posix(),
            "sha256": sha256_file(place_path),
            "public_safe": True,
        },
        "source_registry": {
            "path": registry_path.relative_to(repo_root).as_posix(),
            "sha256": sha256_file(registry_path),
        },
        "design_constitution": {
            "path": constitution_path.relative_to(repo_root).as_posix(),
            "version": constitution["version"],
            "sha256": sha256_file(constitution_path),
        },
        "source_acquisition": {
            "manifest_path": manifest_path.relative_to(acquisition_root).as_posix(),
            "manifest_schema": manifest_schema,
            "manifest_sha256": sha256_file(manifest_path),
            "run_id": run_id,
            "reference_time": data["source_reference_time"],
        },
        "public_projection_receipt": {
            "path": "PUBLIC_PROJECTION_RECEIPT.json",
            "sha256": sha256_file(output_root / "PUBLIC_PROJECTION_RECEIPT.json"),
            "payload_sha256": projection_receipt["payload_sha256"],
        },
        "public_data": {
            "path": "PUBLIC_DATA.json",
            "sha256": sha256_file(output_root / "PUBLIC_DATA.json"),
        },
        "site_manifest": manifest_rows,
        "site_manifest_sha256": sha256_bytes(canonical_bytes(manifest_rows)),
        "release_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    build_receipt["payload_sha256"] = sha256_bytes(canonical_bytes(build_receipt))
    write_json(output_root / "BUILD_RECEIPT.json", build_receipt)
    return build_receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--place", type=Path, default=DEFAULT_PLACE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--constitution", type=Path, default=DEFAULT_CONSTITUTION)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        args.repo_root,
        args.contract.resolve(),
        args.place.resolve(),
        args.registry.resolve(),
        args.constitution.resolve(),
        args.template.resolve(),
        args.acquisition_root.resolve(),
        args.output.resolve(),
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "source_run_id": receipt["source_acquisition"]["run_id"],
                "site_files": len(receipt["site_manifest"]),
                "site_manifest_sha256": receipt["site_manifest_sha256"],
                "projection_receipt_sha256": receipt["public_projection_receipt"]["sha256"],
                "release_effect": receipt["release_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BuildError as exc:
        raise SystemExit(str(exc)) from exc
