#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 app.py serve --project local_customer
