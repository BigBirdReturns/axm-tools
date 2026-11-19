/* AXM member workbench. Deterministic evidence and decision history; no equipment effects. */
(function(root){
'use strict';
const TC=typeof module!=='undefined'&&module.exports?require('./commons-core.js'):{canonical,sha};
const canon=TC.canonical, copy=v=>JSON.parse(JSON.stringify(v)), hash=v=>TC.sha(canon(v));
const SCHEMA='axm-member-workspace/1', VERSION='1.0.0';
const need=(v,m)=>{if(!v)throw Error(m);};
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const id=v=>typeof v==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(v);
const text=(v,max=200)=>typeof v==='string'&&v.trim().length>0&&v.length<=max;
const iso=v=>typeof v==='string'&&Number.isFinite(Date.parse(v));
const hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const safe=v=>{need(object(v),'Expected an object');for(const k of Object.keys(v))need(!['__proto__','prototype','constructor'].includes(k),'Unsafe field name');return v;};
function jsonSize(v,max=12000000){need(canon(v).length<=max,'Input exceeds the supported size');}
function validateValues(v){safe(v);need(Object.keys(v).length>0&&Object.keys(v).length<=32,'A source must contain 1 to 32 fields');for(const [k,x]of Object.entries(v)){need(id(k),'Invalid evidence field name');need(x===null||typeof x==='boolean'||(typeof x==='string'&&x.length<=2000)||(typeof x==='number'&&Number.isFinite(x)&&Math.abs(x)<=1e12),'Evidence must be finite numbers, text, booleans or null');}return v;}
function validateExpression(e,sourceIds,depth=0){
 need(depth<12,'Rule expression is too deep');
 if(e===null||typeof e==='boolean'||typeof e==='number'||typeof e==='string'){need(typeof e!=='number'||Number.isFinite(e),'Invalid literal');return;}
 safe(e);
 if(Object.hasOwn(e,'source')){need(sourceIds.has(e.source)&&id(e.field)&&Object.keys(e).length===2,'Rule references an unknown source or invalid field');return;}
 need(['add','subtract','multiply','divide','min','max'].includes(e.op)&&Array.isArray(e.args)&&e.args.length>=2&&e.args.length<=16&&Object.keys(e).length===2,'Unsupported arithmetic expression');
 if(['subtract','divide'].includes(e.op))need(e.args.length===2,'Subtract and divide need two arguments');
 e.args.forEach(x=>validateExpression(x,sourceIds,depth+1));
}
function validateWorkflow(w){
 safe(w);jsonSize(w,300000);need(w.schema==='axm-member-workflow/1','Unsupported workflow schema');
 need(id(w.id)&&text(w.title),'A workflow needs an ID and title');safe(w.asset);
 need(text(w.asset.element_id,200)&&text(w.asset.label,200),'Name the mapped i3X asset');
 need(['synthetic','member-deidentified','operator-provided'].includes(w.evidence_class),'Declare the workflow evidence class');
 need(typeof w.require_context==='boolean','Declare whether i3X context is required');
 need(w.max_age_hours===null||(typeof w.max_age_hours==='number'&&w.max_age_hours>0&&w.max_age_hours<=87600),'Invalid freshness policy');
 need(Array.isArray(w.sources)&&w.sources.length>=1&&w.sources.length<=24,'A workflow needs 1 to 24 sources');const ids=new Set();
 for(const s of w.sources){safe(s);need(id(s.id)&&!ids.has(s.id),'Source IDs must be unique');ids.add(s.id);need(text(s.label)&&text(s.owner)&&iso(s.observed_at),'Each source needs a label, declared owner and observation time');need(typeof s.note==='string'&&s.note.length<=4000,'Invalid source note');validateValues(s.values);}
 need(Array.isArray(w.rules)&&w.rules.length>=1&&w.rules.length<=32,'A workflow needs 1 to 32 decision rules');const rules=new Set();
 for(const r of w.rules){safe(r);need(id(r.id)&&!rules.has(r.id)&&text(r.label),'Invalid or duplicate rule');rules.add(r.id);need(['gte','lte','gt','lt','eq','neq'].includes(r.op),'Unsupported comparison');validateExpression(r.left,ids);validateExpression(r.right,ids);}
 return copy(w);
}
function expression(e,current){
 if(!object(e))return e;
 if(Object.hasOwn(e,'source'))return current[e.source]?.values?.[e.field]??null;
 const a=e.args.map(x=>expression(x,current));if(a.some(x=>typeof x!=='number'||!Number.isFinite(x)))return null;
 let v;switch(e.op){case'add':v=a.reduce((x,y)=>x+y,0);break;case'subtract':v=a[0]-a[1];break;case'multiply':v=a.reduce((x,y)=>x*y,1);break;case'divide':v=a[1]===0?null:a[0]/a[1];break;case'min':v=Math.min(...a);break;case'max':v=Math.max(...a);break;default:v=null;}
 return typeof v==='number'&&Number.isFinite(v)?v:null;
}
function compare(op,a,b){if(a===null||b===null||typeof a!==typeof b)return null;if(op==='eq')return a===b;if(op==='neq')return a!==b;if(typeof a!=='number')return null;return({gte:a>=b,lte:a<=b,gt:a>b,lt:a<b})[op];}
function latest(w,frontier=null){const current=Object.create(null);for(const s of w.sources){if(!frontier||frontier.includes(s.sha256))current[s.id]=s;}return current;}
const routes={info:'info',namespaces:'namespaces',objecttypes:'objecttypes',relationshiptypes:'relationshiptypes',objects:'objects',related:'objects/related',value:'objects/value',history:'objects/history'};
async function inspectCapture(c,assetId){
 need(object(c)&&c.schema==='axm-i3x-capture/1'&&c.remote_writes===false,'Unsupported read-only capture');jsonSize(c);
 need(typeof c.base_url==='string'&&/^https?:\/\//.test(c.base_url),'Invalid captured endpoint');need(iso(c.captured_at),'Missing capture time');
 need(Array.isArray(c.records)&&c.records.length<=16,'Invalid response record count');
 const by=Object.create(null),issues=[];
 for(const r of c.records){need(object(r)&&Object.hasOwn(routes,r.id)&&!by[r.id],'Unknown or duplicate response');const method=['related','value','history'].includes(r.id)?'POST':'GET';need(r.method===method&&r.url===c.base_url.replace(/\/$/,'')+'/'+routes[r.id],'Unexpected API route or method');need(typeof r.body==='string'&&r.body.length<=2000000&&iso(r.captured_at),'Invalid response body/time');need(r.sha256===await TC.sha(r.body),'Response bytes changed: '+r.id);let data;try{data=JSON.parse(r.body);}catch(e){throw Error('Response is not JSON: '+r.id);}by[r.id]={data,receipt:r};if(r.id!=='history'&&(r.status!==200||data.success!==true))issues.push('Unsuccessful '+r.id+' response');}
 for(const r of ['info','objects','related','value'])if(!by[r])issues.push('Missing '+r+' response');
 const mapping=c.mapping||{asset_id:'pump-101',value_ids:['pump-101-state']};
 need(object(mapping)&&text(mapping.asset_id,200)&&Array.isArray(mapping.value_ids)&&mapping.value_ids.length>0&&mapping.value_ids.length<=64&&mapping.value_ids.every(v=>text(v,200)),'Invalid capture mapping');
 if(mapping.asset_id!==assetId)issues.push('Capture is mapped to '+mapping.asset_id+', workflow is mapped to '+assetId);
 if(by.info?.data.result?.specVersion!=='1.0')issues.push('Server does not declare i3X 1.0');
 const objects=by.objects?.data.result;if(!Array.isArray(objects)||!objects.some(o=>o.elementId===assetId))issues.push('Mapped asset was not discovered');
 const values=[];for(const valueId of mapping.value_ids){const v=by.value?.data.results?.find(x=>x.elementId===valueId);if(!v?.success||v.result?.quality!=='Good'||v.result?.value==null||!iso(v.result?.timestamp))issues.push('Missing, bad or undated value: '+valueId);values.push({element_id:valueId,value:v?.result?.value??null,quality:v?.result?.quality??'Unknown',timestamp:v?.result?.timestamp??null});}
 const related=by.related?.data.results?.find(x=>x.elementId===assetId);if(!related?.success)issues.push('Mapped asset relationship query failed');
 const objectMap=new Map((Array.isArray(objects)?objects:[]).map(o=>[o.elementId,o]));
 const relatedIds=new Set((Array.isArray(related?.result)?related.result:[]).filter(r=>!['HasParent','ComponentOf'].includes(r.sourceRelationship)).map(r=>r.object?.elementId).filter(Boolean));
 function belongs(valueId){if(valueId===assetId||relatedIds.has(valueId))return true;const seen=new Set();let node=objectMap.get(valueId);for(let i=0;node&&i<64;i++){if(seen.has(node.elementId))return false;seen.add(node.elementId);if(node.parentId===assetId||relatedIds.has(node.parentId))return true;node=objectMap.get(node.parentId);}return false;}
 for(const valueId of mapping.value_ids)if(!belongs(valueId))issues.push('Selected value has no retained relationship or ancestry to the mapped asset: '+valueId);
 return{sha256:await hash(c),endpoint:c.base_url,asset_id:mapping.asset_id,captured_at:c.captured_at,complete:issues.length===0,issues,values,object_count:Array.isArray(objects)?objects.length:0,remote_writes:false};
}
async function packet(w,source,previous=null,at=new Date().toISOString()){
 const b={id:source.id,label:source.label,owner:source.owner,observed_at:source.observed_at,recorded_at:at,values:copy(source.values),note:source.note,evidence_class:w.workflow.evidence_class,predecessor:previous};return{...b,sha256:await hash(b)};
}
async function start(workflow,capture,engineDigest){
 need(hex(engineDigest),'Pinned application source digest required');const wf=validateWorkflow(workflow);
 const w={schema:SCHEMA,version:VERSION,engine_sha256:engineDigest,workflow:wf,sources:[],captures:[],decisions:[],reviews:[]};
 for(const s of wf.sources)w.sources.push(await packet(w,s));
 if(capture)await addCapture(w,capture);return w;
}
async function correct(w,sourceId,values,owner,note='',observedAt=new Date().toISOString()){
 validateValues(values);need(text(owner)&&typeof note==='string'&&note.length<=4000&&iso(observedAt),'A correction needs a declared owner and observation time');const current=latest(w)[sourceId];need(current,'Unknown source');need(Object.keys(values).sort().join('|')===Object.keys(current.values).sort().join('|'),'Corrections must preserve field names; import a new workflow to change the schema');need(w.sources.length<1000,'Source history limit reached; export this workspace');
 const p=await packet(w,{...current,values,owner,note,observed_at:observedAt},current.sha256);w.sources.push(p);return p;
}
async function addCapture(w,c){need(w.captures.length<64,'Capture history limit reached');await inspectCapture(c,w.workflow.asset.element_id);const digest=await hash(c);if(!w.captures.some(x=>x.sha256===digest))w.captures.push({sha256:digest,data:copy(c)});return digest;}
function currentFrontier(w){return w.workflow.sources.map(s=>latest(w)[s.id].sha256);}
function isCurrent(w){const d=w.decisions.at(-1);return!!d&&canon(d.frontier)===canon(currentFrontier(w))&&d.capture_sha256===(w.captures.at(-1)?.sha256??null);}
async function calculate(w,frontier,captureDigest,at){
 const current=latest(w,frontier),rules=w.workflow.rules.map(r=>{const left=expression(r.left,current),right=expression(r.right,current);return{id:r.id,label:r.label,op:r.op,left,right,pass:compare(r.op,left,right)};});
 const missing=w.workflow.sources.filter(s=>!current[s.id]).map(s=>s.id);const capture=w.captures.find(c=>c.sha256===captureDigest);const context=capture?await inspectCapture(capture.data,w.workflow.asset.element_id):null;
 const ageIssues=[];if(w.workflow.max_age_hours!==null){for(const s of Object.values(current)){const age=(Date.parse(at)-Date.parse(s.observed_at))/3600000;if(age<0||age>w.workflow.max_age_hours)ageIssues.push(s.id+' is outside the declared freshness window');}if(context){const age=(Date.parse(at)-Date.parse(context.captured_at))/3600000;if(age<0||age>w.workflow.max_age_hours)ageIssues.push('i3X capture is outside the declared freshness window');for(const v of context.values){if(v.timestamp){const valueAge=(Date.parse(at)-Date.parse(v.timestamp))/3600000;if(valueAge<0||valueAge>w.workflow.max_age_hours)ageIssues.push(v.element_id+' value is outside the declared freshness window');}}}}
 let status=rules.some(r=>r.pass===null)||missing.length?'INCONCLUSIVE_ON_RECORD':rules.every(r=>r.pass)?'SUPPORTED_ON_RECORD':'NOT_SUPPORTED_ON_RECORD';
 if(w.workflow.require_context&&(!context||!context.complete))status='INCONCLUSIVE_CONTEXT';if(ageIssues.length)status='INCONCLUSIVE_FRESHNESS';
 const b={workflow_sha256:await hash(w.workflow),frontier:copy(frontier),capture_sha256:captureDigest,evaluated_at:at,status,rules,context,missing_sources:missing,freshness_issues:ageIssues,action:'REVIEW_ONLY',production_authority:false};return{...b,sha256:await hash(b)};
}
async function evaluate(w,at=new Date().toISOString()){need(iso(at),'Invalid evaluation time');need(w.decisions.length<500,'Decision history limit reached');const d=await calculate(w,currentFrontier(w),w.captures.at(-1)?.sha256??null,at);w.decisions.push(d);return d;}
async function review(w,owner,note){need(isCurrent(w),'Re-evaluate changed evidence before recording a review');need(text(owner)&&text(note,4000),'Name the reviewer and record the review');need(w.reviews.length<500,'Review limit reached');const b={decision_sha256:w.decisions.at(-1).sha256,owner,note,at:new Date().toISOString(),identity:'declared-unverified',authority:'review-only'};const r={...b,sha256:await hash(b)};w.reviews.push(r);return r;}
async function seal(w){const b=copy(w);return{...b,sha256:await hash(b)};}
async function restore(p,engineDigest){
 need(object(p)&&p.schema===SCHEMA&&p.version===VERSION,'Unsupported workspace capsule');jsonSize(p,30000000);need(p.engine_sha256===engineDigest&&hex(engineDigest),'Application source digest differs');const{sha256,...body}=p;need(sha256===await hash(body),'Capsule integrity mismatch');validateWorkflow(p.workflow);
 need(Array.isArray(p.sources)&&p.sources.length>=p.workflow.sources.length&&p.sources.length<=1000&&Array.isArray(p.captures)&&p.captures.length<=64&&Array.isArray(p.decisions)&&p.decisions.length<=500&&Array.isArray(p.reviews)&&p.reviews.length<=500,'Invalid capsule collections');
 const current=Object.create(null),seen=new Set(),initial=new Map(p.workflow.sources.map(s=>[s.id,s]));
 for(const s of p.sources){need(object(s)&&initial.has(s.id)&&!seen.has(s.sha256),'Unknown or duplicate source revision');validateValues(s.values);need(text(s.owner)&&text(s.label)&&iso(s.observed_at)&&iso(s.recorded_at)&&typeof s.note==='string'&&s.note.length<=4000&&s.evidence_class===p.workflow.evidence_class,'Invalid source metadata');const{sha256:h,...b}=s;need(h===await hash(b),'Source revision integrity mismatch');need(s.predecessor===(current[s.id]?.sha256??null),'Broken or conflicting correction lineage');need(Object.keys(s.values).sort().join('|')===Object.keys(initial.get(s.id).values).sort().join('|'),'Source field schema changed');if(!current[s.id]){const original=initial.get(s.id);for(const k of ['label','owner','observed_at','values','note'])need(canon(s[k])===canon(original[k]),'Initial source differs from workflow');}current[s.id]=s;seen.add(h);}
 need(Object.keys(current).length===initial.size,'Missing source history');const captures=new Set();for(const c of p.captures){need(!captures.has(c.sha256)&&c.sha256===await hash(c.data),'Invalid capture history');await inspectCapture(c.data,p.workflow.asset.element_id);captures.add(c.sha256);}
 const decisions=new Set();for(const d of p.decisions){need(Array.isArray(d.frontier)&&d.frontier.length===initial.size&&new Set(d.frontier).size===initial.size&&d.frontier.every(h=>seen.has(h))&&iso(d.evaluated_at),'Invalid decision frontier');need(new Set(p.sources.filter(s=>d.frontier.includes(s.sha256)).map(s=>s.id)).size===initial.size,'Decision frontier does not cover every source');need(d.capture_sha256===null||captures.has(d.capture_sha256),'Missing captured dependency');const replay=await calculate(p,d.frontier,d.capture_sha256,d.evaluated_at);need(canon(replay)===canon(d),'Stored conclusion fails independent recomputation');decisions.add(d.sha256);}
 for(const r of p.reviews){const{sha256:h,...b}=r;need(decisions.has(r.decision_sha256)&&text(r.owner)&&text(r.note,4000)&&iso(r.at)&&r.identity==='declared-unverified'&&r.authority==='review-only'&&h===await hash(b),'Invalid declared review');}
 return copy(body);
}
async function captureEndpoint(base,assetId,valueIds){
 const url=new URL(base);need(url.protocol==='https:'||(url.protocol==='http:'&&['localhost','127.0.0.1','[::1]'].includes(url.hostname)),'Use HTTPS or a local loopback server');need(!url.username&&!url.password&&!url.search&&!url.hash,'Endpoint must not contain credentials, query or fragment');base=base.replace(/\/$/,'');need(text(assetId,200)&&Array.isArray(valueIds)&&valueIds.length>0&&valueIds.length<=64&&valueIds.every(v=>text(v,200)),'Name the asset and value IDs');
 const now=new Date().toISOString(),requests=['info','namespaces','objecttypes','relationshiptypes','objects'].map(r=>[r,'GET',null]);requests.push(['related','POST',{elementIds:[assetId],includeMetadata:true}],['value','POST',{elementIds:valueIds,maxDepth:1}]);const records=[];
 for(const[name,method,body]of requests){const requestUrl=base+'/'+routes[name],controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);try{const response=await fetch(requestUrl,{method,headers:{Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,credentials:'omit',redirect:'error',cache:'no-store',signal:controller.signal});const raw=await response.text();need(raw.length<=2000000,'Endpoint response exceeds limit');JSON.parse(raw);records.push({id:name,url:requestUrl,method,request:body,status:response.status,captured_at:new Date().toISOString(),body:raw,sha256:await TC.sha(raw)});}finally{clearTimeout(timer);}}
 return{schema:'axm-i3x-capture/1',evidence_class:base==='https://api.i3x.dev/v1'?'public-demo-api-capture':'operator-provided-read-only-capture',base_url:base,captured_at:now,production_data:base==='https://api.i3x.dev/v1'?false:null,remote_writes:false,mapping:{asset_id:assetId,value_ids:copy(valueIds)},records};
}
function recipe(which='maintenance'){
 const now=new Date().toISOString();const s=(id,label,values)=>({id,label,owner:label+' team',observed_at:now,values,note:'Synthetic example. Replace with your declared operational evidence.'});const ref=(source,field)=>({source,field});let sources,rules,title;
 if(which==='energy'){title='Energy intensity review';sources=[s('meter','Energy meter',{energy_kwh:120}),s('quality','Accepted production',{good_units:40}),s('target','Intensity target',{max_kwh_per_unit:2.5})];rules=[{id:'intensity',label:'Energy per accepted unit meets declared target',op:'lte',left:{op:'divide',args:[ref('meter','energy_kwh'),ref('quality','good_units')]},right:ref('target','max_kwh_per_unit')}];}
 else if(which==='batch'){title='Batch release review';sources=[s('quality','Quality checks',{completed:8,required:8}),s('documents','Document review',{complete:true}),s('holds','Outstanding holds',{open:0})];rules=[{id:'checks',label:'Required checks complete',op:'gte',left:ref('quality','completed'),right:ref('quality','required')},{id:'documents',label:'Required documents reviewed',op:'eq',left:ref('documents','complete'),right:true},{id:'holds',label:'No open holds',op:'eq',left:ref('holds','open'),right:0}];}
 else {title='Maintenance release review';sources=[s('inventory','Serviceable inventory',{serviceable:2}),s('allocation','Existing allocations',{allocated:2}),s('maintenance','Work order',{required:1})];rules=[{id:'parts',label:'Unallocated serviceable stock meets the work order',op:'gte',left:{op:'subtract',args:[ref('inventory','serviceable'),ref('allocation','allocated')]},right:ref('maintenance','required')}];}
 return{schema:'axm-member-workflow/1',id:which+'-review',title,asset:{element_id:'pump-101',label:'Pump 101'},evidence_class:'synthetic',require_context:true,max_age_hours:null,sources,rules};
}
const api={VERSION,SCHEMA,canonical:canon,hash,validateWorkflow,inspectCapture,start,correct,addCapture,evaluate,review,seal,restore,isCurrent,latest,currentFrontier,captureEndpoint,recipe};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AXMWorkbench=api;
})(typeof window!=='undefined'?window:globalThis);
