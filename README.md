# axm-tools

A toolbox, not a project. Each directory in this repo is a small,
self-contained tool that runs itself: GitHub Actions for compute, committed
JSON for state, GitHub Pages for the interface. No servers, no databases, no
API keys, no bills — the whole point is that any one tool can be ignored for
a year and still be working when you come back.

## Tools

| Tool | What it does | Interface |
|------|--------------|-----------|
| [`pta-tracker/`](pta-tracker/) | District-first legislation watch for an Arcadia USD K-6 PTA: nightly fetch, relevance filter, one-click monthly board report | [static page](https://bigbirdreturns.github.io/axm-tools/pta-tracker/) + nightly Action |

## Reference areas (not tools)

Some top-level directories are not tools — they have no compute, no state,
and no nightly Action. They're versioned reference material that other
things build against. They still deploy with the site (the whole repo root
is the Pages artifact), but they follow their own internal law instead of
the tool layout, so don't try to fit them into it.

| Area | What it is | Surface |
|------|------------|---------|
| [`identity/`](identity/) | The AXM / SCG identity system: the pixel-dandelion mark, its four-token palette and type, frozen release bundles, and the provenance law (`SCG_MARK_CONSTITUTION.md`) that governs every rendering | [live showcase](https://bigbirdreturns.github.io/axm-tools/identity/) — self-contained page, no Action |

`identity/` is deliberately **not** a tool: no `scripts/`, no `data/`, no
workflow. Its `index.html` is a read-only showcase that renders the mark
live from the canonical source (`identity/scg/source/scg-pixel-mark.js`) —
it never redraws it. The rules live in the constitution; treat frozen
`releases/` bundles as immutable (a change is a new `vX`, never an edit in
place).

## The shape of a tool

Every tool follows the same conventions so the next one costs nothing to
add and none of them can break each other:

```
<tool>/
├── README.md        # what it does, how to deploy it, what can rot
├── index.html       # the entire UI — one static page, no build step
├── scripts/         # stdlib-only Python; no requirements.txt to go stale
└── data/            # state, committed to git by the tool's own workflow
```

- **One directory per tool, fully self-contained.** Tools never import from
  each other and share no library. Shared code is a dependency, and
  dependencies are maintenance; convention is copyable and rots alone.
- **Workflows live at the repo root** (GitHub requires it) but are named
  and scoped per tool: `.github/workflows/<tool>-<job>.yml`, touching only
  that tool's `data/`.
- **GitHub Pages deploys from Actions** (Settings → Pages → Source
  "GitHub Actions"). A tool's workflow uploads the *repo root* as the
  Pages artifact after refreshing its data, so each tool is reachable at
  `/<tool>/` and this repo's root page is just a directory of them. The
  deploy step must live in the same workflow as any data commit: pushes
  made with the built-in `GITHUB_TOKEN` never trigger other workflows, so
  a standalone on-push Pages workflow would silently skip every scheduled
  refresh. All deploys share the `pages` concurrency group, so tools
  queue rather than clobber each other.
- **Fail loud or show it.** A scheduled job that breaks entirely must exit
  nonzero so GitHub emails the owner; a source that breaks partially must
  be visible on the tool's page. Silent staleness is the only real failure
  mode a zero-maintenance tool has.

## The hostile-source seam

Any tool that watches the world will eventually hit a source that blocks
datacenter IPs — bot protection, paywalled feeds, APIs broken on purpose.
Don't fight that from inside an Action; it's a war of attrition you lose.
Instead, every fetcher honors an out-of-band drop-box
(`<tool>/data/observed.json`): items collected by a human, or by a
[ScreenGhost](https://github.com/BigBirdReturns/screenghost) observer
reading the source off a real device's screen — the one interface a vendor
cannot revoke, because it's the one their paying customers use. The
collector commits the file; the nightly job merges it. The tool stays
stdlib-only and free; the hard cases route around the blockade instead of
through it.

First instance: `pta-tracker`'s board-agenda system (Simbli) sits behind
Incapsula and can't be scraped — see
[ScreenGhost's PTA agenda observer example](https://github.com/BigBirdReturns/screenghost/blob/main/examples/pta_agenda_observer.md)
for the local-device path that fills `observed.json`.

## Adding a tool

1. Create `<tool>/` with the layout above; write the README first,
   including an honest "what can rot" section.
2. Add `.github/workflows/<tool>-<job>.yml` for any scheduled work; make
   total failure exit nonzero, and if the workflow commits data, end it
   with the upload-artifact + deploy-pages steps (see `pta-fetch.yml`).
3. Pre-seed `<tool>/data/` so the page renders before the first run.
4. Add the tool to the table above and to the root `index.html`.
