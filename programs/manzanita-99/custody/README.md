# Manzanita donor custody

This directory operates the first release blocker in the Manzanita 99-point program, `JDB99-001`. It converts donor custody into a reproducible register, deterministic repository manifest, immutable public-route guard, explicit evidence gaps, and a validator that cannot mistake partial custody for completion.

## Object, actors, and authority

The object is the recoverable evidence base beneath the Manzanita successor. The source-custody seat locates, copies, hashes, classifies, and admits artifacts. The design integrator may consume an admitted donor only within its recorded claim boundary. Release authority may close `JDB99-001` only after every required gap is closed and every named donor has a durable recovery path. A cold successor is the eventual replay standard.

A passing validator does not promote a donor, qualify a public release, perform a physical or human campaign, repair the damaged canonical backlog, or authorize an external effect. The ordinary expected result is `PASS` with custody status `PARTIAL`.

The register is steward-owned. The generated manifest is machine-owned and exists as a workflow artifact or local output. Neither object may contain a private household address, resident identity, credential, secret, access token, or provider payload whose terms prohibit retention.

## Current admitted chain

The current register snapshots the repository after the following bounded objects reached `main`: the historical v1.4 public rollback donor; PR #90 source foundation; PR #96 contained review board; PR #97 Forkline Field constitution; PR #98 public-safe demonstration place; PR #99 seven apertures; PR #100 Street Glide kernel; PR #101 eight overlays; PR #102 five roles and FAB handoff; PR #103 whole experience plus repairs #105 and #106 and replay #107; PR #104 automated P8; PR #108 estate parity; PR #109 release control; and PR #111 the external campaign evidence runner.

Those objects are separately classified. Their presence does not establish a public successor, real assistive-technology or human operation, credentialed-provider completeness, lawful field standing, exact public-endpoint bytes, real deployed rollback, an independent cold successor, or canonical task-row closure.

## Files

`DONOR_REGISTER.json` is the human-governed inventory. It records authority, required evidence classes, repository archive scopes, current donor anchors, the immutable v1.4 route guard, and every open close gate.

`build_custody.py` hashes each repository-resident file in the declared scopes with SHA-256, computes the corresponding Git blob SHA-1 for cross-checking, constructs deterministic scope digests, carries donor anchors and open gaps forward, and writes `CUSTODY_MANIFEST.json`.

`validate_custody.py` validates the register, re-hashes every manifest source, enforces the byte identity of the historical public route, verifies the manifest checksum and gap set, and refuses a false closed state. `--require-complete` is reserved for the eventual zero-gap campaign and must fail while any required gap remains.

`tests/test_custody.py` proves deterministic output, source-tamper detection, public-route protection, false-closure refusal, and rejection of a partial manifest under the final-completion flag.

`SOURCE_FOUNDATION_ARTIFACT.json.gz.b64` preserves a deterministic public receipt for the historical PR #90 source-foundation artifact. It is a receipt rather than the provider payload itself. Recover its readable JSON with the Python standard library:

```bash
python -c "import base64,gzip,pathlib; p=pathlib.Path('programs/manzanita-99/custody/SOURCE_FOUNDATION_ARTIFACT.json.gz.b64'); pathlib.Path('SOURCE_FOUNDATION_ARTIFACT.json').write_bytes(gzip.decompress(base64.b64decode(p.read_text())))"
```

## Operation

From the repository root:

```bash
python -m unittest discover \
  -s programs/manzanita-99/custody/tests \
  -p "test_*.py"

python programs/manzanita-99/custody/build_custody.py \
  --repo-root . \
  --output programs/manzanita-99/custody/CUSTODY_MANIFEST.json

python programs/manzanita-99/custody/validate_custody.py \
  --repo-root . \
  --manifest programs/manzanita-99/custody/CUSTODY_MANIFEST.json
```

The ordinary validator should report `PARTIAL` while returning `PASS`. That result means the admitted repository material, public-route guard, and open-gap ledger agree. Final closure requires the same command with `--require-complete`, zero open required gaps, no donor without durable custody, and separate evidence for the public endpoint and cold-successor campaigns.

## Current boundary

The historical public route is guarded by its exact Git blob identities and tree SHA. Custody work is prohibited from changing it. The successor chain and qualification machinery are repository-resident and hashable, but many supporting artifacts remain outside complete custody: prior releases and rejected builds, full-state visual goldens, playtests, failed-run receipts, complete degraded-source corpora, historical observed public bytes, original asset provenance, standalone exports, independently controlled qualification mirrors, the original row-level task register, and the real external campaigns.

The controlling question is whether a cold successor can recover each donor, verify its exact bytes, identify who made or observed it, understand what it proves and does not prove, reproduce the rule that followed from it, and distinguish an honest absence from an artifact that was merely forgotten.
