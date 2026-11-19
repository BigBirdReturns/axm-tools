"use strict";
const SCHEMA='mary-team-contribution/1';
const CHALLENGE={id:'shared-repair-synthetic-01',version:1,snapshot:'synthetic-snapshot-A',scope:'One synthetic pump repair and one part; no operational equipment or external effects.',criterion:'Establish whether recorded serviceable, unallocated stock supports this one work order. Unknown counts remain unknown.',authority:'Synthetic exercise only. Recorded names are declarations, not authenticated identities.'};
const canonical=v=>v===null||typeof v!=='object'?JSON.stringify(v):Array.isArray(v)?'['+v.map(canonical).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
async function sha(s){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))).map(x=>x.toString(16).padStart(2,'0')).join('');}
const cp=x=>JSON.parse(JSON.stringify(x));
const exact=(o,ks)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join('|')===ks.slice().sort().join('|');
const safeID=x=>typeof x==='string'&&/^[A-Za-z0-9._-]{1,100}$/.test(x);
const hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const qty=x=>typeof x==='number'&&Number.isSafeInteger(x)&&x>=0;
const fragments={inventory:{team:'inventory-team',role:'inventory',records:[{part:'PUMP-SEAL-17',on_hand:7,serviceable:2}],method:{},lesson:'Administrative stock and serviceable stock answer different questions.'},maintenance:{team:'maintenance-team',role:'maintenance',records:[{asset:'PUMP-01',work_order:'WO-01',part:'PUMP-SEAL-17',required:1}],method:{},lesson:'An open work order needs a part relationship and a quantity.'},allocation:{team:'allocation-team',role:'allocation',records:[{part:'PUMP-SEAL-17',allocated:2}],method:{},lesson:'Serviceable stock can already be committed elsewhere.'}};
async function makePacket(f,approvedBy,supersedes=null){
 if(typeof approvedBy!=='string'||!approvedBy.trim()||approvedBy.trim().length>100)throw Error('Name the releasing operator. This local declaration is not identity authentication.');
 const raw=canonical({snapshot:CHALLENGE.snapshot,role:f.role,records:f.records});
 const b={schema:SCHEMA,challenge_sha256:await sha(canonical(CHALLENGE)),team:f.team,role:f.role,source:{name:f.role+'.synthetic.json',raw,sha256:await sha(raw)},release:{scope:'synthetic-exercise',approved_by:approvedBy.trim(),at:new Date().toISOString()},supersedes,method:f.method||{},lesson:f.lesson||''};
 return {...b,packet_sha256:await sha(canonical(b))};
}
function checkMap(m){if(!m||typeof m!=='object'||Array.isArray(m)||Object.keys(m).length>5)throw Error('Invalid data-only mapping.');const allowed=['part','on_hand','serviceable','allocated','required'];for(const [k,v]of Object.entries(m))if(!allowed.includes(k)||typeof v!=='string'||!/^[a-zA-Z][a-zA-Z0-9_]{0,39}$/.test(v))throw Error('Mapping must be an allowed field name, never executable code.');if(new Set(Object.values(m)).size!==Object.values(m).length)throw Error('Ambiguous mapping.');}
async function verifyPacket(p){
 if(!exact(p,['schema','challenge_sha256','team','role','source','release','supersedes','method','lesson','packet_sha256']))throw Error('Incorrect contribution fields.');
 if(p.schema!==SCHEMA||!safeID(p.team)||!['inventory','maintenance','allocation'].includes(p.role))throw Error('Unsupported contribution contract.');
 if(p.challenge_sha256!==await sha(canonical(CHALLENGE)))throw Error('Different challenge or acceptance version.');
 if(!exact(p.source,['name','raw','sha256'])||typeof p.source.raw!=='string'||p.source.raw.length>100000||!safeID(p.source.name))throw Error('Invalid source.');
 if(!exact(p.release,['scope','approved_by','at'])||p.release.scope!=='synthetic-exercise'||typeof p.release.approved_by!=='string'||!p.release.approved_by.trim()||p.release.approved_by.length>100||!Number.isFinite(Date.parse(p.release.at)))throw Error('Explicit scoped release required.');
 if(p.supersedes!==null&&!hex(p.supersedes))throw Error('Invalid predecessor.');
 if(typeof p.lesson!=='string'||p.lesson.length>2000)throw Error('Invalid lesson.');checkMap(p.method);
 if(p.source.sha256!==await sha(p.source.raw))throw Error('Source-byte mismatch.');
 const d=JSON.parse(p.source.raw);if(canonical(d)!==p.source.raw)throw Error('Canonical source required; duplicate/noncanonical JSON rejected.');
 if(!exact(d,['snapshot','role','records'])||d.snapshot!==CHALLENGE.snapshot||d.role!==p.role||!Array.isArray(d.records)||d.records.length!==1)throw Error('This exercise accepts one record per role and one snapshot.');
 const r=d.records[0];if(!r||typeof r!=='object'||Array.isArray(r)||Object.keys(r).length>12)throw Error('Invalid record.');
 const {packet_sha256,...body}=p;if(packet_sha256!==await sha(canonical(body)))throw Error('Contribution digest mismatch.');return d;
}
async function compose(packets,mapping={}){
 checkMap(mapping);const current={},history=[];
 for(const p of packets){const d=await verifyPacket(p);history.push(p.packet_sha256);if(current[p.role]){if(current[p.role].p.packet_sha256===p.packet_sha256)continue;if(p.supersedes!==current[p.role].p.packet_sha256)throw Error('Conflicting '+p.role+' contributions; resolve lineage explicitly.');}else if(p.supersedes!==null)throw Error('Missing predecessor; retain correction history.');current[p.role]={p,d};}
 const deps=Object.values(current).map(x=>({team:x.p.team,role:x.p.role,source:x.p.source.sha256,packet:x.p.packet_sha256,row:1}));
 const out={schema:'mary-cooperative-result/1',challenge_sha256:await sha(canonical(CHALLENGE)),scope:CHALLENGE.scope,status:'INCONCLUSIVE',detail:'',missing:[],dependencies:deps,history,calculation:null};
 for(const role of ['maintenance','inventory','allocation'])if(!current[role])out.missing.push(role+' evidence');
 if(out.missing.length){out.detail='One team alone lacks the evidence needed for the shared conclusion.';return out;}
 const i=current.inventory.d.records[0],m=current.maintenance.d.records[0],a=current.allocation.d.records[0];
 const f=(r,k)=>Object.hasOwn(r,k)?r[k]:mapping[k]?r[mapping[k]]:undefined;
 const ip=f(i,'part'),mp=f(m,'part'),ap=f(a,'part');if(!safeID(ip)||ip!==mp||ip!==ap){out.missing.push('an unambiguous shared part identifier');out.detail='Part relationships are absent or conflicting.';return out;}
 const on=f(i,'on_hand'),svc=f(i,'serviceable'),alloc=f(a,'allocated'),need=f(m,'required');
 for(const [label,v]of [['serviceable quantity',svc],['allocated quantity',alloc],['required quantity',need]])if(!qty(v))out.missing.push(label);
 if(out.missing.length){out.detail='Missing or invalid counts remain unknown; no zero default.';return out;}
 if((on!==undefined&&!qty(on))||alloc>svc||(qty(on)&&svc>on)||need===0){out.status='CONFLICT';out.detail='Counts violate the declared one-part exercise contract.';return out;}
 const available=svc-alloc;out.calculation={part:ip,on_hand:on??null,serviceable:svc,allocated:alloc,required:need,issuable:available};out.status=available>=need?'SUPPORTED_ON_RECORD':'SHORTAGE_ON_RECORD';out.detail=`${svc} serviceable minus ${alloc} allocated leaves ${available}; the work order needs ${need}. This is a record-based conclusion, not physical observation.`;return out;
}
async function learningCapsule(approvedBy){if(!approvedBy||!approvedBy.trim())throw Error('Named review required.');const b={schema:'mary-data-mapping/1',author:'inventory-team',reviewed_by:approvedBy.trim(),scope:'synthetic-exercise',mapping:{part:'sku',on_hand:'total_units',serviceable:'usable_units'},credit:'Inventory team field mapping; the recipient retains its own acceptance responsibility.',tests:['Explicit missing quantities','One fresh synthetic schema'],claim:'Field names only; no code, model weights, private prompts or supplier data.'};return {...b,sha256:await sha(canonical(b))};}
async function verifyLesson(p){if(!exact(p,['schema','author','reviewed_by','scope','mapping','credit','tests','claim','sha256'])||p.schema!=='mary-data-mapping/1'||p.scope!=='synthetic-exercise'||!safeID(p.author)||typeof p.reviewed_by!=='string'||!p.reviewed_by.trim())throw Error('Invalid reviewed learning capsule.');checkMap(p.mapping);const {sha256,...b}=p;if(sha256!==await sha(canonical(b)))throw Error('Lesson digest mismatch.');return p.mapping;}
async function freshPackets(){const fs=cp(fragments);fs.inventory.records=[{sku:'PUMP-SEAL-17',total_units:6,usable_units:4}];fs.allocation.records=[{part:'PUMP-SEAL-17',allocated:1}];return Promise.all(Object.values(fs).map(f=>makePacket(f,'synthetic-fixture-operator')));}
async function exerciseTests(){const checks=[];const check=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name);};const ps=await Promise.all(Object.values(fragments).map(f=>makePacket(f,'synthetic-fixture-operator')));
 check('Three individual stations remain inconclusive',(await Promise.all(ps.map(p=>compose([p])))).every(x=>x.status==='INCONCLUSIVE'));
 const r=await compose(ps);check('Complementary evidence finds shortage',r.status==='SHORTAGE_ON_RECORD'&&r.calculation.issuable===0);
 check('Every contributor retains source and row',r.dependencies.length===3&&r.dependencies.every(x=>hex(x.source)&&x.row===1));
 let no=false;const bad=cp(ps[0]);bad.source.raw+=' ';try{await verifyPacket(bad);}catch(e){no=true;}check('Changed bytes rejected',no);
 no=false;try{await makePacket(fragments.inventory,'');}catch(e){no=true;}check('Anonymous release rejected',no);
 const u=cp(fragments.inventory);delete u.records[0].serviceable;check('Missing serviceable is unknown',(await compose([await makePacket(u,'test'),ps[1],ps[2]])).status==='INCONCLUSIVE');
 const ua=cp(fragments.allocation);delete ua.records[0].allocated;check('Missing allocation is unknown',(await compose([ps[0],ps[1],await makePacket(ua,'test')])).status==='INCONCLUSIVE');
 const c=cp(fragments.allocation);c.records[0].allocated=1;const next=await makePacket(c,'test',ps[2].packet_sha256);const updated=await compose([...ps,next]);check('Correction changes dependent result',updated.status==='SUPPORTED_ON_RECORD');check('Correction preserves old result and packet history',updated.history.length===4&&r.status==='SHORTAGE_ON_RECORD');
 no=false;try{await compose([...ps,await makePacket(c,'test')]);}catch(e){no=true;}check('Unresolved replacement conflict rejected',no);
 no=false;try{await compose([next]);}catch(e){no=true;}check('Orphan successor rejected',no);
 const np=await freshPackets();check('Fresh schema initially unresolved',(await compose(np)).status==='INCONCLUSIVE');const lesson=await learningCapsule('fixture-reviewer');check('Reviewed lesson resolves fresh case',(await compose(np,await verifyLesson(lesson))).status==='SUPPORTED_ON_RECORD');
 no=false;try{checkMap({serviceable:'(()=>42)()'});}catch(e){no=true;}check('Executable mapping rejected',no);
 no=false;const wrong=cp(ps[0]);wrong.challenge_sha256='0'.repeat(64);try{await verifyPacket(wrong);}catch(e){no=true;}check('Different challenge version rejected',no);
 check('Duplicate contribution is idempotent',(await compose([...ps,ps[0]])).dependencies.length===3);
 const over=cp(fragments.allocation);over.records[0].allocated=3;check('Contradictory quantities remain conflict',(await compose([ps[0],ps[1],await makePacket(over,'test')])).status==='CONFLICT');
 return {status:'PASS',checks,packets:ps,result:r,corrected_result:updated,lesson,fresh_packets:np};}
