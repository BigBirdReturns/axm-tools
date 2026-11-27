"""Summarize the recipient's own CSV data without contacting any service."""
import csv
import json
import math
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:3])
if not source.is_file():
    raise SystemExit("Place your CSV at " + str(source) + " and run this application again.")
with source.open(encoding="utf-8-sig", newline="") as handle:
    reader = csv.DictReader(handle)
    headers = reader.fieldnames or []
    rows = list(reader)
numeric = {}
for header in headers:
    values = []
    invalid = 0
    for row in rows:
        cell = (row.get(header) or "").strip()
        if not cell:
            continue
        try:
            number = float(cell)
            if not math.isfinite(number):
                raise ValueError("nonfinite")
            values.append(number)
        except ValueError:
            invalid += 1
    if values and not invalid:
        numeric[header] = {"count": len(values), "sum": sum(values), "mean": sum(values) / len(values), "minimum": min(values), "maximum": max(values)}
result = {"rows": len(rows), "columns": headers, "numeric": numeric}
destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False), flush=True)
