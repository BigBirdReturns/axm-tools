# Incident Commons threat model and operational boundaries

Version 0.1, November 16, 2026. Reference framework: NIST SP 800-61 Revision 3 and CISA incident response playbooks.

## Trusted and untrusted actors

- **Organization incident owner:** controls collection authority, permitted sources, access to the incident, disclosure, responder roles and actual containment.
- **Local runtime:** operates on the organization's selected host. The static browser has no remote data submission and no account. The Python pipeline makes no network calls. Optional local model traffic goes only to a literal loopback HTTP endpoint chosen by the operator.
- **Source events:** untrusted, potentially attacker-controlled. IP addresses, log actors, timestamps and even vendor success flags need corroboration; logs may be altered or missing.
- **LLM output:** untrusted hypotheses, even when valid JSON and citing real event IDs. A citation to an event establishes traceability, not semantic correctness or causation.
- **Public hosting:** serves static HTML/JS/CSS and synthetic examples only. It does not receive selected files. Browser extension access, local malware and client runtime integrity remain outside this package's control.

## Attacker objectives and mitigations

| Threat | Current mechanism | Remaining gap |
| --- | --- | --- |
| Prompt injection embedded in alerts | Notes treated as data; DOM uses textContent; local model lane strips raw note fields; model has no action route | Model may still infer poorly from misleading summaries |
| Forged event IDs or duplicate evidence | Strict schema, duplicate refusal, exact case/event references, SHA-256 source binding | Source bytes may themselves be forged; independent trust requires authenticated logs |
| Source omission or manipulated time | Explicit volume limits, timestamp grammar and unsupported-event counts; no negative conclusion from missing signals | No cryptographically authenticated source-completeness proof |
| Cross-tenant contamination | Correlators partition by declared tenant; tenant field checked | An attacker who controls upstream tenant labeling may forge scope |
| Correlation misread as attribution | Findings explicitly mark hypothesis, source IDs and alternative explanation; no automated declaration | Human review and corroborating telemetry required |
| LLM hallucinated evidence | JSON output schema validation and exact event-ID membership | True IDs can still be cited in logically false conclusions |
| Sensitive customer data exfiltrated to model | Loopback-only OpenAI-compatible endpoint; minimized event context; no remote URL accepted | Local model host operator can still inspect prompt; secure that host |
| Source data leaked through sharing | Aggregate-only preview excludes actors, IPs, events, targets, notes and raw source | Counts and case metadata can still be sensitive; human disclosure review |
| Unapproved production containment | No credentials or mutation API; exported request explicitly NOT_AUTHORIZED and NEVER_EXECUTED | External organization must separately authenticate and authorize and observe effects |
| Case tampering | Canonical case fingerprint plus complete referenced-event validation | Unsigned hash alone is not chain-of-custody; seal through AXM Genesis under owner-held key |
| Tool/supply-chain poisoning | Stdlib Python, static JS, no external CDN, no runtime package installation, source integrity and CI checks | Operating-system, browser, GitHub Actions and developer-machine trust remain external |
| Replay and duplicate effects | This package issues no effects; requests cannot cause actions | Actual executor must have idempotency keys, short leases and observed postconditions |
| Incident response delayed by model failure | Deterministic rules remain fully functional without an LLM | Detection quality is bounded by known rules and available telemetry |

## Acceptance tiers

1. **SOURCE:** Browser accepts bounded synthetic JSONL/JSON; Python validates shape, timestamps, IDs, tenants and source hash.
2. **CORRELATION:** Detects configured multi-step identity/export patterns and keeps cross-tenant events separate. No configured detection is not proof of safety.
3. **PROVENANCE:** Case hash/links verified; vendor normalization records original and mapped hashes. Independent signature and authenticated source evidence require external AXM Genesis operation.
4. **CANDIDATE HYPOTHESES:** Optional local LLM returns bounded JSON with existing event IDs, alternatives and falsification checks. It receives no remote tool capability.
5. **HUMAN RESPONSE:** A user can prepare a scoped review-only request with evidence and rationale. Actual organizational approver authentication and action execution are outside this demo.
6. **PRODUCTION:** Requires controlled ingestion, lawful authority, SIEM/EDR integrations, IAM and audit controls, signed evidence custody, secrets handling, asset inventory, escalation contacts, on-call staffing, privacy and response testing.
7. **CLOSED:** No claim of closure until an organization's real operational record proves containment effects, eradication, recovery and sustained absence of the detected behavior.

## Local model prompts

The local model system prompt explicitly treats supplied event descriptions as untrusted. It may make mistakes. The output validator:
- limits number and length of hypotheses;
- requires exact existing evidence IDs;
- requires alternative explanation and next check;
- forbids declaring automated authority through an output field;
- rejects non-JSON and nonconforming outputs.

This is a containment-by-interface design, not a proof of prompt-injection immunity.

## Privacy and consent

Never upload another organization's private incident evidence without its controller's authority. In this release, no raw user data is collected by the host. Do not confuse a public-safe synthetic demonstration with permission to process or publish real victim data. Browser exports and CLI outputs go to destinations selected by the local operator. They are not transmitted to Sonya Huang, Sequoia, or any other third party.

## Known bugs and unqualified work

- This release does not scrape live telemetry or implement real-time streaming correlation, behavioral baselines, endpoint forensics or malware reverse engineering.
- Source-event completeness, clock skew, cross-source joining, identity device binding and attacker attribution require organization-specific sensors.
- Browser rule engine is a human-readable preview. Python runner is the independently verified normative case analysis.
- No field qualification of incident detection rates, false positives, false negatives, full browser accessibility or legal admissibility is claimed.
- No automatic endpoint isolation, credential rotation, domain blocking, account deactivation, deletion, customer notification, ransom handling or incident declaration exists.
- No secrets, private AXM/MARY code or Estate authority are redistributed.
