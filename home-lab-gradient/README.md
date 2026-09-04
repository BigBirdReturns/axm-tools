# Home Lab Capability Gradient

Home Lab Capability Gradient is a local, evidence-tiered production planner for a heterogeneous personal compute estate. It begins with the actual estate shape, three CPU and RAM islands, three iGPUs, an RTX 4060, two RTX 3090s, and several storage surfaces, then converts the hard orchestration objective into a capability graph and a sequence of bounded experiments.

The module does not ask which platform should own the lab. It asks which smallest reversible experiment can close a currently required capability gap, unlock valuable downstream work, and produce acceptance evidence without placing another mandatory service on the critical path.

The seed projection selects two actions:

1. Capture stable identities for the three hosts and six accelerator domains with a read-only Windows collector.
2. Freeze one already useful function, initially the observed local Qwen3.5 route on the RTX 4060, and qualify its exact adapter, model digest, interface, timeout, cleanup, and contract-level replay.

Those two actions admit the next measured floor: worker eligibility, invocation receipts, clock bounds, path costs, residency state, and sequence-dependent rotation costs. The harder goals, prefetch overlap, compact handoffs, capacity tokens, backfill, conditional rotation leases, provisional retirement, and a rolling two-3090 schedule, remain blocked until the receipts establish their prerequisites.

## Operating model

The source tree contains four durable inputs:

```text
data/estate.json       declared estate shape and known boundaries
data/goals.json        capabilities, evidence tiers, dependencies, and hard goals
data/experiments.json  bounded experiments, costs, outputs, acceptance, and commands
data/evidence.json     seed evidence with no silent capability promotion
```

The planner applies four rules in order:

```text
evidence-tier admission
remove already complete work
Pareto fronts across explicit benefit and cost dimensions
documented lexicographic tie-break within each front
```

There is no hidden total score. Benefits and costs remain separate. An experiment can be cheap and useful without being allowed to conceal a fatal prerequisite, an irreversible transition, or a new package dependency.

The evidence ledger has one strict law: narrative relevance never promotes capability. A record changes a capability tier only when its `supports` field names that capability and tier. Experiment receipts may support only outputs declared by the experiment catalog, may not exceed the experiment's production ceiling, and are rejected when a covered artifact is missing or digest-mismatched.

## One authoritative runner

All Python operations enter through `scripts/lab.py`. Helper modules are imported directly and contain no alternate command surface.

```bash
python scripts/lab.py validate
python -m unittest discover -s tests -v
```

Create operator state outside the repository:

```bash
python scripts/lab.py init
python scripts/lab.py next
```

The default state directory is:

```text
Windows: %LOCALAPPDATA%\AXM\home-lab-gradient
Linux:   $XDG_STATE_HOME/axm/home-lab-gradient
         or ~/.local/state/axm/home-lab-gradient
```

Use `--state-dir` before the subcommand to select a different directory. Observations, function contracts, run packages, receipts, evidence, and the current plan remain there. The runner never commits them automatically.

## Easy win 1: identify the estate

Run the collector on each Windows host with the declared host identity:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/collect-windows.ps1 `
  -HostId control-host `
  -OutFile "$env:LOCALAPPDATA\AXM\home-lab-gradient\observations\control-host.json"
```

For Linux hosts, run the standard-library collector instead:

```bash
python3 scripts/collect-linux.py \
  --host-id heavy-host-b \
  --out-file "$HOME/.local/state/axm/home-lab-gradient/observations/heavy-host-b.json"
```

Both collectors require no elevation, install nothing, open no socket, and
publish by atomic rename. Repeat for each host, then gather the three JSON
files on the control host and qualify them:

```bash
python scripts/lab.py qualify-estate \
  control-host.json heavy-host-a.json heavy-host-b.json
