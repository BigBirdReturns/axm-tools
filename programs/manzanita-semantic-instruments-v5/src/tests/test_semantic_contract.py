#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_sha(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT)
    args = parser.parse_args()
    data = json.loads((args.site / "data.json").read_text(encoding="utf-8"))

    require(data["release"] == "source-adaptive-semantic-v5", "Release identity drifted")
    require(len(data["apertures"]) == 7, "Aperture count drifted")
    require(len(data["instruments"]) == 8, "Instrument count drifted")
    require(len(data["sourceModes"]) == 5, "Source-mode count drifted")
    require(len(data["seats"]) == 5, "Seat count drifted")
    require(data["instrumentRendering"]["access"]["surface"] == "semantic_registration", "Access law drifted")
    require(data["instrumentRendering"]["shade"]["surface"] == "semantic_optional", "Shade law drifted")
    require(data["instrumentRendering"]["water"]["surface"] == "semantic_optional", "Water law drifted")
    standalone = args.site / "STANDALONE.html"
    require(standalone.is_file() and standalone.stat().st_size > 1_000_000, "Self-contained standalone is missing or empty")
    standalone_text = standalone.read_text(encoding="utf-8", errors="replace")
    require('href="style.css"' not in standalone_text and 'src="app.js"' not in standalone_text, "Standalone retained external CSS or runtime files")
    require('data:image/' in standalone_text, "Standalone did not embed visual assets")

    source_text = "\n".join(
        (args.site / name).read_text(encoding="utf-8", errors="replace")
        for name in ("index.html", "app.js", "data.json")
    ).lower()
    for forbidden in ("sobel", "find_edges", "gradient registration", "generic line"):
        require(forbidden not in source_text, f"Generic registration mechanism survived: {forbidden}")

    asset_ids: set[str] = set()
    for key, asset in data["assets"].items():
        path = args.site / asset["path"]
        require(path.is_file(), f"Missing asset for {key}: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest == asset["asset_id"], f"Asset digest mismatch for {key}")
        require(asset["asset_id"] not in asset_ids, f"Duplicate asset identity: {asset['asset_id']}")
        asset_ids.add(asset["asset_id"])

    allowed = {
        "access": {"public_sidewalk", "driveway_crossing", "private_drive_side_access", "entry_path", "entry_steps"},
        "shade": {"visible_leaf_canopy", "seasonal_open_crown"},
        "water": {"roof_collection_surface", "eave_edge", "curb_gutter"},
    }
    required_receipts = {"access": 3, "shade": 5, "water": 2}
    required_features = {"access": 11, "shade": 11, "water": 10}
    counts: Counter[str] = Counter()
    feature_counts: Counter[str] = Counter()
    receipt_assets: defaultdict[str, set[str]] = defaultdict(set)
    feature_ids: set[str] = set()

    for key, receipt in data["registrations"].items():
        instrument = receipt["instrument"]
        require(instrument in allowed, f"Unexpected geometric instrument: {instrument}")
        require(key == f"{receipt['asset_id']}:{instrument}", f"Registration lookup key drifted: {key}")
        require(receipt["asset_id"] in asset_ids, f"Registration references unknown asset: {key}")
        require(receipt["coordinate_space"] == "source_image_1600x1000", f"Coordinate space drifted: {key}")
        require(receipt["interpretation_class"] == "authored_semantic_visual_interpretation", f"Interpretation class drifted: {key}")
        require(receipt["feature_count"] == len(receipt["features"]) > 0, f"Feature count drifted: {key}")
        require(set(receipt["feature_classes"]) <= allowed[instrument], f"Unknown semantic class: {key}")
        body = dict(receipt)
        expected = body.pop("receipt_sha256")
        require(canonical_sha(body) == expected, f"Receipt digest mismatch: {key}")
        require(receipt["asset_id"] not in receipt_assets[instrument], f"Asset inherited two {instrument} receipts: {key}")
        receipt_assets[instrument].add(receipt["asset_id"])
        counts[instrument] += 1
        feature_counts[instrument] += receipt["feature_count"]

        for feature in receipt["features"]:
            require(feature["id"] not in feature_ids, f"Duplicate semantic feature identity: {feature['id']}")
            feature_ids.add(feature["id"])
            require(feature["class"] in allowed[instrument], f"Unsupported feature class: {feature['class']}")
            require(feature["geometry"]["type"] in {"polygon", "polyline"}, f"Unsupported geometry type: {feature['id']}")
            points = feature["geometry"]["points"]
            minimum = 4 if feature["geometry"]["type"] == "polygon" else 2
            require(len(points) >= minimum, f"Geometry has too few points: {feature['id']}")
            require(all(0 <= x <= 1600 and 0 <= y <= 1000 for x, y in points), f"Geometry escapes exact source image: {feature['id']}")
            require(feature["evidence"].strip(), f"Feature lacks evidence: {feature['id']}")
            require(feature["non_claim"].strip(), f"Feature lacks non-claim: {feature['id']}")

    require(dict(counts) == required_receipts, f"Semantic receipt coverage drifted: {dict(counts)}")
    require(dict(feature_counts) == required_features, f"Semantic feature coverage drifted: {dict(feature_counts)}")

    expected_access_assets = {
        data["assets"]["street:reference"]["asset_id"],
        *(data["assets"][key]["asset_id"] for key in data["streetProviderScenes"]),
    }
    expected_shade_assets = {
        data["assets"]["household:reference"]["asset_id"],
        data["assets"]["property:reference"]["asset_id"],
        *expected_access_assets,
    }
    expected_water_assets = {
        data["assets"]["household:reference"]["asset_id"],
        data["assets"]["property:reference"]["asset_id"],
    }
    require(receipt_assets["access"] == expected_access_assets, "Access receipt asset set drifted")
    require(receipt_assets["shade"] == expected_shade_assets, "Shade receipt asset set drifted")
    require(receipt_assets["water"] == expected_water_assets, "Water receipt asset set drifted")

    print(json.dumps({
        "result": "PASS",
        "assets": len(asset_ids),
        "semantic_receipts": sum(counts.values()),
        "semantic_receipts_by_instrument": dict(counts),
        "semantic_features": sum(feature_counts.values()),
        "semantic_features_by_instrument": dict(feature_counts),
        "generic_gradient_registrations": 0,
        "image_geometry_instruments": ["shade", "water", "access"],
        "public_route_effect": "none",
    }, indent=2))


if __name__ == "__main__":
    main()
