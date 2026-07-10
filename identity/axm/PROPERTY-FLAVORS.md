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
| **axm-console** | `…/axm-console/` | Dark Ecosystem | `#0d0c09` | **teal/pine `#1c8175`** | The operator cockpit / command seat — a grounded, cool instrument distinct from core's brighter runtime cyan. |
| **axm-aide** | `…/axm-aide/` | Dark Ecosystem | void `#0D0C09` | **gold `#c8a24a`** | The personal spoke — custody of your memory. Warm gold reads personal/valuable, distinct from ember/teal/cyan. |
| **EarCrate** | local-first app UI (`bigbirdreturns/earcrate`, served on loopback) + its Pages installer | **Dark Ecosystem** (default) + Cream Editorial toggle | void `#0d0c09` / paper `#f0ebe0` | **pitch-LED amber `#e6a23c`** (deepened `#9a6a17` on paper) | The station / deck instrument — the amber is the Technics pitch-fader light the app was born with. Ember keeps reserved meaning: refusals, gate failures, thin rails. Like the acceptance page, **zero webfont loads** (local-first law): house faces named in the stack, system equivalents otherwise. |
| exit-demo / ship (on GhostBox) | `…/GhostBox/exit-demo.html`, `ship.html` | instruments | dark | cyan = *sealed/sovereign* | Technical instruments hosted under GhostBox's frame; here cyan is a **functional signal** (the sovereign/sealed record color), not a brand choice. |
| surface acceptance (on axm-tools) | `…/axm-tools/acceptance.html` | **Cream Editorial** (default) + void toggle | paper `#faf9f5` / void `#0D0C09` | status triad: ember (blocked) · gold (gap) · green (supportable) | The buyer-facing handout — a *document*, not an instrument. Paper-light letterhead reads as a finding memo across a desk; ember keeps its reserved meaning (it marks the blocking findings). First Cream Editorial property in production. **Deliberate exception:** no webfont load — the page makes *zero* network requests so it can be handed into an offline/CUI-adjacent room; the house faces are named in the CSS stack and render if installed, system equivalents otherwise. |

*(Every property above now has a deliberate flavor. The type stack — Barlow
Condensed + IBM Plex — is the family thread they all share; the accent is what
makes each itself.)*

## When you add or move a property

1. Pick its flavor here **before** styling the page, and add a row.
2. If it's a findings/tension surface, ember is available as a signature;
   otherwise leave ember to its reserved meaning.
3. Keep the type stack (Barlow Condensed + IBM Plex) — that is the family thread
   every property shares even when colors differ.

This registry is the source of truth for *page flavor*. It is **not** the source
for *cross-repo wiring* (where a package lives, which env var points where) —
that belongs with the ecosystem map, not the identity system.
