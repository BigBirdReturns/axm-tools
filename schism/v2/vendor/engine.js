/* AXM Industrial Continuity: bounded planning, correction and independent replay.
   No device controls, external calls, authenticated identity or production authority. */
(function(root){
'use strict';
const C=typeof module!=='undefined'&&module.exports?require('./commons-core.js'):{canonical,sha};
const clone=x=>JSON.parse(JSON.stringify(x));
const digest=x=>C.sha(C.canonical(x));
const VERSION='axm-industrial-continuity/0.1.0';
const RECIPE='two-product-two-stage-integer-planning/1';
const IDS=['orders','routing','capacity','maintenance','quality','procedure'];
const HEADERS={orders:['sku','demand_units','contribution_usd_per_unit'],routing:['sku','mix_min_per_unit','pack_min_per_unit'],capacity:['stage','available_min'],maintenance:['job','part','serviceable','allocated','recovery_mix_min','repair_cost_usd','expedite_cost_usd','supplier_lead_hours','decision_window_hours'],quality:['sku','released'],procedure:['procedure','revision','planning_allowed','review_role']};
const LABELS={orders:'ERP / customer demand',routing:'MES / product routing',capacity:'MES / available capacity',maintenance:'CMMS / parts and recovery',quality:'QMS / product release',procedure:'SOP / planning review'};
const FIXTURES={
orders:'sku,demand_units,contribution_usd_per_unit\nA,80,55.00\nB,60,40.00\n',
routing:'sku,mix_min_per_unit,pack_min_per_unit\nA,2,1\nB,1,2\n',
capacity:'stage,available_min\nmix,160\npack,150\n',
maintenance:'job,part,serviceable,allocated,recovery_mix_min,repair_cost_usd,expedite_cost_usd,supplier_lead_hours,decision_window_hours\nWO-101,SEAL-17,2,1,80,150.00,200.00,7,4\n',
quality:'sku,released\nA,1\nB,1\n',
procedure:'procedure,revision,planning_allowed,review_role\nPlanning-review,3,1,shift-planner\n'};
const req=(ok,msg)=>{if(!ok)throw Error(msg);};
const hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const exact=(o,ks)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join('|')===ks.slice().sort().join('|');
function csv(id,raw){
 req(IDS.includes(id)&&typeof raw==='string'&&raw.length<=32768,'Unknown source or oversized CSV.');
 req(!/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(raw),'Control characters are not accepted.');
 const lines=raw.replace(/\r\n/g,'\n').trimEnd().split('\n');
 req(lines.length>=2&&lines.length<=20,'Expected a header and bounded data rows.');
 req(lines[0].split(',').join('|')===HEADERS[id].join('|'),'CSV headers do not match the declared '+id+' mapping.');
 const rows=lines.slice(1).map(line=>{const vals=line.split(',');req(vals.length===HEADERS[id].length,'Quoted/extra CSV fields are outside this bounded mapping.');const o={};HEADERS[id].forEach((k,i)=>o[k]=vals[i].trim());return o;});
 req(rows.length===(['maintenance','procedure'].includes(id)?1:2),'This recipe expects two products, two stages and one maintenance/review record.');
 if(['orders','routing','quality'].includes(id))req(rows.map(r=>r.sku).sort().join('|')==='A|B','This pinned example accepts unique products A and B.');
 if(id==='capacity')req(rows.map(r=>r.stage).sort().join('|')==='mix|pack','Expected unique mix and pack stages.');
 return rows;
}
function numeric(v,name,issues,{max=1000000,min=0,integer=true,money=false}={}){
 if(v===''){issues.push(name+': missing');return null;}
 const pattern=money?/^(0|[1-9]\d*)(\.\d{1,2})?$/:integer?/^(0|[1-9]\d*)$/:/^(0|[1-9]\d*)(\.\d+)?$/;
 if(typeof v!=='string'||!pattern.test(v)){issues.push(name+': invalid');return null;}
 let n=Number(v);if(!Number.isFinite(n)||n<min||n>max){issues.push(name+': outside declared range');return null;}
 if(money){const [whole,frac='']=v.split('.');n=Number(whole)*100+Number((frac+'00').slice(0,2));}
 return n;
}
function inputFrom(records){
 const issues=[],by={};
 for(const id of IDS){const rec=records.find(r=>r.source===id);if(!rec){issues.push(id+': missing source');continue;}try{by[id]=csv(id,rec.raw);}catch(e){issues.push(id+': '+e.message);}}
 if(issues.length)return {issues};
 const products=['A','B'].map(id=>{const o=by.orders.find(r=>r.sku===id),r=by.routing.find(r=>r.sku===id),q=by.quality.find(r=>r.sku===id);return {sku:id,demand:numeric(o.demand_units,id+' demand',issues,{max:500}),margin:numeric(o.contribution_usd_per_unit,id+' contribution',issues,{money:true,max:100000}),mix:numeric(r.mix_min_per_unit,id+' mix minutes',issues,{min:1,max:1000}),pack:numeric(r.pack_min_per_unit,id+' pack minutes',issues,{min:1,max:1000}),released:numeric(q.released,id+' quality release',issues,{max:1})};});
 const capacity={};for(const r of by.capacity)capacity[r.stage]=numeric(r.available_min,r.stage+' capacity',issues,{max:1000000});
 const m=by.maintenance[0],p=by.procedure[0];
 const maintenance={job:m.job,part:m.part,serviceable:numeric(m.serviceable,'serviceable parts',issues,{max:10000}),allocated:numeric(m.allocated,'allocated parts',issues,{max:10000}),recovery:numeric(m.recovery_mix_min,'recovery minutes',issues),cost:numeric(m.repair_cost_usd,'repair cost',issues,{money:true}),expedite:numeric(m.expedite_cost_usd,'expedite cost',issues,{money:true}),lead:numeric(m.supplier_lead_hours,'supplier lead hours',issues,{max:8760}),window:numeric(m.decision_window_hours,'decision window hours',issues,{max:168})};
 if(maintenance.allocated!==null&&maintenance.serviceable!==null&&maintenance.allocated>maintenance.serviceable)issues.push('Allocated parts exceed serviceable parts.');
 if(!/^[A-Za-z0-9_.-]{1,64}$/.test(m.job)||!/^[A-Za-z0-9_.-]{1,64}$/.test(m.part))issues.push('Maintenance identifiers invalid.');
 const procedure={id:p.procedure,revision:numeric(p.revision,'procedure revision',issues,{min:1,max:9999}),allowed:numeric(p.planning_allowed,'procedure planning scope',issues,{max:1}),role:p.review_role};
 if(!/^[A-Za-z0-9_.-]{1,64}$/.test(p.procedure)||!/^[A-Za-z0-9_.-]{1,64}$/.test(p.review_role))issues.push('Procedure/role labels invalid.');
 return {issues,products,capacity,maintenance,procedure};
}
function solve(products,capacity,cost){
 let best=null;
 for(let a=0;a<=(products[0].released?products[0].demand:0);a++)for(let b=0;b<=(products[1].released?products[1].demand:0);b++){
  const mix=a*products[0].mix+b*products[1].mix,pack=a*products[0].pack+b*products[1].pack;if(mix>capacity.mix||pack>capacity.pack)continue;
  const gross=a*products[0].margin+b*products[1].margin,net=gross-cost;
  if(!best||net>best.net_cents||(net===best.net_cents&&a+b>best.units))best={a,b,units:a+b,gross_cents:gross,cost_cents:cost,net_cents:net,used:{mix,pack},available:clone(capacity),slack:{mix:capacity.mix-mix,pack:capacity.pack-pack}};
 }
 return best;
}
function calculate(records){
 const input=inputFrom(records),base={recipe:RECIPE,scope:'Record-based planning only',operational_authority:false,external_effects:false};
 if(input.issues.length)return {...base,status:'INCONCLUSIVE',issues:input.issues};
 const {products,capacity,maintenance:m,procedure:p}=input;
 const options=[{id:'existing-capacity',label:'Use existing capacity',eligible:true,cost:0,recovery:0,reason:'Plan inside the current two-stage envelope.'},
 {id:'planned-recovery',label:'Recover mixing capacity',eligible:!!p.allowed&&m.serviceable-m.allocated>=1,cost:m.cost,recovery:m.recovery,reason:!p.allowed?'Procedure is outside planning scope.':m.serviceable-m.allocated<1?'No unallocated serviceable part on record.':'One part available; recovery remains a planning assumption.'},
 {id:'expedited-recovery',label:'Expedite a replacement part',eligible:!!p.allowed&&m.lead<=m.window,cost:m.cost+m.expedite,recovery:m.recovery,reason:!p.allowed?'Procedure is outside planning scope.':m.lead>m.window?'Supplier arrival falls after the decision window.':'Arrival fits the declared window; supplier performance is unverified.'}];
 const candidates=options.map(o=>({...o,plan:o.eligible?solve(products,{mix:capacity.mix+o.recovery,pack:capacity.pack},o.cost):null}));
 const eligible=candidates.filter(o=>o.eligible);eligible.sort((a,b)=>b.plan.net_cents-a.plan.net_cents||a.cost-b.cost||a.id.localeCompare(b.id));
 const chosen=eligible[0],baseline=candidates[0].plan;
 const mixSlack=chosen.plan.slack.mix,packSlack=chosen.plan.slack.pack;
 const demandMet=products.every((p,i)=>(i===0?chosen.plan.a:chosen.plan.b)>=(p.released?p.demand:0));
 const limiting=demandMet?'released demand':mixSlack===0&&packSlack===0?'mix + pack':mixSlack===0?'mix':packSlack===0?'pack':'integer product mix';
 return {...base,status:'COMPUTED',input,chosen:chosen.id,plan:chosen.plan,candidates,baseline_net_cents:baseline.net_cents,incremental_net_cents:chosen.plan.net_cents-baseline.net_cents,limiting,review_role:p.role,explanation:chosen.id==='existing-capacity'?'The released order mix is best served within the existing capacity envelope. Extra asset capacity does not improve this objective after cost.':'The declared recovery increases planned contribution after intervention cost. Physical recovery and customer outcomes remain unobserved.'};
}
async function makeSource(id,raw,previous=null,kind='synthetic-fixture',observed='2026-11-16T16:00:00-08:00'){
 csv(id,raw);req(['synthetic-fixture','operator-supplied-unverified'].includes(kind),'Unknown evidence class.');req(Number.isFinite(Date.parse(observed)),'Observation time required.');
 const body={schema:'axm-process-source/1',source:id,revision:previous?previous.revision+1:1,previous:previous?previous.sha256:null,evidence_class:kind,observed_at:observed,raw};return {...body,sha256:await digest(body)};
}
async function verifySource(s){
 req(exact(s,['schema','source','revision','previous','evidence_class','observed_at','raw','sha256'])&&s.schema==='axm-process-source/1','Invalid source schema.');
 req(Number.isInteger(s.revision)&&s.revision>=1&&s.revision<=200,'Invalid source revision.');req(s.previous===null||hex(s.previous),'Invalid predecessor.');
 req(['synthetic-fixture','operator-supplied-unverified'].includes(s.evidence_class)&&Number.isFinite(Date.parse(s.observed_at)),'Invalid evidence class/time.');csv(s.source,s.raw);
 const {sha256,...body}=s;req(sha256===await digest(body),'Changed source bytes or metadata: '+s.source);return s;
}
function latest(state){const by={};for(const s of state.sources)by[s.source]=s;return IDS.map(id=>by[id]).filter(Boolean);}
function frontier(state){return latest(state).map(s=>s.sha256);}
function current(state,d=state.decisions.at(-1)){return !!d&&C.canonical(frontier(state))===C.canonical(d.frontier);}
async function start(engine){req(hex(engine),'Pinned engine digest required.');const sources=[];for(const id of IDS)sources.push(await makeSource(id,FIXTURES[id]));return {schema:VERSION,engine,recipe:RECIPE,sources,decisions:[],reviews:[]};}
async function change(state,id,raw,{kind='synthetic-fixture',observed='2026-11-16T16:10:00-08:00'}={}){
 req(state.sources.length<200,'Source history limit reached.');const previous=latest(state).find(s=>s.source===id);req(previous,'Source not present.');req(Date.parse(observed)>=Date.parse(previous.observed_at),'A successor cannot predate its predecessor.');
 const s=await makeSource(id,raw,previous,kind,observed);if(raw===previous.raw&&kind===previous.evidence_class)return clone(state);const n=clone(state);n.sources.push(s);return n;
}
async function evaluate(state){
 req(state.decisions.length<64,'Decision history limit reached.');const result=calculate(latest(state)),body={schema:'axm-process-decision/1',sequence:state.decisions.length+1,engine:state.engine,frontier:frontier(state),result};const d={...body,sha256:await digest(body)};const n=clone(state);n.decisions.push(d);return n;
}
async function review(state,reviewer,role){
 const d=state.decisions.at(-1);req(current(state,d)&&d.result.status==='COMPUTED','Re-evaluate complete current evidence before recording a review.');req(typeof reviewer==='string'&&reviewer.trim().length>=2&&reviewer.length<=80,'Reviewer label required.');req(role===d.result.review_role,'Review role does not match the source procedure.');req(state.reviews.length<64,'Review history limit reached.');
 const body={schema:'axm-process-review/1',decision:d.sha256,reviewer:reviewer.trim(),role,identity_status:'unverified-label',operational_authority:false};const n=clone(state);n.reviews.push({...body,sha256:await digest(body)});return n;
}
function reviewStatus(state){const r=state.reviews.at(-1),d=state.decisions.at(-1);return !r?'UNREVIEWED':current(state,d)&&r.decision===d.sha256?'RECORDED_LABEL_ONLY':'STALE';}
async function seal(state){const body=clone(state);return {...body,sha256:await digest(body)};}
async function restore(packet,expectedEngine){
 req(exact(packet,['schema','engine','recipe','sources','decisions','reviews','sha256'])&&packet.schema===VERSION&&packet.recipe===RECIPE,'Unknown handoff schema/recipe.');req(packet.engine===expectedEngine&&hex(expectedEngine),'Different engine: explicit migration and requalification required.');
 req(Array.isArray(packet.sources)&&packet.sources.length>=6&&packet.sources.length<=200&&Array.isArray(packet.decisions)&&packet.decisions.length<=64&&Array.isArray(packet.reviews)&&packet.reviews.length<=64,'Invalid or oversized handoff.');
 const {sha256,...state}=packet;req(sha256===await digest(state),'Handoff digest mismatch.');const by={},seen=new Map(),prefixes=[];
 for(const s of state.sources){await verifySource(s);const prev=by[s.source];req(!seen.has(s.sha256),'Duplicate source receipt.');req(prev?s.previous===prev.sha256&&s.revision===prev.revision+1:s.previous===null&&s.revision===1,'Orphan or forked source revision.');if(prev)req(Date.parse(s.observed_at)>=Date.parse(prev.observed_at),'Successor observation predates predecessor.');by[s.source]=s;seen.set(s.sha256,s);prefixes.push(IDS.map(id=>by[id]?.sha256).filter(Boolean));}
 req(IDS.every(id=>by[id]),'Missing source family.');let lastPrefix=-1;const decisions=new Map();
 for(let i=0;i<state.decisions.length;i++){
  const d=state.decisions[i];req(exact(d,['schema','sequence','engine','frontier','result','sha256'])&&d.schema==='axm-process-decision/1'&&d.sequence===i+1&&d.engine===expectedEngine,'Decision contract mismatch.');
  req(Array.isArray(d.frontier)&&d.frontier.length===6&&new Set(d.frontier).size===6,'Incomplete or duplicate decision frontier.');
  const pi=prefixes.findIndex(f=>C.canonical(f)===C.canonical(d.frontier));req(pi>=lastPrefix&&pi>=0,'Decision uses an impossible or regressing source frontier.');lastPrefix=pi;
  const records=d.frontier.map(h=>{req(seen.has(h),'Missing decision dependency.');return seen.get(h);});const rebuilt=calculate(records);req(C.canonical(rebuilt)===C.canonical(d.result),'Saved conclusion differs from independent recomputation.');const {sha256:dh,...db}=d;req(dh===await digest(db),'Decision digest mismatch.');decisions.set(dh,d);
 }
 for(const r of state.reviews){req(exact(r,['schema','decision','reviewer','role','identity_status','operational_authority','sha256'])&&r.schema==='axm-process-review/1','Invalid review contract.');const d=decisions.get(r.decision);req(d&&d.result.status==='COMPUTED'&&r.role===d.result.review_role&&r.identity_status==='unverified-label'&&r.operational_authority===false&&typeof r.reviewer==='string'&&r.reviewer.trim().length>=2&&r.reviewer.length<=80,'Invalid review scope or invented authority.');const {sha256:rh,...rb}=r;req(rh===await digest(rb),'Review digest mismatch.');}
 return clone(state);
}
async function scenario(state,id){
 const now='2026-11-16T16:20:00-08:00';
 if(id==='customer-mix')return change(state,'orders',FIXTURES.orders.replace('B,60,40.00','B,60,120.00'),{observed:now});
 if(id==='parts-allocation')return change(state,'maintenance',FIXTURES.maintenance.replace('SEAL-17,2,1,','SEAL-17,2,2,'),{observed:now});
 if(id==='quality-hold')return change(state,'quality',FIXTURES.quality.replace('A,1','A,0'),{observed:now});
 if(id==='missing-evidence')return change(state,'capacity',FIXTURES.capacity.replace('pack,150','pack,'),{observed:now});
 throw Error('Unknown correction.');
}
const api={VERSION,RECIPE,IDS,HEADERS,LABELS,FIXTURES,clone,digest,csv,calculate,start,change,evaluate,review,reviewStatus,seal,restore,latest,frontier,current,scenario};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.IndustrialContinuity=api;
})(globalThis);
