# Validation ledger

Release: `polybolos-partition-authority/1.1.0`

## Source identity

- `standing_orders_proof_20260802_215108.log`
  - SHA-256: `fd408eac2c7743e7cc17058242a5b5ecbc8baaf6441c7af826aa7db2512bb575`
- `Standing_Orders_Partition_Epoch_Report.html`
  - SHA-256: `2217491042db3001b21c60dce55e9d82156ffe862b9e34768004e46f7e81685a`
- exported standalone source
  - bytes: `119161`
  - SHA-256: `e292cea1e66579858c22f9eb27f0cb7344ddc2c57f83c3bd011d1d0d140fde55`

## Static deployment transaction

The GitHub Pages entrypoint loads three same-origin Base64 payload parts, joins them, decodes a gzip member, and reconstructs the exact standalone HTML in memory. The payload was independently concatenated, Base64-decoded, gzip-decompressed, and compared byte for byte with the exported standalone.

- payload parts: `3`
- compressed payload: `35703` bytes
- reconstructed HTML: `119161` bytes
- reconstructed SHA-256: `e292cea1e66579858c22f9eb27f0cb7344ddc2c57f83c3bd011d1d0d140fde55`
- byte-for-byte result: `MATCH`
- loader SHA-256: `547d9cb078439093140dfd3f270a8e89939d200c59d467c581ec8cb6f6c4a8c0`

`boot.js` and all three payload scripts pass `node --check`. The loader CSP permits only same-origin scripts, blocks network connections, and hands control to the reconstructed standalone. The standalone CSP blocks network requests while allowing its embedded application logic and local blob/data exports.

## Browser qualification

The standalone was exercised in headless Chromium with no console errors and no network requests. The worked fixture produced:

- 2 source objects
- 54 normalized events
- 15 decisions
- 10 `AUTHORIZE` decisions
- 5 `SAFE_DENY` decisions
- 16 classified claims
- all five views operational: Show, Scenarios, Evidence, Intake, and AXM

The file-intake path was also exercised with structured JSON and an opaque binary. Both were admitted, hashed, and represented without inventing unsupported semantics. Export tests produced normalized JSON, a standalone HTML snapshot, and a portable ZIP containing source bytes, manifest, checksum ledger, normalized evidence, README, and a reopening standalone.

## Evidentiary boundary

The direct trace qualifies the admin-injected `SO_CHROME_TEST` event sequence. It does not directly qualify Lattice auto-detection, local-link state, operator presence, signed authority, lease issuance or expiry, process-restart retention, node-signed journaling, human disposition, operational command, targeting, engagement, or combat effects. Report-only statements remain classified as assertions or conflicts rather than being promoted into observations.
