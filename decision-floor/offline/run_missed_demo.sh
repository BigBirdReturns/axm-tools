#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m decision_floor run --input sample_inputs/missed --config config/sources.json --workspace local_state --out local_report
printf '\nReport: %s/local_report/index.html\n' "$(pwd)"
