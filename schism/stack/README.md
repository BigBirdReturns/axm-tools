# SCHISM Stack

**Run applications under your own authority, retain the work, and change suppliers without rebuilding your operating history.** SCHISM is a general application deployment and recovery stack with a local console, command line, independently owned recipients and optional SSH transport. Its application format accepts declared native commands, so a publisher can package a data processor, web service, local model server, scientific tool or another operator-approved program through the same lifecycle.

Release **0.1.0** includes signed application packages, scoped publisher authorization, detached jobs, persistent application state, health-checked activation, retained prior versions, code rollback, explicit recovery, signed evidence export and application backup/restore. It runs on the recipient's machine using that recipient's OS permissions. Apache-2.0 permits use, modification and redistribution under its terms.

## Start the console

Install Python **3.11 or newer**, extract the complete source release, and run:

```sh
# Linux / macOS source installation
./launch-schism.sh
```

On Windows, open **launch-schism.cmd**. The launcher creates a private versioned environment, installs exact dependencies against the included wheel hash lock, and opens `http://127.0.0.1:8371/`. The first installation needs package-index access unless you supply a compatible offline wheelhouse. Installation does not require an Estate account, hosted controller, model provider, subscription or API key.

```sh
python3 scripts/launch.py --state /your/private/schism-state
python3 scripts/launch.py --wheelhouse /downloaded/compatible-wheels --install-only
```

The launcher prints a quoted command prefix containing its runtime interpreter and chosen `--state`. Commands below use `python schism.py` for readability; replace that prefix with the printed one so your CLI and console use the same operator state. With a standalone controller, use `./schism` on Linux or `.\schism.exe` on Windows instead. State defaults to `~/.schism` and remains separate from the extracted program. Protect that directory with the same care as the applications and signing authority it contains.

The source minimum describes supported dependency metadata. The accompanying qualification report identifies the interpreter and operating-system versions actually exercised. Platform-specific offline kits must match their stated CPython and architecture labels. Any packaged native executable retains its published platform baseline. Applications may require their own interpreters, executables, libraries, containers or hardware; declaring an application does not install those prerequisites automatically.

## First useful application

The included `csv-summary` task reads the recipient's own UTF-8 CSV, with an optional byte-order mark, comma delimiter and header row. It computes numeric-column counts, sums, means and ranges, and writes a JSON summary. Packaging and deployment use the same path as every other application.

```sh
python schism.py init --name "My operator"
python schism.py pack examples/csv-summary --output csv-summary.schism
python schism.py import csv-summary.schism
```

Open the console, select the imported release and deploy it. Packages signed by your own current operator identity already have local authority. Packages from another operator display their public fingerprint; authorize that publisher for the specific application before deploying. Verify a publisher's identity through an independently trusted channel before granting its code access to your account.

Deployment creates the application's data directory. Place your CSV at the `input.csv` path shown under that application and press **Run**. The job records its actual output and exit status. `summary.json` remains in the application's data directory. A missing input creates a failed job with a clear message; the task does not invent a successful result.

For a persistent service, package `examples/counter-service`. Deployment starts a loopback HTTP service at `http://127.0.0.1:8765/`. Visits update a recipient-owned SQLite counter. Package and import `examples/counter-service-v2`, then activate it through the same application panel. Its label changes while the counter persists. **Restore prior version** restarts the retained code while retaining current application data. Stop the service before making a data backup.

## Package your own application

Create `schism.json` in the precise directory you intend to distribute:

```json
{
  "schema": "schism.application/v1",
  "id": "my-processor",
  "name": "My processor",
  "version": "1.0.0",
  "kind": "task",
  "command": ["{python}", "process.py", "{data}/input.csv", "{data}/result.json"],
  "environment": {},
  "secret_env": [],
  "data_schema": "1",
  "task_timeout": 300,
  "stop_timeout": 5
}
```

`kind` accepts `task` or `service`. Commands are argument arrays; the controller does not insert a shell. Declare a shell explicitly only when your own application requires one. The process runs from the package payload, or from its declared relative `cwd`. `{release}`, `{data}` and `{work}` expand to the retained code directory, persistent application data directory and individual run directory. In a source installation, `{python}` selects the controller's Python interpreter. In a standalone controller it selects an external `python3` or `python` from `PATH`; the included Python examples therefore still require installed Python. Native executables may appear directly in `command` or through a declared absolute path. The recipient must have them installed.

