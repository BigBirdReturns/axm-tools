#!/usr/bin/env python3
"""Read-only Linux host observation collector.

Emits ``axm-community-lab/host-observation@2`` observations with:

- a closed runtime denominator,
- explicit missing-tool and unreadable-surface evidence,
- collector identity (collector source digest and Python executable digest),
- no socket, listener, installer, or system-state side effect,
- a coordinate bound to the seed manifest before any host surface is read,
- atomic on-disk publication through an exclusively created, unpredictable
  same-directory temporary that can never be a pre-existing alias,
- a body-free return receipt beside the observation, for the W01 join.

The script is deliberately standard-library only and self-contained so the
offline seed can run it on a host that has no clone of this repository.

The module never imports ``socket``, ``urllib``, ``http``, or any other
transport: the absence of those imports is part of the read-only claim.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "axm-community-lab/host-observation@2"
COLLECTOR_SCHEMA = "axm-community-lab/host-observation-collector@1"
RECEIPT_SCHEMA = "axm-community-lab/host-observation-receipt@1"
RECEIPT_SUFFIX = ".receipt.json"
# The observed-host fingerprint definition is inlined here, in the seed
# validator, and in the qualifier for the same reason canonical_bytes is: the
# seed must run on a host with no clone of this repository. A witness asserts
# all three definitions agree on one fixture, so a drift is a red test rather
# than a silently different digest.
HOST_FINGERPRINT_SCHEMA = "axm-community-lab/observed-host-fingerprint@1"
BUNDLE_ROOT = Path(__file__).resolve().parents[1]
SEED_MANIFEST_NAME = "seed/seed-manifest.json"
SEED_SUMS_NAME = "seed/sha256sums.txt"
SEED_MANIFEST_PATH = BUNDLE_ROOT / "seed" / "seed-manifest.json"
SEED_SUMS_PATH = BUNDLE_ROOT / "seed" / "sha256sums.txt"
REQUIRED_RUNTIME_NAMES = ("python", "git", "ollama", "docker", "wsl", "nvidia-smi")
RUNTIME_WSL_INAPPLICABLE_REASON = "not applicable on a native Linux host"
RUNTIME_ABSENT_REASON = "command not found in the current process PATH"
OPTIONAL_TOOLS = ("lsblk", "lspci", "nvidia-smi")
OS_RELEASE_PATH = Path("/etc/os-release")
CPUINFO_PATH = Path("/proc/cpuinfo")
MEMINFO_PATH = Path("/proc/meminfo")
SYS_DMI_PATH = Path("/sys/class/dmi/id")
SYS_NET_PATH = Path("/sys/class/net")
DMI_TABLE_PATH = Path("/sys/firmware/dmi/tables/DMI")

# DMI identity files that are safe to publish. product_serial, board_serial,
# and product_uuid are deliberately absent: they are the Linux equivalents of
# the chassis serial and machine GUID that Gradient privacy law refuses.
DMI_PUBLIC_FIELDS = (
    ("bios_manufacturer", "bios_vendor"),
    ("bios_version", "bios_version"),
    ("bios_date", "bios_date"),
    ("system_manufacturer", "sys_vendor"),
    ("system_product_name", "product_name"),
    ("system_family", "product_family"),
    ("board_name", "board_name"),
)


class CollectorError(RuntimeError):
    """Raised when the collector cannot run on this host at all."""


class CoordinateError(ValueError):
    """Raised when --host-id or --out-file leaves the declared seed coordinate."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Digest exact file bytes. Never a text-mode read: line endings count."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str | None:
    """Return stripped file text, or None when the surface is unreadable."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def path_readable(path: Path) -> bool:
    try:
        return path.exists() and os.access(path, os.R_OK)
    except OSError:
        return False


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_uname() -> Any:
    """Indirection over ``os.uname`` so the POSIX seam stays patchable.

    ``os.uname`` does not exist on Windows, where this collector's hostile
    witnesses run against mocked surfaces.
    """
    uname = getattr(os, "uname", None)
    if uname is None:
        raise CollectorError("os.uname is unavailable: this collector targets POSIX hosts")
    return uname()


def which(name: str) -> str | None:
    return shutil.which(name)


def run_command(command: Sequence[str], *, timeout: float = 5.0) -> str:
    """Run a read-only local query. Never a shell; failure is an empty string."""
    try:
        process = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return process.stdout.strip()


def parse_os_release(path: Path | None = None) -> dict[str, str]:
    text = read_text(path if path is not None else OS_RELEASE_PATH)
    if not text:
        return {}
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key.strip()] = value
    return result


def coerce_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def parse_cpuinfo(path: Path | None = None) -> list[dict[str, Any]]:
    """One row per physical package, with observed logical-processor counts.

    /proc/cpuinfo repeats every field once per logical processor; publishing
    all of them would be topology noise rather than topology evidence.
    """
    text = read_text(path if path is not None else CPUINFO_PATH)
    if not text:
        return []
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip()
    if current:
        blocks.append(current)

    packages: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for block in blocks:
        package_id = block.get("physical id", "0")
        if package_id not in packages:
            order.append(package_id)
            packages[package_id] = {
                "name": block.get("model name") or None,
                "vendor": block.get("vendor_id") or None,
                "package_id": package_id,
                "cores": coerce_int(block.get("cpu cores")),
                "logical_processors": coerce_int(block.get("siblings")),
                "logical_processors_observed": 0,
                "current_clock_mhz": coerce_int(block.get("cpu MHz")),
                "max_clock_mhz": None,
                "virtualization_firmware_enabled": None,
            }
        row = packages[package_id]
        row["logical_processors_observed"] = int(row["logical_processors_observed"]) + 1
        observed = coerce_int(block.get("cpu MHz"))
        if observed is not None:
            known = row["max_clock_mhz"]
            row["max_clock_mhz"] = observed if known is None else max(int(known), observed)
    return [packages[key] for key in order]


def parse_meminfo(path: Path | None = None) -> dict[str, Any]:
    text = read_text(path if path is not None else MEMINFO_PATH)
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


def collect_memory() -> dict[str, Any]:
    """Total memory plus explicit evidence about module-level readability.

    Per-module evidence lives in the raw DMI table, which is root-only on a
    stock Ubuntu host and carries module serial numbers besides. The collector
    requires no sudo, so the absence is published rather than silently omitted.
    """
    memory = parse_meminfo()
    readable = path_readable(DMI_TABLE_PATH)
    memory["modules"] = []
    memory["modules_available"] = False
    memory["modules_source"] = {
        "path": str(DMI_TABLE_PATH),
        "readable": readable,
        "note": (
            "DMI memory-device table is readable but deliberately not parsed: "
            "it carries module serial numbers that Gradient privacy law refuses"
            if readable
            else "DMI memory-device table is not readable without elevated "
            "access; the collector requires no sudo"
        ),
    }
    return memory


DISK_TYPES = ("disk",)
LOGICAL_TYPES = ("part", "lvm", "crypt", "loop", "raid0", "raid1", "raid5", "raid6", "raid10")


def collect_storage() -> dict[str, Any]:
    """Physical disks and logical volumes from lsblk, never serial numbers.

    The requested column list deliberately omits SERIAL and WWN.
    """
    empty: dict[str, Any] = {"physical_disks": [], "logical_volumes": [], "source": "lsblk"}
    if which("lsblk") is None:
        return {**empty, "available": False, "note": "lsblk is not installed on this host"}
    output = run_command(["lsblk", "--json", "--bytes", "--output", "NAME,TYPE,SIZE,MODEL,ROTA"])
    if not output:
        return {**empty, "available": False, "note": "lsblk produced no readable output"}
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {**empty, "available": False, "note": "lsblk output was not valid JSON"}
    block_devices = payload.get("blockdevices")
    if not isinstance(block_devices, list):
        return {**empty, "available": False, "note": "lsblk reported no block devices"}

    def walk(nodes: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        physical: list[dict[str, Any]] = []
        logical: list[dict[str, Any]] = []
        for item in nodes:
            if not isinstance(item, Mapping):
                continue
            kind = str(item.get("type", ""))
            if kind in DISK_TYPES:
                physical.append(
                    {
                        "name": item.get("name"),
                        "model": item.get("model"),
                        "size_bytes": item.get("size"),
                        "rotational": item.get("rota"),
                    }
                )
            elif kind in LOGICAL_TYPES:
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
    return {
        "physical_disks": physical,
        "logical_volumes": logical,
        "source": "lsblk",
        "available": True,
        "note": None,
    }


DISPLAY_CLASS_MARKERS = ("vga", "3d controller", "display")


def classify_display_vendor(text: str) -> tuple[str, str]:
    lower = text.lower()
    if "nvidia" in lower:
        return "NVIDIA", "dgpu"
    if "intel" in lower:
        return "Intel", "igpu-candidate"
    if "amd" in lower or "radeon" in lower or "advanced micro devices" in lower:
        return "AMD", "igpu-candidate"
    return "Unknown", "unclassified"


def parse_lspci_adapters() -> list[dict[str, Any]]:
    """Display-class PCI functions from ``lspci -mm -nn``.

    Machine-readable mode quotes each field, so shlex splitting is exact:
    ``00:02.0 "VGA compatible controller [0300]" "Intel Corporation [8086]" ...``
    """
    if which("lspci") is None:
        return []
    output = run_command(["lspci", "-mm", "-nn"])
    if not output:
        return []
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            parts = shlex.split(line)
        except ValueError:
            continue
        if len(parts) < 3:
            continue
        bus = parts[0]
        device_class = parts[1]
        vendor_name = parts[2]
        device_name = parts[3] if len(parts) > 3 else ""
        if not any(marker in device_class.lower() for marker in DISPLAY_CLASS_MARKERS):
            continue
        vendor_guess, role_candidate = classify_display_vendor(f"{vendor_name} {device_name}")
        rows.append(
            {
                "name": device_name or device_class,
                "device_class": device_class,
                "pnp_device_id": bus,
                "bus_id": bus,
                "vendor_guess": vendor_guess,
                "role_candidate": role_candidate,
            }
        )
    return rows


NVIDIA_QUERY_FIELDS = (
    "uuid",
    "name",
    "memory.total",
    "driver_version",
    "pci.bus_id",
    "pstate",
    "power.limit",
)


def parse_nvidia_rows() -> list[dict[str, Any]]:
    if which("nvidia-smi") is None:
        return []
    output = run_command(
        [
            "nvidia-smi",
            "--query-gpu=" + ",".join(NVIDIA_QUERY_FIELDS),
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return []

    def as_int(value: str) -> int | None:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def as_float(value: str) -> float | None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < len(NVIDIA_QUERY_FIELDS):
            continue
        uuid = parts[0]
        if not uuid or uuid.lower() in {"n/a", "[n/a]", "unknown"}:
            continue
        rows.append(
            {
                "uuid": uuid,
                "name": parts[1],
                "memory_total_mib": as_int(parts[2]),
                "driver_version": parts[3],
                "pci_bus_id": parts[4],
                "pstate": parts[5],
                "power_limit_watts": as_float(parts[6]),
            }
        )
    return rows


def collect_dmi_fields() -> dict[str, Any]:
    """Publishable DMI identity; unreadable fields stay explicit as null."""
    return {label: read_text(SYS_DMI_PATH / filename) for label, filename in DMI_PUBLIC_FIELDS}


def collect_network_adapters() -> list[dict[str, Any]]:
    """Physical link evidence only.

    ``address`` (the MAC) and every /proc/net address surface are never read.
    Link name, state, MTU, and negotiated speed carry the topology evidence
    Gradient needs without an addressable identifier.
    """
    try:
        entries = sorted(SYS_NET_PATH.iterdir(), key=lambda item: item.name)
    except OSError:
        return []
    adapters: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.is_dir() or entry.name == "lo":
            continue
        adapters.append(
            {
                "name": entry.name,
                "state": read_text(entry / "operstate"),
                "mtu": coerce_int(read_text(entry / "mtu")),
                "speed_mbps": coerce_int(read_text(entry / "speed")),
                "physical": (entry / "device").exists(),
            }
        )
    return adapters


def runtime_rows() -> list[dict[str, Any]]:
    """The closed runtime denominator. A row never disappears, it goes false."""
    rows: list[dict[str, Any]] = []
    for name in REQUIRED_RUNTIME_NAMES:
        if name == "wsl":
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
        path = which(name)
        if path is None:
            rows.append(
                {
                    "name": name,
                    "present": False,
                    "path": None,
                    "disabled": True,
                    "disabled_reason": RUNTIME_ABSENT_REASON,
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


def collect_surfaces() -> dict[str, Any]:
    """Explicit readability evidence for every surface the collector consults."""
    files: dict[str, Any] = {}
    for label, path in (
        ("etc_os_release", OS_RELEASE_PATH),
        ("proc_cpuinfo", CPUINFO_PATH),
        ("proc_meminfo", MEMINFO_PATH),
        ("sys_dmi_id", SYS_DMI_PATH),
        ("sys_class_net", SYS_NET_PATH),
        ("sys_firmware_dmi_table", DMI_TABLE_PATH),
    ):
        files[label] = {"path": str(path), "readable": path_readable(path)}
    tools: dict[str, Any] = {}
    for tool in OPTIONAL_TOOLS:
        location = which(tool)
        tools[tool] = {
            "available": location is not None,
            "path": location,
            "note": None if location is not None else "optional tool not installed on this host",
        }
    return {"files": files, "tools": tools}


def linux_system_identity() -> dict[str, Any]:
    uname = read_uname()
    os_release = parse_os_release()
    firmware = collect_dmi_fields()
    return {
        "hostname": uname.nodename,
        "os_release": os_release.get("PRETTY_NAME") or os_release.get("NAME"),
        "os_version": os_release.get("VERSION_ID"),
        "os_id": os_release.get("ID"),
        "kernel": uname.release,
        "kernel_version": uname.version,
        "architecture": uname.machine,
        "manufacturer": firmware.get("system_manufacturer") or os_release.get("ID"),
        "model": firmware.get("system_product_name"),
        "firmware": firmware,
    }


def collect_clock_observations(sample_count: int = 5) -> dict[str, Any]:
    """Wall-clock and monotonic evidence. No cross-host offset is claimed."""
    samples: list[dict[str, Any]] = []
    for _ in range(sample_count):
        samples.append(
            {
                "wall_utc": utc_now(),
                "monotonic_ns": time.monotonic_ns(),
                "perf_counter_ns": time.perf_counter_ns(),
            }
        )
    return {
        "stopwatch_frequency_hz": 1_000_000_000,
        "monotonic_resolution_ns": int(time.get_clock_info("monotonic").resolution * 1_000_000_000),
        "samples": samples,
        "cross_host_offset_measured": False,
    }


def required_fields_for_observation(observation: Mapping[str, Any]) -> list[str]:
    """Refusal denominator: a missing or contradictory required field."""
    failures: list[str] = []
    if not observation.get("host_id"):
        failures.append("host_id missing")
    if observation.get("platform") != "linux":
        failures.append("platform must be linux")
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
    if not observation.get("cpu"):
        failures.append("cpu inventory missing")
    memory = observation.get("memory")
    if not isinstance(memory, Mapping) or not memory.get("total_bytes"):
        failures.append("memory.total_bytes missing")
    storage = observation.get("storage")
    if not isinstance(storage, Mapping) or not storage.get("physical_disks"):
        failures.append("storage.physical_disks missing")
    collector = observation.get("collector")
    if not isinstance(collector, Mapping):
        failures.append("collector identity missing")
    else:
        python_identity = collector.get("python_executable")
        if (
            not isinstance(python_identity, Mapping)
            or not python_identity.get("path")
            or not python_identity.get("sha256")
        ):
            failures.append("python executable identity missing")
        if not collector.get("source_sha256"):
            failures.append("collector source digest missing")
    runtime = observation.get("runtime")
    if not isinstance(runtime, list):
        failures.append("runtime inventory missing")
        return failures
    names: list[str] = []
    for index, row in enumerate(runtime):
        if not isinstance(row, Mapping):
            failures.append(f"runtime[{index}] is not an object")
            continue
        name = str(row.get("name") or "")
        names.append(name)
        present = row.get("present")
        if present is True:
            if row.get("disabled") is not False or not row.get("path") or row.get("disabled_reason"):
                failures.append(f"runtime row contradictory: {name}")
        elif present is False:
            if row.get("disabled") is not True or row.get("path") is not None or not row.get("disabled_reason"):
                failures.append(f"runtime row contradictory: {name}")
        else:
            failures.append(f"runtime row contradictory: {name}")
    if sorted(names) != sorted(REQUIRED_RUNTIME_NAMES):
        failures.append("runtime denominator mismatch")
    return failures


def collector_identity() -> dict[str, Any]:
    collector_path = Path(__file__).resolve()
    executable = Path(sys.executable) if sys.executable else None
    python_identity: dict[str, Any] = {
        "path": str(executable) if executable else None,
        "sha256": None,
        "version": sys.version.split()[0],
    }
    if executable is not None:
        try:
            python_identity["sha256"] = sha256_file(executable)
        except OSError:
            python_identity["sha256"] = None
    return {
        "schema": COLLECTOR_SCHEMA,
        "platform": "linux",
        "source_path": str(collector_path),
        "source_sha256": sha256_file(collector_path),
        "python_executable": python_identity,
    }


def declared_coordinates(
    *, manifest_path: Path | None = None, sums_path: Path | None = None
) -> dict[str, Any]:
    """Read the immutable seed declaration that binds this collector.

    The manifest is not trusted on its own. seed/sha256sums.txt binds its exact
    bytes and the seed identity is the digest of that sum file, so widening the
    declared host ids cannot be done without producing a different seed.
    """
    manifest_path = SEED_MANIFEST_PATH if manifest_path is None else manifest_path
    sums_path = SEED_SUMS_PATH if sums_path is None else sums_path
    try:
        raw = manifest_path.read_bytes()
    except OSError as exc:
        raise CoordinateError(
            f"seed manifest is unreadable, so no host coordinate is declared: {manifest_path}"
        ) from exc
    try:
        sums = sums_path.read_bytes()
    except OSError as exc:
        raise CoordinateError(
            f"seed checksum file is unreadable, so the declaration is unbound: {sums_path}"
        ) from exc
    expected: str | None = None
    for line in sums.decode("ascii", errors="replace").splitlines():
        digest, separator, name = line.partition("  ")
        if separator and name.strip() == SEED_MANIFEST_NAME:
            expected = digest.strip().lower()
    if expected is None:
        raise CoordinateError(f"{SEED_SUMS_NAME} does not bind {SEED_MANIFEST_NAME}")
    observed = sha256_bytes(raw)
    if observed != expected:
        raise CoordinateError(
            f"seed manifest digest mismatch: {SEED_SUMS_NAME} binds {expected}, observed {observed}"
        )
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoordinateError(f"seed manifest is not readable JSON: {exc}") from exc
    observation = manifest.get("observation")
    if not isinstance(observation, Mapping):
        raise CoordinateError("seed manifest declares no observation contract")
    host_ids = tuple(str(item) for item in observation.get("declared_host_ids") or ())
    if not host_ids:
        raise CoordinateError("seed manifest declares no host ids")
    output_name = str(observation.get("expected_output_name") or "")
    if "<host-id>" not in output_name:
        raise CoordinateError("seed manifest declares no <host-id> output name contract")
    return {
        "host_ids": host_ids,
        "output_name": output_name,
        "manifest_sha256": observed,
        "seed_id": sha256_bytes(sums),
    }


def normalized_basename(out_file: Path | str) -> str:
    """The final path component, with separators and . / .. resolved textually."""
    return os.path.basename(os.path.normpath(str(out_file)))


def validate_coordinates(
    host_id: str, out_file: Path | str, *, coordinates: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Enforce the declared role and output name before anything is read.

    The seed README and manifest have always said --host-id is one of three
    Estate roles and --out-file ends in <host-id>.json. This is where that stops
    being documentation: it runs before any host surface is read and before any
    directory or temporary file exists, so a substituted coordinate never
    reaches a filesystem.
    """
    resolved = dict(coordinates) if coordinates is not None else declared_coordinates()
    host_id = str(host_id).strip()
    if not host_id:
        raise CoordinateError("host_id required")
    declared = tuple(resolved["host_ids"])
    if host_id not in declared:
        raise CoordinateError(
            f"host_id {host_id!r} is not declared by the seed manifest; "
            f"declared host ids are {', '.join(declared)}"
        )
    expected_name = str(resolved["output_name"]).replace("<host-id>", host_id)
    observed_name = normalized_basename(out_file)
    if observed_name != expected_name:
        raise CoordinateError(
            "out-file basename must be the declared observation name: "
            f"expected {expected_name}, observed {observed_name}"
        )
    return resolved