```

The collector uses platform-native interfaces when present. It records CPU, RAM, physical storage, display adapters, NVIDIA UUIDs, PCI bus identities, driver versions, physical network link properties, runtime presence, wall-clock samples, and monotonic timer frequency. It deliberately omits serial numbers, MAC addresses, IP addresses, and the machine GUID.

Windows observations use `axm-community-lab/windows-host-observation@1`; Linux observations use the platform-neutral `axm-community-lab/host-observation@2`, which carries an explicit `platform` field. The qualifier joins both. Retained `@1` bytes stay admissible exactly as they were written: they are normalized in memory only, never rewritten or republished as `@2`.

The required runtime denominator is closed on every platform — `python`, `git`, `ollama`, `docker`, `wsl`, `nvidia-smi` — and a platform-inapplicable runtime does not disappear. On native Linux, `wsl` stays present as an explicit inapplicable row with `disabled_reason` `"not applicable on a native Linux host"`.

### Three labels are not three machines

Three declared `host_id` strings prove three labels. The qualifier therefore derives an **observed-host fingerprint** from the permitted hardware and platform fields the observation already carries — computer name or hostname, system manufacturer and model, OS identity, architecture, firmware identity, CPU rows, total memory, physical disk model and size, display adapter name and bus identity, and accelerator identities — and refuses a census unless the three fingerprints are **distinct**. The fingerprint deliberately excludes `host_id`, `observed_at`, the clock samples, and the collector and runtime rows: those are what an operator edits to relabel one machine as three, so a fingerprint that moved with them would prove only that the labels differ.

Accelerator identities are checked the same way. An NVIDIA UUID is unique to one physical board, so the same UUID appearing under two host ids refuses. PCI bus ids are deliberately not checked this way: they are unique per machine, not per estate.

Both refusals appear under `unresolved.physical_identity` and in the `distinct-physical-hosts` receipt check, and neither `host_inventory` nor `device_identity` can be supported while either stands. Deriving physical identity does not widen the privacy law: every input is a field already admitted into the body, and the published value is a digest.

### Running the Linux collector on a host with no clone

`seed/` is a self-contained, content-addressed bundle for exactly that case: collector, POSIX launcher, schema, deterministic validator, manifest, checksums, self-verifier, and a reconstruction script. It carries no credential, host secret, or private address, and opens no callback.

```bash
python3 seed/verify.py --root .          # verify the bundle before collecting
./scripts/collect-linux --host-id heavy-host-b --out-file <path>/heavy-host-b.json
python3 seed/collect-linux.validator.py <path>/heavy-host-b.json \
  --receipt <path>/heavy-host-b.receipt.json
python3 seed/reconstruct.py --root .     # prove byte-identical reconstruction
```

The launcher self-verifies before it collects, so a tampered bundle refuses rather than producing an observation. See `seed/README.md` for the execution, return, and boundary contract.

The seed coordinate is **enforced, not documented**. `--host-id` must be one of the ids `seed/seed-manifest.json` declares, and the basename of `--out-file` must be exactly `<host-id>.json`. Both are checked against the manifest — whose exact bytes `seed/sha256sums.txt` binds — before any host surface is read and before any directory or temporary file exists.

The collector writes exactly two files: the observation `<host-id>.json` and the body-free receipt `<host-id>.receipt.json` that issue #151 requires for the W01 join. Each is published through a freshly created, exclusively opened, unpredictably named same-directory temporary, then `fsync`, atomic `rename`, and a directory `fsync` where the platform exposes one. No predictable temporary name is ever written through, so a pre-existing alias at a guessable path can never be the inode that gets truncated; a symbolic link, hard link, or reparse point at either output name, or at the historical deterministic temporary name, refuses the run rather than being acted on.

The receipt carries identities and digests only — body digest, exact file digest and size, observed-host fingerprint digest, one digest per accelerator identity, collector and Python executable digests, and the seed identity — so it can be published in the open while the observed body stays on the host that produced it. `seed/collect-linux.validator.py --receipt` enforces that: apart from the declared join coordinates and those digests, no value from the observation body may appear in it.

A complete receipt promotes `host_inventory` and `device_identity` to `observed`. A partial receipt can promote host inventory while leaving unresolved accelerator identities explicit. It cannot admit workers, measure topology, or establish cross-host clock precision.

## Easy win 2: freeze one proven function

Create a draft contract for the existing local Ollama route:

```bash
python scripts/lab.py scaffold-function --id bounded-local-inference
```

The scaffold binds the stdlib adapter digest, local endpoint, exact model name, shell-free argument vector, input and output schema, timeout, failure meanings, nonempty output fields, and stable replay fields. Qualify it with the paths printed by the command:

```bash
python scripts/lab.py qualify-function \
  --contract <state-dir>/functions/bounded-local-inference/function-contract.json \
  --fixture <state-dir>/functions/bounded-local-inference/function-fixture.json
