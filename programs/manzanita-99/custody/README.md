# Manzanita donor custody

This directory operates the first release blocker in the Manzanita 99-point program, `JDB99-001`. It converts donor custody from a prose instruction into a reproducible register, a deterministic file manifest, a public-route integrity guard, explicit acquisition gaps, and a validator that cannot mistake partial custody for completion.

## Object, actors, and authority

The object is the recoverable evidence base beneath the successor build. The source-custody seat locates, copies, hashes, classifies, and admits artifacts. The design integrator may use an admitted donor only within its recorded claim boundary. The release authority may close `JDB99-001` only after every required gap is closed and every named donor is archived. A passing validation does not promote a donor, qualify a release, or authorize a public change.

The register is steward-owned. The generated manifest is machine-owned and exists only as a workflow artifact or local output. Neither file may contain a private household address, secret, credential, access token, or provider payload whose terms prohibit retention.

## Files

`DONOR_REGISTER.json` is the human-governed inventory. It records the current public v1.4 route, the preserved PR #90 source-foundation identities, the superseded PR #89 register, the program-control merges, the current Pages deployment receipt, and the open evidence classes that still prevent closure.

`build_custody.py` hashes every repo-resident file in the declared archive scopes with SHA-256, computes the corresponding Git blob SHA-1 for cross-checking, constructs deterministic scope digests, carries the donor anchors and open gaps forward, and writes `CUSTODY_MANIFEST.json`.

`validate_custody.py` validates the register, re-hashes every manifest source, enforces the byte identity of the historical `manzanita/` route, verifies the manifest checksum and gap set, and refuses a false closed state. `--require-complete` is reserved for the eventual closure campaign and must fail while any required gap remains.

`tests/test_custody.py` proves deterministic output, tamper detection, public-route protection, and refusal to close around missing evidence.

`SOURCE_FOUNDATION_ARTIFACT.json.gz.b64` is the public, deterministic, plain-text recovery copy of the verified 41-file artifact receipt. It uses gzip with a zero modification time followed by Base64, matching the existing canonical-backlog retention pattern. Recover the readable JSON without third-party dependencies:

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

The ordinary validator is expected to report `PARTIAL` while returning `PASS`. That result means the admitted repo-resident material and open-gap ledger are internally consistent. It does not mean the task is complete. Final closure requires the same command with `--require-complete`, zero open required gaps, and no donor in a state other than `archived`.

## Current boundary

The current public Manzanita v1.4 route is guarded by its Git blob identities and the SHA-256 receipts already carried in `manzanita/QUALIFICATION.json`. PR #90 is located by its pre-rebase qualified head, source tree, workflow run, and rebased head. Its exact 41-file Actions artifact was downloaded before expiry, matched GitHub's recorded SHA-256, passed receipt and payload verification, and now has an owner-only Google Drive copy plus the public metadata receipt in `SOURCE_FOUNDATION_ARTIFACT.json.gz.b64`.

That rescue closes the expiring-artifact acquisition gap. It does not transfer the live-run qualification to the rebased commit, and one owner-account copy is not yet sufficient for final succession. An independently controlled local or second archive remains open, along with historical releases, visual goldens, playtests, failure receipts, broader live-data states, prior deployment receipts, asset-provenance records, and standalone exports.

The controlling question is whether a cold successor can recover each donor, verify its exact bytes, identify who made or observed it, understand what it proves and does not prove, reproduce the rule that followed from it, and distinguish an honest absence from an artifact that was merely forgotten.
