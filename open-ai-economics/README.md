# Who captures the value of open AI?

Free research edition, 19 September 2026, version 1.0.

Open `open-ai-economics.pdf` for the seven-page report, or open
`open-ai-economics.html` in a browser for the report and editable calculator.
The HTML works as a standalone file: no server, account, API key, external
script, font download or live-data connection is required. External source
links open only when clicked.

The calculator compares (fixed cost + submitted jobs × variable cost) /
(submitted jobs × verified success fraction). It applies a separate minimum
success-rate gate, computes the positive-volume crossover when one exists,
and exports the assumptions and results as JSON. All starting values are
hypothetical. It does not perform a benchmark or model capacity steps,
correlated retries, failure losses, security constraints or contracts.

## Contents

- `open-ai-economics.pdf`: printable report, provenance and source notes.
- `open-ai-economics.html`: self-contained report and calculator.
- `open-ai-economics.md`: editable report text and linked citations.
- `calculator.js`: the same JavaScript embedded in the HTML.
- `sources.json`: fourteen source entries with dates and evidence limits.
- `evidence.json`: manually extracted, attributed observations, not a raw dataset export.
- `example-scenario.json`: the default calculator scenario exported by the browser.
- `source-verification.json`: the original delivered report verification receipt.
- `verification.json`: publication-specific browser and arithmetic checks.
- `index.html`: hosted entry with directory navigation and download links.
- `post.txt`: accompanying public-reply copy.
- `SHA256SUMS.txt`: checksums of the delivered files, excluding the checksum file itself.

The report identifies the subject through Social Capital's public preview.
The subscriber-only report was not accessed or reproduced. This is independent
analysis of the topic, not a summary or assessment of the unseen paid PDF.

The material is provided free to read and share. Referenced publications retain
their own rights. Extracted Vercel observations are attributed under Vercel's
stated CC BY 4.0 data license. No real model evaluation or infrastructure security
test was conducted. See the report's provenance section for the full boundary.

The browser version was tested at desktop and mobile viewport sizes. Tests
covered the worked example, one-million-job scenario, changed acceptance gate,
invalid inputs, identical cost functions, a dominated alternative, reset and
JSON export. No automatic external requests or JavaScript page errors were
observed. These tests validate the calculator, not its assumed real-world inputs.

## Hosting, ownership and maintenance

Public entry: https://bigbirdreturns.github.io/axm-tools/open-ai-economics/

GitHub Pages serves this directory directly. There is no build step, scheduled job, live-data feed or runtime dependency. All files are steward-owned. Calculator inputs stay in the browser; export occurs only at the reader's request. Observations are a dated September 2026 snapshot.

### What can rot

Citations can move and source observations, prices and capabilities can change. Refresh substantive claims in a dated revision with an updated source ledger. The calculator remains usable with reader-supplied inputs; its constant-cost assumptions and separate quality gate remain explicit. Recheck downloads and calculator behavior after editing.

### Publication boundary

The standalone HTML, report Markdown, calculator and source/evidence ledgers preserve their delivered bytes. The hosted entry adds navigation, metadata and downloads. The PDF is rendered from the unchanged standalone HTML for this publication. The original verification receipt describes the earlier delivered artifact; verification.json records publication checks.

The hosted PDF uses 0.92 print scale with Windows font metrics; the report content is unchanged. The publication PDF contains seven pages and 32 links.
