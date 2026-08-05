from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lab import qualify_estate, scaffold_function, start_protocol  # noqa: E402
from planner import PlannerError, read_json, sha256_json  # noqa: E402


def observation(host_id: str, gpu_uuid: str) -> dict:
    return {
        "schema": "axm-community-lab/windows-host-observation@1",
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
        "clock": {"stopwatch_frequency_hz": 10000000, "samples": []},
    }


class LabTests(unittest.TestCase):
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
                path = base / f"{host_id}.json"
                path.write_text(json.dumps(observation(host_id, gpu_uuid), indent=2) + "\n", encoding="utf-8")
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

    def test_blocked_experiment_cannot_open_run(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(PlannerError):
                start_protocol("qualify-three-host-fabric", Path(raw), generated_at="2026-08-05T02:00:00Z")


if __name__ == "__main__":
    unittest.main()
