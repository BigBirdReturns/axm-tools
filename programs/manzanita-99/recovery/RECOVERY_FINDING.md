# Constitutional backlog recovery finding

## Object and standing

The object under examination is the canonical machine-readable source register asserted to contain the complete 497-task Manzanita 99-point program. It is a constitutional program object, not a product surface, design specimen, or release candidate. The program-authoring seat originally defined the task law and counts. The repository steward and source-custody seat may preserve, hash, inspect, and recover evidence. The release authority may admit a recovered or reconstructed register only after its identity, completeness, provenance, amendments, counts, and dependencies are reproducible. A cold successor is the controlling replay seat.

The current finding is `ORIGINAL_REGISTER_NOT_RECOVERED`. The stated 497-task structure remains supported as a program claim by the merged README, scorecard, pull-request record, and execution overlay. The exact row-level canonical register that was supposed to make that claim machine-verifiable is not present in recoverable form in the repository.

## Failure mechanism

`MASTER_BACKLOG.json.gz.b64` contains 19,999 Base64 characters. Strict decoding fails because the length is invalid. Realigning the surviving characters by dropping the first three characters produces 14,996 bytes whose final eight bytes form a coherent gzip trailer: CRC32 `95f58d14` and uncompressed size `570777`. The surviving file is therefore a terminal slice of a larger gzip stream rather than a complete gzip object. Its SHA-256 after that alignment is `28857b9b252ab8a0ca0a7c92b448b48fee9477c37827d93bd14b07b2c2a71c7e`.

The subsequent repair attempt is also incomplete. The repository contains only `MASTER_BACKLOG.json.bz2.b64.part01` and `part02` from an intended five-part sequence. Their 23,999 concatenated Base64 characters decode to 17,999 bytes with a valid BZ2 header and SHA-256 `913dc94fad74d6be22a6e25eb98fe64d295346b4f8847c41cbcdd6db8cc3b29c`, but the first BZ2 block is incomplete. The decompressor reaches no end marker and emits zero bytes. Parts 03, 04, and 05 are absent.

A full reachable-history inventory found three unique backlog source objects only: the damaged gzip/Base64 tail and the two BZ2/Base64 parts. No complete `MASTER_BACKLOG.json`, CSV expansion, missing BZ2 part, or earlier intact encoded source appears in the fetched repository history or preserved PR heads. The merged program workflow failed at the extraction step before any 497-task validation or expanded-artifact upload could occur. The failure is therefore constitutional source loss, not merely a broken CI command.

## Exact evidence still available

The estate-backfill contribution is recoverable at source level. The ten governed surface records contain exactly 104 components: ten surface epics, thirty findings, and sixty-four required assets. `audit_backlog.py` preserves those components verbatim in `resolution-backfill-exact-components.json` without assigning inferred canonical task IDs, priorities, phases, owners, dependencies, or completion states.

The repository names twenty-two JDB99 identifiers in surviving program prose, amendments, execution state, and related records: `JDB99-000`, `001`, `002`, `003`, `004`, `005`, `006`, `007`, `008`, `009`, `010`, `011`, `013`, `014`, `015`, `016`, `017`, `018`, `020`, `027`, `030`, and `031`. These references do not reproduce the complete eleven-field task objects required by `validate_program.py`. Exact canonical definitions remain absent for `JDB99-012`, `019`, `021` through `026`, `028`, and `029`, and some surviving identifiers are represented only by prose or amendment fragments.

The 361-item Manzanita contribution survives as an exact high-level asset law in the PR #89 register. That source preserves the total count, priority totals, namespace counts, source families, Street Glide provider order, generation boundary, release laws, and build order. It does not contain 361 row-level task objects. Its summary may govern a later reconstruction, but it cannot be represented as the missing canonical machine register.

The exact 497-record object is therefore not recoverable from the evidence presently available. The recoverable source families are asymmetrical: 104 estate components are exact, the 361 product contribution is summary-complete but row-incomplete, and the 32 program contribution is partially named but row-incomplete.

## Receipts

The bounded recovery campaign ran on commit `f780b31781a2fe6def8a1fed733003fc74f39fe0` as workflow run `31926451145`. The run completed successfully and retained artifact `9257973096`, digest `sha256:a5180b497cf52f2a6b1d0662210f6fec275318d8f2638649a7d20cc2db2f0709`. The artifact includes the exact damaged source files, Base64 alignment variants, BZ2 partial bytes, reachable-history inventory, program history, task-token inventory, exact 104-component estate ledger, scorecard, amendment, README, and the PR #89 asset-law source.

The earlier PR #92 review independently identified the same primary defect before merge: the 19,999-character source could not pass strict Base64 decoding, manually adding padding did not produce a gzip header, and the workflow could never reach the asserted 497-task checks. The subsequent workflow logs confirm that extraction terminated with `binascii.Error: Incorrect padding`.

## Evidence ledger

The evidence tier is repository objects, preserved pull-request heads, exact workflow logs, deterministic content hashes, and retained recovery artifacts. The venue is the draft recovery branch and its 90-day Actions artifact. The target is the constitutional task register only. The upside is an honest boundary between exact recovery and later reconstruction, plus preservation of every surviving byte and source component. The downside is that the original row-level object remains unavailable. The failure mode is to manufacture missing rows, assign inferred canonical identities, or teach validation to accept a damaged source while continuing to describe the result as the original 497-task register.

## Permitted next actions

An exact-recovery track may continue searching independently retained packages, local estate copies, chat-produced downloads, external archives, or missing BZ2 parts. Any candidate must reproduce the full source, decompress cleanly, contain 497 unique complete task objects, match the declared priority and family totals, resolve every dependency, retain the no-affiliation statement, accept the recorded amendment to `JDB99-030`, and produce stable JSON and CSV digests.

A reconstruction track requires an explicit release-authority decision. That track would create a new canonical register identity from the exact 104 estate components, the PR #89 asset law, surviving JDB99 definitions, source-foundation evidence, and newly authored rows for every unresolved object. Every reconstructed row would carry a source-family classification and provenance receipt. The result could preserve the 497-task constitutional shape, but it would be a governed successor register rather than a byte-identical restoration of the missing source.

Until one of those tracks passes its own admission criteria, `JDB99-001` remains open, the custody PR remains draft, the original 497-task register remains unvalidated, and no whole-product score or release claim may rely on the damaged machine source.

## Control question

Can a cold successor distinguish every exact recovered component from every newly authored reconstruction, reproduce the count and dependency law from retained sources, and explain why the admitted register is complete without converting a remembered total into fabricated evidence?
