## GRADIENT-151 Linux Seed

This seed package contains all files required to collect a Linux host observation
without external services or network calls.

- Read-only collector source: `scripts/collect-linux.py`
- POSIX launcher: `scripts/collect-linux`
- Linux host-observation schema: `seed/collect-linux-host-observation-2.schema.json`
- Deterministic local validator: `seed/collect-linux.validator.py`
- Seed reconstruction script: `seed/reconstruct.py`
- File manifest and digests: `seed/seed-manifest.json`, `seed/sha256sums.txt`

## Collection contract

Run from a writable operator machine:

```bash
python scripts/collect-linux.py --host-id <control-host|heavy-host-a|heavy-host-b> --out-file <state>/observations/<host-id>.json
```

The output file is written through a same-directory temporary file using UTF-8 text and
`fsync` before atomic `rename`.

- `host_id` must be the declared estate id.
- `observation` output name must be `<host-id>.json`.
- Runtime rows are closed for:
  `python`, `git`, `ollama`, `docker`, `wsl`, `nvidia-smi`.
- On native Linux, `wsl` must be explicitly absent with reason:
  `"not applicable on a native Linux host"`.

The collector returns non-zero when required identity fields are missing or contradictory.

## Privacy and authority boundary

- No MAC addresses, no IP addresses, no disk serials, no machine GUIDs, no
  credentials/tokens/private keys are emitted.
- This seed does not open network sockets, spawn listeners, install software,
  or alter runtime state.
- The collector result is an immutable observation to be consumed by
  `python scripts/lab.py qualify-estate` and cannot replace private claim authority.

## Seed reconstruction and verification

- Run `python seed/reconstruct.py` to rebuild the seed artifact directory layout from
  committed repository files into a temporary directory and compare SHA-256 manifests.
- `seed/sha256sums.txt` binds every seed artifact file.
- The returned artifact is the Linux observation for physical N01 execution.
