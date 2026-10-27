#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path');
const C=require('../source/research-core.js'),L=require('../source/continuity.js');require('../source/measurements.js');const R=require('../source/judgment.js');
(async()=>{
 const dir=process.argv[2];if(!dir)throw Error('Pass a fresh destination directory.');if(fs.existsSync(dir))throw Error('Refusing to overwrite existing fixture history.');fs.mkdirSync(dir,{recursive:true});
 let w=await L.create();w=await R.create(w,R.sample());
 await C.review(w,R.ID,'accept','Synthetic qualification: the temporary choice and its obligations are explicitly authored, not a real industrial approval.','Synthetic scenario reviewer');await C.freeze(w,R.ID,'Synthetic scenario reviewer');
 const origin=await C.pack(w);fs.writeFileSync(path.join(dir,'origin.json'),JSON.stringify(origin,null,2));
 let a={kind:'observe',actor:'Successor operator',at:'2026-10-27T09:00:00Z',reason:'A different operator reconstructs the same bounded decision from the retained packet.',values:{load:50,temperature_c:40,assembly:'B'}};
 w=(await R.apply(w,a)).workspace;
 w=(await R.apply(w,{...R.inspection(),'actor':'Successor operator'})).workspace; // Explicit refusal retained.
 w=(await R.apply(w,R.inspection())).workspace;
 w=(await R.apply(w,{kind:'revise_source',actor:'Operations lead',at:'2026-10-27T13:00:00Z',reason:'Corrected qualification lowers the load ceiling; the previous authorization must be revisited.',source:{id:'qualification',label:'Assembly B corrected qualification (synthetic)',raw_text:'{"assembly":"B","maximum_load":55,"maximum_temperature_c":60,"evidence":"synthetic"}'}})).workspace;
 const held=R.assess(R.get(w),'2026-10-27T13:00:00Z');if(held.applicable)throw Error('Source correction was not held.');
 w=(await R.apply(w,R.successor(R.get(w)))).workspace;
 await R.verify(w);const successor=await C.pack(w);fs.writeFileSync(path.join(dir,'successor.json'),JSON.stringify(successor,null,2));
 const current=R.assess(R.get(w),'2026-10-27T15:00:00Z');if(!current.applicable||current.open_obligations!==1)throw Error('Incorrect successor state.');
 if(C.canonical(C.state(w).reports)!==C.canonical(C.state(origin.workspace).reports))throw Error('Historical edition changed.');
 console.log(JSON.stringify({origin:origin.sha256,successor:successor.sha256,verdict:current.status,inherited:current.obligations.map(o=>({id:o.id,state:o.state})),history_prefix_preserved:C.canonical(w.events.slice(0,origin.workspace.events.length))===C.canonical(origin.workspace.events)},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
