#!/usr/bin/env python3
"""Validate the self-contained Organ Evolution production surface."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1]
HTML = TOOL / "index.html"
EXAMPLE = TOOL / "data" / "axm-estate.example.json"
ACCEPTED = TOOL / "data" / "fixtures" / "accepted-decision.fixture.json"
CORE = TOOL / "core.js"
DECISION_JOB_JS = TOOL / "decision-job.js"
VIEWS = TOOL / "views.js"
DECISION_VIEW_JS = TOOL / "decision-circulation-view.js"
APP = TOOL / "app.js"
STYLE = TOOL / "styles.css"
SEED_JS = TOOL / "data" / "seed.js"

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import decision_job  # noqa: E402

REQUIRED_ROOT = {"format", "estate", "actors", "organs", "evidence", "candidates", "scenarios", "decision"}
DIMENSIONS = {
    "function",
    "authority",
    "reversibility",
    "dependency",
    "adaptability",
    "observability",
    "succession",
    "efficiency",
    "userValue",
    "captureResistance",
    "containment",
    "evidence",
}
GATES = {"function", "authority", "evidence", "migration", "reversibility"}
GATE_STATES = {"pass", "warn", "fail", "open"}
EVIDENCE_TIERS = {"confirmed", "measured", "reported", "derived", "judgment", "open"}
INDEPENDENCE = {"independent", "mixed", "self", "unknown"}


def fail(message: str) -> None:
    raise AssertionError(message)


def duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dup: set[str] = set()
    for value in values:
        if value in seen:
            dup.add(value)
        seen.add(value)
    return sorted(dup)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def embedded_seed(seed_js: str) -> dict:
    prefix = "window.AXM_ORGAN_EVOLUTION_SEED = "
    if not seed_js.startswith(prefix) or not seed_js.rstrip().endswith(";"):
        fail("data/seed.js does not expose the expected local seed constant")
    return json.loads(seed_js[len(prefix):].rstrip()[:-1])


def validate_model(model: dict) -> None:
    missing = REQUIRED_ROOT - set(model)
    if missing:
        fail(f"model is missing required root keys: {sorted(missing)}")
    if model["format"] != "axm-organ-evolution/1":
        fail("unsupported model format")

    actors = model["actors"]
    organs = model["organs"]
    evidence = model["evidence"]
    candidates = model["candidates"]
    scenarios = model["scenarios"]

    actor_ids = [row["id"] for row in actors]
    organ_ids = [row["id"] for row in organs]
    evidence_ids = [row["id"] for row in evidence]
    candidate_ids = [row["id"] for row in candidates]
    scenario_ids = [row["id"] for row in scenarios]

    for label, ids in {
        "actor": actor_ids,
        "organ": organ_ids,
        "evidence": evidence_ids,
        "candidate": candidate_ids,
        "scenario": scenario_ids,
    }.items():
        dup = duplicates(ids)
        if dup:
            fail(f"duplicate {label} ids: {dup}")

    actor_set = set(actor_ids)
    organ_set = set(organ_ids)
    evidence_set = set(evidence_ids)
    candidate_set = set(candidate_ids)

    for organ in organs:
        if not organ["id"].startswith("organ."):
            fail(f"organ id lacks organ. prefix: {organ['id']}")
        health = organ.get("health", {})
        for key, value in health.items():
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5:
                fail(f"{organ['id']} health {key} is outside integer 0..5")
        function_ids = [row["id"] for row in organ.get("functions", [])]
        if duplicates(function_ids):
            fail(f"{organ['id']} contains duplicate function ids")
        for function in organ.get("functions", []):
            for field in ("criticality", "coverage"):
                value = function.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5:
                    fail(f"{function['id']} {field} is outside integer 0..5")
        for dependency in organ.get("dependencies", []):
            if dependency["target"] not in organ_set:
                fail(f"{organ['id']} references unknown dependency {dependency['target']}")
        for group in organ.get("custodians", {}).values():
            for actor_id in group:
                if actor_id not in actor_set:
                    fail(f"{organ['id']} references unknown custodian {actor_id}")

    for row in evidence:
        if row["tier"] not in EVIDENCE_TIERS:
            fail(f"{row['id']} has unsupported evidence tier {row['tier']}")
        if row["independence"] not in INDEPENDENCE:
            fail(f"{row['id']} has unsupported independence {row['independence']}")

    for candidate in candidates:
        if candidate["organId"] not in organ_set:
            fail(f"{candidate['id']} references unknown organ {candidate['organId']}")
        if set(candidate.get("dimensions", {})) != DIMENSIONS:
            fail(f"{candidate['id']} dimensions do not match the full evaluation envelope")
        for key, value in candidate["dimensions"].items():
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5:
                fail(f"{candidate['id']} dimension {key} is outside integer 0..5")
        if set(candidate.get("gates", {})) != GATES:
            fail(f"{candidate['id']} gates do not match the hard-gate set")
        if not set(candidate["gates"].values()) <= GATE_STATES:
            fail(f"{candidate['id']} contains an unsupported gate state")
        for evidence_id in candidate.get("evidenceIds", []):
            if evidence_id not in evidence_set:
                fail(f"{candidate['id']} references unknown evidence {evidence_id}")
        for role, ids in candidate.get("actorLinks", {}).items():
            if role not in {"sponsors", "validators", "deciders", "beneficiaries"}:
                fail(f"{candidate['id']} has unsupported actor role {role}")
            for actor_id in ids:
                if actor_id not in actor_set:
                    fail(f"{candidate['id']} references unknown actor {actor_id}")
        if set(candidate.get("changes", {})) != {"preserve", "alter", "retire", "introduce"}:
            fail(f"{candidate['id']} migration ledger is incomplete")

    for scenario in scenarios:
        unknown = set(scenario.get("dimensions", [])) - DIMENSIONS
        if unknown:
            fail(f"{scenario['id']} references unknown dimensions {sorted(unknown)}")

    decision = model["decision"]
    if decision.get("organId") not in organ_set:
        fail("decision references an unknown organ")
    if decision.get("candidateId") not in candidate_set:
        fail("decision references an unknown candidate")
    if decision.get("decider") not in actor_set:
        fail("decision references an unknown decider")


def validate_surface(html: str, source: str) -> None:
    required_text = [
        "Organ Evolution",
        "Estate adaptation workbench",
        "Anatomy",
        "Evolution",
        "Actors &amp; interests",
        "Evidence",
        "Stress tests",
        "Decision record",
        "axm-organ-evolution/1",
        "axm-organ-evolution-job/1",
        "Motivation without mind-reading",
        "The table preserves the full fitness envelope",
        "It does not establish that the proposal is wise",
        "Export circulation job",
        "Compiler boundary",
    ]
    for text in required_text:
        if text not in html + "\n" + source:
            fail(f"production page is missing required boundary text: {text}")

    required_assets = [
        'href="styles.css"',
        'src="data/seed.js"',
        'src="core.js"',
        'src="decision-job.js"',
        'src="views.js"',
        'src="decision-circulation-view.js"',
        'src="app.js"',
    ]
    for required_asset in required_assets:
        if required_asset not in html:
            fail(f"production page is missing local asset reference: {required_asset}")

    forbidden = [
        r'<link[^>]+href=["\']https?://',
        r'fetch\s*\(',
        r'XMLHttpRequest',
        r'new\s+WebSocket',
        r'EventSource\s*\(',
        r'<iframe',
    ]
    for pattern in forbidden:
        if re.search(pattern, html + "\n" + source, flags=re.IGNORECASE):
            fail(f"production page contains forbidden external/runtime pattern: {pattern}")


if __name__ == "__main__":
    try:
        html = HTML.read_text(encoding="utf-8")
        example = load_json(EXAMPLE)
        accepted = decision_job.load_json(ACCEPTED)
        seed = embedded_seed(SEED_JS.read_text(encoding="utf-8"))
        validate_model(example)
        validate_model(accepted)
        validate_model(seed)
        if seed != example:
            fail("embedded worked example differs from data/axm-estate.example.json")
        job = decision_job.build_job(accepted)
        decision_job.verify_job(job)
        if not job["decision"]["decisionId"].startswith("orgdec1_"):
            fail("accepted fixture did not produce a decision identity")
        if not job["jobId"].startswith("organjob1_"):
            fail("accepted fixture did not produce a circulation job identity")
        if not (job.get("execution") or {}).get("executionId", "").startswith("organexec1_"):
            fail("accepted fixture did not produce a bound execution identity")
        scripts = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (CORE, DECISION_JOB_JS, VIEWS, DECISION_VIEW_JS, APP)
        )
        validate_surface(html, scripts + "\n" + STYLE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(
        "PASS: organ evolution surface, accepted-decision fixture, browser/Python "
        "circulation contract, graph references, authority gates, evidence classes, "
        "and no-network boundary"
    )
