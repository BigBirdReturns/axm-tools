# Validation ledger

Release: `polybolos-evidence-contract/2.0.0`

## Constitutional result

The public surface records Mark Brown’s presentation-integration transaction as `COMPLETE` and the bounded fifteen-decision allowlist scenario as `PASS`. It does not calculate a retrospective global gate score, mark the handoff acceptance-ineligible, or allow a later qualification plan to alter the completed receipt.

`CONSTITUTION.md` is the governing contract.

## Source-bound result

The direct producer trace records 54 timestamped events, 15 decisions, 10 `AUTHORIZE` outcomes, 5 `SAFE_DENY` outcomes, zero observed mapping deviations, an exact 25,505 ms partition interval, communications restoration, Standing Orders deactivation, and acknowledgment through sequence 15.

The accompanying producer report supplies broader claims about authority, operator presence, local-link state, lease behavior, negative controls, and reconciliation. Those remain attributed claims unless a prospective plan is selected and its frozen evidence requirements are met.

## Public application identity

The committed public loader reconstructs one exact sanitized standalone from seven same-origin gzip/Base64 transport fragments in the order `[0, 1, 3, 4, 5, 6, 2]`.

```text
reconstructed bytes    117,546
reconstructed SHA-256  4beaae5aec641a3f0ba3f3e6c7d6c44b3ba2284b0b70ec50e34c24b73475543f
gzip bytes              32,620
gzip SHA-256            4e023932215a726e4a95106237af5f66e57724fc19736f400a6e2da8ef21e1a1
```

The reconstructed application contains the six coordinated views `Show`, `Receipt`, `Evidence`, `Improve`, `Intake`, and `AXM`. It makes no automatic network request.

## Custody split

The current public tree and public runtime contain a sanitized normalized cartridge rather than Mark’s original source files. The former public example paths have been removed. Public exports omit a `sources/` directory. Private exports include original source bytes only after explicit local opt-in.

Historical Git commits prior to this release are outside the current-tree guarantee and require a separate history-rewrite transaction if permanent purge is ever required.

## Automated checks

`polybolos/tests/public_contract_test.py`:

- reconstructs the committed standalone and verifies both transport and standalone identities;
- requires the completed handoff and bounded scenario pass language;
- requires the anti-score and prospective-plan language;
- rejects prohibited global ineligibility language;
- rejects the private raw-log Base64 prefix and exact private event identifier;
- verifies the permanent receipt and optional plan catalog;
- confirms the former raw example paths are absent.

The Pages artifact must be independently downloaded after merge and compared against the same reconstructed identity before the release is called deployed.
