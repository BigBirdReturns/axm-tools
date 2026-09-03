from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lab import qualify_estate, scaffold_function, start_protocol  # noqa: E402
from planner import PlannerError, canonical_bytes, read_json, sha256_json  # noqa: E402


def observation(host_id: str, gpu_uuid: str, schema: str = "axm-community-lab/windows-host-observation@1") -> dict:
    return {
        "schema": schema,
        "observed_at": "2026-08-05T00:00:00Z",
        "host_id": host_id,
        "system": {"computer_name": host_id, "os_caption": "Windows 11"},
        "cpu": [{"name": "fixture cpu", "processor_id": host_id}],
        "memory": {"total_bytes": 34359738368, "modules": []},
        "storage": {"physical_disks": [{"model": "fixture nvme", "size_bytes": 1000}], "logical_volumes": []},
        "graphics": {
            "adapters": [
                {
                    "name": "Intel fixture graphics",
                    "pnp_device_id": f"PCI\\VEN_8086&DEV_{host_id}",
                    "vendor_guess": "Intel",
                    "role_candidate": "igpu",
                },
                {
                    "name": "NVIDIA GeForce fixture",
                    "pnp_device_id": f"PCI\\VEN_10DE&DEV_{host_id}",
                    "vendor_guess": "NVIDIA",
                    "role_candidate": "dgpu",
                },
            ],
            "nvidia": [{"uuid": gpu_uuid, "name": "NVIDIA GeForce fixture", "pci_bus_id": "0000:01:00.0"}],
        },
        "network": {"adapters": [{"name": "Ethernet", "link_speed": "1 Gbps"}]},
        "runtime": [
            {"name": "python", "present": True, "path": "C:\\Python\\python.exe", "disabled": False, "disabled_reason": None},
            {"name": "git", "present": True, "path": "C:\\Git\\git.exe", "disabled": False, "disabled_reason": None},
            {"name": "ollama", "present": True, "path": "C:\\Ollama\\ollama.exe", "disabled": False, "disabled_reason": None},
            {"name": "nvidia-smi", "present": True, "path": "C:\\NVIDIA\\nvidia-smi.exe", "disabled": False, "disabled_reason": None},
            {"name": "docker", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},
            {"name": "wsl", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},
        ],
        "clock": {"stopwatch_frequency_hz": 10000000, "samples": []},
    }


def linux_observation(host_id: str, gpu_uuid: str | None = "GPU-LINUX", *, runtime_reason: str | None = None) -> dict:
    collector = Path(SCRIPTS / "collect-linux.py")
    collector_sha = hashlib.sha256(collector.read_bytes()).hexdigest()
    rows = [
        {"name": "python", "present": True, "path": "/usr/bin/python", "disabled": False, "disabled_reason": None},
        {"name": "git", "present": True, "path": "/usr/bin/git", "disabled": False, "disabled_reason": None},
        {"name": "ollama", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},
        {"name": "docker", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},
        {"name": "wsl", "present": False, "path": None, "disabled": True, "disabled_reason": runtime_reason or "not applicable on a native Linux host"},
        {"name": "nvidia-smi", "present": True, "path": "/usr/bin/nvidia-smi", "disabled": False, "disabled_reason": None},
    ]
    return {
        "schema": "axm-community-lab/host-observation@2",
        "observed_at": "2026-08-05T00:00:00Z",
        "platform": "linux",
        "host_id": host_id,
        "collector": {
            "schema": "axm-community-lab/host-observation-collector@1",
            "platform": "linux",
            "source_path": str(collector),
            "source_sha256": collector_sha,
            "python_executable": {
            "path": os.path.realpath(sys.executable),
            "sha256": sha256_file(Path(sys.executable)),
            },
        },
        "system": {
            "hostname": "heavy-host-b",
            "kernel": "6.6.0",
            "os_release": "Ubuntu 24.04",
            "architecture": "x86_64",
        },
        "cpu": [{"name": "Intel Xeon", "cores": 8, "logical_processors": 16}],
        "memory": {"total_bytes": 34359738368, "modules": []},
        "storage": {"physical_disks": [{"model": "NVMe", "size_bytes": 2000000000}], "logical_volumes": []},
        "graphics": {
            "adapters": [
                {
                    "name": "Intel Arc",
                    "vendor_guess": "Intel",
                    "pnp_device_id": "0000:00:02.0",
                    "role_candidate": "igpu-candidate",
                }
            ],
            "nvidia": [{"uuid": gpu_uuid, "name": "NVIDIA GeForce 4090", "pci_bus_id": "0000:01:00.0"}],
        },
        "network": {"adapters": [{"name": "eth0"}], "addresses_collected": False},
        "runtime": rows,
        "clock": {"stopwatch_frequency_hz": 1000000000, "samples": []},
        "surfaces": {
            "files": {"proc_cpuinfo": {"path": "/proc/cpuinfo", "readable": True}},
            "tools": {"nvidia-smi": {"available": True, "path": "/usr/bin/nvidia-smi", "note": None}},
        },
        "privacy": {
            "serial_numbers_collected": False,
            "mac_addresses_collected": False,
            "ip_addresses_collected": False,
            "machine_guid_collected": False,
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def observation_digest(observation: dict) -> str:
    return hashlib.sha256(canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})).hexdigest()