# ------------------------------------------------------ observed-host identity
def fingerprint_component(value: Any) -> str:
    if value is None or value is True or value is False:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value if item is not None)
    return " ".join(str(value).split()).strip().lower()


def fingerprint_joined(*values: Any) -> str:
    return "|".join(fingerprint_component(value) for value in values)


def accelerator_identities(observation: Mapping[str, Any]) -> list[str]:
    """Globally unique accelerator identifiers, NVIDIA UUIDs included."""
    graphics = observation.get("graphics")
    graphics = graphics if isinstance(graphics, Mapping) else {}
    nvidia = graphics.get("nvidia") if isinstance(graphics.get("nvidia"), list) else []
    adapters = graphics.get("adapters") if isinstance(graphics.get("adapters"), list) else []
    identities: list[str] = []
    for row in list(nvidia) + list(adapters):
        if not isinstance(row, Mapping):
            continue
        identity = fingerprint_component(row.get("uuid"))
        if identity:
            identities.append(identity)
    return sorted(set(identities))


def host_fingerprint_components(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Body-safe physical identity of the observed machine.

    Every input is a field the privacy law already admits into the body, and
    host_id, observed_at, the clock samples, and the collector and runtime rows
    are excluded: those are what an operator edits to relabel one machine as
    three.
    """
    system = observation.get("system")
    system = system if isinstance(system, Mapping) else {}
    firmware = system.get("firmware")
    firmware = firmware if isinstance(firmware, Mapping) else {}
    memory = observation.get("memory")
    memory = memory if isinstance(memory, Mapping) else {}
    storage = observation.get("storage")
    storage = storage if isinstance(storage, Mapping) else {}
    graphics = observation.get("graphics")
    graphics = graphics if isinstance(graphics, Mapping) else {}
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
            if isinstance(row, Mapping)
        ),
        "memory_total_bytes": memory.get("total_bytes"),
        "physical_disks": sorted(
            fingerprint_joined(row.get("model"), row.get("size_bytes"))
            for row in disks
            if isinstance(row, Mapping)
        ),
        "display_adapters": sorted(
            fingerprint_joined(row.get("name"), row.get("pnp_device_id") or row.get("bus_id"))
            for row in adapters
            if isinstance(row, Mapping)
        ),
        "accelerator_identities": accelerator_identities(observation),
    }


def observed_host_fingerprint(observation: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(host_fingerprint_components(observation)))


def build_receipt(
    observation: Mapping[str, Any],
    published: Path,
    coordinates: Mapping[str, Any],
) -> dict[str, Any]:
    """The body-free return receipt issue #151 requires for the W01 join.

    It binds identities and digests and nothing else. No hostname, device name,
    model, capacity, path, kernel string, or accelerator identifier from the
    observation body appears here, so the receipt can be published in the open
    while the body it addresses stays on the host that produced it.
    """
    collector = observation.get("collector")
    collector = collector if isinstance(collector, Mapping) else {}
    python_identity = collector.get("python_executable")
    python_identity = python_identity if isinstance(python_identity, Mapping) else {}
    identities = accelerator_identities(observation)
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "observation_schema": observation.get("schema"),
        "collector_schema": collector.get("schema"),
        "platform": observation.get("platform"),
        "host_id": observation.get("host_id"),
        "observed_at": observation.get("observed_at"),
        "observation_sha256": observation.get("observation_sha256"),
        "observation_file_name": published.name,
        "observation_file_sha256": sha256_file(published),
        "observation_file_bytes": published.stat().st_size,
        "host_fingerprint_sha256": observed_host_fingerprint(observation),
        "accelerator_identity_sha256": sorted(
            sha256_bytes(identity.encode("utf-8")) for identity in identities
        ),
        "accelerator_identity_count": len(identities),
        "collector_source_sha256": collector.get("source_sha256"),
        "python_executable_sha256": python_identity.get("sha256"),
        "seed_id": coordinates.get("seed_id"),
        "seed_manifest_sha256": coordinates.get("manifest_sha256"),
        "carries_observation_body": False,
        "claim_boundary": (
            "Body-free return receipt. It binds the identity and digests of one "
            "observation so the join can be recorded in the open without "
            "publishing the observed body. It carries no host, device, or "
            "accelerator identifier, admits no worker, and cannot substitute "
            "for the observation it addresses."
        ),
    }
    receipt["receipt_sha256"] = sha256_bytes(
        canonical_bytes({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    )
    return receipt


def build_observation(host_id: str) -> tuple[dict[str, Any], list[str]]:
    host_id = host_id.strip()
    if not host_id:
        raise ValueError("host_id required")
    observation: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at": utc_now(),
        "platform": "linux",
        "host_id": host_id,
        "collector": collector_identity(),
        "system": linux_system_identity(),
        "cpu": parse_cpuinfo(),
        "memory": collect_memory(),
        "storage": collect_storage(),
        "graphics": {
            "adapters": parse_lspci_adapters(),
            "nvidia": parse_nvidia_rows(),
        },
        "network": {
            "adapters": collect_network_adapters(),
            "addresses_collected": False,
        },
        "runtime": runtime_rows(),
        "clock": collect_clock_observations(),
        "surfaces": collect_surfaces(),
        "privacy": {
            "serial_numbers_collected": False,
            "mac_addresses_collected": False,
            "ip_addresses_collected": False,
            "machine_guid_collected": False,
        },
        "claim_boundary": (
            "Read-only local observation of one host. It admits no worker, "
            "measures no path cost, proves no cross-host clock relation, and "
            "cannot substitute for a declared estate inventory."
        ),
    }
    observation["observation_sha256"] = sha256_bytes(
        canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
    )
    return observation, required_fields_for_observation(observation)


def temp_path_for(path: Path) -> Path:
    """The historical deterministic temporary name, same directory as the output.

    Nothing is written through this name any more: publication creates an
    unpredictable temporary exclusively. The name is still recognized so that
    residue from an interrupted older run is cleared instead of being left to
    masquerade as output.
    """
    return path.with_name(f".{path.name}.tmp")


def link_kind(path: Path) -> str:
    """Classify an existing entry without ever following it."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable entry"
    if stat.S_ISLNK(info.st_mode):
        return "symbolic link"
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return "reparse point"
    if not stat.S_ISREG(info.st_mode):
        return "non-regular file"
    if getattr(info, "st_nlink", 1) > 1:
        return "hard link to an unlisted object"
    return "regular file"


def alias_failures(path: Path, role: str) -> list[str]:
    """Refuse to act on any name that is an alias for something else.

    Removing or replacing an alias reaches an object the operator never listed.
    A symbolic link, a hard link, and a Windows reparse point all do that, so
    each refuses here and the run publishes nothing.
    """
    kind = link_kind(path)
    if kind in {"absent", "regular file"}:
        return []
    return [
        f"{role} {path.name} is a {kind}: acting on it would leave the declared "
        "output boundary, so nothing was written or removed"
    ]


def parent_kind(path: Path) -> str:
    """Classify one parent component without following that component.

    Components are visited from the filesystem root toward the supplied output
    name.  That ordering matters: once a component is known to be a link or a
    reparse point, no descendant is inspected through it.
    """
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable entry"
    if stat.S_ISLNK(info.st_mode):
        return "symbolic link"
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return "reparse point"
    if not stat.S_ISDIR(info.st_mode):
        return "non-directory entry"
    return "directory"


def parent_failures(path: Path) -> list[str]:
    """Refuse an alias anywhere in the lexical parent chain.

    ``Path.resolve`` and ``realpath`` are intentionally absent.  Relative paths
    are anchored at the current working directory without canonicalizing it,
    and lexical ``.``/``..`` components remain in the walk.
    """
    lexical = path if path.is_absolute() else Path.cwd() / path
    parent = lexical.parent
    chain = [*reversed(parent.parents), parent]
    for component in chain:
        kind = parent_kind(component)
        if kind == "absent":
            break
        if kind != "directory":
            return [
                f"output parent component {component} is a {kind}: following it "
                "would leave the declared output boundary, so nothing was written or removed"
            ]
    return []


def boundary_failures(path: Path) -> list[str]:
    """Every refusal the declared output coordinate can raise before writing."""
    failures = parent_failures(path)
    if failures:
        # Even lstat of the final name would traverse an aliased parent.  Stop at
        # the first unlawful component and never inspect a descendant through it.
        return failures
    return alias_failures(path, "output path") + alias_failures(
        temp_path_for(path), "deterministic temporary name"
    )


def discard_temp(path: Path) -> None:
    """Remove ordinary interrupted residue so it can never be published.

    Only an ordinary single-link regular file is removed. Anything else is an
    alias for an object outside the boundary and was already refused.
    """
    if parent_failures(path):
        return
    temp = temp_path_for(path)
    if link_kind(temp) != "regular file":
        return
    try:
        temp.unlink()
    except OSError:
        pass


def fsync_directory(path: Path) -> bool:
    """fsync the containing directory so the published name itself is durable.

    Windows exposes no directory handle to fsync; there the rename is recorded
    by the filesystem metadata journal and this reports False.
    """
    if os.name == "nt":
        return False
    handle = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)
    return True


