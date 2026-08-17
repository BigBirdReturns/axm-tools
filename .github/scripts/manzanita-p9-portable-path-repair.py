#!/usr/bin/env python3
"""Repair relative-path normalization in the P9 parity builder."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


builder_path = Path("manzanita-next/parity/build_parity.py")
builder = builder_path.read_text(encoding="utf-8")
replacements = {
    'source_path = (inventory_path.parent / str(relative)).resolve()':
        'source_path = (paths["inventory"].parent / str(relative)).resolve()',
    '"source_inventory": inventory_path.relative_to(repo_root).as_posix(),':
        '"source_inventory": paths["inventory"].relative_to(repo_root).as_posix(),',
    '"source_inventory_sha256": sha256_file(inventory_path),':
        '"source_inventory_sha256": sha256_file(paths["inventory"]),',
    '"surface_schema": surface_schema_path.relative_to(repo_root).as_posix(),':
        '"surface_schema": paths["surface_schema"].relative_to(repo_root).as_posix(),',
    '"surface_schema_sha256": sha256_file(surface_schema_path),':
        '"surface_schema_sha256": sha256_file(paths["surface_schema"]),',
}
for old, new in replacements.items():
    if old in builder:
        builder = builder.replace(old, new, 1)
    require(new in builder, f"P9 portable-path correction did not apply: {new}")
builder_path.write_text(builder, encoding="utf-8")

unit_path = Path("manzanita-next/parity/tests/test_parity.py")
unit = unit_path.read_text(encoding="utf-8")
if "import os\n" not in unit:
    unit = unit.replace("import json\n", "import json\nimport os\n", 1)
method = '''
    def test_relative_paths_are_normalized_against_the_repository_root(self) -> None:
        original = Path.cwd()
        try:
            os.chdir(self.repo)
            receipt = builder.build(
                Path("."),
                Path("manzanita-next/parity/PARITY_CONTRACT.json"),
                Path("manzanita-next/parity/SURFACE_DISPOSITIONS.json"),
                Path("resolution-backfill/inventory.json"),
                Path("resolution-backfill/contracts/surface.schema.json"),
                Path("resolution-backfill/out/report.json"),
                Path("resolution-backfill/out/qualification.json"),
                Path("manzanita-next/experience/out/BUILD_RECEIPT.json"),
                Path("manzanita-next/qualification/out/QUALIFICATION_REPORT.json"),
                Path("manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json"),
                Path("manzanita-next/parity/out-relative"),
            )
        finally:
            os.chdir(original)
        self.assertEqual(receipt["result"], "PASS")
        register = json.loads(
            (self.parity / "out-relative/PARITY_REGISTER.json").read_text(encoding="utf-8")
        )
        self.assertEqual(register["source_inventory"], "resolution-backfill/inventory.json")
        self.assertEqual(
            register["surface_schema"],
            "resolution-backfill/contracts/surface.schema.json",
        )

'''
if "def test_relative_paths_are_normalized_against_the_repository_root" not in unit:
    anchor = '\n\nif __name__ == "__main__":\n'
    require(anchor in unit, "Cannot locate P9 unit-test insertion boundary")
    unit = unit.replace(anchor, "\n" + method + anchor, 1)
require(
    "def test_relative_paths_are_normalized_against_the_repository_root" in unit,
    "P9 relative-path regression did not apply",
)
unit_path.write_text(unit, encoding="utf-8")
