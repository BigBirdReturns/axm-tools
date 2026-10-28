# Atmark catalogue workshop

A working, independent storefront preview and reusable catalogue/photo workshop,
made for Atmark to keep. No pitch, account, subscription, analytics or seller
credentials. This is not the seller's operating store. The original eBay item
links remain the purchase and terms boundary.

## Run the delivered site

Unzip the toolkit, then from the directory containing `atmark/` run:

```sh
python -m http.server 8000
```

Open `http://localhost:8000/atmark/`. The site needs HTTP/HTTPS because it reads
its catalogue JSON. The code uses no frontend packages or build step. Existing
seller image URLs are external references, not bundled merchandise photographs.
The local photo studio and CSV imports never upload files.

## What the real run covers

The retained public-web observation packet contains 53 unique listing IDs.
These are actual observed listing records, not synthetic examples. Accessible
store snapshots reported incompatible catalogue totals (659 and 1,665), and
the direct automated store fetch returned HTTP 403. No protection was bypassed;
no complete-store denominator, conversion rate, inventory valuation or sell-
through claim follows. Source extraction came through the explicit observed
input seam, not an authenticated API response. Retained original fields carry
their source URLs and timestamps. The capture is dated, not a live price feed.

The run captured 29 image associations, including one shared-URL collision,
from 28 unique seller-image URLs. Original bytes were retained in the private
capture cache; public `data/media.json` carries their SHA-256, size, dimensions
and exact URL. The site displays those existing URLs. No photograph was
fabricated, retouched to hide condition, or promoted into actual-unit proof.
The 3650 listing's 3630 photograph is withheld rather than replaced with a guess.

Two model-level corrections are supported by Intel's W-1350P specification:
Rocket Lake rather than Emerald Rapids, and FCLGA1200 rather than Socket P.
Other findings remain review tasks: clock wording, a Gold colour field, OS
support disclosure, low-resolution sources, SSD inclusion ambiguity, conflicting
price observations and a followed listing marked out of stock. Title-level OS
siblings are grouped for inspection without merging listings or stock.

## Replay the catalogue and exports

Python 3.10+ and its standard library are sufficient:

```sh
python atmark/scripts/catalog.py build
python atmark/scripts/catalog.py verify
python atmark/tests/test_catalog.py
python atmark/scripts/package.py --out atmark-toolkit.zip
```

`build` retains original records and proposes a presentation. It writes the
normalised catalogue, review CSV, source-bound change plan and shot queue.
`verify` checks the input packet, item accounting, unchanged prices, image
hashes when local files exist, and the no-live-write / partial-coverage boundary.
The CSV is a review document, deliberately NOT an eBay upload template.
A successful schema or hash check does not certify physical merchandise.

### Bring seller-authoritative records

```sh
python atmark/scripts/catalog.py import-csv seller-export.csv --out next-observed.json
python atmark/scripts/catalog.py build --input next-observed.json --media empty-media.json --out next-review
```

An absent `empty-media.json` means no borrowed photo associations. Supported
columns include Item number/Item ID, Title, Current price/Start price, Currency,
Custom label/SKU and Available quantity. Every mapped row retains the original
row and file hash. Invalid rows have explicit dispositions; the browser also
reports duplicate IDs separately. Imported quantities remain seller-reported,
not warehouse-confirmed. The browser import table is local session state until
exported; it never replaces the published baseline automatically.

### Optional official public discovery

An authorised eBay developer application token can enable the read-only Browse
API adapter. Credentials come only from the process environment:

```sh
# Supply EBAY_APP_TOKEN through the operator's normal secret manager.
python atmark/scripts/catalog.py browse --category 58058 --out api-capture
```

This adapter is implemented but NOT live-qualified in this delivery: no eBay
application token was supplied. It pins the API host and seller filter, retains
response bytes/hashes, paginates within the API window and records category
scope. Category search is not a seller inventory export. It never writes,
creates, revises or ends an eBay offer. A missing token exits as blocked, not
as a successful empty catalogue. The endpoint and token permissions may change;
verify against eBay's official Browse API documentation before integration.

### Images and the preparation boundary

```sh
python atmark/scripts/catalog.py collect-media --input next-observed.json --out photo-cache --manifest photo-manifest.json
```

The collector accepts only HTTPS on the exact eBay image host, applies a byte
limit and per-request delay, caches by source URL, verifies cached content,
and stops on 401/403/429. Originals are content-addressed. A capture record is
provenance, not a licence or actual-unit verification. Obtain rights before
rehosting images commercially. A deliberately refreshed capture should use a
new run directory; do not erase older evidence to make the latest image fit.

The browser photo studio accepts an operator's own JPEG/PNG/WebP. It supports
full-frame proportional sizing or an explicit centre-square crop and right-angle
rotation. It does not enlarge beyond source dimensions. It exports the untouched
original, a prepared PNG, and a review/recipe file whose hashes bind both.
Identity and presentation require separate operator assertions and a note;
changing the subject, source or framing clears both assertions. Exports remain
`prepared-not-published`. A self-attestation is not independent audit evidence.

## Files and ownership

Human/observer-owned: `data/observed.json`, source-supported correction rules,
this documentation and UI. Capture-owned: `data/media.json`. Generated:
`data/catalog.json`, `data/listing-review.csv`, `data/change-plan.json`,
`data/photo-queue.json`. Qualification records are generated by actual tests.
Nothing changes on a timer. Re-run acquisition deliberately and inspect diffs.
Do not place credentials, private exports, customer data or raw warehouse labels
in this public repository; its entire root is deployed.

## Tests and current acceptance

`data/qualification.json` records the actual delivered test scope. The standard-
library tests replay the real capture and exercise identity, price, source,
duplicate, formula-injection, URL and approval boundaries. Native Chromium tests
exercise search, comparison, imports, exports, photo preparation, hash/ZIP
integrity and 320/390/768/1440px layouts. The browser harness uses Playwright
as a QA-only dependency, not a site/runtime requirement. Its image requests are
intentionally blocked; successful real image retrieval has separate capture
receipts, and live publication is checked independently.

```sh
python -m pip install playwright
playwright install chromium
# Set CHROMIUM_PATH to the installed Chromium executable when needed.
python atmark/tests/browser_test.py --out /tmp/atmark-browser-check
```

## What can rot

External seller-image URLs can disappear: the card visibly falls back to
"Source image unavailable". Listing prices, stock and titles can change: the
snapshot date stays prominent and purchases route to the source listing.
Seller CSV headers and API formats can change: inspect rejected rows and never
turn absent values into zero. A third-party photo's identity or rights can be
wrong: hold or replace it with a source-backed decision, retain the predecessor.
Browser memory is bounded but large images still consume resources. Restore the
plain files on any static host; there is no proprietary database to recover.

## Publication / rollback

This self-contained directory uses the existing axm-tools Pages publisher.
No seller-facing write service exists. A source change is a new Git commit;
reverting only that scoped commit restores the previous public version without
touching other tools. Source data, display data and test receipts remain separate.
The original code is MIT-licensed; third-party names and photographs retain their
existing rights. Atmark can take, modify and host the code without contacting us.
