# Enterprise sovereignty, deployment, and recovery contract

## Architecture and ownership

Deploy a separate controller plus one or more vLLM GPU pools **inside each authorized jurisdiction**. No central cloud service needs to hold model weights, adapters, prompts, encryption keys, or source records. The authorized organization decides whether records may be replicated across regions. A disaster recovery jurisdiction is a new authorization decision, never an implicit routing fallback.

Request lifecycle:

1. Enterprise IAM validates user, tenant, region, operation, and current organizational policy.
2. Its regional scheduler consults the local controller for an admitted adapter alias.
3. The trusted gateway sends the request to the regional inference data plane. It never forwards requests to the vLLM administrator LoRA loading endpoint.
4. vLLM serves the selected adapter over a warmed base. Deployment-specific observability records request latency, throughput and failures without disclosing raw prompts by default.
5. A separate evidence process periodically seals the hash-chained outcome frontier through AXM Genesis, so external auditors can verify custody and continuity independently.

Labels in configuration do not enforce physical geography. Region sovereignty requires actual transport and storage restrictions, trusted tenancy, signed artifact identity, and a lawful operator decision.

## Registry contents

The JSON registry is operator-owned privileged configuration and must be stored outside a public source tree.

- The artifact root is a canonical directory containing model, tokenizer, and adapter bytes. Every declared file path is resolved and checked against it. Symlink escapes are refused.
- Each pool binds a region to a loopback-only vLLM admin address, exact base source identity and revision, one model alias, approved LoRA maximum rank, pinned base file hashes, and pinned tokenizer file hashes.
- The tokenizer primary digest must match the shared tokenizer identity, and every compatible adapter must declare the same digest.
- Each adapter declares the exact PEFT base identifier and rank, file hashes for its configuration and safetensors weights, an immutable revision and the Genesis shard location.
- Each tenant declares allowed regions, allowed adapters, and a maximum active-adapter count.
- The trusted Genesis verification key is never supplied by an adapter manifest. It must be provided out of band by the authorized operator.
- Configured base/model digests do not magically prove that the engine was launched with those same files. Deployment acceptance must inspect and verify vLLM launch arguments and node state.

## Independent AXM signature binding

The included `scripts/seal_release.py` implements a real offline source-to-Genesis compile and independent verification round-trip. It requires an operator-supplied existing hybrid publisher key and an independently trusted public key. The exact `content/source.txt` binds the tenant, adapter, region, vLLM alias, base revision, tokenizer SHA-256, adapter weight SHA-256 and served model under schema `axm/adapter-release-binding@1`. Source equality is checked after independent Genesis verification, so unrelated signed shards cannot authorize an adapter.

The helper neither generates production keys nor overwrites an existing sealed destination. A November 16 test used a throwaway hybrid test key; the existing `axm-build` and `axm-verify` returned PASS with zero errors. Enterprise publisher identity and authorization remain separately controlled.

## Host procedure

1. Qualify the node GPU, thermal/power firmware, local storage, network, and engine support. Use the public AXM Zombie adapter to calculate placements but never treat a plan as a measurement. Reserve actual hardware through the enterprise scheduler.
2. Stage exact source-approved model files and tokenizer. Verify hashes before starting a warmed private base. Preserve license and origin records.
3. Train or import the adapter from a lawful source; verify PEFT metadata and source model revision; evaluate candidate quality and non-regression. Seal the approved weights through AXM Genesis.
4. Create the regional registry and the separate public-key file. Restrict its write permissions to the deployment authority. Keep the administrator API on localhost with OS-level ACLs.
5. Run doctor, validate, activate, inspect, and resolve. Preserve all receipts. Verify the engine responds to a real adapter-specific inference request before declaring it usable.
6. Promote the alias through the authenticated tenant gateway. Measure true per-region token generation, latency, cache, HBM usage and error rate.
7. For replacement, stage an immutable new alias, run parallel qualification, atomically switch application routing, drain in-flight requests, then revoke and unload the previous alias. Avoid in-place mutation of the weight object serving active traffic.
8. If activation times out, inspect the existing log and engine aliases before retrying. An uncertain remote result is not a known failure. Record the observed reconciliation instead of blindly double-loading.
9. For rollback, restore the original signed manifest and bytes, confirm the alias still resides on the expected local engine and obtain organizational authorization to use it. A changed/revoked model is not implicitly safe to revive.
10. Export a source-safe receipt packet with manifests, hashes, acceptance traces, and independent verification records. Do not embed private data or redistributable-restricted model weights in a public release.

## States and proof

| State transition | Required evidence | Durable result |
| --- | --- | --- |
| untrusted → eligible | Source, bytes, tokenizer, rank, identity and trusted Genesis signature match | Validation receipt or typed refusal |
| eligible → loaded | Warm base present; private vLLM API accepts and reports adapter alias | Activation event and measured milliseconds |
| loaded → routed | IAM and region match approved service contract | Only region and approved model alias returned |
| routed → revoked | Route removed before attempting GPU unload | Revocation event even if unload fails |
| revoked → rollback | Currently pinned, independently verified identity and resident old alias | Explicit rollback event or refusal |
| any → denied | Digest, region, tenant, quota, topology, authority or runtime test fails | Typed failure, no new active route |

Hash chaining **detects** accidental or malicious edits but does not itself authenticate the entire ledger to an independent recipient. Seal the live frontier periodically using Genesis and preserve a separate trusted copy.

## Measurements and comparisons

Measure activation from the time the trusted local controller requests loading until the alias appears in the engine model list. Report cold model start separately. Do not substitute a model-registry listing for actual successful inference.

Record:
- Base load and warm retention; LoRA activation mean, P50, P95 and P99.
- Distinct registered, CPU-cached, and concurrently GPU-active adapters.
- Time to first token, tokens/s, end-to-end latency and error rate per tenant.
- HBM/VRAM working set, KV cache, page-in, PCIe/interconnect traffic and actual GPU frequency.
- Electricity measured at the appropriate meter and joules per successful output.
- Region-specific egress, service authentication, denial events and audit retention.
- Cost per successful task, including equipment depreciation, electricity, staffing and failures.
- Memory-pressure, node-loss, bad-configuration, stopped-controller, journal-corruption and cold-successor recovery drills.

Palantir's claimed 30–45 seconds is a comparison target. A simulated controller test and an unrelated prefix-cache benchmark do not establish our activation latency.

## Reusable software and proprietary boundaries

Public sources include AXM Genesis/Core, AXM Zombie Adapter, Cantos and vLLM, with their own licenses. The new controller is Apache-2.0. MARY Portable and any unlicensed internal Estate donor code remain excluded. Enterprises may implement the published admission interface using their own authorized operations runtime.

Known limits: Host-local JSONL evidence is not a consensus log; private inference gateway identity and regional egress rules must be configured externally; OCI/Kubernetes operational controls and long-term cluster SLOs require an actual enterprise-specific qualification. Source availability grants no production certification.
