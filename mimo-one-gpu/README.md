# MiMo one-GPU lab

A static, copy-ready handoff with a separately downloadable Python-standard-
library controller. It tests the full selected MiMo checkpoint on **one GPU
plus actual host RAM** using an existing vLLM image. It does not claim
single-GPU MiMo inference has already succeeded.

Open the published page at https://bigbirdreturns.github.io/axm-tools/mimo-one-gpu/ or serve `index.html` to select the model and desired benchmark path. The page
fetches only its own static source files for read-only previews. It uses no analytics, browser storage or uploaded files. It produces an
inspectable prompt for the recipient's existing local coding agent, then
links the versioned source kit. The small controller performs read-only
inspection before separate permission for full-file hashing, an existing
runtime-image probe or model loading.

`v1/README.md` is the executable scope and failure contract. Batch requests
and native harnesses are separate routes. The latter uses a bounded,
ephemeral, authenticated loopback bridge to a network-isolated model
container. It is test transport, not a hosted site backend. It stops with its
owned job. No site dependency, model weight, image, API key or billable service
is installed or obtained by this repo.

## Qualification

Run `python3 -m unittest discover -s mimo-one-gpu/tests -v` and the
Playwright handoff test in `tests/browser.py`. The unit/process fixtures are
synthetic: they do not establish GPU execution, MiMo fit or benchmark scores.
The browser test covers page readability, selections, copied prompt and
clipboard-denial fallback. `scripts/check.py` checks the source manifest and
kit contents. The narrow workflow changes no other tool.

## Ownership and what can rot

All files are steward-owned. No scheduled data jobs exist. `v1/` is frozen on
publication; changed behavior belongs in a new version. Public hardware
reports may age, runtime flags and model loaders may change, benchmark access
or protocol may differ, and local Docker/NVIDIA tooling may be absent. These
conditions stop inspection/execution visibly; they never trigger a hidden
fallback. The recipient owns their runtime, benchmark and final approval.

Control qualification and native model qualification are separate states.
Native MiMo execution remains unmeasured until an actual receiver supplies
a source-bound result. Do not upgrade a synthetic
process test or a small canary into a published quality score.
