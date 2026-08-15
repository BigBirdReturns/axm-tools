# AXM resolution backfill

This directory reopens every public surface that the estate previously called complete, passed, released, sealed, or resolved.

The backfill does not erase earlier work. It changes the burden of proof. A legacy qualification remains a historical receipt for the checks it actually ran, but it no longer establishes that the whole product is finished. Every surface must now show the same discipline that the Manzanita v1.6 source foundation introduced: exact object classification, named functional actors, source custody, visible failure states, mechanism fidelity, real interaction deltas, visual and typographic control, responsive and accessibility evidence, negative tests, continuity, provenance, and a retained qualification package.

## Scope

The bootstrap inventory covers every current production surface on `main`:

- repository shell and root catalogue;
- Acceptance;
- Breakout Parity;
- Clinical Site Fabric;
- Essential Attention;
- Identity;
- Manzanita Works;
- Organ Evolution;
- Polybolos;
- PTA Tracker.

The Manzanita v1.6 source foundation in draft PR #90 is registered as a donor, not as a completed product.

## Status vocabulary

`reopened` means a prior completion claim exists, but at least one mandatory gate lacks direct evidence.

`remediation_in_progress` means a successor is already replacing the failed mechanism, but the public surface remains unqualified.

`qualified` is reserved for a surface whose mandatory gates all pass and whose receipts are retained. No bootstrap surface is marked qualified.

## Run the audit

```bash
python resolution-backfill/scripts/audit.py \
  --root . \
  --out resolution-backfill/out
```

The audit is stdlib-only. It verifies the inventory structure, confirms that every claimed evidence path exists, hashes those files, finds legacy qualification records, enforces the rule that a qualified surface cannot contain a non-pass mandatory gate, and writes a machine-readable and human-readable report.

The audit passing means the estate has an honest, complete backfill ledger. It does not mean the underlying surfaces are already remediated.

## Operating sequence

1. Preserve each existing release and qualification as historical evidence.
2. Reconstruct the object, actors, mechanism, sources, authority, and failure modes.
3. Acquire or build the missing assets listed in `inventory.json`.
4. Replace label-only controls with real operating apertures.
5. Qualify typography, visual density, light/dark parity, compact widths, keyboard, touch, and assistive technology.
6. Exercise malformed inputs, stale data, blocked providers, network loss, storage loss, and cold successor replay.
7. Cut a new release. Do not edit a frozen release to make it look as though the evidence always existed.

## Control rule

A product is not resolved because its files load, its feature count matches a checklist, or its current screenshots look good. It is resolved only when the object survives source inspection, real use, failure, handoff, and close visual reading without changing its claims or hiding its weak states.
