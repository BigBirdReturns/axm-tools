# Case Zero local runner

Run the standard-library intake inside RedCat's environment:

```powershell
python casezero.py intake `
  --input "D:\RedCat\CaseZero\raw" `
  --output "D:\RedCat\CaseZero\intake" `
  --case-id "REDCAT-CZ-001" `
  --custody-mode "redcat_local" `
  --as-of "2026-09-01T12:00:00Z"
```

The runner makes no network calls, copies no source files, and emits no matched credential or PII values. It produces a source manifest, case state, ten-row analysis queue, missing-evidence projection, and SHA-256 ledger.

Run its regression suite with:

```bash
python -m unittest -v test_casezero.py
```
