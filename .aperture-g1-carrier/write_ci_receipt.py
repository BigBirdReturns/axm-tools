#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def command_version(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise SystemExit(f"cannot execute tool version command {command}: {exc}") from exc
    value = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0 or not value:
        raise SystemExit(f"cannot determine tool version for {command}: {value}")
    return value.splitlines()[0]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary_path = root / "reports/conformance/summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "PASS":
        raise SystemExit(f"cross-language conformance did not pass: {summary}")
    if summary.get("case_count") != manifest["conformance"]["case_count"]:
        raise SystemExit("conformance case denominator drift")
    expected = manifest["conformance"]["expected_common_result_sha256"]
    if summary.get("common_result_sha256") != expected:
        raise SystemExit("common conformance result digest drift")
    expected_implementations = sorted(manifest["conformance"]["implementations"])
    if sorted(summary.get("executed_implementations", [])) != expected_implementations:
        raise SystemExit("not every required implementation executed")

    result_paths = {
        name: root / "reports/conformance" / f"{name}.json"
        for name in expected_implementations
    }
    result_bytes = {name: path.read_bytes() for name, path in result_paths.items()}
    if len(set(result_bytes.values())) != 1:
        raise SystemExit("hosted implementation outputs are not byte-identical")
    result_hashes = {name: digest(path) for name, path in result_paths.items()}
    if set(result_hashes.values()) != {expected}:
        raise SystemExit(f"hosted result digest mismatch: {result_hashes}")

    receipt = {
        "format": "axm-aperture-csharp-conformance-ci/1",
        "provider": "github-actions",
        "conclusion": "success",
        "authority": "mechanism-qualification-only",
        "run_url": args.run_url,
        "repository": args.repository,
        "ref": args.ref,
        "commit": args.commit,
        "protocol_version": manifest["conformance"]["protocol_version"],
        "case_count": manifest["conformance"]["case_count"],
        "source_sha256": digest(root / "conformance/csharp/Program.cs"),
        "project_sha256": digest(root / "conformance/csharp/Aperture.Conformance.csproj"),
        "result_sha256": result_hashes["csharp"],
        "common_result_sha256": expected,
        "summary_sha256": digest(summary_path),
        "toolchain": {
            "python": platform.python_version(),
            "node": command_version(["node", "--version"]),
            "typescript": command_version(["tsc", "--version"]),
            "dotnet": command_version(["dotnet", "--version"]),
        },
        "limits": [
            "The transport branch is not the normative Aperture repository.",
            "This receipt proves contract compilation and cross-language byte parity only.",
            "No playback adapter, player, story package, or release gate is accepted by this receipt."
        ],
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical(receipt)).hexdigest()
    output = root / "receipts/G1-csharp-ci.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
