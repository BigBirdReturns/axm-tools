# GRADIENT-151 offline Linux seed

Everything needed to collect one read-only Linux host observation on a machine
that has no clone of this repository, no network access to it, and no
credentials from it.

| File | Role |
| --- | --- |
| `scripts/collect-linux.py` | Read-only collector source (standard library only) |
| `scripts/collect-linux` | Optional POSIX launcher; verifies the seed, then collects |
| `seed/collect-linux-host-observation-2.schema.json` | `axm-community-lab/host-observation@2` output schema |
| `seed/collect-linux.validator.py` | Deterministic local validator for a returned observation |
| `seed/verify.py` | Seed self-verification against `seed/sha256sums.txt` |
| `seed/reconstruct.py` | Deterministic reconstruction and byte-identity proof |
| `seed/seed-manifest.json` | File manifest, contracts, and boundaries |
| `seed/sha256sums.txt` | SHA-256 of every seed file's exact bytes |

The **seed identity** is the SHA-256 of the exact bytes of
`seed/sha256sums.txt`. That file binds every other seed file, so one digest
addresses the whole bundle and no seed file has to contain its own digest.

## 1. Verify the seed before collecting

```bash
python3 seed/verify.py --root .
```

Exit code `0` and `"ok": true` mean every file matches its recorded digest and
the manifest and checksum list agree. Any other result means the bundle is
tampered or truncated: stop, do not collect.

The POSIX launcher performs this check itself, so `scripts/collect-linux` never
collects from an unverified bundle.

## 2. Collect

```bash
./scripts/collect-linux \
  --host-id heavy-host-b \
  --out-file "$HOME/.local/state/axm/home-lab-gradient/observations/heavy-host-b.json"
```

Or without the launcher:

```bash
python3 scripts/collect-linux.py \
  --host-id heavy-host-b \
  --out-file "$HOME/.local/state/axm/home-lab-gradient/observations/heavy-host-b.json"
```

Requirements and guarantees:

- **No sudo.** If a surface needs elevation, its absence is recorded instead.
- `--host-id` must be a declared estate id: `control-host`, `heavy-host-a`, or
  `heavy-host-b`.
- **Output-name contract:** `--out-file` must end in `<host-id>.json`. The
  collector writes exactly two paths: that file, and a same-directory temporary
  `.<host-id>.json.tmp`. The temporary file is flushed, `fsync`ed, and published
  by atomic `rename`, so a partial write can never appear as the final output.
- Surfaces read, all read-only and only when available: `/etc/os-release`,
  `uname`, `/proc/cpuinfo`, `/proc/meminfo`, `/sys/class/dmi/id`,
  `/sys/class/net`, `lsblk`, `lspci`, `nvidia-smi`.
- The runtime denominator is closed: exactly one row for `python`, `git`,
  `ollama`, `docker`, `wsl`, `nvidia-smi`. On native Linux `wsl` stays present
  as an explicit inapplicable row (`present=false`, `disabled=true`,
  `disabled_reason="not applicable on a native Linux host"`, `path=null`). An
  inapplicable runtime does not disappear.
- Every absent optional tool and every unreadable optional surface is recorded
  explicitly under `surfaces`.

**Exit codes:** `0` published; `1` a required field was missing or
contradictory and nothing was published; `2` invalid arguments; `3` the host is
not POSIX.

## 3. Validate the returned observation locally

```bash
python3 seed/collect-linux.validator.py \
  "$HOME/.local/state/axm/home-lab-gradient/observations/heavy-host-b.json"
```

The validator recomputes the observation digest over canonical body bytes,
checks the closed runtime denominator and the WSL inapplicability reason,
checks collector and Python executable identity, and refuses any retained
private identifier. It only reads; it creates and deletes nothing.

## 4. Return

Return **only** the single `<host-id>.json` observation file. Nothing else from
the host is requested, and nothing is sent anywhere by the seed: the transfer
is entirely holder-selected and manual.

On the control host the observation joins the estate census:

```bash
python scripts/lab.py qualify-estate \
  control-host.json heavy-host-a.json heavy-host-b.json
```

## Privacy and authority boundary

The seed collects **no** disk or board serial number, machine GUID or
`machine-id`, MAC address, IP address, credential, token, private key, SSH
material, Tailscale identity, or persistent callback coordinate. Serial-bearing
DMI files and the per-module DMI table are deliberately never parsed; the
network surface reads link name, state, MTU, and speed only, never `address`.

The seed itself contains no credential, host secret, or private address, opens
no socket, listener, or callback, installs nothing, starts no daemon, and
alters no system state. It does not require or configure remote access, and it
changes nothing about the host's current workload.

A returned observation is read-only evidence about one host at one moment. It
admits no worker, measures no path cost, proves no cross-host clock relation,
and cannot substitute for a declared estate inventory. Equally, a declared
inventory cannot substitute for it, and no synthetic or fixture observation can
establish a physical host execution.

## Reconstruction

```bash
python3 seed/reconstruct.py --root .
```

Rebuilds the bundle twice into two fresh directories, verifies each against
`seed/sha256sums.txt`, and reports `"byte_identical": true` only when both
rebuilds and the committed source agree byte-for-byte. `--into DIR`
materializes one verified bundle for transfer.

Every seed file is stored with LF line endings and no byte-order mark. The
digests are over exact bytes, so a CRLF conversion in transit is a detected
tamper, not a silent difference.
