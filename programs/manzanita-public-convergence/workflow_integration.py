#!/usr/bin/env python3
"""Bind the rendered visual floor to static and live release workflows."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def install_dependency(text: str) -> str:
    text = text.replace(
        "python -m pip install --disable-pip-version-check playwright==1.57.0",
        "python -m pip install --disable-pip-version-check Pillow==11.3.0 playwright==1.57.0",
    )
    return text


def add_path(text: str) -> str:
    marker = '      - "manzanita/**"'
    addition = marker + '\n      - "programs/manzanita-public-convergence/**"'
    if marker in text and 'programs/manzanita-public-convergence/**' not in text:
        text = text.replace(marker, addition, 1)
    return text


def static_workflow() -> None:
    path = REPO / ".github/workflows/manzanita-check.yml"
    text = install_dependency(add_path(path.read_text(encoding="utf-8")))
    marker = "      - name: Drive light, dark, desktop, and mobile contracts\n        run: python manzanita/tests/browser_test.py"
    addition = marker + "\n      - name: Enforce rendered photographic composition and aperture distinction\n        run: python programs/manzanita-public-convergence/rendered_visual_floor.py --output ${{ runner.temp }}/manzanita-rendered-visual-floor"
    if marker not in text:
        raise SystemExit("Could not locate the permanent browser-contract step")
    if "rendered_visual_floor.py" not in text:
        text = text.replace(marker, addition, 1)
    path.write_text(text, encoding="utf-8")


def live_workflow() -> None:
    path = REPO / ".github/workflows/manzanita-live-check.yml"
    text = install_dependency(path.read_text(encoding="utf-8"))
    marker = "        run: python manzanita/tests/browser_test.py"
    addition = marker + "\n      - name: Enforce rendered photographic composition against the deployed endpoint\n        run: python programs/manzanita-public-convergence/rendered_visual_floor.py --output ${{ runner.temp }}/manzanita-live-visual-floor"
    if marker not in text:
        raise SystemExit("Could not locate the live browser-contract step")
    if "rendered_visual_floor.py" not in text:
        text = text.replace(marker, addition, 1)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    static_workflow()
    live_workflow()
    print("Permanent static and live rendered visual gates: INSTALLED")
