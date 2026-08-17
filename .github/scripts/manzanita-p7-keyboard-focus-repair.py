#!/usr/bin/env python3
"""Repair the P7 dynamic-control focus race exposed by the P8 matrix."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


app_path = Path("manzanita-next/experience/template/app.js")
app = app_path.read_text(encoding="utf-8")
old_focus = '''  function focusControl(kind, id) {
    requestAnimationFrame(() => {
      const selector = kind === "role" ? `[data-role="${CSS.escape(id)}"]` : `[data-${kind}="${CSS.escape(id)}"]`;
      const control = $(selector);
      if (control) control.focus();
    });
  }
'''
new_focus = '''  function focusControl(kind, id) {
    const selector = kind === "role" ? `[data-role="${CSS.escape(id)}"]` : `[data-${kind}="${CSS.escape(id)}"]`;
    const control = $(selector);
    if (control) control.focus();
  }
'''
if old_focus in app:
    app = app.replace(old_focus, new_focus, 1)
require(new_focus in app, "The synchronous focus correction did not apply")
focus_start = app.index("  function focusControl(kind, id) {")
focus_end = app.index("\n  function select(kind, id", focus_start)
require(
    "requestAnimationFrame" not in app[focus_start:focus_end],
    "The focus path still depends on animation-frame timing",
)
app_path.write_text(app, encoding="utf-8")

browser_path = Path("manzanita-next/experience/tests/browser_test.py")
browser = browser_path.read_text(encoding="utf-8")
old_browser = '''    page.locator('[data-section="overview"]').click()
    household = page.locator('[data-aperture="household"]')
    household.focus()
    household.press("ArrowRight")
    require(runtime_snapshot(page)["state"]["aperture"] == "property", "Arrow-key group navigation failed")
    require(page.locator('[data-aperture="property"]').evaluate("node => node === document.activeElement"), "Keyboard focus did not follow selection")
'''
new_browser = '''    page.locator('[data-section="overview"]').click()
    household = page.locator('[data-aperture="household"]')
    household.focus()
    household.press("ArrowRight")
    require(runtime_snapshot(page)["state"]["aperture"] == "property", "Arrow-key group navigation failed")
    require(page.locator('[data-aperture="property"]').evaluate("node => node === document.activeElement"), "Keyboard focus did not follow selection")
    page.keyboard.press("End")
    require(runtime_snapshot(page)["state"]["aperture"] == "stewardship", "End did not select the last aperture")
    require(page.locator('[data-aperture="stewardship"]').evaluate("node => node === document.activeElement"), "Focus did not follow End selection")
    page.keyboard.press("ArrowLeft")
    require(runtime_snapshot(page)["state"]["aperture"] == "region", "Consecutive ArrowLeft did not move exactly one aperture")
    require(page.locator('[data-aperture="region"]').evaluate("node => node === document.activeElement"), "Focus did not follow consecutive ArrowLeft")
    page.keyboard.press("Home")
    require(runtime_snapshot(page)["state"]["aperture"] == "plant", "Home did not select the first aperture")
    require(page.locator('[data-aperture="plant"]').evaluate("node => node === document.activeElement"), "Focus did not follow Home selection")
    page.keyboard.press("ArrowRight")
    require(runtime_snapshot(page)["state"]["aperture"] == "household", "Consecutive ArrowRight did not move exactly one aperture")
    require(page.locator('[data-aperture="household"]').evaluate("node => node === document.activeElement"), "Focus did not follow consecutive ArrowRight")
'''
if old_browser in browser:
    browser = browser.replace(old_browser, new_browser, 1)
require(new_browser in browser, "The rapid consecutive-key browser regression did not apply")
browser_path.write_text(browser, encoding="utf-8")

unit_path = Path("manzanita-next/experience/tests/test_experience.py")
unit = unit_path.read_text(encoding="utf-8")
unit_method = '''
    def test_dynamic_control_focus_is_synchronous(self) -> None:
        script = (EXPERIENCE_ROOT / "template" / "app.js").read_text(encoding="utf-8")
        start = script.index("  function focusControl(kind, id) {")
        end = script.index("\\n  function select(kind, id", start)
        focus = script[start:end]
        self.assertNotIn("requestAnimationFrame", focus)
        self.assertIn("if (control) control.focus();", focus)

'''
if "def test_dynamic_control_focus_is_synchronous" not in unit:
    anchor = '\n\nif __name__ == "__main__":\n'
    require(anchor in unit, "Cannot locate the unit-test insertion boundary")
    unit = unit.replace(anchor, "\n" + unit_method + anchor, 1)
require(
    "def test_dynamic_control_focus_is_synchronous" in unit,
    "The source-level focus regression did not apply",
)
unit_path.write_text(unit, encoding="utf-8")
