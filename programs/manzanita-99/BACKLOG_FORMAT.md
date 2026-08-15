# Backlog format

`MASTER_BACKLOG.json.gz.b64` is the complete 497-task register stored as base64-encoded gzip so it can pass through text-only repository tooling without truncation.

Run:

```bash
python programs/manzanita-99/extract_backlog.py
```

The extractor validates that the summary count equals the task count, then emits:

- `MASTER_BACKLOG.json`, the canonical expanded register;
- `MASTER_BACKLOG.csv`, a practical triage projection.

The register contains the program phases, 99-point scorecard, release rule, summary totals, dependencies, owner seats, deliverables, acceptance criteria, evidence requirements, and every remaining task. Generated projections do not replace the encoded source object.