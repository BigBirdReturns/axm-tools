# Manzanita 99 backlog recovery

This directory preserves and tests the recovery boundary for the damaged canonical 497-task register. It does not replace the register, relax the validator, or authorize a reconstructed task set.

`audit_backlog.py` inventories every reachable backlog source object, decodes the surviving Base64 variants, attempts bounded BZ2 prefix recovery, extracts only complete JSON task objects, records every JDB99 identifier still named in the working tree, and converts the ten resolution-backfill surface records into an exact 104-component source ledger without inventing canonical task fields.

`RECOVERY_FINDING.md` is the human adjudication record. It classifies the object, actors, failure mechanism, receipts, exact recoverable source families, prohibited claims, and the two admissible next tracks.

`RECOVERY_STATE.json` is the machine-readable control state. It records the damaged-source hashes, missing parts, reachable-history result, exact source-family standing, admission tests, authority boundary, and control question.

From a full repository clone with preserved history and pull-request heads available:

```bash
python programs/manzanita-99/recovery/audit_backlog.py \
  --out recovery-out \
  --skip-deflate-scan
```

The ordinary campaign must return `PARTIAL`. That is the correct result while the original 497-record object remains unavailable. The output directory retains `RECOVERY_REPORT.json`, exact source receipts, the BZ2 partial stream, recovered complete-task objects if any, historical blob inventory, JDB history patches, working-tree task tokens, and `resolution-backfill-exact-components.json`.

The optional raw-deflate scan is a heuristic search for independently decodable suffixes. It is not an admission test and cannot establish completeness. Exact recovery still requires one complete source that decompresses cleanly and passes the repository’s full task, priority, field, dependency, benchmark, amendment, and digest checks.

The controlling question is whether a cold successor can reproduce the distinction between recovered evidence and reconstructed design before any new register is admitted as constitutional.
