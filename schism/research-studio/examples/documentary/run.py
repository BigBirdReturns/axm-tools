#!/usr/bin/env python3
"""Collect, verify and display the included public documentary findings."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Directory for the local catalog and verification receipt")
    parser.add_argument("--check-only", action="store_true", help="Collect and verify, then exit")
    parser.add_argument("--port", type=int, default=8374)
    args = parser.parse_args()
    definition = importlib.util.spec_from_file_location("research_studio", SOURCE_ROOT / "app" / "studio.py")
    studio = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(studio)
    source = HERE / "findings.json"
    pins = {filename: digest for digest, filename in
            (line.split() for line in (HERE / "SHA256SUMS").read_text(encoding="ascii").splitlines())}
    for filename, digest in pins.items():
        path = (HERE / filename).resolve(strict=True)
        if not path.is_relative_to(HERE) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("A documentary source differs from its published checksum: " + filename)
    expected = pins[source.name]
    document = studio.load_json(source)
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="schism-research-"))
    output.mkdir(parents=True, exist_ok=True)
    source_id = "public-vendor-findings"
    extract = {"summary": "/aggregate_conclusion", "notes": "/qualifications", "metrics": "/metrics"}
    vendors, declarations = [], []
    for index, vendor in enumerate(document["vendors"]):
        vendor_source_id = "public-vendor-" + vendor["id"]
        vendor_filename = "records/" + vendor["id"] + ".json"
        vendor_path = HERE / vendor_filename
        if studio.load_json(vendor_path) != vendor:
            raise ValueError("Vendor record differs from aggregate findings: " + vendor["id"])
        bindings = {}
        for key in ("name", "notes", "documentary_evidence"):
            bindings[key] = {"source_ref": vendor_source_id, "field": key}
        declarations.append({"id": vendor_source_id, "title": vendor["name"] + ": documentary review",
                             "kind": "documentary_review", "project": "Public vendor review",
                             "source_date": "2026-11-27 (Pacific)", "path": str(vendor_path),
                             "expected_sha256": pins[vendor_filename], "expected_bytes": vendor_path.stat().st_size,
                             "extract": {key: "/" + key for key in bindings}})
        vendors.append({"id": vendor["id"], "state": "documentation_only", "project": "Public vendor review",
                        "source_ref": vendor_source_id, "derive": bindings})
    spec = {"read_roots": [str(HERE)], "sources": [{
        "id": source_id, "title": "Public vendor findings and citations, 27 November 2026 Pacific",
        "kind": "documentary_review", "project": "Public vendor review",
        "source_date": "2026-11-27 (Pacific)", "path": str(source), "expected_sha256": expected,
        "expected_bytes": source.stat().st_size, "extract": extract,
        "notes": [document["projection"]["scope"]]}] + declarations, "catalog": {
        "title": "Research Studio: public documentary sample",
        "summary": [document["aggregate_conclusion"], document["projection"]["scope"]],
        "sources": [], "campaigns": [], "gaps": [], "vendors": vendors,
        "components": [{"id": "public-vendor-review", "title": "Public vendor review", "role": "Documentary evidence",
                        "status": "retained", "summary": "Seventeen vendor records, scoped claims, published reports and public citations.",
                        "evidence_refs": [source_id], "limitations": ["Local collection verifies the included source file and extracted fields."]}],
        "lineage": [{"id": "ledger-review", "date": "2026-11-27", "title": "Original vendor ledger",
                     "description": "Seventeen vendors reviewed under a bounded documentary search.", "source_refs": [source_id]},
                    {"id": "primary-addendum", "date": "2026-11-27 (Pacific)", "title": "Primary-source addendum",
                     "description": "Participant accounts and source qualifications retained in the public findings. Retained UTC timestamp: 28 November 2026.", "source_refs": [source_id]}],
        "findings": [{"id": "public-vendor-summary", "kind": "vendor-summary", "title": document["title"],
                      "status": "retained", "source_ref": source_id,
                      "derive": {key: {"source_ref": source_id, "field": key} for key in ("summary", "notes", "metrics")}}]}}
    spec_path = output / "collection-spec.json"
    catalog_path = output / "catalog.json"
    studio.write_json(spec_path, spec)
    collection = studio.collect(spec_path, catalog_path)
    verification = studio.verify(catalog_path, [HERE])
    studio.write_json(output / "verification.json", verification)
    if collection["unverified"] or not verification["passed"]:
        raise RuntimeError("Documentary sample verification failed")
    print(json.dumps({"verified": True, "vendor_records": len(vendors), "source_sha256": expected,
                      "catalog": str(catalog_path), "verification": str(output / "verification.json"),
                      "new_simulations": collection["new_simulations"]}, indent=2), flush=True)
    if not args.check_only:
        print("Open http://127.0.0.1:" + str(args.port) + "/ and select Vendor access. Press Ctrl+C to stop.", flush=True)
        try:
            studio.serve(catalog_path, args.port)
        except KeyboardInterrupt:
            print("Reader stopped.")


if __name__ == "__main__":
    main()
