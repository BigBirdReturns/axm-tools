# SCHISM Stack 0.1.1 qualification

Release date: 27 November 2026. The release qualifies a general application lifecycle stack with recipient-owned authority, signed package admission, detached execution, retained application data, checked activation, code recovery, independent recipients and verifiable history. The supported platform and operating boundaries below form part of that acceptance.

The final runtime passed the source suite on Windows and Linux and completed all 15 native executable lifecycle cases on each platform. The actual local console completed 20 functional checks, with the browser resource exception retained in its original harness result and explained below. The original public landing page and guide passed all 12 checks across desktop, 375px and 320px layouts. The 0.1.1 landing page changes only six version characters in labels and download links; its separate static comparison retains the original visual qualification without claiming a new browser run.

## Patch and retained evidence

Version 0.1.1 closes every opened database connection even when setup fails, preserves the initiating transaction exception if rollback also fails, and gives a recorded process observer one second to finish exit recording after its application stops before forced termination. The runtime continues to propagate database failures and never retries transaction bodies. The application/state formats remain compatible with 0.1.0.

The earlier [hosted 0.1.0 Windows run](https://github.com/BigBirdReturns/axm-tools/actions/runs/46067747613) completed 35 tests with two errors in the cancellation case: a SQLite I/O error followed by a retained-handle cleanup error. Five independent repetitions of the original case passed on native Windows 11, so repetition did not establish a cause. The setup-handle leak follows directly from the old control flow. The initial SQLite error subtype was absent from the hosted trace and remains unconfirmed. The patch adds three deterministic lifetime/shutdown regressions and requires retained exit evidence and a fresh database integrity check after normal cancellation and abrupt worker loss. Previous 0.1.0 archives remain available under their original names and hashes.

## Exact release identity

The [native compilation input](../downloads/schism-stack-0.1.1-build-source.zip) contains the exact source used for both executable builds:

| Binding | SHA-256 |
|---|---|
| Compilation input ZIP | `8233fc7a65ae724a4f34c30a3c3b220d5a86f35d46c70253eb79607d94ce60d6` |
| Compilation input source inventory | `ead0299da27bd7665faab1c59bc37b2dd9129a8ece6ce14fd1ba8faf3a257ef4` |
| Ordered 16-file runtime inventory | `72378e3abac7bf2532fb4f065a8967c87b00dbf9fcb7de07aec9324119fe515a` |
| Windows controller executable | `9258037b8318c26130c51875e26d33f1d27f6d1f471bb957d7dbd4d1956c45ab` |
| Linux controller executable | `19bb3f18a59d28b1047a537e80430ab97f3d1f46457dd0399fcbf2a099897f72` |

The [documented source release](../downloads/schism-stack-0.1.1-source.zip) adds this report and its [machine-readable evidence](QUALIFICATION.json). Every existing file from the accepted compilation input remains byte-identical. Its complete `SOURCE-MANIFEST.json` inventories the resulting source tree; [SHA256SUMS](../downloads/SHA256SUMS) identifies all downloadable archives. Native ZIPs also contain a closed artifact inventory, exact source/build provenance and upstream license texts. The report distinguishes the source used to compile the binaries from the later documentation package.

## Observed qualification

| Lane | Observed result | Scope |
|---|---|---|
| Source suite, local Python 3.12.14 |38 tests passed | Package, identity, lifecycle, API, recovery, backup and transport boundaries |
| Source suite, Windows 11 / Python 3.13.15 |38 tests passed | Exact final source; inherited legacy Windows locale |
| Source suite, Linux x86_64 / Python 3.14.4 |38 tests passed | Exact final source on glibc 2.43 |
| Native Windows controller | 15 cases passed | Separate compiled CLI processes and retained recipient state |
| Native Linux controller | 15 cases passed | Separate compiled CLI processes and retained recipient state |
| Windows controller to POSIX SSH recipient | 9 cases passed | Existing pinned SSH, independently owned state and signed exact-request replies |
| Fresh offline source installation, both native systems | Passed | New isolated runtime, selected state paths containing spaces |
| Final native ZIP extraction, both native systems | Version/init/status passed | Fresh state outside an installation path containing spaces; complete installation unchanged |
| Actual local console | 20 functional checks passed; raw harness **FAIL** retained | Pointer-driven operations, file selection and actual application state; Chrome task-cap exception |
| Public landing page and guide | 12 original checks passed; version-only update verified | Original desktop and 375px/320px rendering; six literal label/link changes for 0.1.1 |

The final 38-test suite contains 19 package/identity cases, four complete lifecycle journeys, ten targeted acceptance/recovery regressions, two recipient-transport regressions and three shutdown/connection-lifetime regressions. It exercises real subprocess execution where behavior depends on process ownership or duration. Focused failure injection checks atomic selection/receipt commitment and failed recovery. Detailed native records, suite counts and retained receipt digests appear in `QUALIFICATION.json`.

The native executable journeys observed a declared OS-native command running with an empty child `PATH`, unauthorized publisher refusal, signed import without execution, a detached Unicode task surviving its caller, service survival across separate callers, a healthy update, retained-code rollback with continuing data, failed-candidate restoration, schema and stale-generation refusal, stopped recovery without replay, backup restoration under a fresh operator, task cancellation and independent signed-evidence verification. The outer execution host retained its normal process containment throughout these checks.

The SSH journey used the shipped Windows controller and a separately initialized POSIX recipient. It exercised enrollment, signed import, remote scoped authorization, task activation, work surviving the submitting SSH caller, request-id reuse without duplicate work, continuing persistent data, signed reply verification and a changed recipient pin. The changed pin refused both a new package and a new run before the recipient's release or job inventory changed. The recipient key forms part of the exact signed request fingerprint. Windows transport qualification also covers removal of stale OpenSSH descriptor metadata inherited from its parent process before creating replacement input/output pipes.

## Console and installation continuity

The actual console admitted an outside publisher's package, granted one application scope, processed a supplied UTF-8 CSV and retained its computed output. It added a service grant while preserving the earlier task grant, activated service version 1, updated to version 2 and restored version 1 while the persisted counter advanced 1→2→3. It also exercised stop/start/recover, malformed package refusal, private-session access, signed evidence export and a fresh pinned-key verifier. No JavaScript exception or server error appeared in the functional journey. Views measured at 375px and 320px remained within their viewport.

The console was exercised against the earlier frozen input identified in `prior_qualification_continuity`; its three UI files and the exact dependency lock remain byte-identical. Version 0.1.1 received fresh offline installer qualification on both native systems, including new isolated runtimes and selected state paths containing spaces. The runtime correction received the complete native source and executable qualification. The public site retains its earlier visual record and a separate exact comparison of its six version-reference changes. Current destination names are checked against the release inventory and live publication.

The original console receipt's overall failure is a resource observation: the independent Chrome job reached its 128-task host limit 11 times. The SCHISM server used four to six tasks and the driver used 14, with zero task-cap events in those jobs. The report accepts the 20 directly observed product outcomes and retains the broader harness failure. The separate public-site pass recorded zero task-cap events. These observations establish the tested interactions; they do not establish an unlimited browser or host-capacity guarantee.

## Distribution and operating boundaries

The source launcher creates an isolated versioned runtime and requires exact binary-wheel hashes for cryptography 50.0.0, psutil 7.2.2, cffi 2.1.1 and pycparser 3.12. Source dependency metadata accepts Python 3.11 or newer; actual execution covered the three interpreter versions listed above. Offline wheel kits target Windows AMD64/CPython 3.13 and Linux x86_64/CPython 3.14 respectively. Native controllers embed their own runtime, while applications retain their declared prerequisites. The included Python applications need installed Python when run through a native controller. The Linux binary's build baseline is glibc 2.43; use source installation and qualify locally for other compatible Python environments.

An operator's OS account defines the execution boundary. Publisher grants authorize trusted programs to use that account's access; separate OS accounts, containers or virtual machines supply stronger isolation when required. Local HTTP control binds numeric loopback and requires a private session token for every API read and write. SSH uses existing noninteractive authentication, strict host-key checking and the enrolled application identity. This release targets a POSIX recipient shell and leaves account provisioning and remote installation to the operator.

Service activation uses a restart transition with downtime. Acceptance checks establish process survival or an owned loopback HTTP response. A failed candidate triggers an attempt to restart the previous authorized release; failed recovery remains visible. Code rollback preserves current application data, including writes performed before a rejected candidate failed acceptance. Data-schema migration and external transaction correctness require the application's own acceptance. Recovery reconciles observed process state and preserves uncertainty about interrupted work without replaying it. The demonstrated durability covers client/console/SSH disconnects and separate callers; reboot persistence requires a separately configured service supervisor.

Signed packages establish content and publisher-key identity. Signed evidence binds ordered recorded events to an operator key and excludes private keys, runtime configuration values, process logs and application data. A recipient should establish the verifier's expected key independently. Hardware identity, application correctness, physical observations and a compromised signing host require separate evidence. The [operating guide](README.md), [interface contract](CONTRACT.md) and [provenance](PROVENANCE.md) preserve these boundaries.

The qualification is a release acceptance record produced during development. Public JSON projections preserve observed statuses, source/executable hashes and original receipt digests while excluding private account paths and raw runtime logs. The source suite, source inventory, executable inventories and build inputs remain available for independent inspection and repetition.
