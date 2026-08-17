# Manzanita estate parity

This package implements the P9 estate-wide parity gate as an exact disposition register over the existing `resolution-backfill` source inventory. It does not upgrade the underlying estate products. It proves that every public surface, every exact finding, and every required asset is accounted for as qualified, held, archived, or donor, with explicit product relationship and noninheritance.

The design integrator owns the relationship map. Source custody owns the exact surface records and evidence paths. Each source-product owner retains its product, qualification, and release authority. Essential Attention remains a separate administrative product with only a bounded FAB-compatible handoff. The historical public `manzanita/` route remains a rollback and comparison donor. The `manzanita-next` whole experience remains an internally qualified successor candidate rather than a public replacement.

`build_parity.py` validates the source inventory and every surface against the existing surface schema, expands each surface into one epic plus every exact finding and required asset, checks the complete authored disposition map, binds the fresh P8 report and contained-board receipt, and emits deterministic `PARITY_REGISTER.json` and `BUILD_RECEIPT.json` objects. Missing surfaces, duplicate identities, component-count drift, unknown dispositions, invalid evidence, private or credential keys, P8 regression, or any public, release, external, or task-count effect fail the build.

A passing P9 register means the estate has complete disposition coverage. It does not mean all estate products are remediated, P0 is zero, the weighted score is 99, the public endpoint is qualified, or a cold successor has passed. Those remain separate release gates.

The controlling question is whether a cold successor can explain the status, relationship, evidence, unresolved obligations, and authority boundary of every estate surface without mistaking resemblance, shared vocabulary, or a bounded handoff for product completion.
