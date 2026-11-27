#!/bin/sh
set -eu
SCHISM_SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCHISM_SOURCE/scripts/launch.py" "$@"