```

The adapter reads Ollama's local model catalog, binds the installed model digest, runs the fixture twice, records both provider outputs and counters, and compares only the declared contract-stable fields. It does not claim that generated prose is byte-deterministic or semantically correct. A passing receipt promotes only `function_contract` to `qualified`.

## Advancing the gradient

Recompute the plan after any accepted receipt:

```bash
python scripts/lab.py plan
python scripts/lab.py next
```

A general experiment can be opened only when its prerequisites are met:

```bash
python scripts/lab.py start measure-path-costs
```

The resulting run package binds the current plan digest, experiment definition, acceptance criteria, expected artifacts, and command surface. It confers no capability by itself. The later experiment implementation must produce an ingestible receipt:

```bash
python scripts/lab.py ingest <run-directory>/experiment.receipt.json
```

Blocked experiments are refused with their enabling chain. Complete experiments are refused because repeating them without a new version or superseding need would add work without advancing the capability graph.

## Standalone interface

`index.html` embeds the complete seed estate, capability graph, experiment catalog, evidence ledger, and generated plan. It performs no network request. The interface shows:

- current Pareto-admissible work and exact cost vectors;
- acceptance criteria and copyable commands;
- hard-goal progress by required capability;
- the complete capability evidence ledger;
- every blocked experiment and its enabling chain;
- the planning law, claim boundary, plan digest, and control question.

A current operator-generated `plan.json` can be loaded from disk. That import changes only the browser projection and does not write evidence or execute work.

Rebuild the committed projection:

```bash
python scripts/lab.py build --now 2026-08-05T00:00:00Z
python scripts/lab.py page-identity   # the runtime-independent product identity
```

### The page is a byte-addressed product

Every workflow leg rebuilds `index.html` and fails on a tracked difference, so the build must emit the same bytes on every admitted runtime. Two things used to decide those bytes for it, and `scripts/render.py` now owns both.

The gzip container header was the whole of the observed cross-runtime drift. `gzip.compress` does not write a stable header: CPython 3.11 and 3.12 delegate to zlib, which stamps its own platform OS byte, while 3.10 and 3.13 write `0xff`. The deflate body was byte-identical on every leg measured, so the header is now constructed here and never inherited — which is why the committed product bytes did not have to change. Text-mode newline translation was the other: `write_text` turns LF into CRLF on Windows, so the page is written with an explicit LF newline and `.gitattributes` pins it to check out that way too.

The one remaining way the bytes could move is a different deflate implementation. `render.AUTHORITATIVE_COMPRESSOR_SHA256` is the digest of this repository's framing of a fixed probe vector, and `build` **refuses** on a runtime whose fingerprint does not match rather than rewriting a committed, digest-addressed product with bytes no other leg can reproduce.

## Qualification

The source qualification is stdlib-only:

```bash
python -m unittest discover -s tests -v
python scripts/lab.py validate
python seed/verify.py --root .
python seed/reconstruct.py --root .
```

The tests cover deterministic seed selection, timestamp-independent plan identity, evidence-only capability promotion, receipt ceiling enforcement, artifact tamper refusal, idempotent ingestion, function-contract scaffolding, complete synthetic three-host qualification, and refusal to start a blocked hard-goal experiment. They also carry the hostile witnesses for the laws above: one relabelled machine cannot fill three roles, a duplicated accelerator identity refuses, a pre-existing hard link or symbolic link at a publication name refuses without being acted on, an undeclared host id or a mismatched output basename refuses before anything is read, the return receipt is body-free, the aggregate still honours the predecessor row contract, and the page reproduces byte-for-byte or the build refuses.

`.github/workflows/home-lab-gradient-validate.yml` runs that denominator permanently on **Ubuntu and Windows** under Python 3.10 and 3.12, asserts the exact test count, verifies and reconstructs the seed, checks LF custody, parses the PowerShell collector on the Windows legs, fails on tracked post-build drift, and compares one source identity across all four legs.

## File ownership

- `data/estate.json`, `data/goals.json`, `data/experiments.json`, and `data/evidence.json` are steward-owned seed inputs.
- `index.html` is a deterministic, compressed standalone projection of those seed inputs.
- `scripts/planner.py`, `scripts/evidence.py`, `scripts/render.py`, and `scripts/ollama_function.py` are directly imported helper modules.
- `scripts/lab.py` is the sole Python command surface.
- `scripts/collect-windows.ps1` is the read-only Windows observation surface.
- `scripts/collect-linux.py` is the read-only Linux observation surface and the seed's collector; `seed/` is its content-addressed offline bundle.
- `tests/` contains synthetic qualification fixtures in code and does not touch the real estate.
- Operator observations, contracts, run packages, receipts, and evidence belong in the external state directory and remain uncommitted unless the operator deliberately exports them.

## What can rot

Windows CIM fields, NVIDIA `nvidia-smi` query names, Ollama endpoint responses, and local model naming can change. Those failures are bounded: the collector or adapter returns missing fields or a failed receipt, and the planner does not advance. Estimated experiment costs are seed estimates until replaced by measured receipts. The static interface can become visually dated without changing the planning law or evidence ledger.

The material failure mode is a receipt producer that claims a check passed without performing the underlying experiment. The module protects artifact custody, declared ceilings, and deterministic planning, but it cannot manufacture independent observation from a false operator assertion. Stronger experiments should therefore retain raw timings, exact commands, worker identities, and falsification cases inside the receipt directory.

## Boundary

This module selects and receipts bounded experiments. It does not claim that the estate is already a distributed computer, that a particular scheduler will improve wall clock, that the two 3090s can be pooled as transparent 48 GB memory, or that any hard goal is achieved before its exact acceptance comparison passes.
