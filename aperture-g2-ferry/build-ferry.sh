#!/usr/bin/env bash
set -euo pipefail
umask 022

ROOT="${RUNNER_TEMP:?}/axm-aperture-g2-ferry"
OUT="$ROOT/out"
WORK="$ROOT/work"
rm -rf "$ROOT"
mkdir -p "$OUT/repos" "$OUT/wheelhouse" "$OUT/mpv" "$WORK"

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

providers_json="$WORK/providers.json"
cat > "$providers_json" <<'JSON'
[
  {
    "name": "axm-genesis",
    "repository": "BigBirdReturns/axm-genesis",
    "pr": 38,
    "base": "411ef40e6cfc3ecb97ac3e256c8151be678347c8",
    "feature": "347aa43b3e3dc46e27ca67870b5035d9e4870d90",
    "landed": "e81314378eb31aa6a9c8efcc05b533c799709e30"
  },
  {
    "name": "axm-arc",
    "repository": "BigBirdReturns/axm-arc",
    "pr": 245,
    "base": "c65cbe85e865ffe5627a609f38e94d306bf7f94c",
    "feature": "a94fcf69898c7d5ceb40b733f0ca5e6a42794623",
    "landed": "c8b78629217b9ba7237c1ecfff47cdc0e28cbf69"
  },
  {
    "name": "axm-core",
    "repository": "BigBirdReturns/axm-core",
    "pr": 33,
    "base": "968df05e36c059c3aa25b50ade069c3754ba0c90",
    "feature": "a9769b6ab91a9d12e3b9be67550b58cf86973357",
    "landed": "bcc70fa469f43b12adb9a18d395d434fcb794e1a"
  }
]
JSON

python - "$providers_json" "$WORK" "$OUT/repos" <<'PY'
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

providers = json.loads(pathlib.Path(sys.argv[1]).read_text())
work = pathlib.Path(sys.argv[2])
out = pathlib.Path(sys.argv[3])


