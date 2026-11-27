# SCHISM 2.0: the exit test

SCHISM now contains a working continuity application and an independent Python receiving implementation. Export unfinished work, close the source workspace, reconstruct its history, and calculate the next decision from the retained evidence. The included Cantos exhibit carries a real historical compute experiment through independent recipient analysis while preserving its unsuccessful qualification.

Open `index.html` or `SCHISM-v2.0-offline.html`. Both applications contain their entire JavaScript runtime. The examples are synthetic industrial records; local CSV and packet imports stay in the browser. The page distinguishes live JavaScript calculation from retained Python execution receipts.

## Run the recipient

Python 3.10 or later is sufficient for the independent receiver. Extract the complete source package, open a terminal in `SCHISM-2.0`, and use a new output directory outside the installation:

```sh
python -B run.py --out ../schism-recipient-results
```

The runner verifies the delivered source set, launches a fresh Python process for each accepted and refused case, denies ordinary Python socket APIs, and independently completes the pending handoff. To pass that Python-authored continuation back to the original JavaScript implementation, install/use Node 18 or later and select:

```sh
python -B run.py --with-node --out ../schism-roundtrip-results
```

The receiver itself executes no JavaScript. Node participates only in the optional original-receiver check and the development differential suite. `qualification.json` in the chosen output directory retains the result. A repeated output path is refused to preserve earlier observations.

## Use your own compatible records

The page accepts CSV under the six declared source mappings and native handoff JSON. The Python implementation can inspect and continue the same records:

```sh
python -B runtime/receiver.py verify handoff.json --receipt ../verification.json
python -B runtime/receiver.py resume handoff.json --out ../continued.json --receipt ../execution.json
python -B runtime/receiver.py resume handoff.json --source capacity --csv corrected-capacity.csv --observed 2026-11-27T18:00:00Z --out ../corrected.json --receipt ../correction.json
```

The calculation contract has exactly two products, two resource stages and bounded input counts. Source authenticity and physical observations remain the holder's responsibility. Review records carry declared labels, not authenticated operational permission. The Python receiver uses a documented strict JSON and timestamp profile; see the technical note.

## Replay the empirical exhibit

The complete package includes the exact pinned Cantos maintainer archive. This command verifies its digest, closed file set, every file's identity and canonical manifest, then executes its own retained-evidence checker:

```sh
python -B scripts/replay_cantos.py --out ../schism-cantos-results
```

The expected result is a successful verification of an unsuccessful experiment: the original analysis remains `incomparable`, and the recipient finds `no_eligible_configuration`. This uses existing observations and makes no new model or GPU requests. The artifact preserves its original source dates and acceptance threshold.

## Source and reproduction

`vendor/` contains exact pinned AXM source. `runtime/receiver.py` independently implements its record and calculation semantics in Python. `controller.js` owns the browser exit drill, `app.js` and `style.css` its interface. `data/cases/` contains deterministic handoffs and adversarial inputs. `data/*qualification.json` records specific executions. `exhibits/` contains the immutable Cantos kit and its source locator.

```sh
node tests/controller.cjs
python -B runtime/test_receiver.py
python -B build.py
python -B scripts/verify_release.py
```

The differential suite uses Node to compare the Python calculation with the preserved donor and also checks a separate exhaustive optimizer oracle. Building creates the inline application, offline copy, closed release manifest and deterministic source archive. `--preview` builds the two HTML files without requiring the large Cantos exhibit. Generated pages display missing or stale native evidence explicitly.

All source and curated fixture files are steward-owned. HTML outputs, `release-manifest.json`, `SHA256SUMS`, the release ZIP, and aggregate qualification JSON are generated. Execution output belongs outside this installation. Existing source histories and frozen exhibit bytes remain unchanged.

## Maintenance

A changed donor engine requires explicit contract requalification. A changed Python receiver invalidates native receipts tied to its former hash. Keep fresh results under new output paths, update the reviewed evidence projection and regenerate the release. External research links may change; pinned commits and the complete offline source package preserve the delivered inputs. This package adds no scheduled execution, account access, remote control or background service.

Authored work © 2026 Jonathan Sandhu. Included projects retain their own source notices and distribution terms.
