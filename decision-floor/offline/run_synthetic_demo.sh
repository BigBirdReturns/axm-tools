#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 tools/seed_demo.py --project local_demo --scenario missed
python3 app.py serve --project local_demo
