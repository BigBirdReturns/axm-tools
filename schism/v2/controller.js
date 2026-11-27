/* SCHISM 2: an actual local handoff over the pinned Industrial Continuity contract. */
(function (root) {
  'use strict';
  const node = typeof module !== 'undefined' && module.exports;
  const E = node ? require('./vendor/engine.js') : root.IndustrialContinuity;
  const identity = 'f7cb1a8810a4a0c9af406c241fed7bfada2704c6f68ab9053f13af86cafc0e5d';
  const clone = E.clone;
  const requireState = (test, message) => { if (!test) throw new Error(message); };
  function event(session, action, status, detail) {
    session.events.push({sequence:session.events.length + 1, at:new Date().toISOString(), action, status, detail});
    session.events = session.events.slice(-100);
    session.last_result = {action, status, detail};
    return session;
  }
  function summary(state) {
    if (!state) return null;
    const decision = state.decisions.at(-1), result = decision?.result;
    return {status:result?.status || 'UNEVALUATED', current:E.current(state), review_status:E.reviewStatus(state),
      sources:state.sources.length, decisions:state.decisions.length, reviews:state.reviews.length,
      plan:result?.plan || null, chosen:result?.chosen || null, issues:result?.issues || [],
      frontier:E.frontier(state), result:result || null, explanation:result?.explanation || '',
      operational_authority:false, external_effects:false};
  }
  async function make() {
    let producer = await E.evaluate(await E.start(identity));
    producer = await E.review(producer, 'Origin reviewer', 'shift-planner');
    return event({schema:'schism-session/2',producer,receiver:null,transfer:null,events:[],last_result:null},
      'Open source workspace','READY','Six retained sources support the original calculation and a declared review.');
  }
  function active(session) {
    const name = session.producer ? 'producer' : session.receiver ? 'receiver' : null;
    requireState(name, 'Open or receive a workspace before changing its evidence.');
    return name;
  }
  function editCSV(raw, rowName, column, value) {
    const lines=raw.replace(/\r\n/g,'\n').trimEnd().split('\n');
    const row=lines.findIndex((line,i)=>i>0&&line.split(',')[0]===rowName);
    requireState(row>=1,'Required source row is absent.');
    const fields=lines[row].split(',');fields[column]=value;lines[row]=fields.join(',');
    return lines.join('\n')+'\n';
  }
  async function correct(session, scenario) {
    const next=clone(session), name=active(next), state=next[name];
    const latest=Object.fromEntries(E.latest(state).map(x=>[x.source,x]));
    let id,raw;
    if(scenario==='customer-mix'){id='orders';raw=editCSV(latest[id].raw,'B',2,'120.00');}
    else if(scenario==='parts-allocation'){
      id='maintenance';const rows=latest[id].raw.trimEnd().split('\n');const fields=rows[1].split(',');
      fields[3]=fields[2];rows[1]=fields.join(',');raw=rows.join('\n')+'\n';
    } else if(scenario==='quality-hold'){id='quality';raw=editCSV(latest[id].raw,'A',1,'0');}
    else if(scenario==='missing-evidence'){id='capacity';raw=editCSV(latest[id].raw,'pack',1,'');}
    else throw new Error('Unknown source correction.');
    next[name]=await E.change(state,id,raw,{observed:new Date().toISOString()});
    const changed=next[name].sources.length!==state.sources.length;
    return event(next,'Correct '+id,changed?'STALE':'NO_OP',changed?
      'The new source revision is retained. Earlier calculations and reviews keep their original dependencies.':
      'This source already contains the selected value. No new source revision was added.');
  }
  async function applyCSV(session,id,raw) {
    const next=clone(session),name=active(next);
    requireState(typeof raw==='string'&&raw.length<=32768,'Source CSV must be at most 32 KiB.');
    next[name]=await E.change(next[name],id,raw,{kind:'operator-supplied-unverified',observed:new Date().toISOString()});
    return event(next,'Import local '+id,'STALE','Local CSV retained as operator-supplied, unverified evidence. Evaluation remains a separate action.');
  }
  async function handoff(session) {
    const next=clone(session),name=active(next);
    next.transfer=await E.seal(next[name]);
    return event(next,'Seal handoff','SEALED','Source bytes, revision history, calculations and declared reviews are inside the exported record.');
  }
  async function closeProducer(session) {
    const next=clone(session);
    requireState(next.transfer,'Seal a handoff before closing the source workspace.');
    requireState(next.producer,'The source workspace is already closed.');
    next.producer=null;
    return event(next,'Close source workspace','CLOSED','The source workspace was removed from this session. The retained handoff is the receiver input.');
  }
  async function challenged(packet,challenge) {
    const p=clone(packet);
    if(challenge==='valid')return p;
    if(challenge==='bytes'){p.sources[0].raw+=' ';return p;}
    if(challenge==='rehash-result') {
      const d=[...p.decisions].reverse().find(d=>d.result?.plan);
      requireState(d,'This challenge needs a retained computed decision.');
      d.result.plan.net_cents+=10000;
      const old=d.sha256,{sha256,...body}=d;d.sha256=await E.digest(body);
      for(const r of p.reviews)if(r.decision===old){r.decision=d.sha256;const {sha256:rh,...rb}=r;r.sha256=await E.digest(rb);}
    } else if(challenge==='missing-source')p.sources.splice(0,1);
    else if(challenge==='authority') {
      requireState(p.reviews.length,'This challenge needs a retained declared review.');
      const r=p.reviews[0];r.operational_authority=true;
      const {sha256,...body}=r;r.sha256=await E.digest(body);
    } else if(challenge==='recipe')p.engine='0'.repeat(64);
    else throw new Error('Unknown handoff challenge.');
    const {sha256,...body}=p;p.sha256=await E.digest(body);return p;
  }
  async function receive(session,packet=null,challenge='valid') {
    const next=clone(session),candidate=packet || next.transfer;
    requireState(candidate,'Seal or select a handoff to receive.');
    const before=next.receiver?await E.seal(next.receiver):null;
    try {
      const input=await challenged(candidate,challenge);
      const accepted=await E.restore(input,identity);
      next.receiver=accepted;
      return event(next,'Receive handoff','ACCEPTED','Every retained historical decision was recomputed against its own six-source frontier.');
    } catch(error) {
      const after=next.receiver?await E.seal(next.receiver):null;
      requireState((before?.sha256 || null)===(after?.sha256 || null),'A failed import changed the accepted receiver.');
      return event(next,'Receive '+challenge,'REFUSED',String(error.message)+' The accepted receiver is unchanged.');
    }
  }
  async function resume(session) {
    const next=clone(session);
    requireState(next.receiver,'Receive a handoff before continuing the work.');
    if(E.current(next.receiver))return event(next,'Continue work','NO_OP','The latest source frontier already has a decision. Repeating this action adds no duplicate decision.');
    next.receiver=await E.evaluate(next.receiver);
    const result=next.receiver.decisions.at(-1).result;
    return event(next,'Continue work',result.status==='COMPUTED'?'CONTINUED':'INCONCLUSIVE',
      result.status==='COMPUTED'?'A new calculation is bound to the corrected frontier. The earlier review remains stale.':
      'The receiver retained an inconclusive result. Missing evidence remains explicit.');
  }
  async function review(session) {
    const next=clone(session),name=next.receiver?'receiver':active(next);
    next[name]=await E.review(next[name],'Recipient reviewer',next[name].decisions.at(-1)?.result?.review_role);
    return event(next,'Record review','DECLARED','The label and procedure role are retained against this exact decision. They grant no operational authority.');
  }
  async function fullDrill() {
    let s=await make();s=await correct(s,'customer-mix');s=await handoff(s);s=await closeProducer(s);
    s=await receive(s);return resume(s);
  }
  const api={identity,make,reset:make,summary,correct,applyCSV,handoff,closeProducer,receive,resume,review,
    fullDrill,packet:E.seal,challenged,sourceIds:E.IDS,sourceLabels:E.LABELS,sourceHeaders:E.HEADERS,
    latest:E.latest,clone};
  if(node)module.exports=api;else root.Schism=api;
})(globalThis);
