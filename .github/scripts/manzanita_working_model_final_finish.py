#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("manzanita-working-model")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, observed {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise SystemExit(f"{label}: expected one structural match, observed {count}")
    return updated


# Public surface.
index_path = ROOT / "index.html"
html = index_path.read_text(encoding="utf-8")
replacements = {
    "Choose one concrete community problem. The model exposes the evidence, authority, safe action, fallback, closure, and handoff required to move it without inventing consent or assigning invisible labor.":
        "Choose one concrete community problem. The model shows the evidence, authority, safe action, fallback, closure, and handoff needed to move it without inventing consent or assigning invisible labor.",
    '<span class="console-kicker">Prepared example · no active case</span>':
        '<span class="console-kicker">Demonstration trace</span>',
    "Public context can focus attention. It cannot diagnose the parcel, manufacture eligibility, or authorize work. The useful output is a source-linked verification and assistance path.":
        "Public context can focus attention. It cannot diagnose the parcel, decide eligibility, or authorize work. The useful output is a source-backed verification and assistance path.",
    '<p class="mini-label">What the model can prepare now</p>':
        '<p class="mini-label">Prepared output</p>',
    '<p class="mini-label">What it may not manufacture</p>':
        '<p class="mini-label">Prohibited claims and effects</p>',
    "Seven scales over one demonstration place, eight conditions, five operating seats, source states, safe actions, acceptance, and handoff.":
        "One demonstration place across seven scales, with visible source quality, safe actions, acceptance, and handoff.",
    '<div class="instrument-foot"><span>Local-first</span><span>0 participant records</span></div>':
        '<div class="instrument-foot"><span>Local-first</span><span>No private records</span></div>',
    "A working case file for source, interpretation, decisions, effect boundaries, receipts, replay, and cold handoff without silently assigning a person.":
        "A local case file that preserves evidence, decisions, limits, receipts, and handoff without silently assigning work.",
    '<div class="instrument-top"><span>Operating Fabric</span><b>06 organs</b></div>':
        '<div class="instrument-top"><span>Operating Fabric</span><b>06 functions</b></div>',
    '<div class="instrument-foot"><span>Vendors replaceable</span><span>Record organization-owned</span></div>':
        '<div class="instrument-foot"><span>Vendors replaceable</span><span>Organization owns the record</span></div>',
    "The deeper map of program organs, capacity classes, vendor boundaries, shared institutional substrate, and what must remain organization-owned.":
        "The deeper map of program functions, capacity, vendor boundaries, shared services, and the records the organization must own.",
    "Provider fallback, map-only honesty, image registration proposals, five genuinely different functional seats, and explicit adverse-action prohibitions.":
        "Source fallback, map-only honesty, image-alignment proposals, five distinct user roles, and explicit prohibitions on adverse use.",
    '<article><span>02</span><h3>Help cannot become adverse standing.</h3><p>Evidence collected to assist cannot silently become insurance, enforcement, eligibility, property, resident, or punitive scoring.</p></article>':
        '<article><span>02</span><h3>Help cannot become a penalty.</h3><p>Evidence gathered to help cannot silently become insurance, enforcement, eligibility, property, resident, or punitive scoring.</p></article>',
    '<article><span>04</span><h3>Vendors perform jobs. They do not own the model.</h3><p>A replaceable service cannot become the canonical institutional record by convenience.</p></article>':
        '<article><span>04</span><h3>Vendors perform jobs. They do not own the model.</h3><p>No vendor becomes the official record by convenience.</p></article>',
    "A pilot begins when one problem has an accountable sponsor, a funded operator, an execution basis, an authority boundary, and a stop condition.":
        "A pilot begins when one problem has an accountable sponsor, a funded operator, a defined venue and resources, an authority boundary, and a stop condition.",
    '<li><span class="decision-number">01</span><div><h3>Choose one problem.</h3><p>Not “digital transformation.” One real case class worth learning from.</p></div><strong>Pilot scope</strong></li>':
        '<li><span class="decision-number">01</span><div><h3>Choose one problem.</h3><p>Name one specific case the pilot will handle.</p></div><strong>Scope</strong></li>',
    '<li><span class="decision-number">02</span><div><h3>Name the accountable sponsor.</h3><p>The person who owns the public promise, budget envelope, organizational boundary, and stop authority.</p></div><strong>Executive owner</strong></li>':
        '<li><span class="decision-number">02</span><div><h3>Name the accountable sponsor.</h3><p>Name the person who owns the public promise, budget, boundaries, and stop authority.</p></div><strong>Sponsor</strong></li>',
    '<li><span class="decision-number">03</span><div><h3>Assign and fund the continuity operator.</h3><p>The bounded human operating function cannot default to a founder, advisor, volunteer, or whoever remembers the context.</p></div><strong>Operating owner</strong></li>':
        '<li><span class="decision-number">03</span><div><h3>Assign and fund the continuity operator.</h3><p>Name the person responsible for keeping the case moving and fund the time required. The role cannot default to whoever remembers the context.</p></div><strong>Operator</strong></li>',
    '<strong>Execution basis</strong>': '<strong>Venue + resources</strong>',
    '<strong>Authority + safety</strong>': '<strong>Safety limits</strong>',
    "Choose the problem, name the organization-owned seats, state what exists, and preserve every unresolved gate. Exporting the packet contacts nobody and grants no authority.":
        "Choose the problem, name the responsible roles, state what exists, and preserve every unresolved decision. Exporting the packet contacts nobody and grants no authority.",
    '<span>Venue / participant class</span>': '<span>Venue / participant group</span>',
    '<span>Resource envelope</span>': '<span>Available resources</span>',
    '<div class="form-status" id="form-status" role="status" aria-live="polite">0 of 5 organizational gates have named inputs.</div>':
        '<div class="form-status" id="form-status" role="status" aria-live="polite">0 of 5 pilot decisions complete. 5 remain unresolved.</div>',
    'Export bounded pilot packet': 'Export pilot packet',
    '<div><span>Technical system</span><b>Ready for bounded use</b></div>':
        '<div><span>System</span><b>Ready for bounded use</b></div>',
    '<div><span>Working-model front door</span><b>Live</b></div>':
        '<div><span>Working model</span><b>Live</b></div>',
}
for old, new in replacements.items():
    html = replace_once(html, old, new, old[:80])

