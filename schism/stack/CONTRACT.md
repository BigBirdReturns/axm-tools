# SCHISM Stack 0.1.1 application and runtime contract

SCHISM is an operator-owned general application lifecycle stack. The release installs under its recipient’s account, admits signed closed packages, executes declared task/service applications, retains process output and operation state, checks updates, restores retained releases and exports verifiable history. Local OS authority and explicitly configured pinned SSH define execution authority.

## Common contract

Python >=3.11. Direct library use: `cryptography==50.0.0` and `psutil==7.2.2`. The exact dependency closure also pins `cffi==2.1.1` and `pycparser==3.12`. Stdlib SQLite, HTTP, ZIP, JSON and subprocess. Application package suffix `.schism`; ZIP contains `release.json`, `signature.json`, and exactly the inventory under `payload/`. Limits reject overlarge inputs before extraction. Import and inspect never execute code. This is trusted application deployment under the OS account, not a hostile-code sandbox.

Application document is `schism.json` at source root:

```json
{"schema":"schism.application/v1","id":"my-app","name":"My app","version":"1.0.0","kind":"service","command":["{python}","app.py"],"environment":{"PORT":"8765"},"secret_env":[],"data_schema":"1","health":{"type":"http","url":"http://127.0.0.1:8765/health","timeout":10},"stop_timeout":5,"task_timeout":300}
```

`kind` is `service` or `task`; argv is required, shell expansion is never implicit. `{python}`, `{release}`, `{data}`, `{work}` tokens expand in each argument and nonsecret environment value. All applications get `SCHISM_DATA`, `SCHISM_WORK`, `SCHISM_RELEASE` and `SCHISM_APP_ID`. Service health is `http` (loopback only) or `process` (alive after grace); task exit status is its execution result. Persistent data root survives code changes. `data_schema` must match for activation/rollback while retained data exists; migration is an explicit operator workflow. Unknown document fields are rejected. Arbitrary declared commands and operator-configured executable paths are supported.

## Identity and bundle API

`identity.ensure_identity(state: Path, name: str='Local operator') -> dict` creates or returns private state identity, public descriptor includes schema, name, key_id, public_key (base64 raw Ed25519), created_at. Private key is owner-readable and never exported implicitly.

`identity.sign(state: Path, payload: dict, purpose: str) -> dict` returns envelope with schema, purpose, key_id, public_key, payload, signature (base64); signature covers canonical JSON of all envelope fields except signature.

`identity.verify(envelope: dict, purpose: str | None=None, expected_key_id: str | None=None) -> dict` verifies signature, schema, identity and optional pins; returns payload. `identity.canonical(value)->bytes`, `identity.key_id(public_raw:bytes)->str` also exposed.

`bundle.build(source: Path, output: Path, state: Path) -> dict` validates `schism.json`, closes inventory, rejects symlinks, private dot trees, secret-looking filenames and special files, signs release; returns full verified release metadata (including `release_id`, `application`, `publisher`). Output must be outside source. Caller deliberately chooses source contents; no implicit repo or private state collection.

`bundle.inspect(path: Path) -> dict` verifies internal Ed25519 signature and complete bounded ZIP inventory, returns metadata; authenticity alone does not grant deployment authority.

`bundle.extract(path: Path, destination: Path) -> dict` verifies then extracts to a new empty destination; destination contains `payload/`, `release.json`, `signature.json`. `bundle.verify_directory(destination: Path) -> dict` rechecks closed inventory/signature. Metadata shape: `schema:'schism.release/v1', release_id:<sha256>, application:<normalized manifest>, files:[{path,sha256,size,executable}], publisher:<public descriptor>, created_at:<UTC>`. Release ID is content identity computed without the release_id field. Signature purpose `schism.release/v1`. Bind original application bytes through inventory as well as normalized document. No mutable hostname identity in release ID requirement.

## Runtime and UI API

