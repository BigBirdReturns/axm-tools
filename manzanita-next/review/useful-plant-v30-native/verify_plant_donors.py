#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACT = HERE / "PLANT_DONOR_ADMISSION_CONTRACT.json"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any = None,
    expected: Any = None,
) -> None:
    checks.append(
        {
            "name": name,
            "pass": bool(passed),
            "observed": observed,
            "expected": expected,
        }
    )


def parse_length(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+)(?:px)?\s*", value)
    return int(match.group(1)) if match else None


def svg_checks(path: Path, expected: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8")
        add_check(checks, "origin SVG UTF-8", True, "valid", "valid")
    except UnicodeDecodeError as exc:
        add_check(checks, "origin SVG UTF-8", False, str(exc), "valid")
        return checks

    lowered = text.lower()
    forbidden_markup = [token for token in policy["forbidden_markup"] if token.lower() in lowered]
    add_check(checks, "origin SVG passive markup", not forbidden_markup, forbidden_markup, [])

    try:
        root = ET.fromstring(text)
        add_check(checks, "origin SVG XML parse", True, "valid", "valid")
    except ET.ParseError as exc:
        add_check(checks, "origin SVG XML parse", False, str(exc), "valid")
        return checks

    root_name = local_name(root.tag)
    add_check(checks, "origin SVG root", root_name == "svg", root_name, "svg")
    width = parse_length(root.attrib.get("width"))
    height = parse_length(root.attrib.get("height"))
    view_box = " ".join((root.attrib.get("viewBox") or "").split())
    add_check(checks, "origin SVG width", width == expected["width"], width, expected["width"])
    add_check(checks, "origin SVG height", height == expected["height"], height, expected["height"])
    add_check(checks, "origin SVG viewBox", view_box == expected["view_box"], view_box, expected["view_box"])

    forbidden_tags: list[str] = []
    event_attributes: list[str] = []
    external_references: list[dict[str, str]] = []
    forbidden_names = set(policy["forbidden_element_local_names"])
    for element in root.iter():
        name = local_name(element.tag)
        if name in forbidden_names:
            forbidden_tags.append(name)
        for raw_key, raw_value in element.attrib.items():
            key = local_name(raw_key)
            if key.lower().startswith(policy["forbidden_event_attribute_prefix"].lower()):
                event_attributes.append(f"{name}@{key}")
            if key in {"href", "src"}:
                value = raw_value.strip()
                if value and not value.startswith("#") and not value.startswith("data:"):
                    external_references.append({"element": name, "attribute": key, "value": value})
            if "url(" in raw_value.lower():
                for target in re.findall(r"url\(([^)]+)\)", raw_value, flags=re.IGNORECASE):
                    clean = target.strip(" \t\r\n\"'")
                    if clean and not clean.startswith("#") and not clean.startswith("data:"):
                        external_references.append({"element": name, "attribute": key, "value": clean})

    add_check(checks, "origin SVG forbidden elements absent", not forbidden_tags, forbidden_tags, [])
    add_check(checks, "origin SVG event handlers absent", not event_attributes, event_attributes, [])
    add_check(
        checks,
        "origin SVG external references absent",
        not external_references if policy["external_reference_allowed"] is False else True,
        external_references,
        [],
    )
    return checks


def webp_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 20 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        return None
    offset = 12
    while offset + 8 <= len(payload):
        kind = payload[offset : offset + 4]
        size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        start = offset + 8
        end = start + size
        if end > len(payload):
            return None
        chunk = payload[start:end]
        if kind == b"VP8X" and len(chunk) >= 10:
            width = 1 + int.from_bytes(chunk[4:7], "little")
            height = 1 + int.from_bytes(chunk[7:10], "little")
            return width, height
        if kind == b"VP8 " and len(chunk) >= 10 and chunk[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(chunk[6:8], "little") & 0x3FFF
            height = int.from_bytes(chunk[8:10], "little") & 0x3FFF
            return width, height
        if kind == b"VP8L" and len(chunk) >= 5 and chunk[0] == 0x2F:
            b1, b2, b3, b4 = chunk[1:5]
            width = 1 + (((b2 & 0x3F) << 8) | b1)
            height = 1 + (((b4 & 0x0F) << 10) | (b3 << 2) | (b2 >> 6))
            return width, height
        offset = end + (size & 1)
    return None


def webp_checks(path: Path, expected: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    payload = path.read_bytes()
    container = len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    add_check(checks, "cached WebP container", container, payload[:12].hex(), "RIFF....WEBP")
    declared_size = int.from_bytes(payload[4:8], "little") + 8 if len(payload) >= 8 else None
    add_check(checks, "cached WebP RIFF size", declared_size == len(payload), declared_size, len(payload))
    dimensions = webp_dimensions(payload)
    add_check(
        checks,
        "cached WebP dimensions",
        dimensions == (expected["width"], expected["height"]),
        dimensions,
        (expected["width"], expected["height"]),
    )
    return checks


def measurement(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256_path(path) if path.is_file() else None,
    }


def authority(contract: dict[str, Any]) -> dict[str, Any]:
    return dict(contract["authority"])


def hold_receipt(
    origin: Path,
    cached: Path,
    contract: dict[str, Any],
    state: str,
    holds: list[str],
) -> dict[str, Any]:
    return {
        "schema": "manzanita/exact-plant-donor-admission-receipt@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_id": contract["gate_id"],
        "candidate_id": contract["candidate_id"],
        "object_id": contract["object_id"],
        "result": state,
        "admission_state": "HOLD",
        "donors_admitted": False,
        "origin": measurement(origin),
        "cached": measurement(cached),
        "checks_passed": 1,
        "checks_total": 1,
        "checks": [
            {
                "name": "missing exact donor media fails closed",
                "pass": True,
                "observed": {
                    "origin": origin.is_file(),
                    "cached": cached.is_file(),
                },
                "expected": {"origin": True, "cached": True},
            }
        ],
        "blocking_holds": holds,
        "next_gate": None,
        **authority(contract),
    }


def evaluate(origin: Path, cached: Path, contract: dict[str, Any]) -> dict[str, Any]:
    origin_exists = origin.is_file()
    cached_exists = cached.is_file()
    if not origin_exists and not cached_exists:
        return hold_receipt(
            origin,
            cached,
            contract,
            "HOLD_EXACT_PLANT_DONORS_UNMOUNTED",
            [
                "exact Plant origin SVG not mounted",
                "exact cached Plant WebP not mounted",
                "inherited Household, Street, and Property rendered locks not executed",
                "operator visual acceptance absent",
            ],
        )
    if not origin_exists or not cached_exists:
        missing = []
        if not origin_exists:
            missing.append("exact Plant origin SVG not mounted")
        if not cached_exists:
            missing.append("exact cached Plant WebP not mounted")
        return hold_receipt(
            origin,
            cached,
            contract,
            "HOLD_EXACT_PLANT_DONORS_PARTIAL",
            missing + ["partial donor custody has no admission standing"],
        )

    checks: list[dict[str, Any]] = []
    expected_origin = contract["required_donors"]["origin"]
    expected_cached = contract["required_donors"]["cached"]

    for label, path, expected in (
        ("origin", origin, expected_origin),
        ("cached", cached, expected_cached),
    ):
        observed_bytes = path.stat().st_size
        observed_sha = sha256_path(path)
        add_check(checks, f"{label} filename", path.name == expected["filename"], path.name, expected["filename"])
        add_check(checks, f"{label} bytes", observed_bytes == expected["bytes"], observed_bytes, expected["bytes"])
        add_check(checks, f"{label} sha256", observed_sha == expected["sha256"], observed_sha, expected["sha256"])

    checks.extend(svg_checks(origin, expected_origin, contract["passive_svg_floor"]))
    checks.extend(webp_checks(cached, expected_cached))

    passed = sum(1 for item in checks if item["pass"])
    all_pass = bool(checks) and passed == len(checks)
    return {
        "schema": "manzanita/exact-plant-donor-admission-receipt@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_id": contract["gate_id"],
        "candidate_id": contract["candidate_id"],
        "object_id": contract["object_id"],
        "result": "PASS_EXACT_PLANT_DONORS_ADMITTED" if all_pass else "FAIL_PLANT_DONOR_ADMISSION",
        "admission_state": "ADMITTED" if all_pass else "FAIL",
        "donors_admitted": all_pass,
        "origin": measurement(origin),
        "cached": measurement(cached),
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "blocking_holds": [] if all_pass else ["one or more exact Plant donor admission checks failed"],
        "next_gate": contract["next_gate_after_pass"] if all_pass else None,
        **authority(contract),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed exact Plant media admission gate.")
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--cached", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expect-missing",
        action="store_true",
        help="Treat the governed both-missing HOLD as a successful enforcement result.",
    )
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    receipt = evaluate(args.origin, args.cached, contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if receipt["result"] == "PASS_EXACT_PLANT_DONORS_ADMITTED":
        return 0
    if receipt["result"] == "HOLD_EXACT_PLANT_DONORS_UNMOUNTED" and args.expect_missing:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
