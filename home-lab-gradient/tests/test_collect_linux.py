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
import os
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

        second = self.base / "refused" / "heavy-host-b.json"
        self.collector.MEMINFO_PATH = self.base / "proc" / "meminfo-missing"
        self.assertEqual(self.run_main(["--host-id", "heavy-host-b", "--out-file", str(second)]), 1)
        self.assertFalse(second.exists())

        self.assertEqual(self.run_main(["--host-id", "  ", "--out-file", str(second)]), 2)

    def test_non_posix_host_is_refused_not_faked(self):
        """A host without os.uname refuses; it never invents a host identity."""
        third = self.base / "nonposix" / "heavy-host-b.json"
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
    def assert_no_created_temporary(self, directory: Path) -> None:
        if directory.is_dir():
            self.assertFalse(
                any(item.name.endswith(".tmp") for item in directory.iterdir()),
                "a refused coordinate must leave no collector-created temporary",
            )

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
        """The file, then the rename, then the directory that now names it.

        On POSIX ``fsync_directory`` reaches the kernel by calling os.fsync on
        a directory descriptor of its own, so a naive recorder counts every
        directory flush twice -- and not at all on Windows, where the function
        reports False without opening a handle. The nested call is attributed
        to the directory flush that caused it, so the recorded sequence states
        the durability law itself and is the same on both platforms; how many
        of those flushes actually reached a descriptor is asserted separately,
        against what fsync_directory reported rather than against os.name.
        """
        calls: list[str] = []
        directory_reports: list[bool] = []
        nested_fsyncs = 0
        inside_directory_fsync = False
        real_fsync = self.collector.os.fsync
        real_replace = self.collector.os.replace
        real_fsync_directory = self.collector.fsync_directory

        def record_fsync(fd):
            nonlocal nested_fsyncs
            if inside_directory_fsync:
                nested_fsyncs += 1
            else:
                calls.append("fsync")
            return real_fsync(fd)

        def record_replace(src, dst):
            calls.append("replace")
            return real_replace(src, dst)

        def record_fsync_directory(path):
            nonlocal inside_directory_fsync
            calls.append("fsync-directory")
            inside_directory_fsync = True
            try:
                reported = real_fsync_directory(path)
            finally:
                inside_directory_fsync = False
            directory_reports.append(reported)
            return reported

        with mock.patch.object(self.collector.os, "fsync", record_fsync), mock.patch.object(
            self.collector.os, "replace", record_replace
        ), mock.patch.object(self.collector, "fsync_directory", record_fsync_directory):
            _, failures = self.run_collect()

        self.assertEqual(failures, [])
        # Two publications, observation then receipt, each with the same law:
        # a directory fsync only persists the entry once the rename created it.
        self.assertEqual(
            calls,
            ["fsync", "replace", "fsync-directory", "fsync", "replace", "fsync-directory"],
            "fsync must precede the atomic rename, and the directory fsync must follow it",
        )
        # Every directory flush that reported a durable handle made exactly one
        # fsync on it: two on POSIX, none on Windows, asserted either way.
        self.assertEqual(directory_reports, [os.name != "nt", os.name != "nt"])
        self.assertEqual(nested_fsyncs, sum(1 for reported in directory_reports if reported))

    def test_only_the_declared_outputs_and_their_temps_are_written(self):
        """Exactly the two declared outputs, and no temporary survives either."""
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        written = sorted(item.name for item in self.output.parent.iterdir())
        self.assertEqual(written, ["heavy-host-b.json", "heavy-host-b.receipt.json"])
        self.assertFalse(any(name.endswith(".tmp") for name in written))

    def test_ordinary_lexical_output_publishes_observation_and_receipt(self):
        """The clean control keeps the operator's declared basename intact."""
        observation, failures = self.run_collect()
        self.assertEqual(failures, [])
        self.assertEqual(observation["host_id"], "heavy-host-b")
        self.assertTrue(self.output.is_file())
        receipt_path = self.output.parent / "heavy-host-b.receipt.json"
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["observation_file_name"], self.output.name)
        self.assert_no_created_temporary(self.output.parent)

    def test_final_observation_symlink_refuses_before_host_read_and_preserves_alias(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        unlisted = self.base / "unlisted-observation-target.txt"
        original = b"operator-owned observation target\n"
        unlisted.write_bytes(original)
        try:
            os.symlink(unlisted, self.output)
        except (OSError, NotImplementedError) as exc:  # unprivileged Windows
            self.skipTest(f"this platform will not create a symbolic link: {exc}")

        with mock.patch.object(
            self.collector, "read_uname", side_effect=AssertionError("host surface read")
        ):
            observation, failures = self.collector.collect("heavy-host-b", self.output)

        self.assertEqual(observation, {})
        self.assertTrue(any("output path" in item and "symbolic link" in item for item in failures), failures)
        self.assertTrue(os.path.islink(self.output), "the operator-owned alias must remain")
        self.assertEqual(unlisted.read_bytes(), original)
        self.assertFalse((self.output.parent / "heavy-host-b.receipt.json").exists())
        self.assert_no_created_temporary(self.output.parent)

    def test_final_receipt_symlink_refuses_before_host_read_and_preserves_alias(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        receipt_path = self.output.parent / "heavy-host-b.receipt.json"
        unlisted = self.base / "unlisted-receipt-target.txt"
        original = b"operator-owned receipt target\n"
        unlisted.write_bytes(original)
        try:
            os.symlink(unlisted, receipt_path)
        except (OSError, NotImplementedError) as exc:  # unprivileged Windows
            self.skipTest(f"this platform will not create a symbolic link: {exc}")

        with mock.patch.object(
            self.collector, "read_uname", side_effect=AssertionError("host surface read")
        ):
            observation, failures = self.collector.collect("heavy-host-b", self.output)

        self.assertEqual(observation, {})
        self.assertTrue(any("output path" in item and "symbolic link" in item for item in failures), failures)
        self.assertFalse(self.output.exists(), "the observation must not publish ahead of a refused receipt")
        self.assertTrue(os.path.islink(receipt_path), "the operator-owned alias must remain")
        self.assertEqual(unlisted.read_bytes(), original)
        self.assert_no_created_temporary(self.output.parent)

    def test_parent_directory_symlink_escape_refuses_before_host_read(self):
        escaped = self.base / "unlisted-parent-target"
        escaped.mkdir()
        marker = escaped / "operator-owned.txt"
        original = b"outside the declared coordinate\n"
        marker.write_bytes(original)
        try:
            os.symlink(escaped, self.output.parent, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:  # unprivileged Windows
            self.skipTest(f"this platform will not create a directory symbolic link: {exc}")

        with mock.patch.object(
            self.collector, "read_uname", side_effect=AssertionError("host surface read")
        ), mock.patch.object(
            self.collector, "link_kind", side_effect=AssertionError("descendant inspected through parent alias")
        ):
            observation, failures = self.collector.collect("heavy-host-b", self.output)

        self.assertEqual(observation, {})
        self.assertTrue(any("parent component" in item and "symbolic link" in item for item in failures), failures)
        self.assertTrue(os.path.islink(self.output.parent), "the operator-owned parent alias must remain")
        self.assertEqual(marker.read_bytes(), original)
        self.assertFalse((escaped / "heavy-host-b.json").exists())
        self.assertFalse((escaped / "heavy-host-b.receipt.json").exists())
        self.assert_no_created_temporary(escaped)

    def test_parent_directory_reparse_escape_refuses_on_every_platform(self):
        """Drive the Windows reparse classification even where none can be made."""
        self.output.parent.mkdir(parents=True)
        marker = self.output.parent / "operator-owned.txt"
        original = b"reparse target stand-in\n"
        marker.write_bytes(original)
        real_parent_kind = self.collector.parent_kind

        def classify(path):
            return "reparse point" if Path(path) == self.output.parent else real_parent_kind(path)

        with mock.patch.object(self.collector, "parent_kind", side_effect=classify), mock.patch.object(
            self.collector, "read_uname", side_effect=AssertionError("host surface read")
        ), mock.patch.object(
            self.collector, "link_kind", side_effect=AssertionError("descendant inspected through parent reparse")
        ):
            observation, failures = self.collector.collect("heavy-host-b", self.output)

        self.assertEqual(observation, {})
        self.assertTrue(any("parent component" in item and "reparse point" in item for item in failures), failures)
        self.assertEqual(marker.read_bytes(), original)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.output.parent / "heavy-host-b.receipt.json").exists())
        self.assert_no_created_temporary(self.output.parent)

    def test_publication_never_writes_through_a_predictable_temporary_name(self):
        """The temporary is created exclusively under an unpredictable name.

        A deterministic name is what let a pre-created hard link become the
        inode that open("w") truncated, so the name must not be derivable and
        the descriptor must be the one this process created.
        """
        seen: list[tuple] = []
        real_mkstemp = self.collector.tempfile.mkstemp

        def record_mkstemp(*args, **kwargs):
            descriptor, name = real_mkstemp(*args, **kwargs)
            seen.append((kwargs.get("dir"), name))
            return descriptor, name

        with mock.patch.object(self.collector.tempfile, "mkstemp", record_mkstemp):
            _, failures = self.run_collect()

        self.assertEqual(failures, [])
        self.assertEqual(len(seen), 2, "one exclusive temporary per published file")
        for directory, name in seen:
            temp = Path(name)
            published_dir = self.output.resolve().parent
            self.assertTrue(os.path.samefile(temp.parent, published_dir), "the temporary stays in the output directory")
            self.assertTrue(os.path.samefile(Path(str(directory)), published_dir))
            self.assertNotEqual(temp.name, self.collector.temp_path_for(self.output).name)
            self.assertFalse(temp.exists(), "no temporary survives publication")
        self.assertNotEqual(seen[0][1], seen[1][1])

    def test_hard_linked_deterministic_temp_refuses_and_leaves_the_unlisted_file_intact(self):
        """The reproduced P1: a hard link at the temporary name must not be acted on.

        The previous collector opened the deterministic name with mode "w",
        which truncated the linked inode before the rename ever ran.
        """
        self.output.parent.mkdir(parents=True, exist_ok=True)
        unlisted = self.base / "unlisted-secret.txt"
        original = b"bytes the operator never listed as an output\n"
        unlisted.write_bytes(original)
        temp = self.collector.temp_path_for(self.output.resolve())
        os.link(unlisted, temp)
        self.assertEqual(unlisted.stat().st_nlink, 2)

        _, failures = self.run_collect()

        self.assertTrue(
            any(
                "deterministic temporary name" in failure
                and "hard link to an unlisted object" in failure
                and "nothing was written or removed" in failure
                for failure in failures
            ),
            failures,
        )
        self.assertFalse(self.output.exists(), "nothing may be published behind a refusal")
        self.assertFalse((self.output.parent / "heavy-host-b.receipt.json").exists())
        self.assertEqual(unlisted.read_bytes(), original, "the unlisted file was mutated")
        self.assertTrue(temp.exists(), "the operator's link must not be removed either")

    def test_symlinked_deterministic_temp_refuses_and_leaves_the_target_intact(self):
        """A symbolic link at the temporary name is refused, never followed."""
        self.output.parent.mkdir(parents=True, exist_ok=True)
        unlisted = self.base / "unlisted-symlink-target.txt"
        original = b"a second object the operator never listed\n"
        unlisted.write_bytes(original)
        temp = self.collector.temp_path_for(self.output.resolve())
        try:
            os.symlink(unlisted, temp)
        except (OSError, NotImplementedError) as exc:  # unprivileged Windows
            self.skipTest(f"this platform will not create a symbolic link: {exc}")

        _, failures = self.run_collect()

        self.assertTrue(
            any(
                "deterministic temporary name" in failure
                and "symbolic link" in failure
                and "nothing was written or removed" in failure
                for failure in failures
            ),
            failures,
        )
        self.assertFalse(self.output.exists())
        self.assertEqual(unlisted.read_bytes(), original, "the symlink target was mutated")
        self.assertTrue(os.path.islink(temp), "the operator's link must not be removed either")

    def test_symbolic_link_classification_refuses_without_creating_one(self):
        """The same refusal on a platform that will not create a symlink at all.

        The witness drives the classification seam instead of the filesystem, so
        the exact refusal is asserted on every leg, not only the POSIX ones.
        """
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temp = self.collector.temp_path_for(self.output)
        temp.write_bytes(b"stands in for a symbolic link\n")
        real_link_kind = self.collector.link_kind

        def classify(path):
            return "symbolic link" if Path(path) == temp else real_link_kind(path)

        with mock.patch.object(self.collector, "link_kind", classify):
            _, failures = self.run_collect()

        self.assertTrue(
            any(
                "deterministic temporary name" in failure and "symbolic link" in failure
                for failure in failures
            ),
            failures,
        )
        self.assertFalse(self.output.exists())
        self.assertTrue(temp.exists(), "a refused alias is never unlinked")

    def test_hard_linked_output_path_refuses_before_anything_is_written(self):
        """The output name itself may not be an alias for an unlisted object."""
        self.output.parent.mkdir(parents=True, exist_ok=True)
        unlisted = self.base / "unlisted-output-alias.txt"
        original = b"a third object the operator never listed\n"
        unlisted.write_bytes(original)
        os.link(unlisted, self.output)

        with mock.patch.object(
            self.collector, "read_uname", side_effect=AssertionError("host surface read")
        ):
            observation, failures = self.collector.collect("heavy-host-b", self.output)

        self.assertEqual(observation, {})
        self.assertTrue(
            any(
                "output path" in failure and "hard link to an unlisted object" in failure
                for failure in failures
            ),
            failures,
        )
        self.assertEqual(unlisted.read_bytes(), original)
        self.assertEqual(self.output.read_bytes(), original, "the aliased output was rewritten")
        self.assertTrue(self.output.exists(), "the operator-owned hard-link name must remain")
        self.assertFalse((self.output.parent / "heavy-host-b.receipt.json").exists())
        self.assert_no_created_temporary(self.output.parent)

    def test_ordinary_stale_residue_is_still_cleared_but_an_alias_is_not(self):
        """Recovery removes ordinary residue only; aliases are left alone."""
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temp = self.collector.temp_path_for(self.output.resolve())
        temp.write_bytes(b"ordinary interrupted residue\n")
        self.assertEqual(self.collector.link_kind(temp), "regular file")
        self.collector.discard_temp(self.output.resolve())
        self.assertFalse(temp.exists())

        unlisted = self.base / "unlisted-residue-target.txt"
        unlisted.write_bytes(b"still listed nowhere\n")
        os.link(unlisted, temp)
        self.assertEqual(self.collector.link_kind(temp), "hard link to an unlisted object")
        self.collector.discard_temp(self.output.resolve())
        self.assertTrue(temp.exists(), "an alias must survive residue recovery")


class SeedCoordinateTests(CollectLinuxTestCase):
    """The declared coordinate is enforced, not documented."""

    def test_undeclared_host_id_is_refused_before_any_surface_is_read(self):
        target = self.base / "elsewhere" / "undeclared-host.json"
        surfaces_read: list[str] = []

        def tripwire(*args, **kwargs):
            surfaces_read.append("read")
            raise AssertionError("a host surface was read before the coordinate was validated")

        with mock.patch.object(self.collector, "read_uname", tripwire):
            with self.assertRaises(self.collector.CoordinateError) as raised:
                self.collector.collect("undeclared-host", target)

        message = str(raised.exception)
        self.assertIn("is not declared by the seed manifest", message)
        self.assertIn("control-host, heavy-host-a, heavy-host-b", message)
        self.assertEqual(surfaces_read, [])
        self.assertFalse(target.parent.exists(), "no directory may be created for a refused coordinate")

    def test_output_basename_unrelated_to_host_id_is_refused(self):
        """The reproduced P2: heavy-host-b written to not-the-host-id.json."""
        target = self.base / "elsewhere" / "not-the-host-id.json"
        with mock.patch.object(self.collector, "read_uname", side_effect=AssertionError):
            with self.assertRaises(self.collector.CoordinateError) as raised:
                self.collector.collect("heavy-host-b", target)

        message = str(raised.exception)
        self.assertIn("out-file basename must be the declared observation name", message)
        self.assertIn("expected heavy-host-b.json", message)
        self.assertIn("observed not-the-host-id.json", message)
        self.assertFalse(target.parent.exists())

    def test_both_substitutions_exit_two_through_the_cli(self):
        self.assertEqual(
            self.run_main(
                ["--host-id", "undeclared-host", "--out-file", str(self.base / "x" / "undeclared-host.json")]
            ),
            2,
        )
        self.assertEqual(
            self.run_main(
                ["--host-id", "heavy-host-b", "--out-file", str(self.base / "x" / "not-the-host-id.json")]
            ),
            2,
        )
        self.assertFalse((self.base / "x").exists())

    def test_declared_host_ids_come_from_the_bound_seed_manifest(self):
        """The declaration is immutable: sha256sums.txt binds the manifest bytes."""
        coordinates = self.collector.declared_coordinates()
        self.assertEqual(
            coordinates["host_ids"], ("control-host", "heavy-host-a", "heavy-host-b")
        )
        self.assertEqual(coordinates["output_name"], "<host-id>.json")

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "seed").mkdir()
            manifest = root / "seed" / "seed-manifest.json"
            sums = root / "seed" / "sha256sums.txt"
            source = json.loads((SCRIPTS.parent / "seed" / "seed-manifest.json").read_bytes().decode("utf-8"))
            source["observation"]["declared_host_ids"] = ["undeclared-host"]
            manifest.write_bytes((json.dumps(source, indent=2) + "\n").encode("utf-8"))
            sums.write_bytes(
                (
                    hashlib.sha256(
                        (SCRIPTS.parent / "seed" / "seed-manifest.json").read_bytes()
                    ).hexdigest()
                    + "  seed/seed-manifest.json\n"
                ).encode("ascii")
            )
            with self.assertRaises(self.collector.CoordinateError) as raised:
                self.collector.declared_coordinates(manifest_path=manifest, sums_path=sums)
        self.assertIn("seed manifest digest mismatch", str(raised.exception))


