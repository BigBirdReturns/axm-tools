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
    if failures:
        print(json.dumps({"ok": False, "observation": str(path), "failures": failures}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "observation": str(path),
                "host_id": observation.get("host_id"),
                "observation_sha256": observation.get("observation_sha256"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
