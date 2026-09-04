#!/usr/bin/env python3
"""Deterministic local validator for a returned Linux host observation.

Standard library only, and deliberately free of any import from this
repository: the seed must validate a returned observation on a host that has no
clone of it. ``canonical_bytes`` is therefore inlined here and must stay
byte-identical to the collector's and the qualifier's definition, or the
observation digest will not recompute.

The validator reads; it never creates, moves, or deletes anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "axm-community-lab/host-observation@2"
COLLECTOR_SCHEMA = "axm-community-lab/host-observation-collector@1"
RECEIPT_SCHEMA = "axm-community-lab/host-observation-receipt@1"
HOST_FINGERPRINT_SCHEMA = "axm-community-lab/observed-host-fingerprint@1"
# The only observation-body values a body-free receipt may repeat. Everything
# else in the body is host-descriptive, and a receipt that carries it is no
# longer publishable in the open.
RECEIPT_JOIN_COORDINATES = ("schema", "platform", "host_id", "observed_at", "observation_sha256")
RECEIPT_REQUIRED = (
    "schema",
    "observation_schema",
    "collector_schema",
    "platform",
    "host_id",
    "observed_at",
    "observation_sha256",
    "observation_file_name",
    "observation_file_sha256",
    "observation_file_bytes",
    "host_fingerprint_sha256",
    "accelerator_identity_sha256",
    "accelerator_identity_count",
    "collector_source_sha256",
    "python_executable_sha256",
    "seed_id",
    "seed_manifest_sha256",
    "carries_observation_body",
    "claim_boundary",
    "receipt_sha256",
)
REQUIRED_RUNTIME = ("python", "git", "ollama", "docker", "wsl", "nvidia-smi")
WSL_INAPPLICABLE_REASON = "not applicable on a native Linux host"
PROHIBITED_FIELD_MARKERS = (
    "serial",
    "machine_guid",
    "machine-id",
    "mac_address",
    "ip_address",
    "credential",
    "private_key",
    "tailscale",
    "token",
)
REQUIRED_TOP_LEVEL = (
    "schema",
    "observed_at",
    "platform",
    "host_id",
    "collector",
    "system",
    "cpu",
    "memory",
    "storage",
    "graphics",
    "network",
    "runtime",
    "clock",
    "surfaces",
    "observation_sha256",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    """Digest exact file bytes. Never a text-mode read: line endings count."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def retains_value(value: Any) -> bool:
    """True when a prohibited-marker field actually carries an identifier.

    An explicit refusal (``"serial_numbers_collected": false``) is compliance,
    not retention.
    """
    if value is None or value is False:
        return False
    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        return bool(value)
    return True


def collect_private_fields(payload: Any, path: str = "observation") -> list[str]:
    failures: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            label = f"{path}.{key}"
            lower = str(key).lower()
            if any(marker in lower for marker in PROHIBITED_FIELD_MARKERS) and retains_value(value):
                failures.append(f"prohibited private field retained: {label}")
            failures.extend(collect_private_fields(value, path=label))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            failures.extend(collect_private_fields(item, path=f"{path}[{index}]"))
    return failures