Every process also receives `SCHISM_DATA`, `SCHISM_WORK`, `SCHISM_RELEASE` and `SCHISM_APP_ID`. Write application state to `SCHISM_DATA` and temporary/output work to `SCHISM_WORK`; retained release files must remain unchanged. The default process environment carries essential OS paths and locale settings. A publisher's declared nonsecret environment and the recipient's explicit runtime overrides supply additional values. The controller does not inherit the parent process's arbitrary cloud credentials or API keys into applications.

Required secret names belong in `secret_env`. Set their values through the console's private environment editor or a local JSON file:

```sh
python schism.py configure my-processor --environment private-environment.json
```

Values remain in recipient-owned private state. Evidence export and application backup omit runtime configuration. Applications can write their own values to logs or data; control those outputs according to your application's confidentiality requirements.

The console displays UTF-8 process output. Python applications receive `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` by default, including on Windows. Explicit application or recipient overrides take precedence. Write binary outputs into the declared work or data directory.

Services declare an acceptance check:

```json
"health": {
  "type": "http",
  "url": "http://127.0.0.1:8080/health",
  "status": 200,
  "timeout": 15
}
```

HTTP checks remain on numeric loopback, disable proxies and redirects, and require the candidate process tree to own the listening port. A `process` check accepts a process that survives its declared startup grace period. Choose application-specific acceptance appropriate to the workload; process survival and HTTP status alone establish limited operational facts. Task completion records its exit code, and the application retains responsibility for the meaning and correctness of its output.

```sh
python schism.py pack /path/to/explicit/application-source --output /path/to/my-processor.schism
python schism.py inspect /path/to/my-processor.schism
```

A `.schism` package contains a signed release descriptor and a closed file inventory. The builder rejects unsafe paths, symlinks, case collisions, private/secret-looking source files and unsupported files. Keep the output package and private state outside the source directory. Inspect and import verify the signature and complete inventory without executing payload code. Signatures identify a key; the recipient's scoped trust decision grants execution authority.

| Admission boundary | Limit |
|---|---:|
| Local CLI package archive | 256 MiB |
| Expanded application payload | 512 MiB total |
| Individual payload file | 128 MiB |
| Payload inventory | 10,000 files |
| Console or SSH package transfer | 64 MiB archive |
| Application backup | 512 MiB total, 20,000 files |

For a valid package larger than the console or SSH transfer bound, copy it through your own file transport and use local `python schism.py import FILE`. Large external datasets and model weights normally belong in recipient-owned application data or a separately declared runtime dependency.

## Execution, updates and recovery

| Operation | Actual transition |
|---|---|
| Import | Verifies and retains code; starts no process. |
| Authorize publisher | Pins a public key to explicit application ids. An optional wildcard grants authority to every application id. |
| Deploy task | Selects the verified code and creates its data root; the recipient invokes Run separately. |
| Deploy service | Stops the selected service, starts the candidate, checks acceptance, then commits the next generation. This release uses a restart transition with downtime. |
| Failed candidate | Stops the candidate and attempts to restart the previously running, still-authorized release. Failure to restart remains visible. Candidate writes to application data remain observable effects. |
| Restore prior version | Verifies and activates retained code with the same declared data schema. It retains current data. |
| Stop / cancel | Terminates the recorded process identity and its observed descendants. Managed applications remain trusted OS processes; this is not hostile-code containment. |
| Recover | Inspects recorded selection and live process identity, stops uncommitted candidates and reports actual state. It does not replay an uncertain task or promote an interrupted candidate. |
| Revoke publisher | Refuses future starts, runs and activations from that publisher. Explicit Stop controls an already-running process. |

The recipient records the data schema before a first candidate can execute, including a candidate that later fails acceptance. Incompatible state changes require application-owned migration tooling and a separate application id or a freshly staged recipient. This version does not automate an in-place schema migration. Back up the stopped application and validate migrated data before granting the replacement application operational use.

Application generation is a compare-and-swap precondition. A command carrying a stale generation fails before changing the selected deployment. The console carries the version it observed automatically. CLI callers specify it explicitly:

```sh
python schism.py deploy RELEASE_ID --expect 0
python schism.py run my-processor --expect 1 --detach
python schism.py job JOB_ID --wait
python schism.py rollback my-service --expect 2
python schism.py recover my-service
```

Each request has a durable id and input fingerprint. Repeating the same id with identical input returns the original job; changing input under the same id refuses. Client or console loss leaves detached workers operating. A missing worker makes the retained operation **interrupted**. Recovery preserves unknown external effects. Exactly-once effects against arbitrary databases, cloud services, payment systems or detached container daemons require those systems' own transaction and idempotency contracts.

