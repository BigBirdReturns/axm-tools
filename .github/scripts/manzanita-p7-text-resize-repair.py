#!/usr/bin/env python3
"""Repair P7 text-resize recomposition and own the 200% regression at source."""

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


css_path = Path("manzanita-next/experience/template/style.css")
css = css_path.read_text(encoding="utf-8")
main_old = ".main-field { min-width: 0; padding: clamp(1rem, 2.5vw, 2.75rem); }"
main_new = ".main-field { min-width: 0; padding: clamp(1rem, 2.5vw, 2.75rem); container-type: inline-size; container-name: main-field; }"
if main_old in css:
    css = css.replace(main_old, main_new, 1)
require("container-name: main-field" in css, "Main-field container law did not apply")

query = '''
@container main-field (max-width: 720px) {
  .masthead { display: block; }
  .masthead-actions {
    width: 100%;
    margin-top: 1rem;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
  .theme-control,
  .theme-control button,
  .utility-button { min-width: 0; }
  .theme-control button,
  .utility-button { overflow-wrap: anywhere; }
  .stage-head,
  .operating-head,
  .section-heading-inline { flex-wrap: wrap; }
  .experience-grid { grid-template-columns: minmax(0, 1fr); }
  .operating-panel { display: block; }
  .operating-head { border-right: 0; }
  .overview-ledgers,
  .detail-grid,
  .fab-record,
  .help-grid { grid-template-columns: minmax(0, 1fr); }
  .register-row,
  .source-row,
  .ledger-row,
  .detail-list { grid-template-columns: minmax(0, 1fr); }
  .register-row > :nth-child(3),
  .register-row > :nth-child(4) { grid-column: auto; }
  .detail-list div { display: block; }
  .detail-list dd { margin-bottom: .8rem; }
}
'''
if "@container main-field (max-width: 720px)" not in css:
    anchor = "\n@media (prefers-reduced-motion: reduce) {"
    require(anchor in css, "Cannot locate the reduced-motion boundary for container insertion")
    css = css.replace(anchor, "\n" + query + anchor, 1)
css_path.write_text(css, encoding="utf-8")

browser_path = Path("manzanita-next/experience/tests/browser_test.py")
browser = browser_path.read_text(encoding="utf-8")
old = '''    zoom_context = browser.new_context(viewport={"width": 640, "height": 900}, color_scheme="light")
    zoom = zoom_context.new_page()
    zoom.goto(base_url, wait_until="networkidle")
    zoom.evaluate("document.documentElement.style.zoom = '2'")
    zoom.wait_for_timeout(100)
    zoom_overflow = horizontal_overflow(zoom)
    require(zoom_overflow <= 2, "The 200 percent zoom campaign introduced horizontal overflow")
    require(zoom.locator("#operating-action").is_visible(), "Next safe action disappeared at 200 percent zoom")
    zoom_context.close()
'''
new = '''    zoom_context = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="light")
    zoom = zoom_context.new_page()
    zoom.goto(base_url, wait_until="networkidle")
    zoom.evaluate("document.documentElement.style.fontSize = '200%'")
    zoom.wait_for_timeout(100)
    zoom_overflow = horizontal_overflow(zoom)
    require(zoom_overflow <= 2, "The 200 percent text-resize campaign introduced horizontal overflow")
    require(zoom.locator("#operating-action").is_visible(), "Next safe action disappeared at 200 percent text resize")
    require(zoom.locator("#export-button").is_visible(), "Export control disappeared at 200 percent text resize")
    zoom_context.close()
'''
if old in browser:
    browser = browser.replace(old, new, 1)
require("document.documentElement.style.fontSize = '200%'" in browser, "True 200 percent text-resize campaign did not apply")
require("Export control disappeared at 200 percent text resize" in browser, "Text-resize utility-control regression did not apply")
browser_path.write_text(browser, encoding="utf-8")
