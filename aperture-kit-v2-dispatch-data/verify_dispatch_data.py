#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, json, pathlib, sys

EXPECTED_SHA = "71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74"
EXPECTED_BYTES = 90028
EXPECTED_CHUNKS = [{"base64_characters": 15008, "bytes": 15009, "order": 0, "path": "chunks/part-00.b64", "sha256": "1541536dc36b91941630b8b6fdbf0ba790be3158909e1c73cc1f799937ad26f7"}, {"base64_characters": 15008, "bytes": 15009, "order": 1, "path": "chunks/part-01.b64", "sha256": "680cc63427f11494f2dcd786155e027eb75eaab311a9cdf6c673d30e73099909"}, {"base64_characters": 15008, "bytes": 15009, "order": 2, "path": "chunks/part-02.b64", "sha256": "2b3c784f3681f77ad63b1130a04fda2f0f02d28f6e1a4c360d625613581af44b"}, {"base64_characters": 15008, "bytes": 15009, "order": 3, "path": "chunks/part-03.b64", "sha256": "750a049e54777b016d06d55ae0dd33bc42fe5dd3af82f1cd9697cba3d4008889"}, {"base64_characters": 15008, "bytes": 15009, "order": 4, "path": "chunks/part-04.b64", "sha256": "6d0f5e325a7c1c91887fa889cc479c805655b49b653eac8e9ac65c61b82d4cb7"}, {"base64_characters": 15008, "bytes": 15009, "order": 5, "path": "chunks/part-05.b64", "sha256": "458072437ae89b721f589ae6c77cb1f7d35a36f157979df1782033ead5bd1fe4"}, {"base64_characters": 15008, "bytes": 15009, "order": 6, "path": "chunks/part-06.b64", "sha256": "c342f8484402a0320db710fc74cbd8da148373ae986e9e4375ecee0ffc0b6722"}, {"base64_characters": 14984, "bytes": 14985, "order": 7, "path": "chunks/part-07.b64", "sha256": "4685b0be18365a02118e71855c776a1e2c0e8fd45a0b6dd8dcfaf7323461fbee"}]

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent)
parser.add_argument("--output", type=pathlib.Path)
args = parser.parse_args()
root = args.root.resolve()
parts = []
for item in EXPECTED_CHUNKS:
    path = root / item["path"]
    if not path.is_file():
        raise SystemExit(f"REFUSED: missing chunk {path}")
    raw = path.read_bytes()
    if len(raw) != item["bytes"] or digest(raw) != item["sha256"]:
        raise SystemExit(f"REFUSED: chunk custody mismatch {path}")
    parts.append(b"".join(raw.split()))
encoded = b"".join(parts)
try:
    decoded = base64.b64decode(encoded, validate=True)
except Exception as exc:
    raise SystemExit(f"REFUSED: invalid aggregate Base64: {exc}")
if len(decoded) != EXPECTED_BYTES:
    raise SystemExit(f"REFUSED: decoded bytes {len(decoded)} != {EXPECTED_BYTES}")
if digest(decoded) != EXPECTED_SHA:
    raise SystemExit(f"REFUSED: decoded SHA-256 {digest(decoded)} != {EXPECTED_SHA}")
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(decoded)
print(json.dumps({
    "status": "PASS",
    "source_bytes": len(decoded),
    "source_sha256": digest(decoded),
    "chunks": len(EXPECTED_CHUNKS),
}, sort_keys=True))
