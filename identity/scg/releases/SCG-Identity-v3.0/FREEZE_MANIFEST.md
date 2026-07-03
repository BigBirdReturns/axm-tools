# SCG Identity v3.0 — FREEZE MANIFEST

**Frozen:** July 2026
**Controlling document:** `SCG_MARK_CONSTITUTION.md` (provenance law — read it first)
**State:** identity settled. Remaining work is packaging discipline, not design.

---

## Canonical stack

- **AXM-WORLD** — the runtime and original world context.
- **RODOH** — the runtime identity system and cartridge-shell discipline.
- **The chunky pixel dandelion** — the canonical glyph.
- **SCG v3** — the buyer-facing practice identity using that glyph.
- **AXM House Style v1.2** — editorial law for analytical publishing.
- **SCG export set** — applications, NOT source truth.

## The mark, settled

| | Grid | Palette | Source |
|---|---|---|---|
| **ROOT GLYPH** — AXM-WORLD runtime | 16 × 16 | cream `#fffdf5` / moss `#6B784D` / charcoal `#1B1818` | `axm-world/js/sprites.jsx` `SPRITES.dandelion` |
| **PRACTICE DERIVATIVE** — SCG public | 16 × 18 | bone `#ECE7D8` / olive `#7C7F57` / void `#0D0C09` | `scg-identity/scg-pixel-mark.js` `SCGPX.MAP` |

Ember `#C24B2C` = findings/flags only, **never in the mark**. SCG stewards the derivative; it does not own the origin.

## Contents of this freeze

1. `AXM-WORLD-COMPLETE.standalone.html` — runtime standalone (root glyph live in the splash + header; embeds the Program of Record cartridge). Offline.
2. `SCG Identity System v3 (standalone).html` — practice identity, reconciled text. Offline.
3. `AXM House Style v1.2 (standalone).html` — editorial law. Offline.
4. `exports/` — SCG application set: dark avatar (default), on-bone mark, favicon ramp 32–256, desktop + mobile-safe covers, README.
5. `SCG_MARK_CONSTITUTION.md` — custody law. First-class artifact, not notes.
6. `FREEZE_MANIFEST.md` — this file.

## Export targets (applications)

- LinkedIn avatar → `exports/SCG-avatar-800.png` (dark, default).
- LinkedIn cover → `exports/SCG-linkedin-cover-mobile-safe-2256x382.png` (mobile-safe) or `-desktop-`.
- Favicon → `exports/SCG-favicon-{32,48,64,128,256}.png`.
- Print / light document header → `exports/SCG-mark-on-bone-800.png`.

## Reconciliations applied in this freeze (string-only)

- `SCG Identity System v3.html` footer: `MARK ORIGIN SCG · LICENSED TO AXM-WORLD RUNTIME` → **`ROOT GLYPH AXM-WORLD · SCG PRACTICE DERIVATIVE`**.
- `scg-pixel-mark.js` header (both `scg-identity/` and `axm-tools-repo/`): origin claim replaced with the root/derivative lineage + pointer to the constitution.

No map, palette, or export changes. Language aligned to law.

## Rejected — do NOT resurrect

**The sterile vector dandelion** (`SCG Mature Identity.html` → `buildDandelionSVG()`): smooth concentric-circle rings, ink/paper/**rust**, Archivo. Formally **deprecated** by the constitution §7 — provenance breakage, no coordinate map, rust-in-mark. It is rejected, **not archived as an alternate direction**. Any child of it is out of custody.

---

*Freeze `SCG Identity v3.0`. Deploy LinkedIn against this record, not against whichever asset looked best this week.*
