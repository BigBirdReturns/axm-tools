# SCG Identity v3.1 — FREEZE MANIFEST

**Frozen:** July 2026
**Supersedes:** v3.0 (for deployment reference)
**Controlling document:** `SCG_MARK_CONSTITUTION.md` (provenance law — unchanged from v3.0)
**Scope:** **application-layer revision only.** Mark, coordinate map, palette, type, and the constitution are **identical to v3.0.** No design changed. This release exists so a frozen record matches what is actually deployed.

---

## What changed from v3.0 → v3.1

**One decision: the avatar carries the mark, so the LinkedIn cover does not.**

v3.0's covers repeated the dandelion beside an avatar that already shows it — two marks reading at once on the profile. v3.1 makes the **wordmark-only cover** the primary LinkedIn cover: name + tagline on the void field, the dandelion left to the avatar. This is a packaging/application choice permitted without a constitution bump — the mark itself is untouched.

- **New primary cover:** `exports/SCG-linkedin-cover-wordmark-2256x382.png` — SANDHU CONSULTING GROUP (Plex Sans 600) + tagline (Plex Mono, olive) on void. No mark.
- **Demoted to secondary / non-LinkedIn banners:** `-desktop-` and `-mobile-safe-` (both carry the mark; valid for banner surfaces that are *not* shown next to the avatar).

Nothing else in the bundle differs from v3.0.

---

## Canonical stack (unchanged)

- **AXM-WORLD** — runtime and original world context.
- **RODOH** — runtime identity system and cartridge-shell discipline.
- **The chunky pixel dandelion** — the canonical glyph.
- **SCG v3** — buyer-facing practice identity using that glyph.
- **AXM House Style v1.2** — editorial law for analytical publishing.
- **SCG export set** — applications, NOT source truth.

## The mark, settled (unchanged from v3.0)

| | Grid | Palette | Source |
|---|---|---|---|
| **ROOT GLYPH** — AXM-WORLD runtime | 16 × 16 | cream `#fffdf5` / moss `#6B784D` / charcoal `#1B1818` | `axm-world/js/sprites.jsx` `SPRITES.dandelion` |
| **PRACTICE DERIVATIVE** — SCG public | 16 × 18 | bone `#ECE7D8` / olive `#7C7F57` / void `#0D0C09` | `source/scg-pixel-mark.js` `SCGPX.MAP` |

Ember `#C24B2C` = findings/flags only, **never in the mark**. SCG stewards the derivative; it does not own the origin.

## Contents of this freeze

1. `AXM-WORLD-COMPLETE.standalone.html` — runtime standalone (root glyph live). Offline. *(identical to v3.0)*
2. `SCG Identity System v3 (standalone).html` — practice identity. Offline. *(identical to v3.0)*
3. `AXM House Style v1.2 (standalone).html` — editorial law. Offline. *(identical to v3.0)*
4. `exports/` — SCG application set: dark avatar (default), on-bone mark, favicon ramp 32–256, **wordmark cover (primary LinkedIn)**, desktop + mobile-safe covers (secondary banners), README.
5. `SCG_MARK_CONSTITUTION.md` — custody law. *(identical to v3.0)*
6. `FREEZE_MANIFEST.md` — this file.

## Export targets (applications)

- LinkedIn avatar → `exports/SCG-avatar-800.png` (dark, default).
- **LinkedIn cover → `exports/SCG-linkedin-cover-wordmark-2256x382.png` (primary — no mark, avatar carries it).**
- Non-LinkedIn banner (mark + type) → `exports/SCG-linkedin-cover-desktop-2256x382.png` or `-mobile-safe-`.
- Favicon → `exports/SCG-favicon-{32,48,64,128,256}.png`.
- Print / light document header → `exports/SCG-mark-on-bone-800.png`.

## Rejected — do NOT resurrect

**The sterile vector dandelion** (`SCG Mature Identity.html` → `buildDandelionSVG()`): smooth concentric-circle rings, ink/paper/**rust**, Archivo. Formally **deprecated** by the constitution §7 — provenance breakage, no coordinate map, rust-in-mark. Rejected, **not archived as an alternate direction**.

---

*v3.1 = the profile's cover decision, frozen. The mark and its law did not move; only the application caught up. v3.0 remains the ratified record of the freeze that preceded this cover choice.*
