# Case Zero Data Handling Boundary

## Default custody

`redcat_local` is preferred. RedCat runs the deterministic intake and retains the raw engagement corpus. Tier Desk may receive manifests, selected redacted excerpts, or a supervised read-only view.

## Permitted transfer

A redacted transfer contains only the evidence required for qualification. Client names and personal identifiers should become stable aliases. Dates, sequence, roles, commercial amounts, effort, and technical relationships may remain when necessary to the test.

## Do not send

- passwords, API keys, access tokens, private keys, cookies, or connection strings;
- production database dumps;
- protected health information;
- unnecessary personal addresses, phone numbers, or identity documents;
- proprietary source code beyond the bounded review scope;
- live client credentials or authority to contact the client.

## Source code

The first qualification does not require an entire repository. Prefer commit metadata, relevant diffs, tests, acceptance records, and selected interfaces. When full source is necessary, keep it under RedCat custody and provide bounded read-only access.

## Incident rule

A credential-shaped source places the intake in `HOLD_REDACTION_REQUIRED`. The browser and runner record the file and signal class, never the matched value.

## Output boundary

External pre-read and meeting materials contain aliases, evidence coordinates, ranges, and conclusions. Raw client evidence remains under the agreed custody mode.
