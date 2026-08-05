from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one target, found {count}")
    return text.replace(old, new, 1)


def repair_collector() -> None:
    path = ROOT / "scripts" / "collect-windows.ps1"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "runtime rows",
        '''    $runtimeRows += [ordered]@{
        name = $name
        present = [bool]$command
        path = if ($command) { $command.Source } else { $null }
    }
''',
        '''    $present = [bool]$command
    $runtimeRows += [ordered]@{
        name = $name
        present = $present
        path = if ($present) { $command.Source } else { $null }
        disabled = (-not $present)
        disabled_reason = if ($present) { $null } else { "command not found in the current process PATH" }
    }
''',
    )
    text = replace_once(
        text,
        "BOM-producing writer",
        '$body | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $destination -Encoding UTF8\n',
        '$json = $body | ConvertTo-Json -Depth 16\n$utf8NoBom = New-Object System.Text.UTF8Encoding($false)\n[IO.File]::WriteAllText($destination, $json + "`n", $utf8NoBom)\n',
    )
    path.write_bytes(text.encode("utf-8"))


def repair_qualifier() -> None:
    path = ROOT / "scripts" / "lab.py"
    text = path.read_text(encoding="utf-8")
    helper = '''
def disabled_with_reason_failures(
    observation: Mapping[str, Any], host_id: str
) -> list[str]:
    runtime = observation.get("runtime")
    if not isinstance(runtime, list):
        return [f"{host_id}: runtime inventory missing"]
    failures: list[str] = []
    seen: set[str] = set()
    required = {"python", "git", "ollama", "docker", "wsl", "nvidia-smi"}
    for index, raw in enumerate(runtime):
        if not isinstance(raw, Mapping):
            failures.append(f"{host_id}: runtime[{index}] is not an object")
            continue
        name = str(raw.get("name") or "").strip()
        label = name or f"runtime[{index}]"
        if not name:
            failures.append(f"{host_id}: runtime[{index}] name missing")
        elif name in seen:
            failures.append(f"{host_id}: duplicate runtime identity: {name}")
        else:
            seen.add(name)
        present = raw.get("present")
        disabled = raw.get("disabled")
        reason = raw.get("disabled_reason")
        executable = raw.get("path")
        if present is True:
            if disabled is not False:
                failures.append(f"{host_id}: {label} is present but not explicitly enabled")
            if not isinstance(executable, str) or not executable.strip():
                failures.append(f"{host_id}: {label} is present without an executable path")
            if reason is not None and reason != "":
                failures.append(f"{host_id}: {label} is present but carries a disabled reason")
        elif present is False:
            if disabled is not True:
                failures.append(f"{host_id}: {label} is absent but not explicitly disabled")
            if not isinstance(reason, str) or not reason.strip():
                failures.append(f"{host_id}: {label} is disabled without a reason")
            if executable is not None:
                failures.append(f"{host_id}: {label} is disabled but still declares a path")
        else:
            failures.append(f"{host_id}: {label} present must be boolean")
    missing = sorted(required - seen)
    if missing:
        failures.append(f"{host_id}: runtime identities missing: {', '.join(missing)}")
    return failures


'''
    text = replace_once(
        text,
        "qualifier helper insertion",
        "\ndef qualify_estate(\n",
        "\n" + helper + "def qualify_estate(\n",
    )
    text = replace_once(
        text,
        "disabled failure ledger",
        "    host_rows: list[dict[str, Any]] = []\n    inventory_failures: list[str] = []\n    device_failures: list[str] = []\n",
        "    host_rows: list[dict[str, Any]] = []\n    inventory_failures: list[str] = []\n    disabled_reason_failures: list[str] = []\n    device_failures: list[str] = []\n",
    )
    text = replace_once(
        text,
        "per-host disabled check",
        '        system = observation.get("system", {})\n        cpu = observation.get("cpu", [])\n',
        '        disabled_reason_failures.extend(\n            disabled_with_reason_failures(observation, host_id)\n        )\n        system = observation.get("system", {})\n        cpu = observation.get("cpu", [])\n',
    )
    text = replace_once(
        text,
        "aggregate disabled ledger",
        '            "host_inventory": inventory_failures,\n            "device_identity": device_failures,\n',
        '            "host_inventory": inventory_failures,\n            "disabled_with_reason": disabled_reason_failures,\n            "device_identity": device_failures,\n',
    )
    text = replace_once(
        text,
        "host inventory admission",
        "    host_inventory_ok = not failures and not inventory_failures and len(loaded) == len(expected_hosts)\n",
        "    host_inventory_ok = (\n        not failures\n        and not inventory_failures\n        and not disabled_reason_failures\n        and len(loaded) == len(expected_hosts)\n    )\n",
    )
    text = replace_once(
        text,
        "disabled check receipt",
        '        {\n            "id": "six-accelerator-domains-explicit",\n',
        '        {\n            "id": "disabled-components-carry-reasons",\n            "pass": not disabled_reason_failures,\n            "detail": disabled_reason_failures or "every absent runtime is explicitly disabled with a reason",\n        },\n        {\n            "id": "six-accelerator-domains-explicit",\n',
    )
    path.write_bytes(text.encode("utf-8"))


