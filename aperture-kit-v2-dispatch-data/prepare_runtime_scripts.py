#!/usr/bin/env python3
from __future__ import annotations
import hashlib, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
PARTS = [{'path': 'runtime-segments/qualify-00.part', 'bytes': 2400, 'sha256': '6a8badea4a85dc2be0cdba7ea26f78501497f5f27c8799c810123311c69515ec'}, {'path': 'runtime-segments/qualify-01.part', 'bytes': 2400, 'sha256': '9bcee4e1fec0c7e94dcb9c95d3af341979bc07328b66a437547072902179e646'}, {'path': 'runtime-segments/qualify-02.part', 'bytes': 2265, 'sha256': '6b65f3441dab5bb26402c41c352bc491ec3501264ef8be9b5fef176f4b58fe3d'}]
EXPECTED_BYTES = 7065
EXPECTED_SHA256 = "0b9bd6c8f4bbcedea3d7a9279fd6475d7f00eae488a1f005c74acb21fe87e26b"
def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
out = bytearray()
for item in PARTS:
    p = ROOT / item["path"]
    if not p.is_file(): raise SystemExit(f"REFUSED: missing runtime segment {p}")
    b = p.read_bytes()
    if len(b) != item["bytes"] or sha(b) != item["sha256"]: raise SystemExit(f"REFUSED: runtime segment drift {p}")
    out.extend(b)
if len(out) != EXPECTED_BYTES or sha(out) != EXPECTED_SHA256: raise SystemExit("REFUSED: reconstructed qualify.py drift")
target = ROOT / "scripts" / "qualify.py"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(out)
print(f"PASS: reconstructed {target} bytes={len(out)} sha256={sha(out)}")
