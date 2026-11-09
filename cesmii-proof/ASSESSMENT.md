# CESMII × AXM: adversarial fit assessment

Assessment date: 9 November 2026. Evidence: public primary sources and the bounded execution receipts in this directory. This is an independent AXM assessment, not an institutional evaluation of CESMII personnel. Private correspondence and unsupported allegations are excluded.

## The usable conclusion

The shortest test connects a known i3X object to a source-bound decision, changes one declared business input, and transfers the complete calculation to another operator. The strongest initial fit is maintenance and spare-part readiness because the official API demo contains pump-101 and the existing AXM Team Commons source already joins maintenance, inventory and allocation. This reduces new integration work while preserving an observable result: zero issuable parts becomes one after an explicit allocation correction, and a separate client can recompute both conclusions.

The public API capture supplies object existence, relationships, state quality and retained observation context. It does not supply the synthetic stock quantities or work order. The binding is declared explicitly. This proves a read-only application integration and a reproducible calculation, not a plant intervention or a productivity improvement.

## What they already own

CESMII's technology architecture combines Smart Manufacturing Profiles, contextual interoperability platforms and a common API. Its ProveIt demonstration already joined vendor systems and an external client. The specification includes discovery, current and historical queries, update operations and subscriptions, with required versus optional features. The conformance harness checks that contract. Describing CESMII as lacking working interoperability, writes, recovery or testing would therefore be false or materially incomplete.

Primary sources: [technology architecture](https://www.cesmii.org/technology/), [ProveIt recap](https://www.cesmii.org/prove-it-recap/), [normative i3X 1.0 implementation guide](https://github.com/cesmii/i3X/blob/1.0/spec/IMPLEMENTATION_GUIDE.md), [conformance harness](https://conformance.i3x.dev/), [developer FAQ](https://sdk.i3x.dev/faq/).

The API standardizes contextualized information access. A particular platform may also implement workflows, audit records, identities and provenance. Those capabilities must be inspected in that implementation; their absence from the common interface is not proof that the vendor lacks them.

## Where the overlap becomes testable

| Boundary | CESMII / i3X responsibility | AXM proof in this release | Condition that would defeat the proposed distinction |
|---|---|---|---|
| Meaning and context | Types, namespaces, object identity and relationships | Preserve the exact selected API responses and explicit synthetic asset mapping | The mapping cannot be defended, or an object from the wrong namespace is silently treated as equivalent |
| Available information | Current/history queries and quality signals | A retained public read-only capture; missing production values stay unknown | A missing, partial or uncertain required context still produces a complete conclusion |
| Decision lineage | Application-specific; the API does not prescribe the business recipe | Exact contribution inputs, correction predecessor, historical result and recomputation | A changed source can leave a false saved conclusion accepted |
| Workflow continuity | Subscription sync recovers data within the server's documented limits | A separate browser replays the recorded business calculation from an exported capsule | Replay depends on the original chat, operator, application account or hidden source |
| Operational authority | Production security and the platform's controls | No operational authority is claimed or exercised | A local declaration or hash is treated as authorization to operate equipment |
| Commercial value | Adoption and measurable manufacturing results | Unmeasured | Existing tools already deliver equivalent independent handoff at lower total adoption cost |

## The objections worth preparing for

**“Our platform already has history and an audit trail.”** That is plausible. A vendor comparison must test portability, dependency completeness and independent replay, rather than compare feature labels. A result that reconstructs only inside the originating product does not establish the same property as a runnable, evidence-complete export. Conversely, an existing independently replayable export could substantially narrow AXM's incremental value. No competitive benchmark has been run here.

**“This is just a small synthetic calculation.”** Correct as to scope. The chosen arithmetic isolates evidence composition, correction and custody so failures remain easy to see. It does not qualify root-cause diagnosis, predictive maintenance, scheduling optimization or industrial AI. The next data set must belong to the receiving organization, with acceptance fixed before execution.

**“A successful query does not prove the pump's physical state.”** Correct. The official demo explicitly excludes production suitability. Its quality flag is a server-supplied assertion, and a saved capture is historical evidence. The lab does not infer operating safety from a numerical value or introduce a control threshold.

**“Hashes do not prove who approved the work.”** Correct. This release binds bytes and computation source. It uses synthetic role labels, not authenticated identities or legal approvals. A recipient needs an external trust anchor and actual access/release controls for a production claim.

**“i3X already supports writes and reconnect.”** Correct. The added claim is retention of the application decision and its evidence across handoff. This release deliberately performs no API writes or subscription creation. It neither replaces the standard's recovery semantics nor certifies them.

**“Why should we adopt another platform?”** This release is a self-contained client/reference application, not a new service dependency. It has no login, runtime model call, telemetry or paid API. The source archive and offline page let CESMII's technical team inspect or discard the implementation while retaining the experiment.

## Evidence-weighted test order

The displayed numerical heat map is analyst prioritization on a declared scale, not measured business value. The following ledger states the actual implementation levels.

| Workflow | Official API connection | Business inputs | Correction computation | Fresh-client handoff | Production outcome |
|---|---|---|---|---|---|
| Pump repair and spare readiness | One public reference endpoint captured | Three synthetic contributors | Explicit predecessor and stale-result handling tested | Actual downloaded capsule imported and recomputed | Unmeasured |
| Supplier allocation | Not connected | Synthetic quantity fixture | Balance recipe tested | General mechanism exists; this scenario's transfer not exercised | Unmeasured |
| Quality review | Not connected | Synthetic checklist counts | Completion recipe tested | Not exercised for this scenario | Unmeasured |
| Energy per good unit | Not connected | Synthetic numerator and denominator | Ratio correction tested | Not exercised for this scenario | Unmeasured |
| Shift handover | Not connected | Synthetic declared task counts | Completion recipe tested | Not exercised for this scenario | Unmeasured |
| Application change review | Not connected | Synthetic declared checks | Completion recipe tested | Not a deployment pipeline qualification | Unmeasured |
| Second spare-part case | Not connected | New synthetic quantities | Balance recipe tested | No second vendor endpoint tested | Unmeasured |

Published CESMII project areas establish relevance, not an order, a buyer commitment or demand for AXM: [project portfolio](https://www.cesmii.org/projects/). The [Smart Manufacturing Catalog](https://catalog.cesmii.net/) provides the customer-facing distribution pattern: products, demonstrations and developer resources aligned with the three imperatives.

## Decision ownership and acceptance

The executive conversation concerns whether portable decisions improve adoption, retention of capability and manufacturing outcomes. The technical conversation concerns object/model mapping, quality, conformance, evidence release and the smallest controlled integration. The public roles of [John Dyck](https://www.cesmii.org/about/meet-the-team/john-dyck/) and [Jonathan Wise](https://www.cesmii.org/about/meet-the-team/jonathan-wise/) make those relevant review perspectives, not promises of sponsorship.

A receiving team can falsify this release without accepting AXM's broader thesis: run the tests, alter a source, try a rehashed false conclusion, export the record, and replay it in a clean offline client. Production acceptance remains a separate decision with customer-owned data, policy, authority and outcome measurements.
