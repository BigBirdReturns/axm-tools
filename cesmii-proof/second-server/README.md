# Second i3X server and source-bound verification

This package includes the official CESMII i3X 1.0 demo server source at commit
`9ffc352470b9807a0143cd5c43f9680cb5779550`, its official conformance suite,
specification and upstream license. `upstream-source.zip` contains exact Git
archive bytes. `upstream-source.json` identifies every included file by SHA-256.

The verified endpoint was a separate local deployment of the official server.
Its data source is CESMII's simulated manufacturing model. The captured pump
and tank observations establish actual HTTP integration with that second
instance. They do not establish portability across independently authored
vendor implementations or results from a member's operations.

## Observed result

The official suite returned **1.0 Compatible**, with **52 passed, 0 failed,
2 advisory warnings and 6 skipped**. The warnings concern this loopback
development server's HTTP transport and unauthenticated data endpoints.
Historical-value updates are unsupported; current-value write tests were
disabled. The full skipped-test ledger is retained in
[conformance-report.json](conformance-report.json).

The application passed **27 of 27 source-bound checks** against workbench
engine digest
`d64b6f02dfd23a2074d33c6a1b899514a6dce214257e7ba09f9fdcd502606207`.
For each asset, the verification calculates a shortage from separately
declared synthetic operational inputs, applies an allocation correction,
marks the earlier decision stale, retains that original decision, calculates
the corrected result, exports the actual capsule and independently
reconstructs both conclusions in a fresh Node process. A fresh installation
from the bundled upstream archive also started and answered real HTTP
requests successfully.

| Evidence | File |
|---|---|
| Overall source-bound result | [evidence.json](evidence.json) |
| Application checks and source digest | [application-report.json](application-report.json) |
| Official server conformance report | [conformance-report.json](conformance-report.json) |
| Server source, configuration and runtime | [server-provenance.json](server-provenance.json) |
| Fresh installation from bundled source | [recipient-install-proof.json](recipient-install-proof.json) |
| Pump and its state | [capture-local-pump.json](capture-local-pump.json) |
| Tank and its monitoring sensor | [capture-local-tank.json](capture-local-tank.json) |
| Unknown object and missing value | [capture-missing-object.json](capture-missing-object.json) |
| Structural tank object with null / GoodNoData | [capture-no-value.json](capture-no-value.json) |
| Independently replayed pump capsule | [capsule-local-pump.json](capsule-local-pump.json) |
| Independently replayed tank capsule | [capsule-local-tank.json](capsule-local-tank.json) |

A structural object and a measurement are distinct i3X elements. The actual
tank object has no current value; its `MonitoredBy` relationship identifies
`sensor-001`. The positive tank case therefore explicitly maps
`tank-201` to `sensor-001`, while the structural object's null value is
retained as a negative check. The pump maps to `pump-101-state`.
Changing the selected asset without its corresponding source binding remains
inconclusive.

## Start the bundled server

Use Python with venv and pip. The recorded installation used Python 3.13.15
on Windows. The official conformance runner requires Node.js 18.17 or newer.
The AXM browser application itself remains a standalone static application.

From this `second-server` directory, run one of the following commands in
a terminal. The selected work directory must be new and outside the
downloaded package.

Windows PowerShell:

```powershell
python setup.py --work-dir "$env:TEMP/axm-i3x-review" --run
```

Linux or macOS:

```sh
python3 setup.py --work-dir /tmp/axm-i3x-review --run
```

The setup verifies and extracts the included source archive, creates a
private virtual environment, installs the official pinned requirements,
writes an explicit simulated-data configuration and starts the server at
`http://127.0.0.1:8381/v1`. Dependency installation needs a reachable Python
package index or a suitable local package cache. The upstream source and
license are available for inspection without network access. Add
`--fetch-upstream` to acquire the same commit through Git instead of the
bundled archive. Add `--port 8382` when the default local port is occupied.

The command leaves the server running in that terminal. Stop it with
Ctrl+C. No service, startup item, external listener or permanent scheduled
task is installed. Setup without `--run` prints the exact launch command.

The direct launch uses:

```text
python -m uvicorn app:app --host 127.0.0.1 --port 8381
```

Run it with the created environment's Python from `i3X/demo/server`.
The configuration's `app.root_path` is `/v1`; omit uvicorn's
`--root-path` argument for this direct local endpoint. Passing the prefix
both through native `app.py` and in the requested URL doubled it under
the tested uvicorn version and produced HTTP 404. The shipped launcher
uses the verified direct configuration without modifying upstream source.

## Reproduce the full check

Leave the server running, then use another terminal in this directory:

Windows PowerShell:

```powershell
python verify.py --server-source "$env:TEMP/axm-i3x-review/i3X" --out "$env:TEMP/axm-i3x-evidence"
```

Linux or macOS:

```sh
python3 verify.py --server-source /tmp/axm-i3x-review/i3X --out /tmp/axm-i3x-evidence
```

The output directory must be new. A run preserves fresh raw responses,
the official conformance report, application source digests, capsule exports
and independently replayed conclusions. The upstream simulator changes
values over time, so new response hashes and some skipped subscription
tests can differ from this retained run. Every count is reported exactly.

`verify.py` restricts this complete exercise to a selected loopback
endpoint. The official suite receives `--no-writes`; it still creates and
deletes its test subscriptions and probes unsupported historical updates
to verify HTTP 501. The AXM collector separately uses only discovery GETs
and read-query POSTs and performs no remote value writes.

## Connect the member workbench

Open the [workbench](../workbench/index.html), choose the local endpoint,
enter the asset and value IDs, and capture its evidence. Browser privacy
rules may require serving the application locally when contacting a
loopback endpoint. From the parent `cesmii-proof` directory:

```sh
python -m http.server 8380 --bind 127.0.0.1
```

Open `http://127.0.0.1:8380/workbench/`. Select
`http://127.0.0.1:8381/v1`, asset `pump-101`, value
`pump-101-state`, or asset `tank-201`, value `sensor-001`.
The captured context remains distinct from the operator's workflow inputs.

The Python collector also supports approved HTTPS endpoints with explicit
asset and value mappings. From the parent directory:

```sh
python capture.py --base-url http://127.0.0.1:8381/v1 --asset-id tank-201 --value-id sensor-001 --no-history --synthetic-data --out new-tank-capture.json
```

Repeat `--value-id` for each required value. For an authenticated endpoint,
`--token-env YOUR_TOKEN_VARIABLE` reads a bearer token from the environment
without retaining it in the capture. The collector refuses credentials in
URLs, redirects and replacement of a retained capture. Its output retains
the selected source label as an operator declaration, raw JSON response
bodies, timestamps and SHA-256 hashes. A failed or missing source remains
visible to the application.

## Source and ownership

The official source is
[cesmii/i3X](https://github.com/cesmii/i3X/tree/9ffc352470b9807a0143cd5c43f9680cb5779550/demo/server).
The included upstream LICENSE governs that source. This directory's
`setup.py`, `verify.py` and `verify.cjs` are AXM integration and
reproduction tools. The official suite's observed verdict describes this
server and configuration; it does not certify AXM or grant operational
authority. The evidence files are retained observations. Reproduction
writes a new evidence directory and preserves these published bytes.
