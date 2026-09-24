# axm-tools — notes for Claude sessions

Read the root `README.md` first: it defines the repo's conventions (one
self-contained tool per directory, stdlib-only Python, committed-JSON state,
Pages deployed from the fetch workflow). Those conventions are deliberate —
don't add dependencies, build steps, or shared libraries to "improve" things.

Before any structural decision (new directory, changed convention, platform
work), read **`CONTINUITY.md`** — the long-horizon handoff document. It
separates the invariants from the parts that are allowed to rot, and it is
written for whoever maintains this repo next, human or model. This file is
the *quirks ledger* that CONTINUITY.md §8 refers to: when you verify a new
fact about the outside world, add it below and date it.

## Ground rules

- **Python is stdlib-only.** No requirements.txt exists on purpose. If a
  task seems to need a package, it needs a different approach instead
  (`pta-tracker/scripts/fetch.py` parses RSS/Atom with `xml.etree` for this
  reason — `feedparser`'s sgmllib3k dependency doesn't even build on modern
  setuptools).
- **`main` is production.** Pages serves the repo root; every merge and
  every nightly data commit redeploys the live site. Don't leave scratch
  files anywhere in the tree — they get published.
- **Machine-owned files:** `*/data/items.json` and
  `pta-tracker/data/archive.json` (append-only overflow of the live feed;
  the page's timeline search depends on it) are written by the nightly
  workflow; hand edits will be overwritten or merged away. The human-owned
  data files are `*/data/observed.json` (out-of-band drop-box) and
  `pta-tracker/data/parent.json` (curated parent-view cards + watchlist).
  The page is deliberately read-only — the owner rejected on-page edit
  buttons that bounce volunteers to a GitHub login; don't add them back.
  Curation = editing parent.json in the repo (web editor or a Claude
  session).

## Testing changes locally

```bash
# sandboxed environments: exports make the proxy CA visible to urllib
SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 pta-tracker/scripts/fetch.py
# then eyeball the site (fetch is relative, so serve the tool dir):
cd pta-tracker && python3 -m http.server 8899
```

Run `fetch.py` against a **copy** of the data dir if you don't want the run
merged into `data/items.json` — the script merges into whatever is on disk,
and `first_seen` stamps are permanent once committed.

## Known quirks (verified, not guesses)

- **EdSource 403s** every request from datacenter IPs (GitHub runners
  included), which is why it is NOT in `FEEDS` — its stories arrive via
  the Google News query instead. Don't re-add it without verifying the
  block is gone: a permanently-quiet source in the health line trains the
  owner to ignore real outages.
- **Simbli** (AUSD board agendas) is behind Incapsula and cannot be
  fetched by the Action, ever. The escape hatch is `observed.json` — see
  the root README's "hostile-source seam" section. Don't burn time trying
  to scrape it.
- **Google News search feeds return relevant-not-recent** — items can be
  a decade old, hence the `MAX_AGE_DAYS` window in fetch.py.
- **CA bill numbers recycle every 2-year session** (SB 760 = restrooms
  2023-24, behested payments 2025-26, highways 2021-22). Bill links must
  stay disambiguated by subject-vs-story overlap (`find_bills`); a
  "simplification" to newest-session-wins will link parents to the wrong
  law.
- **The AUSD meeting scraper** reads a human-written schedule page
  (`ausd.net/apps/pages/agenda`, refreshed each summer). If meeting items
  vanish during the school year, that page's format is the first suspect.
- **One dead feed is silent by design** (run stays green; the page's
  per-source health line is the tell). All feeds dead = exit nonzero so
  GitHub emails the owner.
- **Essential Attention release query strings do not select an artifact**
  (verified 2026-08-12). `?v=1.2.0` still served the committed v1.1.0 page
  while `main` contained v1.1.0. Treat the deployed title and SHA-256 as
  authority after Pages publishes; never infer the live release from the URL.

## identity/ (reference area, not a tool — verified July 2026)

- **No workflow, no `data/`, deliberately.** Don't fit it into the tool
  layout. Its internal law is `identity/scg/SCG_MARK_CONSTITUTION.md` —
  read it before touching anything under `identity/`.
- **`releases/` folders are frozen.** Never edit one, even to fix an
  error; a change is a new `vX/` folder. `SCG-Identity-v3.0` is the
  ratified baseline; `v3.1` is the current deployment reference
  (application-layer only: the LinkedIn cover is wordmark-only because
  the avatar already carries the mark — never two dandelions at once).
- **The docs there name paths from the full axm.tools monorepo** (a
  root-level `scg-pixel-mark.js`, `/public/assets/scg/`) that don't exist
  in this repo. Already reconciled via "Deployment scope" notes in the
  living docs — don't "fix" the paths, and don't let a merge overwrite
  those notes (re-apply small edits by hand instead).
- **The mark renders live from `identity/scg/source/scg-pixel-mark.js`**
  (the showcase at `identity/index.html` draws all 79 cells from it).
  Never copy the file elsewhere in this repo, never redraw the mark.

## History worth knowing

Multiple sessions built this in parallel; `git log` on `main` is the
authoritative record. The v1 single-view page was archived, then removed —
recover it from history (`git log --all -- pta-tracker/index-v1-archive.html`)
rather than rewriting it. The `identity/` area landed across PRs #5 and #7
(July 2026); the second exists because a PR merged mid-session strands any
later commits on its branch — a merged PR never picks up new pushes, so
follow-ups need a fresh PR from a restarted branch.

## PTA verification ? September 21, 2026

- AUSD now publishes the board-approved 2026-27 LCAP at
  https://www.ausd.net/apps/pages/lcff and signed adopted budget at
  https://www.ausd.net/apps/pages/index.jsp?uREC_ID=2740474&type=d&pREC_ID=2749824.
- https://www.ausd.net/apps/pages/agenda identifies July 14 as the annual
  reorganizational meeting; the former December watchlist assumption was wrong.
- Legal-card review: AB 3216 names emergency, staff permission, physician
  determination and IEP exceptions (do not label every 504 plan an express
  exception in this act). SB 848 authorizes pupil instruction, rather than
  mandating it for every student. SB 760 has a campus-restroom-count condition.
  Parent cards now point to the primary statutes and avoid claiming locally
  verified implementation.
- Archive overflow is durable state: commit archive.json alongside items.json,
  or fresh CI checkouts will forget earlier overflow after 120 live items.
- Simbli was accessible through the local browser on September 21 after
  automated access failed. September 22 agenda: meeting MID=81149, including
  instructional-materials hearing, teacher-assignment authorization and
  facilities update. The meeting listing showed no minutes links for
  August 25 or September 8; do not infer votes from agenda proposals.

- Follow-up verification September 21: Simbli policy-library search "mobile"
  found adopted BP 5131.8 (June 23, 2026); "smartphone" returned no results.
  The current board roster embeds officer titles in images: Shirley Yee,
  President; Jennifer Vargo, Vice President; Raymond Cheung, Clerk.
- Missing minutes do not end research: official August 25 recording
  vw_1xjT_cBQ confirms consent A-J passed (1:18:12-1:18:31), including ELOP
  plan item F. September 8 recording JhVA193LMkM confirms consent A-D/F-H
  passed (1:24:03-1:24:22), including Proposition 28 annual-report item D.
  parent.json records these evidence types and timestamps; do not describe
  transcripts as signed minutes or annual reports as new spending approvals.

## PTA board-review pilot - September 21, 2026

The officer has not yet shared the tracker with the full PTA board. Do not
infer a scheduled PTA meeting from an intention to share it tomorrow, or turn
the district meeting schedule into an attendance obligation. board-brief.html
provides a suggested sharing message and dated brief; no messages were sent.

The former report button promoted raw feed headlines into a board update.
It now uses only selected source-reviewed cards in parent.json.board_report,
checks its own review deadline, and flags past agenda dates as follow-up work.
Run `node pta-tracker/scripts/test_board_report.mjs` after report changes.

Observed in browser QA: cache-first HTML served the previous report generator
on the first visit after an update. Service worker v2 uses network-first page
navigation, retaining offline fallback. Data refresh never renews curation.

## Compute connection verification - September 22, 2026

A fragment-only navigation to a private local workspace does not reload the document. Consume its connection token on `hashchange` as well as initial load and remove it from the address. Native tests must wait for `CONNECTED` as a prefix: `NOT CONNECTED` contains the same substring. Chromium innerText applies CSS text-transform; qualification badges should be checked semantically, with identity disclosures opened before visibility assertions.

## Compute public release browser check - September 23, 2026 UTC

Ubuntu CI exposed 320px page overflow that Windows native checks did not: compact header controls and connected rows needed natural wrapping under fallback-font widths. Keep the narrow layout wrapping and preserve the page-width assertions; do not hide overflow to satisfy them. The original Hot Aisle URL remains the instrument entry and links to the provider-neutral compute desk. Runner instructions use the executable shipped in the kit, not an assumed npm package.

## Shared-site acceptance closeout, September 23, 2026 UTC

The independent brand's nowrap line widened a 390px DejaVu Sans viewport to 404px. Natural brand wrapping fixes the cause; 320px also needs price-tile labels to wrap. Keep document-width assertions and scrollable ledgers; do not hide document overflow. The fresh-browser journey now downloads and recomputes a report and carries a saved decision through reload. All four current full-site Pages publishers require source-matched product qualification before upload; data-only commits may reuse identical passing source trees.

## First-campaign provider facts - September 23, 2026 UTC

Verified for `hot-aisle/campaign/` (the kit is committed; nothing has been rented or run):
Hot Aisle lists $2.99/GPU-hr for a new-customer MI300X VM, billed by the minute, no stated
minimum deposit; bare metal $3.39 with a one-month minimum; VMs ship with ROCm and Docker and
use key-based SSH. DigitalOcean GPU Droplets list MI300X $2.59 and H100 $4.41 per GPU-hour,
billed per second with a 5-minute minimum; image slugs `gpu-amd-base` (ROCm 7.14) and
`gpu-h100x1-base` (CUDA 13.1, container toolkit); the docs do not state new-account GPU
limits, so the first droplet create is the test. RunPod's MI300X was out of stock; Spheron
($3.59/hr, 20-minute minimum) is the H100 fallback. Pins: Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
at dcaee4d4dfc5ee71ad501f01f530e5652438fde0 (31.2 GB, fine-grained FP8 block 128);
rocm/vllm@sha256:30761c21… and vllm/vllm-openai@sha256:8a69ffad…, both published 2026-09-22.
The runner drives `vllm bench serve` over ssh on the host, so a containerised vLLM needs
`target.vllm_command = ["docker","exec","vllm","vllm","bench","serve"]` and the result dir
bind-mounted; `jobs.normalizePlan` accepts that. Comparator arms on other clouds cannot go
through the runner (adapter must be hotaisle or local; local marks records synthetic); import
their files as supplied evidence instead.

## First campaign, field facts - September 23, 2026 UTC

Verified while running `hot-aisle/campaign/` Runs 1-2:
- vLLM 0.30.0 (`vllm/vllm-openai@sha256:8a69ffad…`) rejects `--disable-log-requests`; request logging is off by default. Its bench prints a notice that default sampling temperature changed; pass `--temperature` explicitly when output content matters.
- `rocm/vllm@sha256:30761c21…` is vLLM 0.27.1-dev and its `--save-detailed` output has no per-request `latencies` array, so the report engine (correctly) holds any E2E gate on those files. `vllm/vllm-openai-rocm:v0.30.0` exists (`@sha256:2e7da1ad…`); `rocm/vllm` is deprecated upstream.
- On vLLM 0.30.0 ROCm with `VLLM_ROCM_USE_AITER=1`, a dense FP8 70B auto-selected `ROCM_ATTN` ("incompatible backend TURBOQUANT … overriding") and `RowWiseTorchFP8ScaledMMLinearKernel`. Always collect `serve.log` and name the selected backend in the record.
- `docker inspect <container>` has no RepoDigests; use `docker image inspect` on `.Config.Image` (arm.sh fixed). `rocm-smi` product names contain tab characters, so escape them before writing JSON.
- DigitalOcean new accounts start at GPU Droplet limit 0; a support ticket raised it to 1 GPU (so arms run one at a time). At ~19:10 UTC, H200 1x was out of capacity in all six GPU regions and MI300X was greyed in NYC2/TOR1. The "AI/ML Ready" NVIDIA image ships nvidia-container-toolkit 1.19.1 and `--gpus all` works.
- Hot Aisle admin TUI accepts the team's registered SSH key directly (`ssh -tt admin.hotaisle.app`, no email code); it refuses connections after many logins in a short period. The API has `GET /virtual_machines/available/`.
- Codex on the owner's ChatGPT account rejects `gpt-6-terra`; `gpt-6-astra` works.
- `hot-aisle/campaign/research-2026-09/` is internal strategy, not site content: keep it off `main` before any push, or move it to a private repo.

## Request-input integration, 24 September 2026

Official dstack docs already name Hot Aisle as a native backend and expose MinimumReservationMinutes in its availability response. Fleet idle_duration does not release nodes at the configured minimum. Treat these as lease/lifecycle inputs, not an hourly-price shortcut. Current metadata was captured separately; newest releases do not replace qualified environment digests. The compute helper adds read-only placement calculations without inheriting execution authority.
