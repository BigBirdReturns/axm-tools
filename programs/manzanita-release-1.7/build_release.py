#!/usr/bin/env python3
"""Build Manzanita Works v1.7.0 from the exact semantic-instruments v5 artifact.

This script performs a bounded public read-only promotion. It preserves the
current public route as an exact predecessor manifest, imports the reviewed
runtime, changes release identity without changing semantic receipts, emits
permanent source and browser tests, and hashes the final public file set.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

RELEASE = "1.7.0"
VISUAL_SYSTEM = "semantic-source-adaptive-place-fabric"
SOURCE_RUN_ID = 32270492054
SOURCE_REVIEW = "source-adaptive-semantic-v5"
SOURCE_REVIEW_HEAD = "fd9dad4e787f781492467e7680fb2774ec7f7e66"
EXPECTED_RECEIPTS = {"access": 3, "shade": 5, "water": 2}
EXPECTED_FEATURES = {"access": 11, "shade": 11, "water": 10}
RUNTIME_TOP_LEVEL = {
    "index.html",
    "app.js",
    "style.css",
    "v5-semantic.js",
    "v5-semantic.css",
    "data.json",
    "README.md",
    "REVIEW_CONTRACT.json",
    "BUILD_RECEIPT.json",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(("git", *args), cwd=cwd, text=True).strip()


def locate_review(root: Path) -> Path:
    candidates = sorted(
        path.parent
        for path in root.rglob("index.html")
        if path.parent.name == "manzanita-semantic-instruments-v5"
        or "manzanita-semantic-instruments-v5" in path.parent.as_posix()
    )
    require(bool(candidates), f"No semantic-instruments v5 review exists under {root}")
    scored: list[tuple[int, Path]] = []
    for candidate in candidates:
        score = sum((candidate / name).is_file() for name in ("data.json", "app.js", "style.css", "v5-semantic.js", "BUILD_RECEIPT.json", "BROWSER_AUDIT.json"))
        scored.append((score, candidate))
    scored.sort(reverse=True)
    require(scored[0][0] >= 5, f"Best semantic review candidate is incomplete: {scored[0]}")
    return scored[0][1]


def registration_summary(data: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    receipt_counts = {key: 0 for key in EXPECTED_RECEIPTS}
    feature_counts = {key: 0 for key in EXPECTED_FEATURES}
    for key, receipt in data.get("registrations", {}).items():
        instrument = str(receipt.get("instrument") or key.rsplit(":", 1)[-1]).lower()
        if instrument not in receipt_counts:
            continue
        require(receipt.get("asset_id"), f"Registration {key} lacks asset identity")
        require(key == f"{receipt['asset_id']}:{instrument}", f"Registration key is not exact-asset bound: {key}")
        method = json.dumps(receipt.get("method", {})).lower()
        require("sobel" not in method and "gradient" not in method and "generic" not in method, f"Registration {key} retains generic edge tracing")
        features = receipt.get("features", [])
        require(isinstance(features, list), f"Registration {key} features are not a list")
        require(int(receipt.get("feature_count", len(features))) == len(features), f"Registration {key} feature count drifted")
        for feature in features:
            require(feature.get("feature_id"), f"Registration {key} has an unnamed feature")
            require(feature.get("feature_class"), f"Registration {key} has an unclassified feature")
            require(feature.get("geometry"), f"Registration {key} feature {feature.get('feature_id')} lacks geometry")
            require(feature.get("evidence"), f"Registration {key} feature {feature.get('feature_id')} lacks evidence")
            require(feature.get("confidence"), f"Registration {key} feature {feature.get('feature_id')} lacks confidence")
            require(feature.get("non_claim"), f"Registration {key} feature {feature.get('feature_id')} lacks non-claim")
            require(feature.get("unknowns"), f"Registration {key} feature {feature.get('feature_id')} lacks unknowns")
            require(feature.get("safe_action"), f"Registration {key} feature {feature.get('feature_id')} lacks safe action")
        receipt_counts[instrument] += 1
        feature_counts[instrument] += len(features)
    return receipt_counts, feature_counts


def preserve_predecessor(repo: Path, public_root: Path, evidence_root: Path, base_sha: str) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(p for p in public_root.rglob("*") if p.is_file()):
        payload = path.read_bytes()
        files[path.relative_to(public_root).as_posix()] = {
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "git_blob_sha1": git_blob_sha(payload),
        }
    index_text = (public_root / "index.html").read_text(encoding="utf-8", errors="replace")
    marker = re.search(r'data-release=["\']([^"\']+)', index_text)
    receipt = {
        "schema": "manzanita-works/predecessor-public-route@1",
        "release": marker.group(1) if marker else "unknown",
        "source_commit": base_sha,
        "source_tree": git("rev-parse", f"{base_sha}:manzanita", cwd=repo),
        "route": "manzanita/",
        "files": files,
        "rollback_law": "Restore the exact predecessor tree and redeploy through the ordinary Pages workflow. This receipt does not claim that rollback has been performed.",
    }
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "PREDECESSOR_V1_6_0.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def copy_review(review: Path, public_root: Path) -> None:
    if public_root.exists():
        shutil.rmtree(public_root)
    public_root.mkdir(parents=True)
    for path in sorted(review.iterdir()):
        if path.name in {"evidence", "BROWSER_AUDIT.json", "standalone.html"}:
            continue
        if path.is_dir():
            if path.name == "assets":
                shutil.copytree(path, public_root / path.name)
            continue
        if path.name in RUNTIME_TOP_LEVEL:
            shutil.copy2(path, public_root / path.name)
    required = {"index.html", "app.js", "style.css", "v5-semantic.js", "v5-semantic.css", "data.json", "assets"}
    require(all((public_root / item).exists() for item in required), f"Imported runtime is incomplete: {[item for item in required if not (public_root/item).exists()]}")


def patch_html(index_path: Path, data: dict[str, Any]) -> None:
    text = index_path.read_text(encoding="utf-8")
    if re.search(r"<html\b", text, flags=re.I):
        text = re.sub(r"<html\b[^>]*>", f'<html lang="en" data-release="{RELEASE}" data-visual-system="{VISUAL_SYSTEM}">', text, count=1, flags=re.I)
    else:
        raise SystemExit("Release index lacks an html element")
    text = text.replace(SOURCE_REVIEW, RELEASE)
    replacements = {
        "Manzanita semantic instruments v5 review": "Manzanita Works · Semantic Place Fabric",
        "MANZANITA SEMANTIC INSTRUMENTS V5": "MANZANITA WORKS · SEMANTIC PLACE FABRIC",
        "review_evidence_not_public_release": "bounded_public_read_only_release",
        "REVIEW OBJECT": "PUBLIC READ-ONLY PLACE FABRIC",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"<title>.*?</title>", "<title>Manzanita Works · Semantic Place Fabric</title>", text, count=1, flags=re.I | re.S)
    head_insert = f'''\n  <meta name="description" content="A source-adaptive place fabric with exact-asset semantic Access, Shade, and Water instruments; visible failure states; five functional seats; and assistance-first handoff.">\n  <meta name="application-name" content="Manzanita Works">\n  <meta name="theme-color" content="#111510">\n  <meta name="color-scheme" content="dark light">\n  <link rel="canonical" href="https://bigbirdreturns.github.io/axm-tools/manzanita/">\n  <meta property="og:type" content="website">\n  <meta property="og:title" content="Manzanita Works · Semantic Place Fabric">\n  <meta property="og:description" content="Seven place apertures, exact-asset semantic instruments, source failure custody, five functional seats, and bounded public handoff.">\n  <meta property="og:url" content="https://bigbirdreturns.github.io/axm-tools/manzanita/">\n'''
    if "rel=\"canonical\"" not in text:
        text = text.replace("</head>", head_insert + "</head>", 1)
    else:
        text = re.sub(r'<link[^>]+rel=["\']canonical["\'][^>]*>', '<link rel="canonical" href="https://bigbirdreturns.github.io/axm-tools/manzanita/">', text, count=1, flags=re.I)
    compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    patterns = [
        r'(<script[^>]+id=["\']manzanita-data["\'][^>]*>).*?(</script>)',
        r'(<script[^>]+id=["\']semantic-data["\'][^>]*>).*?(</script>)',
    ]
    for pattern in patterns:
        if re.search(pattern, text, flags=re.I | re.S):
            text = re.sub(pattern, lambda m: m.group(1) + compact + m.group(2), text, count=1, flags=re.I | re.S)
            break
    else:
        old_data = re.search(r'<script[^>]+type=["\']application/json["\'][^>]*>(\{.*?\})</script>', text, flags=re.I | re.S)
        require(old_data is not None, "Could not locate embedded Manzanita data in index.html")
        text = text[: old_data.start(1)] + compact + text[old_data.end(1) :]
    index_path.write_text(text, encoding="utf-8")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def build_standalone(public_root: Path, data: dict[str, Any]) -> None:
    standalone_data = json.loads(json.dumps(data))
    for asset in standalone_data.get("assets", {}).values():
        relative = asset.get("path")
        if relative:
            asset["path"] = data_uri(public_root / relative)
    html = (public_root / "index.html").read_text(encoding="utf-8")
    compact = json.dumps(standalone_data, ensure_ascii=False, separators=(",", ":"))
    for pattern in (
        r'(<script[^>]+id=["\']manzanita-data["\'][^>]*>).*?(</script>)',
        r'(<script[^>]+id=["\']semantic-data["\'][^>]*>).*?(</script>)',
    ):
        if re.search(pattern, html, flags=re.I | re.S):
            html = re.sub(pattern, lambda m: m.group(1) + compact + m.group(2), html, count=1, flags=re.I | re.S)
            break
    else:
        block = re.search(r'<script[^>]+type=["\']application/json["\'][^>]*>(\{.*?\})</script>', html, flags=re.I | re.S)
        require(block is not None, "Standalone builder could not locate embedded data")
        html = html[: block.start(1)] + compact + html[block.end(1) :]
    for css_name in ("style.css", "v5-semantic.css"):
        css = (public_root / css_name).read_text(encoding="utf-8")
        html = re.sub(rf'<link[^>]+href=["\']{re.escape(css_name)}["\'][^>]*>', f"<style data-source=\"{css_name}\">{css}</style>", html, count=1, flags=re.I)
    for js_name in ("app.js", "v5-semantic.js"):
        js = (public_root / js_name).read_text(encoding="utf-8")
        html = re.sub(rf'<script[^>]+src=["\']{re.escape(js_name)}["\'][^>]*></script>', f"<script data-source=\"{js_name}\">{js}</script>", html, count=1, flags=re.I)
    require("assets/" not in html, "Standalone still contains external asset references")
    (public_root / "standalone.html").write_text(html, encoding="utf-8")


def patch_catalog(repo: Path) -> None:
    readme = repo / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        text = re.sub(r"Manzanita Works v1\.6\.0", f"Manzanita Works v{RELEASE}", text)
        text = re.sub(r"Manzanita Works v1\.6", f"Manzanita Works v{RELEASE}", text)
        readme.write_text(text, encoding="utf-8")
    index = repo / "index.html"
    if index.is_file():
        text = index.read_text(encoding="utf-8")
        text = re.sub(r"Manzanita Works v1\.6\.0", f"Manzanita Works v{RELEASE}", text)
        text = re.sub(r"Manzanita Works v1\.6", f"Manzanita Works v{RELEASE}", text)
        index.write_text(text, encoding="utf-8")


def write_release_receipts(public_root: Path, evidence_root: Path, data: dict[str, Any], predecessor: dict[str, Any], source_build: dict[str, Any], source_browser: dict[str, Any], base_sha: str) -> None:
    receipt_counts, feature_counts = registration_summary(data)
    require(receipt_counts == EXPECTED_RECEIPTS, f"Semantic receipt counts drifted: {receipt_counts}")
    require(feature_counts == EXPECTED_FEATURES, f"Semantic feature counts drifted: {feature_counts}")
    assets = data.get("assets", {})
    require(len(assets) == 10, f"Expected ten source-native assets, found {len(assets)}")
    for key, asset in assets.items():
        path = public_root / asset["path"]
        require(path.is_file(), f"Asset {key} missing at {path}")
        require(sha256_file(path) == asset["asset_id"], f"Asset identity mismatch for {key}")
    release = {
        "schema": "manzanita-works/public-release@1",
        "release": RELEASE,
        "visual_system": VISUAL_SYSTEM,
        "release_class": "bounded_public_read_only_semantic_place_fabric",
        "source_review": {
            "release": SOURCE_REVIEW,
            "workflow_run_id": SOURCE_RUN_ID,
            "review_head": SOURCE_REVIEW_HEAD,
            "build_result": source_build.get("result"),
            "browser_result": source_browser.get("result"),
        },
        "semantic_receipts": receipt_counts,
        "semantic_features": feature_counts,
        "asset_count": len(assets),
        "predecessor": {
            "release": predecessor["release"],
            "commit": predecessor["source_commit"],
            "tree": predecessor["source_tree"],
        },
        "authority": {
            "public_projection": "read_only",
            "external_effect": "none",
            "field_authority": "none",
            "adverse_action_authority": "none",
            "canonical_task_count_effect": "none",
        },
        "control_question": "Does every public semantic feature remain bound to the exact displayed asset and selected instrument while unsupported, map-only, held, unknown, and non-geometric states refuse local image geometry?",
    }
    (public_root / "RELEASE.json").write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (evidence_root / "SOURCE_REVIEW_BUILD_RECEIPT.json").write_text(json.dumps(source_build, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (evidence_root / "SOURCE_REVIEW_BROWSER_AUDIT.json").write_text(json.dumps(source_browser, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_ref = {
        "schema": "manzanita-works/semantic-source-reference@1",
        "review_release": SOURCE_REVIEW,
        "workflow_run_id": SOURCE_RUN_ID,
        "review_head": SOURCE_REVIEW_HEAD,
        "imported_at_base_commit": base_sha,
        "source_build_sha256": canonical_sha(source_build),
        "source_browser_sha256": canonical_sha(source_browser),
    }
    (evidence_root / "SOURCE_REVIEW_REFERENCE.json").write_text(json.dumps(source_ref, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def qualification(public_root: Path) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(p for p in public_root.rglob("*") if p.is_file() and p.name != "QUALIFICATION.json"):
        payload = path.read_bytes()
        files[path.relative_to(public_root).as_posix()] = {"bytes": len(payload), "sha256": sha256_bytes(payload)}
    value = {
        "schema": "manzanita-works/public-qualification@3",
        "release": RELEASE,
        "visual_system": VISUAL_SYSTEM,
        "source_review_run_id": SOURCE_RUN_ID,
        "required_semantic_receipts": EXPECTED_RECEIPTS,
        "required_semantic_features": EXPECTED_FEATURES,
        "expected_asset_count": 10,
        "generic_gradient_registration_count": 0,
        "required_campaigns": [
            "static release and semantic contract",
            "every admitted aperture, instrument, source mode, provider scene, functional seat, and detail state",
            "unsupported transition refusal without mutation",
            "exact asset-to-semantic-receipt binding",
            "responsive image and geometry coordinate lock",
            "map-only and held zero local image geometry",
            "non-geometric instrument zero local image geometry",
            "keyboard group continuity and visible focus",
            "bounded export retaining asset and receipt identity",
            "desktop, tablet, mobile, and 200-percent text reflow",
            "zero console, page, failed-resource, and unexpected external-request errors",
            "post-deployment exact-byte and browser replay",
        ],
        "files": files,
    }
    value["manifest_sha256"] = canonical_sha(value)
    (public_root / "QUALIFICATION.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    review = locate_review(args.artifact_root.resolve())
    source_build = json.loads((review / "BUILD_RECEIPT.json").read_text(encoding="utf-8"))
    source_browser = json.loads((review / "BROWSER_AUDIT.json").read_text(encoding="utf-8"))
    require(source_build.get("result") == "PASS", "Source semantic build did not pass")
    require(source_browser.get("result") == "PASS", "Source semantic browser audit did not pass")
    source_data = json.loads((review / "data.json").read_text(encoding="utf-8"))
    receipts, features = registration_summary(source_data)
    require(receipts == EXPECTED_RECEIPTS, f"Source receipt counts do not match release contract: {receipts}")
    require(features == EXPECTED_FEATURES, f"Source feature counts do not match release contract: {features}")

    public_root = repo / "manzanita"
    evidence_root = repo / "programs/manzanita-release-1.7/evidence"
    predecessor = preserve_predecessor(repo, public_root, evidence_root, args.base_sha)
    copy_review(review, public_root)

    data_path = public_root / "data.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    data["release"] = RELEASE
    data["visual_system"] = VISUAL_SYSTEM
    data["classification"] = "bounded_public_read_only_semantic_place_fabric"
    data["public_route_effect"] = "read_only_public_projection"
    data["external_effect"] = "none"
    data["canonical_task_count_effect"] = "none"
    data["source_review"] = {"release": SOURCE_REVIEW, "workflow_run_id": SOURCE_RUN_ID, "review_head": SOURCE_REVIEW_HEAD}
    data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for path in (public_root / "app.js", public_root / "v5-semantic.js", public_root / "README.md", public_root / "REVIEW_CONTRACT.json", public_root / "BUILD_RECEIPT.json"):
        if path.is_file() and path.suffix in {".js", ".md", ".json"}:
            text = path.read_text(encoding="utf-8")
            text = text.replace(SOURCE_REVIEW, RELEASE)
            text = text.replace("review_evidence_not_public_release", "bounded_public_read_only_release")
            path.write_text(text, encoding="utf-8")

    patch_html(public_root / "index.html", data)
    build_standalone(public_root, data)
    patch_catalog(repo)
    write_release_receipts(public_root, evidence_root, data, predecessor, source_build, source_browser, args.base_sha)
    result = qualification(public_root)
    print(json.dumps({"result": "BUILT", "release": RELEASE, "visual_system": VISUAL_SYSTEM, "files": len(result["files"]), "review": str(review)}, indent=2))


if __name__ == "__main__":
    main()
