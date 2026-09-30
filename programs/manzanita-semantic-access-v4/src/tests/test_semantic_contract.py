#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_sha(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> None:
    global ROOT, DATA
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT)
    args = parser.parse_args()
    ROOT = args.site
    DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    require(DATA["release"] == "source-adaptive-semantic-v4", "Release identity drifted")
    require(len(DATA["apertures"]) == 7, "Aperture count drifted")
    require(len(DATA["instruments"]) == 8, "Instrument count drifted")
    require(len(DATA["sourceModes"]) == 5, "Source-mode count drifted")
    require(len(DATA["seats"]) == 5, "Seat count drifted")

    require(DATA["instruments"]["access"]["support"] == ["street"], "Access escaped the Street aperture")
    require(DATA["instrumentRendering"]["access"]["surface"] == "semantic_registration", "Access lost semantic-registration law")
    require(DATA["instrumentRendering"]["shade"]["surface"] == "source_question", "Shade regained invented image geometry")
    require(DATA["instrumentRendering"]["water"]["surface"] == "source_question", "Water regained invented image geometry")
    require(DATA["instruments"]["shade"]["kind"] == "source-question", "Shade is mislabeled as registered geometry")
    require(DATA["instruments"]["water"]["kind"] == "source-question", "Water is mislabeled as registered geometry")

    source_text = "\n".join(
        (ROOT / name).read_text(encoding="utf-8", errors="replace")
        for name in ("index.html", "app.js", "data.json")
    ).lower()
    for forbidden in ("sobel", "find_edges", "gradient registration", "generic line"):
        require(forbidden not in source_text, f"Generic registration mechanism survived: {forbidden}")

    asset_ids: set[str] = set()
    for key, asset in DATA["assets"].items():
        path = ROOT / asset["path"]
        require(path.is_file(), f"Missing asset for {key}: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest == asset["asset_id"], f"Asset digest mismatch for {key}")
        require(asset["asset_id"] not in asset_ids, f"Duplicate asset identity: {asset['asset_id']}")
        asset_ids.add(asset["asset_id"])

    registrations = DATA["registrations"]
    require(len(registrations) == 3, "Expected three exact Street Access receipts")
    allowed_classes = {"public_sidewalk", "driveway_crossing", "private_drive_side_access", "entry_path", "entry_steps"}
    all_feature_ids: set[str] = set()
    all_receipt_assets: set[str] = set()
    for key, receipt in registrations.items():
        require(key == f"{receipt['asset_id']}:access", f"Registration lookup key drifted: {key}")
        require(receipt["asset_id"] in asset_ids, f"Registration references unknown asset: {key}")
        require(receipt["aperture"] == "street" and receipt["instrument"] == "access", f"Registration scope drifted: {key}")
        require(receipt["coordinate_space"] == "source_image_1600x1000", f"Coordinate space drifted: {key}")
        require(receipt["interpretation_class"] == "authored_semantic_visual_interpretation", f"Interpretation class drifted: {key}")
        require(receipt["coverage"] == "partial_visible_access_topology", f"Coverage overclaimed: {key}")
        require(receipt["feature_count"] == len(receipt["features"]) >= 3, f"Feature count drifted: {key}")
        require(set(receipt["feature_classes"]) <= allowed_classes, f"Unknown semantic feature class: {key}")
        body = dict(receipt)
        expected = body.pop("receipt_sha256")
        require(canonical_sha(body) == expected, f"Receipt digest mismatch: {key}")
        require(receipt["asset_id"] not in all_receipt_assets, f"Asset inherited more than one Access receipt: {key}")
        all_receipt_assets.add(receipt["asset_id"])

        for feature in receipt["features"]:
            require(feature["id"] not in all_feature_ids, f"Duplicate semantic feature identity: {feature['id']}")
            all_feature_ids.add(feature["id"])
            require(feature["class"] in allowed_classes, f"Unsupported feature class: {feature['class']}")
            require(feature["geometry"]["type"] == "polygon", f"Access feature is not an area: {feature['id']}")
            points = feature["geometry"]["points"]
            require(len(points) >= 4, f"Access polygon has too few points: {feature['id']}")
            require(all(0 <= x <= 1600 and 0 <= y <= 1000 for x, y in points), f"Access polygon escapes its exact source image: {feature['id']}")
            require(feature["evidence"].strip(), f"Feature lacks evidence: {feature['id']}")
            require(feature["non_claim"].strip(), f"Feature lacks non-claim: {feature['id']}")

    street_receipt_assets = {
        DATA["assets"]["street:reference"]["asset_id"],
        *(DATA["assets"][key]["asset_id"] for key in DATA["streetProviderScenes"]),
    }
    require(all_receipt_assets == street_receipt_assets, "Street Access receipts do not cover the exact retained scene set")

    print(json.dumps({
        "result": "PASS",
        "assets": len(asset_ids),
        "semantic_receipts": len(registrations),
        "semantic_features": len(all_feature_ids),
        "generic_gradient_registrations": 0,
        "image_geometry_instruments": ["access"],
        "public_route_effect": "none",
    }, indent=2))


if __name__ == "__main__":
    main()