# The disclosure repeated the same systems in denser internal language. The cards
# already carry the useful evidence, so remove the duplicate layer entirely.
html = sub_once(
    html,
    r"\n      <details class=\"evidence-details\">.*?</details>",
    "",
    "redundant technical disclosure",
)

for residue in [
    "no active case",
    "0 participant records",
    "source-linked",
    "what it may not manufacture",
    "program organs",
    "shared institutional substrate",
    "functional seats",
    "adverse standing",
    "execution basis",
    "venue / participant class",
    "resource envelope",
    "working-model front door",
    "technical system",
    "Evidence and boundaries",
]:
    if residue.lower() in html.lower():
        raise SystemExit(f"visible editorial residue remains: {residue}")
index_path.write_text(html, encoding="utf-8")


# Dynamic scenario and status language.
app_path = ROOT / "app.js"
js = app_path.read_text(encoding="utf-8")
js_replacements = {
    "Public context can focus attention. It cannot diagnose the parcel, manufacture eligibility, or authorize work. The useful output is a source-linked verification and assistance path.":
        "Public context can focus attention. It cannot diagnose the parcel, decide eligibility, or authorize work. The useful output is a source-backed verification and assistance path.",
    "A bounded verification and assistance packet with every unknown, authority boundary, stop condition, and handoff preserved.":
        "A verification and assistance packet that preserves every unknown, authority boundary, stop condition, and handoff.",
    "A resident, neighbor, or program asks a bounded assistance question. Regional fire or weather context may increase attention, but it does not diagnose a specific home.":
        "A resident, neighbor, or program asks a specific assistance question. Regional fire or weather context may increase attention, but it does not diagnose a specific home.",
    "Use public fire and weather context, the public-safe Place Fabric, and resident-supplied facts. Missing, stale, map-only, authored, and contradictory states stay visible.":
        "Use public fire and weather context, Place Fabric, and resident-supplied facts. Missing, stale, map-only, authored, and contradictory states stay visible.",
    "Aggregate repeated gaps in assistance, sourcing, tools, labor, or program design without exposing household identity or creating adverse standing.":
        "Track repeated gaps in assistance, sources, tools, labor, or program design without exposing household identity or creating a penalty.",
    "A bounded capacity match: what is needed, what is actually available, what each provider is committing, and what closes the obligation.":
        "A capacity match that states what is needed, what is available, what each provider commits, and what closes the obligation.",
    "A participant states a concrete need or someone publishes a concrete offer. The system preserves who said what and the force of the statement.":
        "A participant states a concrete need or someone publishes a concrete offer. The system preserves who said what and whether it is a request, offer, or commitment.",
    "If the first resource is unavailable, route to another tool, another date, a lending partner, a purchase option, instruction, or a safe “cannot fill” closure.":
        "If the first resource is unavailable, route to another tool, date, lending partner, purchase option, or instruction, or record that the need cannot be met.",
    "A bounded mobility path with the trip need, available resources, responsible actors, fallback, acceptance, and unresolved constraints carried together.":
        "A mobility path that keeps the trip need, available resources, responsible people, fallback, acceptance, and unresolved constraints together.",
    "Use current resource records, route and public context, first-party constraints, equipment status, program terms, and provider receipts without flattening them together.":
        "Use current resource records, route context, first-party constraints, equipment status, program terms, and provider receipts while preserving their different sources and authority.",
    "Repeated transportation voids become an evidence base for shared fleet, repair capacity, route support, storage, training, or partnership decisions.":
        "Repeated transportation gaps provide evidence for shared vehicles, repair capacity, route support, storage, training, or partnerships.",
    "Offers, advisory comments, decisions, unknowns, authority, and next safe actions are distinct objects. Preserving those distinctions prevents enthusiasm from turning into invisible labor.":
        "Offers, advice, decisions, unknowns, authority, and next safe actions must remain distinct. Preserving those differences prevents enthusiasm from turning into invisible labor.",
    "Name the seat that can decide, the seat that can prepare, the affected actor, and every effect still withheld. Nobody inherits authority from proximity to the work.":
        "Name who can decide, who can prepare, who is affected, and every effect still withheld. Nobody inherits authority by being close to the work.",
    "Record the disposition, source, decision, acceptance, expiration, or remaining hold in a form a cold successor can replay.":
        "Record the outcome, source, decision, acceptance, expiration, or remaining hold so another person can reopen the case without reconstruction.",
    "status.textContent = `${count} of 5 organizational gates have named inputs. ${unresolved ? `${unresolved} remain unresolved.` : 'All five have inputs; this still does not create authority or adoption.'}`;":
        "status.textContent = `${count} of 5 pilot decisions complete. ${unresolved ? `${unresolved} remain unresolved.` : 'All five are complete; authority and adoption still require explicit review.'}`;",
}
for old, new in js_replacements.items():
    js = replace_once(js, old, new, old[:80])

