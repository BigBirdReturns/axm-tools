#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import py_compile
import re
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1]
ROOT = TOOL.parent
INDEX = TOOL / "index.html"
RUNNER = TOOL / "runner" / "casezero.py"
QUALIFICATION = TOOL / "QUALIFICATION.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    page = INDEX.read_text(encoding="utf-8")
    checks: list[tuple[str, bool]] = [
        ("doctype", page.lower().startswith("<!doctype html>")),
        ("csp-network-refusal", "connect-src 'none'" in page),
        ("no-external-script", "<script src=" not in page),
        ("no-external-style", "<link rel=\"stylesheet\"" not in page),
        ("local-custody-copy", "Local only. Network disabled." in page),
        ("redcat-client-authority", "RedCat retains the client relationship" in page),
        ("tier-desk-nonrepresentation", "It may not contact or represent the historical client." in page),
        ("browser-hashing", "crypto.subtle.digest" in page),
        ("credential-hold", "HOLD_REDACTION_REQUIRED" in page),
        ("source-content-zero", "source_contents_exported:0" in page),
        ("synthetic-case", "Load synthetic case" in page),
        ("runner-download", "Download local runner" in page),
        ("pre-read-download", "Download pre-read" in page),
        ("share-safe-export", "Download share-safe preview" in page),
        ("responsive-table-containment", ".table-wrap{overflow:auto}" in page),
    ]
    for number in range(1, 11):
        token = f"CZ-{number:02d}"
        checks.append((f"queue-{token}", token in page))

    failures = [name for name, passed in checks if not passed]
    if failures:
        raise SystemExit(f"CASE_ZERO_STATIC_REFUSED: {failures}")

    scripts = re.findall(r"<script>(.*?)</script>", page, flags=re.DOTALL | re.IGNORECASE)
    if len(scripts) != 1:
        raise SystemExit(f"expected one inline runtime, found {len(scripts)}")
    Path("/tmp/case-zero-inline.js").write_text(scripts[0], encoding="utf-8", newline="\n")

    py_compile.compile(str(RUNNER), doraise=True)
    for path in sorted((TOOL / "runner").glob("*.json")):
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)

    release_files = [
        TOOL / "downloads" / "CASE_ZERO_PRE_READ.pdf",
        TOOL / "downloads" / "redcat_case_zero_runner_v0.1.zip",
    ]
    for path in release_files:
        if not path.exists() or path.stat().st_size == 0:
            raise SystemExit(f"missing release object: {path.relative_to(ROOT)}")

    qualification = {
        "schema": "axm-tools/case-zero-qualification@0.1",
        "release": "case-zero-workbench/0.1",
        "route": "/case-zero/",
        "index_sha256": sha256(INDEX),
        "runner_sha256": sha256(RUNNER),
        "runner_zip_sha256": sha256(release_files[1]),
        "pre_read_pdf_sha256": sha256(release_files[0]),
        "static_checks": {"passed": len(checks), "failed": 0},
        "queue_rows": 10,
        "network_calls": 0,
        "source_contents_exported_by_preview": 0,
        "client_relationship_owner": "RedCat",
        "substantive_case_analysis": False,
        "shadow_pilot_authorized": False,
        "authority": "candidate_external_qualification_only",
    }
    QUALIFICATION.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"CASE_ZERO_STATIC_PASS {len(checks)}/{len(checks)}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


if __name__ == "__main__":
    main()
