#!/usr/bin/env python3
"""Repair long-label overflow exposed by the true 200 percent text-resize campaign."""

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


path = Path("manzanita-next/experience/template/style.css")
text = path.read_text(encoding="utf-8")

base_anchor = '''.section-nav button { flex: 0 0 auto; padding: .75rem .9rem; border: 0; border-right: 1px solid var(--line); background: transparent; color: inherit; }
'''
base_replacement = '''.section-nav button { flex: 0 0 auto; min-width: 0; max-width: 100%; padding: .75rem .9rem; border: 0; border-right: 1px solid var(--line); background: transparent; color: inherit; white-space: normal; overflow-wrap: anywhere; }
'''
if base_anchor in text:
    text = text.replace(base_anchor, base_replacement, 1)
require(
    ".section-nav button { flex: 0 0 auto; min-width: 0; max-width: 100%;" in text,
    "Section-navigation label wrapping did not apply",
)

segmented_anchor = '''.segmented-controls button { min-width: 0; padding: .55rem .4rem; border: 0; border-right: 1px solid var(--line); background: transparent; color: inherit; font-size: .8rem; line-height: 1.1; }
'''
segmented_replacement = '''.segmented-controls button { min-width: 0; max-width: 100%; padding: .55rem .4rem; border: 0; border-right: 1px solid var(--line); background: transparent; color: inherit; font-size: .8rem; line-height: 1.1; white-space: normal; overflow-wrap: anywhere; word-break: normal; }
'''
if segmented_anchor in text:
    text = text.replace(segmented_anchor, segmented_replacement, 1)
require(
    ".segmented-controls button { min-width: 0; max-width: 100%;" in text,
    "Segmented-control label wrapping did not apply",
)

container_anchor = '''  .theme-control button,
  .utility-button { overflow-wrap: anywhere; }
'''
container_replacement = '''  .theme-control button,
  .utility-button { overflow-wrap: anywhere; }
  .section-nav {
    flex-wrap: wrap;
    overflow-x: visible;
  }
  .section-nav button {
    flex: 1 1 12rem;
  }
  .segmented-controls,
  .overlay-controls {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .segmented-controls button:nth-child(2n) {
    border-right: 0;
  }
  .segmented-controls button:nth-child(n+3) {
    border-top: 1px solid var(--line);
  }
  .control-deck,
  .control-group,
  .section-panel {
    min-width: 0;
    max-width: 100%;
  }
'''
if container_anchor in text:
    text = text.replace(container_anchor, container_replacement, 1)
require(".section-nav button {\n    flex: 1 1 12rem;" in text, "Container-level section navigation recomposition did not apply")
require("grid-template-columns: repeat(2, minmax(0, 1fr));" in text, "Container-level segmented-control recomposition did not apply")

path.write_text(text, encoding="utf-8")
