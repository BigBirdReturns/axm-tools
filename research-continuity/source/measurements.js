/* Research Continuity measurement ledger. MIT. Uses unchanged ResearchCore records,
   revisions, dependencies, reviews and packet identity. No live retrieval or shell. */
(function(root){'use strict';
const L=root.Continuity||(typeof require!=='undefined'?require('./continuity.js'):null),C=L.C;
const ref=r=>({id:r.id,revision:r.revision}),latest=(w,id)=>C.latest(C.state(w),id);
const req=(x,label,max=1000)=>{C.assert(typeof x==='string'&&x.trim()&&x.length<=max,label+' is required.');return x.trim();};
const record=(id,kind,title,summary,data,deps=[],tier='operator_supplied')=>({id,kind,title,summary,data,deps,tier,disposition:kind==='source'?'observed':'draft'});
function key(s){C.assert(typeof s==='string'&&/^[a-z][a-z0-9-]{0,39}$/.test(s),'Measurement ID: lowercase letters, numbers and hyphens, up to 40 characters.');return s;}
function pointer(value,path){
 C.assert(typeof path==='string'&&path.length<=500&&(path===''||path.startsWith('/')),'Use a JSON Pointer such as /observations/count.');
 let v=value;
 if(path)for(const raw of path.slice(1).split('/')){
  C.assert(!/~(?:[^01]|$)/.test(raw),'Invalid JSON Pointer escape.');const k=raw.replace(/~1/g,'/').replace(/~0/g,'~');
  C.assert(v!==null&&typeof v==='object'&&Object.hasOwn(v,k),'JSON Pointer does not resolve: '+path);v=v[k];
 }
 C.assert(typeof v==='number'&&Number.isFinite(v),'A measurement must resolve to one finite numeric value.');return v;
}
function measure(source,path,unit,scale){
 req(unit,'Unit',120);C.assert(['scalar','rate','named_scale'].includes(scale),'Declare scalar, rate or named_scale.');
 return {schema:'research-continuity/measurement@1',source_id:source.id,source_revision:source.revision,pointer:path,value:pointer(C.parse(source.data.raw_text),path),unit,scale,recipe:'json-pointer@1',source_truth:'NOT_ESTABLISHED'};
}
async function makeSource(id,text,filename,meta){
 C.assert(typeof text==='string'&&new TextEncoder().encode(text).length<=2000000,'Source limit: 2 MB.');C.parse(text);
 const source_class=meta.evidence==='synthetic'?'synthetic':'operator_supplied';
 const data={schema:'research-continuity/measurement-source@1',filename:req(filename,'Filename',240),raw_text:text,sha256:await C.hash(text),bytes:new TextEncoder().encode(text).length,instrument:req(meta.instrument,'Instrument'),dataset_version:req(meta.dataset_version,'Dataset version',200),locator:req(meta.locator,'Locator'),re_execution_cmd:req(meta.re_execution_cmd,'Re-execution instruction',2000),captured_at:new Date().toISOString(),cross_check:'NOT_PERFORMED',gauge:'LOCAL_BYTE_IDENTITY_ONLY'};
 return record('measurement-source-'+key(id),'source',meta.title||filename,'Exact supplied JSON bytes and their declared measurement context. Re-execution instructions are text only.',data,[],source_class);
}
async function admit(w,id,text,filename,meta,path,unit,scale='scalar'){
 const next=C.clone(w),source=await makeSource(id,text,filename,meta);
 pointer(C.parse(text),path);req(unit,'Unit',120);C.assert(['scalar','rate','named_scale'].includes(scale),'Invalid scale.');
 const s=await C.put(next,source,'Local source custodian');
 await C.put(next,record('measurement-'+key(id),'claim',meta.title||id,'Value derived from the exact retained source at the declared JSON Pointer.',measure(s,path,unit,scale),[ref(s)],s.tier),'JSON Pointer extractor');return next;
}
async function reviseSource(w,id,text,filename,meta){
 const next=C.clone(w);C.assert(latest(next,'measurement-source-'+key(id)),'Admit this source first.');
 await C.put(next,await makeSource(id,text,filename,meta),'Local source custodian');return next;
}
async function readmit(w,id){
 const next=C.clone(w),m=latest(next,id);C.assert(m?.data.schema==='research-continuity/measurement@1','Choose a direct measurement.');
 const s=latest(next,m.data.source_id);C.assert(!C.dependencyState(C.state(next),id).current,'Measurement is already current.');
 await C.put(next,{...m,data:measure(s,m.data.pointer,m.data.unit,m.data.scale),deps:[ref(s)],summary:'Explicitly re-extracted after a source change. Downstream derived claims retain their own old pins.'},'JSON Pointer extractor');return next;
}
function deriveValue(a,b,op){
 for(const x of [a,b])C.assert(x&&typeof x.data.value==='number'&&Number.isFinite(x.data.value),'Two numeric measurement claims are required.');
 C.assert(a.data.scale!=='named_scale'&&b.data.scale!=='named_scale','Named scales require an explicitly justified domain recipe; generic arithmetic is refused.');
 let value,unit;
 if(op==='ratio'){C.assert(b.data.value!==0,'Division by zero.');value=a.data.value/b.data.value;unit=a.data.unit===b.data.unit?'dimensionless':a.data.unit+'/'+b.data.unit;}
 else{C.assert(['difference','sum'].includes(op),'Supported recipes: ratio, difference, sum.');C.assert(a.data.unit===b.data.unit&&a.data.scale===b.data.scale,'Sum/difference require matching units and scale types.');value=op==='sum'?a.data.value+b.data.value:a.data.value-b.data.value;unit=a.data.unit;}
 C.assert(Number.isFinite(value),'Derived value is not finite.');return {schema:'research-continuity/measurement-derivation@1',recipe:op,inputs:[ref(a),ref(b)],value,unit,scale:op==='ratio'?'rate':a.data.scale,source_truth:'NOT_ESTABLISHED'};
}
async function derive(w,id,left,right,op){
 const next=C.clone(w),s=C.state(next),a=C.latest(s,left),b=C.latest(s,right);
 C.assert(left!==right,'Use two distinct input claims.');C.assert(C.dependencyState(s,left).current&&C.dependencyState(s,right).current,'A derived claim cannot use stale measurement inputs.');
 const value=deriveValue(a,b,op);await C.put(next,record('derived-'+key(id),'claim',id,'Deterministic '+op+' over pinned, source-addressed measurements.',value,[ref(a),ref(b)],a.tier==='synthetic'||b.tier==='synthetic'?'synthetic':'operator_supplied'),'Local arithmetic recipe');return next;
}
async function crossCheck(w,left,right,tolerance=0){
 C.assert(typeof tolerance==='number'&&Number.isFinite(tolerance)&&tolerance>=0,'Tolerance must be finite and nonnegative.');
 const next=C.clone(w),s=C.state(next),a=C.latest(s,left),b=C.latest(s,right);
 C.assert(a&&b&&a.id!==b.id,'Select two distinct measurement claims.');C.assert(C.dependencyState(s,left).current&&C.dependencyState(s,right).current,'Refresh both measurement inputs before cross-checking.');
 C.assert(a.data.unit===b.data.unit&&a.data.scale===b.data.scale,'Cross-check units and scale types must match.');
 const difference=Math.abs(a.data.value-b.data.value),sameSource=a.data.source_id&&a.data.source_id===b.data.source_id;
 const data={schema:'research-continuity/cross-check@1',inputs:[ref(a),ref(b)],difference,tolerance,status:difference<=tolerance?'AGREES':'DISAGREES',independence:sameSource?'SAME_SOURCE':'UNESTABLISHED',meaning:'Observed numeric agreement under declared tolerance; not evidence of independent instrumentation or source truth.'};
 await C.put(next,record('crosscheck-'+next.events.length,'claim','Retained-value cross-check',data.meaning,data,[ref(a),ref(b)],a.tier==='synthetic'||b.tier==='synthetic'?'synthetic':'operator_supplied'),'Local cross-check');return next;
}
async function reviewAndFreeze(w,id,name,rationale){
 req(name,'Reviewer',160);req(rationale,'Rationale',4000);const next=C.clone(w);C.assert(latest(next,id),'Choose a claim.');
 await C.review(next,id,'accept',rationale,name);await C.freeze(next,id,name);return next;
}
function view(w){const s=C.state(w),records=Object.values(s.records).map(x=>x.at(-1));return {sources:records.filter(r=>r.data.schema==='research-continuity/measurement-source@1'),claims:records.filter(r=>['research-continuity/measurement@1','research-continuity/measurement-derivation@1'].includes(r.data.schema)).map(r=>({record:r,dependency:C.dependencyState(s,r.id)})),checks:records.filter(r=>r.data.schema==='research-continuity/cross-check@1').map(r=>({record:r,dependency:C.dependencyState(s,r.id)}))};}
async function verify(w){
 const s=C.state(w);
 for(const versions of Object.values(s.records))for(const r of versions){
  if(r.data.schema==='research-continuity/measurement-source@1'){
   for(const k of ['filename','instrument','dataset_version','locator','re_execution_cmd'])req(r.data[k],k,2000);
   C.parse(r.data.raw_text);C.assert(await C.hash(r.data.raw_text)===r.data.sha256,'Measurement source byte digest failed.');
  }else if(r.data.schema==='research-continuity/measurement@1'){
   C.assert(r.deps.length===1,'Direct measurement requires one source.');const pin=r.deps[0],src=C.version(s,pin.id,pin.revision);C.assert(src?.data.schema==='research-continuity/measurement-source@1','Measurement source missing.');
   C.assert(C.canonical(measure(src,r.data.pointer,r.data.unit,r.data.scale))===C.canonical(r.data),'Measurement does not recompute from its source.');
  }else if(r.data.schema==='research-continuity/measurement-derivation@1'){
   C.assert(r.deps.length===2,'Derived measurement requires two inputs.');const [a,b]=r.deps.map(p=>C.version(s,p.id,p.revision));
   C.assert(C.canonical(deriveValue(a,b,r.data.recipe))===C.canonical(r.data),'Derived measurement failed re-execution.');
  }else if(r.data.schema==='research-continuity/cross-check@1'){
   C.assert(r.deps.length===2,'Cross-check requires two inputs.');const [a,b]=r.deps.map(p=>C.version(s,p.id,p.revision));
   C.assert(a.data.unit===b.data.unit&&a.data.scale===b.data.scale,'Cross-check units mismatch.');const difference=Math.abs(a.data.value-b.data.value),tol=r.data.tolerance;
   C.assert(Number.isFinite(tol)&&tol>=0&&difference===r.data.difference&&r.data.status===(difference<=tol?'AGREES':'DISAGREES'),'Cross-check fails recomputation.');
   C.assert(['SAME_SOURCE','UNESTABLISHED'].includes(r.data.independence),'Numeric agreement cannot establish independence.');
  }
 }
 return w;
}
async function sample(w){
 const metadata={instrument:'Authored public fixture, not a real sensor',dataset_version:'lot-01-v1',locator:'Bundled synthetic laboratory export',re_execution_cmd:'node scripts/check_packet.cjs packet.json --recompute',evidence:'synthetic'};
 let next=await admit(w,'tested',JSON.stringify({lot:'SYN-01',tested:120,passed:90},null,2),'synthetic-lot.json',{...metadata,title:'Specimens tested'},'/tested','specimens');
 next=await admit(next,'passed',JSON.stringify({lot:'SYN-01',tested:120,passed:90},null,2),'synthetic-lot.json',{...metadata,title:'Specimens passing'},'/passed','specimens');
 return derive(next,'yield','measurement-passed','measurement-tested','ratio');
}
const api={admit,reviseSource,readmit,derive,crossCheck,reviewAndFreeze,view,verify,sample,pointer};
L.Measurements=api;const baseVerify=L.verify;L.verify=async packet=>verify(await baseVerify(packet));
root.ContinuityMeasurements=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