def repair_tests() -> None:
    path = ROOT / "tests" / "test_lab.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "fixture runtime custody",
        '        "network": {"adapters": [{"name": "Ethernet", "link_speed": "1 Gbps"}]},\n        "clock": {"stopwatch_frequency_hz": 10000000, "samples": []},\n',
        '        "network": {"adapters": [{"name": "Ethernet", "link_speed": "1 Gbps"}]},\n        "runtime": [\n            {"name": "python", "present": True, "path": "C:\\\\Python\\\\python.exe", "disabled": False, "disabled_reason": None},\n            {"name": "git", "present": True, "path": "C:\\\\Git\\\\git.exe", "disabled": False, "disabled_reason": None},\n            {"name": "ollama", "present": True, "path": "C:\\\\Ollama\\\\ollama.exe", "disabled": False, "disabled_reason": None},\n            {"name": "nvidia-smi", "present": True, "path": "C:\\\\NVIDIA\\\\nvidia-smi.exe", "disabled": False, "disabled_reason": None},\n            {"name": "docker", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},\n            {"name": "wsl", "present": False, "path": None, "disabled": True, "disabled_reason": "command not found in the current process PATH"},\n        ],\n        "clock": {"stopwatch_frequency_hz": 10000000, "samples": []},\n',
    )
    methods = textwrap.indent(
        textwrap.dedent(
            '''
            def test_disabled_runtime_without_reason_blocks_census(self):
                with tempfile.TemporaryDirectory() as raw:
                    base = Path(raw)
                    state = base / "state"
                    files = []
                    for host_id, gpu_uuid in (("control-host", "GPU-4060"), ("heavy-host-a", "GPU-3090-A"), ("heavy-host-b", "GPU-3090-B")):
                        item = observation(host_id, gpu_uuid)
                        if host_id == "heavy-host-a":
                            item["runtime"][4]["disabled_reason"] = None
                        source = base / f"{host_id}.json"
                        source.write_text(json.dumps(item, indent=2) + "\\n", encoding="utf-8")
                        files.append(source)
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

            def test_collector_uses_bom_free_utf8(self):
                source = (SCRIPTS / "collect-windows.ps1").read_text(encoding="utf-8")
                self.assertIn("System.Text.UTF8Encoding($false)", source)
                self.assertIn("[IO.File]::WriteAllText", source)
                self.assertNotIn("Set-Content -LiteralPath $destination -Encoding UTF8", source)

            '''
        ).lstrip("\n"),
        "    ",
    )
    text = replace_once(
        text,
        "negative and BOM tests",
        "    def test_blocked_experiment_cannot_open_run(self):\n",
        methods + "    def test_blocked_experiment_cannot_open_run(self):\n",
    )
    path.write_bytes(text.encode("utf-8"))


def main() -> None:
    repair_collector()
    repair_qualifier()
    repair_tests()


if __name__ == "__main__":
    main()