def validate_runtime(runtime: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(runtime, list):
        return ["runtime inventory missing"]
    names: list[str] = []
    for index, row in enumerate(runtime):
        if not isinstance(row, dict):
            failures.append(f"runtime[{index}] is not an object")
            continue
        name = str(row.get("name") or "").strip()
        names.append(name)
        present = row.get("present")
        if present is True:
            if row.get("disabled") is not False or not row.get("path") or row.get("disabled_reason"):
                failures.append(f"runtime row contradictory: {name}")
        elif present is False:
            if row.get("disabled") is not True or row.get("path") is not None or not row.get("disabled_reason"):
                failures.append(f"runtime row contradictory: {name}")
        else:
            failures.append(f"runtime row present must be boolean: {name}")
        if name == "wsl":
            if row.get("present") is not False or row.get("disabled") is not True:
                failures.append("wsl must be explicitly absent and disabled on a native Linux host")
            if str(row.get("disabled_reason") or "").strip() != WSL_INAPPLICABLE_REASON:
                failures.append(f'wsl disabled_reason must be "{WSL_INAPPLICABLE_REASON}"')
    if sorted(names) != sorted(REQUIRED_RUNTIME):
        failures.append(f"runtime denominator mismatch: {sorted(names)}")
    return failures


def validate_collector(collector: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(collector, dict):
        return ["collector identity missing"]
    if collector.get("schema") != COLLECTOR_SCHEMA:
        failures.append("collector schema mismatch")
    if str(collector.get("platform") or "").lower() != "linux":
        failures.append("collector platform is not linux")
    source_sha256 = str(collector.get("source_sha256") or "").lower()
    if len(source_sha256) != 64:
        failures.append("collector source digest missing")
    source_path = Path(str(collector.get("source_path") or ""))
    if str(source_path) and source_path.is_file():
        if sha256_file(source_path) != source_sha256:
            failures.append("collector source digest mismatch")
    python_identity = collector.get("python_executable")
    if not isinstance(python_identity, dict):
        failures.append("collector python identity missing")
        return failures
    executable = Path(str(python_identity.get("path") or ""))
    executable_sha = str(python_identity.get("sha256") or "").lower()
    if len(executable_sha) != 64:
        failures.append("collector python executable digest missing")
    if str(executable) and executable.is_file() and sha256_file(executable) != executable_sha:
        failures.append("collector python executable digest mismatch")
    return failures


def fingerprint_component(value: Any) -> str:
    if value is None or value is True or value is False:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value if item is not None)
    return " ".join(str(value).split()).strip().lower()


def fingerprint_joined(*values: Any) -> str:
    return "|".join(fingerprint_component(value) for value in values)


def accelerator_identities(observation: Any) -> list[str]:
    """Globally unique accelerator identifiers, NVIDIA UUIDs included."""
    graphics = observation.get("graphics") if isinstance(observation, dict) else None
    graphics = graphics if isinstance(graphics, dict) else {}
    nvidia = graphics.get("nvidia") if isinstance(graphics.get("nvidia"), list) else []
    adapters = graphics.get("adapters") if isinstance(graphics.get("adapters"), list) else []
    identities: list[str] = []
    for row in list(nvidia) + list(adapters):
        if not isinstance(row, dict):
            continue
        identity = fingerprint_component(row.get("uuid"))
        if identity:
            identities.append(identity)
    return sorted(set(identities))


def host_fingerprint_components(observation: Any) -> dict:
    """Body-safe physical identity of the observed machine.

    Inlined here for the same reason canonical_bytes is, and it must stay
    byte-identical to the collector's and the qualifier's definition: three
    labels are not three machines, and the fingerprint is what tells them
    apart. host_id, observed_at, the clock samples, and the collector and
    runtime rows are excluded on purpose -- those are what an operator edits
    when relabelling one machine as three.
    """
    observation = observation if isinstance(observation, dict) else {}
    system = observation.get("system") if isinstance(observation.get("system"), dict) else {}
    firmware = system.get("firmware") if isinstance(system.get("firmware"), dict) else {}
    memory = observation.get("memory") if isinstance(observation.get("memory"), dict) else {}
    storage = observation.get("storage") if isinstance(observation.get("storage"), dict) else {}
    graphics = observation.get("graphics") if isinstance(observation.get("graphics"), dict) else {}
    cpu_rows = observation.get("cpu") if isinstance(observation.get("cpu"), list) else []
    disks = storage.get("physical_disks") if isinstance(storage.get("physical_disks"), list) else []
    adapters = graphics.get("adapters") if isinstance(graphics.get("adapters"), list) else []
    return {
        "schema": HOST_FINGERPRINT_SCHEMA,
        "computer_name": fingerprint_component(system.get("computer_name") or system.get("hostname")),
        "system_manufacturer": fingerprint_component(
            system.get("manufacturer") or firmware.get("system_manufacturer")
        ),
        "system_model": fingerprint_component(system.get("model") or firmware.get("system_product_name")),
        "os_identity": fingerprint_component(system.get("os_caption") or system.get("os_release")),
        "architecture": fingerprint_component(system.get("architecture")),
        "firmware": [
            fingerprint_component(system.get("bios_manufacturer") or firmware.get("bios_manufacturer")),
            fingerprint_component(system.get("bios_version") or firmware.get("bios_version")),
            fingerprint_component(firmware.get("bios_date")),
            fingerprint_component(firmware.get("board_name")),
        ],
        "cpu": sorted(
            fingerprint_joined(
                row.get("name"),
                row.get("manufacturer") or row.get("vendor"),
                row.get("processor_id") or row.get("package_id"),
                row.get("cores"),
                row.get("logical_processors"),
            )
            for row in cpu_rows
            if isinstance(row, dict)
        ),
        "memory_total_bytes": memory.get("total_bytes"),
        "physical_disks": sorted(
            fingerprint_joined(row.get("model"), row.get("size_bytes"))
            for row in disks
            if isinstance(row, dict)
        ),
        "display_adapters": sorted(
            fingerprint_joined(row.get("name"), row.get("pnp_device_id") or row.get("bus_id"))
            for row in adapters
            if isinstance(row, dict)
        ),
        "accelerator_identities": accelerator_identities(observation),
    }


def observed_host_fingerprint(observation: Any) -> str:
    return hashlib.sha256(canonical_bytes(host_fingerprint_components(observation))).hexdigest()


def _body_strings(payload: Any, found: set) -> None:
    if isinstance(payload, dict):
        for value in payload.values():
            _body_strings(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _body_strings(value, found)
    elif isinstance(payload, str) and len(payload) >= 3:
        found.add(payload)


def _receipt_values(payload: Any, found: list) -> None:
    """Receipt values only. Keys are contract names and are never a leak."""
    if isinstance(payload, dict):
        for value in payload.values():
            _receipt_values(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _receipt_values(value, found)
    elif isinstance(payload, str):
        found.append(payload)


def receipt_body_leak_failures(receipt: Any, observation: Any) -> list[str]:
    """Refuse a receipt that repeats any host-descriptive value from the body.

    A value leaks when it equals a receipt value outright, or when it is long
    enough to be an identifier (eight characters or more) and appears inside
    one. Only the declared join coordinates and the collector and Python
    executable digests are exempt.
    """
    collector = observation.get("collector") if isinstance(observation, dict) else {}
    collector = collector if isinstance(collector, dict) else {}
    python_identity = collector.get("python_executable")
    python_identity = python_identity if isinstance(python_identity, dict) else {}
    allowed = {str(observation.get(name)) for name in RECEIPT_JOIN_COORDINATES}
    allowed.update(
        {
            str(collector.get("schema")),
            str(collector.get("source_sha256")),
            str(python_identity.get("sha256")),
        }
    )
    body: set = set()
    _body_strings(observation, body)
    values: list = []
    _receipt_values(receipt, values)
    failures: list[str] = []
    for candidate in sorted(body - allowed):
        for value in values:
            if candidate == value or (len(candidate) >= 8 and candidate in value):
                failures.append(f"receipt carries an observation body value: {candidate!r}")
                break
    return failures


def validate_receipt(receipt: Any, observation: Any, observation_path: Path) -> list[str]:
    """Return the list of refusals for a body-free return receipt."""
    if not isinstance(receipt, dict):
        return ["receipt is not a JSON object"]
    failures: list[str] = []
    for field in RECEIPT_REQUIRED:
        if field not in receipt:
            failures.append(f"receipt field missing: {field}")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        failures.append("receipt schema mismatch")
    if receipt.get("carries_observation_body") is not False:
        failures.append("receipt must declare carries_observation_body false")
    if not isinstance(observation, dict):
        return failures + ["receipt cannot be checked against an unreadable observation"]
    for field, name in (
        ("observation_schema", "schema"),
        ("platform", "platform"),
        ("host_id", "host_id"),
        ("observed_at", "observed_at"),
        ("observation_sha256", "observation_sha256"),
    ):
        if receipt.get(field) != observation.get(name):
            failures.append(f"receipt {field} does not bind the observation {name}")
    if observation_path.is_file():
        if receipt.get("observation_file_name") != observation_path.name:
            failures.append("receipt observation_file_name does not name the observation file")
        if receipt.get("observation_file_sha256") != sha256_file(observation_path):
            failures.append("receipt observation_file_sha256 does not bind the exact file bytes")
        if receipt.get("observation_file_bytes") != observation_path.stat().st_size:
            failures.append("receipt observation_file_bytes does not bind the exact file size")
    if receipt.get("host_fingerprint_sha256") != observed_host_fingerprint(observation):
        failures.append("receipt host_fingerprint_sha256 does not recompute from the observation")
    identities = accelerator_identities(observation)
    expected_identities = sorted(
        hashlib.sha256(identity.encode("utf-8")).hexdigest() for identity in identities
    )
    if receipt.get("accelerator_identity_sha256") != expected_identities:
        failures.append("receipt accelerator_identity_sha256 does not recompute from the observation")
    if receipt.get("accelerator_identity_count") != len(identities):
        failures.append("receipt accelerator_identity_count does not match the observation")
    expected_receipt_digest = hashlib.sha256(
        canonical_bytes({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    ).hexdigest()
    if receipt.get("receipt_sha256") != expected_receipt_digest:
        failures.append("receipt digest mismatch")
    failures.extend(receipt_body_leak_failures(receipt, observation))
    return failures


def validate(observation: Any) -> list[str]:
    """Return the list of refusals. Empty means the observation is admissible."""
    if not isinstance(observation, dict):
        return ["observation is not a JSON object"]
    failures: list[str] = []
    for field in REQUIRED_TOP_LEVEL:
        if field not in observation:
            failures.append(f"required field missing: {field}")
    if observation.get("schema") != SCHEMA:
        failures.append("schema mismatch")
    if observation.get("platform") != "linux":
        failures.append("platform must be linux")
    if not observation.get("host_id"):
        failures.append("host_id missing")
    system = observation.get("system")
    if not isinstance(system, dict):
        failures.append("system object missing")
    else:
        for field in ("hostname", "kernel", "architecture"):
            if not system.get(field):
                failures.append(f"system.{field} missing")
    if not observation.get("cpu"):
        failures.append("cpu inventory missing")
    memory = observation.get("memory")
    if not isinstance(memory, dict) or not memory.get("total_bytes"):
        failures.append("memory.total_bytes missing")
    storage = observation.get("storage")
    if not isinstance(storage, dict) or not storage.get("physical_disks"):
        failures.append("storage.physical_disks missing")
    failures.extend(validate_runtime(observation.get("runtime")))
    failures.extend(validate_collector(observation.get("collector")))
    expected_digest = hashlib.sha256(
        canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
    ).hexdigest()
    if observation.get("observation_sha256") != expected_digest:
        failures.append("observation digest mismatch")
    failures.extend(collect_private_fields(observation))
    return failures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a returned Linux host observation")
    parser.add_argument("observation", help="Path to the returned <host-id>.json observation")
    parser.add_argument(
        "--receipt",
        default="",
        help="Path to the body-free <host-id>.receipt.json returned alongside the observation",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.observation)
    try:
        observation = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "failures": [f"unreadable observation: {exc}"]}, indent=2))
        return 2
    failures = validate(observation)
    receipt_path = Path(args.receipt) if args.receipt else None
    receipt = None
    if receipt_path is not None:
        try:
            receipt = json.loads(receipt_path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "failures": [f"unreadable receipt: {exc}"]}, indent=2))
            return 2
        failures = failures + validate_receipt(receipt, observation, path)
    if failures:
        print(json.dumps({"ok": False, "observation": str(path), "failures": failures}, indent=2))
        return 1
    result = {
        "ok": True,
        "observation": str(path),
        "host_id": observation.get("host_id"),
        "observation_sha256": observation.get("observation_sha256"),
        "host_fingerprint_sha256": observed_host_fingerprint(observation),
    }
    if receipt is not None:
        result["receipt"] = str(receipt_path)
        result["receipt_sha256"] = receipt.get("receipt_sha256")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
