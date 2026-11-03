"""Render one self-contained, no-network decision-to-floor instrument."""
from pathlib import Path
import json

SHELL = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; font-src 'none'; form-action 'none'; base-uri 'none'">
<title>AXM / Decision Floor · Offline</title><style>
:root{--bg:#f2f5f4;--white:#fff;--ink:#1a2b33;--sub:#5d7277;--border:#dae5e1;--green:#176960;--mint:#e4f3ee;--red:#a13f36;--rosy:#fcf0ec;--amber:#a46422;--pale:#f8f9f5}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.48 system-ui,-apple-system,Segoe UI,Arial,sans-serif}h1,h2,h3,p{margin:0}button{font:inherit;cursor:pointer}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #4aada0;outline-offset:2px}.page{max-width:1360px;padding:25px 26px 65px;margin:auto}.top{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ccd8d4;padding:0 0 15px;gap:14px}.logo{font-weight:850;font-size:16px;letter-spacing:.1em}.logo span{color:var(--green)}.top small{text-transform:uppercase;letter-spacing:.075em;font-size:10px;color:var(--sub);text-align:right}.hero{padding:25px 0 19px;display:flex;align-items:end;justify-content:space-between;gap:20px}.kicker{font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:var(--green);font-weight:800}.hero h1{font-size:clamp(31px,4.4vw,54px);max-width:840px;line-height:1.05;letter-spacing:-.052em;margin:8px 0 13px}.hero p{color:var(--sub);font-size:14px;max-width:800px}.flag{display:inline-flex;gap:7px;align-items:center;padding:7px 10px;border-radius:9px;background:#fff9e9;border:1px solid #f2e4bf;color:#835922;font-size:10px;font-weight:750;margin-bottom:10px}.selector{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.selector label{font-size:11px;font-weight:800;color:var(--sub)}.selector select{max-width:310px;padding:9px;border:1px solid var(--border);border-radius:7px;background:white}.headerbar{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:13px}.meta{font-size:11px;color:var(--sub)}.headline{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.tile{padding:15px 16px;border:1px solid var(--border);border-radius:10px;background:white;min-height:130px}.tile .label{color:var(--sub);font-size:10px;letter-spacing:.075em;font-weight:800;text-transform:uppercase}.tile .value{font-size:28px;font-weight:820;letter-spacing:-.045em;margin:8px 0 5px;font-variant-numeric:tabular-nums}.tile .detail{font-size:11px;color:var(--sub)}.tile.red{background:var(--rosy);border-color:#efd7cd}.tile.red .value{color:var(--red)}.tilesub{margin:24px 0 11px;display:flex;align-items:baseline;justify-content:space-between;gap:10px}.tilesub h2{font-size:19px;letter-spacing:-.033em}.tilesub p{font-size:11px;color:var(--sub)}.two{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(290px,1fr);gap:12px}.panel{background:white;border:1px solid var(--border);border-radius:11px;overflow:hidden}.paneltop{padding:15px 17px;border-bottom:1px solid #e5ece9;background:#fafcfb;display:flex;justify-content:space-between;align-items:center;gap:10px}.paneltop h3{font-size:13px}.paneltop small{color:var(--sub);font-size:10px}.replay{padding:17px}.replay>input{width:100%;accent-color:var(--green);cursor:pointer}.replaytools{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-top:10px}.btns{display:flex;gap:7px}.btn{border:1px solid #cbdcd7;background:#fff;border-radius:7px;padding:7px 11px;font-weight:750;font-size:11px}.btn.primary{background:var(--green);border-color:var(--green);color:white}.asof{font-size:10px;color:var(--sub)}.stages{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:15px 17px;border-top:1px solid #e9efed}.step{border:1px solid #e4ebe8;border-radius:8px;padding:11px;min-height:106px;background:var(--pale)}.step strong{display:block;font-size:10px;color:var(--sub);text-transform:uppercase;letter-spacing:.04em}.step b{display:block;font-size:22px;letter-spacing:-.04em;margin:5px 0}.step span{font-size:10px;color:var(--sub)}.step.mismatch{background:var(--rosy);border-color:#f0dad4}.step.mismatch b{color:var(--red)}.eventlog{max-height:445px;overflow:auto;padding:0 16px 8px}.ev{display:grid;grid-template-columns:115px 1fr;gap:10px;padding:11px 0;border-bottom:1px solid #e9eeec}.ev.dim{opacity:.42}.ev time{font-size:10px;color:var(--sub);font-variant-numeric:tabular-nums}.ev h4{margin:0 0 5px;font-size:12px}.ev p{font-size:11px;color:var(--sub);line-height:1.45}.ref{font:9px ui-monospace,Consolas,monospace;color:var(--green);word-break:break-word}.status{padding:17px;background:#183b44;color:#f3f8f6;min-height:180px}.status h3{font-size:20px;line-height:1.2;margin:7px 0 10px;letter-spacing:-.025em}.status p{color:#c5ded8;line-height:1.5}.status .kicker{color:#8ed2bf}.keyfacts{padding:11px 17px}.factrow{display:flex;justify-content:space-between;gap:15px;padding:10px 0;border-bottom:1px solid #ebeeec}.factrow:last-child{border:0}.factrow span{font-size:11px;color:var(--sub)}.factrow strong{text-align:right;font-size:12px}.question{padding:14px 16px;border-bottom:1px solid #e6eeea}.question:last-child{border:0}.question .row{display:flex;justify-content:space-between;align-items:center;gap:9px}.question .tag{font-size:9px;letter-spacing:.02em;font-weight:750;text-transform:uppercase;background:#f3e9dd;color:#855e26;padding:4px 8px;border-radius:99px}.question h4{font-size:12px;line-height:1.45;margin:8px 0 5px}.question p{font-size:10px;color:var(--sub)}.question .evi{font:9px ui-monospace,Consolas,monospace;color:var(--green);margin-top:6px;overflow-wrap:anywhere}.tablewrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:820px}th,td{border-bottom:1px solid #e5ece8;padding:10px 13px;text-align:left;vertical-align:top;font-size:11px}th{background:#fafcfb;font-size:10px;color:var(--sub);text-transform:uppercase;letter-spacing:.045em}tr:last-child td{border:0}.doc{padding:11px 16px;border-bottom:1px solid #e8efec}.doc:last-child{border:0}.doc strong{display:block;font-size:11px}.doc p{font-size:11px;color:var(--sub);margin:4px 0}.footer{border-top:1px solid #d4ded9;margin-top:25px;padding-top:16px;color:var(--sub);display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;font-size:10px}.muted{color:var(--sub)}.wrapnote{padding:12px 15px;background:#f9faf9;border-top:1px solid #e6ece9;color:var(--sub);font-size:10px}.hidden{display:none!important}#error{color:var(--red)}@media(max-width:900px){.two{grid-template-columns:1fr}.headline{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.page{padding:15px 11px 35px}.hero{display:block}.headerbar{align-items:start}.headline,.stages{grid-template-columns:repeat(2,1fr)}.ev{grid-template-columns:92px 1fr}.tile .value{font-size:24px}}
</style></head><body><main class="page">
<header class="top"><div class="logo">AXM <span>/</span> DECISION FLOOR</div><small>Offline investigator · Evidence before narrative<br>Local synthetic qualification unless real exports supplied</small></header>
<section class="hero"><div><div class="flag">LOCAL-ONLY · NO NETWORK · VERIFIED SOURCE HASHES</div><div class="kicker">S&OP decision-to-reality instrument</div><h1>When the plan changed, did the floor?</h1><p>Every statement stays. Every system revision stays. The measure is elapsed time from approved intent to operational reality, with source receipts for each claimed transition.</p></div></section>
<div class="headerbar"><div class="selector"><label for="cases">Operational case</label><select id="cases"></select></div><div class="meta" id="summary"></div></div>
<div class="headline">
 <div class="tile"><div class="label">Before the decision · Plan</div><div class="value" id="before">—</div><div class="detail" id="beforeDetail">Historical source snapshot</div></div>
 <div class="tile"><div class="label">Approved target</div><div class="value" id="target">—</div><div class="detail" id="targetDetail">Authority-linked decision</div></div>
 <div class="tile red"><div class="label">Floor minus decision</div><div class="value" id="floorGap">—</div><div class="detail" id="floorDetail">Observed output, not a meeting claim</div></div>
 <div class="tile"><div class="label">Inventory above target · Book value</div><div class="value" id="exposure">—</div><div class="detail">Stock valuation is not a realized loss</div></div>
</div>
<div class="tilesub"><h2>Rewind the evidence</h2><p>Slide through time without erasing earlier commitments</p></div>
<div class="two"><section class="panel"><div class="paneltop"><h3>Decision-to-floor timeline</h3><small id="clock"></small></div><div class="replay"><input id="seek" type="range" min="0" value="0" aria-label="Replay events through selected point"><div class="replaytools"><div class="btns"><button class="btn" id="prev">Previous</button><button class="btn primary" id="next">Next event</button><button class="btn" id="all">Show all</button></div><div class="asof" id="asof"></div></div></div><div class="stages" id="stages"></div><div class="eventlog" id="eventlog"></div></section>
<aside><div class="panel"><div class="status"><div class="kicker">The operative question right now</div><h3 id="questionHeadline">Loading events</h3><p id="questionExplanation"></p></div><div class="paneltop"><h3>Measured lags</h3></div><div class="keyfacts" id="lagfacts"></div></div><div class="panel" style="margin-top:12px"><div class="paneltop"><h3>Open investigations</h3><small id="questionCount"></small></div><div id="questions"></div></div></aside></div>
<div class="tilesub"><h2>Keep the receipts</h2><p>Event time · system record time · immutable intake bytes</p></div>
<div class="panel"><div class="tablewrap"><table><thead><tr><th>Event</th><th>Occurs</th><th>Recorded</th><th>Value</th><th>System / authority</th><th>Original record / SHA-256 prefix</th></tr></thead><tbody id="receipts"></tbody></table></div><div class="wrapnote">Original source bytes are retained in the local vault. A source hash establishes that the archived bytes have not changed since intake. It does not establish that the source system, signer, or source clock was honest.</div></div>
<div class="tilesub"><h2>Cross-referenced source material</h2><p>Text references remain leads, never substituted for ERP or floor receipts</p></div>
<div class="two"><div class="panel"><div class="paneltop"><h3>Related documents and meeting language</h3></div><div id="documents"></div></div><div class="panel"><div class="paneltop"><h3>Coverage and ingestion issues</h3></div><div id="issues"></div></div></div>
<div class="footer"><div id="meta"></div><div>No outside scripts, fonts, requests, trackers, or APIs · Report opens with file://</div></div>
</main><script id="payload" type="application/json">__PAYLOAD__</script><script>
'use strict';
const D=JSON.parse(document.getElementById('payload').textContent);
const el=id=>document.getElementById(id);
const div=(s,cls)=>{let d=document.createElement('div');if(cls)d.className=cls;d.textContent=s;return d;};
const tx=(parent,tag,value,cls)=>{const e=document.createElement(tag);if(cls)e.className=cls;e.textContent=value;parent.append(e);return e;};
const fmt=v=>v===null||v===undefined?'unobserved':Number(v).toLocaleString('en-US',{maximumFractionDigits:2});
const u=v=>v===null||v===undefined?'—':(v>0?'+':'')+fmt(v);
const money=v=>v===null||v===undefined?'—':'$'+fmt(v);
const date=s=>s?s.replace('T',' ').replace('+00:00','Z').slice(0,16)+'Z':'unrecorded';
const evvalue=e=>e&&e.quantity!==null&&e.quantity!==undefined?fmt(e.quantity):'unobserved';
let caseIndex=0,position=0;
function clear(node){node.replaceChildren()}
function make(parent,cls,header,content){const d=div('',cls);tx(d,'strong',header);tx(d,'span',content);parent.append(d);return d}
function latest(events,kind){return events.filter(e=>e.kind===kind).slice(-1)[0]||null}
function currentCase(){return D.cases[caseIndex]}
function update(){
 const c=currentCase(); if(!c)return;
 const events=c.events,seen=events.slice(0,position),beforeDecision=events.filter(e=>e.kind==='plan' && e.occurred_at <= (c.facts.decision_time||'')),base=beforeDecision.slice(-1)[0];
 const decision=latest(seen,'decision');const target=decision?decision.quantity:null;
 const p=latest(seen,'plan'),co=latest(seen,'commitment'),fl=latest(seen,'floor');
 const inv=latest(seen,'outcome'),invTarget=latest(seen,'inventory_target'),unitCost=latest(seen,'unit_cost');
 const delta=target!==null&&fl?fl.quantity-target:null;
 el('before').textContent=fmt(base?base.quantity:c.facts.prior_plan);
 el('target').textContent=fmt(target);
 el('floorGap').textContent=u(delta);
 el('floorGap').parentElement.classList.toggle('red',delta!==null&&delta!==0);
 const excess=inv&&invTarget?Math.max(0,inv.quantity-invTarget.quantity):null;
 el('exposure').textContent=money(excess!==null&&unitCost?excess*unitCost.quantity:null);
 el('clock').textContent=`Event ${position} of ${events.length}`;
 el('asof').textContent=position?'Through '+date(seen[seen.length-1].occurred_at):'Before first source record';
 el('seek').max=events.length;el('seek').value=position;
 clear(el('stages'));
 const steps=[['1 · Said',target,'Approved target'],['2 · Planned',p?p.quantity:null,'ERP scheduling'],['3 · Committed',co?co.quantity:null,'Purchase order'],['4 · Done',fl?fl.quantity:null,'MES production']];
 for(const [name,qty,note] of steps){const mismatch=target!==null&&qty!==null&&qty!==target;const box=div('',mismatch?'step mismatch':'step');tx(box,'strong',name);tx(box,'b',fmt(qty));tx(box,'span',note);el('stages').append(box)}
 clear(el('eventlog'));
 for(const [i,e] of events.entries()){const d=div('',i>=position?'ev dim':'ev');const left=div('');tx(left,'time',date(e.occurred_at));const right=div('');tx(right,'h4',e.kind.toUpperCase()+' · '+(e.quantity===null?'statement':fmt(e.quantity)+(e.kind==='unit_cost'?' USD/unit':' units')));tx(right,'p',e.notes||e.system);tx(right,'div',e.evidence.ref,'ref');d.append(left,right);el('eventlog').append(d)}
 let headline,why;
 if(!decision){headline='What is the approved change?';why='An input revision or a statement does not establish the operative plan. Locate the authorized decision and preserve its prior state.'}
 else if(!p||p.occurred_at<=decision.occurred_at){headline='Did the ERP change?';why='The decision exists. The first post-decision planning snapshot is the next falsifiable observation.'}
 else if(p.quantity!==target){headline='Why is ERP still on the old plan?';why='A timestamped ERP snapshot contradicts the approved target. Identify the owner, control, and earliest feasible correction.'}
 else if(!co||co.occurred_at<=decision.occurred_at){headline='Did Procurement change its commitment?';why='ERP has converged. The PO commitment requires its own authoritative receipt.'}
 else if(co.quantity!==target){headline='Why did the purchase order not follow?';why='Procurement remained committed to a different number after the planning change. Find supplier cutoffs, authorization, and revision records.'}
 else if(!fl||fl.occurred_at<=decision.occurred_at){headline='Did the physical floor move?';why='The administrative systems agree. A MES or inventory measurement must establish physical execution.'}
 else if(fl.quantity!==target){headline='What produced the physical overshoot?';why='The observed production output differs from the decision. Reconstruct what actions were still feasible when the discrepancy became known.'}
 else{headline='Did the change hold through outcome?';why='The observed plan, commitment and floor now agree. Test final inventory, demand, and financial measures against the original objective.'}
 el('questionHeadline').textContent=headline;el('questionExplanation').textContent=why;
 clear(el('lagfacts'));
 const tracks=c.tracks||{};
 for(const [label,k] of [['ERP convergence','plan'],['PO convergence','commitment'],['Floor convergence','floor']]){
  const row=div('','factrow');tx(row,'span',label);tx(row,'strong',tracks[k]&&tracks[k].convergence_hours!==null?fmt(tracks[k].convergence_hours)+' hours':'not evidenced');el('lagfacts').append(row)
 }
 let row=div('','factrow');tx(row,'span','First recorded post-decision system state');tx(row,'strong',c.facts.first_observed_divergence_hours!==null&&c.facts.first_observed_divergence_hours!==undefined?fmt(c.facts.first_observed_divergence_hours)+' hours':'not evidenced');el('lagfacts').append(row);
 clear(el('questions'));el('questionCount').textContent=c.questions.length+' unresolved / investigate';
 if(!c.questions.length)el('questions').append(div('No presently generated investigation items. Coverage is not proof of correctness.','question'));
 for(const q of c.questions){const d=div('','question'),hdr=div('','row');tx(hdr,'strong',q.code);tx(hdr,'span',q.status,'tag');d.append(hdr);tx(d,'h4',q.question);tx(d,'p',(q.owner?'Owner: '+q.owner+' · ':'')+q.condition);if(q.evidence.length)tx(d,'div',q.evidence.map(x=>x.ref).join(' · '),'evi');el('questions').append(d)}
 clear(el('receipts'));
 for(const e of events){const tr=document.createElement('tr');for(const value of [e.kind+' / '+e.record_id,date(e.occurred_at),date(e.recorded_at),evvalue(e),e.system+(e.authority?' / '+e.authority:''),e.evidence.ref])tx(tr,'td',value);el('receipts').append(tr)}
 clear(el('documents'));
 if(!c.related_documents.length)el('documents').append(div('No text candidate mentions matched this case.','doc'));
 for(const doc of c.related_documents){const d=div('','doc');tx(d,'strong',doc.source);tx(d,'p',doc.snippet);tx(d,'div',doc.ref+' · candidate mention, not execution proof','ref');el('documents').append(d)}
}
function select(i){caseIndex=i;position=currentCase().events.length;update()}
for(const [i,c] of D.cases.entries()){const o=document.createElement('option');o.value=i;o.textContent=c.case_key;el('cases').append(o)}
el('cases').addEventListener('change',e=>select(Number(e.target.value)));
el('seek').addEventListener('input',e=>{position=Number(e.target.value);update()});
el('prev').addEventListener('click',()=>{position=Math.max(0,position-1);update()});
el('next').addEventListener('click',()=>{position=Math.min(currentCase().events.length,position+1);update()});
el('all').addEventListener('click',()=>{position=currentCase().events.length;update()});
el('summary').textContent=D.event_count+' normalized events · '+D.source_count+' immutable source versions';
clear(el('issues'));
if(!D.issues.length)el('issues').append(div('No ingestion issues reported. This does not establish complete data coverage.','doc'));
for(const x of D.issues){const d=div('','doc');tx(d,'strong',x.severity.toUpperCase()+' · '+x.code);tx(d,'p',x.detail);tx(d,'div',(x.original_name||'unknown source')+' · '+x.locator,'ref');el('issues').append(d)}
for(const x of (D.skipped_files||[])){const d=div('','doc');tx(d,'strong','NOT INGESTED · '+x.reason);tx(d,'p',x.path);el('issues').append(d)}
el('meta').textContent='As-of '+date(D.as_of)+' · Generated '+date(D.generated_at)+' · '+D.source_claim;
if(D.cases.length)select(0);else{el('questionHeadline').textContent='No normalized operational case yet';el('questionExplanation').textContent='Supply matching CSV/JSON/JSONL exports, review config/sources.json and rerun the offline importer. Raw text may already be searchable.'}
</script></body></html>'''


def render(report:dict,destination:Path):
    # Escaping '<' prevents user-supplied document content from closing the
    # inert application/json tag; all visible content uses textContent.
    payload=json.dumps(report,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(SHELL.replace('__PAYLOAD__',payload),encoding='utf-8')
