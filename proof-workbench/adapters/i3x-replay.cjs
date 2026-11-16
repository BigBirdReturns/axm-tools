"use strict";
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
const root=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
const E=require(path.join(root,'engine.js')),meta=JSON.parse(fs.readFileSync(path.join(root,'build-meta.json')));
(async()=>{
 if(process.argv[4]==='restore'){
  const restored=await E.restore(JSON.parse(fs.readFileSync(output,'utf8')),meta.engine_sha256);
  if(restored.decisions.length!==2||restored.decisions[0].result.calculation.issuable!==0||restored.decisions[1].result.calculation.issuable!==1)throw Error('Cold replay disagrees');
  console.log(JSON.stringify({status:'PASS',schema:restored.schema,retained_decisions:2,issuable:[0,1],independent_process:true}));return;
 }
 const capture=JSON.parse(fs.readFileSync(path.join(root,'data/capture.json')));
 const w=await E.start(capture,meta.engine_sha256);await E.correct(w);
 if(E.isCurrent(w))throw Error('Correction failed to stale prior conclusion');
 await E.evaluate(w);fs.writeFileSync(output,JSON.stringify(await E.seal(w),null,2)+'\n',{flag:'wx'});
 const child=cp.spawnSync(process.execPath,[__filename,root,output,'restore'],{encoding:'utf8',timeout:30000});
 process.stdout.write(child.stdout||'');process.stderr.write(child.stderr||'');if(child.status!==0)throw Error('Fresh child rejected capsule');
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
