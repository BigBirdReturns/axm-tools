# Manzanita Works · One place, every scale

This directory is the public-safe front door for the connected Household Habitat, Street Glide, Regional Observatory, Civic Planner, Manzanita Works, and Essential Attention estate.

It is a composed website rather than another internal dashboard. A visitor can move one illustrated place record across seven scales, toggle eight independent overlays, and change among five functional perspectives without learning the repository topology first.

## What it shows

The scale rail moves through:

1. Plant
2. Household
3. Property
4. Street
5. Neighborhood
6. Region
7. Stewardship

The overlay dock keeps habitat, shade and heat, water, fire, air, access, labor and tools, and authority and programs distinct. No aggregate household or property score is produced.

The actor switcher projects the same record for a resident, nursery or grower, crew or property steward, planner or public program, and successor. These are role-function-need perspectives, not simulated personalities.

The Manzanita Works section describes an assistance-first sequence and a purpose firewall. The Essential Attention section links to the live FAB Operating Desk as the governance and follow-through layer.

## Public and private custody

The page contains an illustrated reference place and public-safe operating descriptions. It does not publish private household records, private meeting records, source correspondence, exact addresses, or private evidence bytes. It is not an official property assessment, hazard determination, insurance decision, or substitute for lawful authority.

## Runtime

The application is plain static HTML, CSS, SVG, and JavaScript. It has no backend and makes no outbound data requests. GitHub Pages serves the same source that can be downloaded and opened locally.

## Qualification

`tests/public_contract_test.py` verifies the seven scales, eight overlays, five functional perspectives, operating boundaries, module inventory, and public/private custody language. It writes `QUALIFICATION.json`.

`tests/browser_test.py` drives all seven scales, every overlay control, all five functional perspectives, the Essential Attention handoff link, and the mobile layout in Chromium. It asserts zero outbound requests and zero JavaScript errors.

## What can rot

The main maintenance risk is semantic rather than technical. As the estate evolves, the public descriptions, module status, and link targets must remain truthful. Private evidence must never be copied into this public surface merely because it would make the story more vivid.