Server listens exclusively on 127.0.0.1. GET `/api/state` returns `{version, identity, platform, state_root, applications:[], releases:[], jobs:[], events:[], trust:[], peers:[]}`. App fields: `id,name,kind,version,release_id,previous_release_id,generation,status,process:{pid,started_at}|null,data_schema,data_path,last_error`. Release fields: `release_id,application,publisher,created_at,trusted`. Job fields: `id,operation,app_id,status,created_at,ended_at,result,error`; statuses queued/running/succeeded/failed/cancelled/interrupted. GET `/api/job?id=...` adds log text (bounded tail). The HTTP server validates Host, Origin and Fetch Metadata.

Every `/api/*` read and write requires `X-SCHISM-Token`. The launcher supplies the session secret in a URL fragment; the console moves it to tab session storage and removes the fragment. `/api/token` validates an already supplied session token and returns it; it never discloses the session secret to an unauthenticated local caller.

POST `/api/action` JSON `{operation,request_id?,...}` submits and returns `{job_id}`. Operations:

- `trust`: `{publisher:<public descriptor>,apps:["my-app"]|["*"],label?:str}`; explicit replacement of that publisher’s full active scope; the console preserves existing active grants when adding another application. `revoke`: `{key_id}`.
- `deploy`: `{release_id,expected_generation:int}`; execution authorized by current trusted publisher scope. First deploy expected 0. Starts service; task activation does not execute task.
- `start`, `stop`, `run`: `{app_id,expected_generation:int}`; only task `run` executes task.
- `rollback`: `{app_id,expected_generation:int}`; activates the retained prior release; services start and tasks remain ready, with matching data schema required.
- `recover`: `{app_id}` observes retained actual state, never automatically replays an interrupted task/effect.
- `cancel`: `{job_id}`; cancel a running task/lifecycle operation with process ownership verification.
- `configure`: `{app_id,environment:{...}}`; local secret/runtime override values remain outside evidence exports and API reads.

POST `/api/import` raw application/octet-stream `.schism` upload, token protected, returns metadata plus trusted flag without execution. Console then presents publisher fingerprint and explicit scope trust action followed by deploy. GET `/api/export` returns signed evidence archive with public identity/releases/events/jobs (no private keys, secret config, logs, or application data). POST `/api/peer` enrolls a separately installed POSIX SSH recipient using existing host-key/account authority and pins its operator identity. GET `/api/peer-state?name=...` reads that node; POST `/api/peer-action` forwards a lifecycle request; POST `/api/peer-remove` removes its local enrollment.

Jobs run in a separate detached worker process per request; state persists independently of HTTP/CLI client. An OS-owned lock serializes lifecycle transitions for each application; SQLite transactions serialize shared history and generation changes. `request_id` maps exact canonical request fingerprint; duplicate identical input returns existing job, same id/different input refuses. Process identity uses PID plus psutil creation time. Service/task process wrappers own logs and exit recording. Startup reconciles worker/process identity without retrying unknown effects. SQLite transactions keep generations atomic; retained intent/events make interrupted activation observable.

Stopping a recorded application gives its observer a bounded interval to finish exit recording before forced termination. Failed database initialization closes its connection and propagates the initiating error. Transaction failures preserve the original exception even if rollback also fails; the controller never replays the transaction body automatically.

## Release acceptance

Fresh standalone local recipients on Linux and Windows; same manifest API runs at least a batch application and persistent-data HTTP service. Test signature tampering, unknown publisher, scope/revocation, duplicate request identity, path traversal/case collision, wrong generation, staged candidate failure, successful update, rollback, incompatible data schema, service/task cancellation and controller restart. Export verifies in fresh state without signing private key. Actual console import/trust/deploy/run/log/update/rollback controls get browser QA. Public package ships all source, exact lockfiles/licenses, install/run scripts, examples, contract and acceptance evidence. Published executables identify their exact qualified target. The source distribution includes installation instructions and the locked dependency closure. See QUALIFICATION.md and QUALIFICATION.json for observed results.
