# Manzanita Five Functional Roles

This directory operates the bounded `JDB99-016` role-projection architecture over one admitted public-safe Manzanita place. The object is a five-seat machine contract and one internal FAB offer-preparation handoff. It is not a personality simulator, permissions system, private household record, field console, eligibility engine, work order, or public release.

The five seats are Resident, Nursery or Grower, Crew or Property Steward, Planner or Public Program, and Cold Successor. Every seat consumes the same place and source-run lineage while changing evidence, controls, authority, acceptance, export, handoff, failure, and prohibited consequence. Missing credentials, unavailable sources, authored demonstrations, map-only operation, and degraded evidence remain visible inside every projection that consumes them.

`ROLE_CONTRACT.json` freezes the five-seat law. `build_roles.py` consumes the exact public demonstration dossier, seven-aperture bundle, eight-overlay bundle, their build receipts, and the Forkline Field constitution. It proves one place and source run, validates donor effects, rejects private and credential keys, preserves source-state and registration limits, covers all seven apertures and all eight overlays, builds a complete handoff graph, and emits deterministic `ROLE_BUNDLE.json`, `FAB_HANDOFF.json`, and `BUILD_RECEIPT.json` objects.

The Resident projection may review, correct, accept, refuse, narrow, or defer. The Nursery or Grower projection may prepare conditional options and name required observations. The Crew or Steward projection may prepare no-entry verification and work-readiness questions. The Planner or Program projection may prepare source repair, coordination, or an accountable assistance offer without deciding eligibility. The Cold Successor projection may verify, rebuild, compare, and report without inheriting release or external-effect authority.

`FAB_HANDOFF.json` is a portable internal preparation record for Essential Attention’s FAB offer register and executive review. It carries the planner evidence state, affected-resident authority, refusal and appeal, no eligibility, no award, no execution, and a complete effect firewall. It does not send, publish, schedule, pay, appoint, represent, award, deny, authorize work, or create institutional acceptance.

`RECOVERY_RECEIPT.json` records the source-custody boundary. The segmented transport preserved the role contract, README, workflow, and a damaged builder member. The builder member contained 596 null bytes across 81 runs and corrupted source beginning before the first null. The original implementation was therefore not claimed as recovered. The current builder, adversarial tests, and contained review records were authored against the retained contract, workflow assertions, upstream donor schemas, and exact donor artifacts. The damaged archive remains available in the retained diagnostic workflow artifact.

From the repository root, a local role build uses already generated donor outputs:

```bash
python manzanita-next/roles/build_roles.py \
  --repo-root . \
  --public-demo-root manzanita-next/public-demo/out \
  --aperture-root manzanita-next/apertures/out \
  --overlay-root manzanita-next/overlays/out \
  --output manzanita-next/roles/out
```

The adversarial suite is:

```bash
python -m unittest discover \
  -s manzanita-next/roles/tests \
  -p "test_roles.py"
```

A passing role build proves internal architecture and a bounded handoff record. It does not prove an interactive role switcher, private-data operation, actual resident acceptance, nursery inventory, field fitness, provider operation, a real offer, eligibility, award, work authorization, production export and reimport, public serving, rollback, or independent cold-successor operation.

The controlling question is whether one canonical place can pass through five functional seats while every seat changes the governed work and the FAB handoff preserves affected-actor authority, refusal, appeal, uncertainty, and no-effect law without manufacturing consent, eligibility, execution, or release.
