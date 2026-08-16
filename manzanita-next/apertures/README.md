# Manzanita seven-aperture operating system

This directory operates the bounded seven-aperture tranche associated with `JDB99-013`. The object is one canonical place identity projected through Plant, Household, Property, Street, Neighborhood, Region, and Stewardship apertures. Each aperture changes the operating object, evidence set, geometry, safe action, authority, acceptance, and handoff. The system is not qualified merely because seven labels exist or because one field image is cropped seven ways.

## Actors and authority

The aperture composer reads the public-safe place dossier, the Forkline Field constitution, and an explicitly authored non-private demonstration cartridge. It may normalize these donors into one aperture bundle, preserve source and authorship custody, and refuse an aperture whose evidence or authority fields are incomplete. It may not fabricate observation, promote public context into a private household finding, infer a parcel boundary, convert regional conditions into a local score, or authorize inspection, field work, enforcement, insurance action, eligibility, or completed remediation.

The resident seat operates the Plant and Household apertures within household care authority. The steward seat operates bounded verification and planning across Household, Property, and Street after lawful access and evidence requirements are satisfied. The program-operator seat operates Neighborhood, Region, and Stewardship coordination within a named public or community program authority. Release authority controls later product admission and publication. A cold successor must reconstruct every aperture from the retained place, source, authorship, geometry, and decision receipts.

## Mechanism

`APERTURE_CONTRACT.json` freezes the seven aperture identities, evidence and geometry laws, actor authorities, projection boundaries, failure states, and acceptance campaign. `AUTHORED_DEMO.json` supplies only the explicit authored demonstration records needed to prove Plant, Household, and Stewardship behavior without using a private household. `build_apertures.py` consumes the generated public dossier under `manzanita-next/public-demo/out/`, validates the exact source-backed place identity, combines only permitted evidence, and emits `out/APERTURE_BUNDLE.json` plus a deterministic build receipt.

The bundle preserves one `place_id`, one source-run identity, and one public-projection receipt across all seven apertures. Every aperture has:

- a distinct object class and geometry identity;
- source or authorship rows with state, time, uncertainty, rights, and claim scope;
- a reading that does not exceed the evidence;
- a safe action owned by a named actor;
- an authority statement and prohibited consequence;
- acceptance and handoff conditions;
- a degraded-state response when required evidence is missing, empty, stale, limited, unavailable, terms-blocked, or unknown.

The Plant aperture is an authored living-object demonstration, not a diagnosis or sensor reading. Household is an authored public-safe habitat envelope, not a private record. Property uses public imagery, terrain, and map context without claiming a surveyed parcel. Street uses map and imagery-provider state without filling missing coverage with a generated street. Neighborhood and Region use public source context without transferring regional evidence to a parcel or household. Stewardship relates source gaps, offers, decisions, assistance, and follow-through without collapsing them into one score or adverse action.

## Operation

After a source acquisition and public-demo build have produced `manzanita-next/public-demo/out/`:

```bash
python manzanita-next/apertures/build_apertures.py \
  --repo-root . \
  --public-demo-root manzanita-next/public-demo/out \
  --output manzanita-next/apertures/out

python -m unittest discover \
  -s manzanita-next/apertures/tests \
  -p "test_*.py"
```

The ordinary build is expected to produce an internal candidate with explicit holds. It does not modify the historical public `manzanita/` route, deploy a successor, use private household data, perform field work, award assistance, make an adverse decision, qualify a whole product, or mutate the remembered 497-task count.

The controlling question is whether the same canonical place can widen through seven genuinely different operating apertures while every source, authored field, uncertainty, actor, authority, safe action, prohibited consequence, and handoff remains intact.
