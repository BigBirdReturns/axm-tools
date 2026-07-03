# SCG identity — source & releases

Governed by **`SCG_MARK_CONSTITUTION.md`** (custody law — read it first).

## Layout
- **`source/`** — THE source of truth: the derivative mark (`scg-pixel-mark.js`), tokens (`scg.tokens.css`), lockups (`scg-lockups.html`), and the export manifest (`scg-export-manifest.json`).
- **`releases/`** — frozen, auditable identity bundles (e.g. `SCG-Identity-v3.0/`). **Never edit after freeze.** A change = a new `vX` folder.
- **`deprecated/`** — rejected variants, kept only as a warning. No reusable assets stored here.

## Lineage (constitution §1)
- **Root glyph** — AXM-WORLD runtime dandelion, **16×16 cream/moss**, lives in `axm-world/js/sprites.jsx`. Referenced here, **not owned** here.
- **Practice derivative** — SCG, **16×18 bone/olive**, `source/scg-pixel-mark.js`. SCG stewards it.

## The rule
**maps + law → `source/` · frozen bundles → `releases/` · platform files → `exports/` · deployed copies → `/public/assets/scg/` · rejected work → warning only.**

The live site (`../../index.html`) keeps its own root-level copy of `scg-pixel-mark.js` for deployment; the canonical source is the one here.
