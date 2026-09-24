# Request inputs: build the inexpensive path

This is an extension of the existing compute desk, not another scheduler or provider scorecard. `compute_input_materials` exposes a primary-source materials library; `compute_place_request` calculates a request-conditioned route from an operator-configured snapshot. Both run through the existing MCP helper. Native execution remains with the existing approved runner or separately qualified orchestration adapter. Nothing here reserves a GPU, reads a credential implicitly, sends customer content or installs an upstream release.

## Run the working path

From the extracted compute kit:

```sh
node inputs/cli.cjs demo
node inputs/cli.cjs place request.json placement-inputs.json
node scripts/connect.cjs --mcp --placement-file /absolute/path/placement-inputs.json
```

The first command runs 12 labeled synthetic cases. Inspect `fixtures.cjs` for fully populated request and snapshot shapes, or write them to new files with:

```sh
node -e "const f=require('./inputs/fixtures.cjs'),fs=require('fs'); fs.writeFileSync('request.example.json',JSON.stringify(f.request(),null,2),{flag:'wx'}); fs.writeFileSync('placement.example.json',JSON.stringify(f.snapshot(),null,2),{flag:'wx'})"
node inputs/cli.cjs place request.example.json placement.example.json 2026-09-24T19:00:00Z
```

The example time is an explicit simulation reference, not a live observation. Do not renew example timestamps to impersonate a live supply read. Without configured input files the MCP call returns INPUTS_REQUIRED. With expired observations it holds affected routes. It never silently defaults user requests to the synthetic examples.

A request supplies an exact workload and validator hash, unit count, deadline, total budget, minimum expected acceptance, transfer volume, tenant, data policy and destination allowlists. Candidate snapshots supply fresh stock, quote terms, current/planned environment identities and workload-specific performance evidence. Every relevant number is required. Missing minimum reservations, egress prices or release estimates are unknown, never free.

The calculation counts transfer, queue, setup, load, execution, validation, a latency margin, release and configured warm retention. It applies billing granularity and minimum charge, then adds ingress/egress, storage, validation and fixed costs. Expected accepted output is units times the supplied acceptance estimate. These conditional forecasts do not guarantee a deadline or enforce a provider billing cap. Fields `minimum_charge_s` and `allocation_hour_usd` refer to the entire allocation: for a new lease use its minimum; for an existing allocation use the separately evidenced remaining obligation/opportunity-cost policy. Do not charge a full new-lease minimum to every request on the same lease.

Cache savings require matching tenant, workload, unit count, model/runtime and cache key, with unexpired supporting evidence. The cache key must include the tokenizer/context and implementation layout identities relevant to the actual cache. This adapter consumes a qualified savings estimate; it neither asserts universal KV portability nor reads another user's cache. A stale or incompatible cache is ignored and the uncached route is evaluated. More advanced overlapping phase models require a separately versioned calculator; this version sums phases conservatively.

## Pull real change signals

```sh
python inputs/collect.py --out /new/private/input-observation-directory
```

This bounded public read fans out over current dstack, vLLM, SGLang, LMCache and Docling release metadata and the campaign model's Hub metadata. The result records source hashes, actual timestamps and failures. Tags are requalification triggers, not permission to upgrade a working runtime. No third-party code or model weights are fetched or executed. The shipped dated observation is historical; run again to get a new record. Old failed/stale observations are not relabeled current. Retain each immutable output directory.

For source-blocked inputs, accept an operator-observed JSON file with the same schema and genuine origin/time/hash. Never replace a blocked observation with a zero price, zero stock or invented timestamp. Public-price catalog review remains separate and unchanged.

Supply reads require a separate explicit action and a named credential environment variable:

```sh
python inputs/collect.py --supply hotaisle --allow-account-read --token-env HOTAISLE_API_TOKEN --team TEAM_HANDLE --out /new/private/ha-supply
python inputs/collect.py --supply runpod --allow-account-read --token-env RUNPOD_API_KEY --count 1 --cloud SECURE --out /new/private/runpod-supply
```

No credentials are loaded from config files or discovery. Account reads use only the documented GET resource. Secrets, team names and raw account bodies are not saved. The normalized result retains per-allocation rates, source minimums, quantity when supplied and missing fields. Runpod catalog bands remain `listed`; they are not reservation receipts. No live account read was performed to prepare this release.

A non-synthetic new-lease candidate can bind a specific normalized `supply_offer_id`:

```sh
node inputs/cli.cjs compose placement-inputs.json ha-supply/observation.json
```

The output `snapshot` updates observed supply, rate and minimum while retaining independent expiry of other quote terms. It does not fill in a missing region, network price, running environment or workload calibration. Existing warm allocations require their own state observation; a catalog listing cannot stand in for one.

## The components to reuse

`materials.json` identifies 20 usable sources and their decision boundaries. `recipes.json` covers coding batches, multi-turn reusable context and document processing. The important integration findings are dstack's existing HA backend, LMCache's actual HA/MI300X trace study and SGLang's existing cache/load-aware gateway. These remove reasons to recreate cloud orchestration or inference routing. Recipe descriptions remain candidates until their pinned combinations pass native qualification.

Keep a compatible local route, specialist cloud route and alternative route where evidence exists. Lower prices, smaller setup cost, useful cache residency and better accepted throughput can each change selection. Provider medals, follower counts and endorsements never enter the function. A silent first preference for HA would destroy the user-efficiency objective.

## Ownership and qualification

`placement.cjs` owns these new calculations; the existing compute and HA report engines are unchanged. `compose.cjs` owns the supply join. `collect.py` owns bounded observation and parser semantics. All shipped inputs are steward-owned. New capture output is explicitly operator-selected, not scheduled, and does not overwrite the public catalog. Tests exercise real code with authored data; input origin and workload qualification remain external evidence requirements.

```sh
node --test tests/test_placement.cjs tests/test_placement_bridge.cjs
python -m unittest discover -s tests -p test_inputs.py -v
```

The case suite includes local-only work, cold-start/minimum-lease reversals, a congested warm GPU, costly data movement, stale supply, runtime drift, cross-tenant cache rejection and unknown-cost holds. Result objects explicitly set `execution_authorized: false`. The work completed here is the feed-to-placement calculation and client integration. End-to-end arbitrary-request execution, cancellation and provider-release confirmation remain a separate qualification of the execution owner.

## Retained execution is an input too

`retained-calibration.json` projects the three scored Run 3 arms from exact committed ledger and detailed-result bytes, retaining model/runtime, acceptance rules, source hashes and workload identity. The materials MCP tool exposes these beside the public source library. This does not renew observation dates, imply current stock, reconcile invoices or generalize one run to other task families. No synthetic supply was attached to make these records look dispatch-ready.
