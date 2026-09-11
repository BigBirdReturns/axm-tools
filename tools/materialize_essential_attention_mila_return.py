from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EA = ROOT / "essential-attention"
HTML_PATH = EA / "index.html"
README_PATH = EA / "README.md"
STATIC_PATH = EA / "tests" / "public_contract_test.py"
BROWSER_PATH = EA / "tests" / "browser_test.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "essential-attention-check.yml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact anchor, found {count}")
    return text.replace(old, new, 1)


def patch_html() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    if "MILA_RETURN_PROJECTION_V1_2_1" in html:
        raise SystemExit("Mila return projection is already materialized")

    html = html.replace("Essential Attention v1.2.0", "Essential Attention v1.2.1")
    html = html.replace("version:'1.2.0'", "version:'1.2.1'")
    html = html.replace("v1.2.0 · FAB / CASE 001", "v1.2.1 · FAB / CASE 001")

    css = textwrap.dedent(
        r"""

        /* MILA_RETURN_PROJECTION_V1_2_1 */
        .mila-return{display:none}
        body.mila-projection .mila-return{display:block}
        body.mila-projection .executive-generic,
        body.mila-projection #helpButton,
        body.mila-projection #guidanceButton,
        body.mila-projection #importPacketButton,
        body.mila-projection #exportPacketButton,
        body.mila-projection #tourBar,
        body.mila-projection #guidanceDrawer,
        body.mila-projection #guidanceBackdrop{display:none!important}
        body.mila-projection .seat-nav button:not([data-view="executive"]){display:none}
        body.mila-projection .seat-nav{overflow:visible}
        body.mila-projection .view{min-height:calc(100vh - 120px)}
        .mila-return-intro{margin:0 0 24px;padding:clamp(24px,4vw,46px);border:1px solid var(--rule);background:linear-gradient(135deg,var(--paper),var(--green2));box-shadow:var(--shadow)}
        .mila-return-intro h2{max-width:900px;margin:.35rem 0 .8rem;font-size:clamp(2.35rem,5vw,5.4rem);line-height:.92;letter-spacing:-.045em}
        .mila-return-intro>p{max-width:900px;margin:0;color:var(--muted);font-size:1rem;line-height:1.65}
        .mila-communication{margin-top:22px;padding:16px 18px;border-left:5px solid var(--rust);background:var(--rust2);line-height:1.55}
        .mila-communication strong{display:block;margin-bottom:3px;font-family:var(--mono);font-size:.72rem;letter-spacing:.08em;text-transform:uppercase}
        .mila-return-counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:22px;border-top:1px solid var(--rule);border-left:1px solid var(--rule)}
        .mila-return-counts article{min-width:0;padding:15px;border-right:1px solid var(--rule);border-bottom:1px solid var(--rule);background:rgba(255,253,247,.72)}
        .mila-return-counts b{display:block;font-family:var(--serif);font-size:2rem;line-height:1}
        .mila-return-counts span{display:block;margin-top:5px;color:var(--muted);font-size:.72rem;line-height:1.3;text-transform:uppercase;letter-spacing:.055em}
        .mila-return-queues{margin:26px 0}
        .mila-queue-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
        .mila-queue{min-width:0;border:1px solid var(--rule);background:var(--paper)}
        .mila-queue header{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:17px 18px;border-bottom:1px solid var(--rule);background:var(--soft)}
        .mila-queue header h3{margin:0;font-size:1.05rem;line-height:1.18}
        .mila-queue header b{flex:0 0 auto;display:grid;place-items:center;min-width:30px;height:30px;border:1px solid var(--rule);font-family:var(--mono);font-size:.72rem}
        .mila-queue ol{list-style:none;margin:0;padding:0}
        .mila-queue li{min-width:0;padding:16px 18px;border-bottom:1px solid var(--rule);overflow-wrap:anywhere}
        .mila-queue li:last-child{border-bottom:0}
        .mila-queue li strong{display:block;font-size:.92rem;line-height:1.3}
        .mila-queue li p{margin:7px 0;color:var(--muted);font-size:.82rem;line-height:1.5}
        .mila-queue li span{display:block;color:var(--green);font-family:var(--mono);font-size:.66rem;line-height:1.35;text-transform:uppercase;letter-spacing:.045em}
        .mila-drafts{margin-top:26px;padding:clamp(20px,3vw,32px);border:1px solid var(--rule);background:var(--soft)}
        .mila-subhead{display:flex;justify-content:space-between;gap:24px;align-items:end;margin-bottom:16px}
        .mila-subhead h3{margin:0;font-size:clamp(1.65rem,3vw,2.7rem);line-height:1}
        .mila-subhead p{max-width:520px;margin:0;color:var(--muted);font-size:.82rem;line-height:1.5}
        .mila-draft-ledger{border:1px solid var(--rule);background:var(--paper)}
        .mila-draft-row{display:grid;grid-template-columns:minmax(160px,.8fr) minmax(220px,1.45fr) minmax(160px,.75fr);gap:16px;align-items:start;padding:15px 17px;border-bottom:1px solid var(--rule);overflow-wrap:anywhere}
        .mila-draft-row:last-child{border-bottom:0}
        .mila-draft-row strong{font-size:.86rem;line-height:1.35}
        .mila-draft-row p{margin:0;color:var(--muted);font-size:.8rem;line-height:1.45}
        .mila-draft-row em{justify-self:start;padding:5px 7px;border:1px solid var(--rule);font-family:var(--mono);font-size:.64rem;font-style:normal;text-transform:uppercase;letter-spacing:.04em}
        .mila-draft-row.is-drafted{box-shadow:inset 4px 0 0 var(--green)}
        .mila-draft-row.is-drafted em{color:var(--ok);border-color:currentColor}
        .mila-export-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:center;margin-top:18px}
        .mila-export-row p{margin:0;color:var(--muted);font-size:.78rem;line-height:1.5}
        #exportMilaPacketButton{min-height:46px;white-space:normal}
        @media(max-width:1100px){.mila-queue-grid{grid-template-columns:1fr}.mila-return-counts{grid-template-columns:repeat(2,minmax(0,1fr))}}
        @media(max-width:780px){body.mila-projection .seat-nav{display:block}.mila-return-intro{padding:25px 20px}.mila-return-intro h2{font-size:clamp(2.3rem,13vw,4rem)}.mila-draft-row{grid-template-columns:1fr}.mila-draft-row em{grid-row:1}.mila-subhead,.mila-export-row{display:block}.mila-subhead p,.mila-export-row button{margin-top:13px}.mila-export-row button{width:100%}}
        @media(max-width:430px){.mila-return-counts{grid-template-columns:1fr}.mila-queue header,.mila-queue li,.mila-draft-row{padding-inline:13px}.mila-drafts{padding-inline:12px}body.mila-projection .top-actions{display:none}}
        """
    )
    html = replace_once(html, "\n</style>", css + "\n</style>", "style insertion")

    old_executive = textwrap.dedent(
        """\
              <section class="view" id="view-executive">
                <div class="section-head"><div><div class="eyebrow">Decision authority</div><h2>Five bounded questions</h2></div><p>The queue borrows the discipline of an enterprise record process: show the stage, key facts, consequence, safe progress, and next action without pretending that a browser click exercises organizational authority.</p></div>
                <div class="decision-summary" id="decisionSummary"></div>
                <div class="warning"><strong>No executive theater.</strong> Reviewing a question or saving a local draft does not appoint anyone, schedule a meeting, commit Manzanita, or authorize field activity.</div>
                <div class="decision-grid" id="decisionGrid"></div>
              </section>"""
    )
    new_executive = textwrap.dedent(
        """\
              <section class="view" id="view-executive">
                <div class="section-head executive-generic"><div><div class="eyebrow">Decision authority</div><h2>Five bounded questions</h2></div><p>The queue shows the stage, key facts, consequence, safe progress, and next action without pretending that a browser click exercises organizational authority.</p></div>
                <section class="mila-return mila-return-intro" aria-labelledby="milaReturnTitle">
                  <div class="eyebrow">Mila executive projection · draft only</div>
                  <h2 id="milaReturnTitle">Five decisions. No reconstructed universe.</h2>
                  <p>This view contains only the questions that require Manzanita executive authority, the obligations whose status matters now, and the evidence already ready for disposition. It contains zero participant records and zero field cases. Every action remains a local draft until an accepted external authority receipt changes official state.</p>
                  <div class="mila-communication" id="milaCommunicationState"><strong>Communication state</strong>No accepted return receipt exists. Silence remains unresolved and supplies no evidence of rejection, hostility, consent, availability, or duty.</div>
                  <div class="mila-return-counts" id="milaReturnCounts" aria-label="Mila review counts"></div>
                </section>
                <div class="decision-summary" id="decisionSummary"></div>
                <div class="warning executive-generic"><strong>No executive theater.</strong> Reviewing a question or saving a local draft does not appoint anyone, schedule a meeting, commit Manzanita, or authorize field activity.</div>
                <section class="mila-return mila-return-queues" aria-label="Mila decision queues"><div class="mila-queue-grid" id="milaQueueGrid"></div></section>
                <div class="decision-grid" id="decisionGrid"></div>
                <section class="mila-return mila-drafts" aria-labelledby="milaDraftTitle">
                  <div class="mila-subhead"><div><div class="eyebrow">Local disposition ledger</div><h3 id="milaDraftTitle">Five decisions, each explicit.</h3></div><p>Unresolved means unresolved. A local draft records a proposed disposition and its rationale; it creates no appointment, calendar act, commitment, publication, spending, or field authority.</p></div>
                  <div class="mila-draft-ledger" id="milaDraftLedger"></div>
                  <div class="mila-export-row"><p>The exported review packet contains decision states, source references, queue summaries, and local receipt metadata. It excludes private source bytes and performs no network request.</p><button class="primary" id="exportMilaPacketButton" type="button">Export Mila review packet</button></div>
                </section>
              </section>"""
    )
    html = replace_once(html, old_executive, new_executive, "executive projection")

    build_anchor = "const BUILD = Object.freeze({version:'1.2.1',built_at:'2026-08-13T04:00:00Z',host:'axm-tools/essential-attention',network:'none'});"
    mila_constant = textwrap.dedent(
        r"""
        const MILA_RETURN = Object.freeze({
          schema:'essential-attention/mila-review-packet@1',
          release:'1.2.1',
          communication_state:{accepted_return_receipt:false,state:'unresolved',silence_invariant:'Silence supplies no evidence of rejection, hostility, consent, availability, or duty.'},
          queue_order:['authority_required','accepted_obligations_at_risk','evidence_ready_for_disposition'],
          queue_labels:{
            authority_required:'Authority required from Mila',
            accepted_obligations_at_risk:'Accepted obligations at risk',
            evidence_ready_for_disposition:'Evidence ready for disposition'
          },
          queues:{
            authority_required:[
              {id:'EA-DEC-001',title:'Set or hold FAB Meeting #2',detail:'Choose a date and scheduling owner, or keep the meeting held until its evidence agenda is ready.'},
              {id:'EA-DEC-002',title:'Recover or expire the unnamed offers',detail:'Authorize a bounded source pass, preserve only the aggregate mention, or set an expiry trigger.'},
              {id:'EA-DEC-003',title:'Bound the Catnip and field review',detail:'Name one review question and source boundary, or leave the object dormant.'},
              {id:'EA-DEC-004',title:'Preserve the accepted N=0 boundary',detail:'The internal runtime is accepted. Any field, spending, assignment, representation, publication, or release effect still requires separate authority.'},
              {id:'EA-DEC-005',title:'Define the external-effect authority map',detail:'Identify the real authority for each later email, calendar, payment, publication, or institutional acceptance effect.'}
            ],
            accepted_obligations_at_risk:[
              {id:'FAB-ROLE-JS-001',title:'FAB service remains accepted and bounded',detail:'Board participation supports advisory work only. Every new request still needs explicit scope, due state, and work basis.'},
              {id:'FAB-MEETING2-003',title:'Meeting #2 remains held',detail:'A proposed meeting is not a scheduled or accepted obligation until a date and owner are explicitly set.'},
              {id:'FAB-CATNIP-FIELD-006',title:'Catnip review remains offered',detail:'The conditional review offer creates no field partner, deadline, workload, or program obligation.'},
              {id:'FAB-ESSENTIAL-ATTENTION-007',title:'Essential Attention is accepted internally only',detail:'The N=0 administrative runtime may carry records and drafts. No outside actor, role, or real-world effect is accepted.'}
            ],
            evidence_ready_for_disposition:[
              {id:'EA-FIVE-DECISIONS',title:'Five source-linked executive questions',detail:'Each question carries its current state, consequence, safe next step, and source object.'},
              {id:'EA-OFFER-REGISTER',title:'Seven-record FAB offer register',detail:'The register distinguishes accepted, completed, held, offered, and unresolved states without converting silence into motive.'},
              {id:'EA-SOURCE-METADATA',title:'Local source receipt metadata',detail:'Names, sizes, types, timestamps, purposes, and SHA-256 identities may travel; private source bytes do not.'},
              {id:'EA-SUCCESSOR-REPLAY',title:'Successor replay and current custody',detail:'The packet states the object, accepted authority, unresolved facts, deliberate omissions, fallback, and next lawful action.'}
            ]
          }
        });
        """
    ).strip()
    html = replace_once(html, build_anchor, build_anchor + "\n" + mila_constant, "Mila return constant")

    decision_anchor = "function decisionDraft(decisionId){return [...state.ledger].reverse().find(x=>x.kind==='executive-disposition'&&x.object_id===decisionId)}\nfunction stateCounts()"
    mila_functions = textwrap.dedent(
        r"""
        function isMilaProjection(){
          return new URLSearchParams(location.search).get('projection')==='mila'||location.hash.toLowerCase()==='#mila';
        }

        function milaDecisionRows(){
          return cartridge.decisions.map(decision=>{
            const draft=decisionDraft(decision.decision_id);
            return {
              decision_id:decision.decision_id,
              title:decision.title,
              question:decision.question,
              source_state:decision.current,
              consequence:decision.consequence,
              safe_next:decision.safe_next,
              source_refs:[...(decision.sources||[])],
              local_draft:draft?{
                receipt_id:draft.receipt_id,
                disposition:draft.payload?.disposition||'UNRESOLVED',
                rationale:draft.payload?.rationale||'',
                created_at:draft.created_at,
                official_effect:'none'
              }:'UNRESOLVED'
            };
          });
        }

        function milaSourceReceiptMetadata(){
          return state.source_receipts.map(receipt=>({
            receipt_id:receipt.receipt_id,
            name:receipt.name,
            size:receipt.size,
            type:receipt.type,
            last_modified:receipt.last_modified,
            sha256:receipt.sha256,
            purpose:receipt.purpose,
            imported_at:receipt.imported_at,
            network_transmitted:false,
            bytes_included:false
          }));
        }

        function milaQueueSnapshot(){
          const decisions=Object.fromEntries(cartridge.decisions.map(item=>[item.decision_id,item]));
          const offers=Object.fromEntries(activeOffers().map(item=>[item.offer_id,item]));
          const replayPassed=state.ledger.some(item=>item.kind==='successor-replay'&&Number(item.payload?.passed)===Number(item.payload?.total));
          return {
            authority_required:MILA_RETURN.queues.authority_required.map(item=>({...item,source_state:decisions[item.id]?.current||'unresolved',source_refs:[...(decisions[item.id]?.sources||[])]})),
            accepted_obligations_at_risk:MILA_RETURN.queues.accepted_obligations_at_risk.map(item=>({...item,source_state:offers[item.id]?.current_state||'unresolved',source_refs:[...(offers[item.id]?.source_receipts||[])]})),
            evidence_ready_for_disposition:MILA_RETURN.queues.evidence_ready_for_disposition.map(item=>{
              const dynamic={
                'EA-FIVE-DECISIONS':`${cartridge.decisions.length} questions`,
                'EA-OFFER-REGISTER':`${activeOffers().length} records`,
                'EA-SOURCE-METADATA':`${state.source_receipts.length} metadata receipts`,
                'EA-SUCCESSOR-REPLAY':replayPassed?'cold replay passed':'replay packet ready'
              };
              return {...item,source_state:dynamic[item.id],source_refs:item.id==='EA-FIVE-DECISIONS'?[...new Set(cartridge.decisions.flatMap(decision=>decision.sources||[]))]:[]};
            })
          };
        }

        function renderMilaReturn(){
          const counts=$('#milaReturnCounts');
          const grid=$('#milaQueueGrid');
          const ledger=$('#milaDraftLedger');
          if(!counts||!grid||!ledger)return;
          const decisions=milaDecisionRows();
          const drafted=decisions.filter(item=>item.local_draft!=='UNRESOLVED').length;
          const queues=milaQueueSnapshot();
          counts.innerHTML=[
            [decisions.length,'executive questions'],
            [drafted,'local dispositions'],
            [decisions.length-drafted,'still unresolved'],
            [0,'field cases']
          ].map(([value,label])=>`<article><b>${esc(value)}</b><span>${esc(label)}</span></article>`).join('');
          grid.innerHTML=MILA_RETURN.queue_order.map(key=>{
            const items=queues[key];
            return `<section class="mila-queue" data-mila-queue="${esc(key)}"><header><h3>${esc(MILA_RETURN.queue_labels[key])}</h3><b>${items.length}</b></header><ol>${items.map(item=>`<li><strong>${esc(item.title)}</strong><p>${esc(item.detail)}</p><span>${esc(item.id)} · ${esc(item.source_state)}</span></li>`).join('')}</ol></section>`;
          }).join('');
          ledger.innerHTML=decisions.map(item=>{
            const draftedNow=item.local_draft!=='UNRESOLVED';
            const detail=draftedNow?`${item.local_draft.disposition}: ${item.local_draft.rationale}`:'No local disposition has been recorded.';
            return `<article class="mila-draft-row ${draftedNow?'is-drafted':''}" data-mila-draft="${esc(item.decision_id)}"><strong>${esc(item.decision_id)} · ${esc(item.title)}</strong><p>${esc(detail)}</p><em>${draftedNow?'local draft':'unresolved'}</em></article>`;
          }).join('');
        }

        function buildMilaReviewPacket(){
          const decisions=milaDecisionRows();
          const sourceReceipts=milaSourceReceiptMetadata();
          return {
            schema:MILA_RETURN.schema,
            release:MILA_RETURN.release,
            generated_at:now(),
            build:{...BUILD},
            projection:{
              id:'mila',
              purpose:'Return only the executive decisions, accepted obligations at risk, and evidence ready for disposition.',
              communication_state:{...MILA_RETURN.communication_state}
            },
            object:{
              cartridge_id:cartridge.cartridge_id,
              cartridge_version:cartridge.version,
              evidence_ceiling:cartridge.evidence_ceiling,
              official_effect:'none'
            },
            queues:milaQueueSnapshot(),
            decisions,
            decision_counts:{required:decisions.length,local_drafts:decisions.filter(item=>item.local_draft!=='UNRESOLVED').length,unresolved:decisions.filter(item=>item.local_draft==='UNRESOLVED').length},
            source_receipts:{representation:'metadata_only',count:sourceReceipts.length,private_source_bytes_included:false,source_content_included:false,items:sourceReceipts},
            recipient_return_confirmation:{
              status:'unresolved',
              may_be_confirmed_by:['Mila'],
              definition:'Mila confirms that she can decide the object without reconstructing the portfolio from memory or becoming its routine operator.'
            },
            privacy:{participant_records:0,field_cases:0,participant_data_included:false,private_source_bytes_included:false},
            authority:{
              institutional_acceptance:false,
              participant_consent:false,
              field_authority:false,
              spend_authority:false,
              assignment_authority:false,
              calendar_authority:false,
              payment_authority:false,
              representation_authority:false,
              publication_authority:false,
              release_authority:false,
              operator_acceptance:false,
              external_effect:'none'
            },
            silence_invariant:MILA_RETURN.communication_state.silence_invariant,
            next_lawful_action:'Mila may draft, narrow, hold, reject, correct, or expire each decision. Official state changes only through an accepted external authority receipt.'
          };
        }

        async function exportMilaReview(){
          const packet=buildMilaReviewPacket();
          downloadJSON(`essential-attention-mila-review-${Date.now()}.json`,packet);
          await appendLedger('mila-review-export','attention-sovereign',cartridge.cartridge_id,{schema:packet.schema,decision_drafts:packet.decision_counts.local_drafts,source_receipt_count:packet.source_receipts.count,private_source_bytes_included:false,external_effect:'none'});
          toast('Mila review packet exported locally. No external effect occurred.');
        }

        function applyProjectionShell(){
          const active=isMilaProjection();
          document.body.classList.toggle('mila-projection',active);
          document.title=active?'Mila review · Essential Attention v1.2.1':'Essential Attention v1.2.1 · FAB Operating Desk';
          if(active){
            state.preferences.tour_active=false;
            state.preferences.guidance_open=false;
            const help=$('#helpDialog');if(help?.open)help.close();
            const drawer=$('#guidanceDrawer');if(drawer){drawer.classList.remove('open');drawer.setAttribute('aria-hidden','true')}
            const backdrop=$('#guidanceBackdrop');if(backdrop)backdrop.hidden=true;
          }
          renderMilaReturn();
          return active;
        }
        """
    ).strip()
    html = replace_once(
        html,
        decision_anchor,
        "function decisionDraft(decisionId){return [...state.ledger].reverse().find(x=>x.kind==='executive-disposition'&&x.object_id===decisionId)}\n"
        + mila_functions
        + "\nfunction stateCounts()",
        "Mila return functions",
    )

    old_render_all = "function renderAll(){renderStart();renderOverview();renderRegister();renderExecutive();renderFab();renderRuntime();renderSuccessor();renderSources();renderLedger();renderHandoff();renderTour();renderGuidance();$('#runtimeStatus').textContent=latestRun()?'Internal check passed':'Local case ready';$('.brand small').textContent='v1.2.1 · FAB / CASE 001'}"
    new_render_all = "function renderAll(){renderStart();renderOverview();renderRegister();renderExecutive();renderFab();renderRuntime();renderSuccessor();renderSources();renderLedger();renderHandoff();renderMilaReturn();renderTour();renderGuidance();$('#runtimeStatus').textContent=latestRun()?'Internal check passed':'Local case ready';$('.brand small').textContent='v1.2.1 · FAB / CASE 001'}"
    html = replace_once(html, old_render_all, new_render_all, "renderAll")

    old_show = "function showView(view){if(!document.getElementById(`view-${view}`))view='start';$$('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${view}`));$$('.seat-nav button').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.view===view)));state.preferences.view=view;storage.set('state',state);window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});renderTour();renderGuidance()}"
    new_show = "function showView(view,{persist=true}={}){if(!document.getElementById(`view-${view}`))view='start';$$('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${view}`));$$('.seat-nav button').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.view===view)));if(persist){state.preferences.view=view;storage.set('state',state)}window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});renderTour();renderGuidance()}"
    html = replace_once(html, old_show, new_show, "non-persistent direct projection route")

    old_tour = "function renderTour(){\n  const bar=$('#tourBar');const active=Boolean(state.preferences?.tour_active);bar.hidden=!active;if(!active)return;"
    new_tour = "function renderTour(){\n  const bar=$('#tourBar');if(isMilaProjection()){bar.hidden=true;return}const active=Boolean(state.preferences?.tour_active);bar.hidden=!active;if(!active)return;"
    html = replace_once(html, old_tour, new_tour, "Mila tour suppression")

    old_export_bind = "$('#hashSourcesButton').addEventListener('click',hashSelectedSources);$('#exportSourcesButton').addEventListener('click',()=>downloadJSON(`ea-source-receipts-${Date.now()}.json`,{schema:'essential-attention/source-receipt-export@2',generated_at:now(),cartridge_id:cartridge.cartridge_id,receipts:state.source_receipts}));$('#exportPacketButton').addEventListener('click',()=>exportPacket().catch(err=>{console.error(err);toast(`Export unavailable: ${err.message}`)}));$('#exportLedgerButton').addEventListener('click',()=>downloadJSON(`ea-ledger-${Date.now()}.json`,{schema:'essential-attention/ledger-export@2',generated_at:now(),cartridge_id:cartridge.cartridge_id,ledger:allLedgerRows()}));"
    new_export_bind = old_export_bind + "\n  $('#exportMilaPacketButton').addEventListener('click',()=>exportMilaReview().catch(err=>{console.error(err);toast(`Mila review export unavailable: ${err.message}`)}));"
    html = replace_once(html, old_export_bind, new_export_bind, "Mila export binding")

    old_boot = textwrap.dedent(
        """\
        async function boot(){
          const saved=await storage.get('state');if(saved&&typeof saved==='object'){const defaults=DEFAULT_STATE();const p={...defaults.preferences,...(saved.preferences||{})};p.visited_offers=Array.isArray(p.visited_offers)?p.visited_offers:[];p.recent_objects=Array.isArray(p.recent_objects)?p.recent_objects:[];p.reviewed_decisions=Array.isArray(p.reviewed_decisions)?p.reviewed_decisions:[];state={...defaults,...saved,ledger:Array.isArray(saved.ledger)?saved.ledger:[],source_receipts:Array.isArray(saved.source_receipts)?saved.source_receipts:[],seat_runs:Array.isArray(saved.seat_runs)?saved.seat_runs:[],preferences:p};if(saved.active_cartridge){try{validateImportedCartridge(saved.active_cartridge);cartridge=saved.active_cartridge}catch{cartridge=FAB_CARTRIDGE}}}
          selectedOfferId=cartridge.offers[0]?.offer_id||'';bind();renderAll();const ordinaryViews=new Set(['overview','register','executive','sources','handoff']);showView(ordinaryViews.has(state.preferences.view)?state.preferences.view:'overview');if(state.preferences.tour_active){const step=TOUR_STEPS[Math.max(0,Math.min(Number(state.preferences.tour_step)||0,TOUR_STEPS.length-1))];showView(step.view)}else if(!state.preferences.onboarding_seen){openHelp()}
        }"""
    )
    new_boot = textwrap.dedent(
        """\
        async function boot(){
          const saved=await storage.get('state');if(saved&&typeof saved==='object'){const defaults=DEFAULT_STATE();const p={...defaults.preferences,...(saved.preferences||{})};p.visited_offers=Array.isArray(p.visited_offers)?p.visited_offers:[];p.recent_objects=Array.isArray(p.recent_objects)?p.recent_objects:[];p.reviewed_decisions=Array.isArray(p.reviewed_decisions)?p.reviewed_decisions:[];state={...defaults,...saved,ledger:Array.isArray(saved.ledger)?saved.ledger:[],source_receipts:Array.isArray(saved.source_receipts)?saved.source_receipts:[],seat_runs:Array.isArray(saved.seat_runs)?saved.seat_runs:[],preferences:p};if(saved.active_cartridge){try{validateImportedCartridge(saved.active_cartridge);cartridge=saved.active_cartridge}catch{cartridge=FAB_CARTRIDGE}}}
          selectedOfferId=cartridge.offers[0]?.offer_id||'';bind();renderAll();const mila=applyProjectionShell();const ordinaryViews=new Set(['overview','register','executive','sources','handoff']);if(mila){showView('executive',{persist:false});const help=$('#helpDialog');if(help?.open)help.close()}else{showView(ordinaryViews.has(state.preferences.view)?state.preferences.view:'overview');if(state.preferences.tour_active){const step=TOUR_STEPS[Math.max(0,Math.min(Number(state.preferences.tour_step)||0,TOUR_STEPS.length-1))];showView(step.view)}else if(!state.preferences.onboarding_seen){openHelp()}}
          window.addEventListener('hashchange',()=>{const direct=applyProjectionShell();if(direct){showView('executive',{persist:false});const help=$('#helpDialog');if(help?.open)help.close()}else{showView(ordinaryViews.has(state.preferences.view)?state.preferences.view:'overview',{persist:false})}});
        }"""
    )
    html = replace_once(html, old_boot, new_boot, "direct Mila boot route")

    required = [
        "MILA_RETURN_PROJECTION_V1_2_1",
        "get('projection')==='mila'",
        "location.hash.toLowerCase()==='#mila'",
        "Five decisions. No reconstructed universe.",
        "Authority required from Mila",
        "Accepted obligations at risk",
        "Evidence ready for disposition",
        "essential-attention/mila-review-packet@1",
        "private_source_bytes_included:false",
        "external_effect:'none'",
    ]
    missing = [token for token in required if token not in html]
    if missing:
        raise SystemExit(f"materialized HTML missing: {missing}")
    HTML_PATH.write_text(html, encoding="utf-8")


