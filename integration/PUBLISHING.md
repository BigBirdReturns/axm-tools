# Shared Pages publication

The four existing publishers call `.github/actions/publish-site/action.yml`
after their own collector or qualification work. Their schedules and the
`pages` concurrency group remain the execution owners. The action reuses
GitHub's official configure, upload and deploy actions and its existing
workflow token. It adds no account, service, key or browser login.

## Exact publication identity

`integration/pages_publication.py` supplies the missing evidence between
the official actions. Each run:

1. Builds the established offline launcher and the reviewed publication index.
2. Runs the existing compute release gate, then stages the historical Cantos
   redirects and frozen non-HTML bytes under their existing contract.
3. Requires the checkout to match current remote main, copies the public
   tree into a separate runner-temporary directory and writes `pages-build.json`.
4. Uploads with an artifact name unique to the workflow run and attempt.
5. Checks every actual tar member against the prepared file hashes, obtains
   the provider's artifact ID and archive digest, and checks current main again.
6. Uses the official Pages deploy action, reads the exact marker, root index
   and publication index from the returned URL, and correlates the environment
   deployment ID with the workflow run's status log URL.
7. Commits only `.github/pages-deployment.json` through a separate checkout of
   current main and a normal fast-forward push. The complete per-file receipt,
   release gate and compatibility manifest remain in the run artifact for 90 days.

The public staging rule retains the previous upload action's exclusion of
dotfiles and dot-directories, and additionally omits Python bytecode caches.
It rejects symlinks instead of following a target outside the public tree.
It does not copy private Second Run source or draft packets. Individual tool
pages still have independent runtimes and offline behavior.

| Receipt field | Meaning |
| --- | --- |
| `trigger_sha` | Commit that caused this workflow event |
| `built_sha` | Actual checkout HEAD after any committed data refresh |
| `source_sha` | Legacy alias of `trigger_sha` for existing receipt readers |
| `content_manifest_sha256` | Digest of the sorted path, size and SHA-256 records before adding the build marker |
| `artifact.id` | Observed GitHub Actions artifact ID |
| `artifact.provider_digest` | GitHub's SHA-256 identity of the uploaded artifact archive |
| `artifact.tar.sha256` | SHA-256 of the exact tar supplied to the upload action; separately verified member by member |
| `deployment.id` | Observed GitHub environment deployment ID, correlated with this run |
| `deployment.kind` | `github-environment-deployment`, explicitly distinct from any unexposed Pages-internal ID |
| `live_readback` | Observed HTTP 200, exact bytes and digest for the marker and indexes |

The environment job can still have an `in_progress` status while it writes
its receipt. `DEPLOYED_AND_READ_BACK` means the deploy action completed and
the named public objects matched at the recorded observation time. It does
not assert that every future CDN response, every individual tool or the
separate axm.tools apex was requalified by this run.

## Failure and continuation

The final artifact-retention step uses `always()`. Read the existing run
and receipt before repeating an uncertain action. `PREPARED` is a local
candidate. `UPLOADED_ARTIFACT_VERIFIED` identifies an uploaded artifact.
`DEPLOYMENT_COMPLETED_READBACK_PENDING` records that deployment completed
while readback or provider correlation remains unfinished. Only
`DEPLOYED_AND_READ_BACK` can update the repository receipt.

A changed main causes `source_advanced` before deployment. A readback
mismatch leaves the completed deployment visible in its retained attempt;
it does not claim the previous receipt still describes current live bytes.
A concurrent main update can reject the receipt push. The observed receipt
still remains in the run artifact; inspect it and the current live marker
before retaining it on a newer main. No force push or automatic replay is used.

The published marker cannot contain the later receipt commit's identity:
that commit records an already uploaded artifact. Use `built_sha` together
with the file manifest and archive identity to identify those bytes.

## Publication catalog

`publications/data/catalog.json` is the reviewed public catalog. Its consumer
accepts only `publication-catalog/0.1` entries with `state: published` and a
matching `publication-release/0.1` receipt. The receipt binds publication ID,
revision, canonical URL and a dated HTTP readback digest. These are retained
observations supplied by the source owner, not an independent signature of
authorship or continuing availability. Hash-named image files are checked
before they enter the tree. Unknown fields, private local paths, credentialed
URLs, candidate states and unlisted files cause a nonzero result.

The connected publishing controller imports the allowlisted directory in
an isolated branch, using the current catalog SHA as a write guard:

```sh
python -B publications/scripts/catalog.py import \
  --source /absolute/reviewed-public-export \
  --expected-current-sha EXACT_CURRENT_CATALOG_SHA256
python -B publications/scripts/catalog.py build
python -B publications/scripts/catalog.py check
```

The author stays in the existing conversation. The controller supplies
paths, hashes, branch operations and the reviewable result. A matching rerun
is unchanged; a conflicting write preserves the existing catalog. An
interrupted import retains its lock for inspection rather than assuming it
failed. Imports use a staged directory swap with rollback for caught errors;
they are not a crash-atomic filesystem transaction. Git retains the accepted
catalog history. A production specimen or an unverified draft does not
become a published article. Existing public archive entries use
`OBSERVED_EXISTING_PUBLICATION` evidence; that metadata import acquires
no Ghost editing ownership and preserves its distinct revision meaning.

## Validation

```sh
python -B -m unittest integration.tests.test_pages_publication \
  integration.tests.test_release_gate integration.tests.test_cantos_compat -v
python -B -m unittest discover -s publications/tests -v
python -B publications/scripts/catalog.py check
```

`publication-check.yml` runs these checks for publication changes without
deploying Pages. A draft pull request is prepared work. Live activation
requires the reviewed change to reach main and its actual workflow and
public readback to succeed.
