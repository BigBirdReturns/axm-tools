# Manzanita eight registered overlay instruments

This directory operates the bounded overlay tranche associated with `JDB99-015`. The object is one canonical place and one retained base registration projected through eight independent instruments: Care, Shade, Water, Heat, Air, Fire, Access, and Assistance. Each overlay carries its own evidence, geometry class, legend, reading, uncertainty, safe action, authority, conflict behavior, prohibited consequence, source state, and handoff. The system is not qualified because eight labels or colored layers exist.

## Actors and authority

The overlay composer consumes the exact public-safe place dossier, the seven-aperture bundle, the Street Glide scene decision and registration receipt, the Forkline Field constitution, and an explicitly authored public-safe overlay cartridge. It may bind each overlay to the exact base-image identity and normalized coordinate space, preserve public source and authored geometry custody, classify healthy and degraded states, and refuse invalid geometry or cross-object identity drift. It may not convert an authored overlay extent into an observed condition, transfer regional evidence to a parcel or household, identify a physical feature from an image gradient, infer an adverse score, or create an external action.

The resident may use Care and Household-related readings for ordinary household attention after real observation. The steward may use Shade, Water, Heat, and Access to prepare bounded verification questions after lawful access and evidence requirements are met. The program operator may use Air, Fire, and Assistance for public information, source repair, coordination, and assistance routing within lawful program authority. Release authority controls later interactive and public admission. A cold successor must rebuild every overlay from the retained source, authored geometry, base registration, legend, conflict, and decision receipts.

## Mechanism

`OVERLAY_CONTRACT.json` freezes the eight overlay identities, source apertures, actors, readings, actions, authorities, legends, uncertainty, conflict law, and adverse-action boundary. `AUTHORED_OVERLAY_DEMO.json` supplies only normalized registration geometry and legend symbols for demonstration. Its polygons, lines, and points are authored placements, not observed canopy, drainage, temperature, pollutant, incident, access, work, need, or assistance geometry.

`build_overlays.py` consumes:

- `manzanita-next/public-demo/out/PUBLIC_DATA.json` and its projection receipt;
- `manzanita-next/apertures/out/APERTURE_BUNDLE.json` and build receipt;
- `manzanita-next/street-glide/out/SCENE_DECISION.json`;
- `manzanita-next/street-glide/out/REGISTRATION_RECEIPT.json`;
- the Forkline Field constitution;
- the authored overlay cartridge.

It proves that every donor refers to the same public-safe `place_id` and `source_run_id`, binds the overlays to the exact base-image digest and normalized image coordinate space, validates every geometry coordinate, resolves every source and aperture reference, generates explicit unknown rows where a registered public source is absent, derives the overlay state without treating missing as zero, constructs a symmetric conflict matrix, rejects private and credential fields, and emits deterministic overlay and build digests.

The expected exact-head candidate may contain mixed operating states. Heat may be source-backed while Air is held for a missing approved credential. Fire may be degraded because official incident perimeters are available while thermal detections are absent. Access may remain map-only because no street scene qualifies. Care and Assistance may remain explicitly authored demonstrations. These are different states and remain visible.

## Overlay laws

Care relates living-object and household attention but cannot diagnose or fabricate a sensor reading. Shade relates public imagery, terrain, and weather context but cannot identify or measure a real canopy. Water relates terrain, weather, and nearby monitoring without becoming household moisture, irrigation, drainage, or supply evidence. Heat relates official weather observations and forecasts without becoming a local exposure or safety directive. Air preserves AirNow availability or absence without inventing AQI or health advice. Fire separates incident perimeters, alerts, thermal detections, terrain, and source failures without producing parcel risk, insurance, evacuation, damage, cause, or loss findings. Access preserves public map and Street Glide coverage without authorizing entry, traffic, pruning, inspection, or work. Assistance relates evidence gaps and authored workflow mechanics without creating a real need, offer, eligibility, award, decision, execution, or completion.

Every overlay shares the same base registration but retains its own geometry and evidence. Shared coordinate space does not create shared authority. Two overlays may be displayed together only under their declared conflict behavior. Contradictory, stale, empty, missing, or unavailable sources remain visible and cannot be averaged into a confidence score.

## Operation

After the public-demo, aperture, and Street Glide outputs exist:

```bash
python manzanita-next/overlays/build_overlays.py \
  --repo-root . \
  --output manzanita-next/overlays/out

python -m unittest discover \
  -s manzanita-next/overlays/tests \
  -p "test_*.py"
```

The ordinary result is an internal machine candidate with explicit holds. It does not modify the historical public `manzanita/` route, expose a private household, operate a provider credential, identify a physical feature, authorize field work, create assistance or adverse decisions, qualify an interactive overlay product, produce a public endpoint, award a design score, or mutate the remembered 497-task count.

The controlling question is whether a cold successor can compose all eight instruments over one exact place and base registration while preserving every source, authored geometry, state, legend, uncertainty, conflict, actor, action, authority, prohibited consequence, and handoff independently.
