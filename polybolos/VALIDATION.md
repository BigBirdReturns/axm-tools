# Validation ledger

Release: `polybolos-evidence-contract/2.0.0`

## Constitutional result

The public surface records Mark Brown’s presentation-integration transaction as `COMPLETE` and the bounded fifteen-decision allowlist scenario as `PASS`. It does not calculate a retrospective global gate score, mark the handoff acceptance-ineligible, or allow a later qualification plan to alter the completed receipt.

`CONSTITUTION.md` is the governing contract.

## Source-bound result

The direct producer trace records 54 timestamped events, 15 decisions, 10 `AUTHORIZE` outcomes, 5 `SAFE_DENY` outcomes, zero observed mapping deviations, an exact 25,505 ms partition interval, communications restoration, Standing Orders deactivation, and acknowledgment through sequence 15.

The accompanying producer report supplies broader claims about authority, operator presence, local-link state, lease behavior, negative controls, and reconciliation. Those remain attributed claims unless a prospective plan is selected and its frozen evidence requirements are met.

## Public application identity

The committed `polybolos/index.html` is the public and offline application. It is served directly, with no build, payload reconstruction, Base64 transport, gzip decompression, external script, or automatic network request.

```text
direct bytes    117,546
direct SHA-256  4beaae5aec641a3f0ba3f3e6c7d6c44b3ba2284b0b70ec50e34c24b73475543f
```

The application contains the six coordinated views `Show`, `Receipt`, `Evidence`, `Improve`, `Intake`, and `AXM`.

## Custody split

The current public tree and public runtime contain a sanitized normalized cartridge rather than Mark’s original source files. Public exports omit a `sources/` directory. Private exports include original source bytes only after explicit local opt-in.

Historical Git commits prior to this release are outside the current-tree guarantee and require a separate history-rewrite transaction if permanent purge is ever required.

## Automated checks

`polybolos/tests/public_contract_test.py`:

- verifies the direct file’s exact byte count and SHA-256;
- requires the completed handoff and bounded scenario pass language;
- requires the anti-score and prospective-plan language;
- rejects prohibited global ineligibility language and loader machinery;
- rejects private raw-log markers;
- verifies the permanent receipt and optional plan catalog;
- confirms the former raw example paths and legacy loader files are absent.

CI extracts every inline JavaScript block from the direct HTML and runs `node --check` on each block.

The Pages artifact must be independently fetched after merge and compared with the same direct identity before the release is called deployed.
