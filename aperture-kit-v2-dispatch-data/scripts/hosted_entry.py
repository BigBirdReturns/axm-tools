#!/usr/bin/env python3
from __future__ import annotations
import argparse, pathlib, subprocess, sys

SOURCE = "AXM-Aperture-G3-Platform-Observation-Kit-v2.tar.gz"

def run(command: list[str]) -> None:
    subprocess.run(command, check=True)

def prepare(root: pathlib.Path, hosted: bool = False) -> None:
    run([sys.executable, str(root / "prepare_segmented_chunks.py")])
    run([sys.executable, str(root / "prepare_runtime_scripts.py")])
    if hosted: run([sys.executable, str(root / "prepare_hosted_stage.py")])

def qualify(root: pathlib.Path, work: pathlib.Path, label: str) -> None:
    run([sys.executable, str(root / "scripts/qualify.py"), "--data-root", str(root), "--work-root", str(work), "--runner-label", label])

def main() -> None:
    p = argparse.ArgumentParser(); s = p.add_subparsers(dest="mode", required=True)
    source = s.add_parser("source"); source.add_argument("--data-root", type=pathlib.Path, required=True); source.add_argument("--work-root", type=pathlib.Path, required=True); source.add_argument("--runner-label", required=True)
    custody = s.add_parser("custody"); custody.add_argument("--data-root", type=pathlib.Path, required=True); custody.add_argument("--temp-root", type=pathlib.Path, required=True); custody.add_argument("--os-receipts", type=pathlib.Path, required=True); custody.add_argument("--output", type=pathlib.Path, required=True)
    witness = s.add_parser("witness"); witness.add_argument("--data-root", type=pathlib.Path, required=True); witness.add_argument("--downloaded", type=pathlib.Path, required=True); witness.add_argument("--output", type=pathlib.Path, required=True)
    a = p.parse_args(); root = a.data_root.resolve()
    if a.mode == "source":
        prepare(root); qualify(root, a.work_root.resolve(), a.runner_label); return
    if a.mode == "custody":
        prepare(root, hosted=True); temp = a.temp_root.resolve(); cold_a, cold_b = temp / "cold-a", temp / "cold-b"
        qualify(root, cold_a, "custody"); qualify(root, cold_b, "custody")
        for rel in (SOURCE, "blocked-progress.json", "qualification.env"):
            if (cold_a / rel).read_bytes() != (cold_b / rel).read_bytes(): raise SystemExit(f"REFUSED: cold-root drift {rel}")
        run([sys.executable, str(root / "scripts/hosted_stage.py"), "seal-carrier", "--cold-a", str(cold_a), "--cold-b", str(cold_b), "--os-receipts", str(a.os_receipts), "--output", str(a.output)]); return
    prepare(root, hosted=True)
    run([sys.executable, str(root / "scripts/hosted_stage.py"), "replay", "--downloaded", str(a.downloaded), "--output", str(a.output)])
if __name__ == "__main__": main()
