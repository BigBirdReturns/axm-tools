/* Independent AXM application proof. No network or device effects. */
(function(root){
'use strict';
const TC=typeof module!=='undefined'&&module.exports?require('./commons-core.js'):{canonical,sha,compose,makePacket,verifyPacket,fragments,makeWorkspace,verifyWorkspace,exerciseTests};
const clone=x=>JSON.parse(JSON.stringify(x));
const hash=x=>TC.sha(TC.canonical(x));
const VERSION='axm-i3x-proof/0.1.0';
const REQUIRED=['info','namespaces','objecttypes','relationshiptypes','objects','related','value','history'];
const req=(ok,msg)=>{if(!ok)throw Error(msg);};
async function inspectCapture(c){
 req(c&&c.schema==='axm-i3x-capture/1'&&c.remote_writes===false,'Unsupported read-only capture');
 req(['public-demo-api-capture','operator-provided-read-only-capture'].includes(c.evidence_class),'Unknown evidence class');
 req(Array.isArray(c.records)&&c.records.length<=32,'Invalid capture record count');
 req(typeof c.base_url==='string'&&/^https?:\/\//.test(c.base_url),'Invalid endpoint');
 const by={};
 for(const r of c.records){
  req(REQUIRED.includes(r.id)&&!by[r.id],'Unknown or duplicate capture record');
  req(['GET','POST'].includes(r.method),'Only discovery and read-query captures are accepted');
  const route={related:'objects/related',value:'objects/value',history:'objects/history'}[r.id]||r.id;
  req(r.url===c.base_url.replace(/\/$/,'')+'/'+route,'Capture route mismatch');
  req(r.method===(['related','value','history'].includes(r.id)?'POST':'GET'),'Capture method mismatch');
  req(typeof r.body==='string'&&r.body.length<=2000000,'Invalid raw response');
  req(r.sha256===await TC.sha(r.body),'Captured source bytes changed: '+r.id);
  req(Number.isFinite(Date.parse(r.captured_at)),'Missing observation time');
  by[r.id]={receipt:r,data:JSON.parse(r.body)};
 }
 const missing=REQUIRED.filter(id=>!by[id]);
 const issues=missing.map(id=>'Missing '+id+' response');
 for(const [id,v] of Object.entries(by))if(v.receipt.status!==200||v.data.success!==true)issues.push('Incomplete '+id+' response');
 if(by.info?.data.result?.specVersion!=='1.0')issues.push('Server does not declare i3X 1.0');
 const objects=by.objects?.data.result;
 if(!Array.isArray(objects)||!objects.some(x=>x.elementId==='pump-101'))issues.push('pump-101 was not discovered');
 const related=by.related?.data.results?.find(x=>x.elementId==='pump-101');
 if(!related?.success||!Array.isArray(related.result)||!related.result.some(x=>x.sourceRelationship==='HasComponent'&&x.object?.elementId==='pump-101-state'))issues.push('Required pump-to-state relationship absent');
 const state=by.value?.data.results?.find(x=>x.elementId==='pump-101-state');
 if(!state?.success||state.result?.quality!=='Good'||state.result?.value==null||!Number.isFinite(Date.parse(state.result?.timestamp)))issues.push('Pump state is missing, uncertain, or has no usable timestamp');
 const production=by.value?.data.results?.find(x=>x.elementId==='pump-101-production');
 return {capture_sha256:await hash(c),issues,complete:issues.length===0,endpoint:c.base_url,captured_at:c.captured_at,
  object_count:Array.isArray(objects)?objects.length:0,namespace_count:by.namespaces?.data.result?.length||0,
  state:state?.result?.value?.type?.name||'Unknown',state_quality:state?.result?.quality||'Unknown',
  production_known:!!(production?.success&&production.result?.quality==='Good'&&production.result?.value!==null),
  observation_status:'retained snapshot; freshness for a real decision is not established',remote_writes:false};
}
async function calculate(capture,packets){
 const context=await inspectCapture(capture),result=await TC.compose(packets);
 const body={engine:VERSION,context,fixture_binding:{fixture_asset:'PUMP-01',i3x_object:'pump-101',authority:'explicit synthetic exercise mapping, not a CESMII equipment model'},
  frontier:packets.map(p=>p.packet_sha256),result,status:context.complete?result.status:'INCONCLUSIVE_CONTEXT',
  action:'REVIEW_ONLY',physical_truth_verified:false,production_authority:false};
 return {...body,decision_sha256:await hash(body)};
}
async function start(capture,engineDigest){
 req(typeof engineDigest==='string'&&/^[a-f0-9]{64}$/.test(engineDigest),'A pinned engine digest is required');
 const packets=await Promise.all(Object.values(clone(TC.fragments)).map(f=>TC.makePacket(f,'synthetic-'+f.team)));
 const decision=await calculate(capture,packets);
 return {schema:VERSION,engine_sha256:engineDigest,capture:clone(capture),packets,decisions:[decision]};
}
async function correct(w){
 const before=await TC.compose(w.packets);const current=before.dependencies.find(x=>x.role==='allocation');
 const old=w.packets.find(p=>p.packet_sha256===current.packet);const source=JSON.parse(old.source.raw);
 req(source.records[0].allocated===2,'The planned allocation correction has already been applied');
 const f=clone(TC.fragments.allocation);f.records[0].allocated=1;
 const p=await TC.makePacket(f,'synthetic-allocation-reviewer',old.packet_sha256);
 w.packets.push(p);return p;
}
function isCurrent(w){return !!w.decisions.length&&TC.canonical(w.decisions.at(-1).frontier)===TC.canonical(w.packets.map(p=>p.packet_sha256));}
async function evaluate(w){const d=await calculate(w.capture,w.packets);if(w.decisions.at(-1)?.decision_sha256!==d.decision_sha256)w.decisions.push(d);return d;}
async function seal(w){const body=clone(w);return {...body,sha256:await hash(body)};}
async function restore(p,engineDigest){
 req(p&&p.schema===VERSION&&p.engine_sha256===engineDigest,'Different engine version or source digest');
 req(Array.isArray(p.packets)&&p.packets.length<=100&&Array.isArray(p.decisions)&&p.decisions.length<=100,'Invalid capsule size');
 const {sha256,...body}=p;req(sha256===await hash(body),'Capsule integrity mismatch');
 await inspectCapture(p.capture);const by=new Map();
 for(const packet of p.packets){await TC.verifyPacket(packet);req(!by.has(packet.packet_sha256),'Duplicate retained contribution');by.set(packet.packet_sha256,packet);}
 for(const d of p.decisions){
  req(Array.isArray(d.frontier),'Decision has no evidence frontier');
  const ps=d.frontier.map(id=>{req(by.has(id),'Missing predecessor evidence');return by.get(id);});
  const replay=await calculate(p.capture,ps);req(TC.canonical(replay)===TC.canonical(d),'Stored conclusion fails independent recomputation');
 }
 await TC.compose(p.packets);return clone(body);
}
function scenario(s,corrected=false){
 const e=clone(s.evidence);if(corrected)e[s.correction.field]=s.correction.value;
 let value=null,status='INCONCLUSIVE',explanation='Required evidence is missing or invalid';
 const numbers=Object.values(e).every(x=>typeof x==='number'&&Number.isFinite(x)&&x>=0);
 if(s.recipe==='balance'&&numbers&&e.committed<=e.usable){value=e.usable-e.committed;status=value>=e.required?'SUPPORTED_ON_RECORD':'SHORTAGE_ON_RECORD';explanation=`${e.usable} usable minus ${e.committed} committed = ${value}; ${e.required} required`;}
 if(s.recipe==='ratio'&&numbers&&e.good_units>0){value=e.energy_kwh/e.good_units;status='CALCULATED_ON_RECORD';explanation=`${e.energy_kwh} kWh / ${e.good_units} good units = ${value} kWh per good unit`;}
 if(s.recipe==='completion'&&numbers&&e.completed<=e.required){value=e.required-e.completed;status=value===0?'REVIEW_READY':'INCOMPLETE_ON_RECORD';explanation=`${e.completed} of ${e.required} declared checks complete; ${value} outstanding`;}
 return {scenario:s.id,status,value,explanation,evidence:e,evidence_class:'synthetic-recipe-fixture',production_authority:false};
}
async function selftest(capture,digest,scenarios){
 const checks=[];const check=(name,value)=>{checks.push({name,pass:!!value});if(!value)throw Error(name);};
 const reject=async(name,fn)=>{let failed=false;try{await fn();}catch(e){failed=true;}check(name,failed);};
 const old=await TC.exerciseTests();for(const c of old.checks)checks.push({name:'Team Commons: '+c.name,pass:c.pass});
 const c=await inspectCapture(capture);check('Eight read-only API responses retained',capture.records.length===8);check('Public demo pump context can be resolved',c.complete);
 const w=await start(capture,digest);check('Baseline is shortage',w.decisions[0].status==='SHORTAGE_ON_RECORD');
 check('Each team alone remains inconclusive',(await Promise.all(w.packets.map(p=>TC.compose([p])))).every(r=>r.status==='INCONCLUSIVE'));
 check('No device or production authority',w.decisions[0].action==='REVIEW_ONLY'&&!w.decisions[0].production_authority);
 await correct(w);check('Correction makes prior decision stale',!isCurrent(w));
 check('Correction retains original decision',w.decisions.length===1&&w.decisions[0].result.calculation.issuable===0);
 await evaluate(w);check('Corrected result has one issuable part',w.decisions[1].status==='SUPPORTED_ON_RECORD'&&w.decisions[1].result.calculation.issuable===1);
 check('New evaluation closes only the stale calculation',isCurrent(w)&&w.decisions.length===2);
 const p=await seal(w),r=await restore(clone(p),digest);check('Cold restore recomputes both conclusions',r.decisions.length===2&&isCurrent(r));
 const bad=clone(p);bad.decisions[1].status='AUTHORIZED';await reject('Raw tampering rejected',()=>restore(bad,digest));
 const {sha256,...b}=bad;bad.sha256=await hash(b);await reject('Rehashed false conclusion rejected',()=>restore(bad,digest));
 const missing=clone(p);missing.packets.shift();const {sha256:x,...mb}=missing;missing.sha256=await hash(mb);await reject('Removed source cannot retain a conclusion',()=>restore(missing,digest));
 await reject('Different engine cannot silently accept capsule',()=>restore(p,'0'.repeat(64)));
 const changed=clone(capture);changed.records[0].body+=' ';await reject('Captured API byte tampering rejected',()=>inspectCapture(changed));
 for(const quality of ['Bad','Uncertain','GoodNoData']){const cc=clone(capture),v=cc.records.find(x=>x.id==='value'),d=JSON.parse(v.body);d.results.find(x=>x.elementId==='pump-101-state').result.quality=quality;v.body=JSON.stringify(d);v.sha256=await TC.sha(v.body);check(quality+' state produces an inconclusive context',(await calculate(cc,w.packets)).status==='INCONCLUSIVE_CONTEXT');}
 const partial=clone(capture);partial.records.find(x=>x.id==='value').status=206;check('Partial response is not complete evidence',!(await inspectCapture(partial)).complete);
 for(const s of scenarios){const a=scenario(s),b=scenario(s,true);check(s.id+': baseline fixture',a.status===s.expected.before);check(s.id+': corrected fixture',b.status===s.expected.after);check(s.id+': correction changes retained inputs',TC.canonical(a.evidence)!==TC.canonical(b.evidence));const u=clone(s);u.evidence[Object.keys(u.evidence)[0]]=null;check(s.id+': missing remains unknown',scenario(u).status==='INCONCLUSIVE');}
 return {schema:'axm-i3x-test-report/1',engine:VERSION,engine_sha256:digest,capture_sha256:await hash(capture),status:'PASS',passed:checks.length,total:checks.length,checks,limits:'Same-author software tests on public demo captures and synthetic business records; not CESMII certification or plant qualification.'};
}
const api={VERSION,inspectCapture,start,correct,evaluate,isCurrent,seal,restore,scenario,selftest,hash,clone};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AXMI3X=api;
})(globalThis);
