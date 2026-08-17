#!/usr/bin/env python3
"""Synchronize the P8 keyboard campaign with P7's deferred focus restoration."""

from pathlib import Path

path = Path("manzanita-next/qualification/run_qualification.py")
text = path.read_text(encoding="utf-8")
old = '''    page.locator(f'[data-aperture="{first_aperture}"]').focus()
    page.keyboard.press("End")
    require(runtime_snapshot(page)["state"]["aperture"] == last_aperture, "End did not select the last aperture")
    page.keyboard.press("ArrowLeft")
    require(runtime_snapshot(page)["state"]["aperture"] == data["aperture_order"][-2], "ArrowLeft did not move one aperture")
'''
new = '''    page.locator(f'[data-aperture="{first_aperture}"]').focus()
    page.keyboard.press("End")
    require(runtime_snapshot(page)["state"]["aperture"] == last_aperture, "End did not select the last aperture")
    page.wait_for_function(
        "(id) => document.activeElement?.dataset.aperture === id",
        arg=last_aperture,
    )
    require(
        page.locator(f'[data-aperture="{last_aperture}"]').evaluate("node => node === document.activeElement"),
        "End did not transfer focus to the selected aperture",
    )
    previous_aperture = data["aperture_order"][-2]
    page.keyboard.press("ArrowLeft")
    require(runtime_snapshot(page)["state"]["aperture"] == previous_aperture, "ArrowLeft did not move one aperture")
    page.wait_for_function(
        "(id) => document.activeElement?.dataset.aperture === id",
        arg=previous_aperture,
    )
    require(
        page.locator(f'[data-aperture="{previous_aperture}"]').evaluate("node => node === document.activeElement"),
        "ArrowLeft did not transfer focus to the selected aperture",
    )
'''
if old in text:
    text = text.replace(old, new, 1)
elif "End did not transfer focus to the selected aperture" not in text:
    raise SystemExit("Cannot locate the bounded P8 keyboard campaign block")
path.write_text(text, encoding="utf-8")
