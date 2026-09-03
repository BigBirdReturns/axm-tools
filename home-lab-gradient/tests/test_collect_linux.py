"""Hostile witnesses for the read-only Linux host observation collector.

Every Linux surface is mocked deterministically: /etc/os-release, /proc/cpuinfo,
/proc/meminfo, /sys/class/dmi/id, /sys/class/net, lsblk, lspci, and nvidia-smi.
No physical host is observed, and the suite runs on Windows, where os.uname does
not exist -- which is why the collector reaches uname through a patchable seam.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import socket
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

WSL_INAPPLICABLE_REASON = "not applicable on a native Linux host"
# RFC 7042 documentation MAC and RFC 5737 TEST-NET-1 address. They exist only
# so the witnesses can prove the collector never reads an address surface;
# no routable or host-derived identifier appears anywhere in this tree.
MOCK_MAC = "00:00:5e:00:53:01"
MOCK_IPV4 = "192.0.2.31"


def load_collector():
    """Load a fresh module per test: the surface constants are module globals."""
    spec = importlib.util.spec_from_file_location("collect_linux_module", str(SCRIPTS / "collect-linux.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def lsblk_output() -> str:
    return json.dumps(
        {
            "blockdevices": [
                {
                    "name": "nvme0n1",
                    "type": "disk",
                    "size": 2_000_000_000_000,
                    "model": "Fixture NVMe 2TB",
                    "rota": 0,
                    "children": [
                        {"name": "nvme0n1p1", "type": "part", "size": 1_000_000_000, "model": None, "rota": 0},
                        {"name": "nvme0n1p2", "type": "part", "size": 1_998_000_000_000, "model": None, "rota": 0},
                    ],
                },
                {"name": "sda", "type": "disk", "size": 10_000_000_000_000, "model": "Fixture HDD 10TB", "rota": 1},
            ]
        }
    )


LSPCI_OUTPUT = "\n".join(
    [
        '00:02.0 "VGA compatible controller [0300]" "Intel Corporation [8086]" "Alder Lake-N [UHD Graphics] [8086:46d1]" -r0c "Intel Corporation [8086]" "Device [2212]"',
        '01:00.0 "VGA compatible controller [0300]" "NVIDIA Corporation [10de]" "GA102 [GeForce RTX 3090] [10de:2204]" -ra1 "NVIDIA Corporation [10de]" "Device [1467]"',
        '00:1f.6 "Ethernet controller [0200]" "Intel Corporation [8086]" "Ethernet Connection I219-V [8086:15fa]" "Intel Corporation [8086]" "Device [7270]"',
    ]
)

NVIDIA_SMI_OUTPUT = "GPU-6b6c1f2e-0f1a-4c3d-9e88-2f4b7a1c0d55, NVIDIA GeForce RTX 3090, 24576, 535.154.05, 00000000:01:00.0, P8, 350.00"


class CollectLinuxTestCase(unittest.TestCase):
    """Shared deterministic mocked-surface harness."""

    def setUp(self):
        self.collector = load_collector()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.output = self.base / "observations" / "heavy-host-b.json"
        self.tools = {
            "lsblk": lsblk_output(),
            "lspci": LSPCI_OUTPUT,
            "nvidia-smi": NVIDIA_SMI_OUTPUT,
        }
        self.available_tools = {"python", "git", "ollama", "docker", "nvidia-smi", "lsblk", "lspci"}
        self.mock_surfaces()

    def mock_surfaces(self, *, with_dmi: bool = True) -> None:
        base = self.base
        os_release = base / "etc" / "os-release"
        cpuinfo = base / "proc" / "cpuinfo"
        meminfo = base / "proc" / "meminfo"
        dmi = base / "sys" / "class" / "dmi" / "id"
        net = base / "sys" / "class" / "net"

        write_file(
            os_release,
            '\n'.join(
                [
                    'NAME="Ubuntu"',
                    'VERSION_ID="24.04"',
                    'PRETTY_NAME="Ubuntu 24.04.1 LTS"',
                    "ID=ubuntu",
                ]
            ),
        )
        # Two logical processors of one physical package: the collector must
        # collapse them into a single package row, not emit the raw repetition.
        write_file(
            cpuinfo,
            "\n".join(
                [
                    "processor\t: 0",
                    "vendor_id\t: GenuineIntel",
                    "model name\t: Intel(R) Core(TM) i5-13500T",
                    "physical id\t: 0",
                    "cpu cores\t: 14",
                    "siblings\t: 20",
                    "cpu MHz\t: 2200.000",
                    "",
                    "processor\t: 1",
                    "vendor_id\t: GenuineIntel",
                    "model name\t: Intel(R) Core(TM) i5-13500T",
                    "physical id\t: 0",
                    "cpu cores\t: 14",
                    "siblings\t: 20",
                    "cpu MHz\t: 3100.000",
                ]
            ),
        )
        write_file(meminfo, "MemTotal:       32768000 kB\nMemFree:         1000000 kB")
        if with_dmi:
            write_file(dmi / "bios_vendor", "Fixture BIOS Inc")
            write_file(dmi / "bios_version", "1.2.3")
            write_file(dmi / "bios_date", "01/02/2026")
            write_file(dmi / "sys_vendor", "FixtureSystems")
            write_file(dmi / "product_name", "EdgeNode NUC")
            write_file(dmi / "product_family", "EdgeNode")
            write_file(dmi / "board_name", "FX-B550")
            # Serial-bearing DMI files exist and must never be read.
            write_file(dmi / "product_serial", "SERIAL-MUST-NOT-APPEAR")
            write_file(dmi / "board_serial", "BOARD-MUST-NOT-APPEAR")
            write_file(dmi / "product_uuid", "12345678-1234-1234-1234-123456789abc")

        write_file(net / "eth0" / "operstate", "up")
        write_file(net / "eth0" / "speed", "1000")
        write_file(net / "eth0" / "mtu", "1500")
        # Address surfaces exist and must never be read.
        write_file(net / "eth0" / "address", MOCK_MAC)
        write_file(net / "eth0" / "ip", MOCK_IPV4)
        write_file(net / "lo" / "operstate", "unknown")

        self.collector.OS_RELEASE_PATH = os_release
        self.collector.CPUINFO_PATH = cpuinfo
        self.collector.MEMINFO_PATH = meminfo
        self.collector.SYS_DMI_PATH = dmi
        self.collector.SYS_NET_PATH = net
        self.collector.DMI_TABLE_PATH = base / "sys" / "firmware" / "dmi" / "tables" / "DMI"

    def uname(self):
        return types.SimpleNamespace(
            sysname="Linux",
            nodename="octo-n01",
            release="6.8.0-45-generic",
            version="#45-Ubuntu SMP",
            machine="x86_64",
        )

    def fake_which(self, name: str):
        return f"/usr/bin/{name}" if name in self.available_tools else None

    def fake_run_command(self, command, timeout=5.0):
        return self.tools.get(command[0], "")

    def run_collect(self, host_id: str = "heavy-host-b", out_file: Path | None = None):
        target = self.output if out_file is None else out_file
        with mock.patch.object(self.collector, "read_uname", side_effect=self.uname), mock.patch.object(
            self.collector, "which", side_effect=self.fake_which
        ), mock.patch.object(self.collector, "run_command", side_effect=self.fake_run_command):
            return self.collector.collect(host_id, target)

    def run_main(self, argv):
        """Exercise the CLI and return its exit code, swallowing its report."""
        with mock.patch.object(self.collector, "read_uname", side_effect=self.uname), mock.patch.object(
            self.collector, "which", side_effect=self.fake_which
        ), mock.patch.object(self.collector, "run_command", side_effect=self.fake_run_command):
            with contextlib.redirect_stdout(io.StringIO()):
                return self.collector.main(argv)

    def published(self) -> dict:
        return json.loads(self.output.read_bytes().decode("utf-8"))

    def runtime_row(self, payload: dict, name: str) -> dict:
        rows = [row for row in payload["runtime"] if row["name"] == name]
        self.assertEqual(len(rows), 1, f"expected exactly one {name} runtime row")
        return rows[0]


class DeterministicSurfaceTests(CollectLinuxTestCase):
    def test_deterministic_mocked_surfaces_collects_linux_observation(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        payload = self.published()

        self.assertEqual(payload["schema"], "axm-community-lab/host-observation@2")
        self.assertEqual(payload["platform"], "linux")
        self.assertEqual(payload["host_id"], "heavy-host-b")

        # /etc/os-release and uname
        self.assertEqual(payload["system"]["hostname"], "octo-n01")
        self.assertEqual(payload["system"]["kernel"], "6.8.0-45-generic")
        self.assertEqual(payload["system"]["architecture"], "x86_64")
        self.assertEqual(payload["system"]["os_release"], "Ubuntu 24.04.1 LTS")
        self.assertEqual(payload["system"]["os_version"], "24.04")

        # /sys/class/dmi/id
        self.assertEqual(payload["system"]["firmware"]["bios_manufacturer"], "Fixture BIOS Inc")
        self.assertEqual(payload["system"]["model"], "EdgeNode NUC")

        # /proc/cpuinfo collapses to one package row carrying observed topology
        self.assertEqual(len(payload["cpu"]), 1)
        self.assertEqual(payload["cpu"][0]["name"], "Intel(R) Core(TM) i5-13500T")
        self.assertEqual(payload["cpu"][0]["cores"], 14)
        self.assertEqual(payload["cpu"][0]["logical_processors"], 20)
        self.assertEqual(payload["cpu"][0]["logical_processors_observed"], 2)
        self.assertEqual(payload["cpu"][0]["max_clock_mhz"], 3100)

        # /proc/meminfo
        self.assertEqual(payload["memory"]["total_bytes"], 32768000 * 1024)

        # lsblk: two physical disks, two logical volumes, no serials
        self.assertEqual([disk["name"] for disk in payload["storage"]["physical_disks"]], ["nvme0n1", "sda"])
        self.assertEqual([vol["name"] for vol in payload["storage"]["logical_volumes"]], ["nvme0n1p1", "nvme0n1p2"])

        # lspci: display-class functions only, Ethernet controller excluded
        adapters = payload["graphics"]["adapters"]
        self.assertEqual(len(adapters), 2)
        self.assertEqual(
            {adapter["vendor_guess"] for adapter in adapters},
            {"Intel", "NVIDIA"},
        )
        igpu = next(a for a in adapters if a["vendor_guess"] == "Intel")
        self.assertEqual(igpu["role_candidate"], "igpu-candidate")
        self.assertEqual(igpu["bus_id"], "00:02.0")

        # nvidia-smi
        self.assertEqual(len(payload["graphics"]["nvidia"]), 1)
        nvidia = payload["graphics"]["nvidia"][0]
        self.assertEqual(nvidia["uuid"], "GPU-6b6c1f2e-0f1a-4c3d-9e88-2f4b7a1c0d55")
        self.assertEqual(nvidia["memory_total_mib"], 24576)
        self.assertEqual(nvidia["driver_version"], "535.154.05")
        self.assertEqual(nvidia["power_limit_watts"], 350.0)

        # /sys/class/net, loopback excluded
        self.assertEqual([nic["name"] for nic in payload["network"]["adapters"]], ["eth0"])
        self.assertEqual(payload["network"]["adapters"][0]["speed_mbps"], 1000)
        self.assertFalse(payload["network"]["addresses_collected"])

        # Explicit surface evidence
        self.assertTrue(payload["surfaces"]["files"]["proc_cpuinfo"]["readable"])
        self.assertTrue(payload["surfaces"]["tools"]["lspci"]["available"])

    def test_native_linux_wsl_row_is_explicitly_inapplicable(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        payload = self.published()
        wsl = self.runtime_row(payload, "wsl")
        self.assertIs(wsl["present"], False)
        self.assertIs(wsl["disabled"], True)
        self.assertIsNone(wsl["path"])
        self.assertEqual(wsl["disabled_reason"], WSL_INAPPLICABLE_REASON)
        self.assertEqual(
            [row["name"] for row in payload["runtime"]],
            ["python", "git", "ollama", "docker", "wsl", "nvidia-smi"],
        )

    def test_absent_optional_tools_are_explicit_and_never_inferred(self):
        self.available_tools = {"python", "git"}
        self.tools = {}
        with mock.patch.object(self.collector, "read_uname", side_effect=self.uname), mock.patch.object(
            self.collector, "which", side_effect=self.fake_which
        ), mock.patch.object(self.collector, "run_command", side_effect=self.fake_run_command):
            observation, failures = self.collector.build_observation("heavy-host-b")

        for tool in ("lsblk", "lspci", "nvidia-smi"):
            self.assertFalse(observation["surfaces"]["tools"][tool]["available"])
            self.assertIsNone(observation["surfaces"]["tools"][tool]["path"])
            self.assertTrue(observation["surfaces"]["tools"][tool]["note"])

        # Absence is recorded, never inferred into a device.
        self.assertEqual(observation["graphics"]["adapters"], [])
        self.assertEqual(observation["graphics"]["nvidia"], [])
        self.assertEqual(observation["storage"]["physical_disks"], [])
        self.assertFalse(observation["storage"]["available"])
        self.assertIn("lsblk", observation["storage"]["note"])

        # The closed runtime denominator survives: rows go false, never missing.
        self.assertEqual(len(observation["runtime"]), 6)
        for name in ("ollama", "docker", "nvidia-smi"):
            row = self.runtime_row(observation, name)
            self.assertIs(row["present"], False)
            self.assertIs(row["disabled"], True)
            self.assertIsNone(row["path"])
            self.assertEqual(row["disabled_reason"], "command not found in the current process PATH")

        self.assertIn("storage.physical_disks missing", failures)

    def test_unreadable_optional_surface_is_explicit(self):
        missing_dmi = self.base / "sys" / "class" / "dmi" / "absent"
        self.collector.SYS_DMI_PATH = missing_dmi
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        payload = self.published()
        self.assertFalse(payload["surfaces"]["files"]["sys_dmi_id"]["readable"])
        self.assertEqual(
            set(payload["system"]["firmware"].values()),
            {None},
            "unreadable DMI fields must stay explicitly null, not disappear",
        )
        self.assertFalse(payload["memory"]["modules_available"])
        self.assertFalse(payload["memory"]["modules_source"]["readable"])
        self.assertIn("sudo", payload["memory"]["modules_source"]["note"])


class RefusalTests(CollectLinuxTestCase):
    def test_missing_memory_causes_validation_failure(self):
        self.collector.MEMINFO_PATH = self.base / "proc" / "meminfo-missing"
        _, failures = self.run_collect()
        self.assertIn("memory.total_bytes missing", failures)
        self.assertFalse(self.output.exists(), "a refused collection must publish nothing")

    def test_missing_physical_disk_refuses_and_publishes_nothing(self):
        self.tools["lsblk"] = json.dumps({"blockdevices": []})
        _, failures = self.run_collect()
        self.assertIn("storage.physical_disks missing", failures)
        self.assertFalse(self.output.exists())

    def test_missing_host_identity_refuses(self):
        blank = types.SimpleNamespace(sysname="Linux", nodename="", release="", version="", machine="")
        with mock.patch.object(self.collector, "read_uname", return_value=blank), mock.patch.object(
            self.collector, "which", side_effect=self.fake_which
        ), mock.patch.object(self.collector, "run_command", side_effect=self.fake_run_command):
            _, failures = self.collector.collect("heavy-host-b", self.output)
        self.assertIn("system.hostname missing", failures)
        self.assertIn("system.kernel missing", failures)
        self.assertIn("system.architecture missing", failures)
        self.assertFalse(self.output.exists())

    def test_empty_host_id_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_collect(host_id="   ")

    def test_cli_exit_codes(self):
        self.assertEqual(self.run_main(["--host-id", "heavy-host-b", "--out-file", str(self.output)]), 0)

        second = self.base / "observations" / "refused.json"
        self.collector.MEMINFO_PATH = self.base / "proc" / "meminfo-missing"
        self.assertEqual(self.run_main(["--host-id", "heavy-host-b", "--out-file", str(second)]), 1)
        self.assertFalse(second.exists())

        self.assertEqual(self.run_main(["--host-id", "  ", "--out-file", str(second)]), 2)

    def test_non_posix_host_is_refused_not_faked(self):
        """A host without os.uname refuses; it never invents a host identity."""
        third = self.base / "observations" / "nonposix.json"
        # Remove os.uname wherever it exists (it does not on Windows) and put it
        # back afterwards; patch.dict restores the module namespace exactly.
        with mock.patch.dict(self.collector.os.__dict__, clear=False):
            self.collector.os.__dict__.pop("uname", None)
            with self.assertRaises(self.collector.CollectorError):
                self.collector.read_uname()
            with mock.patch.object(self.collector, "which", side_effect=self.fake_which), mock.patch.object(
                self.collector, "run_command", side_effect=self.fake_run_command
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        self.collector.main(["--host-id", "heavy-host-b", "--out-file", str(third)]),
                        3,
                    )
        self.assertFalse(third.exists())


class AtomicPublicationTests(CollectLinuxTestCase):
    def test_interrupted_and_foreign_temp_output_is_replaced(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temp = self.collector.temp_path_for(self.output.resolve())
        temp.write_text("stale collector residue from an interrupted run", encoding="utf-8")

        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        self.assertTrue(self.output.is_file())
        self.assertFalse(temp.exists(), "the temporary file must not survive publication")
        payload = self.published()
        self.assertEqual(payload["host_id"], "heavy-host-b")

    def test_refusal_clears_residue_so_it_cannot_masquerade_as_output(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temp = self.collector.temp_path_for(self.output.resolve())
        temp.write_text('{"schema": "forged", "host_id": "heavy-host-b"}', encoding="utf-8")
        self.collector.MEMINFO_PATH = self.base / "proc" / "meminfo-missing"

        _, failures = self.run_collect()
        self.assertNotEqual(failures, [])
        self.assertFalse(self.output.exists())
        self.assertFalse(temp.exists())

    def test_temp_name_is_same_directory_and_distinct_from_output(self):
        temp = self.collector.temp_path_for(self.output)
        self.assertEqual(temp.parent, self.output.parent)
        self.assertNotEqual(temp.name, self.output.name)
        self.assertTrue(temp.name.endswith(".tmp"))

    def test_publication_flushes_fsyncs_and_renames(self):
        calls: list[str] = []
        real_fsync = self.collector.os.fsync
        real_replace = self.collector.os.replace

        def record_fsync(fd):
            calls.append("fsync")
            return real_fsync(fd)

        def record_replace(src, dst):
            calls.append("replace")
            return real_replace(src, dst)

        with mock.patch.object(self.collector.os, "fsync", record_fsync), mock.patch.object(
            self.collector.os, "replace", record_replace
        ):
            _, failures = self.run_collect()

        self.assertEqual(failures, [])
        self.assertEqual(calls, ["fsync", "replace"], "fsync must precede the atomic rename")

    def test_only_the_named_output_and_its_temp_are_written(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        written = sorted(item.name for item in self.output.parent.iterdir())
        self.assertEqual(written, ["heavy-host-b.json"])


class IdentityAndDigestTests(CollectLinuxTestCase):
    def test_observation_digest_binds_canonical_body_bytes(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        payload = self.published()
        body = {k: v for k, v in payload.items() if k != "observation_sha256"}
        expected = hashlib.sha256(self.collector.canonical_bytes(body)).hexdigest()
        self.assertEqual(payload["observation_sha256"], expected)

        tampered = dict(payload)
        tampered["memory"] = dict(payload["memory"], total_bytes=1)
        recomputed = hashlib.sha256(
            self.collector.canonical_bytes({k: v for k, v in tampered.items() if k != "observation_sha256"})
        ).hexdigest()
        self.assertNotEqual(recomputed, payload["observation_sha256"])

    def test_collector_binds_its_own_source_and_python_identity(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        collector = self.published()["collector"]
        self.assertEqual(collector["schema"], "axm-community-lab/host-observation-collector@1")
        self.assertEqual(collector["platform"], "linux")
        self.assertEqual(
            collector["source_sha256"],
            hashlib.sha256((SCRIPTS / "collect-linux.py").read_bytes()).hexdigest(),
            "the source digest must be over exact bytes, never a text-mode read",
        )
        self.assertEqual(Path(collector["source_path"]).name, "collect-linux.py")
        self.assertEqual(len(collector["python_executable"]["sha256"]), 64)
        self.assertTrue(collector["python_executable"]["path"])

    def test_output_is_lf_utf8_without_bom(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        raw = self.output.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "no byte-order mark")
        self.assertNotIn(b"\r", raw, "observation bytes must use LF endings on every platform")
        self.assertTrue(raw.endswith(b"\n"))
        raw.decode("utf-8")

    def test_repeated_collection_is_byte_identical_apart_from_time(self):
        frozen_clock = {
            "stopwatch_frequency_hz": 1_000_000_000,
            "monotonic_resolution_ns": 1,
            "samples": [{"wall_utc": "2026-08-05T00:00:00Z", "monotonic_ns": 1, "perf_counter_ns": 1}],
            "cross_host_offset_measured": False,
        }
        with mock.patch.object(self.collector, "utc_now", return_value="2026-08-05T00:00:00Z"), mock.patch.object(
            self.collector, "collect_clock_observations", return_value=frozen_clock
        ):
            self.run_collect()
            first = self.output.read_bytes()
            self.run_collect()
            second = self.output.read_bytes()
        self.assertEqual(first, second, "a frozen clock must produce byte-identical output")


class PrivacyTests(CollectLinuxTestCase):
    def test_serial_mac_ip_and_guid_surfaces_are_never_retained(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        raw = self.output.read_bytes().decode("utf-8")

        for forbidden in (
            MOCK_MAC,
            MOCK_IPV4,
            "SERIAL-MUST-NOT-APPEAR",
            "BOARD-MUST-NOT-APPEAR",
            "12345678-1234-1234-1234-123456789abc",
        ):
            self.assertNotIn(forbidden, raw, f"{forbidden} leaked into the observation")

        payload = self.published()
        self.assertFalse(payload["privacy"]["serial_numbers_collected"])
        self.assertFalse(payload["privacy"]["mac_addresses_collected"])
        self.assertFalse(payload["privacy"]["ip_addresses_collected"])
        self.assertFalse(payload["privacy"]["machine_guid_collected"])

    def test_serial_bearing_dmi_files_are_not_in_the_read_allowlist(self):
        read_files = [str(name) for _, name in self.collector.DMI_PUBLIC_FIELDS]
        for forbidden in ("product_serial", "board_serial", "product_uuid", "chassis_serial"):
            self.assertNotIn(forbidden, read_files)

    def test_collector_source_declares_no_transport_import(self):
        source = (SCRIPTS / "collect-linux.py").read_bytes().decode("utf-8")
        for transport in ("import socket", "import urllib", "import http", "import ftplib", "import requests"):
            self.assertNotIn(transport, source)

    def test_collection_opens_no_socket(self):
        def refuse(*args, **kwargs):
            raise AssertionError("the collector must not open a socket")

        with mock.patch.object(socket, "socket", refuse), mock.patch.object(
            socket, "create_connection", refuse
        ):
            _, failures = self.run_collect()
        self.assertEqual(failures, [])
        self.assertTrue(self.output.is_file())


class LauncherTests(unittest.TestCase):
    def test_posix_launcher_is_lf_and_verifies_the_seed_before_collecting(self):
        raw = (SCRIPTS / "collect-linux").read_bytes()
        self.assertNotIn(b"\r", raw, "a CRLF shebang makes the launcher unrunnable on Linux")
        text = raw.decode("utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env sh"))
        self.assertIn("seed/verify.py", text)
        verify_index = text.index("verify.py")
        exec_index = text.index("exec ")
        self.assertLess(verify_index, exec_index, "self-verification must precede collection")


if __name__ == "__main__":
    unittest.main()
