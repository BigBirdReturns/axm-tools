# AXM × i3X application and technical review
Prepared 19 November 2026. Producer: Jonathan Sandhu, AXM, [jvssandhu@gmail.com](mailto:jvssandhu@gmail.com).

## Start here

The [member workbench](../workbench/) combines retained i3X observations with an explicitly defined operational workflow. A team supplies source records and rules, evaluates them, retains corrections and exports a capsule that another client can independently recompute. The [complete review kit](https://bigbirdreturns.github.io/axm-tools/cesmii-proof/cesmii-member-kit.zip) includes applications, source, setup, sample inputs and verification evidence. The [recording](demo.mp4), [captions](demo.vtt) and [transcript](transcript.html) support an architecture review.

The package contains three executable applications:

| Application | Purpose | Entry and source |
| --- | --- | --- |
| Member workbench | Operator-defined sources and arithmetic checks, selectable i3X context, correction history, portable decision capsules | [Browser](../workbench/), [offline client](../workbench/offline.html), [implementation](../workbench/core.js) |
| Industrial Continuity | Six-source product-mix and maintenance planning; CSV intake; source and review staleness; offline historical replay | [Browser](../../industrial-continuity/), [offline client](../../industrial-continuity/offline.html), [operating guide](../../industrial-continuity/README.md) |
| Original i3X reference lab | Preserved public pump demonstration, three synthetic team records and independently replayable original/corrected conclusions | [Browser](../), [offline client](../offline.html), [source and provenance](../README.md) |

Each application retains its own engine and input contract. A capsule belongs to the application and engine version that created it; the complete package provides the corresponding receiver.

## 1. What the system does

The application makes a calculation's dependencies portable. It retains the inputs, their provenance labels, the explicit calculation and the result at each revision. When a contributor changes a source, the previous decision remains available and loses current standing. Evaluation produces a successor against the new evidence frontier. A recipient imports the exported capsule and reconstructs the retained results from the original inputs instead of accepting a stored result on trust.

This addresses a practical handoff: maintenance, inventory, planning and a receiving reviewer can refer to the same decision while preserving which source versions actually supported it. The receiving party can inspect the calculation with an offline browser and the included source. The member workbench includes editable maintenance, energy-intensity and batch-review examples, plus the five-source maintenance template in this guide.

## 2. Architecture

### Source adapter

An operator explicitly selects an i3X endpoint and asset. The adapter performs discovery and read queries, retaining the endpoint, method, request, response status, exact response body, observation timestamp and SHA-256 digest. The asset and selected value IDs remain explicit. A separately captured JSON file follows the same review path as a direct browser capture.

The retained original reference capture contains five discovery GET responses and three read-query POST responses for the public pump exercise. The delivered collector accepts a selected asset and value IDs while preserving the reference defaults; it can omit history when that record is unnecessary. Read-query POST requests retrieve observations and differ from server mutation routes. The delivered application issues no equipment commands or production writes.

A browser reading a locally configured endpoint must satisfy that server's CORS and browser transport rules. Running the workbench from a local HTTP server beside the local i3X instance avoids relying on an HTTPS page reaching an insecure remote host. Importing a previously saved capture provides a browser-independent route.

Context completeness requires a discovered mapped asset, successful read responses, the declared i3X 1.0 version and dated, non-null values with Good quality. Each selected value must be the asset itself, a retained non-parent relationship target or a discovered descendant of that asset or target. A Good value from an unrelated object remains incomplete context.

### Workflow contract

The member workbench accepts `axm-member-workflow/1`. The workflow identifies a decision, an asset mapping, an evidence class, its source records, a context requirement, an optional freshness limit and the rules to evaluate. A source carries a stable ID, descriptive label, declared owner, observation time, values and a note. The complete workflow definition is inspectable as JSON.

The current contract supports 1–24 sources, up to 32 scalar fields per source and 1–32 rules. Retained history accepts up to 1,000 source revisions, 64 captures and 500 decisions or review declarations; export preserves the completed record when those limits are reached. Rules contain data expressions, not executable scripts. Supported numeric operations are addition, subtraction, multiplication, division, minimum and maximum. Comparisons are greater-than-or-equal, less-than-or-equal, equal, not-equal, greater-than and less-than. A source reference names the source and field explicitly; scalar literals are direct values. Source fields accept finite numbers, strings, booleans or null. Missing values remain unknown.

The default example connects three business inputs: serviceable stock, already allocated stock and maintenance requirement. The review template adds maintenance duration, its planning window and a declared procedure condition. Member workflows can use different source IDs and rules within the same declared contract.

### Evaluation and correction

Evaluation binds a result to its workflow, selected context and current source revisions. Each correction retains its predecessor rather than replacing the original source. Current standing is a dependency relationship: the evaluated frontier must match the current input frontier.

The member workbench exposes these result classes:

| Result | Meaning |
| --- | --- |
| `SUPPORTED_ON_RECORD` | Every defined comparison evaluates true |
| `NOT_SUPPORTED_ON_RECORD` | At least one comparison is false and no comparison remains unknown |
| `INCONCLUSIVE_ON_RECORD` | At least one rule has missing, invalid or unresolved input |
| `INCONCLUSIVE_CONTEXT` | Required i3X context is absent or incomplete |
| `INCONCLUSIVE_FRESHNESS` | An observation falls outside the declared freshness window |

All decisions retain `action: REVIEW_ONLY` and `production_authority: false`. A supported parts calculation describes supplied records; it is not a maintenance-release instruction.

A workflow with `max_age_hours: null` deliberately uses retained snapshots without asserting current plant freshness. A finite maximum age checks the source observation times, the capture time and the selected i3X value timestamps. A recent capture therefore preserves an old value's actual age. The decision retains its evaluation time, and historical replay uses that same time so it can reproduce the original judgment. Re-evaluate for a new time-sensitive decision. Source timestamps remain observations; rebuilding or exporting a package does not silently make them newer.

### Export and receiving client

The exported capsule retains the workflow, context, source lineage, historical decisions and declared reviews with their engine identity. A review attaches to one exact decision and retains that relationship after later corrections. The receiver verifies the internal digests and input contract, resolves the exact retained dependencies and recomputes the conclusions. It also reconstructs the current or stale standing from the history.

The browser saves separate workspaces in local storage and verifies them when reopened. Export a capsule before clearing that storage or moving to another device. A visible storage error leaves the active in-memory workspace available to export.

The independent command-line receiver derives the engine identity from the actual installed `core.js` bytes, a newline and `commons-core.js` bytes. From the repository or extracted package root, verify a received capsule with:

```sh
node cesmii-proof/workbench/verify-capsule.cjs received-handoff.json
```

A successful run reports the workflow, source revisions, captures, recomputed decision count, declared reviews, latest result and current standing. An integrity or semantic mismatch exits nonzero.

This semantic replay matters because a fabricated saved answer can be rehashed. Checking the outer file digest alone would accept that file's internal byte consistency. Recomputing the answer from its retained inputs detects a saved conclusion that conflicts with those inputs. The included source lets a recipient inspect and run the verification independently.

## 3. A concrete de-identified member workflow

“De-identified member workflow” means an ordinary decision record whose business relationships survive removal of unnecessary identifying information. It does not require a plant-wide data export. A suitable example contains Equipment-A, WorkOrder-A, Part-A, the relevant stock and maintenance records, one correction and the receiving team's replay.

The [editable template](member-workflow-template.json) is synthetic and importable. Its asset mapping uses the public reference object's `pump-101` ID while displaying the alias Equipment-A.

| Source ID | Included values | Initial example |
| --- | --- | --- |
| `inventory` | `serviceable` | 2 recorded usable parts |
| `allocation` | `allocated` | 2 parts already committed |
| `maintenance` | `required`, `duration_hours` | 1 required part; 2 planned hours |
| `capacity` | `planning_window_hours` | 4 available planning hours |
| `procedure` | `planning_allowed` | 1, a declared permission to perform this planning calculation |

The three comparisons establish whether unallocated serviceable stock meets the task requirement, whether the planned duration fits the window and whether the supplied procedure condition permits planning. Initially, `2 - 2 >= 1` is false. A correction of allocated stock from 2 to 1 makes `2 - 1 >= 1` true while preserving the original result and its supporting records.

For a member contribution, replace the example values and labels with the organization's chosen record, set `evidence_class` to `member-deidentified`, and select the actual asset ID within the authorized capture. `operator-provided` is available for other supplied records. Preserve units, source times and the relationships among the aliases. Keep any private alias lookup in the organization's custody.

Customer names, personnel names, email addresses, site addresses and credentials are unnecessary for the example. A consistent alias preserves a relationship; removing the relationship would change the calculation. A missing quantity should remain null or absent and produce an unknown result, not become an invented zero.

Importing a workflow creates a new review context. To revise evidence in an existing review, change the source through the workbench's source editor so its predecessor and affected decisions remain retained. Export the current capsule before starting a separate workflow when you need to retain both.

## 4. Browser walkthrough

1. Open the member workbench from the hosted URL or the downloaded local package. Load the included example or import `member-workflow-template.json`.
2. Inspect the asset mapping. Select the retained reference capture, import a capture JSON file, or explicitly read your chosen i3X endpoint.
3. Evaluate the workflow. Inspect the result of each rule and the source fields used to calculate it.
4. Change the allocation value from 2 to 1 and save that source correction. Inspect the prior decision's stale standing before evaluating the successor.
5. Evaluate again and compare the earlier and current decision. The first decision and original allocation remain part of the retained history.
6. Export the capsule. Open the offline workbench in a clean browser context, import the file and inspect the reconstructed decision history.
7. Change a required value to null in a separate review and evaluate. Verify that an unknown input produces an inconclusive result.
8. Use a workflow with a finite freshness limit when the selected decision requires current observations. Inspect how an expired record changes the result.

The multi-file application runs from HTTPS or localhost. For a downloaded repository or extracted kit, serve the directory containing `cesmii-proof` and `industrial-continuity`:

```sh
python -m http.server 8080 --bind 127.0.0.1
```

Open `http://127.0.0.1:8080/cesmii-proof/review/`. The single-file offline clients also travel with the complete kit. Actual local values belong in local exports, not in a public source checkout.

## 5. Second i3X server

The [second-server instructions](../second-server/README.md) and [execution evidence](../second-server/evidence.json) identify the exact setup and observed result. The upstream source is CESMII's [i3X demo server](https://github.com/cesmii/i3X/tree/1.0/demo/server), pinned at commit `9ffc352470b9807a0143cd5c43f9680cb5779550`.

The official FastAPI application runs as a separate loopback instance with an explicit port and configuration. The observed direct-server route uses an upstream-supported uvicorn launch; it preserves the official application source. Use the delivered setup helper and its instructions for exact interpreter, dependency and configuration paths.

From the `cesmii-proof/second-server` directory, `python setup.py --work-dir NEW_EXTERNAL_DIR --run` verifies and extracts the bundled upstream source, creates an isolated environment, installs the official requirements and starts the server. Choose a new work directory outside the extracted review package. In a second terminal, `python verify.py --server-source NEW_EXTERNAL_DIR/i3X --out NEW_EVIDENCE_DIR` reproduces the integration and retains a new evidence directory. The linked instructions provide complete Windows and Linux/macOS examples.

The retained official-suite run reports `1.0 Compatible`: 52 passed, 0 failed, 2 advisory warnings and 6 skipped. The warnings identify the loopback development server's HTTP transport and unauthenticated data access. Current-value write tests were disabled; the suite still created and removed test subscriptions and probed unsupported historical updates. The full report preserves that scope. These are observed local-server results.

A typical member capture after server setup is:

```sh
python cesmii-proof/capture.py \
  --base-url http://127.0.0.1:8381/v1 \
  --asset-id pump-101 \
  --value-id pump-101-state \
  --no-history \
  --synthetic-data \
  --out new-local-capture.json
```

Choose a new output filename for each observation. Import the resulting capture in the member workbench and inspect the endpoint and observation identity before evaluation. The package also retains captures from the local pump and tank objects and the relevant source provenance. The tank's `MonitoredBy` relationship binds `tank-201` to `sensor-001`; the tank object itself has a null value with `GoodNoData` quality and remains a negative case. The local example uses official simulated data, which the collector marks explicitly.

A second running instance establishes behavior against distinct server state and a separate capture. Both reference servers use the CESMII implementation. Cross-vendor interoperability is an additional experiment with another implementation and its actual model; the application keeps the selected IDs and assumptions explicit for that purpose.

## 6. Industrial Continuity

[Industrial Continuity](../../industrial-continuity/) is included as an implemented business-context example with its own source, tests and receiver. It accepts six exact CSV mappings:

| Source | CSV fields |
| --- | --- |
| Orders | `sku,demand_units,contribution_usd_per_unit` |
| Routing | `sku,mix_min_per_unit,pack_min_per_unit` |
| Capacity | `stage,available_min` |
| Maintenance | `job,part,serviceable,allocated,recovery_mix_min,repair_cost_usd,expedite_cost_usd,supplier_lead_hours,decision_window_hours` |
| Quality | `sku,released` |
| Procedure | `procedure,revision,planning_allowed,review_role` |

The calculation exhaustively compares integer quantities of products A and B through mixing and packaging capacity. The initial synthetic record selects A80/B35 and $5,650 planned net contribution after a $150 maintenance cost. Its no-intervention comparison is $4,975, producing $675 modeled incremental value under those same assumptions.

Change the customer mix so B's contribution rises from $40 to $120 per unit. The retained old decision and review become stale. Re-evaluation chooses A30/B60 within existing capacity, worth $8,850 on the revised record. Additional mixing capacity produces no better product mix and consumes the $150 intervention cost. The $3,200 difference between scenario totals reflects a changed economic assumption, not measured AXM-created revenue.

The other included challenges allocate the last spare, impose a quality hold or remove a capacity value. Local CSV import uses the displayed headers and preserves an operator-supplied evidence class. A reviewer label records a declared review against an exact decision. It authenticates no person.

From the repository root, the application provides:

```sh
node industrial-continuity/tests/verify.cjs
node industrial-continuity/verify-handoff.cjs industrial-continuity/data/example-handoff.json
```

The independent CLI derives the engine identity from actual engine and donor bytes, then recomputes the decisions and review relationships. A failed browser import preserves the current accepted workspace.

## 7. Evidence, provenance and limits

The [workbench build metadata](../workbench/build-meta.json), [workbench qualification](../workbench/qualification.json), [second-server evidence](../second-server/evidence.json), [original reference qualification](../data/qualification.json) and Industrial Continuity source provide the execution record. Test counts belong to their specific engine and run. Earlier reference-lab tests do not qualify a later member-workbench revision.

The original lab and Industrial Continuity retain copied, hashed Team Commons code; no runtime import from a sibling tool is required. The member workbench carries its own source and identity. The complete package preserves the source for all included receivers.

The trust boundary is explicit: hashes and replay establish consistency of the provided record under the included engine. The contributing organization supplies source authenticity, physical truth, user identity, authorization and operational freshness requirements. The public examples use reference data and synthetic business inputs. A self-consistent fabricated source remains a fabricated source; replay does not convert it into physical evidence. The application sends no equipment commands.

The package supports CESMII's technical review and supplies publication assets. CESMII's technical assessment, conformance decisions and publication remain their own activities.

## 8. Publication and contact

The [review page](index.html) links the complete application, downloadable package, architecture guide, workflow template, recording, captions and transcript. It identifies the producer as:

Jonathan Sandhu  
AXM  
[jvssandhu@gmail.com](mailto:jvssandhu@gmail.com)  
[AXM Tools](https://bigbirdreturns.github.io/axm-tools/)

The hosted and downloadable applications are available for use, with source included for inspection and reproducibility. The repository carries no blanket software license. Contact the producer for distribution or integration terms.

## Source map

| File or area | Role |
| --- | --- |
| `workbench/core.js` | Workflow contract, calculation, source lineage and capsule verification |
| `workbench/index.html` and accompanying UI files | Member-facing workflow and evidence interface |
| `capture.py` | Explicit read-only i3X collection |
| `workbench/offline.html` | Downloadable receiver and workbench |
| `workbench/verify-capsule.cjs` | Independent Node receiver using actual installed engine bytes |
| `workbench/build-meta.json` | Engine identity and build provenance |
| `second-server/` | Reproducible official server setup, captures and observed evidence |
| `engine.js`, `commons-core.js`, `data/capture.json` | Preserved original reference-lab calculation and retained observation |
| `industrial-continuity/engine.js` | Six-source planning, corrections and review standing |
| `industrial-continuity/verify-handoff.cjs` | Independent Node replay using actual source bytes |
| `review/` | Public review guide, template, recording, captions and producer contact |

The review guide, page and template are steward-owned source. Generated media, build metadata and qualification records retain their own source identities and execution provenance.
