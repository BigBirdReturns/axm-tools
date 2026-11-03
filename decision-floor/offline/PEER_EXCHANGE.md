# Decision Floor: sovereign peer exchange (candidate 0.3)

This is an offline file-based recorder-to-recorder protocol. Each party owns an
independent source vault and private signing key. Neither party uploads its
ERP exports, private source files, investigative history or private signing
key to the other. A signed envelope discloses only the event fields admitted
by a local reciprocal contract. The receiving party verifies it against an
**out-of-band pinned** public key, compares identical recorded observations,
and preserves the original signed statement even when the local record differs.

This protocol uses Ed25519 through a locally installed **OpenSSL 3+**
executable. Set `DF_OPENSSL` to its path if it is not discoverable. On
Windows, a supported default is the local Git for Windows OpenSSL binary at
`C:\Program Files\Git\usr\bin\openssl.exe`. The Decision Floor ingestion
and reconciliation engine remains Python-standard-library-only, and no
network/socket access is used in peer exchange. AXM Genesis hybrid
attestation is a separate, stronger cryptographic acceptance boundary.
An Ed25519 signature establishes only continuity with a locally pinned
signing key; it does not authenticate the original ERP entry, timestamps,
business authority or intent.

## Demonstrate the complete interaction

Run from this extracted kit:

```sh
python tools/peer_replay.py --output my_peer_demonstration.json
```

The script creates **two independent temporary identity/vault roots**, each
ingests a separately preserved synthetic history, makes the same PO revision
differ by quantity, explicitly enrolls its counterparty key and scoped
contract, exchanges a signed, hash-only evidence claim and receives a
separately signed human-review declaration. A tampered packet is refused.
All private demo keys are deleted when the test finishes. The resulting JSON
contains receipt hashes, match/mismatch states, no private source data and
clear qualification boundaries.

## Apply to authorized customer evidence

1. Ingest authorized exports separately in each organization's environment
   using the existing `decision_floor run` or the local console. Keep each
   `evidence.sqlite3` and `vault/objects` under its own private filesystem
   and service identity.
2. Create identities locally. Only the **public.pem** file and its
   independently verified fingerprint cross the organizational boundary.

```sh
python -m decision_floor.peer init --root /private/recorder-a --party supplierA
python -m decision_floor.peer init --root /private/recorder-b --party buyerB
python -m decision_floor.peer trust --root /private/recorder-a --party buyerB --key /authorized/b-public.pem
python -m decision_floor.peer trust --root /private/recorder-b --party supplierA --key /authorized/a-public.pem
```

3. Each party installs its own contract JSON, with complementary
   `party`/`counterparty` values. Each must agree on exactly the same
   `contract_id`, case scope and fields. The contract is a *local disclosure
   allowlist*, and any attempted scope or field change requires a new
   contract identity. One example for the supplier is:

```json
{
  "schema": "axm-decision-peer-contract/1",
  "contract_id": "evaluation-Q4",
  "party": "supplierA",
  "counterparty": "buyerB",
  "scope": {
    "site": "PLANT-07",
    "sku": "VALVE-P204",
    "period": "2026-10"
  },
  "allowed_kinds": ["decision", "commitment", "floor"],
  "allowed_fields": [
    "kind", "record_id", "quantity", "occurred_at", "recorded_at",
    "source_digest", "locator"
  ],
  "max_records": 50
}
```

```sh
python -m decision_floor.peer contract --root /private/recorder-a --file /authorized/supplier-contract.json
python -m decision_floor.peer export --root /private/recorder-a --workspace /private/source-a --contract evaluation-Q4
```

The export returns the path of one signed JSON packet. Transfer that one
file using the parties' approved transport. Receipt is an explicit local
import, **not a call into a vendor system**:

```sh
python -m decision_floor.peer receive --root /private/recorder-b --file /received/signed-packet.json --workspace /private/source-b
```

The receiver checks the contract, local key pin, signature, hash, recipient,
scope, per-record field allowlist, and prior packet chain. A difference at
the same record ID and occurrence time is reported as
`CONTRADICTORY_RECORDED_VALUE`. An unmatched remote observation becomes
`NO_IDENTICAL_LOCAL_EVENT`, not a fabricated contradiction. Receipt never
modifies an ERP, PO, MES or local source event.

4. An authorized person can explicitly issue a *declared review*:

```sh
python -m decision_floor.peer review --root /private/recorder-b --reply-to <original-packet-sha256> --disposition contested --authority "Procurement controller"
```

The resulting signed review packet returns through the same approved channel.
The original source statement and conflicting evidence remain intact.
The authority string is a signer's declaration, **not proof of actual
enterprise role or permission**. Production admission would require an
organization-controlled key, separation of signer and human approval, and
verified authorization workflow.

## Evidence boundary and acceptance

- **Shared:** contract scope, selectively allowed event fields, hashed source
  references and signed receipt chain. Even hashes and identifiers can disclose
  business-sensitive relationships; contract admission must account for them.
- **Local:** full source bytes, original correspondence, unselected evidence,
  private signing keys, customer data, and operational source-system privileges.
- **Claim established:** a locally pinned key signed this exact disclosure,
  the packet has not been altered, and its declared observations can be
  compared against the receiver's independent records.
- **Claim not established:** the signer's original source was truthful or
  complete, its clock was externally trusted, the signer had business authority,
  a mismatch was negligent, or disclosed hashes prove an unseen file's
  contents. Each recorder can still withhold a record or fork a separate
  history; cross-party acknowledgments expose observed differences, not
  absolute completeness.
- **Terminal conditions:** reject altered signatures, unpinned identities,
  stale predecessors, unauthorized scope/fields, conflicting contracts,
  corrupt source vaults, and unmatched review references. Preserve the
  signed envelopes and review history; operational changes always remain
  separately authorized human actions.

This is a **qualified synthetic boundary**, not a real Aankhen or fiChains
integration, an authenticated enterprise counterparty, or a legal liability
determination.