for residue in [
    "public-safe Place Fabric",
    "organizational gates have named inputs",
    "source-linked verification",
    "transportation voids",
    "cold successor",
    "Name the seat",
]:
    if residue in js:
        raise SystemExit(f"dynamic editorial residue remains: {residue}")
app_path.write_text(js, encoding="utf-8")


# Static release contract: assert both the positive surface and absence of known
# residue. Remove the old disclosure assertion because that layer is now gone.
static_path = ROOT / "tests" / "public_contract_test.py"
static = static_path.read_text(encoding="utf-8")
static = replace_once(
    static,
    '    require("Evidence and boundaries" in html, "concise evidence disclosure label absent")\n',
    "",
    "obsolete evidence disclosure assertion",
)
anchor = '    require(\'placeholder="Operator unresolved"\' in html, "compact operator placeholder absent")\n'
plain_checks = anchor + '''    require("Demonstration trace" in html, "plain-language demonstration label absent")
    require("No private records" in html, "privacy-forward record label absent")
    require("Prepared output" in html and "Prohibited claims and effects" in html, "case consequence labels differ")
    require("Venue / participant group" in html and "Available resources" in html, "plain-language form labels differ")
    require("Export pilot packet" in html, "plain-language export action absent")
    require("06 functions" in html, "Operating Fabric function count label differs")
    require("Help cannot become a penalty." in html, "plain-language adverse-use rule absent")
    require("details class=\"evidence-details\"" not in html, "redundant technical disclosure remains")
    for residue in [
        "no active case", "0 participant records", "public-safe", "source-linked",
        "adverse standing", "execution basis", "resource envelope",
        "technical system", "working-model front door", "program organs",
        "shared institutional substrate", "functional seats",
    ]:
        require(residue not in html.lower(), f"plain-language residue remains in public HTML: {residue}")
    require("public-safe place fabric" not in js.lower(), "public-safe application rhetoric remains")
    require("pilot decisions complete" in js, "plain-language form status absent")
'''
static = replace_once(static, anchor, plain_checks, "static plain-language assertions")
static_path.write_text(static, encoding="utf-8")


# Local and live browser campaigns: prove the exact public language and the clean
# structure in rendered output, not only in source text.
render_checks = '''        assert page.locator(".console-kicker").inner_text() == "Demonstration trace"
        assert "No private records" in page.locator(".attention-instrument .instrument-foot").inner_text()
        assert page.locator("#form-status").inner_text() == "0 of 5 pilot decisions complete. 5 remain unresolved."
        assert page.locator('label:has(#pilot-venue) > span').inner_text() == "Venue / participant group"
        assert page.locator('label:has(#pilot-resources) > span').inner_text() == "Available resources"
        assert page.locator("#export-pilot").inner_text() == "Export pilot packet"
        assert page.locator(".evidence-details").count() == 0
        body_text = page.locator("body").inner_text().lower()
        for residue in ["no active case", "0 participant records", "public-safe", "source-linked", "adverse standing", "execution basis", "resource envelope", "technical system", "working-model front door"]:
            assert residue not in body_text, residue
'''
for test_name in ["browser_test.py", "live_browser_test.py"]:
    test_path = ROOT / "tests" / test_name
    test = test_path.read_text(encoding="utf-8")
    anchor = '        assert page.locator("html").get_attribute("data-theme") is None\n'
    test = replace_once(test, anchor, anchor + render_checks, f"{test_name} public-finish assertions")
    test_path.write_text(test, encoding="utf-8")


# Contract statement for the final authored surface.
contract_path = ROOT / "WORKING_MODEL_CONTRACT.json"
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract["visual_evidence"]["editorial_surface"] = {
    "duplicate_exposition_removed": True,
    "public_internal_jargon_removed": True,
    "operational_proof_instruments": 4,
    "redundant_technical_disclosure_removed": True,
    "single_authored_visual_mode": True,
}
contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

print("PASS_MANZANITA_WORKING_MODEL_FINAL_EDITORIAL_PROGRAM")
