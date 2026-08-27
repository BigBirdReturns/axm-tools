#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEW_PREFIX = "manzanita-next/review/useful-plant-v30-native/"
WORKFLOW = ".github/workflows/manzanita-useful-plant-v30-native-review.yml"


def digest(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--output", type=Path, default=HERE / "SOURCE_VERIFICATION_RECEIPT.json")
    args = parser.parse_args()

    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: object = "") -> None:
        checks.append({"name": name, "pass": bool(condition), "detail": detail})

    required = [
        HERE / "CONTRACT.json",
        HERE / "README.md",
        HERE / "index.html",
        HERE / "style.css",
        HERE / "app.js",
        HERE / "browser_review.py",
        HERE / "verify.py",
        HERE / "V29_PARENT_ADMISSION_CONTRACT.json",
        HERE / "verify_v29_parent.py",
        HERE / "test_v29_parent_admission.py",
        HERE / "PLANT_DONOR_ADMISSION_CONTRACT.json",
        HERE / "verify_plant_donors.py",
        HERE / "test_plant_donor_admission.py",
        ROOT / WORKFLOW,
        ROOT / "manzanita/assets/plant.webp",
    ]
    for path in required:
        check(f"required file: {path.relative_to(ROOT)}", path.is_file())

    contract = json.loads((HERE / "CONTRACT.json").read_text(encoding="utf-8"))
    review = contract["review_contract"]
    check("object class bounded review", contract["object_class"] == "REPOSITORY_NATIVE_OPERATOR_REVIEW_SURFACE")
    check("useful plant aperture", contract["aperture"] == "useful_plant")
    check("operator acceptance absent", review["operator_visual_acceptance"] == "ABSENT")
    check("release denied", review["release_authorized"] is False)
    check("merge denied", review["merge_authorized"] is False)
    check("public route effect none", review["public_route_effect"] == "none")
    check("Pages effect none", review["pages_deployment_effect"] == "none")
    check("external effect none", review["external_effect"] == "none")
    check("five operating actors", len(contract["actors"]) == 5)
    check("six-stage use loop", contract["use_loop"] == ["recognize", "place", "tend", "observe", "use", "return"])
    check("three household stops", len(contract["household_stop_authority"]) == 3)
    check("five firewall clauses", len(contract["firewall"]) == 5)
    check("exact donor substitution denied", contract["source_donor"]["substitution_allowed"] is False)

    parent_gate = json.loads((HERE / "V29_PARENT_ADMISSION_CONTRACT.json").read_text(encoding="utf-8"))
    plant_gate = json.loads((HERE / "PLANT_DONOR_ADMISSION_CONTRACT.json").read_text(encoding="utf-8"))
    parent_authority = parent_gate["authority"]
    plant_authority = plant_gate["authority"]
    check("parent gate binds v29", parent_gate["parent_release_id"] == "mw-habitat-live-photo-029")
    check("parent gate exact archive hash", parent_gate["required_archive"]["sha256"] == "1bfa88922381650bc4b16b27c1ed8d728abba6f16e1159c85e0b1d294acc3ce6")
    check("parent gate exact archive bytes", parent_gate["required_archive"]["bytes"] == 56875424)
    check("parent gate authority held", parent_authority == review)
    check("Plant gate exact origin hash", plant_gate["required_donors"]["origin"]["sha256"] == "2a531b108dfbfba5f7bfc1064c2adfa44d29649ea9fa3654ac3092fbe9a8bb03")
    check("Plant gate exact cached hash", plant_gate["required_donors"]["cached"]["sha256"] == "dd2d3b7f5683ec8c785c6baac8b0036ae7ad043767463b963d8c132201817a02")
    check("Plant gate requires both donors", set(plant_gate["required_donors"]) == {"origin", "cached"})
    check("Plant gate authority held", plant_authority == review)
    check("Plant gate current photograph non-substitute", any(row.get("path") == "manzanita/assets/plant.webp" and row.get("classification") == "ADMITTED_PUBLIC_PHOTOGRAPHIC_DONOR_NOT_EXACT_RETAINED_PLANT_MEDIA" for row in plant_gate["explicit_non_substitutes"]))

    html = (HERE / "index.html").read_text(encoding="utf-8")
    css = (HERE / "style.css").read_text(encoding="utf-8")
    js = (HERE / "app.js").read_text(encoding="utf-8")
    combined = "\n".join((html, css, js))

    check("review marker present", 'data-review-state="bounded"' in html)
    check("acceptance marker absent", 'data-operator-acceptance="absent"' in html)
    check("no embedded acceptance form", "<form" not in html.lower() and "accept candidate" not in html.lower())
    check("six mode controls", len(re.findall(r'<button[^>]+data-mode="', html)) == 6)
    check("five seat controls", len(re.findall(r'<button[^>]+data-seat="', html)) == 5)
    check("five image hotspots", len(re.findall(r'<button[^>]+data-zone="', html)) == 5)
    check("three stop controls", len(re.findall(r'<button[^>]+data-stop="', html)) == 3)
    check("seven operator questions", len(re.findall(r"<li>", html.split('<section class="review-gate"', 1)[1])) == 7)
    check("registered image geometry", "registration-layer" in html and "preserveAspectRatio=\"none\"" in html)
    check("donor remains repository relative", '../../../manzanita/assets/plant.webp' in html)
    check("no external source URL", re.search(r"https?://", combined, re.IGNORECASE) is None)
    check("no network write primitive", not any(token in js for token in ("XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource")))
    check("no fetch except donor measurement", js.count("fetch(") == 1 and "plant-image" in js)
    check("responsive floor declared", "@media (max-width: 390px)" in css)
    check("reduced motion declared", "prefers-reduced-motion" in css)
    check("print path declared", "@media print" in css)

    donor = ROOT / "manzanita/assets/plant.webp"
    donor_measurement = digest(donor)
    header = donor.read_bytes()[:12]
    check("donor has WebP container", header[:4] == b"RIFF" and header[8:12] == b"WEBP", header.hex())
    check("donor has photographic substance floor", donor_measurement["bytes"] >= 40_000, donor_measurement)
    excluded_public_donor = next(row for row in plant_gate["explicit_non_substitutes"] if row.get("path") == "manzanita/assets/plant.webp")
    check("public donor remains exact declared non-substitute", donor_measurement == {"bytes": excluded_public_donor["bytes"], "sha256": excluded_public_donor["sha256"]}, donor_measurement)

    changed_paths: list[str] = []
    rejected_paths: list[str] = []
    if args.base and args.head:
        proc = subprocess.run(
            ["git", "diff", "--name-only", args.base, args.head],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        check("git diff executable", proc.returncode == 0, proc.stderr.strip())
        changed_paths = [line for line in proc.stdout.splitlines() if line]
        rejected_paths = [
            path for path in changed_paths
            if path != WORKFLOW and not path.startswith(REVIEW_PREFIX)
        ]
        check("changed path set nonempty", bool(changed_paths), changed_paths)
        check("changed paths bounded", not rejected_paths, rejected_paths)
        check("public route untouched", not any(path == "manzanita" or path.startswith("manzanita/") for path in changed_paths), changed_paths)
        check("root entry points untouched", not any(path in {"index.html", "README.md", "CONTINUITY.md", "PROJECT_ESTATE.json"} for path in changed_paths), changed_paths)

    files = {
        str(path.relative_to(ROOT)): digest(path)
        for path in required
        if path.is_file()
    }
    passed = sum(1 for item in checks if item["pass"])
    result = {
        "schema": "manzanita/useful-plant-v30-native-source-verification@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if passed == len(checks) else "FAIL",
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "changed_paths": changed_paths,
        "rejected_paths": rejected_paths,
        "donor": {
            "path": "manzanita/assets/plant.webp",
            **donor_measurement,
            "classification": "admitted_public_photographic_donor",
            "exact_v29_claim": False,
        },
        "files": files,
        "operator_visual_acceptance": "ABSENT",
        "release_authorized": False,
        "merge_authorized": False,
        "public_route_effect": "none",
        "pages_deployment_effect": "none",
        "external_effect": "none",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
