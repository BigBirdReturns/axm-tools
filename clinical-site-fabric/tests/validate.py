#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import csv, hashlib, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
README = ROOT / "README.md"
SAMPLES = ROOT / "samples"

errors: list[str] = []

def require(ok: bool, message: str) -> None:
    if not ok:
        errors.append(message)

text = HTML.read_text(encoding="utf-8")
core = (ROOT / "app-core.js").read_text(encoding="utf-8")
ui = (ROOT / "app-ui.js").read_text(encoding="utf-8")
js = core + "\n" + ui
require("Clinical Site Fabric" in text, "missing title")
require('type="file" multiple' in text, "multiple local-file input missing")
require("crypto.subtle.digest" in js, "browser SHA-256 missing")
require("parseCSV" in js and "importJSONValue" in js, "structured parsers missing")
require("portable-packet@2" in js, "portable packet v2 missing")
require("manual object-type and column-mapping" in README.read_text(encoding="utf-8"), "README mapping contract missing")
require("safe_to_stop" in text + js, "explicit prohibited GLP-1 output missing")
require("model-risk note" in (text + js).lower(), "model-risk boundary missing")
require("http://" not in text and "https://" not in text, "external runtime URL present")
require(all(not src.startswith(("http://","https://","//")) for src in re.findall(r'src="([^"]+)"', text)), "external script dependency present")
require("localStorage" not in js, "imported state must not persist in localStorage")
for js_path in [ROOT / "app-core.js", ROOT / "app-ui.js"]:
    try:
        subprocess.run(["node", "--check", str(js_path)], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        errors.append("node runtime unavailable for JavaScript syntax check")
        break
    except subprocess.CalledProcessError as exc:
        errors.append(f"{js_path.name}: JavaScript syntax failure: {exc.stderr.strip()}")

expected = {
    "protocols.csv": 4,
    "participants.csv": 6,
    "visits.csv": 5,
    "delegations.csv": 4,
    "resources.csv": 5,
    "bookings.csv": 3,
    "source_events.csv": 6,
    "mec6_assessments.csv": 6,
}
for name, count in expected.items():
    p = SAMPLES / name
    require(p.exists(), f"missing sample {name}")
    if p.exists():
        with p.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        require(len(rows) == count, f"{name}: expected {count} rows, got {len(rows)}")
        require(all(not any(k.lower() in {"name", "dob", "mrn", "email", "phone", "address"} for k in r) for r in rows), f"{name}: direct-identifier column present")

# cross-file fixture checks
with (SAMPLES/"bookings.csv").open(newline="", encoding="utf-8") as f:
    bookings=list(csv.DictReader(f))
def overlaps(a,b):
    return a["start_at"] < b["end_at"] and b["start_at"] < a["end_at"]
collisions=[]
for i,a in enumerate(bookings):
    for b in bookings[i+1:]:
        if a["resource_id"]==b["resource_id"] and overlaps(a,b):
            collisions.append((a["booking_id"],b["booking_id"]))
require(len(collisions)==1, f"expected one resource collision, got {collisions}")

with (SAMPLES/"delegations.csv").open(newline="", encoding="utf-8") as f:
    delegations=list(csv.DictReader(f))
require(any(d["status"]=="expired" and d["action"]=="specimen.release" for d in delegations), "expired specimen delegation fixture missing")

with (SAMPLES/"source_events.csv").open(newline="", encoding="utf-8") as f:
    events=list(csv.DictReader(f))
require(any("sae" in e["event_type"] and e["due_at"] for e in events), "SAE clock fixture missing")

with (SAMPLES/"mec6_assessments.csv").open(newline="", encoding="utf-8") as f:
    mec=list(csv.DictReader(f))
statuses={r["status"] for r in mec}
require({"pass","fail","hold","incomplete"}.issubset(statuses), f"MEC-6 evidence states incomplete: {statuses}")
require(all(r["reason_for_exit"]=="coverage termination" for r in mec), "external exit-pressure fixture drift")

cert=(SAMPLES/"synthetic_exposure_certificate.report.md").read_text(encoding="utf-8")
for section in ["## Theorem", "## Assumptions", "## Parameter provenance", "## Proof identity", "## Model-risk note"]:
    require(section in cert, f"certificate missing {section}")
require("not evidence that a drug, dose, taper, or discontinuation is safe for a patient" in cert, "certificate clinical boundary missing")

manifest={}
for p in sorted(ROOT.rglob("*")):
    if p.is_file() and p.name != "QUALIFICATION.json":
        manifest[str(p.relative_to(ROOT)).replace("\\","/")]={"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}

result={
    "schema":"clinical-site-fabric/qualification@1",
    "release":"0.2.0",
    "status":"PASS" if not errors else "FAIL",
    "static_checks":20,
    "fixture_counts":expected,
    "expected_resource_collisions":1,
    "errors":errors,
    "files":manifest,
    "browser_selftest":"Run ?selftest=1; body[data-selftest=pass] requires 12/12 cells.",
    "boundary":"Static and synthetic mechanism evidence only; no clinical, HIPAA, Part 11, GxP, EHR, EDC, or sponsor validation."
}
(ROOT/"QUALIFICATION.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if errors:
    print(json.dumps(result,indent=2)); sys.exit(1)
print(json.dumps(result,indent=2))
