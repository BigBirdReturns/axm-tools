# AXM property flavors — the per-page identity registry

*So nobody has to hold it in their head.* Each AXM GitHub Pages property is
allowed **its own flavor** — it does **not** inherit the full house style. This
file records which flavor each property uses, so a future page (or a future
model) reads the map here instead of guessing or cloning whatever page it saw
last.

## What is and isn't frozen

- **Frozen (do not drift):** the SCG mark (`../scg/SCG_MARK_CONSTITUTION.md`) and
  its **four-token palette** — bone `#ECE7D8`, olive `#7C7F57`, void `#0D0C09`,
  ember `#C24B2C` (ember = *findings / flags ONLY*). Type: Barlow Condensed
  (display) + IBM Plex Mono (evidence) + IBM Plex Sans (running text).
- **The two families** (house style, `house-style/`): **Cream Editorial** (paper
  light) and **Dark Ecosystem** (warm-black). Editorial law, not per-page law.
- **NOT frozen — this file:** the *application* choices below. A property picks a
  flavor within/adjacent to the palette and families. Flavors may be added or
  retuned; that is a normal edit here, never a mark or palette change.

## The rule of thumb

- A property's flavor should read as **itself**, recognizably in the family, not
  as a clone of another property.
- **Ember is reserved-meaning.** Use it as a *signature* only where the property
  is genuinely about findings / flags / tension. Don't spend ember for decoration.
- Cyan/steel is **not** a frozen token; it is the ecosystem's "cold runtime
  instrument" convention. Fine for runtime/technical surfaces; it is a
  *convention*, not law.

## The registry

| Property | Page(s) | Family | Background | Signature accent | Rationale |
|---|---|---|---|---|---|
| **GhostBox** | `bigbirdreturns.github.io/GhostBox/` | Dark Ecosystem | void `#0D0C09` | **ember `#C24B2C`** | The intelligence / tension / findings spoke — ember is *earned* (it is the findings token). Warm, editorial-evidence feel. |
| **axm-core** | `…/axm-core/` | Dark (runtime) | `#0d1117` | cyan/steel `#39d0d8` | The hub / query runtime — cold instrument convention. |
| **axm-console** | `…/axm-console/` | Dark (runtime) | `#0d1117` | cyan/steel | Operator cockpit; currently the runtime convention. *Flavor may be given its own accent later — TBD.* |
| **axm-aide** | `…/axm-aide/` | Dark (runtime) | `#0d1117` | cyan/steel | Personal spoke; currently the runtime convention. *Flavor TBD.* |
| exit-demo / ship (on GhostBox) | `…/GhostBox/exit-demo.html`, `ship.html` | instruments | dark | cyan = *sealed/sovereign* | Technical instruments hosted under GhostBox's frame; here cyan is a **functional signal** (the sovereign/sealed record color), not a brand choice. |

*(Rows marked TBD are honest: they currently ride the runtime convention and have
not been given a deliberate flavor. Recording that is the point — an unassigned
flavor is a known gap, not a mystery.)*

## When you add or move a property

1. Pick its flavor here **before** styling the page, and add a row.
2. If it's a findings/tension surface, ember is available as a signature;
   otherwise leave ember to its reserved meaning.
3. Keep the type stack (Barlow Condensed + IBM Plex) — that is the family thread
   every property shares even when colors differ.

This registry is the source of truth for *page flavor*. It is **not** the source
for *cross-repo wiring* (where a package lives, which env var points where) —
that belongs with the ecosystem map, not the identity system.