class ReturnReceiptTests(CollectLinuxTestCase):
    """The body-free receipt issue #151 requires for the W01 join."""

    def receipt_path(self) -> Path:
        return self.output.parent / "heavy-host-b.receipt.json"

    def receipt(self) -> dict:
        return json.loads(self.receipt_path().read_bytes().decode("utf-8"))

    def test_receipt_is_published_beside_the_observation(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        self.assertTrue(self.receipt_path().is_file())
        receipt = self.receipt()
        self.assertEqual(receipt["schema"], "axm-community-lab/host-observation-receipt@1")
        self.assertEqual(receipt["host_id"], "heavy-host-b")
        self.assertIs(receipt["carries_observation_body"], False)

    def test_receipt_binds_the_exact_published_observation_bytes(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        receipt = self.receipt()
        published = self.output.read_bytes()
        self.assertEqual(receipt["observation_file_sha256"], hashlib.sha256(published).hexdigest())
        self.assertEqual(receipt["observation_file_bytes"], len(published))
        self.assertEqual(receipt["observation_file_name"], "heavy-host-b.json")
        self.assertEqual(receipt["observation_sha256"], self.published()["observation_sha256"])
        self.assertNotEqual(
            receipt["observation_file_sha256"],
            receipt["observation_sha256"],
            "the file digest and the body digest are different facts",
        )
        body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        self.assertEqual(
            receipt["receipt_sha256"],
            hashlib.sha256(self.collector.canonical_bytes(body)).hexdigest(),
        )

    def test_receipt_carries_no_value_from_the_observation_body(self):
        """Nothing host-descriptive may travel with the publishable artifact."""
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        observation = self.published()
        receipt = self.receipt()

        allowed = {
            observation["schema"],
            observation["platform"],
            observation["host_id"],
            observation["observed_at"],
            observation["observation_sha256"],
            observation["collector"]["schema"],
            observation["collector"]["source_sha256"],
            str(observation["collector"]["python_executable"]["sha256"]),
        }

        def strings(payload, found):
            if isinstance(payload, dict):
                for value in payload.values():
                    strings(value, found)
            elif isinstance(payload, list):
                for value in payload:
                    strings(value, found)
            elif isinstance(payload, str) and len(payload) >= 3:
                found.add(payload)

        body_values: set = set()
        strings(observation, body_values)
        receipt_values: list = []

        def values(payload, found):
            if isinstance(payload, dict):
                for value in payload.values():
                    values(value, found)
            elif isinstance(payload, list):
                for value in payload:
                    values(value, found)
            elif isinstance(payload, str):
                found.append(payload)

        values(receipt, receipt_values)
        leaked = [
            candidate
            for candidate in sorted(body_values - allowed)
            for value in receipt_values
            if candidate == value or (len(candidate) >= 8 and candidate in value)
        ]
        self.assertEqual(leaked, [], "the receipt is not body-free")

        # The specific identifiers this seam exists to keep out.
        text = self.receipt_path().read_bytes().decode("utf-8")
        for forbidden in (
            observation["system"]["hostname"],
            observation["system"]["kernel"],
            observation["storage"]["physical_disks"][0]["model"],
            observation["graphics"]["nvidia"][0]["uuid"],
        ):
            self.assertNotIn(forbidden, text, f"{forbidden} leaked into the receipt")

    def test_receipt_publishes_accelerator_identity_only_as_a_digest(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        observation = self.published()
        receipt = self.receipt()
        identities = [row["uuid"].lower() for row in observation["graphics"]["nvidia"]]
        self.assertTrue(identities)
        self.assertEqual(receipt["accelerator_identity_count"], len(identities))
        self.assertEqual(
            receipt["accelerator_identity_sha256"],
            sorted(hashlib.sha256(item.encode("utf-8")).hexdigest() for item in identities),
        )

    def test_receipt_is_lf_utf8_without_bom(self):
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        raw = self.receipt_path().read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))
        raw.decode("utf-8")

    def test_receipt_fingerprint_ignores_the_role_label_and_the_timestamp(self):
        """One machine relabelled is one fingerprint, whatever the label says."""
        _, failures = self.run_collect()
        self.assertEqual(failures, [])
        observation = self.published()
        relabelled = dict(observation, host_id="control-host", observed_at="2027-01-01T00:00:00Z")
        self.assertEqual(
            self.collector.observed_host_fingerprint(observation),
            self.collector.observed_host_fingerprint(relabelled),
        )
        self.assertEqual(self.receipt()["host_fingerprint_sha256"], self.collector.observed_host_fingerprint(observation))

        other_machine = json.loads(json.dumps(observation))
        other_machine["system"]["hostname"] = "a-different-machine"
        self.assertNotEqual(
            self.collector.observed_host_fingerprint(observation),
            self.collector.observed_host_fingerprint(other_machine),
        )


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
