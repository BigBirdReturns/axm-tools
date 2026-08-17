#!/usr/bin/env python3
"""Repair the bounded not-applicable reason in the P9 review records."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


old = (
    "P9 is deterministic machine governance; accessible operation of the current "
    "Manzanita successor remains controlled by P8, while the other source surfaces "
    "retain their own open accessibility gates."
)
new = (
    "This gate is not applicable to the P9 machine-readable governance register: "
    "accessible operation of the current Manzanita successor remains controlled by "
    "P8, while the other source surfaces retain their own open accessibility gates."
)

for relative in (
    "manzanita-next/parity/review/M99-RB-PKT-011.json",
    "manzanita-next/parity/review/M99-RB-DEC-011.json",
):
    path = Path(relative)
    text = path.read_text(encoding="utf-8")
    if old in text:
        text = text.replace(old, new, 1)
    require(new in text, f"Bounded not-applicable reason did not apply to {relative}")
    path.write_text(text, encoding="utf-8")

unit_path = Path("manzanita-next/parity/tests/test_parity.py")
unit = unit_path.read_text(encoding="utf-8")
method = '''
    def test_review_not_applicable_reasons_are_explicitly_bounded(self) -> None:
        for relative in (
            "review/M99-RB-PKT-011.json",
            "review/M99-RB-DEC-011.json",
        ):
            value = json.loads((PARITY_ROOT / relative).read_text(encoding="utf-8"))
            gates = value["gates"] if "gates" in value else value["gate_disposition"]
            for gate_id, row in gates.items():
                if row["state"] == "not_applicable":
                    reason = row["reason"].lower()
                    self.assertTrue(
                        "not" in reason or "no " in reason,
                        f"{relative}:{gate_id} lacks a bounded not-applicable reason",
                    )

'''
if "def test_review_not_applicable_reasons_are_explicitly_bounded" not in unit:
    anchor = '\n\nif __name__ == "__main__":\n'
    require(anchor in unit, "Cannot locate P9 review-reason test insertion boundary")
    unit = unit.replace(anchor, "\n" + method + anchor, 1)
require(
    "def test_review_not_applicable_reasons_are_explicitly_bounded" in unit,
    "P9 review-reason regression did not apply",
)
unit_path.write_text(unit, encoding="utf-8")
