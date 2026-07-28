'use strict';
const STORAGE_KEY = 'axm-organ-evolution-workspace-v1';
const VIEWS = ['anatomy','evolution','actors','evidence','stress','decision'];
const DIMENSIONS = [
  ['function','Function continuity'],['authority','Authority integrity'],['reversibility','Reversibility'],
  ['dependency','Dependency reduction'],['adaptability','Adaptation capacity'],['observability','Observability'],
  ['succession','Succession'],['efficiency','Resource efficiency'],['userValue','Downstream value'],
  ['captureResistance','Capture resistance'],['containment','Failure containment'],['evidence','Evidence sufficiency']
];
const GATES = [['function','Function'],['authority','Authority'],['evidence','Evidence'],['migration','Migration'],['reversibility','Reversibility']];
const ACTIONS = ['retain','harden','specialize','generalize','split','merge','graft','replace_implementation','commoditize','replicate','federate','dormancy','sunset','restore','fork'];
const EVIDENCE_WEIGHT = {confirmed:1,measured:.95,reported:.72,derived:.58,judgment:.25,open:0};
const INDEPENDENCE_WEIGHT = {independent:1,mixed:.72,self:.38,unknown:.2};
const SEED = window.AXM_ORGAN_EVOLUTION_SEED;
let model = loadWorkspace();
let currentView = 'anatomy';
let selectedOrganId = model.decision?.organId || model.organs[0]?.id;
let selectedCandidateId = model.decision?.candidateId || model.candidates.find(c=>c.organId===selectedOrganId)?.id;
let stressResults = null;
let dialogMode = null;

