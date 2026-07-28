# Accepted decision circulation

Organ Evolution may serialize a decision only after a human-owned record marks one candidate `accepted`. The serialization path does not authenticate the decider, create a mandate, admit work into the estate, choose a lane, schedule an actor, execute an adaptation, merge a branch, accept an outcome, or mutate a campaign.

The source workspace remains:

```text
axm-organ-evolution/1
```

A successful compilation produces three independently bound records:

```text
axm-organ-decision/1       orgdec1_<sha256>
axm-organ-evolution-job/1  organjob1_<sha256>
axm-organ-execution/1      organexec1_<sha256>  optional
```

## Admission requirements

The compiler refuses circulation unless all of the following are visible in the source workspace:

- the decision state is `accepted`;
- the selected candidate belongs to the selected organ;
- the named decider is one of the candidate's declared deciders;
- all twelve fitness dimensions are bounded integer values;
- the function, authority, evidence, migration, and reversibility gates all pass;
- the preserve, alter, retire, and introduce migration sets are present;
- the candidate cites at least one independent confirmed, measured, or reported evidence record;
- the decision carries an ISO-8601 decision time, mandate reference, mandate basis, and rationale;
- the circulation lane, task, surface, producer, and consumers are explicit;
- a terminal execution carries an outcome, completion time, implementation references, and verification references.

These checks establish structural admissibility. They do not establish that the source claims are authentic.

## Identity law

`orgdec1_` binds the accepted decision, candidate geometry, decider assertion, mandate assertion, gates, dimensions, migration ledger, and cited evidence. Execution evidence cannot rewrite this identity.

`organjob1_` binds the exact source-model identity, decision, circulation route, authority membrane, and limits. The optional execution record is excluded from the job digest and binds back to the job through its own `organexec1_` identity.

The source-model digest remains visible so a later workspace revision cannot impersonate the exact source from which the job was compiled.

## Authority membrane

```text
Decision authority  external named authority under the cited mandate
Compiler authority  canonical serialization and structural refusal only
Bloodstream         preserve, route, block, invalidate, recover, report
Executor             owning implementation organ under its own authority
Verifier             produce cited evidence
Acceptance           named decision authority, never the compiler or carrier
```

The compiler and resulting job explicitly forbid automatic admission, priority inference, supplier selection, agent scheduling, branch merge, action execution, outcome acceptance, and campaign mutation.

## Browser and command-line parity

The production page loads `decision-job.js` locally and exposes an **Export circulation job** control only for a locally accepted, admissible candidate. The browser performs the same structural refusal and canonical SHA-256 derivation as the Python reference implementation.

Build and verify the synthetic accepted-decision fixture:

```bash
python organ-evolution/scripts/decision_job.py build \
  organ-evolution/data/fixtures/accepted-decision.fixture.json \
  --output /tmp/accepted-decision-job.json

python organ-evolution/scripts/decision_job.py verify \
  /tmp/accepted-decision-job.json
```

Run the fail-closed regression suite:

```bash
python organ-evolution/scripts/test_decision_job.py -v
```

The permanent browser journey imports the same fixture, compiles it in Chromium, compiles it with Python, compares the complete products, invokes the visible download control, and verifies that the downloaded job is byte-equivalent in data to the qualified reference product.

## Current limit

The fixture is synthetic. A valid exported job is a reconstructable decision assertion, not proof that Bloodstream accepted it, that an owning organ executed it, that a verifier is independent, or that the named authority accepted a terminal outcome. The first downstream consumer must independently verify the job before recording it, and must preserve rejection as evidence rather than silently repairing the source. Those are separate receipts in the next circulation boundary.
