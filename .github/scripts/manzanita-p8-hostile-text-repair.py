#!/usr/bin/env python3
"""Keep the hostile-text campaign on a visible, operator-reachable surface."""

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


path = Path("manzanita-next/qualification/run_qualification.py")
text = path.read_text(encoding="utf-8")
old = '''    if mode == "hostile_text":
        page.locator(f'[data-role="{data["role_order"][0]}"]').click()
        literal = page.locator(f'[data-role="{data["role_order"][0]}"]').inner_text()
        require(HOSTILE_MARKER in literal, "Hostile role label did not survive as literal text")
        require(page.locator("img[src='x']").count() == 0, "Hostile text created an image element")
        require(page.evaluate("window.__M99_XSS__") is None, "Hostile text executed script")
'''
new = '''    if mode == "hostile_text":
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
if old in text:
    text = text.replace(old, new, 1)
elif "Hostile aperture reading did not survive as literal text" not in text:
    raise SystemExit("Cannot locate the hostile-text campaign interaction block")
require("page.locator('[data-section=\"overview\"]').click()" in text, "Visible overview navigation did not apply")
require("role_button.wait_for(state=\"visible\")" in text, "Visible role-control gate did not apply")
require("Hostile source text did not survive as literal text" in text, "Hostile source literal assertion did not apply")
path.write_text(text, encoding="utf-8")
