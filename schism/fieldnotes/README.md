# Fieldnotes for SCHISM

**Keep meeting notes, research, repair logs and project decisions in a searchable notebook on your own computer. Export ordinary text, change the application, or move the whole notebook to another operator. Your notes remain yours.** Fieldnotes is a useful application built on the released SCHISM 0.1.1 stack. Its source uses Python's standard library and ships under Apache-2.0.

## Open your notebook

Install Python 3.11 or newer. Download and extract the complete [SCHISM 0.1.1 source release](https://bigbirdreturns.github.io/axm-tools/schism/downloads/schism-stack-0.1.1-source.zip) and this Fieldnotes archive. Keep each extracted folder intact. From the Fieldnotes folder, run one command with the path to your extracted SCHISM folder:

Windows:

```powershell
py -3 open-fieldnotes.py --schism "C:\Tools\schism-stack"
```

Linux:

```sh
python3 open-fieldnotes.py --schism /home/you/tools/schism-stack
```

The launcher prepares SCHISM's hash-locked runtime, creates or uses your operator identity, signs the included Fieldnotes source with your key, imports it and starts the notebook. Your browser opens the private local address. Initial source setup needs package-index access; later opens reuse the installed runtime. A compatible downloaded dependency directory can be supplied with `--wheelhouse PATH` for offline setup.

The default operator state is `~/.schism`. Use `--state PATH` to choose a separate operator and notebook. The helper prints every SCHISM operation and its operator fingerprint. It makes no publisher-authorization changes. Running and signing downloaded application source gives that program the access of your OS account; inspect the source you intend to run.

For a standalone SCHISM controller, point `--schism` at the complete native distribution folder or its executable instead. Fieldnotes still needs Python 3.11+ on `PATH`: a native controller does not bundle its applications' Python interpreter. The Linux native controller keeps its published glibc 2.43 requirement; using the source controller follows your system's Python compatibility. Current platform results appear in `ACCEPTANCE.json`; untested platforms remain unqualified.

## Use it

Create a note with a title, plain text and optional comma-separated tags. **Save note**, or Control/Command+S, commits it to disk. Search matches titles, bodies and tags. Import a UTF-8 `.txt` or `.md` file to create a draft. Fieldnotes preserves Markdown as text. It never executes or renders embedded HTML.

**Download text** exports the selected saved title and body as UTF-8 text. **Export notebook** downloads every saved note, including archived notes, as ordinary JSON plus reading copies in `.txt` files. Save changes before exporting. An archive flag hides a note from the ordinary list; **Include archived** lets you restore it. Version 1.1.0 adds pinning. Revision checks reject a save from a stale tab, preserving the newer saved note.

Notes live at `STATE/data/fieldnotes/notes/NOTE_ID.json`. The `fieldnotes.note/v1` format contains the identifier, title, body, tags, creation and modification times, revision, archive flag and pin flag. Both supplied app versions use the same `fieldnotes/1` data contract. Your exported notebook can be read without SCHISM or Fieldnotes. The bound is 2,000 notes, 256 KiB of UTF-8 body text per note and 32 MiB of saved JSON overall. Data is plaintext under your local account's access controls; Fieldnotes does not add encryption at rest.

The service uses `http://127.0.0.1:8787/`. Every notebook read and write needs the temporary token from its private launch link. The browser removes that token from the visible address and keeps it in the tab's session storage. A fresh service start generates a fresh token in SCHISM's private work directory, outside the application data. Reopen the launcher after a restart. Avoid sharing the private link or logs containing it. A busy port makes startup fail; the launcher does not stop unrelated software.

Closing the browser leaves the service running. To stop it:

```sh
python3 open-fieldnotes.py --schism /path/to/schism-stack --stop
```

On Windows, use `py -3` in place of `python3`. Reopening the ordinary launch command starts a stopped notebook. SCHISM 0.1.1 requires separate host service supervision for automatic start after a reboot; this helper starts it explicitly.

## Change the code and retain the work

Two actual app releases are included. Version 1.0.0 contains the notebook, import, search, export and archive features. Version 1.1.0 adds pinning while preserving the same data format. The first ordinary launch selects 1.1.0. To exercise an upgrade yourself, stop any running Fieldnotes instance before starting a separate notebook at 1.0.0. Each instance uses port 8787. Save your own notes, then update:

```sh
python3 open-fieldnotes.py --schism /path/to/schism-stack --state /path/to/demo-state --app-version 1.0.0
python3 open-fieldnotes.py --schism /path/to/schism-stack --state /path/to/demo-state --app-version 1.1.0
python3 open-fieldnotes.py --schism /path/to/schism-stack --state /path/to/demo-state --rollback
```

Each transition uses the public pack/import/deploy or rollback commands with the observed application generation. The service briefly restarts. Your current notes survive, including notes or compatible fields written by the newer version. Code rollback retains present application data. Reopening without `--app-version` keeps the selected code rather than changing it implicitly.

## Hand the notebook to another operator

Use the SCHISM command prefix printed by the Fieldnotes helper: the PowerShell prefix on Windows or the shell prefix on Linux. In the commands below, `SCHISM` stands for that full command, including its interpreter/native executable and `--state` path. It is a placeholder, not a literal executable name. Use `status` to read the current Fieldnotes generation and selected release ID.

On the original operator:

```text
SCHISM status
SCHISM stop fieldnotes --expect CURRENT_GENERATION
SCHISM backup fieldnotes --output notebook-backup.zip
SCHISM export-evidence --output original-evidence.zip
SCHISM identity
```

Keep the backup and evidence outside live operator state. Transfer them with the original public identity and establish its fingerprint through an independently trusted channel. The backup carries the selected/prior app packages and notes; the separate evidence export preserves the original operator's signed event history. Neither transfers the original private signing key or browser token.

On a new operator, prepare SCHISM itself before opening the Fieldnotes helper. Restore needs an unused application ID, and an ordinary first Fieldnotes launch would create that application. For the source controller, run its setup-only command from the extracted SCHISM folder:

```sh
python3 scripts/launch.py --install-only --state /path/to/new-private-state
```

Use `py -3` on Windows. This command prepares the controller runtime and prints its command prefix without installing Fieldnotes. The source launcher's Windows prefix is labeled for Command Prompt; the Unix prefix is for a shell. With a native controller, use `schism.exe --state NEW_PRIVATE_STATE init` on Windows or `./schism --state NEW_PRIVATE_STATE init` on Linux. Set every subsequent command's `--state` to that new private state. Then restore and authorize before invoking the Fieldnotes helper:

```text
SCHISM restore notebook-backup.zip --key-id ORIGINAL_FINGERPRINT
SCHISM verify-evidence original-evidence.zip --key-id ORIGINAL_FINGERPRINT
SCHISM status
SCHISM trust PATH_TO_ORIGINAL_PUBLIC_IDENTITY_JSON --app fieldnotes
SCHISM start fieldnotes --expect 1
```

Save the original `identity` command's public JSON output as UTF-8 without a byte-order mark to the identity file used by `trust`. Legacy Windows PowerShell redirection can produce UTF-16 and its UTF-8 mode may add a byte-order mark; choose UTF-8 without a byte-order mark in your editor or use the package-based alternative below. You may instead use one of the restored `.schism` packages under the new state's `packages` directory; compare the publisher fingerprint with the independently established original identity first. Authorization applies only to `fieldnotes`. Restore leaves code stopped and untrusted, so an attempted start before that explicit decision fails.

Run the Fieldnotes helper with the new `--state` to open its fresh private link. Its ordinary open path keeps the restored selection and performs no trust grant. The new operator can continue editing the notebook and export a new signed record. The new restore event binds the backup's hash and original signer, while the original event history remains in its independently verified export.

## Source and qualification

| File | Purpose |
|---|---|
| `open-fieldnotes.py` | Starts, updates, restores prior code or stops the notebook through the unchanged SCHISM public CLI. |
| `versions/1.0.0/schism.json`, `versions/1.1.0/schism.json` | Complete application manifests with the same stable data contract. |
| Each version's `server.py` | Loopback API, authorization, revision checks and atomic UTF-8 JSON storage. |
| Each version's `index.html`, `app.js`, `style.css` | Self-contained notebook interface. |
| `tools/qualify.py` | Real public-launcher/CLI/HTTP update, rollback and operator-transfer journey. |
| `ACCEPTANCE.json` | Observed qualification scope and results. |
| `SOURCE-MANIFEST.json` | Exact distributed source inventory. |

`tools/qualify.py` reproduces the application journey using isolated operator states and synthetic notes:

```sh
python3 tools/qualify.py --schism /path/to/schism-stack --output /path/to/fieldnotes-result.json
```

Its native command-line/HTTP receipt proves the actions it lists. Browser interaction, native controller distributions and reboot supervision need their separately stated evidence. `SOURCE-MANIFEST.json` records exact included file sizes and SHA-256 values; The download page's `SHA256SUMS` records the downloadable archive. No user data, private operator keys or browser tokens ship in this distribution.