The operating model uses one local account as the trust boundary. Publisher code runs with that account's access. Keep unrelated security principals in separate OS accounts, containers or virtual machines according to your deployment policy. An owner who can rewrite the controller and its private state can also change its observations; signed history supports verification by other recipients, not protection against a compromised signing host.

## Move an application to another operator

Stop the application and create a signed backup:

```sh
python schism.py stop my-service --expect 3
python schism.py backup my-service --output my-service-backup.zip
python schism.py identity
```

Transmit the backup and establish the backup signer's fingerprint independently. On a fresh recipient:

```sh
python schism.py --state /new/private/state restore my-service-backup.zip --key-id BACKUP_SIGNER_FINGERPRINT
```

Restore verifies every retained file and imports the selected/prior packages and data into an unused application id. It leaves execution stopped. The replacement operator authorizes the application publisher, restores required local runtime configuration, and starts the service or runs the task. Its own signing identity remains separate. The backup contains application data; handle it according to that data's sensitivity. It omits original private keys, runtime configuration, logs and process state. A live database requires a stopped application or an application-specific quiesced export.

Keep an independently secured backup of your complete private state if you need to retain the original operator identity. Application backup provides a deliberately different contract: a new operator can continue the work while owning its own authority.

## Independent recipients over SSH

The optional node adapter uses the operator's existing OpenSSH account and known-host pins. Install SCHISM and its runtime on a POSIX SSH recipient first; remote installation and credential creation remain explicit operator administration. The adapter requires noninteractive authentication and `StrictHostKeyChecking=yes`. It pins the recipient's application signing identity in addition to the SSH transport identity. Each subsequent request binds that recipient key; the recipient checks it before importing packages or submitting work, and signs the exact request fingerprint in its response.

```sh
python schism.py node add workstation \
  --host my-configured-ssh-alias \
  --python /home/me/schism-runtime/bin/python \
  --root /home/me/schism-stack \
  --remote-state /home/me/.schism
python schism.py node status workstation
python schism.py node import workstation my-processor.schism
python schism.py node action workstation request.json
python schism.py node job workstation REMOTE_JOB_ID
```

`request.json` uses the same lifecycle fields as the local API, for example `{"operation":"deploy","release_id":"...","expected_generation":0,"request_id":"deployment-2026-001"}`. Authorize a publisher remotely with `{"operation":"trust","publisher":{...},"apps":["my-processor"]}` using the verified imported publisher descriptor. Import and trust remain separate transitions. Remote responses sign the exact request fingerprint. A transport failure can leave an operation's outcome unknown; reuse its original request id to inspect the existing operation instead of creating a duplicate.

Windows hosts run the same local application lifecycle and can control POSIX SSH recipients. This release's remote command adapter targets a POSIX login shell. It does not assert a Windows-SSH-shell contract or require an exposed network daemon.

## Export and verify the record

```sh
python schism.py export-evidence --output evidence.zip
python schism.py verify-evidence evidence.zip --key-id OPERATOR_FINGERPRINT
```

The export includes signed release metadata, signed sequential events, observed application selection and job identity/status. The verifier checks the outer signature, exact event order, predecessor digests and release signatures. Supplying an independently known operator fingerprint binds the record to that key. Omitting it establishes self-consistency and reports `identity_pinned: false`. Verification accepts data and never runs code from the evidence archive.

Evidence export omits private signing keys, runtime override values, process logs and application data. A public key, signature or content hash does not establish physical hardware identity, application correctness, institutional approval or the truth of external claims. Publish the evidence appropriate to the decision being made.

## Interface and maintenance

The local HTTP API binds only `127.0.0.1`. It validates Host, Origin and browser fetch metadata. Every API read and write requires the current session token. The launcher opens a private bootstrap URL; the console removes its token fragment from the address bar and retains it in that tab's session storage. After restarting the server, open the fresh URL printed by the launcher. Console assets are self-contained and have a restrictive content security policy. The API is an OS-local operator interface, not a multi-tenant internet service.

`CONTRACT.md` documents the application, package and API shapes. `PROVENANCE.md` identifies source relationships and retained design boundaries. `QUALIFICATION.json` and `QUALIFICATION.md` in a published release report actual acceptance results and platform limits. Run the source acceptance suite with:

```sh
python -m unittest discover -s tests -v
```

To update the controller, verify a new release's hashes, extract it separately and point its launcher at the existing private state. Preserve a backup before a schema-changing controller upgrade; this release uses `schism.state/v1`. Application updates use the verified deployment path described above. Applications, operator state and versioned controller files retain separate ownership.
