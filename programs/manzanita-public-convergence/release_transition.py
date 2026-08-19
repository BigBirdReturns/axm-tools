#!/usr/bin/env python3
"""Prepare the public front door and move donor custody to v1.6.0."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREDECESSOR_COMMIT = "750ad90f40462ab442a546bdbc2c7f02c81e2b27"
PHOTO_COMMIT = "507ace9af2d2121cb93614158809ee5ff88437f2"


def command(*args: str) -> str:
    return subprocess.check_output(args, cwd=REPO, text=True).strip()


def prepare() -> None:
    root_readme = REPO / "README.md"
    text = root_readme.read_text(encoding="utf-8")
    row = "| [`manzanita/`](manzanita/) | Public-safe photographic place fabric with seven genuine apertures, image-registered conditions, five operational seats, assistance-first horticultural and wildfire remediation, an explicit adverse-use firewall, local export, and an Essential Attention handoff | [Place Fabric v1.6.0](https://bigbirdreturns.github.io/axm-tools/manzanita/) |"
    pattern = r"^\| \[`manzanita/`\]\(manzanita/\) \|.*$"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, row, text, count=1, flags=re.M)
    else:
        marker = "|------|--------------|-----------|"
        text = text.replace(marker, marker + "\n" + row, 1)
    root_readme.write_text(text, encoding="utf-8")

    root_index = REPO / "index.html"
    text = root_index.read_text(encoding="utf-8")
    block = '''<div class="tool">
  <div class="title"><a href="manzanita/">Manzanita Works · Photographic Place Fabric</a></div>
  <div class="desc">A public-safe place fabric built around retained photographic donors, seven genuine apertures, image-registered environmental conditions, five operational seats, assistance-first horticultural and wildfire remediation, and a firewall against converting prevention context into automatic insurance denial or punitive property scoring.</div>
  <a class="open" href="manzanita/">Open Manzanita Works →</a>
</div>'''
    pattern = re.compile(r'<div class="tool">\s*<div class="title"><a href="manzanita/">.*?</div>\s*<div class="desc">.*?</div>\s*<a class="open" href="manzanita/">.*?</a>\s*</div>', re.S)
    if pattern.search(text):
        text = pattern.sub(block, text, count=1)
    else:
        text = text.replace("</header>", "</header>\n\n" + block, 1)
    root_index.write_text(text, encoding="utf-8")

    check = REPO / ".github/workflows/manzanita-check.yml"
    text = check.read_text(encoding="utf-8")
    text = text.replace("Manzanita Works v1.4.1 Signal Sheet contract", "Manzanita Works v1.6.0 Photographic Place Fabric contract")
    text = text.replace("manzanita-signal-sheet-v1.4.1-screens", "manzanita-place-fabric-v1.6.0-screens")
    check.write_text(text, encoding="utf-8")

    live = REPO / ".github/workflows/manzanita-live-check.yml"
    text = live.read_text(encoding="utf-8")
    text = text.replace("Manzanita Works v1.4.1 live Pages gate", "Manzanita Works v1.6.0 live Pages gate")
    text = text.replace("1.4.1", "1.6.0")
    text = text.replace("signal-sheet", "photographic-place-fabric")
    text = text.replace("manzanita-live-screens", "manzanita-v1.6.0-live-screens")
    live.write_text(text, encoding="utf-8")


def custody(product_commit: str) -> None:
    directory = REPO / "programs/manzanita-99/custody"
    contract_path = directory / "CUSTODY_CONTRACT.json"
    register_path = directory / "DONOR_REGISTER.json"
    observed_path = directory / "OBSERVED_EXECUTION_LEDGER.json"
    readme_path = directory / "README.md"

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    old_guard = copy.deepcopy(contract["public_route_guard"])
    historical = contract.setdefault("historical_public_route_guards", [])
    if not any(row.get("release") == "1.4.1" for row in historical):
        historical.append(
            {
                "release": "1.4.1",
                "path": "manzanita",
                "commit": PREDECESSOR_COMMIT,
                "tree": old_guard["tree"],
                "files": old_guard["files"],
                "claim_boundary": "Exact predecessor rollback donor. Its public standing does not release the complete manzanita-next successor.",
            }
        )
    historical.sort(key=lambda row: tuple(int(part) for part in row["release"].split(".")))

    route_tree = command("git", "rev-parse", f"{product_commit}:manzanita")
    listing = command("git", "ls-tree", "-r", product_commit, "manzanita")
    files: dict[str, dict[str, str]] = {}
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        _, kind, sha = meta.split()
        if kind == "blob":
            files[path] = {"git_blob_sha1": sha}

    contract["version"] = "2.2.0"
    contract["public_route_guard"] = {
        "path": "manzanita",
        "release": "1.6.0",
        "tree": route_tree,
        "files": files,
        "failure_message": "The v1.6.0 public photographic route changed outside its release-authority transaction. Stop and investigate before admission.",
    }
    contract["observed_repository"]["release_transition_base"] = PREDECESSOR_COMMIT
    contract["qualification_boundary"] = "A passing custody workflow proves the exact current photographic public route, every explicitly guarded predecessor release, repo-resident donors, observed successor records, and the open-gap ledger agree. It does not close JDB99-001, release the complete manzanita-next successor, prove external campaigns, or change canonical task counts."
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    register = json.loads(register_path.read_text(encoding="utf-8"))
    register["observed_main_head"] = product_commit
    donors = [row for row in register["donors"] if row.get("id") != "manzanita-public-1.6.0"]
    for row in donors:
        if row.get("id") == "manzanita-public-1.4.1":
            row["archive_scope_ids"] = []
            row["anchors"]["source_commit"] = PREDECESSOR_COMMIT
            row["claim_boundary"] = "Exact predecessor public rollback donor retained by commit, route tree, and file blob identities. It does not transfer complete-successor standing."
    current = {
        "id": "manzanita-public-1.6.0",
        "class": "historical_public_release",
        "custody_state": "archived_repo",
        "archive_scope_ids": ["historical-public-route"],
        "anchors": {
            "release": "1.6.0",
            "supersedes": "1.4.1",
            "source_commit": product_commit,
            "route_tree": route_tree,
            "qualification_blob": files["manzanita/QUALIFICATION.json"]["git_blob_sha1"],
            "release_receipt_blob": files["manzanita/RELEASE_RECEIPT.json"]["git_blob_sha1"],
            "photographic_donor_commit": PHOTO_COMMIT,
        },
        "claim_boundary": "Current bounded public photographic convergence release. It combines retained public visual donors with admitted operating laws without releasing the complete manzanita-next successor or changing external-campaign or task-count standing.",
    }
    insert_at = next((index + 1 for index, row in enumerate(donors) if row.get("id") == "manzanita-public-1.4.1"), 0)
    donors.insert(insert_at, current)
    register["donors"] = donors
    register["qualification_boundary"] = "A passing custody workflow proves current and predecessor public-route identities, repo-resident sources, donor anchors, observed successor records, and the explicit gap ledger agree. It does not close JDB99-001, release the complete manzanita-next successor, prove external campaigns, or change canonical task counts."
    register_path.write_text(json.dumps(register, indent=2) + "\n", encoding="utf-8")

    observed = json.loads(observed_path.read_text(encoding="utf-8"))
    observed["public_route_transition"] = {
        "release": "1.6.0",
        "release_class": "bounded_public_photographic_convergence",
        "source_commit": product_commit,
        "route_tree": route_tree,
        "photographic_donor_commit": PHOTO_COMMIT,
        "successor_program_effect": "none",
        "external_campaign_effect": "none",
        "canonical_task_count_effect": "none",
    }
    observed["claim_boundary"] = "This ledger records observed merged successor operating objects and their admitted claim boundaries. The complete manzanita-next successor remains HOLD with ten external campaigns not performed. The separate v1.6.0 public photographic convergence transaction changes only the already public route and has no successor-program, external-campaign, or canonical-task-count effect."
    observed_path.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")

    text = readme_path.read_text(encoding="utf-8")
    section = f'''\n## Public photographic convergence transition\n\nManzanita Works v1.6.0 replaces the simplified v1.4.1 Signal Sheet route with a bounded photographic place fabric. Exact v1.4.1 bytes remain guarded at commit `{PREDECESSOR_COMMIT}` and route tree `{old_guard['tree']}`. The current route is guarded at candidate commit `{product_commit}` and route tree `{route_tree}`. The release retains photographic donor commit `{PHOTO_COMMIT}`, seven distinct aperture assets, image-registered conditions, five operational seats, the adverse-use firewall, and the Essential Attention handoff.\n\nThis transaction performs no `manzanita-next` external campaign, closes no custody gap, releases no private or physical standing, reconstructs no canonical backlog rows, and has no canonical task-count effect.\n'''
    if "## Public photographic convergence transition" not in text:
        text += section
    readme_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "custody"])
    parser.add_argument("--product-commit")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    else:
        if not args.product_commit:
            parser.error("--product-commit is required for custody mode")
        custody(args.product_commit)
