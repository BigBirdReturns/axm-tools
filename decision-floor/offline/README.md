# Decision Continuity: local evaluation kit 0.3.0

Independent AXM evaluation aligned to the publicly described fiChains workflow. Synthetic examples are labeled. This is not an Aankhen release or a proprietary fiChains integration. The public page is the interactive entrance; this folder is the source-distributed local investigator. Python 3.10+ is required. No pip packages, cloud accounts or model credentials are required for the core.

## Start locally

Windows: extract the complete download, then run `LAUNCH_WINDOWS.cmd`.
macOS/Linux: run `sh launch_linux_macos.sh`.
Direct: `python app.py serve --project local_customer`.
The process prints a token-protected 127.0.0.1 browser address. Enter approved exports, inspect their profiles and explicitly review source mappings before scanning. Input, evidence, reports and review history stay local. Stop the process with Ctrl-C. Source business systems remain read-only.

## Verify first, then bring new evidence

`python qualify.py --out ../verification.json` rehashes the distribution, runs 22 Python regression/API tests and 1,000 newly generated synthetic cases by default. `python tools/novel_case_oracle.py --cases 1000 --seed 931527` replays the stated seed. A new seed changes the artificial cases; this qualifies mechanics, not accuracy on customer data.

Run the missed case with `python -m decision_floor run --input sample_inputs/missed --config config/sources.json --workspace local_missed_state --out local_missed_report`; use a distinct workspace for `sample_inputs/closed`. Generated reports are created on demand rather than shipped as stale screenshots. Open `local_missed_report/index.html` or import `decision_floor_report.json` into the public workflow viewer using its local file picker. Original source bytes remain in the local evidence vault. For sensitive material, open the bundled `workflow/index.html` completely offline instead of using a hosted page.

## Input and unattended execution

The engine accepts reviewed CSV/JSON/JSONL structured exports and searchable EML, text, HTML, DOCX and XLSX. Text PDF support requires a separately approved local pypdf installation; scanned OCR is unqualified. `config/sources.json` declares file patterns, source identity, record kinds, field mappings and authority. Site, SKU and period match exactly. The investigator skips unknown mappings instead of inferring operational facts from arbitrary prose.

After configuration, `python -m decision_floor watch --input /approved/exports --config config/sources.json --workspace /private/state --out /private/report --interval 60` rescans without consulting the creator. The customer controls the service identity, folder rights and retention. No schedule, account or background process is installed automatically.

## Evidentiary floor

Preserve exact original bytes, versions, approval and quoted commitments. Event time, source-recorded time and investigator intake are separate. Missing observations remain missing; statements remain statements. The first received observation bounds detection and does not prove who knew or acted. Conflicting source values withhold quantitative conclusions. Stock above a recorded policy at an explicit unit book cost is book value, not realized loss or demonstrated causal savings. SHA-256 checks local byte continuity, not original truth, authority or timestamp authenticity.

## Boundaries

This release has no live ERP connector, proprietary fiChains data, general autonomous semantic entailment, scanned OCR, enterprise SSO/ACL inheritance, source-signature verification, trusted timestamp authority or causal attribution. The local web console uses the customer's filesystem permissions and a token; it is not a multi-user enterprise access-control service. Private exports and investigation results must stay inside the customer's chosen boundary.

## Layout

`decision_floor/` owns extraction, search, reconciliation and report generation. `app.py` and `ui/` are the local console; `tests/` and `tools/novel_case_oracle.py` provide portable checks. `sample_inputs/` contains only authored synthetic exports. `workflow/` is the new public-facing replay copied for offline use. `MANIFEST.json` is generated for the complete distribution. Original engine version 0.2 is retained; distribution 0.3.0 changes presentation, delivery and packaging.

## Optional sovereign peer exchange

The independent file-based exchange uses each organization's own original source vault and signing key, a manually pinned counterparty public key, and a local contract governing disclosed fields. An Ed25519 packet can be compared with another organization's matching operational records; returned human dispositions remain signed statements, never source-system writeback. Requires a local OpenSSL executable for the peer exchange only. Core ingestion and investigation remain stdlib-only. Run `python tools/peer_replay.py --output /private/synthetic-peer-receipt.json` to exercise two fresh independent synthetic recorders. Read `PEER_EXCHANGE.md` for contract setup, explicit disclosure, limits and the exact CLI path.
