#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$(uname -s):$(uname -m)" in
  Linux:x86_64) URL="https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz"; SHA="f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f" ;;
  Linux:aarch64) URL="https://github.com/astral-sh/uv/releases/download/0.13.5/uv-aarch64-unknown-linux-gnu.tar.gz"; SHA="4bb69cf95ed13f23713bb7bc09f241896ea0c75b7c557e615a20604b82f9c403" ;;
  Darwin:x86_64) URL="https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-apple-darwin.tar.gz"; SHA="b0f52b0e3945b4107d89024ea38e625683011fbfc05a0d98f9fa2d6dcee28c66" ;;
  Darwin:arm64) URL="https://github.com/astral-sh/uv/releases/download/0.13.5/uv-aarch64-apple-darwin.tar.gz"; SHA="743f85035a1996ecb350659e01cd9faea9709829be09b1b4b03c73eaf3c9cd73" ;;
  *) echo 'No pinned bootstrap binary for this platform. Read BUILD.md for the existing-Python route.' >&2; exit 2 ;;
esac
if [ "$(uname -s)" = Darwin ]; then APP="$HOME/Library/Application Support/MARY-App"; else APP="${XDG_DATA_HOME:-$HOME/.local/share}/mary-app"; fi
BOOT="$APP/bootstrap/uv-0.13.5"
mkdir -p "$BOOT"
ARCHIVE="$BOOT/uv.tar.gz"
if [ ! -f "$ARCHIVE" ]; then curl --fail --location --retry 2 --connect-timeout 20 --max-time 600 "$URL" -o "$ARCHIVE.part"; mv "$ARCHIVE.part" "$ARCHIVE"; fi
if command -v sha256sum >/dev/null 2>&1; then ACTUAL=$(sha256sum "$ARCHIVE" | cut -d ' ' -f1); else ACTUAL=$(shasum -a 256 "$ARCHIVE" | cut -d ' ' -f1); fi
[ "$ACTUAL" = "$SHA" ] || { echo 'Bootstrap archive checksum failed; nothing was executed.' >&2; exit 2; }
mkdir -p "$BOOT/bin"
tar -xzf "$ARCHIVE" -C "$BOOT/bin" --strip-components=1
UV="$BOOT/bin/uv"
[ -x "$UV" ] || { echo 'Pinned bootstrap executable is absent.' >&2; exit 2; }
export UV_PYTHON_INSTALL_DIR="$APP/python"
export UV_CACHE_DIR="$APP/cache"
export UV_PYTHON_BIN_DIR="$APP/bin"
export UV_NO_PROGRESS=1
"$UV" python install 3.12
exec "$UV" run --no-project --managed-python --python 3.12 "$HERE/bootstrap.py" --uv "$UV" "$@"
