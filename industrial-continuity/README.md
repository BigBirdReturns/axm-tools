# Industrial Continuity 0.1.0

A working AXM integration proof for the boundary between operational flow, factory workflows and evidence-complete decision handoff. Public ThroughPut and OpsMate materials inform the interaction model; Rick Bullotta's published process-context discussion informs the selected test. This is an independent implementation with synthetic operational data, not a vendor integration or endorsement.

## Run the actual demonstration

Open `offline.html` directly in a current browser. The file contains its exact calculation engine, retained Team Commons hashing/canonicalization implementation, interface and initial fixture. No account, network, model call, telemetry, framework or external asset is required.

The initial six-source record describes two products, mixing and packaging constraints, a maintenance capacity-recovery option, serviceable-part allocation, quality release and a versioned procedure. The exact bounded optimizer selects A80/B35 with planned net contribution of $5,650 after a $150 recovery cost. Its no-intervention counterfactual is $4,975, so modeled incremental value is $675.

Record a review, then change the customer mix. The fixture changes Product B contribution from $40 to $120 per unit. The prior conclusion and review become stale before any new calculation. Re-evaluate: the correct plan becomes A30/B60 inside existing capacity, worth $8,850 on that revised record. Recovering more mixing capacity produces the same output and loses the $150 intervention cost. The $3,200 difference between old and new scenario totals is a changed economic assumption, not measured improvement or AXM-created revenue. Only compare intervention alternatives under the same source frontier.

The other challenges reserve the last serviceable spare, hold Product A through QMS, or remove a required capacity value. These alter eligibility, feasible production or the ability to issue any conclusion. The evidence editor accepts actual local CSV input under the displayed strict mapping. Operator-supplied data stays unverified and local.

Export a handoff JSON. Import it in a different browser or the downloaded offline client. The receiver recomputes all historical decisions using their exact dependencies and reconstructs current/stale review standing. The attack button changes a saved economic result and recomputes its hashes; semantic replay still rejects it. A failed import preserves the accepted workspace.

## Reproduce outside the browser

```
python3 build.py
node tests/verify.cjs
node verify-handoff.cjs data/example-handoff.json
```

The CLI derives the engine identity from actual engine and donor bytes. It does not trust the package's reported engine hash. Browser qualification additionally uses Playwright as an optional developer test dependency; it is absent from the runtime and distribution requirements:

```
PLAYWRIGHT_MODULE=/absolute/path/to/playwright BROWSER_OUTPUT=/private/evidence/path node tests/browser.cjs
```

`build.py` uses the Python standard library to produce `offline.html`, a file manifest and a deterministic source ZIP. Successive builds from the same files produce the same archive bytes. A fresh test run has a new observation timestamp, so rerunning tests is a deliberate evidence revision before rebuilding.

## Reuse and source ownership

`commons-core.js` is the exact existing AXM Team Commons copy from the accepted CESMII proof. Its SHA-256 is `0158ea96c0c99a4f479e37573bacf26916348318e2811b75196ce390cab36cdd`. The new engine reuses its canonicalization and digest functions; it does not modify the original Team Commons challenge or claim those older tests qualify the new process recipe. The new calculation, source-chain contract and replay checks receive their own finite acceptance suite.

The new bounded recipe is exhaustive integer planning for exactly two products and two resource stages. It is not an AI forecast, industrial optimizer, scheduling solver, MES implementation or authenticated operational control. Product-specific quantities are limited to 500 per source record to bound work. Alternative schemas require explicit mapping and requalification rather than inferred equivalence.

## Actual authority and evidence boundaries

A recorded review contains an unverified label and a declared role. The example checks that declaration against its procedure; it authenticates no person, verifies no employment or work permission, and never authorizes maintenance or production. No output reaches equipment, a vendor API or an enterprise system. Hashes detect inconsistency under the supplied record; a self-consistent fabricated history remains fabricated. Physical observations, trusted identities, source authenticity, release controls and live freshness must come from the receiving organization.

The fixture's source dates define a historical scenario. The UI's `CURRENT ON RECORD` means dependency consistency within that scenario, not current plant truth. Prior versions stay preserved; a newer source never rewrites the older conclusion. Synthetic financial values are modeled contribution after stated intervention costs, not revenue, free cash flow, ROI or observed results.

## Public research and CI

`research/ASSESSMENT.md` separates vendor-reported capabilities, observed public materials and AXM hypotheses. Public raw page/CSS captures and private outreach context stay with the owning session, outside this source directory. The UI borrows documented visual vocabulary and information hierarchy while retaining independent AXM identity. It includes no vendor logo, portrait, proprietary frontend source or bundled font file. No message has been sent by this package.

All source, fixture and curated assessment files are steward-owned. `build-meta.*`, `offline.html`, `MANIFEST.json`, `package-receipt.json`, the ZIP and qualification receipts are generated; preserve earlier observations in the owning session before deliberate replacement.
