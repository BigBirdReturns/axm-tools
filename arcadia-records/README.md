# Arcadia / Santa Anita LA28 public records

Independent source-linked records archive. Static HTML works without a build step or JavaScript. `app.js` adds library filters only.

## Evidence and custody

Original production ZIPs and PDF bytes are in `records/`; per-occurrence metadata in `data/catalog.json` preserves receipt context, hashes, duplicates and parent archives. Public correspondence in `transcripts/` is explicitly derivative and omits personal contact information, routing headers and quoted history. Private originals, Gmail identifiers, credentials and automation state do not belong in this directory.

All page references are physical PDF page numbers. The 136-page biological report contains a 100-page arborist Appendix A at pages 27–126, plus further appendices. Text extraction does not replace visual source inspection. Preserve City redactions.

## Maintenance

New receipts must pass scope, retrieval, integrity, extraction, review and publication checks in that order. Preserve originals and version differences. Update the catalog, findings, timeline, request coverage, version and change log together. Never label a production or category complete merely because files arrived. Files received but not yet reviewed must retain that status. Do not imply legal, ecological or engineering validation from document processing.

Run `python arcadia-records/scripts/validate.py` from the repository root before publication. After deployment, verify the unauthenticated page and every document URL; compare returned SHA-256 with the catalog. Use the repository's existing Pages publisher, preserving unrelated site content.

## Rights

This archive republishes records supplied through the City's public-records process and materials captured from official public sources. Original documents retain their authorship and any stated notices. Public disclosure does not imply that every third-party component has been dedicated to the public domain. No blanket license is asserted over original source records.
