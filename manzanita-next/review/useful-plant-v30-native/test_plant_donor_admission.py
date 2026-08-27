#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("plant_gate", HERE / "verify_plant_donors.py")
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def svg_fixture(width: int = 1600, height: int = 1000, extra: str = "") -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%"/>{extra}</svg>\n'
    ).encode("utf-8")


def webp_fixture(width: int = 1600, height: int = 1000) -> bytes:
    payload = bytes([0, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    chunk = b"VP8X" + len(payload).to_bytes(4, "little") + payload
    body = b"WEBP" + chunk
    return b"RIFF" + len(body).to_bytes(4, "little") + body


def contract(origin: bytes, cached: bytes, width: int = 1600, height: int = 1000) -> dict[str, Any]:
    return {
        "schema": "test",
        "gate_id": "TEST-PLANT-DONORS",
        "candidate_id": "TEST-CANDIDATE",
        "object_id": "MW-PLANT-BH02-001",
        "required_donors": {
            "origin": {
                "filename": "plant-origin.svg",
                "bytes": len(origin),
                "sha256": sha(origin),
                "width": width,
                "height": height,
                "view_box": f"0 0 {width} {height}",
            },
            "cached": {
                "filename": "plant-derived-reference.webp",
                "bytes": len(cached),
                "sha256": sha(cached),
                "width": width,
                "height": height,
            },
        },
        "passive_svg_floor": {
            "forbidden_markup": [
                "<!DOCTYPE",
                "<!ENTITY",
                "<?xml-stylesheet",
                "<script",
                "<foreignObject",
                "<iframe",
                "<object",
                "<embed",
            ],
            "forbidden_element_local_names": ["script", "foreignObject", "iframe", "object", "embed"],
            "forbidden_event_attribute_prefix": "on",
            "external_reference_allowed": False,
        },
        "next_gate_after_pass": "next",
        "authority": {
            "operator_visual_acceptance": "ABSENT",
            "merge_authorized": False,
            "release_authorized": False,
            "public_route_effect": "none",
            "pages_deployment_effect": "none",
            "external_effect": "none",
        },
    }


def write_pair(root: Path, origin: bytes, cached: bytes) -> tuple[Path, Path]:
    origin_path = root / "plant-origin.svg"
    cached_path = root / "plant-derived-reference.webp"
    origin_path.write_bytes(origin)
    cached_path.write_bytes(cached)
    return origin_path, cached_path


class PlantDonorAdmissionTests(unittest.TestCase):
    def test_exact_pair_passes_without_elevating_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture()
            cached = webp_fixture()
            origin_path, cached_path = write_pair(root, origin, cached)
            receipt = GATE.evaluate(origin_path, cached_path, contract(origin, cached))
            self.assertEqual(receipt["result"], "PASS_EXACT_PLANT_DONORS_ADMITTED")
            self.assertTrue(receipt["donors_admitted"])
            self.assertEqual(receipt["operator_visual_acceptance"], "ABSENT")
            self.assertFalse(receipt["merge_authorized"])
            self.assertFalse(receipt["release_authorized"])

    def test_both_missing_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = GATE.evaluate(
                root / "plant-origin.svg",
                root / "plant-derived-reference.webp",
                contract(svg_fixture(), webp_fixture()),
            )
            self.assertEqual(receipt["result"], "HOLD_EXACT_PLANT_DONORS_UNMOUNTED")
            self.assertFalse(receipt["donors_admitted"])

    def test_partial_mount_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture()
            cached = webp_fixture()
            origin_path = root / "plant-origin.svg"
            origin_path.write_bytes(origin)
            receipt = GATE.evaluate(origin_path, root / "plant-derived-reference.webp", contract(origin, cached))
            self.assertEqual(receipt["result"], "HOLD_EXACT_PLANT_DONORS_PARTIAL")
            self.assertFalse(receipt["donors_admitted"])

    def test_origin_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture()
            cached = webp_fixture()
            origin_path, cached_path = write_pair(root, origin + b" ", cached)
            receipt = GATE.evaluate(origin_path, cached_path, contract(origin, cached))
            self.assertEqual(receipt["result"], "FAIL_PLANT_DONOR_ADMISSION")
            self.assertTrue(any(row["name"] == "origin sha256" and not row["pass"] for row in receipt["checks"]))

    def test_cached_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture()
            cached = webp_fixture()
            origin_path, cached_path = write_pair(root, origin, cached + b" ")
            receipt = GATE.evaluate(origin_path, cached_path, contract(origin, cached))
            self.assertEqual(receipt["result"], "FAIL_PLANT_DONOR_ADMISSION")
            self.assertTrue(any(row["name"] == "cached sha256" and not row["pass"] for row in receipt["checks"]))

    def test_wrong_cached_container_fails_even_when_hash_is_rebased(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture()
            cached = b"not-webp"
            origin_path, cached_path = write_pair(root, origin, cached)
            receipt = GATE.evaluate(origin_path, cached_path, contract(origin, cached))
            self.assertEqual(receipt["result"], "FAIL_PLANT_DONOR_ADMISSION")
            self.assertTrue(any(row["name"] == "cached WebP container" and not row["pass"] for row in receipt["checks"]))

    def test_active_svg_fails_even_when_hash_is_rebased(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture(extra='<script>alert(1)</script>')
            cached = webp_fixture()
            origin_path, cached_path = write_pair(root, origin, cached)
            receipt = GATE.evaluate(origin_path, cached_path, contract(origin, cached))
            self.assertEqual(receipt["result"], "FAIL_PLANT_DONOR_ADMISSION")
            self.assertTrue(any(row["name"] == "origin SVG passive markup" and not row["pass"] for row in receipt["checks"]))

    def test_wrong_dimensions_fail_even_when_hash_is_rebased(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = svg_fixture(width=800, height=500)
            cached = webp_fixture(width=800, height=500)
            origin_path, cached_path = write_pair(root, origin, cached)
            receipt = GATE.evaluate(origin_path, cached_path, contract(origin, cached, width=1600, height=1000))
            self.assertEqual(receipt["result"], "FAIL_PLANT_DONOR_ADMISSION")
            self.assertTrue(any("dimensions" in row["name"] and not row["pass"] for row in receipt["checks"]))


if __name__ == "__main__":
    unittest.main()
