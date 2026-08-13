"use strict";

function statusPill(t){let c="warn";if(["controlled","restored","resolved"].includes(t.state))c="ok";if(t.breached)c="bad";return `<span class="pill ${c}">${t.state}</span>`;}
function renderRegistry(){
  const body=document.getElementById("registryBody");body.innerHTML="";
  for(const t of visibleThreats()){
    const tr=document.createElement("tr");tr.className="row-select"+(state.selected===t.id?" selected":"");tr.onclick=()=>{state.selected=t.id;render();};
    const margin=(t.actual==="decoy"||t.controlled)?"—":fmtMonth(threatMargin(t));
    tr.innerHTML=`<td><b>${t.id}</b></td><td>${t.lineage}</td><td>${t.observedStrategy||"unknown"}</td><td>${t.covered?'<span class="pill ok">covered</span>':'<span class="pill bad">holdout</span>'}</td><td>${statusPill(t)}</td><td>${pct(t.confidence)}</td><td>${t.finding.replaceAll("_"," ")}</td><td>${margin}</td>`;
    body.appendChild(tr);
  }
}
function renderRoles(){const box=document.getElementById("roleButtons");box.innerHTML="";Object.entries(ROLES).forEach(([id,r])=>{const b=document.createElement("button");b.className="role"+(state.role===id?" active":"");b.textContent=r.label;b.onclick=()=>{state.role=id;render();};box.appendChild(b);});}
function renderActions(){
  const t=state.selected?getThreat(state.selected):null;
  document.getElementById("seatNote").textContent=ROLES[state.role].note;
  document.getElementById("selectedCase").innerHTML=t?`<b>${t.id} · ${t.label}</b><p>Lineage ${t.lineage}. Observed class: ${t.observedStrategy||"unknown"}. Confidence ${pct(t.confidence)}. ${t.covered?"Inside":"Outside"} the declared baseline.</p>`:`<b>No registry object selected</b><p>Portfolio-level actions remain available to the facilitator and Evidence Cell.</p>`;
  const grid=document.getElementById("actionGrid");grid.innerHTML="";
  Object.entries(ACTIONS).filter(([,a])=>a.role===state.role).forEach(([id,a])=>{
    const target=targetRequired(id)?t:null;const err=canAct(state.role,id,target);const b=document.createElement("button");b.className="action"+(err?" locked":"");b.innerHTML=`<strong>${a.label}</strong><small>${a.desc}${a.duration?` · +${a.duration} month${a.duration>1?"s":""}`:""}${err?` · ${err}`:""}</small>`;b.onclick=()=>perform(state.role,target?.id||null,id);grid.appendChild(b);
  });
}
function renderResources(){
  const box=document.getElementById("resourceGrid");box.innerHTML="";Object.entries(state.resources).forEach(([r,v])=>{const cap=usableCapacity(r),use=v.used,ratio=clamp(use/Math.max(.1,cap*3),0,1);const d=document.createElement("div");d.className="resource"+(state.failedResource===r?" failed":"");d.innerHTML=`<div class="resource-head"><span>${r}</span><span>${cap.toFixed(1)} usable · ${use} actions</span></div><div class="bar"><i style="width:${ratio*100}%"></i></div>`;box.appendChild(d);});
}
function renderInjects(){
  const next=state.scenario.injects.find(i=>i.month>state.month);document.getElementById("injectBox").innerHTML=next?`<div class="inject"><strong>Next scheduled inject · M+${next.month}: ${next.title}</strong><small>${next.text}</small></div>`:`<div class="inject"><strong>No later scheduled inject</strong><small>Continue until the portfolio is controlled, held, or recertified.</small></div>`;
  document.getElementById("eventLog").innerHTML=state.log.slice().reverse().map(x=>`<div class="log-entry ${x.kind}"><span class="t">M+${x.month}</span> <b>${x.title}</b> · ${x.text}</div>`).join("");
}
function renderAuthority(){const box=document.getElementById("authorityMatrix");box.innerHTML="";Object.entries(ROLES).forEach(([,r])=>{const d=document.createElement("div");d.className="card";d.innerHTML=`<h3>${r.label}</h3><p>${r.note}</p>`;box.appendChild(d);});}
function receiptObject(){
  return {protocol:VERSION,schema:SCHEMA,scenario:{id:state.scenario.id,title:state.scenario.title},generated_at:nowIso(),final_month:state.month,gate:state.gate,known_holdouts:state.knownHoldouts,false_actions:state.falseActions,dissent:state.dissent,n_minus_one:{occurred:state.n1Occurred,resource:state.scenario.n1.resource,flex_activated:state.flex,passed:state.n1Passed},controls:{capacity_boost:state.capacityBoost,physical_latency_months:state.physicalLatency,signal_redundancy:state.signalRedundancy},threats:state.threats.map(t=>({id:t.id,lineage:t.lineage,actual_class:t.actual,covered:t.covered,state:t.state,confidence:t.confidence,finding:t.finding,controlled:t.controlled,restored:t.restored,breached:t.breached,restoration_due:t.restorationDue,restoration_at:t.restorationAt,history:t.history})),actions:state.actions,evidence_boundary:"Synthetic exercise result. Not an empirical estimate, legal finding, or institutional endorsement."};
}
async function renderReceipt(){const obj=receiptObject();obj.canonical_sha256=await sha256(stable(obj));document.getElementById("receiptBox").textContent=JSON.stringify(obj,null,2);return obj;}
function renderGate(){
  const g=state.gate,b=document.getElementById("gateBanner");b.className="gate "+(g.pass?"pass":(g.state==="fail"?"fail":"hold"));document.getElementById("gateState").textContent=g.state.replaceAll("_"," ");document.getElementById("gateReason").textContent=g.reason;document.getElementById("monthLabel").textContent=`M+${state.month}`;
  document.getElementById("marginMetric").textContent=fmtMonth(g.metrics?.margin??truthMinMargin());document.getElementById("riskMetric").textContent=pct(g.metrics?.risk??estimatedRisk(truthMinMargin()));document.getElementById("restoreMetric").textContent=pct(g.metrics?.restore??restorationRate());document.getElementById("n1Metric").textContent=!state.n1Occurred?"Pending":(state.n1Passed?"PASS":"FAIL");document.getElementById("holdoutMetric").textContent=String(state.knownHoldouts);document.getElementById("loadMetric").textContent=`${capacityLoad().toFixed(2)}x`;
}
function render(){renderGate();renderRoles();renderRegistry();renderActions();renderResources();renderInjects();renderAuthority();renderReceipt();}

