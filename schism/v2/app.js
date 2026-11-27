(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const S=window.Schism;
  const build=window.SCHISM_BUILD||{};
  let session=null,busy=true,noticeOverride=null,csvDirty=false;
  const descriptions={
    'customer-mix':"Raise Product B's recorded contribution from $40 to $120 per unit. The prior decision becomes stale before recalculation.",
    'parts-allocation':'Allocate the remaining serviceable spare. The next calculation must reconsider which intervention is eligible.',
    'quality-hold':'Record a quality hold on Product A. A new calculation must respect the revised release state.',
    'missing-evidence':'Remove the packaging capacity value. A missing quantity must remain unknown and withhold a complete calculation.'
  };
  const familyNames={orders:'Orders',routing:'Routing',capacity:'Capacity',maintenance:'Maintenance',quality:'Quality',procedure:'Procedure'};
  const actionNames={make:'Open fixture',reset:'Reset fixture',correct:'Correct source',correction:'Correct source',handoff:'Seal handoff',closeProducer:'Close origin',close_producer:'Close origin',close:'Close origin',receive:'Replay handoff',replay:'Replay handoff',resume:'Continue calculation',review:'Record declared review',applyCSV:'Apply local CSV',apply_csv:'Apply local CSV'};
  const el=(tag,text,className)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(className)n.className=className;return n;};
  const asText=x=>typeof x==='string'?x:typeof x==='number'||typeof x==='boolean'?String(x):'';
  const short=x=>typeof x==='string'&&x.length>22?x.slice(0,12)+'…'+x.slice(-8):asText(x);
  const money=cents=>Number.isFinite(cents)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:cents%100===0?0:2,maximumFractionDigits:2}).format(cents/100):'—';
  const safeSummary=n=>n&&S&&typeof S.summary==='function'?S.summary(n):null;
  const tone=status=>{const v=String(status||'').toUpperCase();if(/FAIL|ERROR|INVALID/.test(v))return 'error';if(/REFUS|STALE|INCONCLUSIVE|CONFLICT|INCOMPARABLE|PENDING|UNREVIEWED|NO_OP/.test(v))return 'warning';if(/PASS|ACCEPT|CURRENT|COMPUTED|RECORDED|REPLAY|RESUM|CONTINUED|SEALED|CLOSED|SUCCESS/.test(v))return 'success';return 'neutral';};
  const displayStatus=s=>!s?'EMPTY':!s.current&&s.decisions>0?'STALE':s.status==='INCONCLUSIVE'?'INCONCLUSIVE':s.current?'CURRENT ON RECORD':asText(s.status)||'NO DECISION';
  const nativeWorking=()=>session&&(session.producer||session.receiver);
  const historyWorking=()=>session&&(session.receiver||session.producer||session.transfer);
  function setPill(node,text){node.textContent=text;node.dataset.tone=tone(text);}
  function clear(node){while(node.firstChild)node.removeChild(node.firstChild);}
  function setNotice(label,detail,type){noticeOverride={label,detail,tone:type||tone(label)};renderNotice();}
  function renderNotice(){
    const last=session&&session.last_result;
    const events=session&&Array.isArray(session.events)?session.events:[];
    const event=events.length?events[events.length-1]:null;
    const notice=noticeOverride||{label:last&&asText(last.status)||event&&asText(event.status)||'Ready',detail:last&&asText(last.detail)||event&&asText(event.detail)||'Change a source to begin, or run the complete exit test.',tone:tone(last&&last.status||event&&event.status)};
    $('notice-label').textContent=busy&&session?'Working':notice.label;
    $('notice-detail').textContent=notice.detail;
    $('notice').dataset.tone=notice.tone;
  }
  function addCounts(target,summary){
    clear(target);if(!summary)return;
    for(const [key,label]of [['sources','source versions'],['decisions','decisions'],['reviews','declared reviews']]){const item=el('span');item.append(el('strong',summary[key]===undefined?'—':summary[key]),document.createTextNode(' '+label));target.append(item);}
  }
  function renderPlan(node,summary,emptyTitle,emptyDetail){
    clear(node);
    if(!summary||!summary.plan){
      const empty=el('div',null,'empty-plan');empty.append(el('h4',summary&&summary.status==='INCONCLUSIVE'?'Calculation withheld':emptyTitle),el('p',summary&&summary.status==='INCONCLUSIVE'?'The retained evidence does not support a complete calculation.':emptyDetail));
      if(summary&&Array.isArray(summary.issues)&&summary.issues.length){const ul=el('ul',null,'issue-list');for(const issue of summary.issues.slice(0,8))ul.append(el('li',issue));empty.append(ul);}node.append(empty);return;
    }
    const grid=el('div',null,'plan-grid');
    for(const [value,label]of [[summary.plan.a,'Product A / units'],[summary.plan.b,'Product B / units'],[money(summary.plan.net_cents),'Modeled net contribution']]){const cell=el('div',null,'plan-cell');cell.append(el('strong',value===undefined?'—':value,'plan-value'),el('span',label,'plan-label'));grid.append(cell);}
    node.append(grid);
    if(!summary.current)node.append(el('p','STALE · retained result awaits evaluation of the corrected source.','plan-stale'));
  }
  function renderWorkspaces(){
    const p=safeSummary(session&&session.producer),r=safeSummary(session&&session.receiver);
    const closed=!!session&&!session.producer;
    setPill($('producer-status'),p?displayStatus(p):closed?'CLOSED':'LOADING');
    $('producer-description').textContent=closed?'The originating working state has been cleared. Continuation now depends on the retained handoff and the receiver.':p&&!p.current?'A source changed. The earlier calculation and its review retain their history but have lost current standing.':'The fixture begins with a complete source record, a calculation and a declared review.';
    renderPlan($('producer-plan'),p,closed?'Origin closed':'Opening fixture',closed?'The receiver can continue from a valid retained packet. The origin supplies no working state.':'The source workspace is being initialized.');
    addCounts($('producer-counts'),p);
    setPill($('receiver-status'),displayStatus(r));
    $('receiver-description').textContent=!r?'Replay validates the retained dependencies and recomputes every historical conclusion before accepting the handoff.':!r.current?'The historical calculation replayed successfully. The corrected source still needs its own decision.':r.status==='INCONCLUSIVE'?'The receiver retained the evidence and withheld a complete calculation. Missing inputs remain explicit.':'The receiver holds a calculation consistent with its latest retained source frontier.';
    renderPlan($('receiver-plan'),r,'A separate receiver is ready.','Seal a handoff, close the origin, then replay the retained record here.');
    addCounts($('receiver-counts'),r);
    $('receiver-explanation').hidden=!!r;
    const editor=$('source-editor');
    if(session&&session.producer){$('producer-editor-slot').append(editor);editor.hidden=false;$('editor-target').textContent='ORIGIN';$('correction-label').textContent='Correct a source';}
    else if(session&&session.receiver){$('receiver-editor-slot').append(editor);editor.hidden=false;$('editor-target').textContent='RECEIVER';$('correction-label').textContent='Correct a receiver source';}
    else editor.hidden=true;
    $('origin-footnote').textContent=closed?'The sealed handoff remains available below. Reset opens a fresh fixture.':'A handoff retains raw sources, every decision and its review history.';
    $('resume').textContent=r&&r.current?'Calculation is current':'Continue calculation';
    $('review').textContent=r&&r.review_status==='RECORDED_LABEL_ONLY'?'Declared review recorded':'Record declared review';
    $('scenario-help').textContent=descriptions[$('scenario').value]||'';
    if(!csvDirty)loadCSV();
  }
  function markStep(id,done){const n=$(id);n.classList.toggle('is-done',!!done);n.querySelector('.step-state').textContent=done?'✓':'';n.setAttribute('aria-label',n.querySelectorAll('span')[1].textContent+(done?', completed':', not completed'));}
  function renderProgress(){
    const states=session?[session.producer,session.transfer,session.receiver].filter(Boolean):[];
    const corrected=states.some(s=>Array.isArray(s.sources)&&s.sources.some(x=>x.revision>1));
    const received=!!(session&&session.receiver),rs=safeSummary(session&&session.receiver);
    const transferDecisions=session&&session.transfer&&Array.isArray(session.transfer.decisions)?session.transfer.decisions.length:0;
    markStep('step-correct',corrected);markStep('step-handoff',session&&session.transfer);markStep('step-close',session&&!session.producer&&session.transfer);markStep('step-replay',received);markStep('step-resume',received&&rs&&rs.current&&rs.decisions>transferDecisions);
  }
  function renderTransfer(){
    const t=session&&session.transfer;
    if(!t){$('transfer-detail').textContent='Seal a handoff to retain a transferable snapshot.';$('transfer-digest').textContent='';return;}
    const parts=[Array.isArray(t.sources)?t.sources.length+' source versions':null,Array.isArray(t.decisions)?t.decisions.length+' decisions':null,Array.isArray(t.reviews)?t.reviews.length+' declared reviews':null].filter(Boolean);
    $('transfer-detail').textContent=parts.join(' · ')+' · snapshot retained locally';
    $('transfer-digest').textContent=t.sha256?'SHA-256 '+t.sha256:'Sealed packet present';
  }
  function renderEvents(){
    const events=session&&Array.isArray(session.events)?session.events:[];clear($('events'));$('event-count').textContent=events.length+' '+(events.length===1?'event':'events');
    if(!events.length){$('events').append(el('li','Events appear as the test runs.','empty-event'));return;}
    for(const e of events.slice(-30).reverse()){const li=el('li');const status=el('span',asText(e.status)||'RECORDED','event-status');status.dataset.tone=tone(e.status);const action=asText(e.action);li.append(status,el('span',actionNames[action]||action.replace(/[_-]/g,' ')||'Transition','event-action'),el('span',asText(e.detail),'event-detail'));$('events').append(li);}
  }
  function renderHistory(){
    const state=historyWorking(),summary=safeSummary(state);clear($('history-body'));clear($('source-body'));
    $('history-owner').textContent=session&&session.receiver?'RECEIVER':session&&session.producer?'ORIGIN':state?'SEALED HANDOFF':'NO RECORD';
    if(!state||!Array.isArray(state.decisions)||!state.decisions.length){const row=el('tr'),cell=el('td','No calculation has been retained.');cell.colSpan=5;row.append(cell);$('history-body').append(row);}
    else state.decisions.forEach((d,i)=>{
      const result=d.result||{},last=i===state.decisions.length-1,current=!!(last&&summary&&summary.current),review=(state.reviews||[]).find(x=>x.decision===d.sha256),row=el('tr');
      const identity=el('td','D'+String(d.sequence===undefined?i+1:d.sequence).padStart(2,'0'));identity.append(el('span',short(d.sha256),'table-note'));
      const standing=el('td'),label=current?'CURRENT':last?'STALE':'HISTORICAL',pill=el('span',label,'table-state');pill.dataset.tone=current?'success':last?'warning':'neutral';standing.append(pill);
      const plan=result.plan?String(result.plan.a)+' / '+String(result.plan.b):asText(result.status)||'—';
      const rv=el('td',review?'Declared':'Unreviewed');if(review)rv.append(el('span',current?'Label only':'Historical label','table-note'));
      row.append(identity,standing,el('td',plan),el('td',result.plan?money(result.plan.net_cents):'—'),rv);$('history-body').append(row);
    });
    const sources=state&&Array.isArray(state.sources)?state.sources:[];$('source-record-count').textContent=sources.length?'('+sources.length+')':'';
    for(const source of sources){const row=el('tr'),hash=el('code',short(source.sha256));hash.title=asText(source.sha256);const cell=el('td');cell.append(hash);row.append(el('td',familyNames[source.source]||source.source),el('td',source.revision),el('td',source.evidence_class==='synthetic-fixture'?'Synthetic fixture':source.evidence_class==='operator-supplied-unverified'?'Local / unverified':asText(source.evidence_class)),cell);$('source-body').append(row);}
  }
  function enable(id,can){const n=$(id);n.disabled=busy||!can;if(n.type==='file'&&n.parentElement.classList.contains('file-button'))n.parentElement.classList.toggle('is-disabled',n.disabled);}
  function renderControls(){
    const p=session&&session.producer,r=session&&session.receiver,t=session&&session.transfer,rs=safeSummary(r);
    enable('full-drill',!!S);enable('reset',!!S);enable('correct',!!(p||r));enable('handoff',!!p);enable('close-producer',!!p&&!!t);enable('receive',!!t);enable('resume',!!r&&!!rs&&!rs.current);enable('review',!!r&&!!rs&&rs.current&&rs.status==='COMPUTED'&&rs.review_status!=='RECORDED_LABEL_ONLY');enable('export-receiver',!!r);enable('download-packet',!!t);enable('packet-file',!!session);enable('test-challenge',!!t);enable('apply-csv',!!(p||r)&&!!S&&typeof S.applyCSV==='function');enable('csv-file',!!(p||r)&&!!S&&typeof S.applyCSV==='function');
    for(const id of ['scenario','source-family','source-csv','challenge'])$(id).disabled=busy||!session;
    document.body.classList.toggle('busy',busy);
  }
  function render(){renderWorkspaces();renderProgress();renderTransfer();renderEvents();renderHistory();renderNotice();renderControls();}
  function loadCSV(){
    const s=nativeWorking();if(!s||!Array.isArray(s.sources)){$('source-csv').value='';return;}
    const records=s.sources.filter(x=>x.source===$('source-family').value);$('source-csv').value=records.length?asText(records[records.length-1].raw):'';
  }
  async function run(operation,{label,scroll=false}={}){
    if(busy)return;busy=true;noticeOverride=null;renderControls();if(label)setNotice('Working',label,'neutral');
    try{const next=await operation();if(!next||!Array.isArray(next.events))throw Error('The controller returned no valid session.');session=next;noticeOverride=null;csvDirty=false;}
    catch(error){setNotice('Unable to complete',error&&error.message?error.message:String(error),'error');}
    finally{busy=false;render();if(scroll&&window.matchMedia('(max-width:780px)').matches)$('receiver-panel').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'start'});}
  }
  function downloadObject(value,name){const blob=new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);}
  function allowedHref(value,fallback){if(typeof value!=='string'||!value.trim())return fallback;const s=value.trim();if(/^(https?:\/\/|\.\.?\/|[A-Za-z0-9_-]+(?:\/|\.|#))/.test(s)&&!/[\u0000-\u001f]/.test(s))return s;return fallback;}
  function renderEvidence(){
    const definitions=[['linux','Linux recipient','PYTHON / RETAINED RUN'],['windows','Windows recipient','PYTHON / RETAINED RUN'],['roundtrip','Cross-runtime continuity','QUALIFICATION / RETAINED RUN'],['cantos','Acceptance precedent','CANTOS / RELATED EVIDENCE']];
    clear($('proof-grid'));
    for(const [key,title,kind]of definitions){
      const raw=build.evidence&&build.evidence[key];const item=raw&&typeof raw==='object'?raw:{};const status=asText(item.status)||asText(item.verdict)||'PENDING';
      const card=el('section',null,'proof-card'),top=el('div',null,'proof-top'),pill=el('span',status,'status-pill');pill.dataset.tone=tone(status);top.append(el('span',kind,'proof-type'),pill);card.append(top,el('h3',title));
      let description=asText(item.summary)||asText(item.description)||asText(item.detail);
      if(!description)description=raw?'The retained record supplies this result. Inspect its exact scope and execution details.':'This build contains no execution receipt for this card.';
      card.append(el('p',description));
      const link=el('a',raw?'Inspect retained record ↗':'Inspect qualification record ↗');link.href=allowedHref(item.href||item.url||item.path,'data/qualification.json');if(/^https?:/.test(link.href)&&!link.href.startsWith(location.origin+'/')){link.target='_blank';link.rel='noopener noreferrer';}card.append(link);
      if(raw){const details=el('details');details.append(el('summary','Receipt details'),el('pre',JSON.stringify(raw,null,2),'receipt'));card.append(details);}
      $('proof-grid').append(card);
    }
    $('contract-identity').textContent=asText(build.contract_sha256)||(S&&asText(S.identity))||'No contract identity included';
    $('edition').textContent=(asText(build.version)||'2.0')+' / SOFTWARE CONTINUITY';
    $('release-line').textContent='Edition '+(asText(build.version)||'2.0')+(build.release_date?' · '+asText(build.release_date):'');
  }
  function bind(){
    $('scenario').addEventListener('change',()=>{$('scenario-help').textContent=descriptions[$('scenario').value]||'';});
    $('source-family').addEventListener('change',()=>{csvDirty=false;loadCSV();});$('source-csv').addEventListener('input',()=>{csvDirty=true;});
    $('full-drill').addEventListener('click',()=>run(()=>S.fullDrill(),{label:'Running the full correction, handoff, closure and continuation path.',scroll:true}));
    $('reset').addEventListener('click',()=>run(()=>typeof S.reset==='function'?S.reset():S.make(),{label:'Opening a fresh fixture.'}));
    $('correct').addEventListener('click',()=>run(()=>S.correct(session,$('scenario').value),{label:'Recording a corrected source without recalculating.'}));
    $('handoff').addEventListener('click',()=>run(()=>S.handoff(session),{label:'Sealing the current sources, calculations and reviews.'}));
    $('close-producer').addEventListener('click',()=>run(()=>S.closeProducer(session),{label:'Closing the originating working state.'}));
    $('receive').addEventListener('click',()=>run(()=>S.receive(session),{label:'Replaying every retained historical decision.'}));
    $('resume').addEventListener('click',()=>run(()=>S.resume(session),{label:'Calculating from the receiver’s current source frontier.'}));
    $('review').addEventListener('click',()=>run(()=>S.review(session),{label:'Recording a declared review against the receiver’s current decision.'}));
    $('test-challenge').addEventListener('click',()=>run(()=>S.receive(session,null,$('challenge').value),{label:'Testing a modified copy of the handoff against the receiver.'}));
    $('apply-csv').addEventListener('click',()=>run(()=>S.applyCSV(session,$('source-family').value,$('source-csv').value),{label:'Recording local CSV as unverified source evidence.'}));
    $('download-packet').addEventListener('click',()=>{if(session&&session.transfer){downloadObject(session.transfer,'SCHISM-handoff.json');setNotice('Downloaded','The sealed handoff JSON has been downloaded.','success');}});
    $('export-receiver').addEventListener('click',async()=>{if(busy||!session||!session.receiver)return;busy=true;renderControls();try{const packet=await S.packet(session.receiver);downloadObject(packet,'SCHISM-receiver-handoff.json');setNotice('Downloaded','The receiver’s current sources and retained history have been exported.','success');}catch(e){setNotice('Export failed',e.message||String(e),'error');}finally{busy=false;renderNotice();renderControls();}});
    $('packet-file').addEventListener('change',async event=>{const file=event.target.files&&event.target.files[0];event.target.value='';if(!file)return;if(file.size>4194304){setNotice('Import refused','Handoff exceeds the 4 MiB limit. The accepted workspace is unchanged.','warning');return;}try{const packet=JSON.parse(await file.text());await run(()=>S.receive(session,packet,'valid'),{label:'Validating and replaying the imported handoff.',scroll:true});}catch(e){setNotice('Import refused',(e.message||String(e))+'. The accepted workspace is unchanged.','warning');}});
    $('csv-file').addEventListener('change',async event=>{const file=event.target.files&&event.target.files[0];event.target.value='';if(!file)return;if(file.size>131072){setNotice('CSV not loaded','This bounded source editor accepts at most 32,768 text characters.','warning');return;}try{const raw=await file.text();if(raw.length>32768)throw Error('CSV exceeds the 32,768-character source limit.');$('source-csv').value=raw;csvDirty=true;setNotice('CSV loaded','Review the selected mapping, then apply the local CSV to record an unverified source revision.','neutral');}catch(e){setNotice('CSV not loaded',e.message||String(e),'warning');}});
  }
  async function start(){renderEvidence();bind();if(!S||typeof S.make!=='function'){busy=false;setNotice('Runtime unavailable','The controller is missing from this build. The published source and qualification files remain available.','error');renderControls();return;}try{session=await S.make();noticeOverride={label:'Ready',detail:'The reviewed fixture is open. Correct its source, or run the complete exit test.',tone:'neutral'};}catch(e){setNotice('Unable to open fixture',e.message||String(e),'error');}finally{busy=false;render();}}
  start();
})();
