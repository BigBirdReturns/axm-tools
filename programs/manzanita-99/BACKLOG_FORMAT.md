# Backlog format

`MASTER_BACKLOG.json.gz.b64` is the complete 497-task source register stored as base64-encoded gzip so it can pass through text-only repository tooling without truncation. `AMENDMENTS.json` contains explicit, reviewable corrections that must be applied to the source object rather than silently rewriting its history.

Run:

```bash
python programs/manzanita-99/extract_backlog.py
```

The extractor validates the source object, applies every declared amendment by task ID, confirms that the summary count equals the task count, then emits:

- `MASTER_BACKLOG.json`, the canonical expanded and amended register;
- `MASTER_BACKLOG.csv`, a practical triage projection.

The register contains the program phases, 99-point scorecard, release rule, summary totals, dependencies, owner seats, deliverables, acceptance criteria, evidence requirements, and every remaining task. Generated projections do not replace the encoded source object or the amendment ledger.