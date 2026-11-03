# Publications and linked tools

This reference area connects canonical FakeSoap articles to their public
tools and evidence. It remains a standalone static page and adds no account,
runtime API, analytics or shared dependency to any tool.

`data/catalog.json` and `data/assets/` contain only the explicit reviewed
export from the publication owner. The connected controller imports that
directory with `scripts/catalog.py import --source DIRECTORY
--expected-current-sha SHA256`. `scripts/catalog.py build` generates the
committed `index.html`; `check` detects drift. Each full-site publisher builds
it again from the same source catalog so scheduled collection cannot replace
the index with an older projection.

File ownership:

- `data/catalog.json` and its hash-named assets are controller-owned projections
  of released publication records. Existing catalog bytes guard replacement.
- `index.html` is generated from that catalog and the renderer.
- `scripts/`, `tests/` and this procedure are steward-owned.
- `tests/fixtures/synthetic-catalog.json` is an explicit interoperability test
  fixture, separate from the actual public catalog. It is never imported by a
  normal build.

The accepted format is `publication-catalog/0.1`, containing published
`publication-catalog-entry/0.1` entries and matching
`publication-release/0.1` readback evidence. These are local publishing
integration formats. Private source packets, draft posts, account secrets
and arbitrary export fields have no place in this directory. The consumer
rejects candidate states, private paths, credentialed URLs, wrong image
hashes and unknown files. Existing public articles can enter through an
explicit `OBSERVED_EXISTING_PUBLICATION` receipt. Those entries carry an
Archive import label; their revision identifies the imported public
metadata and observations, not a Ghost editing revision or ownership of
the original article. Ordinary pipeline releases use `PIPELINE_PUBLICATION`
or the existing receipt format without an evidence-kind field.

The canonical article and related links can change or disappear. Readback
evidence retains its actual observation time; rebuilding the index does not
refresh that evidence. A malformed catalog makes publication fail visibly
while the last deployed site remains available. Keep the catalog source and
renderer together when moving this reference area to another static host.

See [the shared publication procedure](../integration/PUBLISHING.md) for
deployment identities and recovery. Run `python -B -m unittest discover -s
publications/tests -v` and `python -B publications/scripts/catalog.py check`
from the repository root before changing the consumer.
