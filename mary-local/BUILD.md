# Build and use MARY Local Workbench 0.3.0

MARY is a locally owned work environment: source records, current versions, task intent, checked tools, checkpoints and results stay on your device. A local model receives the relevant working context through a bounded adapter. The installed path uses AXM Core's Forge extraction and model adapter, Genesis sealing and independent verification, Spectra mounting/query, and MARY's occurrence history. ODS supplies pinned hardware/model-fit candidates rather than the authority to act.

## Install

Download and extract `MARY-Local-0.3.0.zip` into a normal folder. On Windows x64, open `Install.cmd`. On Linux or macOS, run `sh Install.sh` from that folder. The launchers acquire a hash-pinned uv executable and managed Python 3.12, create a private versioned application environment, install the hash-locked dependencies and the included Core, Genesis and MARY wheels, run installed-kernel and exact-calculation checks, and open the local interface. No Git, cloud API key, administrator permission, driver change, subscription or persistent service is required. Installation needs internet access; configured local work uses locally installed assets.

The Windows launcher uses the operating system's curl, tar and certutil. It changes no PowerShell execution policy. A missing prerequisite produces a visible build failure. Windows ARM, unusual Linux distributions and alternative architectures must pass their own installation and runtime checks; availability of a pinned executable alone is not a tested platform claim. The acceptance record names the environments actually exercised.

For a machine that already has Python 3.11–3.14 and pip:

```console
python bootstrap.py
```

For an unattended application build without opening a browser:

```console
sh Install.sh --no-launch
```

The build is versioned. A failed new build leaves the previous application and personal workspace intact. Reopening the generated `Start MARY.cmd`, `Start MARY.command` or `start-mary.sh` starts the same local workspace. Application code is separate from your source data. The portable source and tests are in `source/`; public upstream pins and wheel hashes are in the provenance and manifest files.

## Start doing work

Open Sources and choose files, or explicitly authorize a particular local folder. Intake copies selected originals into verified custody without modifying the source folder. A retained import identity carries its pending directory/file frontier across interruption. Current versions and withdrawn history remain distinct. Unsupported, unreadable, oversized and partially extracted input stays visible rather than disappearing from a success count.

Open Hardware and scan the actual machine. The report separates physical memory, available memory and inherited execution limits. ODS's catalog produces configuration candidates. It does not establish that a GPU backend works or that a model can do a task.

An existing ODS, llama.cpp, Ollama or other OpenAI-compatible local runtime can be connected by exact URL and model ID. Discover probes standard loopback endpoints only. A private-network address requires explicit opt-in; that endpoint's operator controls where its inference actually executes. Direct local runtimes are the intended default, and there is no silent hosted-model fallback.

Without an existing runtime, Prepare local CPU worker downloads a pinned Qwen3.5 2B or 4B quantized model and CPU-only llama.cpp profile selected against the observed memory envelope. This provides a portable floor without GPU drivers. The owned model process starts with MARY and stops when MARY exits. It does not become a hidden background service. Run Qualify before semantic tasks. Qualification records its exact route, implementation and visible task checks; it is scoped calibration, not a universal model-quality certification.

Use Work to request a source-grounded answer, a usable draft or a comparison. Select sources to restrict a request, or leave the selection empty to use current sources. Each result retains exact quotation references to verified source bytes, unresolved issues, actual artifacts and a durable work identity. Generated interpretation remains a source-linked draft for the owner to review; valid quotations alone do not prove every statement true or complete.

Exact calculation and table analysis work without an LLM. Calculate accepts bounded arithmetic and expressions such as `0.1 + 0.2` or `solve: 2*x + 3 = 11`. Table analysis supports CSV/XLSX description, count, sum, mean, minimum, maximum and grouped count/sum. Select the table and exact column names. Calculations preserve decimal/rational values. Formula cells are preserved and block unsupported numeric aggregation rather than being silently omitted. Macros, arbitrary SQL and generated code are not executed.

