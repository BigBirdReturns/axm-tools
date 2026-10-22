#!/usr/bin/env python3
"""Deterministic local validator for Linux host observations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from planner import canonical_bytes

REQUIRED_RUNTIME = ("python", "git", "ollama", "docker", "wsl", "nvidia-smi")
SCHEMA = "axm-community-lab/host-observation@2"
COLLECTOR_SCHEMA = "axm-community-lab/host-observation-collector@1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_mapping(value: dict) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def collect_private_fields(observation: object, path: str = "observation") -> list[str]:
    if not isinstance(observation, dict):
        return []
    prohibited = ("serial", "machine_guid", "mac_address", "ip_address", "credential", "private_key", "token", "tailscale")
    failures: list[str] = []
    for key, value in observation.items():
        lower = str(key).lower()
        if any(marker in lower for marker in prohibited):
            failures.append(f"prohibited private field: {path}.{key}")
        if isinstance(value, (dict, list)):
            child = collect_private_fields(value, path=f"{path}.{key}")
            failures.extend(child)
    return failures


def validate(observation: dict, source_hint: Path) -> list[str]:
    failures: list[str] = []
    if observation.get("schema") != SCHEMA:
        failures.append("schema mismatch")
    if observation.get("platform") != "linux":
        failures.append("platform must be linux")
    system = observation.get("system")
    if not isinstance(system, dict) or not system.get("kernel"):
        failures.append("system.kernel missing")
    runtime = observation.get("runtime")
    if not isinstance(runtime, list):
        failures.append("runtime inventory missing")
    else:
        names = {str(row.get("name") or "").strip() for row in runtime if isinstance(row, dict)}
        if names != set(REQUIRED_RUNTIME):
            failures.append(f"runtime denominator mismatch: {sorted(names)}")
    for row in runtime if isinstance(runtime, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if name == "wsl" and row.get("present") is not False:
            failures.append("wsl must be explicit false on native Linux")
    collector = observation.get("collector")
    if not isinstance(collector, dict) or collector.get("schema") != COLLECTOR_SCHEMA:
        failures.append("collector schema mismatch")
    if isinstance(collector, dict):
        source_path = Path(str(collector.get("source_path") or ""))
        if source_path.exists():
            if collector.get("source_sha256") != sha256_file(source_path):
                failures.append("collector source digest mismatch")
        else:
            failures.append("collector source_path missing")
        executable = Path(str(collector.get("python_executable", {}).get("path") or ""))
        executable_sha = collector.get("python_executable", {}).get("sha256")
        if not executable.exists():
            failures.append("collector python executable missing")
        elif executable_sha != sha256_file(executable):
            failures.append("collector python executable digest mismatch")
    if observation.get("observation_sha256") != sha256_mapping({k: v for k, v in observation.items() if k != "observation_sha256"}):
        failures.append("observation digest mismatch")
    if source_hint and source_hint != Path(""):
        source_hint.parent.mkdir(parents=True, exist_ok=True)
    failures.extend(collect_private_fields(observation))
    return failures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Linux host observation")
    parser.add_argument("observation")
    parser.add_argument("--source-hint", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    observation = json.loads(Path(args.observation).read_text(encoding="utf-8"))
    failures = validate(observation, Path(args.source_hint))
    if failures:
        print(json.dumps({"ok": False, "failures": failures}, indent=2))
        return 1
    print(json.dumps({"ok": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