function clone(v){return JSON.parse(JSON.stringify(v));}
function loadWorkspace(){
  try{
    const raw=localStorage.getItem(STORAGE_KEY);
    if(!raw)return clone(SEED);
    const parsed=JSON.parse(raw);
    return parsed?.format==='axm-organ-evolution/1'?parsed:clone(SEED);
  }catch{return clone(SEED);}
}
function persist(){
  try{localStorage.setItem(STORAGE_KEY,JSON.stringify(model));}catch{}
  renderTop();renderRail();
}
function esc(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function slug(v=''){return String(v).toLowerCase().replace(/[^a-z0-9]+/g,'.').replace(/^\.|\.$/g,'')||'record';}
function organ(id=selectedOrganId){return model.organs.find(o=>o.id===id);}
function candidate(id=selectedCandidateId){return model.candidates.find(c=>c.id===id);}
function actor(id){return model.actors.find(a=>a.id===id);}
function evidence(id){return model.evidence.find(e=>e.id===id);}
function candidateSet(organId=selectedOrganId){return model.candidates.filter(c=>c.organId===organId);}
function avg(values){const v=values.filter(Number.isFinite);return v.length?v.reduce((a,b)=>a+b,0)/v.length:0;}
function median(values){const v=[...values].sort((a,b)=>a-b);return v.length?(v.length%2?v[(v.length-1)/2]:(v[v.length/2-1]+v[v.length/2])/2):0;}
function cap(s){return String(s).replaceAll('_',' ').replace(/\b\w/g,m=>m.toUpperCase());}
function stageTone(o){const m=avg(Object.values(o.health||{}));return m>=4?'good':m>=2.8?'warn':'fail';}
function evidenceStrength(c){
  const rows=(c.evidenceIds||[]).map(evidence).filter(Boolean);
  const value=rows.length?avg(rows.map(e=>(EVIDENCE_WEIGHT[e.tier]??0)*(INDEPENDENCE_WEIGHT[e.independence]??.2))):0;
  const independent=rows.some(e=>e.independence==='independent'&&['confirmed','measured','reported'].includes(e.tier));
  return {value,rows,independent};
}
function posture(c){
  const g=Object.values(c.gates||{});
  if(g.includes('fail'))return {key:'fail',label:'Blocked'};
  if(g.includes('open'))return {key:'open',label:'Hold'};
  if(g.includes('warn'))return {key:'warn',label:'Pilot only'};
  return {key:'pass',label:'Admissible'};
}
function actorConcentration(c){
  const links=c.actorLinks||{};const roles=['sponsors','validators','deciders','beneficiaries'];
  const ids=[...new Set(roles.flatMap(r=>links[r]||[]))];
  return ids.map(id=>({id,roles:roles.filter(r=>(links[r]||[]).includes(id))})).sort((a,b)=>b.roles.length-a.roles.length);
}
function candidateFlags(c){
  const out=[];const ev=evidenceStrength(c);const p=posture(c);const concentration=actorConcentration(c);
  if(p.key==='fail')out.push({level:'high',title:'Hard gate failure',text:'This candidate is not decision-admissible until the failed function, authority, evidence, migration, or reversibility boundary is repaired.'});
  if(ev.rows.length<2||!ev.independent)out.push({level:'high',title:'Evidence dependence',text:'The candidate lacks at least two load-bearing records with one externally anchored or independent source.'});
  const top=concentration[0];
  if(top&&top.roles.length>=4)out.push({level:'high',title:'Authority and benefit concentration',text:`${actor(top.id)?.name||top.id} occupies sponsor, validator, decider, and beneficiary positions. The mechanism may still be valid, but independent validation and a separate decision authority are required.`});
  else if(top&&top.roles.includes('deciders')&&top.roles.includes('beneficiaries'))out.push({level:'medium',title:'Decision-benefit overlap',text:`${actor(top.id)?.name||top.id} both decides and benefits. Preserve the overlap and add an independent reviewer rather than inferring motive.`});
  if((c.dimensions?.containment??0)<=2)out.push({level:'high',title:'Blast-radius expansion',text:'The proposed transition enlarges the failure domain or centralizes functions that currently fail independently.'});
  if((c.dimensions?.reversibility??0)<=2)out.push({level:'medium',title:'Weak exit path',text:'The proposal has no cheap rip-out or rollback route. A pilot must preserve the current product and canonical data.'});
  if((c.dimensions?.authority??0)>=4&&(c.dimensions?.captureResistance??0)>=4&&p.key==='pass')out.push({level:'good',title:'Authority separation survives',text:'The candidate retains one accepted authority boundary and keeps suppliers, validators, and observers from silently acquiring it.'});
  if(!out.length)out.push({level:'good',title:'No structural capture flag',text:'No current rule identifies a concentration, evidence, or blast-radius defect. This is a bounded structural result, not proof that the proposal is correct.'});
  return out;
}
function constraints(){return model.estate.constraints||[];}
function renderTop(){
  const admissible=model.candidates.filter(c=>posture(c).key==='pass').length;
  const blocked=model.candidates.filter(c=>posture(c).key==='fail').length;
  const critical=model.organs.flatMap(o=>o.dependencies||[]).filter(d=>d.criticality>=4&&d.replaceability<=1).length;
  document.getElementById('topStats').innerHTML=[
    ['organs',model.organs.length],['candidates',model.candidates.length],['admissible',admissible],['blocked',blocked],['single-source seams',critical]
  ].map(([k,v])=>`<div class="statpill"><strong>${v}</strong> ${k}</div>`).join('');
}
function renderRail(){
  document.getElementById('estateName').textContent=model.estate.name;
  document.getElementById('estatePurpose').textContent=model.estate.purpose;
  const q=document.getElementById('organSearch').value.trim().toLowerCase();
  document.getElementById('organList').innerHTML=model.organs.filter(o=>!q||[o.name,o.class,o.stage,o.mission].join(' ').toLowerCase().includes(q)).map(o=>`
    <button class="organ-button ${o.id===selectedOrganId?'active':''}" data-organ="${esc(o.id)}">
      <i class="pulse ${stageTone(o)==='warn'?'warn':stageTone(o)==='fail'?'fail':''}"></i>
      <span><b>${esc(o.name)}</b><span>${esc(o.class)} · ${esc(o.stage)}</span></span>
      <code>${candidateSet(o.id).length}</code>
    </button>`).join('')||'<div class="empty">No organs match this filter.</div>';
}
function render(){
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.view===currentView));
  const fn={anatomy:renderAnatomy,evolution:renderEvolution,actors:renderActors,evidence:renderEvidence,stress:renderStress,decision:renderDecision}[currentView];
  document.getElementById('workspace').innerHTML=fn();
  persist();
}
function renderHero(o){
  const m=avg(Object.values(o.health||{}));const essential=(o.functions||[]).filter(f=>f.criticality>=4);const open=essential.filter(f=>f.coverage<4).length;
  const concentration=(o.dependencies||[]).filter(d=>d.criticality>=4&&d.replaceability<=1).length;
  return `<section class="hero">
    <div class="hero-card"><div class="kicker">${esc(o.class)} organ · ${esc(o.stage)}</div><h1>${esc(o.name)}</h1><p class="lead">${esc(o.mission)}</p><div class="tagrow">${(o.pressures||[]).map(p=>`<span class="tag gold">${esc(p)}</span>`).join('')}</div><div class="control-line"><button class="btn primary" data-view-jump="evolution">Evaluate evolution</button><button class="btn" data-edit-organ="${esc(o.id)}">Edit organ</button></div></div>
    <div class="hero-card"><div class="metric-grid">
      <div class="metric ${m>=4?'good':m>=3?'warn':'bad'}"><strong>${m.toFixed(1)}</strong><span>median health envelope</span></div>
      <div class="metric ${open===0?'good':open<2?'warn':'bad'}"><strong>${open}</strong><span>critical function gaps</span></div>
      <div class="metric ${concentration===0?'good':concentration<2?'warn':'bad'}"><strong>${concentration}</strong><span>single-source seams</span></div>
      <div class="metric"><strong>${candidateSet(o.id).length}</strong><span>evolution candidates</span></div>
    </div></div>
  </section>`;
}
