# Manzanita Works · Essential Capacity v0.1.0

Essential Capacity is the first operating slice of a community-capacity commons. It places tools, time, skills, pilotage, knowledge, space, mobility, and money inside one portable institutional model without requiring those resource classes to share the same accounting rules.

The release proves one public-safe N=1 chain:

1. a workshop need and a contributor offer remain open intents;
2. the contributor accepts a bounded commitment;
3. a steward records a MyTurn reference for the physical tool without claiming checkout;
4. the contributor records the workshop as performed;
5. a steward accepts the eligible contribution;
6. 120 Essential Minutes are issued against that accepted event;
7. the contributor redeems 60 minutes for bounded pilotage from a different provider;
8. a successor runs the contained checks and carries the packet forward.

This is collective clearing rather than bilateral barter. The person who receives the later pilotage does not have to receive it from the person or program that benefited from the earlier workshop.

## Open the application

The hosted route will be:

`https://bigbirdreturns.github.io/axm-tools/capacity-commons/`

The committed runtime is a self-contained static directory: `index.html` carries the public-safe seed and component register, `style.css` carries the visual surface, and `app.js` carries the local state machine, qualification sequence, portable export, and import logic. It loads no third-party runtime asset, opens no external connection, and has no source-system writeback.

## Hierarchy

The tool makes the operating hierarchy explicit:

- **Manzanita Works** supplies the public interaction grammar, scale, purpose limits, and assistance-first posture.
- **Essential Attention** determines what deserves bounded attention, what evidence exists, what authority is held, and where a handoff should go.
- **Essential Capacity** records what the community has or needs, what was offered, what was agreed, what actually happened, what was accepted, what credit was issued or redeemed, and what external effect remains withheld.
- **Domain programs** such as Essential Tools, the e-bike project, victim services, prevention, workshops, stewardship, and later mobility cartridges provide specialized vocabulary and rules.
- **External systems** remain commodities or donors at the perimeter. They do not define the canonical cross-domain relationships.

## Nine-object core

The release carries nine governed object families:

| Object | Function |
|---|---|
| Agent | A person, household, program, or organization with bounded standing |
| Project | The purpose and authority under which capacity moves |
| Capacity | A class of usable excess: tool, time, skill, pilotage, knowledge, space, mobility, or money |
| Intent | An offer or need that has not yet become an agreed obligation |
| Commitment | An agreed future event |
| Event | What was actually observed or performed |
| Credit | A community entitlement issued only after accepted eligible contribution |
| Evidence | The source, reference, receipt, or classification supporting a state |
| Policy | The authority, purpose, eligibility, custody, and adverse-use limits governing the chain |

Adapters are deliberately outside the nine-object constitutional core. They translate a narrow external system into references or events without granting that system authority over the entire commons.

## Functional seats

The runtime distinguishes five functions:

- **Member** drafts an offer or need and may request redemption.
- **Contributor** accepts a commitment and records performance.
- **Pilot / Navigator** supplies bounded hand-holding and prepares handoffs without replacing a domain professional.
- **Steward / Operator** reconciles external references, accepts eligible performance, and issues credit.
- **Successor / Auditor** reconstructs the chain, runs qualification, and exports the portable packet.

A seat is a function, not a named person. The same person may occupy different seats at different moments, but the authority and conflict rules still follow the function.

## MyTurn boundary

MyTurn remains the narrow authoritative source for physical item identity, availability, reservation, checkout, return, and condition where those events are recorded there. Essential Capacity may retain an external identifier, import receipt, or reconciliation note. It may not fabricate a checkout, return, reservation, or condition event.

The component register records MyTurn as `wrap`, not `replace` and not `canonical core`. This permits Essential Tools to keep using the system that already works while Manzanita owns the cross-program relationships and a replacement path.

## Essential Minutes

The seed defines one participation unit, the **Essential Minute**. It is:

- issued only after a steward accepts an eligible performed event;
- usable through collective redemption rather than bilateral repayment;
- noncash participation accounting;
- not asserted to be wages, legal tender, an investment, or a fixed monetary value;
- subject to activity eligibility, safeguarding, licensing, and other governing rules.

The pilot deliberately keeps credit issuance and performance acceptance as separate events. A promise, signup, reservation, or self-attestation does not mint credit.

## Component register

`data/component-register-v0.1.json` converts the open-source and commodity sweep into a repeatable procurement discipline. Each candidate receives one disposition:

- `adopt`
- `adapt`
- `wrap`
- `donor`
- `hold`
- `build`