def patch_readme() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    readme = readme.replace("# Essential Attention v1.2.0", "# Essential Attention v1.2.1", 1)
    marker = "## Mila return projection (v1.2.1)"
    if marker not in readme:
        readme += textwrap.dedent(
            r"""

            ## Mila return projection (v1.2.1)

            `?projection=mila` and `#mila` open the Decisions surface directly as a bounded executive projection. The ordinary operating-desk route remains unchanged. The direct projection suppresses onboarding, the guided tour, advanced packet controls, and unrelated navigation so Mila receives only five executive questions, three current queues, the local disposition ledger, and one local review-packet export.

            The three queues separate authority required from Mila, accepted obligations at risk, and evidence ready for disposition. They preserve the source states of the five decisions and seven FAB records. Accepted FAB participation remains bounded advisory service; Meeting #2 remains held; Catnip remains a conditional review offer; Essential Attention remains accepted only as an internal N=0 runtime. None of those states creates a field partner, unbounded workload, calendar act, expenditure, publication, representation, or institutional commitment.

            Communication state remains exact: no accepted return receipt exists. Mila's silence remains unresolved and supplies no evidence of rejection, hostility, consent, availability, or duty. The interface does not manufacture a motive or convert elapsed time into an organizational disposition.

            The export uses `essential-attention/mila-review-packet@1`. It contains the five decision records, latest local disposition or `UNRESOLVED`, source references, all three queues, recipient-return status, and local source-receipt metadata. It includes zero participant records, zero field cases, and zero private source bytes. Every real-world authority field remains false and `external_effect` remains `none`; only an accepted external authority receipt can change official state.
            """
        )
    README_PATH.write_text(readme, encoding="utf-8")