def write_atomic_json(payload: Mapping[str, Any], path: Path) -> Path:
    """Publish through a fresh exclusive temporary, fsync, rename, fsync dir.

    The temporary is created with O_CREAT|O_EXCL under an unpredictable name,
    so a pre-existing alias at a guessable path can never be the inode this
    writes through. open("w") on a deterministic name truncates whatever inode
    that name already resolves to, which is exactly how a hard link to an
    unlisted file was mutated by an earlier version of this collector.
    """
    for failure in boundary_failures(path):
        raise CollectorError(failure)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CollectorError(f"output parent cannot be created: {exc}") from exc
    # Reclassify after creation.  This both covers the newly created components
    # and refuses if an existing component changed while mkdir was in flight.
    for failure in boundary_failures(path):
        raise CollectorError(failure)
    data = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor, raw_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp = Path(raw_name)
    try:
        links = getattr(os.fstat(descriptor), "st_nlink", 1)
        if links != 1:
            raise CollectorError(
                f"exclusive temporary already carries {links} links; publication refused"
            )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    fsync_directory(path.parent)
    return path


def receipt_path_for(out_file: Path, host_id: str) -> Path:
    """The body-free receipt published beside the observation it addresses."""
    return out_file.with_name(f"{host_id}{RECEIPT_SUFFIX}")


