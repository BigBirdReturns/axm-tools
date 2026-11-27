'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const E=require('../vendor/engine.js'),root=path.resolve(__dirname,'..');
(async()=>{
 const file=process.argv[2];if(!file)throw Error('Usage: node scripts/check-roundtrip.cjs python-resumed.json');
 const bytes=fs.readFileSync(file);assert(bytes.length<=4194304);
 const identity=crypto.createHash('sha256').update('axm-industrial-engine/1\0').update(fs.readFileSync(path.join(root,'vendor','engine.js'))).update('\0').update(fs.readFileSync(path.join(root,'vendor','commons-core.js'))).digest('hex');
 const input=JSON.parse(bytes),state=await E.restore(input,identity);
 const expected=JSON.parse(fs.readFileSync(path.join(root,'data','cases','completed-js.json'),'utf8'));
 assert.equal(input.sha256,expected.sha256,'Python continuation differs from the independent JavaScript result');
 assert.equal(state.decisions.length,2);assert.equal(E.current(state),true);assert.equal(E.reviewStatus(state),'STALE');
 console.log(JSON.stringify({schema:'schism-roundtrip/2',status:'PASS',direction:'JavaScript → Python continuation → original JavaScript receiver',
   observed_at:new Date().toISOString(),contract_sha256:identity,packet_sha256:input.sha256,
   source_count:state.sources.length,decision_count:state.decisions.length,review_status:E.reviewStatus(state),
   plan:state.decisions.at(-1).result.plan,operational_authority:false,external_effects:false},null,2));
})().catch(e=>{console.error(JSON.stringify({status:'FAIL',reason:e.message}));process.exitCode=1});
