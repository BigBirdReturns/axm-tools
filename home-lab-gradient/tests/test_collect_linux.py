from __future__ import annotations

import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_collector():
    spec = importlib.util.spec_from_file_location("collect_linux_module", str(SCRIPTS / "collect-linux.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def lsblk_output():
    return json.dumps(
        {
            "blockdevices": [
                {"name": "sda", "type": "disk", "size": 2_000_000_000, "model": "SAMSUNG", "rota": 0},
                {"name": "sda1", "type": "part", "size": 100_000_000, "model": None, "rota": 0},
            ]
        }
    )


class CollectLinuxTests(unittest.TestCase):
    def setUp(self):
        self.collector = load_collector()

    def mock_sources(self, base: Path):
        os_release = base / "etc" / "os-release"
        cpuinfo = base / "proc" / "cpuinfo"
        meminfo = base / "proc" / "meminfo"
        dmi = base / "sys" / "class" / "dmi" / "id"
        net = base / "sys" / "class" / "net"
        write_file(os_release, 'NAME="Ubuntu"\nVERSION_ID="24.04"\nPRETTY_NAME="Ubuntu 24.04 LTS"\n')
        write_file(
            cpuinfo,
            "\n".join(
                [
                    "processor\t: 0",
                    "vendor_id\t: GenuineIntel",
                    "cpu cores\t: 8",
                    "siblings\t: 16",
                    "model name\t: Intel Xeon",
                    "cpu MHz\t: 2200.000",
                    "",
                    "processor\t: 1",
                    "vendor_id\t: GenuineIntel",
                    "cpu cores\t: 8",
                    "siblings\t: 16",
                    "model name\t: Intel Xeon",
                    "cpu MHz\t: 2200.000",
                ]
            ),
        )
        write_file(meminfo, "MemTotal:       33554432 kB")
        write_file(dmi / "bios_vendor", "ACME")
        write_file(dmi / "bios_version", "1.2.3")
        write_file(dmi / "sys_vendor", "AcmeSystems")
        write_file(dmi / "product_name", "EdgeNode")
        write_file(net / "eth0" / "operstate", "up")
        write_file(net / "eth0" / "speed", "1000")
        write_file(net / "eth0" / "mtu", "1500")
        self.collector.OS_RELEASE_PATH = os_release
        self.collector.CPUINFO_PATH = cpuinfo
        self.collector.MEMINFO_PATH = meminfo
        self.collector.SYS_DMI_PATH = dmi
        self.collector.SYS_NET_PATH = net
        return types.SimpleNamespace(sysname="Linux", nodename="n01", release="6.6.0", version="#1", machine="x86_64")

    def test_deterministic_mocked_surfaces_collects_linux_observation(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            uname = self.mock_sources(base)
            output = base / "observations" / "heavy-host-b.json"
            run = {
                "lsblk": lsblk_output(),
                "lspci": '0000:00:02.0 "Intel Corporation" "Alder Lake Graphics" "Intel Corporation"',
                "nvidia-smi": "GPU-9999, NVIDIA GeForce, 24000, 535.154.05, 0000:01:00.0, P0, 250.0",
            }
            with mock.patch.object(self.collector.os, "uname", return_value=uname):
                with mock.patch.object(self.collector.shutil, "which", side_effect=lambda name: "/usr/bin/" + name):
                    with mock.patch.object(self.collector, "run_command", side_effect=lambda command, timeout=5.0: run.get(command[0], "")):
                        _, failures = self.collector.collect("heavy-host-b", output)
            self.assertEqual(failures, [])
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "axm-community-lab/host-observation@2")
            self.assertEqual(payload["platform"], "linux")
            wsl = [row for row in payload["runtime"] if row["name"] == "wsl"][0]
            self.assertFalse(wsl["present"])
            self.assertEqual(wsl["disabled_reason"], "not applicable on a native Linux host")
            self.assertTrue(payload["storage"]["physical_disks"])

    def test_interrupted_and_foreign_temp_output_is_replaced(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            uname = self.mock_sources(base)
            output = base / "observations" / "heavy-host-b.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            temp = output.with_name(f".{output.name}.tmp")
            temp.write_text("stale collector residue", encoding="utf-8")
            run = {
                "lsblk": lsblk_output(),
                "lspci": '0000:00:02.0 "Intel Corporation" "Alder Lake Graphics" "Intel Corporation"',
                "nvidia-smi": "GPU-9999, NVIDIA GeForce, 24000, 535.154.05, 0000:01:00.0, P0, 250.0",
            }
            with mock.patch.object(self.collector.os, "uname", return_value=uname):
                with mock.patch.object(self.collector.shutil, "which", side_effect=lambda name: "/usr/bin/" + name):
                    with mock.patch.object(self.collector, "run_command", side_effect=lambda command, timeout=5.0: run.get(command[0], "")):
                        _, failures = self.collector.collect("heavy-host-b", output)
            self.assertEqual(failures, [])
            self.assertTrue(output.is_file())
            self.assertFalse(temp.exists())

    def test_missing_memory_causes_validation_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            uname = self.mock_sources(base)
            output = base / "observations" / "heavy-host-b.json"
            self.collector.MEMINFO_PATH = base / "proc" / "meminfo-missing"
            run = {
                "lsblk": lsblk_output(),
                "lspci": '0000:00:02.0 "Intel Corporation" "Alder Lake Graphics" "Intel Corporation"',
                "nvidia-smi": "GPU-9999, NVIDIA GeForce, 24000, 535.154.05, 0000:01:00.0, P0, 250.0",
            }
            with mock.patch.object(self.collector.os, "uname", return_value=uname):
                with mock.patch.object(self.collector.shutil, "which", side_effect=lambda name: "/usr/bin/" + name):
                    with mock.patch.object(self.collector, "run_command", side_effect=lambda command, timeout=5.0: run.get(command[0], "")):
                        _, failures = self.collector.collect("heavy-host-b", output)
            self.assertNotEqual(failures, [])
            self.assertIn("memory.total_bytes missing", failures)


if __name__ == "__main__":
    unittest.main()
