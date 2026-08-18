#!/usr/bin/env python3
"""Keep compact controls operable without creating horizontal overflow."""

from __future__ import annotations

from pathlib import Path

STYLE = Path("manzanita/style.css")
MARKER = "/* Manzanita compact utility controls v1.6.0 */"

css = STYLE.read_text(encoding="utf-8")
if MARKER not in css:
    css += r'''

/* Manzanita compact utility controls v1.6.0 */
@media (max-width: 720px) {
  html,
  body {
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: clip !important;
  }

  body > *,
  main,
  section,
  header,
  nav,
  article,
  aside,
  figure,
  .topbar,
  .hero,
  .fabric,
  .workbench,
  .instrument-grid,
  .estate-grid,
  .firewall-grid,
  .handoff,
  .origin-band,
  .portable-row {
    min-width: 0 !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }

  img,
  svg {
    max-width: 100% !important;
  }

  .topbar {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) !important;
    align-items: stretch !important;
    gap: 0.65rem !important;
  }

  .brand,
  .topbar nav,
  .header-actions {
    grid-column: 1 !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
  }

  .brand {
    order: 1 !important;
    overflow-wrap: anywhere !important;
  }

  .topbar nav {
    order: 2 !important;
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 0.35rem !important;
  }

  .topbar nav a {
    min-width: 0 !important;
    max-width: 100% !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
    text-align: center !important;
  }

  .header-actions {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: static !important;
    order: 3 !important;
    gap: 0.5rem !important;
  }

  .header-actions .quiet-button,
  .hero-actions a,
  .aperture-rail button,
  .chip-row button,
  .portable-row button {
    min-width: 0 !important;
    max-width: 100% !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
  }

  .header-actions .quiet-button {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: static !important;
    width: 100% !important;
    min-height: 44px !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
  }

  .hero-actions,
  .aperture-rail,
  .chip-row,
  .portable-row {
    min-width: 0 !important;
    max-width: 100% !important;
    flex-wrap: wrap !important;
  }

  .scene,
  .scene-card,
  .reading-card,
  .control-card {
    min-width: 0 !important;
    max-width: 100% !important;
    overflow: hidden !important;
  }
}

@media (max-width: 420px) {
  .topbar nav,
  .header-actions {
    grid-template-columns: minmax(0, 1fr) !important;
  }

  .hero-actions,
  .portable-row {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) !important;
  }

  .hero-actions a,
  .portable-row button {
    width: 100% !important;
  }
}
'''
    STYLE.write_text(css, encoding="utf-8")

print("Compact controls and horizontal-overflow repair: APPLIED")
