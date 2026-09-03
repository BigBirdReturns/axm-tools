"""Hostile witnesses for the offline Linux seed bundle.

The seed is content-addressed and must run on a host with no clone of this
repository, no credentials from it, and no network path back to it. These
witnesses prove reconstruction determinism, self-verification, independence
from repository imports, and privacy of the bundle's own bytes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import contextlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SEED = ROOT / "seed"
sys.path.insert(0, str(SCRIPTS))

from lab import IPV4_RE, IPV6_RE, MAC_RE, PROHIBITED_FIELD_MARKERS  # noqa: E402

SUM_FILE = "seed/sha256sums.txt"
REPOSITORY_MODULES = ("planner", "evidence", "lab", "render")


def load_seed_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, str(SEED / filename))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def valid_observation(host_id: str = "heavy-host-b") -> dict:
    """A structurally valid @2 observation bound to the real collector identity."""
    collector_source = SCRIPTS / "collect-linux.py"
    executable = Path(sys.executable)
    observation = {
        "schema": "axm-community-lab/host-observation@2",
        "observed_at": "2026-08-05T00:00:00Z",
        "platform": "linux",
        "host_id": host_id,
        "collector": {
            "schema": "axm-community-lab/host-observation-collector@1",
            "platform": "linux",
            "source_path": str(collector_source),
            "source_sha256": sha256_bytes(collector_source.read_bytes()),
            "python_executable": {
                "path": str(executable),
                "sha256": sha256_bytes(executable.read_bytes()),
                "version": "3.13.0",
            },
        },
        "system": {
            "hostname": "octo-n01",
            "os_release": "Ubuntu 24.04.1 LTS",
            "os_version": "24.04",
            "os_id": "ubuntu",
            "kernel": "6.8.0-45-generic",
            "kernel_version": "#45-Ubuntu SMP",
            "architecture": "x86_64",
            "manufacturer": "FixtureSystems",
            "model": "EdgeNode NUC",
            "firmware": {"bios_manufacturer": "Fixture BIOS Inc", "bios_version": "1.2.3"},
        },
        "cpu": [{"name": "Intel(R) Core(TM) i5-13500T", "cores": 14, "logical_processors": 20}],
        "memory": {
            "total_bytes": 33554432000,
            "modules": [],
            "modules_available": False,
            "modules_source": {"path": "/sys/firmware/dmi/tables/DMI", "readable": False, "note": "not readable without sudo"},
        },
        "storage": {
            "physical_disks": [{"name": "nvme0n1", "model": "Fixture NVMe", "size_bytes": 2000000000000, "rotational": 0}],
            "logical_volumes": [],
            "source": "lsblk",
            "available": True,
            "note": None,
        },
        "graphics": {
            "adapters": [
                {
                    "name": "Alder Lake-N",
                    "device_class": "VGA compatible controller",
                    "pnp_device_id": "00:02.0",
                    "bus_id": "00:02.0",
                    "vendor_guess": "Intel",
                    "role_candidate": "igpu-candidate",
                }
            ],
            "nvidia": [{"uuid": "GPU-fixture-3090", "name": "NVIDIA GeForce RTX 3090", "memory_total_mib": 24576}],
        },
        "network": {"adapters": [{"name": "eth0", "state": "up", "mtu": 1500, "speed_mbps": 1000}], "addresses_collected": False},
        "runtime": [
            {"name": "python", "present": True, "path": "/usr/bin/python3", "disabled": False, "disabled_reason": None},
            {"name": "git", "present": True, "path": "/usr/bin/git", "disabled": False, "disabled_reason": None},
            {"name": "ollama", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},
            {"name": "docker", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},
            {"name": "wsl", "present": False, "path": None, "disabled": True, "disabled_reason": "not applicable on a native Linux host"},
            {"name": "nvidia-smi", "present": True, "path": "/usr/bin/nvidia-smi", "disabled": False, "disabled_reason": None},
        ],
        "clock": {
            "stopwatch_frequency_hz": 1000000000,
            "monotonic_resolution_ns": 1,
            "samples": [{"wall_utc": "2026-08-05T00:00:00Z", "monotonic_ns": 1, "perf_counter_ns": 1}],
            "cross_host_offset_measured": False,
        },
        "surfaces": {
            "files": {"proc_cpuinfo": {"path": "/proc/cpuinfo", "readable": True}},
            "tools": {"lsblk": {"available": True, "path": "/usr/bin/lsblk", "note": None}},
        },
        "privacy": {
            "serial_numbers_collected": False,
            "mac_addresses_collected": False,
            "ip_addresses_collected": False,
            "machine_guid_collected": False,
        },
    }
    observation["observation_sha256"] = sha256_bytes(canonical_bytes(observation))
    return observation


class SeedIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_seed_module("seed_verify_under_test", "verify.py")
        self.reconstructor = load_seed_module("seed_reconstruct_under_test", "reconstruct.py")
        self.manifest = json.loads((SEED / "seed-manifest.json").read_text(encoding="utf-8"))

    def test_committed_seed_verifies_against_its_own_sums(self):
        self.assertEqual(self.verifier.verify(ROOT), [])

    def test_sums_file_is_plain_ascii_lf_without_bom(self):
        raw = (ROOT / SUM_FILE).read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "a BOM would corrupt the first digest")
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))
        raw.decode("ascii")

    def test_every_seed_file_is_lf_without_bom(self):
        for name in self.manifest["files"]:
            with self.subTest(name=name):
                raw = (ROOT / name).read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"{name} carries a BOM")
                self.assertNotIn(b"\r", raw, f"{name} carries CRLF and would break its digest on Linux")

    def test_manifest_and_sums_bind_exactly_the_same_files(self):
        sums = self.verifier.load_sums(ROOT / SUM_FILE)
        self.assertEqual(set(sums), set(self.manifest["files"]))
        self.assertNotIn(SUM_FILE, self.manifest["files"], "the sum file must not bind itself")
        for name, expected in sums.items():
            with self.subTest(name=name):
                self.assertEqual(sha256_bytes((ROOT / name).read_bytes()), expected)

    def test_seed_id_is_the_digest_of_the_sum_file_bytes(self):
        self.assertEqual(
            self.verifier.seed_id(ROOT),
            sha256_bytes((ROOT / SUM_FILE).read_bytes()),
        )

    def test_verification_refuses_a_tampered_seed_file(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle = Path(raw) / "bundle"
            self.reconstructor.reconstruct(ROOT, bundle)
            self.assertEqual(self.verifier.verify(bundle), [])
            target = bundle / "scripts" / "collect-linux.py"
            target.write_bytes(target.read_bytes() + b"# smuggled line\n")
            failures = self.verifier.verify(bundle)
            self.assertTrue(any("digest mismatch" in item for item in failures))
            self.assertTrue(any("collect-linux.py" in item for item in failures))

    def test_verification_refuses_a_truncated_seed(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle = Path(raw) / "bundle"
            self.reconstructor.reconstruct(ROOT, bundle)
            (bundle / "seed" / "collect-linux.validator.py").unlink()
            failures = self.verifier.verify(bundle)
            self.assertTrue(any("seed file missing" in item for item in failures))

    def test_verification_refuses_a_crlf_converted_sum_file(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle = Path(raw) / "bundle"
            self.reconstructor.reconstruct(ROOT, bundle)
            sums = bundle / SUM_FILE
            sums.write_bytes(sums.read_bytes().replace(b"\n", b"\r\n"))
            failures = self.verifier.verify(bundle)
            self.assertTrue(any("CRLF" in item for item in failures))


class SeedReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.reconstructor = load_seed_module("seed_reconstruct_under_test", "reconstruct.py")

    def run_reconstruct(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = self.reconstructor.main(argv)
        return code, json.loads(stream.getvalue())

    def test_reconstruction_is_byte_identical_across_two_runs(self):
        code, result = self.run_reconstruct(["--root", str(ROOT)])
        self.assertEqual(code, 0)
        self.assertTrue(result["ok"])
        self.assertTrue(result["byte_identical"])
        first, second = result["runs"]
        self.assertEqual(first["files"], second["files"])
        self.assertEqual(first["bundle_sha256"], second["bundle_sha256"])
        self.assertEqual(first["bundle_sha256"], result["source_bundle_sha256"])

    def test_materialized_bundle_verifies_and_matches_committed_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "seed-bundle"
            code, result = self.run_reconstruct(["--root", str(ROOT), "--into", str(destination)])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            for name, digest in result["files"].items():
                with self.subTest(name=name):
                    self.assertEqual(digest, sha256_bytes((ROOT / name).read_bytes()))
                    self.assertEqual((destination / name).read_bytes(), (ROOT / name).read_bytes())

    def test_reconstruction_refuses_when_source_is_tampered(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle = Path(raw) / "bundle"
            self.reconstructor.reconstruct(ROOT, bundle)
            target = bundle / "seed" / "seed-manifest.json"
            target.write_bytes(target.read_bytes().replace(b"axm-tools#151", b"axm-tools#000"))
            code, result = self.run_reconstruct(["--root", str(bundle)])
            self.assertEqual(code, 1)
            self.assertFalse(result["ok"])
            self.assertEqual(result["stage"], "source")


class SeedIndependenceTests(unittest.TestCase):
    """The seed must run on a host with no clone of this repository."""

    def setUp(self):
        self.reconstructor = load_seed_module("seed_reconstruct_under_test", "reconstruct.py")
        self.manifest = json.loads((SEED / "seed-manifest.json").read_text(encoding="utf-8"))

    def test_no_seed_file_imports_a_repository_module(self):
        for name in self.manifest["files"]:
            if not name.endswith(".py"):
                continue
            source = (ROOT / name).read_bytes().decode("utf-8")
            for module in REPOSITORY_MODULES:
                with self.subTest(name=name, module=module):
                    self.assertNotIn(f"import {module}", source)
                    self.assertNotIn(f"from {module} import", source)

    def test_validator_runs_from_a_materialized_bundle_without_the_repository(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bundle = root / "seed-bundle"
            self.reconstructor.reconstruct(ROOT, bundle)
            observation_path = root / "heavy-host-b.json"
            observation_path.write_bytes(
                (json.dumps(valid_observation(), indent=2) + "\n").encode("utf-8")
            )
            completed = subprocess.run(
                [sys.executable, str(bundle / "seed" / "collect-linux.validator.py"), str(observation_path)],
                capture_output=True,
                text=True,
                cwd=str(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["ok"])

    def test_seed_verification_runs_from_a_materialized_bundle(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle = Path(raw) / "seed-bundle"
            self.reconstructor.reconstruct(ROOT, bundle)
            completed = subprocess.run(
                [sys.executable, str(bundle / "seed" / "verify.py"), "--root", str(bundle)],
                capture_output=True,
                text=True,
                cwd=str(raw),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["seed_id"], sha256_bytes((ROOT / SUM_FILE).read_bytes()))


class SeedPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((SEED / "seed-manifest.json").read_text(encoding="utf-8"))
        self.files = list(self.manifest["files"]) + [SUM_FILE]

    def test_seed_carries_no_address_or_credential_material(self):
        for name in self.files:
            text = (ROOT / name).read_bytes().decode("utf-8")
            with self.subTest(name=name):
                self.assertIsNone(MAC_RE.search(text), f"{name} carries a MAC address")
                self.assertIsNone(IPV4_RE.search(text), f"{name} carries an IP address")
                self.assertIsNone(IPV6_RE.search(text), f"{name} carries an IPv6 address")
                for marker in ("BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", "ssh-rsa ", "ssh-ed25519 "):
                    self.assertNotIn(marker, text, f"{name} carries {marker}")

    def test_seed_declares_no_transport_and_no_callback(self):
        for name in self.files:
            if not name.endswith(".py") and not name.endswith("collect-linux"):
                continue
            source = (ROOT / name).read_bytes().decode("utf-8")
            with self.subTest(name=name):
                for transport in ("import socket", "import urllib", "import http", "import ftplib", "curl ", "wget "):
                    self.assertNotIn(transport, source, f"{name} references {transport}")

    def test_seed_names_no_tailscale_or_remote_host_identity(self):
        """Naming a refused identifier class is law; carrying one is a leak.

        "tailscale" appears legitimately in the prohibited-marker list and in
        the boundary prose, so the witness looks for actual coordinates and
        credentials instead of the word.
        """
        for name in self.files:
            text = (ROOT / name).read_bytes().decode("utf-8").lower()
            with self.subTest(name=name):
                for marker in (
                    ".ts.net",
                    "tskey-",
                    "tailscale up",
                    "--authkey",
                    "authorized_keys",
                    "ssh -i ",
                    "id_rsa",
                    "id_ed25519",
                ):
                    self.assertNotIn(marker, text, f"{name} carries {marker}")

    def test_manifest_states_the_authority_and_claim_boundary(self):
        authority = self.manifest["authority_boundary"].lower()
        for phrase in ("no sudo", "installs nothing", "opens no socket", "no network request"):
            self.assertIn(phrase, authority)
        claim = self.manifest["claim_boundary"].lower()
        self.assertIn("cannot substitute", claim)
        self.assertIn("physical host execution", claim)


class SeedSchemaAndValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = load_seed_module("seed_validator_under_test", "collect-linux.validator.py")
        self.schema = json.loads((SEED / "collect-linux-host-observation-2.schema.json").read_text(encoding="utf-8"))

    def test_schema_pins_the_closed_runtime_denominator(self):
        runtime = self.schema["properties"]["runtime"]
        self.assertEqual(runtime["minItems"], 6)
        self.assertEqual(runtime["maxItems"], 6)
        self.assertEqual(
            set(runtime["items"]["properties"]["name"]["enum"]),
            {"python", "git", "ollama", "docker", "wsl", "nvidia-smi"},
        )
        self.assertEqual(
            set(runtime["items"]["required"]),
            {"name", "present", "path", "disabled", "disabled_reason"},
        )

    def test_schema_refuses_address_collection_by_construction(self):
        self.assertIs(self.schema["properties"]["network"]["properties"]["addresses_collected"]["const"], False)
        privacy = self.schema["properties"]["privacy"]["properties"]
        for field in ("serial_numbers_collected", "mac_addresses_collected", "ip_addresses_collected", "machine_guid_collected"):
            self.assertIs(privacy[field]["const"], False)

    def test_schema_requires_platform_and_collector_identity(self):
        self.assertIn("platform", self.schema["required"])
        self.assertIn("collector", self.schema["required"])
        self.assertIn("surfaces", self.schema["required"])
        collector = self.schema["properties"]["collector"]
        self.assertEqual(
            set(collector["required"]),
            {"schema", "platform", "source_path", "source_sha256", "python_executable"},
        )

    def test_validator_accepts_a_well_formed_observation(self):
        self.assertEqual(self.validator.validate(valid_observation()), [])

    def test_validator_refuses_an_observation_digest_tamper(self):
        observation = valid_observation()
        observation["memory"]["total_bytes"] = 1
        self.assertIn("observation digest mismatch", self.validator.validate(observation))

    def test_validator_refuses_a_collector_source_digest_tamper(self):
        observation = valid_observation()
        observation["collector"]["source_sha256"] = "0" * 64
        observation["observation_sha256"] = sha256_bytes(
            canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
        )
        self.assertIn("collector source digest mismatch", self.validator.validate(observation))

    def test_validator_refuses_a_missing_runtime_row(self):
        observation = valid_observation()
        observation["runtime"] = [row for row in observation["runtime"] if row["name"] != "wsl"]
        observation["observation_sha256"] = sha256_bytes(
            canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
        )
        failures = self.validator.validate(observation)
        self.assertTrue(any("runtime denominator mismatch" in item for item in failures))

    def test_validator_refuses_a_duplicate_runtime_row(self):
        observation = valid_observation()
        observation["runtime"].append(dict(observation["runtime"][0]))
        observation["observation_sha256"] = sha256_bytes(
            canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
        )
        failures = self.validator.validate(observation)
        self.assertTrue(any("runtime denominator mismatch" in item for item in failures))

    def test_validator_refuses_a_contradictory_runtime_row(self):
        observation = valid_observation()
        observation["runtime"][0]["disabled"] = True
        observation["observation_sha256"] = sha256_bytes(
            canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
        )
        failures = self.validator.validate(observation)
        self.assertTrue(any("runtime row contradictory" in item for item in failures))

    def test_validator_refuses_a_wsl_row_that_claims_applicability(self):
        observation = valid_observation()
        wsl = next(row for row in observation["runtime"] if row["name"] == "wsl")
        wsl["disabled_reason"] = "command not found in the current process PATH"
        observation["observation_sha256"] = sha256_bytes(
            canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
        )
        failures = self.validator.validate(observation)
        self.assertTrue(any("disabled_reason" in item for item in failures))

    def test_validator_refuses_retained_private_identifiers(self):
        for field, value in (
            ("serial_number", "S/N-12345"),
            # RFC 7042 / RFC 5737 documentation values: refusal witnesses,
            # never a routable or host-derived identifier.
            ("mac_address", "00:00:5e:00:53:01"),
            ("ip_address", "192.0.2.31"),
            ("machine_guid", "12345678-1234-1234-1234-123456789abc"),
            ("api_token", "sk-live-abcdef"),
            ("tailscale_node", "n01.example.ts.net"),
        ):
            with self.subTest(field=field):
                observation = valid_observation()
                observation["system"][field] = value
                observation["observation_sha256"] = sha256_bytes(
                    canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
                )
                failures = self.validator.validate(observation)
                self.assertTrue(
                    any("prohibited private field retained" in item and field in item for item in failures),
                    msg=f"{field} was not refused",
                )

    def test_validator_accepts_explicit_privacy_refusals(self):
        """An explicit `false` refusal is compliance, not retention."""
        observation = valid_observation()
        self.assertEqual(self.validator.collect_private_fields(observation["privacy"]), [])
        self.assertTrue(all(marker for marker in PROHIBITED_FIELD_MARKERS))

    def test_validator_refuses_a_non_linux_platform(self):
        observation = valid_observation()
        observation["platform"] = "windows"
        observation["observation_sha256"] = sha256_bytes(
            canonical_bytes({k: v for k, v in observation.items() if k != "observation_sha256"})
        )
        self.assertIn("platform must be linux", self.validator.validate(observation))

    def test_validator_only_reads(self):
        """Validating must not create, move, or delete anything."""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "heavy-host-b.json"
            path.write_bytes((json.dumps(valid_observation(), indent=2) + "\n").encode("utf-8"))
            before = sorted(item.name for item in root.iterdir())
            digest_before = sha256_bytes(path.read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.validator.main([str(path)]), 0)
            self.assertEqual(sorted(item.name for item in root.iterdir()), before)
            self.assertEqual(sha256_bytes(path.read_bytes()), digest_before)


if __name__ == "__main__":
    unittest.main()
