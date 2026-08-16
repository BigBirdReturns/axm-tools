# Manzanita Works v1.6 source and asset foundation

This directory begins the successor build with real sources, explicit provider contracts, and an artifact-producing acquisition run. It does not alter or certify the current public Manzanita page.

## Governing rule

The interface may use an authored reference world to explain the product. It may not use generated imagery to impersonate street imagery, aerial imagery, terrain, current weather, current air quality, incident data, monitoring data, captured work, or a source-backed operating receipt.

## Street Glide provider order

```text
Google Street View
→ Mapillary
→ KartaView
→ Panoramax
→ owned 360 or site capture
→ map-only mode
```

Provider selection is based on availability first, then provider policy, capture recency, distance, image quality, registration fitness, and rights. The provider and capture date remain visible. A provider outage or coverage gap produces an explicit degraded state. It does not trigger a generated substitute.

## Coordinate law

Street imagery, the camera model, every natural-border anchor, every visibility mask, and every overlay share one scene transform. Panning, zooming, heading, pitch, or field-of-view changes must update the imagery and overlay together. A release fails when the overlay drifts from the curb, sidewalk, driveway, roof, canopy, utility, or work edge it claims to follow.

## Live-source law

Every retrieval produces a source envelope containing the source ID, exact request, retrieval time, HTTP response metadata, payload path, byte count, SHA-256 digest, attribution, storage policy, freshness limit, claim scope, and any error. Optional sources may fail. Their failure must remain visible. Required sources block qualification.

## Public demonstration place

The initial source run uses the Los Angeles County Arboretum as a public institutional testbed. It exercises source acquisition, terrain, aerial context, street-imagery coverage, attribution, outage handling, and spatial normalization without publishing a private household address. Household-specific behavior remains illustrative until a consented first-party record exists.

## First qualification floor

The source-foundation workflow must acquire and validate:

- NWS point routing, forecast, hourly forecast, alerts, and a current observation when available;
- CAL FIRE current incident source and a normalized incident table;
- USGS orthoimagery and 3DEP hillshade exports at usable resolution;
- OpenStreetMap geometry through Overpass with ODbL attribution;
- nearby USGS water-site metadata and instantaneous values when available;
- KartaView and Panoramax coverage probes;
- explicit missing-credential receipts for Google Street View, Mapillary, AirNow, and FIRMS when keys are absent.

The workflow uploads the complete acquisition directory, including payloads, source envelopes, manifest, visual report, and qualification receipt. Nothing in this directory claims that the successor site is complete.
