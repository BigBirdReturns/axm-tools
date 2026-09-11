from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "essential-attention" / "index.html"
README_PATH = ROOT / "essential-attention" / "README.md"
STATIC_PATH = ROOT / "essential-attention" / "tests" / "public_contract_test.py"
BROWSER_PATH = ROOT / "essential-attention" / "tests" / "browser_test.py"


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact anchor, found {count}")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, new_body: str) -> str:
    start = text.find(f"function {name}(")
    if start < 0:
        raise SystemExit(f"function {name} missing")
    brace = text.find("{", start)
    depth = 0
    quote: str | None = None
    escaped = False
    i = brace
    while i < len(text):
        c = text[i]
        if quote:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + new_body + text[i + 1 :]
        i += 1
    raise SystemExit(f"function {name} unterminated")


def patch_html() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    if "MILA_BOUNDED_TRANSACTION_V1_3_0" in html:
        raise SystemExit("bounded Mila v1.3.0 already materialized")

    html = html.replace("Essential Attention v1.2.1", "Essential Attention v1.3.0")
    html = html.replace("version:'1.2.1'", "version:'1.3.0'")
    html = html.replace("release:'1.2.1'", "release:'1.3.0'")
    html = html.replace("v1.2.1 · FAB / CASE 001", "v1.3.0 · FAB / CASE 001")
    html = html.replace("MILA_RETURN_PROJECTION_V1_2_1", "MILA_RETURN_PROJECTION_V1_3_0")
    html = html.replace("MILA_RECEIVER_POLISH_V1_2_1", "MILA_RECEIVER_POLISH_V1_3_0")
    html = html.replace(
        "essential-attention/mila-review-packet@1",
        "essential-attention/mila-bounded-review-packet@2",
    )

    replacements = {
        "Essential Attention · Mila executive review · local draft only": "Essential Attention · bounded decision brief · local draft only",
        "Five decisions. Everything needed to decide them.": "One real problem. Five decisions. No portfolio reconstruction.",
        "These are the five choices that require Manzanita’s decision. Everything else stays in its existing state. The page contains no participant records or field cases, and every selection remains a local draft until Manzanita records it through its own accepted process.": "The last exchange identified the missing interface: a defined problem or decision and clear roles. This page asks what should happen next, who owns it, what Jonathan’s role is, what object moves, and where authority stops. It contains no participant records or field cases, and every selection remains a local draft until Manzanita records it through its own accepted process.",
        "No response has been recorded. Silence stays unresolved; it does not mean rejection, hostility, consent, availability, or obligation.": "No accepted return receipt exists. Silence remains unresolved and supplies no evidence of rejection, hostility, consent, availability, duty, or institutional disposition.",
        "Five decisions, each explicit.": "Five required decisions, each explicit.",
    }
    for old, new in replacements.items():
        html = once(html, old, new, f"copy replacement: {old[:32]}")

    css = """

/* MILA_BOUNDED_TRANSACTION_V1_3_0 */
body.mila-projection .mila-return-queues{display:none!important}
body.mila-projection .decision-card .eyebrow{overflow-wrap:anywhere}
body.mila-projection .decision-card .controls{align-items:stretch}
body.mila-projection .decision-card .controls button{min-height:46px;white-space:normal;text-align:left}
body.mila-projection .mila-draft-row em{white-space:normal}
"""
    html = once(html, "\n</style>", css + "\n</style>", "bounded route CSS")

    default_state_anchor = "const DEFAULT_STATE=()=>({"
    bounded = r"""const MILA_BOUNDED_DECISIONS=Object.freeze([
  {decision_id:'MILA-D1',title:'Name the first bounded problem',question:'Which real Manzanita problem should receive the first bounded pass?',current:'unresolved',consequence:'Preparation stays held until one problem is selected or named in one sentence.',safe_next:'Select Catnip, nursery, or field; wildfire and household continuity; another named problem; or hold all pilot work.',options:['CATNIP / NURSERY / FIELD','WILDFIRE / HOUSEHOLD CONTINUITY','OTHER NAMED PROBLEM','HOLD'],sources:[]},
  {decision_id:'MILA-D2',title:'Define Jonathan’s role',question:'What role, if any, should Jonathan hold on that object?',current:'unresolved',consequence:'FAB participation does not silently create project labor, delivery duty, or operating responsibility.',safe_next:'Choose bounded systems reviewer, prototype owner for one pilot, FAB advisory participation only, or no role.',options:['BOUNDED REVIEWER','ONE-PILOT PROTOTYPE OWNER','FAB ONLY','NO ROLE'],sources:[]},
  {decision_id:'MILA-D3',title:'Name problem and decision ownership',question:'Who owns the problem and who can accept, reject, narrow, or close the result?',current:'unresolved',consequence:'An object without a receiving owner cannot become accountable work.',safe_next:'Name Mila for both roles, name separate owners, or hold because ownership is unknown.',options:['MILA OWNS BOTH','NAME SEPARATE OWNERS','OWNERSHIP UNKNOWN'],sources:[]},
  {decision_id:'MILA-D4',title:'Choose the next shared object',question:'What finite object should move next?',current:'unresolved',consequence:'A broad portfolio or open-ended call would recreate the receiver burden already observed.',safe_next:'Choose a one-page problem brief, one supplied rough draft, a thirty-minute decision session using these five questions, or archive and hold.',options:['ONE-PAGE PROBLEM BRIEF','ONE SUPPLIED ROUGH DRAFT','30-MINUTE DECISION SESSION','ARCHIVE / HOLD'],sources:[]},
  {decision_id:'MILA-D5',title:'Set authority and the stop rule',question:'What may this work affect, and what condition stops it?',current:'unresolved',consequence:'Technical readiness cannot authorize participant contact, field activity, spending, assignment, publication, representation, or release.',safe_next:'Keep the object internal, name each permitted external effect and its revocation condition, or grant no authority.',options:['INTERNAL DRAFT ONLY','NAMED EFFECTS ONLY','NO AUTHORITY'],sources:[]}
]);
function activeExecutiveDecisions(){return isMilaProjection()?MILA_BOUNDED_DECISIONS:cartridge.decisions}

"""
    html = once(
        html,
        default_state_anchor,
        bounded + default_state_anchor,
        "bounded decision insertion",
    )

    start = html.find("const MILA_RETURN = Object.freeze({")
    end = html.find("\n});", start)
    if start < 0 or end < 0:
        raise SystemExit("MILA_RETURN block missing")
    end += 4
    new_return = r"""const MILA_RETURN = Object.freeze({
  schema:'essential-attention/mila-bounded-review-packet@2',
  release:'1.3.0',
  communication_state:{accepted_return_receipt:false,state:'unresolved',silence_invariant:'Silence supplies no evidence of rejection, hostility, consent, availability, duty, or institutional disposition.'},
  queue_order:['authority_required','accepted_obligations_at_risk','evidence_ready_for_disposition'],
  queue_labels:{authority_required:'Five required decisions',accepted_obligations_at_risk:'What remains held',evidence_ready_for_disposition:'What the draft can carry'},
  queues:{
    authority_required:MILA_BOUNDED_DECISIONS.map(d=>({id:d.decision_id,title:d.title,detail:d.question})),
    accepted_obligations_at_risk:[
      {id:'MILA-HOLD-ROLE',title:'FAB participation remains advisory',detail:'No project labor follows without an explicit bounded role.'},
      {id:'MILA-HOLD-PILOT',title:'No pilot is accepted',detail:'A problem, owner, object, authority boundary, and stop rule remain required.'},
      {id:'MILA-HOLD-EFFECTS',title:'All external effects remain held',detail:'No contact, field activity, spending, assignment, calendar action, payment, representation, publication, or release is authorized.'}
    ],
    evidence_ready_for_disposition:[
      {id:'MILA-EVIDENCE-BRIEF',title:'One public-safe decision brief',detail:'Five questions and their consequences, without correspondence coordinates or private message bodies.'},
      {id:'MILA-EVIDENCE-DRAFT',title:'One local disposition ledger',detail:'Each decision remains unresolved until a local selection and rationale exist.'},
      {id:'MILA-EVIDENCE-EXPORT',title:'One bounded review export',detail:'The export records a proposed transaction and every false authority field.'}
    ]
  }
});"""
    html = html[:start] + new_return + html[end:]

    html = replace_function(
        html,
        "milaDecisionRows",
        r"""function milaDecisionRows(){
  return MILA_BOUNDED_DECISIONS.map(decision=>{
    const draft=decisionDraft(decision.decision_id);
    return {
      decision_id:decision.decision_id,title:decision.title,question:decision.question,source_state:decision.current,
      consequence:decision.consequence,safe_next:decision.safe_next,source_refs:[],
      local_draft:draft?{receipt_id:draft.receipt_id,disposition:draft.payload?.disposition||'UNRESOLVED',rationale:draft.payload?.rationale||'',created_at:draft.created_at,official_effect:'none'}:'UNRESOLVED'
    };
  });
}""",
    )
    html = replace_function(
        html,
        "milaQueueSnapshot",
        r"""function milaQueueSnapshot(){
  const rows=Object.fromEntries(milaDecisionRows().map(item=>[item.decision_id,item]));
  return {
    authority_required:MILA_RETURN.queues.authority_required.map(item=>({...item,source_state:rows[item.id]?.local_draft==='UNRESOLVED'?'unresolved':'local draft',source_refs:[]})),
    accepted_obligations_at_risk:MILA_RETURN.queues.accepted_obligations_at_risk.map(item=>({...item,source_state:'held',source_refs:[]})),
    evidence_ready_for_disposition:MILA_RETURN.queues.evidence_ready_for_disposition.map(item=>({...item,source_state:'ready',source_refs:[]}))
  };
}""",
    )

    render_start = html.find("function renderExecutive(){")
    render_end = html.find("\n}\n", render_start)
    if render_start < 0 or render_end < 0:
        raise SystemExit("renderExecutive missing")
    render_end += 3
    fn = html[render_start:render_end]
    fn = fn.replace(
        "function renderExecutive(){\n  const reviewed=",
        "function renderExecutive(){\n  const decisions=activeExecutiveDecisions();\n  const reviewed=",
        1,
    )
    fn = fn.replace("cartridge.decisions.filter", "decisions.filter")
    fn = fn.replace("cartridge.decisions.length", "decisions.length")
    fn = fn.replace("cartridge.decisions.map", "decisions.map")
    html = html[:render_start] + fn + html[render_end:]

    html = html.replace(
        "cartridge.decisions.find(d=>d.decision_id===decisionId)",
        "activeExecutiveDecisions().find(d=>d.decision_id===decisionId)",
    )
    html = html.replace(
        "purpose:'Return only the executive decisions, accepted obligations at risk, and evidence ready for disposition.'",
        "purpose:'Let the receiver define one bounded Manzanita transaction without reconstructing the prior portfolio.'",
    )
    html = html.replace(
        "source_receipts:{representation:'metadata_only',count:sourceReceipts.length,private_source_bytes_included:false,source_content_included:false,items:sourceReceipts}",
        "source_receipts:{representation:'public_safe_none',count:0,private_source_bytes_included:false,source_content_included:false,items:[]}",
    )
    html = html.replace(
        "source_receipt_count:packet.source_receipts.count",
        "source_receipt_count:0",
    )
    html = html.replace(
        "definition:'Mila confirms that she can decide the object without reconstructing the portfolio from memory or becoming its routine operator.'",
        "definition:'The receiver confirms that the five questions are sufficient to define or hold one bounded transaction without reconstructing the prior portfolio.'",
    )
    html = html.replace(
        "next_lawful_action:'Mila may draft, narrow, hold, reject, correct, or expire each decision. Official state changes only through an accepted external authority receipt.'",
        "next_lawful_action:'The receiver may select, narrow, hold, reject, or correct each decision. Official state changes only through a separately verified and accepted Manzanita receipt.'",
    )
    html = html.replace(
        "document.title=active?'Mila review · Essential Attention v1.3.0'",
        "document.title=active?'Mila bounded decision brief · Essential Attention v1.3.0'",
    )

    required = [
        "MILA_BOUNDED_TRANSACTION_V1_3_0",
        "MILA_BOUNDED_DECISIONS",
        "One real problem. Five decisions. No portfolio reconstruction.",
        "essential-attention/mila-bounded-review-packet@2",
        "representation:'public_safe_none'",
        "function activeExecutiveDecisions()",
    ]
    missing = [token for token in required if token not in html]
    if missing:
        raise SystemExit(f"materialized HTML missing {missing}")
    HTML_PATH.write_text(html, encoding="utf-8")


