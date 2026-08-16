#!/usr/bin/env python3
"""Correct duplicate authored overlay geometry detection."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


path = Path("manzanita-next/overlays/build_overlays.py")
text = path.read_text(encoding="utf-8")
old = '''        geometry = validate_geometry(authored_geometries[geometry_id], overlay_id)
        require(geometry["payload_sha256"] not in geometry_digests, f"Duplicate authored geometry for {overlay_id}")
        geometry_digests.add(geometry["payload_sha256"])
'''
new = '''        geometry = validate_geometry(authored_geometries[geometry_id], overlay_id)
        registration_identity = sha256_bytes(
            canonical_bytes(
                {
                    "geometry_type": geometry["geometry_type"],
                    "coordinate_space": geometry["coordinate_space"],
                    "coordinates": geometry["coordinates"],
                    "edges": geometry["edges"],
                    "source_class": geometry["source_class"],
                    "legend_symbol": geometry["legend_symbol"],
                    "claim_boundary": geometry["claim_boundary"],
                }
            )
        )
        require(registration_identity not in geometry_digests, f"Duplicate authored geometry for {overlay_id}")
        geometry_digests.add(registration_identity)
'''
if old in text:
    text = text.replace(old, new, 1)
require(
    "registration_identity = sha256_bytes(" in text,
    "The duplicate registration-identity correction did not apply",
)
path.write_text(text, encoding="utf-8")
