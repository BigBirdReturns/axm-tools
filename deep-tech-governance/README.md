# AXM Deep-Tech Governance Pack v1.0.0

This directory extracts the reusable mechanism proven against the first real deep-tech reference target into a target-neutral product surface. It is designed for small defense, robotics, autonomy, maritime, aerospace, industrial, and adjacent deep-technology startups whose public footprint is richer than their internal governance record.

The pack does not select companies. A human supplies the target and exact selection receipt. The same code then compiles a bounded public baseline, a diligence map, an admission map, and an operating-readiness view without allowing public observations to become private company truth.

## Product contract

```text
human-selected target
→ exact selection receipt
→ bounded public acquisition
→ governed company state
→ sector transfer controls
→ Public Baseline
→ Diligence Map
→ Admission Map
→ Operating Readiness
→ deterministic qualification
→ successor event delta
```

A portability pass requires zero target-specific code changes. Target names, facts, sources, and company-specific state belong in fixtures or target cartridges, never in the generic pack.

## What this pack makes reusable

`pack.json` is the executable policy surface. It carries the public/private boundary, eleven independent state tracks, twenty-four claim-transfer controls, nine successor-event classes, the minimum technical-evidence contract, and ten portability gates.

The schemas define:
- `governed-state.schema.json`: target selection and the strict company-state envelope.
- `technical-evidence.schema.json`: configuration, sensors, calibration, environment, telemetry, acceptance, result, and observed-versus-generated provenance.
- `authority-rights.schema.json`: entity-bound authority and explicit IP/data/publicity/manufacturing/evidence-use rights.
- `successor-event.schema.json`: bounded public events and the permitted successor actions.

`scripts/compile_outputs.py` turns any conforming target state into four product projections. `scripts/validate.py` validates the pack, enforces the target-neutral boundary, exercises a synthetic target, checks the reference fixture contract, and writes a deterministic qualification receipt.

## Four product projections

1. **Public Baseline**: public claims and evidence with allowed language, prohibited upgrades, and source boundaries.
2. **Diligence Map**: held, stale, high-risk, and critical state with the exact evidence gaps that block promotion.
3. **Admission Map**: company-controlled records needed to resolve open instruments, rights, authority, financing, technical, customer, and procurement gaps.
4. **Operating Readiness**: unresolved high/critical exceptions, technical evidence requirements, authority gaps, and capability maturity.

These are projections over one governed state. They do not rewrite evidence.

## Reference Target 01

`fixtures/reference-01.json` binds the frozen first real-world reference implementation as a regression fixture. Its company-specific data stays outside generic code. The fixture exists to force the generic pack to continue handling synthetic media, partner-capability leakage, financing language, simulated telemetry, authority ambiguity, first-party testing, registry ambiguity, bounded search misses, public-IP assertions, and source-ingestion corrections.

The CEO-facing reference branch remains untouched. This pack is developed on a separate branch so the evaluation object cannot drift while the reusable machinery advances.

## Running it

```bash
python deep-tech-governance/scripts/validate.py --root deep-tech-governance --write
python deep-tech-governance/scripts/compile_outputs.py \
  deep-tech-governance/fixtures/synthetic-target.json \
  --out /tmp/deep-tech-projections
```

The scripts use only the Python standard library. No network call, account, target discovery, or external-effect adapter is required.

## Boundary

This pack can reconstruct and govern what public evidence supports. It cannot establish private agreements, internal counterparties, cap-table or bank records, nonpublic technical evidence, actual corporate authority, private system access, or organizational adoption. Those remain explicit admission gaps until the selected company supplies an attributable record and the operator has authority to admit it.