async function exportReceipt(){const obj=await renderReceipt();const blob=new Blob([JSON.stringify(obj,null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`${state.scenario.id}_receipt.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
async function copyReceipt(){const obj=await renderReceipt();await navigator.clipboard.writeText(JSON.stringify(obj,null,2));log("Receipt copied","Canonical receipt copied to the clipboard.","good");render();}

function bind(){
  const sel=document.getElementById("scenarioSelect");Object.entries(SCENARIOS).forEach(([k,s])=>{const o=document.createElement("option");o.value=k;o.textContent=`${s.id} · ${s.title}`;sel.appendChild(o);});sel.onchange=()=>initScenario(sel.value);
  document.getElementById("resetBtn").onclick=()=>initScenario(state.scenarioKey);document.getElementById("referenceBtn").onclick=runReference;document.getElementById("redTeamBtn").onclick=runRedTeam;document.getElementById("exportBtn").onclick=exportReceipt;document.getElementById("copyBtn").onclick=copyReceipt;
  document.querySelectorAll(".tab").forEach(t=>t.onclick=()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".tabview").forEach(x=>x.classList.remove("active"));t.classList.add("active");document.getElementById(`tab-${t.dataset.tab}`).classList.add("active");});
}

window.BP_TEST={SCENARIOS,ACTIONS,ROLES,initScenario,getState:()=>clone(state),perform,runReference,runRedTeam,computeGate,receiptObject,sha256,stable};
bind();initScenario("qualified");