def patch_readme() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    readme = readme.replace("# Essential Attention v1.2.1", "# Essential Attention v1.3.0", 1)
    readme = readme.replace(
        "## Mila return projection (v1.2.1)",
        "## Mila return projection (v1.3.0)",
    )
    readme = readme.replace(
        "## Mila receiver polish (v1.2.1)",
        "## Mila receiver polish (v1.3.0)",
    )
    readme += """

## Bounded Mila transaction (v1.3.0)

The direct Mila route now implements the receiver interface requested in the last observed exchange: one defined problem or decision and explicit roles. It no longer presents Meeting #2, unnamed-offer recovery, or the accumulated portfolio as the primary decision burden. The five required choices are the first problem, Jonathan's role, problem and decision ownership, the next shared object, and the authority and stop rule. The ordinary operating desk retains its original case decisions.

The direct export uses `essential-attention/mila-bounded-review-packet@2`. It carries no correspondence coordinates, email addresses, message identifiers, private source metadata, participant records, field cases, or external authority. A local complete draft remains preparatory until a separately verified and accepted Manzanita receipt creates an official state transition.
"""
    README_PATH.write_text(readme, encoding="utf-8")


def patch_static_test() -> None:
    static = STATIC_PATH.read_text(encoding="utf-8")
    static = static.replace("release_1_2_1", "release_1_3_0")
    static = static.replace("Essential Attention v1.2.1", "Essential Attention v1.3.0")
    static = static.replace("version:'1.2.1'", "version:'1.3.0'")
    static = static.replace(
        "essential-attention/mila-review-packet@1",
        "essential-attention/mila-bounded-review-packet@2",
    )
    static = static.replace("MILA_RETURN_PROJECTION_V1_2_1", "MILA_RETURN_PROJECTION_V1_3_0")
    static = static.replace("MILA_RECEIVER_POLISH_V1_2_1", "MILA_RECEIVER_POLISH_V1_3_0")
    static = static.replace('"release": "1.2.1"', '"release": "1.3.0"')
    static = static.replace(
        '"mila_review_packet_schema": "essential-attention/mila-review-packet@1"',
        '"mila_review_packet_schema": "essential-attention/mila-bounded-review-packet@2"',
    )
    anchor = '    "mila_readme": "## Mila return projection (v1.3.0)" in readme,'
    static = once(
        static,
        anchor,
        '    "mila_bounded_transaction": "MILA_BOUNDED_DECISIONS" in source and "One real problem. Five decisions. No portfolio reconstruction." in source,\n'
        '    "mila_public_safe_export": "public_safe_none" in source and "essential-attention/mila-bounded-review-packet@2" in source,\n'
        + anchor,
        "static bounded transaction checks",
    )
    STATIC_PATH.write_text(static, encoding="utf-8")


