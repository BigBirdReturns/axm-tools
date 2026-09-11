# Manzanita v31 self-hosted Windows recovery execution

This bounded object executes the exact `MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip` on the repository owner's self-hosted Windows recovery seat. It exists to perform the Windows storage and browser recovery campaign that remained unexecuted after the exact package passed its GitHub-hosted Windows platform replay.

The execution script requires a Windows administrator context, downloads the exact 553,074-byte package at SHA-256 `2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738`, extracts it under `RUNNER_TEMP`, and invokes the package-owned platform replay, preparation, accepted-parent and remaining-input recovery, and deterministic return-collection entrypoints. The package controls which files can enter the returned archive. The workflow retains only a privacy-bounded machine summary, its validation, the package-governed return collection, and source-verification evidence for one day.

The summary hashes the runner and computer names and does not retain the user profile path. Raw lane logs remain local to the temporary execution workspace and are represented only by byte counts and SHA-256 digests. The workflow does not upload arbitrary local files.

A successful workflow establishes that the exact recovery campaign ran on a self-hosted Windows seat and produced a structurally valid deterministic return collection. It does not prove that the seat was the historical v30 build origin. It does not grant exact-object or provenance standing to any returned candidate. The return must pass through the qualified provenance-aware V2 receiving intake before any production input, accepted parent, admission, inherited baseline replay, or v31 product authority can advance.

The source branch is the only automatic push trigger. Pull requests and forks do not execute the self-hosted campaign. A manual `workflow_dispatch` remains available for an explicitly authorized replay. Product mutation, merge, release, Pages, public-route, and external-effect authority remain held throughout this transaction.
