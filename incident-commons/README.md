# Incident Commons: deploy your own AI-native incident-response desk

**Local-first. Evidence before inference. Every change needs actual authority. Free software, Apache-2.0.**

Public browser desk: https://bigbirdreturns.github.io/axm-tools/incident-commons/  
Source: https://github.com/BigBirdReturns/axm-tools/tree/main/incident-commons

Incident Commons gives an organization a usable first-response workbench without a vendor account, source-code subscription or hosted AI. It responds to the November 16, 2026 discussion about whether conventional incident-response firms can keep up with changing AI-assisted attacks. It offers a defender-owned evidence and decision system. It is not a claim to operate a 24/7 DFIR service, to contain other organizations' incidents, or to replace Mandiant.

## The operational workflow

    OWNED EVENT EXPORTS
       |
       v
    Normalize vendor source + retain original SHA-256
       |
       v
    Deterministic correlations + explicit non-matches
       |
       v
    Evidence-addressed case + integrity verification
       |
       +-- optional LOCAL AI -> falsifiable hypotheses only
       |
       v
    Human incident commander + organizational approval
       |
       v
    Scoped containment request (not executed by this kit)
       |
       v
    Separately authorized IAM / EDR / SIEM action
       |
       v
    Independent outcome, recovery, corrected playbook

This separation follows the roles, authorities, detection, response, and recovery emphasis in [NIST SP 800-61r3](https://csrc.nist.gov/pubs/sp/800/61/r3/final), finalized April 2025. The [CISA federal IR playbooks](https://www.cisa.gov/resources-tools/resources/federal-government-cybersecurity-incident-and-vulnerability-response-playbooks) provide examples of operational process. This code is not an agency compliance certification.

## What is shipped

| Surface | Source | Observed proof |
| --- | --- | --- |
| Local-only browser desk | [index.html](index.html), [app.js](app.js), [style.css](style.css) | 13 synthetic events, five supported signals, tenant isolation, redacted share-preview export |
| Offline case analysis | [incident.py](incident.py) | Byte-level source SHA-256, evidence-addressed findings, fail-closed import, case export and verification |
| Vendor log normalization | [adapters.py](adapters.py) | Offline AWS CloudTrail and Microsoft Entra sign-in formats, mapping receipts and unmapped-event counts |
| Optional local AI hypotheses | [local_ai.py](local_ai.py) | Loopback-only model endpoint, minimized context, exact event-ID citations, no execution authority |
| Containment review | Browser desk | A request records scoped target, accountable person, evidence and rationale; never executes |
| Threat model and checks | [THREAT_MODEL.md](docs/THREAT_MODEL.md), [ACCEPTANCE.json](evidence/ACCEPTANCE.json) | 28 native Python tests plus JavaScript engine tests; no cloud runtime |

## Run a complete synthetic investigation

Open the [live desk](https://bigbirdreturns.github.io/axm-tools/incident-commons/) and choose **Investigate synthetic breach**. Inspect the simulated password-spray attempt, suspicious successful login, subsequent identity changes, token issuance, secret access, large export, and untrusted prompt-injection content. Every finding links to precise event IDs. You may also choose a local JSONL or JSON export of your own.

Raw selected events stay in your browser. Private-case export includes those events; aggregate-only sharing excludes actors, IPs, event IDs, targets and raw source text. A browser preview is not an independently authenticated evidence record. Use the Python runner below to verify byte-level identity.

## Run completely offline with Python

Python 3.10+, standard library only, no registration, package install, API token or network call.

    cd incident-commons
    python incident.py analyze examples/synthetic-identity-export.jsonl --case-id SYNTH-001 --out case.json
    python incident.py verify case.json
    python incident.py share case.json --out share-preview.json

The source_sha256 field binds exact input bytes. The verify command checks complete case integrity and whether each finding cites actual event IDs. A hash is not an independent signature or evidence custody chain. Reuse [AXM Genesis](https://github.com/BigBirdReturns/axm-genesis) for externally trusted signed provenance.

## Import real vendor log exports without cloud access

CloudTrail: supply a locally exported JSON array or a Records array. Explicit mappings cover ConsoleLogin, CreateAccessKey, DisableMFADevice, role-policy changes and GetSecretValue. Unmapped actions are counted rather than assigned invented semantics.

    python adapters.py aws-cloudtrail cloudtrail-export.json --tenant organization-a --out converted.jsonl --receipt mapping-receipt.json
    python incident.py analyze converted.jsonl --case-id IR-001 --out case.json

Microsoft Entra: exported sign-in records in a JSON list or value array. Inputs must include ID, timestamp, principal, IP address, status.errorCode and an optional destination resource.

    python adapters.py entra-signin entra-export.json --tenant organization-a --out converted.jsonl --receipt mapping-receipt.json

Retain the original export under organizational custody. Mapping receipts bind original and normalized byte hashes with mapped/skipped counts. No endpoint credentials or cloud API calls are used. A live SIEM/EDR integration remains an organization-specific deployment adapter, not something silently asserted by this kit.

## Optional AI-native hypothesis lane, locally hosted

The optional local model is an analyst, not an incident commander. It sees minimized event kinds, IDs, times, finding summaries and outcomes, without raw external notes, account identifiers, IPs or sensitive target names. It must cite existing event IDs, name an alternative explanation and propose a falsifiable next check. Unsupported citations and malformed JSON are refused.

    python local_ai.py case.json --url http://127.0.0.1:11434 --model YOUR_LOCAL_MODEL --out hypotheses.json

Requires a user-operated OpenAI-compatible chat completions API on loopback (for example local Ollama or vLLM). The model receives no directory, IAM, cloud or EDR credentials and cannot execute containment. Network endpoints other than loopback are rejected.

## Reproduce acceptance

    python -m unittest discover -s tests -v
    node tests/test_browser.cjs
    node --check app.js

At release qualification, 28/28 Python tests and the Node/browser-engine parity checks passed. These establish deterministic software-contract behavior on synthetic and simulated vendor events. They do not demonstrate production detection coverage, continuous telemetry, a full-browser visual playthrough, DFIR staffing, incident confirmation, legal evidence admissibility or an enterprise incident-response SLA. Inspect the [acceptance record](evidence/ACCEPTANCE.json).

## AXM and Estate integration

The release preserves the working boundaries of the existing system. AXM Genesis signs and verifies evidence when a legitimate source owner provides authorized artifacts. AXM Witness/Embodied addresses validated witness and physical provenance. CAIRN/APERTURE patterns address constrained admission and working sets. TierDesk Estate and MARY inform bounded execution, durable jobs and recoverability, without exporting their private control planes or unlicensed MARY source. Cantos can measure costs, evidence use and corrected outcomes. All integration remains explicit and independently qualified; these tools are not represented as preinstalled in a visitor's browser.

## Security boundaries

Novel attacks can fall outside configured rules. No finding is not an all-clear. Even a CRITICAL correlation does not prove attribution, malicious intent or unauthorized export. This package cannot disable an account, isolate a host, revoke a token, contact a victim, or execute a command against an external system. Organizational IAM, independent authorization, containment execution, incident counsel, communication and recovery remain with the affected organization.

Apache-2.0 for the new code. No license/subscription charges for this release; hardware, storage, monitoring, staff, incident counsel and external response services still cost money. No private user data, credentials, model weights or nonredistributable AXM code are included. The release is independent of Sonya Huang, Sequoia, Mandiant, Google, and any real-world incident victim.
