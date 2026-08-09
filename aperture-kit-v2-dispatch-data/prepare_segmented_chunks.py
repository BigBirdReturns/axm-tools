#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
CHUNKS = ROOT / "chunks"

ASSEMBLIES = {
    "part-06.b64": {
        "bytes": 15009,
        "sha256": "c342f8484402a0320db710fc74cbd8da148373ae986e9e4375ecee0ffc0b6722",
        "segments": [
            ("part-06.segment-00", 5003, "95ed98d5d736f12620e4d1a87f5f4601598aeaab1322bc4c69b42bd459c6f673"),
            ("part-06.segment-01", 5003, "9b2b11925d73212c6100803101fcfb20aea62e9e9d935388acaed7f87936fec2"),
            ("part-06.segment-02", 5003, "552f79d35bc1245f3a17d67522856eceb518bab4bceef4b46a90714b6cef56f9"),
        ],
    },
    "part-07.b64": {
        "bytes": 14985,
        "sha256": "4685b0be18365a02118e71855c776a1e2c0e8fd45a0b6dd8dcfaf7323461fbee",
        "segments": [
            ("part-07.segment-00", 4995, "121ffe52dedba58a211496ac743faec256a17bbc0727bff0c31b756c0d0793fa"),
            ("part-07.segment-01", 4995, "cb058e8b7a698cf8315aa86a7651e1bc9e90193afad9557dc95709f9ff6d764d"),
            ("part-07.segment-02", 4995, "7fcb3b9a75612a34547d58ad1e31640a0543d4be365bc84f03824550d6860fa6"),
        ],
    },
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


for output_name, assembly in ASSEMBLIES.items():
    pieces: list[bytes] = []
    for segment_name, expected_bytes, expected_sha in assembly["segments"]:
        path = CHUNKS / segment_name
        if not path.is_file():
            raise SystemExit(f"REFUSED: missing segmented transport object {path}")
        raw = path.read_bytes()
        if len(raw) != expected_bytes or digest(raw) != expected_sha:
            raise SystemExit(f"REFUSED: segmented transport custody mismatch {path}")
        pieces.append(raw)
    combined = b"".join(pieces)
    if len(combined) != assembly["bytes"] or digest(combined) != assembly["sha256"]:
        raise SystemExit(f"REFUSED: assembled transport custody mismatch {output_name}")
    (CHUNKS / output_name).write_bytes(combined)

print("PASS: reconstructed exact part-06.b64 and part-07.b64 from six immutable segments")
