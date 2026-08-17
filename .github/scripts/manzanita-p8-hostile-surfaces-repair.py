#!/usr/bin/env python3
"""Verify hostile text through the visible source, scale, seat, and control surfaces."""

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


path = Path("manzanita-next/qualification/run_qualification.py")
text = path.read_text(encoding="utf-8")
old = '''    if mode == "hostile_text":
        require(HOSTILE_MARKER in source_text, "Hostile source text did not survive as literal text")
        page.locator('[data-section="overview"]').click()
        role_button = page.locator(f'[data-role="{data["role_order"][0]}"]')
        role_button.wait_for(state="visible")
        role_button.click()
        literal = role_button.inner_text()
        require(HOSTILE_MARKER in literal, "Hostile role label did not survive as literal text")
        require(
            HOSTILE_MARKER in page.locator("#operating-reading").inner_text(),
            "Hostile aperture reading did not survive as literal text",
        )
        require(page.locator("img[src='x']").count() == 0, "Hostile text created an image element")
        require(page.evaluate("window.__M99_XSS__") is None, "Hostile text executed script")
'''
new = '''    if mode == "hostile_text":
        require(HOSTILE_MARKER in source_text, "Hostile source text did not survive as literal text")

        page.locator('[data-section="scales"]').click()
        scale_register = page.locator("#scale-register")
        scale_register.wait_for(state="visible")
        require(
            HOSTILE_MARKER in scale_register.inner_text(),
            "Hostile aperture reading did not survive as literal text in the scale register",
        )

        page.locator('[data-section="seats"]').click()
        seat_register = page.locator("#seat-register")
        seat_register.wait_for(state="visible")
        require(
            HOSTILE_MARKER in seat_register.inner_text(),
            "Hostile role label did not survive as literal text in the seat register",
        )

        page.locator('[data-section="overview"]').click()
        role_button = page.locator(f'[data-role="{data["role_order"][0]}"]')
        role_button.wait_for(state="visible")
        role_button.click()
        require(
            HOSTILE_MARKER in role_button.inner_text(),
            "Hostile role label did not survive as literal text in the role control",
        )
        require(page.locator("img[src='x']").count() == 0, "Hostile text created an image element")
        require(page.evaluate("window.__M99_XSS__") is None, "Hostile text executed script")
'''
if old in text:
    text = text.replace(old, new, 1)
elif "Hostile aperture reading did not survive as literal text in the scale register" not in text:
    raise SystemExit("Cannot locate the hostile-text visible-surface block")
require("page.locator('[data-section=\"scales\"]').click()" in text, "Scale-register navigation did not apply")
require("page.locator('[data-section=\"seats\"]').click()" in text, "Seat-register navigation did not apply")
require("Hostile role label did not survive as literal text in the role control" in text, "Role-control literal assertion did not apply")
path.write_text(text, encoding="utf-8")
