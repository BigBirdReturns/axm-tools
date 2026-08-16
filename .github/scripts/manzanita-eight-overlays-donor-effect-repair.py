#!/usr/bin/env python3
"""Align overlay donor-effect validation with admitted donor receipt schemas."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


builder_path = Path("manzanita-next/overlays/build_overlays.py")
builder = builder_path.read_text(encoding="utf-8")
old = '''    for row in (contract["object"], public_build, aperture_build, scene, registration):
        require(row.get("public_effect") == "none", "A consumed donor carries a public effect")
        require(row.get("constitutional_count_effect") == "none", "A consumed donor carries a constitutional count effect")
'''
new = '''    for row in (contract["object"], public_build, aperture_build, scene, registration):
        public_effect = row.get("public_effect")
        if public_effect is None:
            public_effect = row.get("release_effect")
        require(public_effect == "none", "A consumed donor carries a public effect")
        require(row.get("constitutional_count_effect") == "none", "A consumed donor carries a constitutional count effect")
'''
if old in builder:
    builder = builder.replace(old, new, 1)
require(
    'public_effect = row.get("public_effect")' in builder
    and 'public_effect = row.get("release_effect")' in builder,
    "The donor-effect compatibility correction did not apply",
)
builder_path.write_text(builder, encoding="utf-8")

unit_path = Path("manzanita-next/overlays/tests/test_overlays.py")
unit = unit_path.read_text(encoding="utf-8")
anchor = '''    def test_build_is_deterministic_for_same_inputs(self) -> None:
'''
addition = '''    def test_public_demo_release_effect_field_is_admitted(self) -> None:
        receipt_path = self.public_demo / "BUILD_RECEIPT.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("public_effect")
        receipt["release_effect"] = "none"
        write_json(receipt_path, receipt)
        result = self.build()
        self.assertEqual(result["result"], "PASS")

    def test_non_none_public_demo_release_effect_is_rejected(self) -> None:
        receipt_path = self.public_demo / "BUILD_RECEIPT.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("public_effect")
        receipt["release_effect"] = "public"
        write_json(receipt_path, receipt)
        with self.assertRaisesRegex(builder.OverlayError, "public effect"):
            self.build()

'''
if "test_public_demo_release_effect_field_is_admitted" not in unit:
    require(anchor in unit, "Cannot locate deterministic test anchor")
    unit = unit.replace(anchor, addition + anchor, 1)
require(
    "test_non_none_public_demo_release_effect_is_rejected" in unit,
    "Donor-effect regression tests did not apply",
)
unit_path.write_text(unit, encoding="utf-8")
