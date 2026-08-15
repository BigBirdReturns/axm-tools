# Manzanita Works complete asset register v1

This file freezes the successor-build asset law after the v1.5.0 playtest. Manzanita Works is a live, source-adaptive place instrument with a clearly labeled deterministic demo mode. It is not a gallery of generated hero images.

## Inventory totals

- 361 total assets
- 222 P0 release blockers
- 128 P1 public-beta requirements
- 11 P2 enrichments
- 60 live runtime assets
- 22 first-party captured assets
- 74 derived analytical assets
- 143 system, schema, service, and test assets
- 61 authored assets
- 14 assets where generation is permitted

Generation is limited to labeled reference, demo, explanatory motion, redaction assist, or model-suggestion states. It may not replace available live street imagery, public geospatial data, current regional conditions, first-party observations, or completed-work receipts.

## Street Glide provider order

1. Google Street View, rendered live with provider attribution and storage restrictions.
2. Mapillary.
3. KartaView.
4. Panoramax or an owned Panoramax instance.
5. Owned 360 or site capture.
6. Map-only mode.

A coverage resolver selects the best available scene and exposes provider, capture date, heading, coordinates, source identity, attribution, and freshness. Every analytical layer shares the camera and scene transform. A generated street scene may never appear as observed evidence.

## Asset namespaces

| Namespace | System | Count |
|---|---|---:|
| `CORE-*` | Place core, time, source, geometry, privacy, lineage, snapshot | 18 |
| `UX-*` | Responsive navigation, themes, typography, controls, help, accessibility | 24 |
| `SG-*`, `ST-*` | Street imagery providers, registration, natural borders, street layers | 47 |
| `PL-*`, `HH-*` | Plant and household records, sensors, care, water, use, evidence | 30 |
| `PR-*` | Parcel, structures, aerial, terrain, roof, runoff, utilities, rules | 20 |
| `NB-*`, `RG-*` | Neighborhood and regional live conditions, resources, programs | 42 |
| `OV-*` | Eight overlays with source, geometry, reading, action, and legend | 40 |
| `ROLE-*` | Five seats with evidence projections, actions, authority, acceptance | 30 |
| `SW-*` | Essential Attention evidence, decisions, authority, execution, handoff | 20 |
| `INF-*` | Gateway, adapters, stores, transforms, cache policy, rendering | 28 |
| `CNT-*` | Editorial copy, tutorials, source/freshness and provenance content | 20 |
| `QA-*` | Full-seat, scale, overlay, role, live/stale/outage, visual and a11y tests | 30 |
| `LEG-*` | Terms, privacy, licenses, consent, purpose firewall, retention | 12 |

## Live source families

Street media: Google Street View, Mapillary, KartaView, Panoramax, owned 360 capture.

Property and map context: Los Angeles County GIS, City of Arcadia GIS, Overture Maps, OpenStreetMap data, Census TIGERweb and Geocoder, USGS NAIP, USGS 3DEP, Annual NLCD, and optional Google Solar/Aerial View enrichments.

Regional conditions: National Weather Service forecasts and alerts, AirNow current AQI, EPA AQS history, CAL FIRE incidents and FRAP/OSFM layers, NASA FIRMS hotspots, LANDFIRE vegetation and fuels, USGS Water Data APIs, and Drought.gov products.

First-party state: household observations, 360 imagery, site photos, local sensors, equipment/controller data, work evidence, and FAB records.

## Release laws

1. Seven scales must change the actual object, source aperture, geometry, action, and authority boundary. A crop of one image is a failure.
2. Eight overlays must remain registered to the base scene and carry source, freshness, legend, uncertainty, and a safe-action route.
3. Five roles must change the evidence projection, action set, authority, and acceptance criteria. A paragraph-only role switch is a failure.
4. Live data must show observation time, source time, ingestion time, valid-through state, and staleness.
5. Provider-specific attribution, caching, storage, and redistribution rules are executable policy.
6. Public and private projections are independently tested. No exact private address, household record, secret, or unredacted owned media enters the public bundle.
7. The static shell may be hosted on GitHub Pages, but live adapters, secrets, rate limits, normalization, source health, and policy-aware caching require a governed data gateway.
8. Qualification must cover the entire site in desktop, tablet, mobile, compact, light, dark, keyboard, touch, poor-network, stale-data, provider-outage, and cold-successor states.

## Build order

1. Place core, source registry, live-data gateway, policy and privacy projection.
2. Street Glide provider resolver, owned capture, camera model, scene registration, natural-border layers, and source drawer.
3. Seven distinct scale apertures.
4. Eight registered live overlays.
5. Five functional role apertures.
6. Whole-site typography, navigation, help, provenance, responsive and theme parity.
7. Public-endpoint qualification and cold-successor playtest.

This register is a release input. It does not authorize deployment and does not convert source context into survey, inspection, enforcement, coverage, ownership, or work authority.
