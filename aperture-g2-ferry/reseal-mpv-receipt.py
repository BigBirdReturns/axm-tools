#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: reseal-mpv-receipt.py <out> <mpv-root>")
    out = Path(sys.argv[1])
    mpv_root = Path(sys.argv[2])
    receipt_path = out / "provider-runtime-ferry.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("format") != "axm-aperture-g2-provider-runtime-ferry/1":
        raise SystemExit("unexpected ferry receipt format")
    if receipt.get("authority") != "transport_only":
        raise SystemExit("ferry receipt acquired authority")
    if receipt.get("accepted_gates") != []:
        raise SystemExit("ferry receipt attempted gate acceptance")

    bundle = out / "mpv" / "mpv-linux-x64-portable.tar.gz"
    wrapper = mpv_root / "mpv-portable"
    receipt["mpv"]["bundle_sha256"] = sha256(bundle)
    receipt["mpv"]["portable_wrapper_sha256"] = sha256(wrapper)
    receipt.pop("receipt_sha256", None)
    core = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receipt_sha256"] = hashlib.sha256(core).hexdigest()
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