def patch_static_test() -> None:
    static = STATIC_PATH.read_text(encoding="utf-8")
    static = replace_once(
        static,
        '    "release_1_2_0": "Essential Attention v1.2.0" in source and "version:\'1.2.0\'" in source,',
        '    "release_1_2_1": "Essential Attention v1.2.1" in source and "version:\'1.2.1\'" in source,',
        "static release version",
    )
    checks_anchor = '    "readme_present": README.exists() and len(readme) > 8000,'
    checks = textwrap.dedent(
        r'''\
            "mila_query_and_hash_routes": "get('projection')==='mila'" in source and "location.hash.toLowerCase()==='#mila'" in source,
            "mila_body_projection": "mila-projection" in source and "Five decisions. No reconstructed universe." in source,
            "mila_three_queues": all(token in source for token in ["authority_required:", "accepted_obligations_at_risk:", "evidence_ready_for_disposition:"]),
            "mila_packet_schema": "essential-attention/mila-review-packet@1" in source,
            "mila_source_bytes_excluded": "private_source_bytes_included:false" in source and "source_content_included:false" in source and "bytes_included:false" in source,
            "mila_recipient_return_unresolved": "recipient_return_confirmation" in source and "status:'unresolved'" in source,
            "mila_silence_invariant": "Silence supplies no evidence of rejection, hostility, consent, availability, or duty." in source,
            "mila_real_world_authority_held": all(token in source for token in ["institutional_acceptance:false", "field_authority:false", "spend_authority:false", "assignment_authority:false", "publication_authority:false", "release_authority:false", "external_effect:'none'"]),
            "mila_readme": "## Mila return projection (v1.2.1)" in readme,
        ''')
    static = replace_once(static, checks_anchor, checks + checks_anchor, "static Mila checks")
    static = static.replace('"schema": "essential-attention/pages-qualification@4"', '"schema": "essential-attention/pages-qualification@5"')
    static = static.replace('"release": "1.2.0"', '"release": "1.2.1"')
    static = replace_once(
        static,
        '    "operator_surface": "AXM Operating Desk with Today, Records, Decisions, Evidence, Handoff, and progressive advanced tools",\n    "external_effect_adapters": 0,',
        '    "operator_surface": "AXM Operating Desk plus a direct Mila decision-only return projection",\n    "mila_return_projection": True,\n    "mila_review_packet_schema": "essential-attention/mila-review-packet@1",\n    "external_effect_adapters": 0,',
        "static receipt fields",
    )
    STATIC_PATH.write_text(static, encoding="utf-8")


