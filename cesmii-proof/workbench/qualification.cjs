#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
const E=require('./core.js'), root=__dirname, clone=x=>JSON.parse(JSON.stringify(x));
const checks=[];function check(name,pass){checks.push({name,pass:!!pass});if(!pass)throw Error(name);}
async function rejects(name,fn){let rejected=false;try{await fn();}catch(e){rejected=true;}check(name,rejected);}
const digest=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'core.js'))).update('\n').update(fs.readFileSync(path.join(root,'commons-core.js'))).digest('hex');
async function rehash(p){const{sha256,...b}=p;p.sha256=await E.hash(b);return p;}
(async()=>{
 const c=JSON.parse(fs.readFileSync(path.join(root,'capture-example.json'),'utf8'));
 check('Actual installed sources match build metadata',digest===JSON.parse(fs.readFileSync(path.join(root,'build-meta.json'),'utf8')).engine_sha256);
 check('Retained public i3X context validates',(await E.inspectCapture(c,'pump-101')).complete);
 const unrelated=clone(c);unrelated.mapping={asset_id:'pump-101',value_ids:['unrelated-value']};for(const r of unrelated.records){if(r.id==='objects'){const b=JSON.parse(r.body);b.result.push({elementId:'unrelated-value',parentId:'other-plant'});r.body=JSON.stringify(b);r.sha256=await require('./commons-core.js').sha(r.body);}if(r.id==='value'){const b=JSON.parse(r.body);b.results.push({elementId:'unrelated-value',success:true,result:{quality:'Good',timestamp:new Date().toISOString(),value:42}});r.body=JSON.stringify(b);r.sha256=await require('./commons-core.js').sha(r.body);}}check('A good value on the same endpoint cannot impersonate an asset dependency',!(await E.inspectCapture(unrelated,'pump-101')).complete);
 const w=await E.start(E.recipe('maintenance'),c,digest);let d=await E.evaluate(w);
 check('Joined baseline has zero available against one required',d.status==='NOT_SUPPORTED_ON_RECORD'&&d.rules[0].left===0&&d.rules[0].right===1);
 const original=d.sha256;await E.review(w,'Reviewer A','Verified source owners');await E.correct(w,'allocation',{allocated:1},'Planning reviewer','Corrected duplicate allocation');
 check('Correction retains original source and decision and makes standing stale',w.sources.length===4&&w.decisions[0].sha256===original&&!E.isCurrent(w));
 await rejects('A stale decision cannot acquire a new review',()=>E.review(w,'Reviewer B','Review'));
 d=await E.evaluate(w);check('Successor uses corrected evidence without transferring original review',d.status==='SUPPORTED_ON_RECORD'&&w.decisions.length===2&&w.reviews[0].decision_sha256===original&&d.sha256!==original&&E.isCurrent(w));
 const capsule=await E.seal(w),restored=await E.restore(clone(capsule),digest);check('Cold restore recomputes both original and corrected decisions',restored.decisions.length===2&&E.isCurrent(restored));
 let p=clone(capsule);p.decisions[1].rules[0].left=999;await rejects('Raw conclusion modification rejected',()=>E.restore(p,digest));await rehash(p);await rejects('Rehashed invented conclusion rejected by recomputation',()=>E.restore(p,digest));
 p=clone(capsule);p.sources[3].values.allocated=0;await rehash(p);await rejects('Source bytes cannot change behind a retained source hash',()=>E.restore(p,digest));
 p=clone(capsule);p.sources[3].predecessor=null;{const{sha256,...b}=p.sources[3];p.sources[3].sha256=await E.hash(b);}await rehash(p);await rejects('Rehashed fork in correction lineage rejected',()=>E.restore(p,digest));
 p=clone(capsule);p.sources.shift();await rehash(p);await rejects('Missing predecessor history rejected',()=>E.restore(p,digest));
 p=clone(capsule);p.decisions[0].frontier=[p.sources[0].sha256,p.sources[0].sha256,p.sources[0].sha256];await rehash(p);await rejects('Duplicate frontier cannot substitute for missing source families',()=>E.restore(p,digest));
 p=clone(capsule);p.captures[0].data.records[0].body+=' ';await rehash(p);await rejects('Changed retained API response bytes rejected',()=>E.restore(p,digest));
 await rejects('Different actual application source identity rejected',()=>E.restore(capsule,'0'.repeat(64)));
 const unknown=await E.start(E.recipe('maintenance'),c,digest);await E.correct(unknown,'inventory',{serviceable:null},'Inventory','Unknown count');check('Unknown inventory remains inconclusive',(await E.evaluate(unknown)).status==='INCONCLUSIVE_ON_RECORD');
 const noContext=await E.start(E.recipe('maintenance'),null,digest);check('Missing required context is visible',(await E.evaluate(noContext)).status==='INCONCLUSIVE_CONTEXT');
 const stale=E.recipe('maintenance');stale.max_age_hours=1;stale.sources[0].observed_at='2000-01-01T00:00:00Z';check('Declared freshness limit changes the decision state',(await E.evaluate(await E.start(stale,c,digest))).status==='INCONCLUSIVE_FRESHNESS');
 const oldValue=clone(c);oldValue.captured_at=new Date().toISOString();for(const r of oldValue.records){if(r.id==='value'){const b=JSON.parse(r.body);b.results.find(x=>x.elementId==='pump-101-state').result.timestamp='2000-01-01T00:00:00Z';r.body=JSON.stringify(b);r.sha256=await require('./commons-core.js').sha(r.body);}}const freshRule=E.recipe('maintenance');freshRule.max_age_hours=1;const oldValueDecision=await E.evaluate(await E.start(freshRule,oldValue,digest));check('A new capture cannot refresh an old value timestamp',oldValueDecision.status==='INCONCLUSIVE_FRESHNESS'&&oldValueDecision.freshness_issues.some(s=>s.includes('pump-101-state')));
 const batch=await E.start(E.recipe('batch'),c,digest);check('Batch recipe evaluates three independent conditions',(await E.evaluate(batch)).status==='SUPPORTED_ON_RECORD');await E.correct(batch,'holds',{open:2},'Quality','Two open deviations');check('Batch source correction changes result',(await E.evaluate(batch)).status==='NOT_SUPPORTED_ON_RECORD');
 const energy=await E.start(E.recipe('energy'),c,digest);check('Energy ratio recipe evaluates actual arithmetic',(await E.evaluate(energy)).rules[0].left===3);await E.correct(energy,'quality',{good_units:0},'Quality','No accepted production');check('Division by zero stays unknown',(await E.evaluate(energy)).status==='INCONCLUSIVE_ON_RECORD');
 const custom=JSON.parse(fs.readFileSync(path.join(root,'..','review','member-workflow-template.json'),'utf8'));const member=await E.start(custom,c,digest);check('Delivered five-source member template imports and evaluates three rules',(await E.evaluate(member)).rules.length===3&&member.sources.length===5);await E.correct(member,'allocation',{allocated:1},'Member planner','Corrected reservation');check('Member template uses all rules after correction',(await E.evaluate(member)).status==='SUPPORTED_ON_RECORD');
 const memberInput=clone(custom);memberInput.evidence_class='member-deidentified';check('Member evidence classification survives the source contract',(await E.start(memberInput,c,digest)).sources.every(s=>s.evidence_class==='member-deidentified'));
 const bad=clone(custom);bad.rules[0].left={op:'eval',args:['alert(1)',1]};await rejects('Executable or unknown AST operator rejected',()=>E.start(bad,c,digest));
 const duplicate=clone(custom);duplicate.sources.push(clone(duplicate.sources[0]));await rejects('Duplicate source identity rejected',()=>E.start(duplicate,c,digest));
 const missing=clone(custom);missing.rules[0].right={source:'absent',field:'x'};await rejects('Unknown source reference rejected',()=>E.start(missing,c,digest));
 await rejects('Corrections cannot silently change source schema',()=>E.correct(w,'allocation',{other:1},'Planner','Wrong schema'));
 const out=path.join(root,'sample-handoff.json');fs.writeFileSync(out,JSON.stringify(capsule,null,2)+'\n');const result=cp.spawnSync(process.execPath,[path.join(root,'verify-capsule.cjs'),out],{encoding:'utf8'});check('Independent Node process replays actual exported handoff',result.status===0&&JSON.parse(result.stdout).recomputed_decisions===2);
 const report={schema:'axm-member-qualification/1',status:'PASS',engine_sha256:digest,passed:checks.length,total:checks.length,checks};fs.writeFileSync(path.join(root,'qualification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(JSON.stringify({status:'FAIL',error:e.message,checks},null,2));process.exitCode=1;});
