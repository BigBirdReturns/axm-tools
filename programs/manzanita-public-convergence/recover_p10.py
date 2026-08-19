#!/usr/bin/env python3
"""Recover the exact archived P10 candidate from retained GitHub Actions artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

RELEASE_HEAD = "ed387ac8d27576484c71a13a7d0c8c8194f9b2ed"
EXPECTED_SHA256 = "73a222505b40ffd74c3c2464a0a313b0fc5c4ff7df9f9b6e996cba8be036e90b"


def gh(*args: str, binary: bool = False):
    return subprocess.check_output(["gh", "api", *args], text=not binary)


def main(output: Path) -> None:
    repo = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise SystemExit("GH_REPO or GITHUB_REPOSITORY is required")
    output = output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        runs = json.loads(gh(f"repos/{repo}/actions/runs?head_sha={RELEASE_HEAD}&per_page=100")).get("workflow_runs", [])
        rows = []
        for run in runs:
            artifacts = json.loads(gh(f"repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100")).get("artifacts", [])
            for artifact in artifacts:
                if artifact.get("expired"):
                    continue
                rows.append({"run_id": run["id"], "run_name": run.get("name"), "artifact_id": artifact["id"], "artifact_name": artifact["name"]})
        if not rows:
            raise SystemExit("No retained artifacts exist for the exact P10 release head")

        matches = []
        for row in rows:
            archive = temp / f"{row['run_id']}-{row['artifact_id']}.zip"
            archive.write_bytes(gh(f"repos/{repo}/actions/artifacts/{row['artifact_id']}/zip", binary=True))
            expanded = temp / archive.stem
            expanded.mkdir()
            try:
                with zipfile.ZipFile(archive) as handle:
                    handle.extractall(expanded)
            except zipfile.BadZipFile:
                continue
            for path in expanded.rglob("*"):
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_SHA256:
                    matches.append((row, path))
        if len(matches) != 1:
            raise SystemExit(f"Expected one P10 candidate SHA match, found {len(matches)}")
        row, candidate = matches[0]
        with zipfile.ZipFile(candidate) as handle:
            handle.extractall(output / "archive")

        html = []
        for index in (output / "archive").rglob("index.html"):
            text = index.read_text(encoding="utf-8", errors="replace")
            score = sum(token.lower() in text.lower() for token in ("Manzanita", "aperture", "overlay", "role", "Essential Attention"))
            html.append((score, len(text), index))
        html.sort(reverse=True)
        if not html or html[0][0] < 3:
            raise SystemExit("Could not identify the whole-experience entrypoint")
        selected = html[0][2].parent
        shutil.copytree(selected, output / "site")
        receipt = {
            "schema": "manzanita-works/p10-recovery@2",
            "release_head": RELEASE_HEAD,
            "candidate_sha256": EXPECTED_SHA256,
            "run_id": row["run_id"],
            "run_name": row["run_name"],
            "artifact_id": row["artifact_id"],
            "artifact_name": row["artifact_name"],
            "selected_site": str(selected.relative_to(output / "archive")),
            "classification": "internal_donor_only",
            "public_release_authorized": False,
            "canonical_task_count_effect": "none",
        }
        (output / "P10_RECOVERY.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output)
