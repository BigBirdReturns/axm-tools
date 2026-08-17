#!/usr/bin/env python3
"""Prevent accumulated keyboard handlers from moving a Manzanita selection twice."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


app_path = Path("manzanita-next/experience/template/app.js")
app = app_path.read_text(encoding="utf-8")
old = '''    $$('[data-control-group]').forEach((fieldset) => {
      fieldset.addEventListener("keydown", (event) => {
        if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
        const buttons = $$('button', fieldset);
        if (!buttons.length) return;
        const current = Math.max(0, buttons.indexOf(document.activeElement));
        let next = current;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (current + 1) % buttons.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (current - 1 + buttons.length) % buttons.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = buttons.length - 1;
        event.preventDefault();
        buttons[next].focus();
        buttons[next].click();
      });
    });
'''
new = '''    $$('[data-control-group]').forEach((fieldset) => {
      if (fieldset.dataset.keyboardBound === "true") return;
      fieldset.dataset.keyboardBound = "true";
      fieldset.addEventListener("keydown", (event) => {
        if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
        const buttons = $$('button', fieldset);
        if (!buttons.length) return;
        const current = Math.max(0, buttons.indexOf(document.activeElement));
        let next = current;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (current + 1) % buttons.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (current - 1 + buttons.length) % buttons.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = buttons.length - 1;
        const target = buttons[next];
        const kind = target.hasAttribute("data-aperture")
          ? "aperture"
          : target.hasAttribute("data-overlay")
            ? "overlay"
            : target.hasAttribute("data-role")
              ? "role"
              : null;
        const id = kind ? target.dataset[kind] : null;
        if (!kind || !id) return;
        event.preventDefault();
        select(kind, id);
        focusControl(kind, id);
      });
    });
'''
if old in app:
    app = app.replace(old, new, 1)
require(
    'fieldset.dataset.keyboardBound === "true"' in app,
    "Single keyboard binding guard did not apply",
)
require(
    "select(kind, id);" in app and "focusControl(kind, id);" in app,
    "Selection and post-render focus custody did not apply",
)
require(
    "buttons[next].click();" not in app,
    "The stale-node click path remains in the keyboard handler",
)
app_path.write_text(app, encoding="utf-8")

unit_path = Path("manzanita-next/experience/tests/test_experience.py")
unit = unit_path.read_text(encoding="utf-8")
method = '''    def test_keyboard_group_binding_is_single_and_focus_safe(self) -> None:
        app = (EXPERIENCE_ROOT / "template" / "app.js").read_text(encoding="utf-8")
        self.assertIn('fieldset.dataset.keyboardBound === "true"', app)
        self.assertIn('fieldset.dataset.keyboardBound = "true"', app)
        self.assertIn("select(kind, id);", app)
        self.assertIn("focusControl(kind, id);", app)
        self.assertNotIn("buttons[next].click();", app)

'''
anchor = '\n\nif __name__ == "__main__":\n'
if "test_keyboard_group_binding_is_single_and_focus_safe" not in unit:
    require(anchor in unit, "Cannot locate the experience-test class boundary")
    unit = unit.replace(anchor, "\n\n" + method + 'if __name__ == "__main__":\n', 1)
require(
    "test_keyboard_group_binding_is_single_and_focus_safe" in unit,
    "Keyboard regression test did not apply",
)
unit_path.write_text(unit, encoding="utf-8")
