# Manzanita Street Glide scene and registration kernel

This directory operates the bounded Street Glide tranche associated with `JDB99-014`. The object is a provider-aware street-scene resolver and a natural-border registration kernel. It selects the best admissible scene in the frozen provider order, retains provider and rights custody, refuses generated substitution, and can snap an explicitly authored candidate line toward strong image edges within a bounded search radius. It does not identify a curb, canopy, parcel, hazard, ownership boundary, access route, work condition, or completed field observation merely because an image edge exists.

## Actors and authority

The provider resolver reads the public source registry, exact acquisition receipts, provider-health state, and any admissible scene metadata. It may rank eligible scenes by provider precedence, rights, source health, capture time, distance, heading, and required metadata. It may return a map-only hold when no scene qualifies. It may not request an unapproved credential, exceed a quota, purchase imagery, cache prohibited bytes, invent coverage, or present generated or modeled media as observation.

The registration operator supplies an authored candidate polyline and a bounded search radius. The kernel may inspect local image gradients, propose snapped points, compute displacement and edge-strength receipts, and preserve the original and proposed line. It may not name the physical feature, close an unknown boundary, alter the source image, or authorize a downstream overlay without accountable review. The design integrator may consume an admitted scene and registration receipt. The steward may use it to prepare a field-verification question but receives no inspection, entry, pruning, work, traffic, safety, property, enforcement, or completion authority. Release authority controls later product integration and publication.

## Mechanism

`STREET_GLIDE_CONTRACT.json` freezes the provider order, scene eligibility law, map-only behavior, registration law, evidence fields, failure states, and adverse-action boundary. `AUTHORED_REGISTRATION_DEMO.json` supplies non-private demonstration control points and expressly denies observed-feature standing. `resolve_scene.py` converts public-demo source rows and optional provider-scene metadata into one admissible scene decision or an explicit map-only hold. `register_natural_border.py` uses a deterministic grayscale gradient field to search normal to each authored segment, selects a bounded edge candidate, and emits original points, proposed points, displacement, edge strength, confidence class, image digest, parameters, and claim boundary.

The provider order is:

1. Google Street View, rendered live under provider attribution and storage restrictions.
2. Mapillary.
3. KartaView.
4. Panoramax or an owned Panoramax instance.
5. Owned 360 or authorized site capture.
6. Map-only mode.

A provider wins only when its source state, scene metadata, rights, capture time, distance, heading, and payload or render path satisfy the declared contract. Missing credentials, empty coverage, stale scenes, rate limits, outages, terms blocks, unknown metadata, and failed registration remain visible. A higher-ranked provider that is unavailable does not erase the reason it was skipped. A lower-ranked provider does not inherit the higher provider’s rights or claim scope.

Natural-border registration is deliberately narrower than feature recognition. The kernel can report that a proposed point moved toward a strong local image gradient. It cannot report that the gradient is a curb, property line, roof edge, vegetation boundary, drainage feature, fuel break, or work limit without separate source-backed interpretation and accountable review. A no-snap result is valid evidence and must remain available to the operator.

## Operation

After a public-demo build has produced `manzanita-next/public-demo/out/`:

```bash
python manzanita-next/street-glide/resolve_scene.py \
  --public-data manzanita-next/public-demo/out/PUBLIC_DATA.json \
  --scenes manzanita-next/street-glide/AUTHORED_REGISTRATION_DEMO.json \
  --output manzanita-next/street-glide/out/SCENE_DECISION.json

python manzanita-next/street-glide/register_natural_border.py \
  --image manzanita-next/public-demo/out/site/assets/base-imagery.png \
  --demo manzanita-next/street-glide/AUTHORED_REGISTRATION_DEMO.json \
  --output manzanita-next/street-glide/out/REGISTRATION_RECEIPT.json

python -m unittest discover \
  -s manzanita-next/street-glide/tests \
  -p "test_*.py"
```

The expected result under zero commercial credentials may be map-only mode plus a valid registration demonstration over public base imagery. That is a successful degraded state, not a source-coverage success. This tranche does not modify the historical public `manzanita/` route, expose a private household, authorize field action, qualify Street Glide as an interactive product, produce a public endpoint, or mutate the remembered 497-task count.

The controlling question is whether a cold successor can explain why one provider or map-only mode was selected, reproduce the exact registration proposal, distinguish image-edge evidence from physical-feature interpretation, and preserve every source, rights, failure, field, adverse, and release boundary.
