/* Actual-second-server application acceptance. Run through verify.py or point at retained captures. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const here=__dirname,app=path.resolve(here,'..'),wb=path.join(app,'workbench');
const W=require(path.join(wb,'core.js'));
const rawsha=b=>crypto.createHash('sha256').update(b).digest('hex');
const digest=rawsha(Buffer.concat([fs.readFileSync(path.join(wb,'core.js')),Buffer.from('\n'),fs.readFileSync(path.join(wb,'commons-core.js'))]));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
(async()=>{
 if(process.argv[2]==='--restore'){
  const p=read(process.argv[3]),w=await W.restore(p,digest);
  if(w.decisions.length!==2||!W.isCurrent(w)||w.decisions[0].status!=='NOT_SUPPORTED_ON_RECORD'||w.decisions[1].status!=='SUPPORTED_ON_RECORD')throw Error('Fresh process did not reconstruct both expected conclusions');
  process.stdout.write(JSON.stringify({status:'PASS',decisions:w.decisions.length,engine_sha256:digest}));
  return;
 }
 if(!process.argv[2])throw Error('Specify a fresh evidence directory containing captures; use verify.py for a complete run.');
 const out=path.resolve(process.argv[2]),checks=[],check=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name);};
 const reject=async(name,fn)=>{let error=false;try{await fn();}catch(e){error=true;}check(name,error);};
 for(const file of ['application-report.json','capsule-local-pump.json','capsule-local-tank.json'])if(fs.existsSync(path.join(out,file)))throw Error('Refusing to overwrite retained evidence: '+file);
 const report={schema:'axm-i3x-second-server-application/1',observed_at:new Date().toISOString(),engine_sha256:digest,source_sha256:{'workbench/core.js':rawsha(fs.readFileSync(path.join(wb,'core.js'))),'workbench/commons-core.js':rawsha(fs.readFileSync(path.join(wb,'commons-core.js'))),'capture.py':rawsha(fs.readFileSync(path.join(app,'capture.py')))},checks};
 try{
  check('Published build digest equals actual application bytes',read(path.join(wb,'build-meta.json')).engine_sha256===digest);
  const historical=read(path.join(app,'data/capture.json'));
  check('Original retained public context still imports',(await W.inspectCapture(historical,'pump-101')).complete);
  const missing=read(path.join(out,'capture-missing-object.json'));
  check('Real missing object responses remain inconclusive',!(await W.inspectCapture(missing,'axm-missing-object')).complete);
  for(const [label,file,asset]of [['pump','capture-local-pump.json','pump-101'],['tank','capture-local-tank.json','tank-201']]){
   const c=read(path.join(out,file)),ctx=await W.inspectCapture(c,asset);
   check(label+': actual source bytes and context validate',ctx.complete);
   check(label+': expected mapped asset',ctx.asset_id===asset);
   check(label+': real independent loopback endpoint',['localhost','127.0.0.1','[::1]'].includes(new URL(ctx.endpoint).hostname)&&ctx.endpoint!==historical.base_url);
   const wf=W.recipe('maintenance');wf.asset={element_id:asset,label:label==='pump'?'Pump 101':'Tank 201'};
   const w=await W.start(wf,c,digest),d0=await W.evaluate(w);
   check(label+': baseline shortage is calculated',d0.status==='NOT_SUPPORTED_ON_RECORD'&&d0.rules[0].left===0&&d0.rules[0].right===1);
   await W.correct(w,'allocation',{allocated:1},'Synthetic allocation reviewer','Corrected the separately declared local allocation');
   check(label+': correction makes old decision stale',!W.isCurrent(w)&&w.decisions.length===1);
   const d1=await W.evaluate(w);
   check(label+': corrected decision is calculated',d1.status==='SUPPORTED_ON_RECORD'&&d1.rules[0].left===1&&W.isCurrent(w));
   check(label+': earlier conclusion is preserved',w.decisions[0].sha256===d0.sha256&&w.decisions[0].rules[0].left===0);
   await W.review(w,'Synthetic receiving reviewer','Reviewed original and corrected decisions against the retained source evidence.');
   const capsule=await W.seal(w),capsulePath=path.join(out,'capsule-local-'+label+'.json');
   fs.writeFileSync(capsulePath,JSON.stringify(capsule,null,2)+'\n',{flag:'wx'});
   const fresh=cp.spawnSync(process.execPath,[__filename,'--restore',capsulePath],{encoding:'utf8',timeout:30000});
   check(label+': fresh Node process independently replays both decisions',fresh.status===0&&JSON.parse(fresh.stdout).status==='PASS');
   const bad=structuredClone(capsule);bad.decisions[1].status='AUTHORIZED';
   const {sha256,...body}=bad;bad.sha256=await W.hash(body);
   await reject(label+': rehashed false conclusion rejected',()=>W.restore(bad,digest));
   check(label+': decision grants review only',d1.action==='REVIEW_ONLY'&&d1.production_authority===false);
  }
  const tank=read(path.join(out,'capture-local-tank.json'));
  check('Asset mismatch stays inconclusive',!(await W.inspectCapture(tank,'pump-101')).complete);
  const tampered=structuredClone(tank);tampered.records[0].body+=' ';
  await reject('Changed response bytes rejected',()=>W.inspectCapture(tampered,'tank-201'));
  const badQuality=structuredClone(tank),record=badQuality.records.find(r=>r.id==='value'),data=JSON.parse(record.body);
  data.results.find(r=>r.elementId==='sensor-001').result.quality='Uncertain';record.body=JSON.stringify(data);record.sha256=rawsha(record.body);
  check('Uncertain source quality remains inconclusive',!(await W.inspectCapture(badQuality,'tank-201')).complete);
  check('Real structural object with GoodNoData remains inconclusive',!(await W.inspectCapture(read(path.join(out,'capture-no-value.json')),'tank-201')).complete);
  report.status='PASS';report.passed=checks.filter(c=>c.pass).length;report.total=checks.length;
 }catch(e){report.status='FAIL';report.error=String(e.stack||e);process.exitCode=1;}
 fs.writeFileSync(path.join(out,'application-report.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 process.stdout.write(JSON.stringify(report)+'\n');
})().catch(e=>{process.stderr.write(String(e.stack||e));process.exitCode=1;});
