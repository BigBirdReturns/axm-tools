# MiMo one-GPU experiment, version 1.0.0

This is an independent, inspectable test kit for a single NVIDIA GPU plus
**real host RAM**. It keeps the selected checkpoint intact and tests an
existing vLLM runtime's CPU-offload path. The public research target is one
96 GB card in Osmantic's published two-card RTX PRO 6000 Blackwell tower.
Its host RAM and free capacity were not publicly established; scan them.

**MiMo single-GPU inference has NOT been qualified by the author.** The kit
is executable instrumentation, not a claim that the new model loads or
retains every benchmark score. It may correctly stop at missing weights,
insufficient RAM, unsupported quantization, loader/kernel errors or timeout.
No model output, token rate or benchmark score has been invented.

## Lowest-friction handoff

Use the public page's copy-ready prompt with your existing local coding
agent. It performs a read-only scan first, fills the settings from observed
hardware and your chosen local checkpoint, and shows the exact plan. It asks
for approval before hashing the full checkpoint, importing an existing
runtime image or starting a load. No new agent framework, ODS installation,
account, shared machine access or cloud model is needed.

Manual equivalents, run from this directory:

    python3 one_gpu.py inspect --out hardware-private.json
    python3 one_gpu.py plan settings.json --out plan-private.json
    python3 one_gpu.py run plan-private.json canary.jsonl --out runs/canary-001 --approve-load

`settings.json` must name an existing local complete checkpoint and an
existing Docker image with MiMo support. The publisher names
`vllm/vllm-openai:mimov25-cu129`; this is a **candidate**, not an author-tested
one-card image. The kit resolves your selected local image to its immutable
Docker image ID and uses `--pull=never`. No image is downloaded. The selected
model ID and 40-character repository revision stay explicit. Local files are
hashed; your attribution of those bytes to an upstream revision remains an
operator assertion unless separately authenticated against publisher hashes.

The launch uses tensor parallel 1, pipeline parallel 1, one active sequence,
85% GPU allocation target, your explicit context/prefill/offload budgets,
chunked prefill and eager execution. It changes no checkpoint, expert pool,
quantization configuration, tokenizer or supplied request JSON. These runtime
choices are experimental variables; do not describe them as bitwise parity.

## Why 42B active does not mean a 42B file

The Pro card reports 1.02T total parameters and 42B active per token. Different
positions can select different experts. This test retains the complete
indexed checkpoint rather than deleting whichever experts a benchmark did
not happen to use. CPU offload trades VRAM residency for host memory and
transfer time; **this runner does not implement NVMe layer streaming**.
An insufficient host-RAM result remains blocked. We do not call swap a GPU,
pool the other card into the denominator, or silently switch to Flash.

The released Pro config combines `quant_method: fp8` with
`store_dtype: mxfp4`. Disk bytes are not a guaranteed loaded footprint. The
header scan catches definite capacity failures but cannot prove loaded fit.
RAM cgroup caps, no container swap, reserved host headroom and a deadline
bound the subsequent native canary. A failed load remains evidence.

## Each benchmark gets its own immutable protocol

Choose an existing trusted benchmark harness, dataset revision, scorer and
prompt/chat-template protocol. Use the same complete checkpoint and image
for comparison. Keep few-shot formatting, tool schema, temperature, top-p,
seed policy, reasoning settings, token limits, context, task subset and
stopping conditions fixed. Never profile on held-out answers or prune experts
for a particular benchmark. Distillation is a different experiment.

### Independent request benchmarks

Export exact requests in the OpenAI batch-file shape (one JSON object per
line with `custom_id`, `method`, `url`, `body`). The kit does not rewrite the
model name or request body. Run your **native scorer** on the returned
responses. A canary and a completed batch are both explicitly UNSCORED.

    python3 one_gpu.py run plan-private.json requests.jsonl --kind benchmark --protocol protocol.json --out runs/benchmark-001 --approve-load

