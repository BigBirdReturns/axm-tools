# Clinical Site Fabric

A local, static workbench for reconstructing the operating reality of a multi-protocol clinical research site from de-identified exports and source artifacts.

**Live path after merge:** `https://bigbirdreturns.github.io/axm-tools/clinical-site-fabric/`

## What it does

The tool accepts multiple local files in one browser session. It computes a SHA-256 for every file, parses supported structured formats, normalizes recognized records into a portable site model, preserves unsupported files as hash-only source receipts, and exposes actor-specific projections without sending bytes to a server.

Supported structured inputs:

- CSV or TSV
- JSON
- NDJSON / JSONL
- AXM Exposure-style Markdown certificate reports
- Clinical Site Fabric portable packets exported by this tool

PDF, XLSX, DOCX, images, and other artifacts are still admitted to the source manifest by byte hash, size, media type, and parse status. They are not semantically interpreted. Export them to CSV or JSON for structured ingestion.

## Object contracts

| Object | Required fields |
|---|---|
| `protocols` | `protocol_id`, `sponsor_id`, `version` |
| `participants` | `participant_id`, `protocol_id`, `sponsor_id` |
| `visits` | `visit_id`, `participant_id`, `protocol_id`, `protocol_version`, `scheduled_at` |
| `delegations` | `delegation_id`, `role_id`, `protocol_id`, `action` |
| `resources` | `resource_id`, `type` |
| `bookings` | `booking_id`, `resource_id`, `protocol_id`, `participant_id`, `start_at`, `end_at` |
| `source_events` | `event_id`, `event_type`, `source_identity` |
| `mec6_assessments` | `assessment_id`, `participant_id`, `criterion_id`, `criterion_name`, `status` |
| `model_certificates` | `certificate_id`, `name`, `verdict` |

Common EDC, EHR, and site-export aliases such as `subject_id`, `USUBJID`, `study_id`, `visit_name`, and `event_date` are detected. Unrecognized files open a manual object-type and column-mapping surface instead of being silently discarded.

## Clinical and regulatory boundary

This is a public static demonstration. It is not HIPAA infrastructure, a validated GxP system, an EDC, CTMS, EHR, eTMF, safety database, medical device, or clinical decision-support system. Use synthetic or properly de-identified files only.

The browser may normalize evidence, identify missing joins, expose protocol-version mismatches, detect overlapping resource bookings, evaluate a delegation record, and prepare a portable packet. It cannot create clinical authority, cure a missing source, report an SAE, make an eligibility decision, clear a participant for discontinuation, or write back to any source system.

## GSK and formal-proof boundary

The model-certificate intake deliberately tests the attack surface identified in the GSK / LeanBio work:

1. A model specification is not a proof certificate.
2. A certificate without theorem scope, assumptions, parameter provenance, proof identity, and a model-risk note is refused as incomplete.
3. A valid certificate proves only a model-relative statement under declared assumptions.
4. The certificate remains attached to the model and cannot become patient safety, biological truth, successful taper, or clinical disposition.
5. Open, portable source and proof identities survive the current interface.

The tool accepts the Markdown report format emitted by `axm-exposure` and preserves the distinction between a kernel-checked model statement and a clinical fact.

## GLP-1 exit boundary

The synthetic B-301 case carries the MEC-6 discontinuation work into the site model. The operating distinction is:

```text
coverage / cost / supply / side-effect pressure
≠
clinical readiness to taper or discontinue
```

Weight stability, satiety evidence, lean-mass evidence, resistance training, dose history, and neuropsychiatric screening retain separate evidence classes and states. Missing evidence remains missing. Positive screening creates a hold. The tool never emits `safe_to_stop`.

## Portable export

`clinical-site-fabric/portable-packet@2` contains:

- normalized object tables
- file names, byte sizes, media types, SHA-256 digests, and parse status
- duplicate, orphan, resource, and protocol-version findings
- append-only session receipts
- explicit evidence and authority boundaries

It does not contain original file bytes. The exported packet can be re-imported by another copy of the tool without this session's hidden state.

## Samples

The `samples/` directory contains a complete synthetic site:

- two sponsors
- three protocols, including first-in-human oncology, single-arm accelerated-approval support, and GLP-1 discontinuation
- six participants
- a protocol amendment
- a stale delegation
- an SAE follow-up clock
- a missing lab kit
- a cross-protocol coordinator collision
- a six-criterion MEC-6 assessment
- a model-relative exposure certificate

## Validation

Run:

```bash
python clinical-site-fabric/tests/validate.py
```

For a browser self-test, serve the repository root and open:

```text
clinical-site-fabric/?selftest=1
```

The page sets `body[data-selftest="pass"]` only when all twelve synthetic admission cells pass.

## What can rot

- Browser File API and Web Crypto behavior.
- Header aliases used by outside exports.
- New versions of EHR, EDC, CTMS, and sponsor export layouts.
- The Markdown shape emitted by `axm-exposure`.

Rot must be visible as an unparsed source, mapping request, or failed admission cell. Silent inference is prohibited.

## Ownership

- `index.html`: steward-owned executable surface.
- `samples/`: frozen synthetic source fixtures for v0.2.0.
- `tests/validate.py`: steward-owned static and fixture validator.
- `QUALIFICATION.json`: generated qualification receipt for the released tree.

No file in this tool is machine-owned at runtime. Imported files live only in browser memory for the current session.
