#!/usr/bin/env python3
"""Keep print and theme controls operable across compact Manzanita layouts."""

from __future__ import annotations

from pathlib import Path

STYLE = Path("manzanita/style.css")
MARKER = "/* Manzanita compact utility controls v1.6.0 */"

css = STYLE.read_text(encoding="utf-8")
if MARKER not in css:
    css += r'''

/* Manzanita compact utility controls v1.6.0 */
@media (max-width: 720px) {
  .topbar {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) auto !important;
    align-items: center !important;
    gap: 0.65rem !important;
  }

  .topbar nav {
    grid-column: 1 / -1 !important;
    order: 3 !important;
    min-width: 0 !important;
  }

  .header-actions {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: static !important;
    grid-column: 1 / -1 !important;
    order: 4 !important;
    width: 100% !important;
    min-width: 0 !important;
    gap: 0.5rem !important;
  }

  .header-actions .quiet-button {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: static !important;
    flex: 1 1 0 !important;
    min-width: 0 !important;
    min-height: 44px !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: normal !important;
    text-align: center !important;
  }
}

@media (max-width: 360px) {
  .header-actions {
    flex-direction: column !important;
  }

  .header-actions .quiet-button {
    width: 100% !important;
  }
}
'''
    STYLE.write_text(css, encoding="utf-8")

print("Compact print and theme control repair: APPLIED")