`protocol.json` binds the benchmark/harness/dataset/scorer identities, context
and SHA-256 of the request file. An offline batch cannot replace interactive
environments or benchmarks with per-request deadline rules. Those require the
native harness route below. A shortened smoke set stays a smoke set, not an
Artificial Analysis composite result.

### Native interactive / tool / timed benchmarks

    python3 one_gpu.py serve plan-private.json --out runs/native-001 --approve-load

This starts a temporary local adapter while the owned model container has
`--network none`. Read `runs/native-001/connection-private.json` for the
loopback OpenAI-compatible URL, ephemeral API key and exact model ID. The
adapter forwards completion JSON bytes unchanged, supports streaming and
never retries. GET `/health` and `/v1/models` also work. Wait for health 200;
the connection file by itself says STARTING, not ready.

Point the existing native harness at that URL using its documented model-
provider configuration. Leave its environment, tools, scorer and deadlines
intact. No benchmark software or judge is installed/invoked by this kit.
Responses/embeddings/vendor-specific APIs outside the exposed endpoints must
return ADAPTER REQUIRED rather than being approximated. Client concurrency
above four outstanding proxy calls gets 429; this transport limit is part of
the declared experiment and may preclude a specific protocol.

Create a file named `STOP` in that run folder to end the serving window, or
allow its declared deadline to end it. The owned container is stopped and
removed; existing ODS/vLLM services are untouched. The bridge records hashes,
HTTP status and elapsed time, not a benchmark grade. It introduces transport
overhead, so this is a capability/cost test, not a clean raw-latency benchmark.
The caller must stop its own harness when the serving window closes. The
adapter does not extend native deadlines or fabricate missing responses.

## Inspect before sharing

Open `report.html` in the completed run folder for a readable summary.
The run folder also retains the launch argument vector, immutable image ID,
full checkpoint content manifest, request hash, responses, engine log,
GPU/RAM samples and result receipt. Hashing time and load/batch time are
separate. Full hashing can read hundreds of GB and takes real time.

Hardware and plans contain local paths and GPU UUIDs; native connection
files contain an ephemeral API key. They remain mode 0600 in a private
run directory. Logs/outputs can contain prompts and benchmark data. Review
before sharing. Prefer a manually reduced summary of model/revision,
checkpoint root, runtime image, one-card observation, host-RAM cap,
context, native score, sample count, time, failures and limitations.
No result is uploaded automatically. Do not publish restricted benchmark
items or answer keys. A GPU inventory match is not an independent attestation.

## Source and method boundary

The prior estate Kimi-K3 work demonstrates a **model-specific** retained-state
and streaming experiment, with a 588 s/token sequential baseline and a
reported 1.38x strict canonical improvement over retained artifacts. Its
93-layer state comparisons cover two accepted positions, not a complete
benchmark campaign. The 2.83x number belongs to noncanonical verification
throughput. That port is not shipped here or silently renamed MiMo support.
Aperture 0.4.7 already supplies permissioned hardware/model inspection and a
qualified smaller GGUF CPU/GPU split. Its published managed path does not
implement distributed serving or automatic benchmark-harness attachment.

This kit carries forward the discipline: separate weight capacity, active
working set, placement, numerical/quality evidence and operational cost.
MiMo-specific native support still has to pass on the receiver's machine.

## Dependencies, maintenance and terminal conditions

Python 3.10+, Linux (including a configured Linux WSL2 environment), Docker,
NVIDIA container support, an existing compatible vLLM image, and the exact
local checkpoint are external prerequisites. The controller uses only the
Python standard library. The site has no backend or telemetry. The local
adapter exists only during a bounded approved test.

No auto-install, weight acquisition, remote APIs, hardware purchase,
service shutdown, power/clock change, benchmark repair or model fallback.
All release files are steward-owned and frozen at publication. A behavioral
change is a new version. Inspect sources in `SOURCES.json`. Browser checks
and simulated process tests qualify the control surface only. They never
count as native MiMo inference or benchmark acceptance.
