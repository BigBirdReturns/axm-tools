# Sovereign GPU Hubs: free enterprise deployment kit

**One warm model. Many independently pinned adapters. Your hardware, your regions, your records, your keys. No license fee.**

This is an open, self-hosted integration of existing AXM components with the open-source vLLM multi-LoRA engine. It gives an enterprise a reproducible implementation and acceptance contract for the capabilities described at Palantir DevCon 7 on November 16, 2026, without any requirement for Palantir software.

## Full operational architecture

| Responsibility | Existing public/open implementation | This release's integration |
| --- | --- | --- |
| Shared base and dynamic LoRA adapters | [vLLM](https://docs.vllm.ai/en/v0.33.0/features/lora/) | Verify dependencies; load from trusted node-local controller; measure model visibility |
| GPU topology, placement and loss recovery | [AXM Zombie Adapter](https://github.com/BigBirdReturns/axm-zombie-adapter) (MIT); established Estate/TierDesk patterns | Regional pool identities, resource-specific refusals and placement receipts |
| Independent cryptographic provenance | [AXM Genesis](https://github.com/BigBirdReturns/axm-genesis) and [AXM Core](https://github.com/BigBirdReturns/axm-core) (Apache-2.0) | Require an externally trusted Genesis shard verification before adapter admission |
| Evidence ingestion, compiled knowledge and transport | AXM Forge, Spectra and Clarion | Preserve established source and custody boundaries rather than recoding the knowledge stack |
| Measurement, model promotion and financial qualification | [Cantos](https://github.com/BigBirdReturns/cantos), Hot Aisle, [Owned Learning Loop](https://bigbirdreturns.github.io/axm-tools/owned-learning-loop/) | Record true adapter activation time and reproducible acceptance results |
| Sovereignty, authority, audit and recovery | CAIRN/APERTURE contracts and enterprise-held network/IAM | Explicit tenant+region admission, immutable revision pins, refusal on mismatch, hash-chained events and rollback gates |

The source tree includes a Python 3 standard-library host-local adapter controller, synthetic conformance tests, an example manifest, complete deployment procedures and an independently auditable status report. It deliberately reuses the existing inference engine, model verifier and GPU placement components. Internal MARY and TierDesk code is not copied or re-licensed here.

## What the controller does

- Confirms exact SHA-256 hashes for declared base, tokenizer, adapter configuration and LoRA weights under a pinned artifact root.
- Requires matching base identity/revision, tokenizer identity, LoRA rank and permitted tenant/region before any load.
- Calls the operator-installed Genesis verifier with a separately held trusted public key; bypass is an explicit fixture-only switch.
- Connects only to a vLLM administrator API on loopback, verifies the warm base, calls dynamic LoRA load, and checks that the adapter appears in the engine's model list.
- Measures elapsed activation milliseconds; does not assume Palantir's advertised 30–45 seconds.
- Records failures, successful admission, and revocation in an append-only hash-chained JSONL log with synchronized writes.
- Revokes routing before attempting unload. Rollback requires identical currently pinned bytes and independent verification; it never imports an old untrusted alias.
- Returns an admitted inference-model alias to a trusted enterprise IAM gateway, without exposing the administrator endpoint.

A model service can cache many registered adapters, but actual concurrent GPU-resident adapters are constrained by GPU memory, adapter size, batch configuration, and the vLLM runtime. The capacity planner treats VRAM as belonging to each physical GPU, not as a fungible total across unrelated devices.

## Installation and execution

Install independently owned public components as needed:

~~~bash
git clone https://github.com/BigBirdReturns/axm-genesis.git
git clone https://github.com/BigBirdReturns/axm-core.git
git clone https://github.com/BigBirdReturns/axm-zombie-adapter.git
git clone https://github.com/BigBirdReturns/cantos.git
~~~

Install a pinned version of vLLM compatible with the local GPU, driver and Python runtime. Launch the trusted node-local model server with one already verified base checkpoint:

~~~bash
export VLLM_ALLOW_RUNTIME_LORA_UPDATING=True
CUDA_VISIBLE_DEVICES=0 vllm serve /srv/models/pinned-base \
  --served-model-name demo-base --host 127.0.0.1 --port 18406 \
  --enable-lora --max-loras 8 --max-cpu-loras 32 --max-lora-rank 64 \
  --gpu-memory-utilization 0.70
~~~

The administrator port **must remain private and accessible only to trusted processes**. vLLM explicitly warns against exposing dynamic adapter loading to untrusted callers. Use a separately authenticated enterprise ingress for inference.

Create a private registry using [the template](examples/template-registry.json). Replace every placeholder with actual model, tokenizer and LoRA artifact paths and full content hashes. Put each signed Genesis shard under appropriate custody, and supply the trusted verifier's public key separately. The manifest is privileged configuration and should never be accepted from an inference caller.

~~~bash
python3 sovereign.py --registry /etc/sovereign/registry.json \
  --ledger /var/lib/sovereign/admissions.jsonl doctor

python3 sovereign.py --registry /etc/sovereign/registry.json \
  --ledger /var/lib/sovereign/admissions.jsonl \
  --trusted-key /etc/sovereign/genesis-public.key \
  validate --tenant plant-a --adapter quality --region us-west

python3 sovereign.py --registry /etc/sovereign/registry.json \
  --ledger /var/lib/sovereign/admissions.jsonl \
  --trusted-key /etc/sovereign/genesis-public.key \
  activate --tenant plant-a --adapter quality --region us-west

python3 sovereign.py --registry /etc/sovereign/registry.json \
  --ledger /var/lib/sovereign/admissions.jsonl \
  resolve --tenant plant-a --adapter quality --region us-west

python3 sovereign.py --registry /etc/sovereign/registry.json \
  --ledger /var/lib/sovereign/admissions.jsonl \
  revoke --tenant plant-a --adapter quality --region us-west --unload

python3 sovereign.py --ledger /var/lib/sovereign/admissions.jsonl verify-ledger
~~~

The resolve output is designed for an **authenticated enterprise gateway**. The controller is not a public network service and does not itself authenticate remote users. Each enterprise keeps the real identity and network authority.

Run test acceptance locally, no GPU required:

~~~bash
python3 -m unittest discover -s tests -v
~~~

## Production acceptance

Before claiming enterprise deployment, require:

1. Independently verified Genesis artifact signatures, exact component digests and licensed model and adapter weights.
2. Real organizational IAM, private per-region networking, egress controls, version-pinned binaries, host process isolation and authorization separation.
3. Measured genuine model/LoRA load and mixed-adapter generation on intended accelerators, including concurrent GPU and CPU-cache pressure.
4. Measured latency, throughput, model quality, energy, cost per accepted task, adapter eviction and cold recoverability.
5. Tampering, mismatched tokenizer, denied region, quota, engine timeout, process death, ambiguous-result recovery, rollback and reauthorization tests.
6. Durable trusted receipts with named owners, cold-successor verification and periodic independent Genesis sealing of the ledger head.

See [Enterprise Deployment](docs/DEPLOY.md) and [Palantir Feature Mapping](docs/FEATURE_PARITY.md). All public validation is scoped to the tests actually run. The 30–45 second figure is a competing vendor claim, not a benchmark result for this stack.

## Measured evidence: W03, November 16, 2026

The release includes [the mechanical acceptance ledger](evidence/ACCEPTANCE.json) and [the complete public-safe real-engine trace](evidence/w03-live-20261116.json). These are reproduced results, not synthetic estimates.

| Real observation | Observed result |
| --- | --- |
| Runtime and GPU | vLLM 0.33.0, NVIDIA Quadro RTX 8000, 48 GiB |
| Base | Qwen3-0.6B, pretrained model weights independently SHA-256 pinned |
| LoRA | Public phh/Qwen3-0.6B-TLDR-Lora, rank 8, about 4.4 MB |
| Base cold startup until API healthy | 44.081 seconds, recorded separately |
| Warm-base adapter activation, 3 runs | **23.367 ms, 30.164 ms, 18.409 ms** |
| Activation mean | **23.980 ms**, local loopback API to model-list visibility |
| Adapter-specific generation | 3 successful 32-token completions |
| Adapter revocation and unloading | 3/3 successful |
| Inference first-call cost | 19.679 seconds for first completion; following two 1.530 s and 1.533 s |
| Actual Genesis compiler/verifier round-trip | PASS, zero errors, throwaway test key (not production credential) |
| Offline conformance suite | 10/10 PASS, no model weights |
| Region/IAM field deployment | Unqualified, requires customer network and authority configuration |

**Interpretation:** The 18–30 ms is a local adapter-load control-plane measurement on a small, pre-staged adapter and an already-resident base. It is not equivalent to Palantir's advertised 30–45 second end-to-end model-studio workflow. The first-generation initialization cost shows why adapter visibility differs from steady-state inference. The real runtime used fixture admission, barred from production routing. A separate test exercised the actual Genesis signed-release path.

### Signing a release with AXM Genesis

The included [sealing helper](scripts/seal_release.py) invokes the existing AXM Genesis compiler and independent verifier. It requires an existing publisher private key and independently trusted public key under enterprise custody, and refuses to overwrite a signed shard.

```bash
python3 scripts/seal_release.py \
  --registry /etc/sovereign/registry.json \
  --tenant plant-a --adapter quality --region us-west \
  --private-key /secure/keys/publisher.key \
  --trusted-key /secure/keys/publisher.pub
```

Source, model, tokenizer and adapter digests are bound into a canonical JSON source which AXM Genesis seals. The operator holds keys and decides real-world release authority. No private keys, model weights or internal Estate infrastructure are redistributed.

## License and custody

New source code, docs and examples: Apache License 2.0. Linked repositories keep their own licenses. MARY Portable's current LICENSE_STATUS.md has not granted redistribution rights; this package neither republishes nor pretends to license it. No per-seat, per-adapter, per-GPU, or cloud-API subscription is charged by this kit. Physical hardware, power, qualified operations, and any separately licensed model assets still have costs.

**Status:** A mechanically tested integration is different from a fully qualified live multi-region deployment. The requirements above define the remaining terminal conditions instead of silently treating every step as complete.
