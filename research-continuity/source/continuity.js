/* Research Continuity 1.0.0. MIT. Workflow around unchanged Cantos ResearchCore.
   No network, model calls, shell execution, or external authorization. */
(function(root){'use strict';
const C=root.ResearchCore||(typeof require!=='undefined'?require('./research-core.js'):null);
if(!C)throw Error('Pinned ResearchCore is required.');
const VERSION='2.0.0', CORE_SHA='6375c45ae35890250020ae24e3edfc18a9c9e3bc7f2fa92dd87e578e1d29f0a5';
const SOURCE_COMMIT='0c9594b4d0c302e5b6da41f32fb983256c0e1391';
const actor='Local operator', stamp=()=>new Date().toISOString();
const ref=r=>({id:r.id,revision:r.revision});
const rec=(id,kind,title,summary,data,deps=[],tier='synthetic',disposition='draft')=>({id,kind,title,summary,data,deps,tier,disposition});
const get=(w,id)=>C.latest(C.state(w),id);
const all=(w,prefix)=>Object.values(C.state(w).records).map(x=>x.at(-1)).filter(r=>r.id.startsWith(prefix));
function required(s,label,max=500){C.assert(typeof s==='string'&&s.trim()&&s.length<=max,label+' is required (up to '+max+' characters).');return s.trim();}
function syntheticRun(letter){
 const tasks=[];
 for(let i=1;i<=12;i++){
  const expected={invoice:'INV-'+String(i).padStart(3,'0'),amount:100+i};
  const raw=JSON.stringify(expected);let output=raw,status='ok',elapsed_ms=400+i*140;
  const attempts=[];
  if(letter==='A'){
   if(i>=6&&i<=10)output='```json\n'+raw+'\n```';
   if(i===11)output=JSON.stringify({...expected,amount:0});
   if(i===12){status='timeout';elapsed_ms=6500;output='';}
  }else{
   elapsed_ms=900+i*220;
   if(i===10)output=JSON.stringify({...expected,amount:0});
   if(i===11){attempts.push({status:'error',elapsed_ms:800,output:'upstream error',cost_usd:null});elapsed_ms=3900;}
   if(i===12)elapsed_ms=8000;
  }
  attempts.push({status,elapsed_ms,output,cost_usd:null});
  tasks.push({id:'task-'+i,expected,attempts});
 }
 return {schema:'second-run/task-run@1',run_id:'configuration-'+letter.toLowerCase(),label:'Configuration '+letter,evidence:'synthetic',pins:{taskset:'invoices-12-v1',contract:'invoice-fields-v1',load:'retained-attempts-v1',boundary:'original request through all retries'},tasks,billing:{actual_total_usd:null,quote_total_usd:letter==='A'?1.2:2.4,currency:'USD',scope:'Authored example: full quote for all original tasks, retries, late answers and failures. Not a bill or model benchmark.'}};
}
async function receipt(text,name,meta){
 required(name,'Filename',240);C.assert(typeof text==='string'&&text.length<=2000000,'Source must be text of at most 2 MB.');
 const parsed=C.parse(text);C.validateRun(parsed);
 const instrument=required(meta.instrument,'Instrument'),dataset_version=required(meta.dataset_version,'Dataset version',160);
 const command=required(meta.re_execution_cmd,'Re-execution command',2000), locator=required(meta.locator,'Source locator',1000);
 const hash=await C.hash(text);
 return {schema:'research-continuity/source-receipt@1',filename:name,media_type:'application/json',raw_text:text,sha256:hash,bytes:new TextEncoder().encode(text).length,instrument,dataset_version,locator,re_execution_cmd:command,observed_at:stamp(),cross_check:{status:'NOT_PERFORMED',method:'No independent source lookup supplied.'},gauge:{status:'BYTES_CHECKED',method:'SHA-256 over retained file bytes; not an independent source-truth check.',observed_sha256:hash},evidence:parsed.evidence};
}
async function create(){
 const w=C.empty('Research Continuity / purchase-order extraction');
 await C.put(w,rec('intent','claim','Which extraction procedure is worth reusing?','Choose the lowest full cost per accepted original invoice, while preserving failures, human review and the conditions supporting reuse.',{schema:'research-continuity/intent@1',measurand:'Accepted original tasks under exact-field and deadline checks',decision:'Recommend a configuration for a bounded follow-up; no purchase or deployment.',context:'Twelve fictional invoices. Both configurations retain every attempt. This is an exploratory demonstration, not a blinded experiment.'}),actor);
 await C.put(w,rec('method','claim','Pinned evaluator','Unchanged ResearchCore 1.0.0 performs grading, comparison, journal checks, review and frozen reports.',{procedure:'ResearchCore.compare / task-cost@1',implementation_version:'1.0.0',core_sha256:CORE_SHA,source_commit:SOURCE_COMMIT,runtime:'JavaScript / Web Crypto; exact host version belongs in a native run receipt.'}),actor);
 await C.put(w,rec('policy','policy','Acceptance contract','Exact fields, completion within 5 seconds, at least half of the twelve original tasks accepted.',{grader:'strict_json',deadline_ms:5000,quality_floor:.5,min_tasks:12,cost_basis:'quote',comparison_mode:'task'}),actor);
 for(const letter of ['A','B']){
  const text=JSON.stringify(syntheticRun(letter),null,2),key=letter.toLowerCase();
  const data=await receipt(text,'configuration-'+key+'.json',{instrument:'Authored fixture generator / Research Continuity 1.0.0',dataset_version:'invoices-12-v1',locator:'Bundled synthetic fixture',re_execution_cmd:'node scripts/check_packet.cjs packet.json --recompute'});
  const src=await C.put(w,rec('source-'+key,'source','Retained source '+letter,'Original response bytes, expected fields, timing and billing scope.',data,[],'synthetic','observed'),actor);
  await C.put(w,rec('run-'+key,'run','Configuration '+letter,'Parsed native task-run record. Source bytes remain attached.',C.parse(text),[ref(src)]),actor);
 }
 await C.put(w,rec('note-0','claim','Custody and proof boundary','Work remains on this device until you export it. Hashes identify a declared history; they do not authenticate its author, provide an external timestamp, or prove the source true.',{schema:'research-continuity/note@1',external_effects:false,lean_verifier:'NOT_CONNECTED',external_anchor:'NOT_VERIFIED',private_provider_material:false}),actor);
 return w;
}
async function changePolicy(w,patch){
 const next=C.clone(w),old=get(next,'policy'),allowed=['grader','deadline_ms','quality_floor','min_tasks','cost_basis'];
 C.assert(Object.keys(patch).every(k=>allowed.includes(k)),'Unsupported policy field.');
 const data={...old.data,...patch};C.validatePolicy(data);C.assert(C.canonical(data)!==C.canonical(old.data),'No policy change.');
 await C.put(next,{...old,data,summary:'Revised acceptance contract; prior outputs and reviews remain historical.'},actor);return next;
}
async function changeIntent(w,text){
 const next=C.clone(w),old=get(next,'intent');required(text,'Intent',2000);C.assert(text!==old.summary,'No intent change.');
 await C.put(next,{...old,summary:text,data:{...old.data,decision:text}},actor);return next;
}
async function changeMethod(w,version){
 required(version,'Procedure version',100);const next=C.clone(w),old=get(next,'method');C.assert(version!==old.data.implementation_version,'No method change.');
 await C.put(next,{...old,summary:'Declared procedure identity changed. The executable evaluator remains the pinned ResearchCore; this scenario changes its admitted applicability and prevents reuse under the old identity.',data:{...old.data,implementation_version:version,scenario_only:true}},actor);return next;
}
async function importRun(w,slot,text,name,meta){
 C.assert(['a','b'].includes(slot),'Choose source slot A or B.');
 const data=await receipt(text,name,meta),run=C.parse(text),tier=run.evidence==='synthetic'?'synthetic':'operator_supplied';
 const next=C.clone(w),src=await C.put(next,rec('source-'+slot,'source',name,'Admitted exact local bytes. Cross-source validation remains explicitly unperformed.',data,[],tier,'observed'),actor);
 await C.put(next,rec('run-'+slot,'run',run.label,'Native task record parsed from the admitted file, with all attempts retained.',run,[ref(src)],tier),actor);return next;
}
async function correctSource(w,slot){
 C.assert(['a','b'].includes(slot),'Choose source A or B.');const next=C.clone(w),old=get(next,'source-'+slot);
 await C.put(next,{...old,summary:'Source dataset version corrected. Dependent run has not yet been rebound.',data:{...old.data,dataset_version:old.data.dataset_version+'-corrected',observed_at:stamp()}},actor);return next;
}
async function acknowledgeSource(w,slot){
 const next=C.clone(w),src=get(next,'source-'+slot),r=get(next,'run-'+slot);
 C.assert(!C.dependencyState(C.state(next),r.id).current,'Source binding is already current.');
 C.assert(await C.hash(src.data.raw_text)===src.data.sha256,'Source bytes fail their recorded digest.');
 const data=C.parse(src.data.raw_text);C.validateRun(data);
 await C.put(next,{...r,data,deps:[ref(src)],summary:'Explicit operator readmission against corrected source metadata; no new model run or source-truth assertion.'},actor);return next;
}
async function gauge(w,slot){
 const next=C.clone(w),src=get(next,'source-'+slot);C.assert(src,'Source missing.');
 const digest=await C.hash(src.data.raw_text);C.assert(digest===src.data.sha256,'Retained source bytes were altered.');
 const id='gauge-'+String(next.events.length+1);
 await C.put(next,rec(id,'claim','Local byte gauge','Recomputed SHA-256 matches the retained bytes. Independent measurement and source truth remain unverified.',{schema:'research-continuity/gauge@1',source:ref(src),expected:src.data.sha256,observed:digest,status:'PASS'},[ref(src)],src.tier),actor);return next;
}
async function seal(w){
 const next=C.clone(w),s=C.state(next),ids=['intent','method','policy','run-a','run-b'];
 for(const id of ids)C.assert(C.dependencyState(s,id).current,'Resolve '+id+': '+C.dependencyState(s,id).blockers.join('; '));
 const records=ids.map(id=>C.latest(s,id)),manifest={scope:'Bounded evaluation over already-visible retained responses',inputs:records.map(r=>({id:r.id,revision:r.revision,data:r.data,summary:r.summary})),exploratory:true};
 const sha256=await C.hash(manifest);
 await C.put(next,rec('plan','claim','Sealed local evaluation plan','Pins the current intent, procedure, contract and source-bound runs before evaluation. Local ordering, not external pre-registration or output secrecy.',{schema:'research-continuity/plan@1',manifest,sha256,external_anchor:{status:'NOT_VERIFIED',locator:null},prior_exposure:'Retained responses are visible; exploratory replay.'},records.map(ref),records.some(r=>r.tier==='synthetic')?'synthetic':'operator_supplied'),actor);return next;
}
async function externalAnchor(w,locator,digest){
 required(locator,'Independent anchor locator',1000);C.assert(/^[0-9a-f]{64}$/.test(digest),'Anchor digest must be 64 lowercase hexadecimal characters.');
 const next=C.clone(w),p=get(next,'plan');C.assert(p,'Seal a plan first.');C.assert(digest===p.data.sha256,'Supplied anchor digest differs from the sealed plan.');
 await C.put(next,rec('anchor-'+next.events.length,'claim','External-anchor reference supplied','The user supplied a location and matching digest. No remote witness or timestamp was independently verified.',{schema:'research-continuity/anchor@1',locator,sha256:digest,status:'DECLARED_NOT_VERIFIED'},[ref(p)],'operator_supplied'),actor);return next;
}
async function keyFor(w){
 return C.hash({procedure:get(w,'method').data,policy:get(w,'policy').data,runs:['run-a','run-b'].map(id=>get(w,id).data)});
}
async function compute(w,forceFailure=false){
 const next=C.clone(w),s=C.state(next),plan=get(next,'plan'),n=all(next,'attempt-').length+1,id='attempt-'+n;
 let error=null;
 if(!plan)error='No sealed plan. Seal the current basis first.';
 else if(!C.dependencyState(s,'plan').current)error='Sealed plan is stale: '+C.dependencyState(s,'plan').blockers.join('; ');
 else if(forceFailure)error='Deliberately injected interruption before result commitment. The failed attempt is retained.';
 if(error){await C.put(next,rec(id,'claim','Attempt '+n+' held',error,{schema:'research-continuity/attempt@1',state:forceFailure?'FAILED':'HELD',mode:'not_executed',reason:error,model_calls:0,gpu_runs:0},[],plan?.tier||'proposal'),actor);return next;}
 const key=await keyFor(next),prior=all(next,'commit-').filter(r=>r.data.computation_key===key).at(-1);
 const pol=get(next,'policy'),runs=['run-a','run-b'].map(x=>get(next,x));
 const t=typeof performance!=='undefined'?performance.now():Date.now();
 let comparison;
 if(prior){
  const oldcalc=get(next,prior.data.calculation_id);
  C.assert(oldcalc,'Cached calculation missing.');
  C.assert(await C.hash(oldcalc.data)===prior.data.output_sha256,'Cached output checksum failed.');
  // Native put rechecks arithmetic against the exact pinned inputs below.
  comparison=C.clone(oldcalc.data);
 }else comparison={...C.compare(runs.map(r=>r.data),pol.data),selectedRecordIds:runs.map(r=>r.id),recipe:'task-cost@1'};
 const tier=runs.some(r=>r.tier==='synthetic')?'synthetic':'operator_supplied';
 const calc=await C.put(next,rec('calculation-'+n,'calculation','Evaluation '+n,'Recomputable accepted-work accounting over all retained original tasks.',comparison,[ref(pol),...runs.map(ref)],tier),'Pinned ResearchCore');
 const output_sha256=await C.hash(calc.data);
 const commit=await C.put(next,rec('commit-'+n,'claim','Output commitment '+n,'Output identity recorded before the UI reveals the outcome. Full packet bytes remain inspectable; no secrecy guarantee.',{schema:'research-continuity/commit@1',calculation_id:calc.id,computation_key:key,output_sha256,plan:ref(plan),mode:prior?'reused':'executed',reused_from:prior?.id||null},[ref(plan),ref(calc)],tier),'Local evaluator');
 const elapsed=(typeof performance!=='undefined'?performance.now():Date.now())-t;
 await C.put(next,rec(id,'claim','Attempt '+n+' committed','Completed local deterministic evaluation; no inference, purchase or deployment.',{schema:'research-continuity/attempt@1',state:'COMMITTED',mode:prior?'reused':'executed',commit_id:commit.id,elapsed_ms:elapsed,model_calls:0,gpu_runs:0},[ref(commit)],tier),'Local evaluator');return next;
}
async function reveal(w){
 const next=C.clone(w),attempt=all(next,'attempt-').at(-1);C.assert(attempt?.data.state==='COMMITTED','A committed result is required.');
 const commit=get(next,attempt.data.commit_id),calc=get(next,commit.data.calculation_id),s=C.state(next);
 C.assert(C.dependencyState(s,commit.id).current,'Committed result is stale; seal and run the current basis.');
 C.assert(await C.hash(calc.data)===commit.data.output_sha256,'Output identity mismatch.');
 const n=attempt.id.slice(8),id='decision-'+n;C.assert(!get(next,id),'This result is already revealed.');
 const winner=calc.data.results.find(r=>r.run_id===calc.data.winner);
 await C.put(next,rec(id,'conclusion','Decision candidate '+n,winner?winner.label+' has the lowest eligible full cost per accepted original task under this plan.':'No configuration qualifies under this plan.',{schema:'research-continuity/decision@1',winner:calc.data.winner,calculation_id:calc.id,commit_id:commit.id,attempt_id:attempt.id,limitations:[calc.data.scope,'Human review is separate. No deployment or underwriting authority.']},[ref(commit)],calc.tier),'Local evaluator');return next;
}
async function review(w,name,rationale){
 required(name,'Reviewer',160);required(rationale,'Review rationale',4000);C.assert(rationale.length>=12,'Explain the review in at least 12 characters.');
 const next=C.clone(w),decision=all(next,'decision-').at(-1);C.assert(decision,'Reveal a result first.');
 await C.review(next,decision.id,'accept',rationale,name);return next;
}
async function freeze(w){const next=C.clone(w),d=all(next,'decision-').at(-1);C.assert(d,'No revealed decision.');const s=C.state(next),rs=await C.reviewState(s,d.id);C.assert(!s.reports.some(r=>r.fingerprint===rs.fingerprint),'This exact edition is already frozen.');await C.freeze(next,d.id,rs.review?.reviewer||actor);return next;}
async function heatmap(w){
 const next=C.clone(w),runs=['run-a','run-b'].map(id=>get(next,id)),pol=get(next,'policy'),cells=[];
 for(const grader of ['strict_json','extract_json'])for(const deadline_ms of [1000,2500,5000,10000]){
  const p={...pol.data,grader,deadline_ms};const v=C.compare(runs.map(r=>r.data),p);
  cells.push({grader,deadline_ms,winner:v.winner,blockers:v.blockers,results:v.results.map(r=>({label:r.label,accepted:r.accepted,tasks:r.tasks,cost_per_success:r.cost_per_success,eligible:r.eligible}))});
 }
 const deps=[ref(pol),...runs.map(ref)];
 await C.put(next,rec('sensitivity-'+next.events.length,'claim','Sensitivity over retained responses','Eight actual evaluator calls over the same recorded responses. This is exploratory recomputation, not fresh model inference or a population probability estimate.',{schema:'research-continuity/sensitivity@1',cells,model_calls:0,gpu_runs:0},deps,runs.some(x=>x.tier==='synthetic')?'synthetic':'operator_supplied'),'Local sensitivity evaluator');return next;
}
async function proofArtifact(w,name,text){
 required(name,'Proof artifact name',200);C.assert(typeof text==='string'&&text.length<=1000000,'Proof artifact must be at most 1 MB of text.');
 const next=C.clone(w),digest=await C.hash(text);
 await C.put(next,rec('proof-'+next.events.length,'source',name,'Supplied proof artifact retained by byte identity. No Lean kernel or provider verifier has run here.',{schema:'research-continuity/proof-artifact@1',filename:name,raw_text:text,sha256:digest,checker_status:'NOT_RUN',theorem_scope:'UNESTABLISHED',assumptions:'UNESTABLISHED',authority:'NONE'},[],'operator_supplied','observed'),actor);return next;
}
async function view(w){
 const s=C.state(w),attempts=all(w,'attempt-'),commits=all(w,'commit-'),decisions=all(w,'decision-'),d=decisions.at(-1),plan=get(w,'plan'),calcs=all(w,'calculation-');
 const curr=d?C.dependencyState(s,d.id):{current:false,blockers:['No revealed result']};
 const latestCalc=d?get(w,d.data.calculation_id):null;
 const planBefore=plan?.data.manifest.inputs||[];
 const drift={intent:false,method:false,policy:false,sources:false};
 for(const r of planBefore){const now=get(w,r.id);if(!now||now.revision!==r.revision){if(r.id==='intent')drift.intent=true;else if(r.id==='method')drift.method=true;else if(r.id==='policy')drift.policy=true;else drift.sources=true;}}
 for(const id of ['run-a','run-b'])if(!C.dependencyState(s,id).current)drift.sources=true;
 const nativeCosts=latestCalc?.data.results||[];
 return {version:VERSION,workspace:w.label,events:w.events,records:s.records,reports:s.reports,attempts,commits,decisions,plan,policy:get(w,'policy'),intent:get(w,'intent'),method:get(w,'method'),sources:['a','b'].map(x=>({slot:x,record:get(w,'source-'+x),run:get(w,'run-'+x),current:C.dependencyState(s,'run-'+x)})),latestAttempt:attempts.at(-1)||null,decision:d||null,calculation:latestCalc,current:curr,review:d?await C.reviewState(s,d.id):null,drift,hash:(await C.pack(w)).sha256,sensitivity:all(w,'sensitivity-').at(-1)||null,proofs:all(w,'proof-'),anchors:all(w,'anchor-'),costs:nativeCosts,counts:{attempts:attempts.length,executed:attempts.filter(x=>x.data.mode==='executed').length,reused:attempts.filter(x=>x.data.mode==='reused').length,failed:attempts.filter(x=>['FAILED','HELD'].includes(x.data.state)).length,original_tasks:nativeCosts.reduce((n,r)=>n+r.tasks,0),accepted:nativeCosts.reduce((n,r)=>n+r.accepted,0),full_cost:nativeCosts.every(r=>r.total_usd!==null)?nativeCosts.reduce((n,r)=>n+r.total_usd,0):null}};
}
async function verify(packet){
 const w=await C.verifyPacket(packet),state=C.state(w);C.assert(get(w,'intent')?.data.schema==='research-continuity/intent@1','Not a Research Continuity workspace.');
 const records=Object.values(state.records).flat(),created=new Map();
 for(const e of w.events)if(e.type==='record')created.set(e.payload.id+'@'+e.payload.revision,e.seq);
 for(const source of records.filter(r=>r.data.schema==='research-continuity/source-receipt@1')){
  const r=source.data;required(r.instrument,'Instrument');required(r.dataset_version,'Dataset version');required(r.re_execution_cmd,'Re-execution command',2000);required(r.locator,'Source locator',1000);
  C.assert(typeof r.raw_text==='string'&&await C.hash(r.raw_text)===r.sha256,'Original source digest failed.');C.validateRun(C.parse(r.raw_text));
 }
 for(const slot of ['a','b'])C.assert(get(w,'source-'+slot)?.data.schema==='research-continuity/source-receipt@1','Missing source receipt.');
 for(const run of records.filter(r=>/^run-[ab]$/.test(r.id))){const d=run.deps[0],source=d&&C.version(state,d.id,d.revision);C.assert(source?.data.raw_text&&C.canonical(C.parse(source.data.raw_text))===C.canonical(run.data),'Parsed run differs from its pinned source bytes.');}
 for(const plan of state.records.plan||[]){
  C.assert(await C.hash(plan.data.manifest)===plan.data.sha256,'Plan digest failed.');
  const ids=['intent','method','policy','run-a','run-b'];C.assert(plan.deps.length===ids.length&&plan.data.manifest.inputs.length===ids.length,'Plan coverage mismatch.');
  for(const id of ids){const pin=plan.deps.find(x=>x.id===id),record=pin&&C.version(state,id,pin.revision),input=plan.data.manifest.inputs.find(x=>x.id===id);C.assert(record&&input&&input.revision===record.revision&&C.canonical(input.data)===C.canonical(record.data)&&input.summary===record.summary,'Plan manifest does not match its declared input: '+id);}
 }
 for(const commit of records.filter(r=>r.data.schema==='research-continuity/commit@1')){
  const calcPin=commit.deps.find(x=>x.id===commit.data.calculation_id),calc=calcPin&&C.version(state,calcPin.id,calcPin.revision),pp=commit.data.plan,plan=pp&&C.version(state,pp.id,pp.revision);
  C.assert(calc&&plan&&commit.deps.some(x=>x.id===pp.id&&x.revision===pp.revision),'Commit dependencies missing.');
  C.assert(await C.hash(calc.data)===commit.data.output_sha256,'Committed output digest failed.');
  const inputs=Object.fromEntries(plan.data.manifest.inputs.map(x=>[x.id,x]));
  const expectedKey=await C.hash({procedure:inputs.method.data,policy:inputs.policy.data,runs:[inputs['run-a'].data,inputs['run-b'].data]});
  C.assert(commit.data.computation_key===expectedKey,'Computation key does not match the sealed basis.');
  C.assert(C.canonical(calc.deps)===C.canonical(['policy','run-a','run-b'].map(id=>({id,revision:inputs[id].revision}))),'Calculation inputs differ from the sealed basis.');
  C.assert(created.get(plan.id+'@'+plan.revision)<created.get(calc.id+'@'+calc.revision)&&created.get(calc.id+'@'+calc.revision)<created.get(commit.id+'@'+commit.revision),'Local seal/compute/commit order failed.');
  C.assert(['executed','reused'].includes(commit.data.mode),'Unknown commitment mode.');
  if(commit.data.mode==='reused'){const old=C.latest(state,commit.data.reused_from);C.assert(old&&old.data.computation_key===expectedKey&&old.data.output_sha256===commit.data.output_sha256&&created.get(old.id+'@'+old.revision)<created.get(commit.id+'@'+commit.revision),'Reuse reference does not establish a prior matching result.');}
 }
 for(const d of records.filter(r=>r.data.schema==='research-continuity/decision@1')){
  const pin=d.deps[0],commit=pin&&C.version(state,pin.id,pin.revision),calc=commit&&C.latest(state,commit.data.calculation_id);
  C.assert(commit&&calc&&d.data.commit_id===commit.id&&d.data.calculation_id===calc.id&&d.data.winner===calc.data.winner,'Decision does not match its committed calculation.');
  C.assert(created.get(commit.id+'@'+commit.revision)<created.get(d.id+'@'+d.revision),'Result was revealed before its local commitment.');
 }
 for(const p of records.filter(r=>r.data.schema==='research-continuity/proof-artifact@1'))C.assert(p.data.checker_status==='NOT_RUN'&&await C.hash(p.data.raw_text)===p.data.sha256,'Supplied proof identity or unverified boundary changed.');
 if(root.RetainedJudgment)await root.RetainedJudgment.verify(w);
 else C.assert(!records.some(r=>r.data.schema==='research-continuity/retained-judgment@1'),'This packet needs the retained judgment consumer; no partial verification.');
 return w;
}
async function tamperCheck(w){const packet=await C.pack(w),copy=C.clone(packet);copy.workspace.events[0].payload.summary+=' changed';let rejected=false,reason='';try{await verify(copy);}catch(e){rejected=true;reason=e.message;}return {rejected,reason,original_unchanged:await C.hash(w)===packet.sha256};}
const api={VERSION,CORE_SHA,SOURCE_COMMIT,C,syntheticRun,create,receipt,changePolicy,changeIntent,changeMethod,importRun,correctSource,acknowledgeSource,gauge,seal,externalAnchor,keyFor,compute,reveal,review,freeze,heatmap,proofArtifact,view,verify,tamperCheck,pack:C.pack};
root.Continuity=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
