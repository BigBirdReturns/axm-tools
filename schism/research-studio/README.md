# Research Studio

Research Studio is a local, read-only projection of retained research. It binds file identities and selected JSON values to their exact source bytes, preserves original owners and evidence classes, and exposes a browser for history, recorded campaigns, research dependencies and implementation access. It can play already recorded object positions. It does not launch simulations or imported software.

The application uses Python 3.11 or newer and the standard library. Its static browser files use no external dependencies. `research-index@1` describes this review projection; existing project ledgers remain authoritative.

## Collect and verify

Create a private collection specification with `read_roots`, explicit `sources`, and a `catalog` template. Keep private paths, conversation material, assets and generated catalogs outside this source directory. A source can declare `expected_sha256`, `expected_bytes` and JSON-pointer `extract` bindings. Component, campaign, lineage, dependency and vendor `derive` bindings reference those extracted fields. Collection hashes and extracts from the same bounded byte snapshot. Verification checks both the original bytes and the retained projections.

```sh
python app/studio.py collect --spec /private/collection-spec.json --output /private/catalog.json
python app/studio.py verify --catalog /private/catalog.json --root /original/source/root --output /private/verification.json
python app/studio.py serve --catalog /private/catalog.json --port 8374
```

Open `http://127.0.0.1:8374/` on that computer. The server accepts read requests only and exposes the declared catalog plus its fixed browser assets. It does not expose arbitrary source files. The OS account is the local privacy boundary; this is not an internet or multi-tenant service.

File identity checks establish which source was inspected. Historical claims and scientific acceptance retain their own scope. Campaign totals remain separate. A vendor's executed state requires source-derived implementation and invocation identity in a distinct execution record. That attribution still requires domain review before it establishes capability.

## Existing SCHISM lifecycle

`app/schism.json` packages this viewer as a SCHISM service with a loopback health endpoint. Use the existing SCHISM runtime and its documented signing and authority model. Pack only the explicit `app` directory. Its generated catalog belongs in the recipient's persistent `data/research-studio/catalog.json`, outside the code package.

First deploy the service into an empty application data directory so SCHISM records its declared schema. The reader starts without inventing a catalog: its interface reports unavailable data until the verified catalog is placed in the displayed data directory. The health endpoint describes reader readiness; `/api/catalog` validates every returned catalog and reports an error for missing or invalid data. A stopped-application backup carries the code and data to a separately initialized recipient, which independently authorizes the original application publisher. Keep the recorded source-host identity when moving a catalog; local browser playback on the recipient does not reverify unavailable source paths or rerun the historical experiments.

## Evidence and presentation

Components and lineage link to exact source references. Campaigns can carry additional declared metrics and optional playback. The native retained-film shape `{balls:[{traj:[[x,y,z],...]}],frames,fps}` remains unchanged in the catalog and is normalized only for display. Coordinates retain their declared units, including undeclared units. Recorded playback and new dynamics are different evidence classes.

## Validation and ownership

```sh
python -m unittest discover -s tests -v
```

The focused tests check source drift, extraction identity, projection tampering, provenance resolution, execution claims, overlapping counts, native playback preservation, read roots and actual loopback HTTP behavior. Browser acceptance belongs to each installed release and data projection.

All source files in this directory are steward-owned. Collection outputs and source specifications remain in the operator's private project records. An installed service keeps operator state, locked dependencies and receipts in a durable project runtime directory. `supervise_service.py` provides optional OS service supervision for an explicitly deployed SCHISM service. It starts through the controller, observes its state and stops through its generation-checked lifecycle; an operator stop is terminal for that supervision session. Task applications require their own explicit invocation and are never resumed by this supervisor. Apache-2.0 applies to this application source; source documents and scene assets retain their original rights.

The supervisor is qualified against SCHISM Stack 0.1.1. It also binds shutdown to the adopted release and run identity because a start/stop cycle does not advance the controller generation. Its guarded worker uses that version's ordinary durable stop path and application lock; this private API dependency fails closed for another controller version. See `QUALIFICATION.md` for the observed acceptance boundary. A service-manager start, including boot, explicitly starts the selected reader; an operator stop during supervision ends that session without automatic restart.
