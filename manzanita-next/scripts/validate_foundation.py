from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-schema", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((args.root / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads(args.source_schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    entries = manifest["entries"]
    by_id = {entry["source_id"]: entry for entry in entries}

    for entry in entries:
        errors = sorted(validator.iter_errors(entry), key=lambda error: list(error.path))
        assert not errors, f"{entry['source_id']}: {[error.message for error in errors]}"
        payload = entry["payload"]
        if payload["path"]:
            path = args.root / payload["path"]
            assert path.exists(), path
            data = path.read_bytes()
            assert len(data) == payload["bytes"], (path, len(data), payload["bytes"])
            assert hashlib.sha256(data).hexdigest() == payload["sha256"], path

    required = ["nws_points", "nws_forecast", "nws_alerts", "calfire_incidents", "usgs_imagery", "usgs_3dep_hillshade", "osm_overpass"]
    missing = [source_id for source_id in required if by_id.get(source_id, {}).get("status") != "ok"]
    assert not missing, f"required sources failed or missing: {missing}"
    assert manifest["required_failures"] == [], manifest["required_failures"]

    for source_id in ("usgs_imagery", "usgs_3dep_hillshade"):
        path = args.root / by_id[source_id]["payload"]["path"]
        with Image.open(path) as image:
            assert image.width >= 1200 and image.height >= 900, (source_id, image.size)
            assert image.format == "PNG", (source_id, image.format)

    optional_statuses = {"ok", "empty", "failed", "skipped_missing_credential"}
    for source_id in ("google_street_view", "mapillary", "kartaview", "panoramax", "airnow", "firms"):
        assert source_id in by_id, source_id
        assert by_id[source_id]["status"] in optional_statuses, (source_id, by_id[source_id]["status"])

    serialized_manifest = json.dumps(manifest)
    for name in ("AIRNOW_API_KEY", "FIRMS_MAP_KEY", "GOOGLE_MAPS_API_KEY", "MAPILLARY_ACCESS_TOKEN", "USGS_API_KEY"):
        secret = os.getenv(name)
        if secret:
            assert secret not in serialized_manifest, f"credential leaked into manifest: {name}"

    now = datetime.now(timezone.utc)
    generated = datetime.fromisoformat(manifest["generated_at"].replace("Z", "+00:00"))
    assert abs((now - generated).total_seconds()) < 3600

    qualification = {
        "schema": "manzanita-works/source-foundation-qualification@1",
        "qualified_at": now.isoformat().replace("+00:00", "Z"),
        "place_id": manifest["place_id"],
        "required_sources": required,
        "receipt_count": len(entries),
        "successful_sources": sorted(entry["source_id"] for entry in entries if entry["status"] == "ok"),
        "empty_sources": sorted(entry["source_id"] for entry in entries if entry["status"] == "empty"),
        "optional_failures": sorted(entry["source_id"] for entry in entries if entry["status"] == "failed"),
        "missing_credentials": sorted(entry["source_id"] for entry in entries if entry["status"] == "skipped_missing_credential"),
        "result": "PASS",
    }
    (args.root / "qualification.json").write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qualification, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
