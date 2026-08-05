#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_checksums(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.lstrip("* ")
        if name in rows:
            raise SystemExit(f"duplicate checksum path: {name}")
        rows[name] = digest.lower()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    receipt = json.loads((root / "provider-runtime-ferry.json").read_text(encoding="utf-8"))
    if receipt.get("format") != "axm-aperture-g2-provider-runtime-ferry/1":
        raise SystemExit("unsupported ferry receipt")
    if receipt.get("authority") != "transport_only":
        raise SystemExit("transport acquired authority")

    expected = load_checksums(root / "SHA256SUMS")
    actual_names = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.name
        not in {"SHA256SUMS", "SHA512SUMS", "verification.json", "verification.json.sha256"}
    }
    if set(expected) != actual_names:
        missing = sorted(actual_names - set(expected))
        extra = sorted(set(expected) - actual_names)
        raise SystemExit(f"checksum denominator mismatch missing={missing} extra={extra}")
    for name, digest in sorted(expected.items()):
        observed = sha(root / name)
        if observed != digest:
            raise SystemExit(f"sha256 mismatch: {name}: {observed} != {digest}")

    for provider in receipt["providers"]:
        bundle = root / provider["bundle"]
        output = subprocess.check_output(
            ["git", "bundle", "list-heads", str(bundle)],
            text=True,
        )
        heads = {
            line.split()[1]: line.split()[0]
            for line in output.splitlines()
            if line.strip()
        }
        for role in ("base", "feature", "landed"):
            ref = f"refs/heads/aperture-g2/{role}"
            if heads.get(ref) != provider[role]:
                raise SystemExit(f"{provider['name']} {role} ref mismatch")

    print(
        json.dumps(
            {
                "status": "PASS",
                "receipt_sha256": sha(root / "provider-runtime-ferry.json"),
                "file_count": len(expected),
                "providers": [provider["name"] for provider in receipt["providers"]],
                "mpv_version": receipt["mpv"]["version"],
                "python": receipt["python"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
