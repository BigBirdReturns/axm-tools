#!/usr/bin/env python3
"""Read-only Linux host observation collector.

The collector emits ``axm-community-lab/host-observation@2`` observations with:

- closed runtime denominator,
- explicit missing-tool evidence,
- collector identity (collector source and Python executable),
- no socket/listener/network side effect,
- atomic on-disk publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence
import sys

from planner import canonical_bytes

SCHEMA = "axm-community-lab/host-observation@2"
COLLECTOR_SCHEMA = "axm-community-lab/host-observation-collector@1"
REQUIRED_RUNTIME_NAMES = ("python", "git", "ollama", "docker", "wsl", "nvidia-smi")
RUNTIME_WSL_INAPPLICABLE_REASON = "not applicable on a native Linux host"
OS_RELEASE_PATH = Path("/etc/os-release")
CPUINFO_PATH = Path("/proc/cpuinfo")
MEMINFO_PATH = Path("/proc/meminfo")
SYS_DMI_PATH = Path("/sys/class/dmi/id")
SYS_NET_PATH = Path("/sys/class/net")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path, *, strict: bool = False) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None if not strict else None
    except OSError:
        return None


def utc_now() -> str:
    return __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(command: Sequence[str], *, timeout: float = 5.0) -> str:
    try:
        process = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except OSError:
        return ""
    return process.stdout.strip()


def parse_os_release(path: Path = OS_RELEASE_PATH) -> dict[str, str]:
    text = read_text(path)
    if not text:
        return {}
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        result[key.strip()] = value
    return result


def parse_cpuinfo(path: Path = CPUINFO_PATH) -> list[dict[str, Any]]:
    text = read_text(path)
    if not text:
        return []
    fields: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                fields.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip()
    if current:
        fields.append(current)
    cores = set()
    logicals = set()
    rows: list[dict[str, Any]] = []
    for row in fields:
        try:
            logicals.add(int(row.get("processor", "").strip()))
        except ValueError:
            pass
        if row.get("processor", "").strip() == "0":
            cores.add(row.get("cpu cores", ""))
        rows.append(
            {
                "name": row.get("model name", ""),
                "vendor": row.get("vendor_id", ""),
                "processor_id": row.get("processor", ""),
                "physical_id": row.get("physical id", ""),
                "cores": int(row.get("cpu cores", "0") or 0),
                "logical_processors": int(row.get("siblings", "0") or 0),
                "max_clock_mhz": int(row.get("cpu MHz", "0") or 0),
                "current_clock_mhz": int(row.get("cpu MHz", "0") or 0),
                "virtualization_firmware_enabled": None,
            }
        )
    return rows


def parse_meminfo(path: Path = MEMINFO_PATH) -> dict[str, Any]:
    text = read_text(path)
    if not text:
        return {}
    for line in text.splitlines():
        if line.lower().startswith("memtotal:"):
            parts = line.split()
            try:
                return {"total_bytes": int(parts[1]) * 1024}
            except (IndexError, ValueError):
                return {}
    return {}


def collect_storage() -> dict[str, Any]:
    output = run_command(["lsblk", "--json", "--bytes", "--output", "NAME,TYPE,SIZE,MODEL,ROTA"])
    if not output:
        return {"physical_disks": [], "logical_volumes": []}
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {"physical_disks": [], "logical_volumes": []}
    block_devices = payload.get("blockdevices")
    if not isinstance(block_devices, list):
        return {"physical_disks": [], "logical_volumes": []}

    def walk(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        physical: list[dict[str, Any]] = []
        logical: list[dict[str, Any]] = []
        for item in nodes:
            kind = str(item.get("type", ""))
            row = {
                "name": item.get("name"),
                "model": item.get("model"),
                "size_bytes": item.get("size"),
                "interface": item.get("rota"),
                "partitions": None,
            }
            if kind == "disk":
                physical.append({k: v for k, v in row.items() if k != "partitions"})
            elif kind in {"part", "lvm", "crypt", "loop"}:
                logical.append(
                    {
                        "name": item.get("name"),
                        "size_bytes": item.get("size"),
                        "type": kind,
                    }
                )
            children = item.get("children")
            if isinstance(children, list):
                physical_children, logical_children = walk(children)
                physical.extend(physical_children)
                logical.extend(logical_children)
        return physical, logical

    physical, logical = walk(block_devices)
    return {"physical_disks": physical, "logical_volumes": logical}


def parse_lspci_adapters() -> list[dict[str, Any]]:
    output = run_command(["lspci", "-mm", "-nn"])
    if not output:
        return []
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [segment.strip('"') for segment in re.split(r"\s+", line, maxsplit=3)]
        if len(parts) < 3:
            continue
        bus, _class, vendor_name = parts[:3]
        name = _class
        vendor = (vendor_name or "").upper()
        if not name:
            continue
        lower = f"{vendor_name} {name}".lower()
        if "intel" in lower:
            vendor_guess = "Intel"
            role_candidate = "igpu-candidate"
        elif "nvidia" in lower:
            vendor_guess = "NVIDIA"
            role_candidate = "dgpu"
        elif "amd" in lower or "radeon" in lower:
            vendor_guess = "AMD"
            role_candidate = "igpu-candidate"
        else:
            vendor_guess = "Unknown"
            role_candidate = "unclassified"
        rows.append(
            {
                "name": name,
                "pnp_device_id": bus,
                "vendor_guess": vendor_guess,
                "role_candidate": role_candidate,
                "bus_id": bus,
            }
        )
    return rows


def parse_nvidia_rows() -> list[dict[str, Any]]:
    command = run_command(["nvidia-smi", "--query-gpu=uuid,name,memory.total,driver_version,pci.bus_id,pstate,power.limit", "--format=csv,noheader,nounits"])
    if not command:
        return []
    rows: list[dict[str, Any]] = []
    for line in command.splitlines():
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 7:
            continue
        uuid = parts[0]
        if not uuid or uuid.lower() == "n/a":
            continue
        def _as_int(value: str) -> int | None:
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return None
        def _as_float(value: str) -> float | None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        rows.append(
            {
                "uuid": uuid,
                "name": parts[1],
                "memory_total_mib": _as_int(parts[2]),
                "driver_version": parts[3],
                "pci_bus_id": parts[4],
                "pstate": parts[5],
                "power_limit_watts": _as_float(parts[6]),
            }
        )
    return rows


def collect_dmi_fields() -> dict[str, Any]:
    values = {
        "bios_manufacturer": read_text(SYS_DMI_PATH / "bios_vendor"),
        "bios_version": read_text(SYS_DMI_PATH / "bios_version"),
        "system_manufacturer": read_text(SYS_DMI_PATH / "sys_vendor"),
        "system_product_name": read_text(SYS_DMI_PATH / "product_name"),
        "system_family": read_text(SYS_DMI_PATH / "product_family"),
    }
    firmware = {key: value for key, value in values.items() if value}
    if firmware:
        return firmware
    return {}


def collect_network_adapters() -> list[dict[str, Any]]:
    if not SYS_NET_PATH.exists():
        return []
    adapters: list[dict[str, Any]] = []
    for entry in sorted(SYS_NET_PATH.iterdir(), key=lambda item: item.name):
        if not entry.is_dir() or entry.name == "lo":
            continue
        state = read_text(entry / "operstate")
        speed = read_text(entry / "speed")
        mtu = read_text(entry / "mtu")
        adapters.append(
            {
                "name": entry.name,
                "state": state,
                "mtu": _coerce_int(mtu),
                "speed_mbps": _coerce_int(speed),
            }
        )
    return adapters


def _coerce_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def runtime_rows(platform: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    in_wsl = platform == "wsl"
    for name in REQUIRED_RUNTIME_NAMES:
        path = shutil.which(name)
        if name == "wsl" and not in_wsl:
            rows.append(
                {
                    "name": name,
                    "present": False,
                    "path": None,
                    "disabled": True,
                    "disabled_reason": RUNTIME_WSL_INAPPLICABLE_REASON,
                }
            )
            continue
        if path is None:
            rows.append(
                {
                    "name": name,
                    "present": False,
                    "path": None,
                    "disabled": True,
                    "disabled_reason": "command not found in the current process PATH",
                }
            )
            continue
        rows.append(
            {
                "name": name,
                "present": True,
                "path": path,
                "disabled": False,
                "disabled_reason": None,
            }
        )
    return rows


def linux_system_identity() -> dict[str, Any]:
    uname = os.uname()
    os_release = parse_os_release()
    return {
        "hostname": uname.nodename,
        "os_release": os_release.get("PRETTY_NAME") or os_release.get("NAME"),
        "kernel": uname.release,
        "architecture": uname.machine,
        "firmware": collect_dmi_fields(),
        "manufacturer": read_text(SYS_DMI_PATH / "sys_vendor") or os_release.get("ID"),
        "model": read_text(SYS_DMI_PATH / "product_name"),
        "os_version": os_release.get("VERSION_ID"),
    }


def collect_clock_observations(sample_count: int = 5) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for _ in range(sample_count):
        samples.append({"wall_utc": utc_now(), "monotonic_ticks": __import__("time").perf_counter_ns()})
    return {
        "stopwatch_frequency_hz": 1_000_000_000,
        "samples": samples,
        "cross_host_offset_measured": False,
    }


def required_fields_for_observation(observation: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if not observation.get("host_id"):
        failures.append("host_id missing")
    system = observation.get("system")
    if not isinstance(system, Mapping):
        failures.append("system object missing")
        return failures
    if not system.get("hostname"):
        failures.append("system.hostname missing")
    if not system.get("kernel"):
        failures.append("system.kernel missing")
    if not system.get("architecture"):
        failures.append("system.architecture missing")
    memory = observation.get("memory")
    if not isinstance(memory, Mapping) or not memory.get("total_bytes"):
        failures.append("memory.total_bytes missing")
    storage = observation.get("storage")
    if not isinstance(storage, Mapping) or not storage.get("physical_disks"):
        failures.append("storage.physical_disks missing")
    runtime = observation.get("runtime")
    if not isinstance(runtime, list):
        failures.append("runtime inventory missing")
        return failures
    names = [str(item.get("name") or "") for item in runtime if isinstance(item, Mapping)]
    if set(names) != set(REQUIRED_RUNTIME_NAMES):
        failures.append("runtime denominator mismatch")
    return failures


def build_observation(host_id: str) -> tuple[dict[str, Any], list[str]]:
    host_id = host_id.strip()
    if not host_id:
        raise ValueError("host_id required")
    adapters = parse_lspci_adapters()
    nvidia = parse_nvidia_rows()
    system = linux_system_identity()
    memory = parse_meminfo()
    memory["modules"] = []
    storage = collect_storage()
    clock = collect_clock_observations()
    collector_path = Path(__file__).resolve()
    collector = {
        "schema": COLLECTOR_SCHEMA,
        "platform": "linux",
        "source_path": str(collector_path),
        "source_sha256": sha256_file(collector_path),
        "python_executable": {
            "path": sys.executable,
            "sha256": sha256_file(Path(sys.executable)),
        },
    }
    if not collector["python_executable"]["path"] or not collector["python_executable"]["sha256"]:
        failures = ["python executable identity missing"]
    else:
        failures = []
    observation: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at": utc_now(),
        "platform": "linux",
        "host_id": host_id,
        "collector": collector,
        "system": system,
        "cpu": parse_cpuinfo(),
        "memory": memory,
        "storage": storage,
        "graphics": {
            "adapters": adapters,
            "nvidia": nvidia,
        },
        "network": {
            "adapters": collect_network_adapters(),
            "addresses_collected": False,
        },
        "runtime": runtime_rows("linux"),
        "clock": clock,
        "privacy": {
            "serial_numbers_collected": False,
            "mac_addresses_collected": False,
            "ip_addresses_collected": False,
            "machine_guid_collected": False,
        },
    }
    observation["observation_sha256"] = sha256_bytes(canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"}))
    failures.extend(required_fields_for_observation(observation))
    return observation, failures


def write_atomic_json(payload: Mapping[str, Any], path: Path) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    data = json.dumps(payload, indent=2) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def collect(host_id: str, out_file: Path) -> tuple[dict[str, Any], list[str]]:
    observation, failures = build_observation(host_id)
    if failures:
        return observation, failures
    write_atomic_json(observation, out_file)
    return observation, []


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-id", required=True, help="Host id declared in estate")
    parser.add_argument("--out-file", required=True, help="Observation JSON destination path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _, failures = collect(args.host_id, Path(args.out_file))
        if failures:
            print(json.dumps({"ok": False, "failures": failures}, indent=2))
            return 1
        print(json.dumps({"ok": True, "output": str(Path(args.out_file).resolve())}, indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
