# SCHISM

SCHISM is an operator-owned application stack for keeping programs, data and operating history usable through supplier changes. Its public site is https://bigbirdreturns.github.io/axm-tools/schism/.

The front page explains the purpose and gives visitors a practical application to run. The controller installs on the operator's own machine. The hosted site serves static files and downloads; application data stays in the operator's environment.

## Current entry points

| Path | Purpose |
| --- | --- |
| `index.html` and `style.css` | Product introduction, downloads and links to the application and original argument. |
| `guide.html` | Setup, application contract and current operating boundaries. |
| `evidence.html` | Qualification records, exact release source and checksums. |
| `fieldnotes.html` | Useful local application and its continuity walkthrough. |
| `stack/` | Accepted SCHISM Stack 0.1.1 source, instructions, licence and qualification. |
| `downloads/` | Versioned controller distributions, source and offline dependency kits. |
| `v2/` | Earlier executable exit-test exhibit and independent receiver. |
| `SCHISM-v1.2-offline.html` | Source-backed public edition of the Darkhive/FleetForge dossier. |

The landing page and companion pages are maintained directly as static HTML and CSS. Source and download changes belong to a new qualified release. Keep existing versioned archives and their accepted source inventories unchanged. The source runtime, native distributions and application examples each retain the conditions under which they were tested; a new front page does not broaden platform or application compatibility.

## Dossier origin and retained edition

Jonathan Sandhu privately circulated the original SCHISM dossier on 26 June 2026. Public edition 1.2, dated 26 November 2026, preserves its central customer-control argument and ten-part organization, credits FleetForge's software-delivery direction, and adds primary sources and explicit evidence boundaries. It covers ownership, sourcing, procurement and support continuity. Private correspondence, contractual terms and operational implementation material remain outside the public edition.

Read [the complete offline HTML](SCHISM-v1.2-offline.html) in a browser, [the readable text](SCHISM.md), or [the public edition package](SCHISM-v1.2-public.zip). The HTML contains the text, navigation and original editorial artwork; external references require a connection. `sources.json` records the dated source review and `provenance.json` distinguishes the original private artifact from this public edition. The original artwork is identified as AI-generated. The retained chronology establishes prior existence of the argument; it supplies no independently verified predictive lead or claim that Darkhive rejected it.

## Reconstruct the historical dossier

Extract `SCHISM-v1.2-public.zip` into a separate directory outside this publishing checkout, enter its `SCHISM-v1.2` folder, and run:

```console
python build.py
```

The included builder uses the Python standard library and the extracted `content.json` and `assets/cover.png`. It writes `index.html`, `README.md`, the offline edition, source/provenance records, the release package and checksums beside itself. Run it only in that isolated edition directory so its historical outputs remain separate from the current product front page. Review a revised dossier as a new edition while preserving the existing artifacts.

The top-level `SHA256SUMS` belongs to the original public dossier reconstruction, including the index and README shipped in its ZIP. Use `downloads/SHA256SUMS` for the released application-stack archives and the exact inventories inside each source or native archive for their contents.

## Rights and maintenance

The application stack uses Apache-2.0; see `stack/LICENSE` and `stack/NOTICE`. Authored dossier analysis is © 2026 Jonathan Sandhu; linked sources retain their respective rights. Darkhive is the subject of the independent research. Source dates, company statements, author analysis and observed software behavior keep their separate evidentiary roles.

Verify changed pages in a browser, check their actual download and navigation targets, and preserve the repository's existing Pages publication route. Keep private correspondence, credentials, operator state, native machine paths and raw qualification logs outside the publication tree. External references may change; a new review date requires a new source review.