A conversational request can produce a bounded plan of available operations. The executor enforces the allowed functions and source selection. It writes local task-owned artifacts, checks them independently of the model's narration, and seals the completed occurrence/output journal through Genesis. This release exposes no email-send, original-file deletion, purchase or system-configuration tool. Those require separately qualified adapters and explicit authority.

## Continue after interruption

The work page displays actual state, accepted steps, errors and downloadable artifacts. Stop affects only that work's owned worker. Resume adopts accepted checkpoints and verifies their hashes instead of repeating completed steps. A changed selected source requires revised work with a new request identity, preserving the previous edition. An uncertain request is inspected by its retained ID before a replacement is started. Each work attempt has a finite allowance.

## Back up and restore

Prepare the pinned restic recovery tool from Recovery. Choose a dedicated repository on a second physical device and use a strong independently retained password. The backup is encrypted and includes source custody, owner keys, source lifecycle, task intent, checkpoints, accepted outputs and private endpoint credentials. A successful backup does not by itself prove independent physical custody or restoration.

The recovery path restores into a new directory, verifies Genesis source shards and MARY occurrence history, checks accepted output hashes, rebuilds the disposable index and requires model-route requalification. It never overwrites an existing workspace.

```console
mary-workbench --home RECOVERY_TOOL_HOME tools install
mary-workbench --home RECOVERY_TOOL_HOME restore BACKUP_REPOSITORY NEW_WORKSPACE
mary-workbench --home NEW_WORKSPACE serve
```

The command requests the password privately. External model weights and executable/dependency assets are separate from the context backup. Retain the build kit and the selected runtime/model assets as well for replacement-host operation without downloads. `bootstrap.py --offline` uses an already populated uv cache, or an explicitly prepared `wheelhouse` for its pip route; it does not pretend missing packages can be recovered without a source.

## Hardware profiles

The application and its context container are independent of a GPU vendor. Native local endpoints can use an admitted CPU, NVIDIA, AMD, Intel or Apple profile. Driver/runtime compatibility belongs to that supplier profile. Nothing in this package flashes firmware, changes power limits, bypasses a hardware reservation or claims every model fits every device.

A NUC6i7KYK with a Thunderbolt-attached accelerator is an intended compact host profile. The live Estate target observed during this release has an MI100, not an MI50. The MI50/gfx906 path remains a separately commissioned legacy-runtime candidate: preserve the selected driver's/runtime's support boundary and run its task/memory/recovery checks on the actual card. Do not infer MI50 acceptance from an MI100 or CPU result. See ACCEPTANCE.json for exact measured targets.

## Security and ownership boundary

This is a single-owner, loopback-only personal workbench, not a public multi-tenant server. It requires a local owner token, refuses cross-origin mutations and arbitrary endpoint redirects, treats source/model text as data, and has no generic shell API. Source evidence is re-derived from verified sealed bytes; the search index is only a discovery hint. Parser/model calls have finite process, output and time bounds. Native same-user processing is not a complete hostile-document security sandbox. Start with sources you are authorized to use and trust; an adversarial-document or multi-user deployment needs an additional OS/container isolation profile and its own acceptance.

Do not expose the application port to the internet or treat a reachable private-network model endpoint as proof of local inference. The interface displays evidence and uncertainty; domain judgment remains with the human. Private source text, prompts, keys and work history are not published by the build or submitted to a telemetry service.

## Evidence and licenses

Read ACCEPTANCE.json, SOURCE-PROVENANCE.json, MANIFEST.json and NOTICE. Software tests, actual source/model transactions, installation checks and physical-device results retain separate scopes. Historical failed attempts are retained in the owner's private development records; successful checks are not retrospectively assigned to those attempts.

The selected owner-authored release source is Apache-2.0. Public AXM, ODS, tool and package dependencies retain their licenses. Model weights have their own upstream terms. This release snapshot contains no private Estate history, personal documents, credentials, model weights or font files. Publishing this selected snapshot does not publish or relicense unrelated private repositories or personal records.