def run(*args: str, cwd: pathlib.Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


for provider in providers:
    name = provider["name"]
    bare = work / f"{name}.git"
    run("git", "init", "--bare", str(bare))
    run(
        "git",
        "-C",
        str(bare),
        "remote",
        "add",
        "origin",
        f"https://github.com/{provider['repository']}.git",
    )
    run(
        "git",
        "-C",
        str(bare),
        "fetch",
        "--no-tags",
        "origin",
        "refs/heads/main:refs/heads/upstream-main",
    )
    run(
        "git",
        "-C",
        str(bare),
        "fetch",
        "--no-tags",
        "origin",
        f"refs/pull/{provider['pr']}/head:refs/heads/upstream-feature",
    )
    for role in ("base", "feature", "landed"):
        run("git", "-C", str(bare), "cat-file", "-e", f"{provider[role]}^{{commit}}")
    run(
        "git",
        "-C",
        str(bare),
        "merge-base",
        "--is-ancestor",
        provider["base"],
        provider["feature"],
    )
    run(
        "git",
        "-C",
        str(bare),
        "merge-base",
        "--is-ancestor",
        provider["base"],
        provider["landed"],
    )
    run(
        "git",
        "-C",
        str(bare),
        "merge-base",
        "--is-ancestor",
        provider["feature"],
        provider["landed"],
    )
    run(
        "git",
        "-C",
        str(bare),
        "merge-base",
        "--is-ancestor",
        provider["landed"],
        "refs/heads/upstream-main",
    )
    for role in ("base", "feature", "landed"):
        run(
            "git",
            "-C",
            str(bare),
            "update-ref",
            f"refs/heads/aperture-g2/{role}",
            provider[role],
        )
    bundle = out / f"{name}-g2-provider.bundle"
    run(
        "git",
        "-C",
        str(bare),
        "bundle",
        "create",
        str(bundle),
        "refs/heads/aperture-g2/base",
        "refs/heads/aperture-g2/feature",
        "refs/heads/aperture-g2/landed",
    )
    run("git", "-C", str(bare), "bundle", "verify", str(bundle))
PY

cat > "$WORK/requirements.txt" <<'REQ'
jsonschema==4.26.0
referencing==0.37.0
pytest==9.0.2
pytest-cov>=6,<7
blake3>=0.4,<2
PyNaCl>=1.5,<2
click>=8,<9
dilithium-py>=0.5,<1
duckdb>=1,<2
cryptography>=41,<50
setuptools>=68
wheel
REQ

python -m pip download \
  --dest "$OUT/wheelhouse" \
  --only-binary=:all: \
  --requirement "$WORK/requirements.txt"
cp "$WORK/requirements.txt" "$OUT/wheelhouse/requirements.txt"

python -m venv "$WORK/wheelcheck"
"$WORK/wheelcheck/bin/python" -m pip install \
  --no-index --find-links "$OUT/wheelhouse" \
  --requirement "$OUT/wheelhouse/requirements.txt"
"$WORK/wheelcheck/bin/python" - <<'PY' > "$OUT/wheelhouse/import-smoke.json"
import importlib.metadata as md
import json

mods = [
    "jsonschema",
    "referencing",
    "pytest",
    "blake3",
    "nacl",
    "click",
    "dilithium_py",
    "duckdb",
    "cryptography",
]
for name in mods:
    __import__(name)
packages = [
    "jsonschema",
    "referencing",
    "pytest",
    "blake3",
    "PyNaCl",
    "click",
    "dilithium-py",
    "duckdb",
    "cryptography",
]
print(json.dumps({name: md.version(name) for name in packages}, indent=2, sort_keys=True))
PY

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  mpv ffmpeg ca-certificates

MPV_ROOT="$WORK/mpv-root"
mkdir -p "$MPV_ROOT"
python - /usr/bin/mpv "$MPV_ROOT" <<'PY'
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

binary = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
queue = [binary]
seen: set[pathlib.Path] = set()
pattern = re.compile(r"(?:=>\s+)?(/[^\s(]+)")
while queue:
    path = queue.pop(0)
    if not path.is_absolute():
        path = path.resolve()
    if path in seen or not path.is_file():
        continue
    seen.add(path)
    target = root / path.relative_to("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path.resolve(), target)
    result = subprocess.run(["ldd", str(path)], text=True, capture_output=True)
    if result.returncode != 0:
        continue
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        dependency = pathlib.Path(match.group(1))
        if dependency.is_file() and dependency not in seen:
            queue.append(dependency)

for candidate in [pathlib.Path("/usr/share/mpv"), pathlib.Path("/usr/share/lua")]:
    if candidate.exists():
        target = root / candidate.relative_to("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, target, dirs_exist_ok=True)
PY

cat > "$MPV_ROOT/mpv-portable" <<'WRAP'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$HERE"
paths=()
for candidate in \
  "$ROOT/lib" \
  "$ROOT/lib64" \
  "$ROOT/lib/x86_64-linux-gnu" \
  "$ROOT/usr/lib" \
  "$ROOT/usr/lib/x86_64-linux-gnu" \
  "$ROOT/usr/local/lib"; do
  if [ -d "$candidate" ]; then paths+=("$candidate"); fi
done
library_path="$(IFS=:; echo "${paths[*]}")"
export LUA_PATH="$ROOT/usr/share/lua/5.2/?.lua;$ROOT/usr/share/lua/5.2/?/init.lua;;"
loader=""
for candidate in \
  "$ROOT/lib64/ld-linux-x86-64.so.2" \
  "$ROOT/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"; do
  if [ -x "$candidate" ]; then loader="$candidate"; break; fi
done
if [ -z "$loader" ]; then
  echo "portable MPV loader is missing" >&2
  exit 126
fi
exec "$loader" --library-path "$library_path" \
  "$ROOT/usr/bin/mpv" --no-config --load-scripts=no "$@"
WRAP
chmod +x "$MPV_ROOT/mpv-portable"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=black:s=320x180:r=24:d=3 \
  -f lavfi -i anullsrc=r=48000:cl=stereo \
  -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac "$WORK/mpv-smoke.mp4"

SOCKET="$WORK/mpv.sock"
"$MPV_ROOT/mpv-portable" \
  --vo=null --ao=null --idle=yes --pause=yes \
  --input-ipc-server="$SOCKET" --terminal=no --really-quiet \
  "$WORK/mpv-smoke.mp4" &
MPV_PID=$!
python - "$SOCKET" <<'PY' > "$OUT/mpv/ipc-smoke.json"
from __future__ import annotations

import json
import pathlib
import socket
import sys
import time

path = pathlib.Path(sys.argv[1])
for _ in range(200):
    if path.exists():
        break
    time.sleep(0.05)
else:
    raise SystemExit("mpv IPC socket did not appear")

commands = [
    {"command": ["get_property", "mpv-version"], "request_id": 1},
    {"command": ["get_property", "duration"], "request_id": 2},
    {"command": ["get_property", "pause"], "request_id": 3},
    {"command": ["set_property", "time-pos", 1.25], "request_id": 4},
    {"command": ["get_property", "time-pos"], "request_id": 5},
    {"command": ["quit"], "request_id": 6},
]
responses = []
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(str(path))
    reader = client.makefile("r", encoding="utf-8")
    for command in commands:
        client.sendall((json.dumps(command, separators=(",", ":")) + "\n").encode())
        deadline = time.time() + 5
        while time.time() < deadline:
            line = reader.readline()
            if not line:
                raise SystemExit("mpv closed IPC before response")
            response = json.loads(line)
            if response.get("request_id") == command["request_id"]:
                responses.append(response)
                break
        else:
            raise SystemExit(f"timeout waiting for {command['request_id']}")
for response in responses:
    if response.get("error") != "success":
        raise SystemExit(f"mpv IPC failure: {response}")
print(json.dumps({"status": "PASS", "responses": responses}, indent=2, sort_keys=True))
PY
wait "$MPV_PID"

"$MPV_ROOT/mpv-portable" --version > "$OUT/mpv/version.txt"
dpkg-query -W -f='${Package}\t${Version}\n' mpv libmpv2 ffmpeg \
  > "$OUT/mpv/debian-packages.txt" || true

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -C "$WORK" -cf - mpv-root \
  | gzip -n -9 > "$OUT/mpv/mpv-linux-x64-portable.tar.gz"

cp "${GITHUB_WORKSPACE}/aperture-g2-ferry/verify-ferry.py" "$OUT/verify-ferry.py"
cp "${GITHUB_WORKSPACE}/aperture-g2-ferry/README.md" "$OUT/README.md"
chmod +x "$OUT/verify-ferry.py"

python - "$providers_json" "$OUT" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import sys

providers = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2])


def sha(path: pathlib.Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


for provider in providers:
    bundle = out / "repos" / f"{provider['name']}-g2-provider.bundle"
    provider["bundle"] = bundle.relative_to(out).as_posix()
    provider["bundle_sha256"] = sha(bundle)
    provider["bundle_sha512"] = sha(bundle, "sha512")

mpv_version = (out / "mpv" / "version.txt").read_text(encoding="utf-8").splitlines()[0]
wheel_files = sorted(path.name for path in (out / "wheelhouse").glob("*.whl"))
receipt = {
    "format": "axm-aperture-g2-provider-runtime-ferry/1",
    "authority": "transport_only",
    "accepted_gates": [],
    "providers": providers,
    "python": {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "wheel_count": len(wheel_files),
        "wheels": wheel_files,
        "import_smoke_sha256": sha(out / "wheelhouse" / "import-smoke.json"),
    },
    "mpv": {
        "version": mpv_version,
        "bundle": "mpv/mpv-linux-x64-portable.tar.gz",
        "bundle_sha256": sha(out / "mpv" / "mpv-linux-x64-portable.tar.gz"),
        "ipc_smoke_sha256": sha(out / "mpv" / "ipc-smoke.json"),
    },
    "runner": {
        "os": os.environ.get("RUNNER_OS"),
        "arch": os.environ.get("RUNNER_ARCH"),
        "image": os.environ.get("ImageOS"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "sha": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
    },
    "control_question": (
        "Can Aperture independently reconstruct every transported prerequisite "
        "while the ferry remains incapable of accepting G2?"
    ),
}
core = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
receipt["receipt_sha256"] = hashlib.sha256(core).hexdigest()
(out / "provider-runtime-ferry.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

(
  cd "$OUT"
  find . -type f ! -name SHA256SUMS ! -name SHA512SUMS -printf '%P\0' \
    | sort -z \
    | xargs -0 sha256sum > SHA256SUMS
  find . -type f ! -name SHA256SUMS ! -name SHA512SUMS -printf '%P\0' \
    | sort -z \
    | xargs -0 sha512sum > SHA512SUMS
)

python "$OUT/verify-ferry.py" "$OUT" > "$OUT/verification.json"
# verification.json is produced after the checksum denominator is fixed. Bind
# it separately without introducing a self-referential checksum manifest.
sha256sum "$OUT/verification.json" > "$OUT/verification.json.sha256"

printf 'FERRY_ROOT=%s\n' "$OUT"
find "$OUT" -maxdepth 3 -type f -printf '%P\t%s bytes\n' | sort
