# Manzanita public-safe demonstration place

This directory operates the public-safe demonstration-place tranche associated with `JDB99-018`. The object is a source-adaptive read-only place dossier built from the admitted source foundation, a public place configuration, the Forkline Field design constitution, and explicit degraded-state receipts. It is not the historical public `manzanita/` route, a private household record, a live safety directive, a field inspection, a completed-work claim, or a public release.

## Actors and authority

The source-custody seat acquires and validates provider payloads and receipts. The projection builder reads only the public-safe place configuration and admitted acquisition bundle, removes private or unnecessary fields, preserves source times and failure states, and emits a self-contained site artifact. The design integrator applies the admitted Forkline Field constitution. Three contained product seats operate the artifact: visitor, steward, and program operator. The visitor may read public context and source health. The steward may prepare a bounded site-verification plan but receives no entry, inspection, work, or completion authority. The program operator may route source gaps, assistance, and accountable review but may not create a parcel score, insurance consequence, eligibility decision, enforcement action, or unreviewed external effect. Release authority controls any later publication.

## Mechanism

`PLACE_DEMO_CONTRACT.json` freezes the public projection, actors, views, source families, failure law, privacy boundary, and qualification campaign. `build_public_demo.py` reads `manzanita-next/config/place-demo.json`, `manzanita-next/config/source-registry.json`, the generated `manzanita-next/out/` acquisition bundle, and `manzanita-next/design-system/CONSTITUTION.json`. It emits a self-contained site under `out/site/`, a public projection receipt, and a build receipt.

The generated site contains four operating views over one public place identity:

- **Place** exposes public coordinates at reduced precision, map and imagery source state, public geometry counts, and the distinction between source imagery and authored registration marks.
- **Weather** exposes National Weather Service observation, forecast, hourly, station, and alert state with source times, staleness, and no safety guarantee.
- **Water** exposes nearby USGS monitoring availability and returned values without implying household supply, pot moisture, irrigation fitness, or site inspection.
- **Fire** exposes CAL FIRE/NIFC/FIRIS and NASA FIRMS acquisition state without creating a parcel-risk, insurance, evacuation, containment, or loss determination.

Each view changes the evidence object, source aperture, geometry layer, reading, safe action, authority, and prohibited consequence. Three actor controls change evidence, action, authority, acceptance, and handoff. Auto, Light, and Dark preserve identical content and semantic materials. Source failures remain visible as missing credential, empty coverage, stale, rate-limited, unavailable, terms-blocked, or unknown rather than being converted to zero or safe conditions.

## Public projection law

The artifact may contain only the configured public place label, place identifier, rounded public coordinates, public provider payload summaries, provider-attributed public imagery permitted for the artifact, source and retrieval times, transforms, uncertainty, health, rights, and claim boundaries. It excludes private household addresses, resident identities, private observations, secrets, credential values, unredacted first-party media, precise private coordinates, account identifiers, and provider payloads whose terms prohibit redistribution.

The source acquisition bundle remains the evidentiary donor. The site contains a bounded projection and digest, not the full underlying payload set. A source summary never inherits stronger authority than its receipt. A missing provider does not disappear. A statewide or regional feature count is not relabeled as a local incident. A nearby monitoring site is not relabeled as condition at the demonstration point.

## Operation

From the repository root, after the source-foundation acquisition and validation steps have produced `manzanita-next/out/`:

```bash
python manzanita-next/public-demo/build_public_demo.py \
  --repo-root . \
  --acquisition-root manzanita-next/out \
  --output manzanita-next/public-demo/out

python -m unittest discover \
  -s manzanita-next/public-demo/tests \
  -p "test_*.py"

python manzanita-next/public-demo/tests/browser_test.py \
  --root manzanita-next/public-demo/out/site \
  --out manzanita-next/public-demo/out/qualification
```

The contained board packet and decision under `review/` run only after the generated public projection, source summary, screenshots, browser report, projection receipt, and build receipt exist. The expected board result is `admit_with_holds` with release effect `internal_candidate_only`. A passing artifact proves a public-safe demonstration candidate. It does not deploy or qualify a public endpoint.

The controlling question is whether a cold outsider can understand the public place, source, time, transform, uncertainty, actor, authority, next safe action, and prohibited consequence in every healthy and degraded state without receiving a private record, a fabricated observation, or an adverse decision surface.
