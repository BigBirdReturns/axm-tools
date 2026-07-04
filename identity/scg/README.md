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
**maps + law → `source/` · frozen bundles → `releases/` · platform files → `exports/` · deployed copies (full axm.tools site, when deployed) → `/public/assets/scg/` · rejected work → warning only.**

## Deployment scope
The path references across this tree — `/public/assets/scg/`, a root-level
`scg-pixel-mark.js`, and the `axm-world/` / `scg-identity/` siblings named in
the constitution and export manifest — describe the full **axm.tools**
monorepo, where the mark ships as a generated deploy copy. This standalone
**axm-tools** repo (the leaner PTA-tracker toolbox) does **not** carry that
layout: there is no `/public/` path and no root-level copy of the mark. Here,
surfaces reference the canonical source directly — see the identity showcase
(`../index.html`), which renders the mark straight from
`source/scg-pixel-mark.js`. When the identity is deployed on the full site,
any root-level / `/public/assets/scg/` copy is generated from the `source/`
file here; that file stays the source of truth either way.
