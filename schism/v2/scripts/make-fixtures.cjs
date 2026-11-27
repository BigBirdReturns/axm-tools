'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),E=require('../vendor/engine.js'),S=require('../controller.js');
const out=path.join(root,'data','cases');fs.mkdirSync(out,{recursive:true});
const write=(name,x)=>fs.writeFileSync(path.join(out,name),JSON.stringify(x,null,2)+'\n');
(async()=>{
 const actual=crypto.createHash('sha256').update('axm-industrial-engine/1\0').update(fs.readFileSync(path.join(root,'vendor','engine.js'))).update('\0').update(fs.readFileSync(path.join(root,'vendor','commons-core.js'))).digest('hex');
 assert.equal(actual,S.identity);
 let baseline=await E.evaluate(await E.start(actual));baseline=await E.review(baseline,'Origin reviewer','shift-planner');
 assert.equal(baseline.decisions[0].result.plan.net_cents,565000);
 const pending=await E.scenario(baseline,'customer-mix'),complete=await E.evaluate(pending);
 assert.equal(E.current(pending),false);assert.equal(E.reviewStatus(pending),'STALE');
 assert.equal(complete.decisions[1].result.plan.net_cents,885000);
 assert.deepEqual(complete.decisions[0],baseline.decisions[0]);assert.deepEqual(complete.reviews[0],baseline.reviews[0]);
 const packets={baseline:await E.seal(baseline),pending:await E.seal(pending),'completed-js':await E.seal(complete)};
 for(const [name,packet] of Object.entries(packets))write(name+'.json',packet);
 const missing=await E.evaluate(await E.scenario(baseline,'missing-evidence'));
 assert.equal(missing.decisions.at(-1).result.status,'INCONCLUSIVE');write('inconclusive.json',await E.seal(missing));
 for(const challenge of ['bytes','rehash-result','missing-source','authority','recipe'])write('reject-'+challenge+'.json',await S.challenged(packets.pending,challenge));
 const record={schema:'schism-case-register/2',contract_sha256:actual,evidence_class:'synthetic-industrial-records',
   required:[{file:'baseline.json',accept:true},{file:'pending.json',accept:true},{file:'completed-js.json',accept:true},{file:'inconclusive.json',accept:true},
    ...Object.entries({bytes:'Handoff digest mismatch.', 'rehash-result':'Saved conclusion differs from independent recomputation.',
      'missing-source':'Orphan or forked source revision.', authority:'Invalid review scope or invented authority.',
      recipe:'Different engine: explicit migration and requalification required.'}).map(([x,error])=>({file:'reject-'+x+'.json',accept:false,error}))],
   resume:{input:'pending.json',expected:'completed-js.json',expected_sha256:packets['completed-js'].sha256},
   boundary:'Record consistency and bounded calculations. No physical observation, authenticated reviewer or device operation.'};
 fs.writeFileSync(path.join(root,'data','case-register.json'),JSON.stringify(record,null,2)+'\n');
 console.log(JSON.stringify({state:'BUILT',cases:record.required.length,contract:actual,pending:packets.pending.sha256,completed:packets['completed-js'].sha256}));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