class LabTests(unittest.TestCase):
    def write_observation(self, base: Path, item: dict, host_id: str) -> Path:
        item["observation_sha256"] = observation_digest(item)
        path = base / f"{host_id}.json"
        path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
        return path

    def write_observation_bytes(self, path: Path, item: dict) -> Path:
        """Write an observation exactly as given; the stored digest is never rebound."""
        path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
        return path

    def test_scaffold_binds_adapter_digest(self):
        with tempfile.TemporaryDirectory() as raw:
            contract_path, fixture_path = scaffold_function("test-function", Path(raw), model="qwen3.5:9b-q4_K_M", host="http://127.0.0.1:11434")
            contract = read_json(contract_path)
            self.assertEqual(contract["implementation_sha256"], sha256_json(contract["implementation"]))
            self.assertEqual(read_json(fixture_path)["function_id"], "test-function")

    def test_three_fixture_hosts_qualify_inventory_and_devices(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                path = self.write_observation(base, observation(host_id, gpu_uuid), host_id)
                files.append(path)
            receipt_path, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T01:00:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(
                {item["capability"] for item in receipt["supports"]},
                {"host_inventory", "device_identity"},
            )
            self.assertTrue(receipt_path.is_file())

    def test_mixed_windows_linux_qualify_pass(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A")):
                files.append(self.write_observation(base, observation(host_id, gpu_uuid), host_id))
            files.append(self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T01:15:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(
                {item["capability"] for item in receipt["supports"]},
                {"host_inventory", "device_identity"},
            )

    def test_disabled_runtime_without_reason_blocks_census(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                item = observation(host_id, gpu_uuid)
                if host_id == "heavy-host-a":
                    item["runtime"][4]["disabled_reason"] = None
                path = self.write_observation(base, item, host_id)
                files.append(path)
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T01:30:00Z",
                ingest=False,
            )
            check = next(
                row for row in receipt["checks"]
                if row["id"] == "disabled-components-carry-reasons"
            )
            self.assertFalse(check["pass"])
            self.assertNotEqual(receipt["status"], "PASS")

    def test_missing_runtime_row_blocks_qualification(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                item = observation(host_id, gpu_uuid)
                if host_id == "heavy-host-b":
                    item["runtime"] = [row for row in item["runtime"] if row["name"] != "wsl"]
                files.append(self.write_observation(base, item, host_id))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T01:40:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["checks"][2]["pass"], False)

    def test_duplicate_runtime_row_blocks_qualification(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                item = observation(host_id, gpu_uuid)
                if host_id == "control-host":
                    item["runtime"].append(item["runtime"][0])
                files.append(self.write_observation(base, item, host_id))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T01:50:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")

    def test_linux_runtime_denominator_and_wsl_inapplicability(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            good_windows = observation("control-host", "GPU-4060")
            good_windows["runtime"][5]["disabled_reason"] = "not applicable on a native Linux host"
            files.append(self.write_observation(base, good_windows, "control-host"))
            files.append(self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"))
            linux = linux_observation("heavy-host-b", "GPU-3090-B", runtime_reason=None)
            linux["runtime"][4]["disabled_reason"] = "wrong value"
            files.append(self.write_observation(base, linux, "heavy-host-b"))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:05:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["checks"][2]["pass"], False)

    def test_missing_memory_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                item = observation(host_id, gpu_uuid)
                if host_id == "heavy-host-b":
                    item["memory"]["total_bytes"] = 0
                files.append(self.write_observation(base, item, host_id))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:20:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertIn(
                "heavy-host-b: memory.total_bytes missing",
                receipt["unresolved"]["host_inventory"],
            )
            check = next(row for row in receipt["checks"] if row["id"] == "stable-host-inventory")
            self.assertFalse(check["pass"])

    def test_observation_digest_tamper_is_rejected(self):
        # the digest is bound first, then the body is altered to a still-valid value:
        # only a digest comparison can catch this
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
            ]
            tampered = observation("heavy-host-b", "GPU-3090-B")
            tampered["observation_sha256"] = observation_digest(tampered)
            tampered["memory"]["total_bytes"] = tampered["memory"]["total_bytes"] * 2
            files.append(self.write_observation_bytes(base / "heavy-host-b.json", tampered))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:20:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertEqual(
                receipt["unresolved"]["observation_digests"],
                ["heavy-host-b: observation_sha256 mismatch"],
            )
            # nothing else may explain the refusal: the tampered value is itself valid
            self.assertEqual(receipt["unresolved"]["general"], [])
            self.assertEqual(receipt["unresolved"]["host_inventory"], [])
            self.assertEqual(receipt["unresolved"]["device_identity"], [])

    def test_missing_observation_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
            ]
            undigested = observation("heavy-host-b", "GPU-3090-B")
            undigested.pop("observation_sha256", None)
            files.append(self.write_observation_bytes(base / "heavy-host-b.json", undigested))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:20:30Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertIn(
                "heavy-host-b: observation_sha256 missing",
                receipt["unresolved"]["observation_digests"],
            )
            self.assertEqual(receipt["unresolved"]["general"], [])
            self.assertEqual(receipt["unresolved"]["host_inventory"], [])

    def test_duplicate_host_observation_is_rejected(self):
        # product law F: every expected host exactly once
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                files.append(self.write_observation(base, observation(host_id, gpu_uuid), host_id))
            second = observation("control-host", "GPU-4060")
            second["observed_at"] = "2026-08-05T00:30:00Z"
            second["observation_sha256"] = observation_digest(second)
            files.append(self.write_observation_bytes(base / "control-host-second.json", second))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:25:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["unresolved"]["general"], ["duplicate host_id: control-host"])
            check = next(row for row in receipt["checks"] if row["id"] == "three-distinct-host-records")
            self.assertFalse(check["pass"])
            # every submitted host is otherwise complete: duplication alone must refuse
            self.assertEqual(receipt["unresolved"]["host_inventory"], [])
            self.assertEqual(receipt["unresolved"]["observation_digests"], [])

    def test_linux_collector_source_digest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
            ]
            item = linux_observation("heavy-host-b", "GPU-3090-B")
            item["collector"]["source_sha256"] = "0" * 64
            files.append(self.write_observation(base, item, "heavy-host-b"))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:40:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(any("source_identity" in row for row in receipt["unresolved"]["source_identity"]))

    def test_missing_physical_disks_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
            ]
            item = linux_observation("heavy-host-b", "GPU-3090-B")
            item["storage"]["physical_disks"] = []
            files.append(self.write_observation(base, item, "heavy-host-b"))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T02:55:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")

    def test_declared_igpu_without_observed_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            item = linux_observation("control-host", "GPU-4060")
            item["host_id"] = "heavy-host-a"
            item["graphics"]["adapters"] = []
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, item, "heavy-host-a"),
                self.write_observation(base, observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T03:10:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")

    def test_declared_nvidia_uuid_missing_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
            ]
            item = linux_observation("heavy-host-b", None)
            files.append(self.write_observation(base, item, "heavy-host-b"))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T03:25:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")

    def test_private_fields_must_be_absent(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            bad = observation("control-host", "GPU-4060")
            bad["network"]["serial_numbers_collected"] = "bad"
            files[0] = self.write_observation(base, bad, "control-host")
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T03:40:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(any("prohibited private field" in item for item in receipt["unresolved"]["privacy"]))

    def test_synthetic_n01_observation_cannot_replace_physical(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            intended = linux_observation("heavy-host-b", "GPU-SYNTH")
            intended["collector"]["source_sha256"] = "deadbeef" * 8
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, intended, "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:10:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertIn("collector", receipt["unresolved"]["source_identity"][0])

    def test_contradictory_present_disabled_state_blocks_qualification(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = []
            for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                item = observation(host_id, gpu_uuid)
                if host_id == "heavy-host-a":
                    item["runtime"][0]["disabled"] = True
                files.append(self.write_observation(base, item, host_id))
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T03:45:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            check = next(row for row in receipt["checks"] if row["id"] == "disabled-components-carry-reasons")
            self.assertFalse(check["pass"])

    def test_mac_retention_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            bad = observation("control-host", "GPU-4060")
            bad["network"]["adapters"][0]["note"] = "00:00:5e:00:53:01"
            files = [
                self.write_observation(base, bad, "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T03:50:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(any("MAC" in item for item in receipt["unresolved"]["privacy"]))

    def test_ip_retention_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            for retained in ("192.0.2.50", "2001:db8::abcd:1234"):
                bad = observation("control-host", "GPU-4060")
                bad["network"]["adapters"][0]["note"] = retained
                files = [
                    self.write_observation(base, bad, "control-host"),
                    self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                    self.write_observation(base, observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
                ]
                _, receipt = qualify_estate(
                    observations=files,
                    state_dir=state,
                    generated_at=f"2026-08-05T03:5{5 if ':' in retained else 6}:00Z",
                    ingest=False,
                )
                self.assertNotEqual(receipt["status"], "PASS")
                self.assertTrue(
                    any("IP" in item or "IPv6" in item for item in receipt["unresolved"]["privacy"]),
                    msg=f"no IP privacy refusal recorded for {retained}",
                )

    def test_machine_guid_retention_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            bad = observation("control-host", "GPU-4060")
            bad["system"]["machine_guid"] = "12345678-1234-1234-1234-123456789abc"
            files = [
                self.write_observation(base, bad, "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:00:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(any("machine_guid" in item for item in receipt["unresolved"]["privacy"]))

    def test_intended_inventory_cannot_replace_observation(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:05:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(any("heavy-host-b" in item for item in receipt["unresolved"]["general"]))
            check = next(row for row in receipt["checks"] if row["id"] == "three-distinct-host-records")
            self.assertFalse(check["pass"])

    def test_existing_windows_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            source_path = base / "control-host.json"
            raw_payload = observation("control-host", "GPU-4060")
            raw_payload["observation_sha256"] = observation_digest(raw_payload)
            source_path.write_text(json.dumps(raw_payload, indent=2) + "\n", encoding="utf-8")
            files = [
                source_path,
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            receipt_path, _ = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:25:00Z",
                ingest=False,
            )
            observed = sha256_file(Path(source_path))
            copied = Path(receipt_path.parent) / "inputs" / "control-host.json"
            copied_digest = sha256_file(copied)
            self.assertEqual(observed, copied_digest)

    def test_collector_uses_bom_free_utf8(self):
        source = (SCRIPTS / "collect-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("System.Text.UTF8Encoding($false)", source)
        self.assertIn("[IO.File]::WriteAllText", source)
        self.assertNotIn("Set-Content -LiteralPath $destination -Encoding UTF8", source)

    def test_serial_number_retention_is_refused(self):
        """A disk serial is the classic collector leak; it must refuse."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            bad = observation("control-host", "GPU-4060")
            bad["storage"]["physical_disks"][0]["serial_number"] = "S3Z9NB0M123456"
            files = [
                self.write_observation(base, bad, "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:30:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(
                any("serial_number" in item for item in receipt["unresolved"]["privacy"]),
                msg="no serial refusal recorded",
            )

    def test_explicit_privacy_refusals_are_compliance_not_retention(self):
        """A negative declaration is the collector obeying the law.

        Regression witness: a prohibited-marker key whose value is empty or
        negative must not be read as a retained identifier.
        """
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            item = linux_observation("heavy-host-b", "GPU-3090-B")
            item["storage"]["physical_disks"][0]["serial_number"] = None
            item["network"]["mac_addresses"] = []
            item["system"]["machine_guid"] = ""
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, item, "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:35:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["unresolved"]["privacy"], [])
            self.assertEqual(receipt["status"], "PASS")

    def test_prose_and_bus_identifiers_are_not_mistaken_for_addresses(self):
        """PCI ids, timestamps, and prose colons must not read as addresses."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            item = linux_observation("heavy-host-b", "GPU-3090-B")
            item["graphics"]["nvidia"][0]["pci_bus_id"] = "00000000:01:00.0"
            item["system"]["note"] = "Usage:: collected 2026-08-05T01:00:00Z from 0000:01:00.0"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, item, "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:40:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["unresolved"]["privacy"], [])
            self.assertEqual(receipt["status"], "PASS")

    def test_windows_observation_is_not_republished_as_v2(self):
        """@1 bytes are normalized in memory only; the stored body is untouched."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            source_path = base / "control-host.json"
            payload = observation("control-host", "GPU-4060")
            payload["observation_sha256"] = observation_digest(payload)
            original_bytes = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            source_path.write_bytes(original_bytes)
            files = [
                source_path,
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            receipt_path, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:45:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["status"], "PASS")

            # The operator's own file is never rewritten.
            self.assertEqual(source_path.read_bytes(), original_bytes)

            # Neither is the copy the run retains as its input evidence.
            copied = receipt_path.parent / "inputs" / "control-host.json"
            self.assertEqual(copied.read_bytes(), original_bytes)
            stored = json.loads(copied.read_bytes().decode("utf-8"))
            self.assertEqual(stored["schema"], "axm-community-lab/windows-host-observation@1")
            self.assertNotIn("platform", stored, "no @2 field may be inferred into a stored @1 body")
            self.assertNotIn("collector", stored)
            self.assertEqual(stored["observation_sha256"], payload["observation_sha256"])

    def test_mixed_platform_rows_are_explicit_in_the_aggregate(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            receipt_path, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:50:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["status"], "PASS")
            aggregate = read_json(receipt_path.parent / "estate-observation.json")
            self.assertEqual(
                aggregate["platform_rows"],
                {"control-host": "windows", "heavy-host-a": "windows", "heavy-host-b": "linux"},
            )
            self.assertEqual(aggregate["host_count_observed"], 3)
            self.assertEqual(
                aggregate["accelerator_domains_resolved"],
                aggregate["accelerator_domains_expected"],
            )

    def test_aggregate_digest_recomputes_over_canonical_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            receipt_path, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T04:55:00Z",
                ingest=False,
            )
            aggregate = read_json(receipt_path.parent / "estate-observation.json")
            recomputed = sha256_json(
                {k: v for k, v in aggregate.items() if k not in {"generated_at", "observation_sha256"}}
            )
            self.assertEqual(aggregate["observation_sha256"], recomputed)
            self.assertEqual(receipt["metadata"]["observation_sha256"], aggregate["observation_sha256"])

            # Every per-host source digest recomputes from the retained bytes.
            for host_id, digest in aggregate["source_digests"].items():
                stored = read_json(receipt_path.parent / "inputs" / f"{host_id}.json")
                self.assertEqual(stored["observation_sha256"], digest)

    def test_unresolved_device_domain_blocks_pass_but_keeps_host_inventory(self):
        """An unresolved declared domain refuses device identity, explicitly."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            item = linux_observation("heavy-host-b", "GPU-3090-B")
            item["graphics"]["nvidia"] = []
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, item, "heavy-host-b"),
            ]
            receipt_path, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T05:00:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["status"], "PARTIAL")
            self.assertEqual({row["capability"] for row in receipt["supports"]}, {"host_inventory"})
            self.assertTrue(receipt["unresolved"]["device_identity"])
            aggregate = read_json(receipt_path.parent / "estate-observation.json")
            self.assertLess(
                aggregate["accelerator_domains_resolved"],
                aggregate["accelerator_domains_expected"],
            )

    def test_linux_observation_without_platform_is_not_admitted(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            item = linux_observation("heavy-host-b", "GPU-3090-B")
            del item["platform"]
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, item, "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T05:05:00Z",
                ingest=False,
            )
            self.assertNotEqual(receipt["status"], "PASS")
            self.assertTrue(any("heavy-host-b" in row for row in receipt["unresolved"]["general"]))

    def test_synthetic_fixture_cannot_establish_a_physical_three_host_pass(self):
        """A passing fixture join is source behaviour, not a physical census.

        The receipt must keep saying so: its claim boundary refuses to admit
        workers or infer roles, and nothing in it asserts a physical execution.
        """
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            files = [
                self.write_observation(base, observation("control-host", "GPU-4060"), "control-host"),
                self.write_observation(base, observation("heavy-host-a", "GPU-3090-A"), "heavy-host-a"),
                self.write_observation(base, linux_observation("heavy-host-b", "GPU-3090-B"), "heavy-host-b"),
            ]
            _, receipt = qualify_estate(
                observations=files,
                state_dir=state,
                generated_at="2026-08-05T05:10:00Z",
                ingest=False,
            )
            self.assertEqual(receipt["status"], "PASS")
            boundary = receipt["claim_boundary"]
            self.assertIn("does not admit workers", boundary)
            self.assertIn("infer missing accelerator roles", boundary)
            self.assertNotIn("physical", json.dumps(receipt["supports"]))

    def test_blocked_experiment_cannot_open_run(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(PlannerError):
                start_protocol("qualify-three-host-fabric", Path(raw), generated_at="2026-08-05T02:00:00Z")


if __name__ == "__main__":
    unittest.main()
