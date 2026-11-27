'use strict';
const assert=require('node:assert/strict');
const S=require('../controller.js');
(async()=>{
 const checks=[];const check=(name,value)=>{assert(value,name);checks.push(name);};
 let s=await S.make();const baseline=await S.packet(s.producer);
 s=await S.correct(s,'customer-mix');
 check('Correction stales the existing decision and review before evaluation',!S.summary(s.producer).current&&S.summary(s.producer).review_status==='STALE');
 check('Historical decision remains byte-equivalent',JSON.stringify(s.producer.decisions[0])===JSON.stringify(baseline.decisions[0]));
 s=await S.handoff(s);s=await S.closeProducer(s);check('Origin workspace removed after export',s.producer===null);
 s=await S.receive(s);check('Recipient reconstructs the unfinished handoff',s.last_result.status==='ACCEPTED'&&!S.summary(s.receiver).current);
 s=await S.resume(s);check('Recipient computes corrected plan',S.summary(s.receiver).plan.net_cents===885000&&S.summary(s.receiver).current);
 check('Old review remains stale after a new calculation',S.summary(s.receiver).review_status==='STALE');
 const accepted=await S.packet(s.receiver);
 for(const challenge of ['bytes','rehash-result','missing-source','authority','recipe']){
  s=await S.receive(s,null,challenge);
  check(challenge+' is refused without replacing accepted state',s.last_result.status==='REFUSED'&&(await S.packet(s.receiver)).sha256===accepted.sha256);
 }
 s=await S.resume(s);check('Repeated continuation does not duplicate completed work',s.last_result.status==='NO_OP'&&s.receiver.decisions.length===2);
 s=await S.review(s);check('Separate recipient review binds to the new result',S.summary(s.receiver).review_status==='RECORDED_LABEL_ONLY');
 s=await S.correct(s,'missing-evidence');s=await S.resume(s);
 check('Incomplete evidence yields an explicit inconclusive decision',S.summary(s.receiver).status==='INCONCLUSIVE'&&S.summary(s.receiver).current);
 let refused=false;try{await S.review(s);}catch{refused=true;}check('An inconclusive result cannot be reviewed as computed',refused);
 s=await S.make();const old=s.producer.sources.length;
 const csv='sku,demand_units,contribution_usd_per_unit\nA,50,55.00\nB,20,40.00\n';
 s=await S.applyCSV(s,'orders',csv);
 check('Local CSV intake is a new unverified source revision',s.producer.sources.length===old+1&&s.producer.sources.at(-1).evidence_class==='operator-supplied-unverified');
 console.log(JSON.stringify({schema:'schism-controller-qualification/2',status:'PASS',checks,passed:checks.length,observed_at:new Date().toISOString()}));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
