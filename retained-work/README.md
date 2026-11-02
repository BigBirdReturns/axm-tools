# Retained Work and Suginami Field Desk 2.0

Open `review/` for the working product. Open the directory's `index.html` for the full bilingual project explanation, finite-model and operational evidence, conceptual overlaps and proposed engagement. `map/` preserves the original supplied compiled map as an alternative view. The native Suginami 1.1 application remains a separate private runtime; Field Desk 2.0 is the public browser-local product, not a new native release.

## Product structure

Field Desk has one application shell and seven views: Overview, Atlas, Research, Action plan, Costs & delivery, History & recovery, and Library & access. Global search, available through Ctrl/Command K, finds original claims, actions, place records and documents in both languages. Claims, actions and selected places have explicit routes. The atlas is a native SVG component, not an iframe containing another application's navigation.

The redesigned map uses the exact geographic object extracted from the supplied data module. It retains all nine layers, 656 geometric features, 45 claims, 15 authored relationships and ten action/dependency records. Source fields and original object identities remain inspectable. Business shading represents supplied establishment counts per neighborhood; it does not invent area-normalized density. The rail layer contains 14 station points and four approximate lines. Source attribution and limitations are visible in the feature inspector. Collision-aware labels, layer presets, feature search, keyboard pan/zoom, fit controls and a searchable/paginated place list provide alternate access.

Research separates author grades, local source attachments and subsequent reviews. Source quotation matching is an exact local test, while a separate attributed review records scope and interpretation. In-session source drafts, including metadata-only drafts, follow their claim across navigation. Saved records continue to use the existing journal. Action cards expose original instructions, proposed dates, prerequisites, successors, linked claims and attributed comments. Progress reports do not become artifact acceptance automatically.

Costs include all six existing categories and preserve negative results. Delivery stages stay distinct. History provides a readable timeline plus the exact event record, plain export/import and encrypted browser backup. Library provides categorized access to fourteen actual public tools, guides, evidence descriptions and named external-input boundaries. Public Markdown guides open in a formatted reader with bilingual section navigation and original downloads.

## Assets, data and custody

`assets/suginami-atlas.svg` is drawn from the supplied polygons and station/rail geometry. `assets/field-mark.svg` and `review/icons.js` are original UI symbols, not substitutes for the AXM/SCG identity. System fonts are used; no font file is distributed. No external photographs, imagery service, tile server, geocoder, model, API key, analytics or billing dependency is introduced. `assets/ASSETS.json` and `data/geography-provenance.json` retain the exact source identities and projection boundary.

The original `map/assets/data-wdyG7mqn.js` remains byte-identical. `data/geography.js` is a reviewed static projection for the redesigned renderer; it is not a new observation. The original 45 claims and their grades remain author supplied. Missing primary-source originals are not invented. Raw geography, source dates, affiliations and public-source facts do not acquire independent authority through improved visual design.

The existing `review/core.js`, journal key and schema remain byte-identical to the prior public release. There is no migration, journal clearing or replacement. Saved browser history and its hash/sequence/quote checks remain authoritative for this browser workspace. Source dates retain their written calendar day and timezone instead of silently becoming a different date in the viewing machine's timezone. Local actor identities remain self-reported.

User records stay in the visitor's browser unless explicitly exported. Plain exports include supplied text and recorder names. This public-site origin is unsuitable for confidential client data or secrets. The native installation retains official NTA signature verification, case production/admission, signed peer identities and native whole-workspace recovery. No public-page control impersonates those services, uploads user records, reaches estate machines, sends messages or makes institutional decisions.

## Files

All files are steward-owned. There is no new scheduler or machine-written source state.

- `review/index.html`, `product.css`, `app.js`, `atlas.js`, `icons.js`: product shell, design system, controller and native cartography.
- `review/core.js`: unchanged browser-journal authority.
- `assets/`: original source-derived cartography and interface assets, with provenance.
- `data/map-data.*`: original claims, actions and relationships.
- `data/geography.js`, `geography-provenance.json`: exact original geometric object and identity.
- `data/access-ledger.json`: fourteen explicit access dispositions.
- `map/`: retained original compiled geographic application, its public journal bridge and presentation-only polish.
- `library/FIELD_DESK_GUIDE_EN_JA.md`: current public-product operating guide. The native 1.1 operating guide and pilot sheet retain their original scope.
- `index.html`, `engagement-brief.md`: complete bilingual project and commercial explanation, with the same source-derived visual system.
- `data/evidence.json`, `operations.json`, `finite-model.json`: historical qualification projections, not fresh external audits.
- `scripts/check.py`, `check_map.py`, `check_product.py`: stdlib static/source/custody checks.

## Qualification and publication

Run all three static validators from the repository root. Native browser acceptance separately exercises the actual product, both languages and 1440/390/320 layouts. It checks original data, all layers, place search, zoom/fit, exact routes, malformed route recovery, source drafts, quote refusal, review separation, costs, stages, journal exports, encrypted restore, real document access, reload continuity and absence of external requests. Public live readback verifies exact deployed bytes and reruns the browser paths after the unchanged normal Pages pipeline.

The existing shared-site publisher, release gate and Cantos compatibility stage remain unchanged. The `retained-work-check.yml` workflow checks this directory; it is not a second publisher. Private runtime data, keys, credentials, original correspondence and native operator state remain outside the public tree.

## Offline use

Download `downloads/Suginami_Public_Map_Kit.zip`, extract it, and run `START_MAP.cmd` on Windows or `python3 -B scripts/serve_local.py` elsewhere with Python 3.11 or newer. The stdlib server binds only to localhost and opens the same product. All required code and source data are included. Related external projects still require their own destination or connection. Export/import carries browser journals between public and local origins; the application never silently transfers them.

The main explanatory page additionally supports a self-contained HTML save. The functional atlas and desk use the complete kit because their real modules and data must accompany them.

## Evidence and completion boundaries

Historical software tests are scoped to their exact paths. Improved styling does not establish a customer, institutional acceptance, professional translation approval, measured labor savings or an insurance guarantee. The proposed implementation remains $35,000 for six weeks, with $17,500 at signing and $17,500 upon contractual acceptance; the separate audit proposal remains $15,000. Existing intellectual-property and authority boundaries remain controlling.

Japanese interface text and guides are working explanatory copy. Original source wording and historical documents remain in their original languages where appropriate. New observations, supported defects or specifically authorized scope changes warrant new work; a fresh conversation does not reopen completed calculations merely to reconstruct context.