if(typeof module!=='undefined')module.exports={canonical,sha,compose,makePacket,verifyPacket,verifyLesson,exerciseTests,fragments,CHALLENGE};

async function makeWorkspace(packets,results){
 for(const p of packets)await verifyPacket(p);
 const body={schema:'mary-team-handoff/1',challenge_sha256:await sha(canonical(CHALLENGE)),packets:cp(packets),results:cp(results)};
 return {...body,sha256:await sha(canonical(body))};
}
async function verifyWorkspace(w){
 if(!exact(w,['schema','challenge_sha256','packets','results','sha256'])||w.schema!=='mary-team-handoff/1'||w.challenge_sha256!==await sha(canonical(CHALLENGE))||!Array.isArray(w.packets)||w.packets.length>100||!Array.isArray(w.results)||w.results.length>100)throw Error('Invalid handoff contract.');
 const {sha256,...body}=w;if(sha256!==await sha(canonical(body)))throw Error('Handoff digest mismatch.');
 const byHash=new Map();for(const p of w.packets){await verifyPacket(p);byHash.set(p.packet_sha256,p);}
 for(const r of w.results){if(!Array.isArray(r.history))throw Error('Result has no source frontier.');const input=r.history.map(id=>{if(!byHash.has(id))throw Error('Missing retained contribution.');return byHash.get(id);});const rebuilt=await compose(input);if(canonical(rebuilt)!==canonical(r))throw Error('Stored result differs from recomputed source evidence.');}
 await compose(w.packets);return {packets:cp(w.packets),results:cp(w.results)};
}
const earlierExerciseTests=exerciseTests;
exerciseTests=async()=>{
 const report=await earlierExerciseTests();const checks=report.checks;const ck=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name);};
 const w=await makeWorkspace(report.packets,[report.result]);const restored=await verifyWorkspace(JSON.parse(JSON.stringify(w)));ck('Cross-seat workspace recomputes retained result',restored.results[0].status==='SHORTAGE_ON_RECORD');
 let fail=false;const b=cp(w);b.results[0].status='SUPPORTED_ON_RECORD';try{await verifyWorkspace(b);}catch(e){fail=true;}ck('Altered workspace rejected',fail);
 const {sha256,...body}=b;b.sha256=await sha(canonical(body));fail=false;try{await verifyWorkspace(b);}catch(e){fail=true;}ck('Rehashed but false saved conclusion rejected',fail);
 const l=cp(report.lesson);l.mapping.serviceable='total_units';fail=false;try{await verifyLesson(l);}catch(e){fail=true;}ck('Changed lesson rejected',fail);
 ck('Exported lesson replays on a recipient',(await compose(report.fresh_packets,await verifyLesson(JSON.parse(JSON.stringify(report.lesson))))).status==='SUPPORTED_ON_RECORD');
 return report;
};
if(typeof module!=='undefined')Object.assign(module.exports,{exerciseTests,makeWorkspace,verifyWorkspace});