The initial register includes MyTurn, Stripe, ValueFlows, TimeOverflow, CiviCRM / CiviVolunteer, Credit Commons, Hyperswitch, Givebutter, Network for Good, and the thin Manzanita layer. Every entry states what it may remain canonical for, what it may never capture, its current evidence, and the replacement test it must survive.

No TimeOverflow code is incorporated. Its AGPL-3.0 license is treated as an explicit admission gate. The release harvests public workflow patterns and vocabulary without importing a server runtime.

## Local operation

The browser can:

- switch among the five functional seats;
- inspect all eight capacity classes;
- inspect the public-safe offers and needs;
- save additional private-local draft intents;
- walk the seven-state N=1 qualification chain;
- preserve an append-oriented receipt ledger in local storage;
- derive issued, redeemed, and remaining Essential Minutes;
- inspect the component register and replacement boundaries;
- run eight contained qualification checks;
- export the complete state and source snapshots as plain JSON with a SHA-256 digest;
- import a prior packet locally;
- print the current view.

URL parameters preserve the selected view and seat. They do not contain the local ledger or private draft data.

## External-effect boundary

The application has no adapter for:

- MyTurn reservation, checkout, or return;
- email, calendar, messaging, or enrollment;
- Stripe or any other payment processor;
- fundraising publication or donor contact;
- identity verification;
- employment, insurance, law enforcement, or eligibility decisions;
- credit recognition outside the exported local packet.

A named steward must release each outside act in the authoritative source system. The runtime may prepare the action and its evidence packet, but it cannot perform or falsely attest the act.

## Public and sensitive data

The committed seed contains synthetic people only. It does not publish a member list, victim-service case, address, contact details, tool inventory, financial record, or private source bytes.

Real victim-service and other sensitive needs require a private cartridge or packet, minimum disclosure, role-specific access, and an authority decision separate from this public release. Participation data may support access, recognition, continuity, safety, and assistance. It may not silently become punitive scoring, eligibility denial, employment screening, insurance action, or unrelated reputation ranking.

## File ownership

- `index.html` is steward-owned and contains the public-safe seed, component register, and semantic interface.
- `style.css` is steward-owned and contains the responsive and print visual surface.
- `app.js` is steward-owned and contains the local operating state machine.
- `data/capacity-core-v0.1.json` is steward-owned constitutional and seed data.
- `data/component-register-v0.1.json` is steward-owned procurement evidence and disposition data.
- `QUALIFICATION.json` is a frozen release receipt. A changed release cuts a new qualification object rather than silently rewriting the admitted result.
- `scripts/validate.py` is steward-owned and stdlib-only.
- Local browser state and exported packets are operator-owned. They are never committed automatically.

There are no machine-owned files and no scheduled data-refresh workflow in v0.1.0. The repository check workflow only runs the stdlib validator when this tool or its directory entries change.

## Qualification

Run:

```bash
python capacity-commons/scripts/validate.py
```

The validator checks:

- the nine-object core and eight capacity classes;
- unique identifiers and valid references;
- the five functional seats;
- the public-safe synthetic-actor boundary;
- the no-preperformance-credit and adapter-custody policies;
- component dispositions, evidence, and replacement tests;
- exact equality between the committed JSON files and the copies embedded in `index.html`;
- exact local `app.js` and `style.css` references with no third-party runtime dependency;
- the required interface, local persistence, export, import, print, theme, reduced-motion, and 320-pixel hooks.

The admitted candidate browser campaign exercises every seat and state transition, creates a private-local draft intent, completes collective redemption, exports and re-imports the packet, independently verifies its digest, invokes print media, tests reduced motion, and renders at a 320-pixel viewport with 200 percent text. It records zero page-level overflow, zero unexpected external requests, and zero browser errors. The qualification receipt preserves the harness boundary: the exact document was assembled from the committed local files because the execution environment blocks browser navigation, and test-only localStorage and SHA-256 interface shims were used before independent digest verification.

## What can rot

Browser support for localStorage, Web Crypto, Blob downloads, file input, `structuredClone`-equivalent JSON semantics, Content Security Policy, and `history.replaceState` can change. GitHub Pages deployment can change. External evidence URLs, product APIs, pricing, processor relationships, and open-source project status can also change.

Failure must remain visible. The application must never silently issue credit, infer a completed service, claim a MyTurn event, upload a private source, or treat a payment platform as the constitutional record because a browser or vendor capability changed.
