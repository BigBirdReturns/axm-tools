# Manzanita external campaign evidence runner

This package is the local-first operating instrument for the ten campaigns that control Manzanita public release. It makes the remaining evidence work executable without treating software, a green workflow, a complete form, or a synthetic fixture as proof that a physical, human, private, provider, field, archive, endpoint, or rollback campaign occurred.

The campaign operator owns the observation. The evidence custodian owns source bytes, rights, retention, and visibility. An affected actor owns acceptance or refusal where applicable. Provider, field, deployment, and release authorities retain their own lawful decisions. The runner may create and verify a receipt. It may never borrow another actor’s authority.

## Commands

`campaign_runner.py` provides seven transactions:

```text
init
add-evidence
observe
status
finalize
verify
propose-ledger
qualify
```

`init` creates one empty, held workspace from `CAMPAIGN_CONTRACT.json`. It records the exact campaign definition, accountable operator, actual venue, versioned procedure, start time, and receipt visibility.

`add-evidence` hashes one operator-controlled file and records its evidence class, actor, time, rights, claim scope, visibility, and opaque locator. The local path is retained only inside the operator workspace. It is removed from every public receipt.

`observe` records one contract-admitted observation type with its actor, object, mechanism, result, notes, and evidence references. Unknown evidence, observation classes, and duplicate identities are rejected.

`status` reports every missing observation type, missing evidence class, absent file, failed digest, nonpassing observation, and observation without evidence.

`finalize` emits `PASSED`, `FAILED`, `HOLD`, or `ABORTED`. `PASSED` is refused unless every required observation and evidence class exists, every retained local byte still matches its digest, every observation passes, every observation cites evidence, and acceptance and failure disposition are complete.

`verify` checks the receipt payload checksum, public-boundary keys, evidence-manifest checksum, authority firewalls, and optional evidence-root readback.

`propose-ledger` turns one passed receipt into a separate proposed one-row ledger update. The proposal remains `PROPOSED`, preserves release `HOLD`, requires release-authority review, and grants neither canonical ledger mutation nor public-release authority.

`qualify` proves that the runner contract and canonical release ledger share the same ten identities. It reports the ledger’s actual passed and open campaigns without performing or promoting any campaign.

## Private evidence

Private source bytes should remain in an operator-controlled workspace outside Git. A public receipt contains only the evidence identifier, class, basename, media type, byte count, SHA-256, observation time, actor, rights, claim scope, visibility, and opaque locator. A `private_controlled` item can therefore be reviewed without copying its source bytes into the repository or a public artifact.

Do not put addresses, resident identities, credentials, tokens, passwords, secrets, private keys, raw evidence, or file contents into a public receipt. The verifier rejects those keys even when the receipt checksum is otherwise valid.

## Example initialization

```bash
python manzanita-next/external-campaigns/campaign_runner.py init \
  --campaign-id M99-PHYS-DEVICE-001 \
  --workspace /operator-controlled/manzanita-device-campaign \
  --operator "Accountable device operator" \
  --venue "Named physical device and room" \
  --procedure "Manzanita real-device campaign" \
  --procedure-version "1.0.0" \
  --started-at "2026-08-17T00:00:00Z" \
  --receipt-visibility private_controlled
```

The controlling question is whether an accountable operator can perform one named campaign, retain every required observation and evidence class, verify exact bytes, record acceptance and failure disposition, and produce a receipt that release authority can review without exposing private evidence or manufacturing standing that the campaign did not earn.
