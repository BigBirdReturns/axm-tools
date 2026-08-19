#!/usr/bin/env python3
"""Static release and exact-asset semantic contract for Manzanita v1.7.0."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

RELEASE = "1.7.0"
VISUAL_SYSTEM = "semantic-source-adaptive-place-fabric"
EXPECTED_RECEIPTS = {"access": 3, "shade": 5, "water": 2}
EXPECTED_FEATURES = {"access": 11, "shade": 11, "water": 10}
SEMANTIC = set(EXPECTED_RECEIPTS)
NON_GEOMETRIC = {"care", "heat", "air", "fire", "assistance"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def recursive_strings(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from recursive_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from recursive_strings(nested)
    elif isinstance(value, str):
        yield value


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "manzanita").resolve()
    required = [
        "index.html", "app.js", "style.css", "v5-semantic.js", "v5-semantic.css",
        "data.json", "standalone.html", "RELEASE.json", "QUALIFICATION.json",
    ]
    for relative in required:
        require((root / relative).is_file(), f"Missing required release file: {relative}")

    html = (root / "index.html").read_text(encoding="utf-8")
    require(f'data-release="{RELEASE}"' in html, "Index release marker drifted")
    require(f'data-visual-system="{VISUAL_SYSTEM}"' in html, "Index visual-system marker drifted")
    require("bigbirdreturns.github.io/axm-tools/manzanita/" in html, "Canonical public route is absent")
    require("source-adaptive-semantic-v5" not in html, "Review release leaked into the public index")
    require("review_evidence_not_public_release" not in html, "Review-only classification leaked into public index")

    data = json.loads((root / "data.json").read_text(encoding="utf-8"))
    release = json.loads((root / "RELEASE.json").read_text(encoding="utf-8"))
    qualification = json.loads((root / "QUALIFICATION.json").read_text(encoding="utf-8"))
    require(data["release"] == RELEASE, "Runtime release drifted")
    require(data["visual_system"] == VISUAL_SYSTEM, "Runtime visual system drifted")
    require(data["classification"] == "bounded_public_read_only_semantic_place_fabric", "Runtime classification drifted")
    require(data["external_effect"] == "none", "Runtime requests an external effect")
    require(data["canonical_task_count_effect"] == "none", "Runtime requests a canonical task-count effect")
    require(release["release"] == RELEASE and release["visual_system"] == VISUAL_SYSTEM, "Release receipt drifted")
    require(release["authority"]["external_effect"] == "none", "Release receipt grants an external effect")
    require(release["authority"]["field_authority"] == "none", "Release receipt grants field authority")
    require(release["authority"]["adverse_action_authority"] == "none", "Release receipt grants adverse authority")

    apertures = data.get("apertures", {})
    instruments = data.get("instruments", {})
    modes = data.get("sourceModes", {})
    seats = data.get("seats", {})
    assets = data.get("assets", {})
    registrations = data.get("registrations", {})
    require(len(apertures) == 7, f"Expected seven apertures, found {len(apertures)}")
    require(set(instruments) == {"care", "shade", "water", "heat", "air", "fire", "access", "assistance"}, "Instrument set drifted")
    require(len(modes) == 5, f"Expected five source modes, found {len(modes)}")
    require(len(seats) == 5, f"Expected five functional seats, found {len(seats)}")
    require(len(assets) == 10, f"Expected ten source-native assets, found {len(assets)}")

    for key, asset in assets.items():
        path = root / asset["path"]
        require(path.is_file(), f"Asset is missing: {key} -> {path}")
        require(sha256(path) == asset["asset_id"], f"Asset SHA-256 identity drifted: {key}")
        require(asset.get("width") == 1600 and asset.get("height") == 1000, f"Asset coordinate frame drifted: {key}")

    receipt_counts = {key: 0 for key in EXPECTED_RECEIPTS}
    feature_counts = {key: 0 for key in EXPECTED_FEATURES}
    registration_geometry = {}
    for key, receipt in registrations.items():
        instrument = str(receipt.get("instrument") or key.rsplit(":", 1)[-1]).lower()
        require(instrument in SEMANTIC, f"Non-semantic instrument carries local image registration: {instrument}")
        require(key == f"{receipt['asset_id']}:{instrument}", f"Registration is not keyed to exact asset and instrument: {key}")
        require(receipt["asset_id"] in {row["asset_id"] for row in assets.values()}, f"Registration refers to unknown asset: {key}")
        method_text = json.dumps(receipt.get("method", {})).lower()
        require(all(term not in method_text for term in ("sobel", "gradient", "generic_edge", "strongest_contrast")), f"Generic contrast tracing remains in {key}")
        require(receipt.get("coordinate_space") == "normalized_asset_frame_1600x1000", f"Registration coordinate space drifted: {key}")
        features = receipt.get("features", [])
        require(receipt.get("feature_count") == len(features), f"Feature count drifted: {key}")
        require(bool(features), f"Semantic receipt has no features: {key}")
        signatures = []
        for feature in features:
            require(feature.get("feature_id"), f"Unnamed semantic feature in {key}")
            require(feature.get("feature_class"), f"Unclassified semantic feature in {key}")
            require(feature.get("geometry", {}).get("points"), f"Feature geometry is absent in {key}")
            require(feature.get("evidence"), f"Feature evidence is absent in {key}")
            require(feature.get("confidence"), f"Feature confidence is absent in {key}")
            require(feature.get("non_claim"), f"Feature non-claim is absent in {key}")
            require(feature.get("unknowns"), f"Feature unknowns are absent in {key}")
            require(feature.get("safe_action"), f"Feature safe action is absent in {key}")
            require(feature.get("authority"), f"Feature authority is absent in {key}")
            points = feature["geometry"]["points"]
            require(all(isinstance(point, list) and len(point) == 2 for point in points), f"Malformed points in {key}")
            require(all(0 <= float(x) <= 1600 and 0 <= float(y) <= 1000 for x, y in points), f"Feature escapes the asset frame in {key}")
            signatures.append(canonical_sha(feature["geometry"]))
        require(len(signatures) == len(set(signatures)), f"Receipt contains duplicate feature geometry: {key}")
        receipt_counts[instrument] += 1
        feature_counts[instrument] += len(features)
        registration_geometry.setdefault(instrument, set()).add(canonical_sha([feature["geometry"] for feature in features]))

    require(receipt_counts == EXPECTED_RECEIPTS, f"Semantic receipt counts drifted: {receipt_counts}")
    require(feature_counts == EXPECTED_FEATURES, f"Semantic feature counts drifted: {feature_counts}")
    for instrument, expected in EXPECTED_RECEIPTS.items():
        require(len(registration_geometry[instrument]) == expected, f"{instrument} receipts do not carry distinct geometry")

    all_text = "\n".join(recursive_strings(data)).lower()
    require("insurance denial" in all_text or "insurance" in all_text, "Adverse-use firewall disappeared")
    require("authority" in all_text and "safe action" in all_text, "Authority or safe-action vocabulary disappeared")
    require("occluded" in all_text or "unverified" in all_text, "Semantic uncertainty vocabulary disappeared")

    require(qualification["release"] == RELEASE, "Qualification release drifted")
    require(qualification["visual_system"] == VISUAL_SYSTEM, "Qualification visual system drifted")
    require(qualification["required_semantic_receipts"] == EXPECTED_RECEIPTS, "Qualification receipt floor drifted")
    require(qualification["required_semantic_features"] == EXPECTED_FEATURES, "Qualification feature floor drifted")
    require(qualification["expected_asset_count"] == 10, "Qualification asset floor drifted")
    require(qualification["generic_gradient_registration_count"] == 0, "Qualification permits generic gradient registrations")
    for relative, expected in qualification["files"].items():
        path = root / relative
        require(path.is_file(), f"Qualified file is missing: {relative}")
        require(path.stat().st_size == expected["bytes"], f"Qualified byte count drifted: {relative}")
        require(sha256(path) == expected["sha256"], f"Qualified SHA-256 drifted: {relative}")
    candidate = dict(qualification)
    manifest_sha = candidate.pop("manifest_sha256")
    require(canonical_sha(candidate) == manifest_sha, "Qualification manifest digest drifted")

    standalone = (root / "standalone.html").read_text(encoding="utf-8")
    require("assets/" not in standalone, "Standalone retains external asset references")
    require(f'data-release="{RELEASE}"' in standalone, "Standalone release marker drifted")
    require(len(standalone.encode("utf-8")) > 2_000_000, "Standalone lacks embedded media substance")

    scripts = (root / "app.js").read_text(encoding="utf-8") + "\n" + (root / "v5-semantic.js").read_text(encoding="utf-8")
    require("fetch(" not in scripts and "XMLHttpRequest" not in scripts and "WebSocket" not in scripts, "Runtime contains an external request mechanism")
    require("window.open" not in scripts, "Runtime contains an uncontrolled external window mechanism")
    require("sobel" not in scripts.lower() and "strongest" not in scripts.lower(), "Runtime contains contrast-edge registration machinery")

    print(json.dumps({
        "result": "PASS",
        "release": RELEASE,
        "visual_system": VISUAL_SYSTEM,
        "apertures": len(apertures),
        "instruments": len(instruments),
        "source_modes": len(modes),
        "seats": len(seats),
        "assets": len(assets),
        "semantic_receipts": receipt_counts,
        "semantic_features": feature_counts,
        "qualified_files": len(qualification["files"]),
    }, indent=2))


if __name__ == "__main__":
    main()