def patch_browser_test() -> None:
    browser = BROWSER_PATH.read_text(encoding="utf-8")
    browser = browser.replace("Essential Attention v1.2.1", "Essential Attention v1.3.0")
    browser = browser.replace("v1.2.1", "v1.3.0")
    browser = browser.replace(
        "essential-attention/mila-review-packet@1",
        "essential-attention/mila-bounded-review-packet@2",
    )
    browser = browser.replace(
        "Mila review · Essential Attention v1.3.0",
        "Mila bounded decision brief · Essential Attention v1.3.0",
    )
    anchor = '    check("Mila projection preserves five decision cards", mila_page.locator(".decision-card").count() == 5)'
    browser = once(
        browser,
        anchor,
        anchor
        + '\n    check("Mila projection uses the bounded transaction questions", mila_page.locator(".decision-card h3").all_inner_texts() == ["Name the first bounded problem", "Define Jonathan’s role", "Name problem and decision ownership", "Choose the next shared object", "Set authority and the stop rule"])'
        + '\n    check("Mila projection removes portfolio-era decision burden", "Meeting #2" not in mila_page.locator("#view-executive").inner_text() and "unnamed offers" not in mila_page.locator("#view-executive").inner_text())',
        "browser bounded question checks",
    )
    browser = browser.replace(
        'mila_packet["source_receipts"]["private_source_bytes_included"] is False and mila_packet["source_receipts"]["source_content_included"] is False and all(item["bytes_included"] is False for item in mila_packet["source_receipts"]["items"])',
        'mila_packet["source_receipts"]["count"] == 0 and mila_packet["source_receipts"]["items"] == [] and mila_packet["source_receipts"]["private_source_bytes_included"] is False and mila_packet["source_receipts"]["source_content_included"] is False',
    )
    browser = browser.replace(
        '"schema": "essential-attention/browser-qualification@5"',
        '"schema": "essential-attention/browser-qualification@6"',
    )
    BROWSER_PATH.write_text(browser, encoding="utf-8")


def main() -> None:
    patch_html()
    patch_readme()
    patch_static_test()
    patch_browser_test()
    print("Essential Attention bounded Mila v1.3.0 materialized")


if __name__ == "__main__":
    main()