def patch_browser_test() -> None:
    browser = BROWSER_PATH.read_text(encoding="utf-8")
    browser = browser.replace("Essential Attention v1.2.0 · FAB Operating Desk", "Essential Attention v1.2.1 · FAB Operating Desk")
    browser = browser.replace("portable packet carries v1.2.0 build", "portable packet carries v1.2.1 build")
    browser = browser.replace('packet["build"]["version"] == "1.2.0"', 'packet["build"]["version"] == "1.2.1"')

    output_anchor = 'HTML = ROOT / "essential-attention" / "index.html"\n'
    browser = replace_once(
        browser,
        output_anchor,
        output_anchor
        + 'OUT = Path(os.environ.get("EA_BROWSER_OUT", "/tmp/essential-attention-v1.2.1-browser"))\n'
        + 'OUT.mkdir(parents=True, exist_ok=True)\n',
        "browser evidence directory",
    )

    reduced_anchor = '    reduced = browser.new_context(viewport={"width": 900, "height": 700}, reduced_motion="reduce").new_page()'
    mila_block = textwrap.dedent(
        r'''\
            page.screenshot(path=str(OUT / "operating-desk-mobile.png"), full_page=True)

            mila_context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            mila_page = mila_context.new_page()
            mila_errors: list[str] = []
            mila_console_errors: list[str] = []
            mila_page.on("pageerror", lambda error: mila_errors.append(str(error)))
            mila_page.on("console", lambda message: mila_console_errors.append(message.text) if message.type == "error" else None)
            if file_mode:
                mila_page.on(
                    "request",
                    lambda request: external_requests.append(request.url)
                    if not request.url.startswith(("data:", "blob:", "file:", "about:"))
                    else None,
                )
                direct_mila_url = HTML.as_uri() + "?projection=mila&browser-test=1"
                ordinary_url = HTML.as_uri() + "?browser-test=1"
            else:
                mila_page.on(
                    "request",
                    lambda request: external_requests.append(request.url)
                    if not request.url.startswith(origin + "/")
                    else None,
                )
                direct_mila_url = origin + "/essential-attention/?projection=mila&browser-test=1"
                ordinary_url = origin + "/essential-attention/?browser-test=1"

            mila_page.goto(direct_mila_url, wait_until="domcontentloaded")
            mila_page.wait_for_selector("#view-executive.active")
            check("Mila query route opens the decision projection", "mila-projection" in (mila_page.locator("body").get_attribute("class") or ""))
            check("Mila projection has a receiver-specific title", mila_page.title() == "Mila review · Essential Attention v1.2.1")
            check("Mila projection suppresses onboarding", not mila_page.locator("#helpDialog").evaluate("el => el.open"))
            check("Mila projection suppresses unrelated navigation", mila_page.locator('.seat-nav button:not([data-view="executive"])').evaluate_all("els => els.every(el => getComputedStyle(el).display === 'none')"))
            check("Mila projection shows three current queues", mila_page.locator("[data-mila-queue]").count() == 3)
            check("Mila projection preserves five decision cards", mila_page.locator(".decision-card").count() == 5)
            check("Mila projection exposes five explicit draft rows", mila_page.locator("[data-mila-draft]").count() == 5)
            check("Mila projection keeps silence unresolved", "silence remains unresolved" in mila_page.locator("#milaCommunicationState").inner_text().lower())
            mila_page.screenshot(path=str(OUT / "mila-review-desktop.png"), full_page=True)

            mila_page.locator("[data-decision]").first.click()
            check("Mila can draft one local disposition", mila_page.locator("#decisionDialog").evaluate("el => el.open"))
            mila_page.fill("#decisionDraftRationale", "Keep the meeting held until a named owner and evidence agenda exist.")
            mila_page.click('#decisionDraftForm button[type="submit"]')
            check("Mila draft ledger records one disposition", mila_page.locator(".mila-draft-row.is-drafted").count() == 1)
            with mila_page.expect_download() as mila_download:
                mila_page.click("#exportMilaPacketButton")
            mila_packet = json.loads(Path(mila_download.value.path()).read_text(encoding="utf-8"))
            check("Mila packet uses the dedicated schema", mila_packet["schema"] == "essential-attention/mila-review-packet@1")
            check("Mila packet carries the v1.2.1 build", mila_packet["release"] == "1.2.1" and mila_packet["build"]["version"] == "1.2.1")
            check("Mila packet carries all five decisions", len(mila_packet["decisions"]) == 5)
            check("Mila packet distinguishes one draft from four unresolved", mila_packet["decision_counts"]["local_drafts"] == 1 and mila_packet["decision_counts"]["unresolved"] == 4)
            check("Mila packet carries all three queues", set(mila_packet["queues"]) == {"authority_required", "accepted_obligations_at_risk", "evidence_ready_for_disposition"})
            check("Mila packet preserves unresolved recipient return", mila_packet["recipient_return_confirmation"]["status"] == "unresolved")
            check("Mila packet excludes participant and field records", mila_packet["privacy"]["participant_records"] == 0 and mila_packet["privacy"]["field_cases"] == 0)
            check("Mila packet excludes private source bytes", mila_packet["source_receipts"]["private_source_bytes_included"] is False and mila_packet["source_receipts"]["source_content_included"] is False and all(item["bytes_included"] is False for item in mila_packet["source_receipts"]["items"]))
            held_authority = ["institutional_acceptance", "participant_consent", "field_authority", "spend_authority", "assignment_authority", "calendar_authority", "payment_authority", "representation_authority", "publication_authority", "release_authority", "operator_acceptance"]
            check("Mila packet withholds every real-world authority", all(mila_packet["authority"][key] is False for key in held_authority) and mila_packet["authority"]["external_effect"] == "none")

            mila_page.reload(wait_until="domcontentloaded")
            mila_page.wait_for_selector("#view-executive.active")
            check("Mila direct route preserves the local draft", mila_page.locator(".mila-draft-row.is-drafted").count() == 1)
            mila_page.goto(ordinary_url, wait_until="domcontentloaded")
            mila_page.wait_for_selector("#view-overview.active")
            check("ordinary route remains unchanged", mila_page.title() == "Essential Attention v1.2.1 · FAB Operating Desk")
            check("direct Mila route did not consume first-use orientation", mila_page.locator("#helpDialog").evaluate("el => el.open"))
            mila_page.click("#helpCloseBottomButton")
            mila_page.goto(ordinary_url + "#mila", wait_until="domcontentloaded")
            mila_page.wait_for_selector("#view-executive.active")
            check("Mila hash alias opens the same projection", "mila-projection" in (mila_page.locator("body").get_attribute("class") or "") and not mila_page.locator("#helpDialog").evaluate("el => el.open"))

            mila_page.set_viewport_size({"width": 320, "height": 800})
            mila_page.evaluate("document.documentElement.style.fontSize='200%'")
            mila_page.wait_for_timeout(120)
            mila_geometry = mila_page.evaluate("""() => ({
              scrollWidth: document.documentElement.scrollWidth,
              clientWidth: document.documentElement.clientWidth,
              exportWidth: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().width,
              exportHeight: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().height
            })""")
            check("Mila projection remains bounded at 320px and 200 percent text", mila_geometry["scrollWidth"] <= mila_geometry["clientWidth"], json.dumps(mila_geometry))
            check("Mila export remains operable at narrow text zoom", mila_geometry["exportWidth"] > 0 and mila_geometry["exportHeight"] >= 44, json.dumps(mila_geometry))
            mila_page.screenshot(path=str(OUT / "mila-review-320-200pct.png"), full_page=True)
            check("Mila projection has zero JavaScript errors", len(mila_errors) == 0, json.dumps(mila_errors))
            check("Mila projection has zero console errors", len(mila_console_errors) == 0, json.dumps(mila_console_errors))
            mila_context.close()

        ''')
    browser = replace_once(browser, reduced_anchor, mila_block + reduced_anchor, "Mila browser qualification")

    final_anchor = '    browser.close()\n\nprint("\\nEssential Attention operating desk: all assertions passed")\n'
    final_block = textwrap.dedent(
        '''\
            result = {
                "schema": "essential-attention/browser-qualification@5",
                "release": "1.2.1",
                "ordinary_operating_desk": "PASS",
                "mila_query_projection": "PASS",
                "mila_hash_projection": "PASS",
                "mila_review_packet": "PASS",
                "mila_silence_invariant": "PASS_UNRESOLVED_WITHOUT_MOTIVE_INFERENCE",
                "private_source_bytes_in_mila_packet": 0,
                "participant_records": 0,
                "field_cases": 0,
                "external_effect": "none",
                "screenshots": ["operating-desk-mobile.png", "mila-review-desktop.png", "mila-review-320-200pct.png"],
            }
            (OUT / "browser-result.json").write_text(json.dumps(result, indent=2) + "\\n", encoding="utf-8")
            browser.close()

        print("\\nEssential Attention v1.2.1 operating desk and Mila return projection: all assertions passed")
        ''')
    browser = replace_once(browser, final_anchor, final_block, "browser result receipt")
    BROWSER_PATH.write_text(browser, encoding="utf-8")


def patch_permanent_workflow() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    marker = "      - name: Retain Essential Attention v1.2.1 browser evidence"
    if marker not in workflow:
        workflow += textwrap.dedent(
            """

                  - name: Retain Essential Attention v1.2.1 browser evidence
                    if: always()
                    uses: actions/upload-artifact@v4
                    with:
                      name: essential-attention-v1.2.1-${{ github.sha }}
                      path: |
                        /tmp/essential-attention-v1.2.1-browser
                        essential-attention/QUALIFICATION.json
                      if-no-files-found: error
                      retention-days: 30
            """
        )
    WORKFLOW_PATH.write_text(workflow, encoding="utf-8")


def main() -> None:
    patch_html()
    patch_readme()
    patch_static_test()
    patch_browser_test()
    patch_permanent_workflow()
    print("Essential Attention Mila return projection materialized")


if __name__ == "__main__":
    main()
