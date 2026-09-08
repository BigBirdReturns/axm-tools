#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "manzanita-working-model"


def replace_exact(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise SystemExit(f"{path.relative_to(REPO)}: expected {count} copies of {old!r}, found {found}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    assets = TOOL / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "manzanita" / "assets" / "property.webp", assets / "property.webp")
    shutil.copy2(REPO / "manzanita" / "assets" / "household.webp", assets / "household.webp")

    html = TOOL / "index.html"
    replace_exact(html, 'content="mw-working-model-v1.0.0-candidate"', 'content="mw-working-model-v1.0.0"')
    replace_exact(html, "<small>Working model · candidate</small>", "<small>Working model · public-safe</small>")
    replace_exact(html, "../manzanita/assets/property.webp", "assets/property.webp")
    replace_exact(html, "../manzanita/assets/household.webp", "assets/household.webp")
    replace_exact(
        html,
        "<div><span>Working-model front door</span><b>Candidate here</b></div>",
        "<div><span>Working-model front door</span><b>Released public-safe route</b></div>",
    )
    replace_exact(
        html,
        "<div><b>Manzanita Works · Working Model</b><span>Internal adoption-ready candidate. No institutional acceptance is implied.</span></div>",
        "<div><b>Manzanita Works · Working Model</b><span>Public-safe v1.0.0. No institutional acceptance is implied.</span></div>",
    )

    replace_exact(
        TOOL / "app.js",
        "const RELEASE = 'mw-working-model-v1.0.0-candidate';",
        "const RELEASE = 'mw-working-model-v1.0.0';",
    )

    browser_path = TOOL / "tests" / "browser_test.py"
    browser = browser_path.read_text(encoding="utf-8")
    if browser.count("mw-working-model-v1.0.0-candidate") != 2:
        raise SystemExit("browser test candidate release markers differ")
    browser = browser.replace("mw-working-model-v1.0.0-candidate", "mw-working-model-v1.0.0")
    browser = browser.replace(
        "PASS_WORKING_MODEL_CHROMIUM_CAMPAIGN",
        "PASS_WORKING_MODEL_CHROMIUM_RELEASE_CAMPAIGN",
    )
    browser_path.write_text(browser, encoding="utf-8")

    contract_path = TOOL / "WORKING_MODEL_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["version"] = "1.0.0"
    contract["state"] = "released_public_safe_working_model"
    contract["object"]["public_effect"] = "public_static_route_only"
    contract["object"]["claim_boundary"] = (
        "This object is the released public-safe Manzanita working model and local "
        "pilot-preparation surface. Publication proves route availability and the "
        "qualified bytes only. It is not Manzanita Works institutional adoption, a "
        "volunteer assignment, a funded continuity operator, a field program, a "
        "participant record, a work order, an eligibility system, a fundraising or "
        "payment system, or proof that any pilot or organizational commitment exists."
    )
    contract["publication"] = {
        "state": "released_public_safe_static_route",
        "route": "https://bigbirdreturns.github.io/axm-tools/manzanita-working-model/",
        "repository_path": "manzanita-working-model/",
        "authority": "repository_owner",
        "public_effect": "route_publication_only",
        "institutional_acceptance": False,
        "participant_consent": False,
        "field_authority": False,
        "spend_authority": False,
        "assignment_authority": False,
        "representation_authority": False,
        "program_external_effect": "none",
    }
    contract["release_holds"] = [
        "No Manzanita Works institutional acceptance receipt is present for this release.",
        "No pilot sponsor, funded continuity operator, venue, resource envelope, participant class, or field partner is admitted by this release.",
        "No participant consent, private household record, lawful field-access receipt, work authorization, completion receipt, or field acceptance is admitted.",
        "Public route publication grants no institutional, participant, field, spend, assignment, representation, eligibility, award, work, or program authority.",
    ]
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    test_path = TOOL / "tests" / "public_contract_test.py"
    test = test_path.read_text(encoding="utf-8")
    replacements = [
        (
            '    "README.md",\n]',
            '    "README.md",\n    "RELEASE_CONTRACT.json",\n    "assets/property.webp",\n    "assets/household.webp",\n]',
        ),
        ("required candidate file absent", "required release file absent"),
        ("required candidate file empty", "required release file empty"),
        ('content="mw-working-model-v1.0.0-candidate"', 'content="mw-working-model-v1.0.0"'),
        (
            'contract["state"] == "internal_adoption_ready_candidate"',
            'contract["state"] == "released_public_safe_working_model"',
        ),
        ('"candidate state differs"', '"release state differs"'),
        (
            '["../manzanita/assets/property.webp", "../manzanita/assets/household.webp"]',
            '["assets/property.webp", "assets/household.webp"]',
        ),
        ("candidate_files = [ROOT / name for name in REQUIRED]", "release_files = [ROOT / name for name in REQUIRED]"),
        (
            "for path in sorted(candidate_files, key=lambda p: p.name):",
            "for path in sorted(release_files, key=lambda p: p.as_posix()):",
        ),
        ('"PASS_WORKING_MODEL_STATIC_CONTRACT"', '"PASS_WORKING_MODEL_STATIC_RELEASE_CONTRACT"'),
        ('"mw-working-model-v1.0.0-candidate"', '"mw-working-model-v1.0.0"'),
        ('"files": len(candidate_files)', '"files": len(release_files)'),
        ('"candidate_bundle_digest": digest.hexdigest()', '"release_bundle_digest": digest.hexdigest()'),
    ]
    for old, new in replacements:
        if old not in test:
            raise SystemExit(f"public contract test pattern absent: {old}")
        test = test.replace(old, new)

    old_load = '    contract = json.loads((ROOT / "WORKING_MODEL_CONTRACT.json").read_text(encoding="utf-8"))\n'
    new_load = old_load + '    release_contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))\n'
    if test.count(old_load) != 1:
        raise SystemExit("public contract test load insertion point differs")
    test = test.replace(old_load, new_load)

    old_check = '    require(contract["state"] == "released_public_safe_working_model", "release state differs")\n'
    new_check = old_check + (
        '    require(contract["object"]["public_effect"] == "public_static_route_only", "public effect differs")\n'
        '    require(release_contract["schema"] == "manzanita-works/working-model-release@1", "release contract schema differs")\n'
        '    require(release_contract["release"] == "mw-working-model-v1.0.0", "release identity differs")\n'
        '    require(release_contract["publication_authority"]["institutional_acceptance"] is False, "release may not accept institution")\n'
        '    require(release_contract["publication_authority"]["program_external_effect"] == "none", "release may not create program effect")\n'
    )
    if test.count(old_check) != 1:
        raise SystemExit("public contract test state-check insertion point differs")
    test = test.replace(old_check, new_check)
    test_path.write_text(test, encoding="utf-8")

    (TOOL / "README.md").write_text(
        """# Manzanita Works Working Model v1.0.0

This public-safe surface is the ordinary front door for the Manzanita estate. It starts with one concrete problem and exposes the common operating grammar directly:

`signal → source → authority → safe action → fallback → closure → learning`

Four representative cases exercise that grammar: wildfire assistance, tools and time, mobility, and continuity. Each case identifies the useful preparation the system can produce and the consequence it may not manufacture.

Live route: `https://bigbirdreturns.github.io/axm-tools/manzanita-working-model/`

## The five-pilot gate

The surface compresses the remaining organizational dependency into five explicit decisions:

1. choose one real problem;
2. name the accountable sponsor;
3. assign and fund the continuity operator;
4. name the venue, resources, and field partners;
5. set the external-effect boundary and stop conditions.

The local form preserves every blank as `UNRESOLVED` and exports a `manzanita-works/bounded-pilot-preparation@1` JSON packet. A fully populated packet remains `PREPARED_FOR_ACCOUNTABLE_REVIEW_NOT_ACCEPTED`; it cannot contact, schedule, assign, spend, enroll, inspect, publish, represent, authorize work, accept institutional scope, or release a field pilot.

## Existing surfaces remain authoritative for their own scope

The working model links rather than collapses the mature estate:

- `manzanita/` is the released public-safe Place Fabric.
- `essential-attention/` is the local-first administrative case runtime.
- `manzanita-works/` is the deeper Operating Fabric architecture index.
- `manzanita-next/street-glide/`, `roles/`, and `experience/` remain separately governed internal candidates.

The working model does not supersede those contracts or upgrade an internal candidate to released standing. Its two photographic assets are copied into `assets/` so the route remains self-contained if another tool changes.

## Governing invariants

Silence does not create consent, assignment, rejection, or completion. Capability and proximity do not assign the nearest person. Evidence visibility does not grant authority. Assistance and place evidence cannot become punitive standing. Affected actors retain correction, refusal, narrowing, deferral, acceptance, and appeal where applicable. Replaceable services may perform jobs without becoming the canonical institutional record. Continuity lives in records, receipts, replay, and a bounded operating seat rather than one person's memory.

## Public-release boundary

The release contains no private participant record, field case, provider credential, telemetry, model call, payment adapter, email adapter, calendar adapter, or source-system writeback. It makes no runtime external API request. Deliberate navigation to another released Manzanita surface is the only way a user leaves the page.

Public publication establishes route availability and exact released bytes. It does not establish Manzanita Works institutional adoption, a funded operator, a pilot venue, resource commitment, participant consent, field authority, completed work, eligibility, award, representation, or any program effect.

## Qualification and custody

`QUALIFICATION.json` preserves the historical candidate qualification. `RELEASE_CONTRACT.json` defines the separately authorized public-safe release and the proof required to close it.

`tests/public_contract_test.py` verifies the exact release vocabulary, source links, self-contained assets, scenario count, seven-stage grammar, five-pilot gate, export authority fields, privacy and network boundaries, accessibility hooks, and absence of personalized names.

`tests/browser_test.py` runs the local release through Chromium. `tests/live_readback.py` requires byte-for-byte parity between every release file on `main` and the public route. `tests/live_browser_test.py` repeats the material interactions against GitHub Pages. The workflow records a durable live receipt under `.github/receipts/` only after all four proofs pass.

All files in this tool directory are steward-owned. The generated live receipt is machine-owned by `.github/workflows/manzanita-working-model.yml`.
""",
        encoding="utf-8",
    )

    root_readme = REPO / "README.md"
    text = root_readme.read_text(encoding="utf-8")
    row = (
        "| [`manzanita-working-model/`](manzanita-working-model/) | Public-safe adoption front door: run one concrete problem through source, authority, safe action, fallback, closure, and learning; name the five organization-owned pilot gates; export a bounded no-effect preparation packet | [Working Model v1.0.0](https://bigbirdreturns.github.io/axm-tools/manzanita-working-model/) |\n"
    )
    if "[`manzanita-working-model/`]" not in text:
        marker = "|------|--------------|-----------|\n"
        if text.count(marker) != 1:
            raise SystemExit("root README tool-table marker differs")
        text = text.replace(marker, marker + row)
        root_readme.write_text(text, encoding="utf-8")

    root_index = REPO / "index.html"
    text = root_index.read_text(encoding="utf-8")
    if 'href="manzanita-working-model/"' not in text:
        marker = "</header>\n\n"
        card = """<div class="tool">
  <div class="title"><a href="manzanita-working-model/">Manzanita Works · Working Model</a></div>
  <div class="desc">The public-safe front door for the Manzanita estate. Start with one concrete problem, follow the common path from signal through closure and learning, identify the five organization-owned pilot gates, and export a bounded preparation packet that preserves every unresolved fact and grants no institutional, participant, field, spend, assignment, representation, or program authority.</div>
  <a class="open" href="manzanita-working-model/">Open the working model →</a>
</div>

"""
        if text.count(marker) != 1:
            raise SystemExit("root index insertion point differs")
        text = text.replace(marker, marker + card)
        root_index.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