def collect(
    host_id: str, out_file: Path, *, coordinates: Mapping[str, Any] | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Validate the coordinate, build, then publish. Refusal publishes nothing."""
    resolved_coordinates = validate_coordinates(host_id, out_file, coordinates=coordinates)
    out_path = Path(out_file).expanduser()
    target = out_path
    receipt_target = receipt_path_for(target, host_id.strip())
    coordinate_failures = list(
        dict.fromkeys(boundary_failures(target) + boundary_failures(receipt_target))
    )
    if coordinate_failures:
        return {}, coordinate_failures

    observation, failures = build_observation(host_id)
    failures = list(failures)
    if failures:
        discard_temp(target)
        discard_temp(receipt_target)
        return observation, failures
    discard_temp(target)
    discard_temp(receipt_target)
    published = write_atomic_json(observation, target)
    write_atomic_json(build_receipt(observation, published, resolved_coordinates), receipt_target)
    return observation, []


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a read-only Linux host observation")
    parser.add_argument("--host-id", required=True, help="Host id declared by the seed manifest")
    parser.add_argument(
        "--out-file",
        required=True,
        help="Observation JSON destination path, whose basename must be <host-id>.json",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _, failures = collect(args.host_id, Path(args.out_file))
    except CollectorError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 3
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    if failures:
        print(json.dumps({"ok": False, "failures": failures}, indent=2))
        return 1
    output = Path(args.out_file).expanduser()
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "receipt": str(receipt_path_for(output, args.host_id.strip())),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
