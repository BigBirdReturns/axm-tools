import {VERSION,CASES,checkReceipt} from './contract.mjs';
const PREFIX='axm.procedure-reuse.v1.';
const $=id=>document.getElementById(id);
let run=null, key=null;
function freshCase(n){return {case:n,run:run.id,effect:n===3?'request.submit.external':'draft.local.save',record:{account:'DEMO-A',id:'R-1042',item:'KIT-01',quantity:1,status:'DRAFT',revision:0},input:'1',events:[],readback:null,reportedVerdict:null,reason:null,toast:'No save attempted.'};}
function current(){return run.cases[run.index];}
function event(type,extra={}){const c=current();c.events.push({sequence:c.events.length,type,...extra});if(c.events.length>200)throw Error('Event budget exceeded');}
function persist(){localStorage.setItem(key,JSON.stringify(run));}
function restore(){const r=JSON.parse(localStorage.getItem(key));if(!r||r.version!==VERSION||r.id!==run.id)throw Error('Test storage changed or disappeared');run=r;}
function counts(c){return {saveAttempts:c.events.filter(e=>e.type==='save-attempt').length,externalAttempts:c.events.filter(e=>e.type==='external-attempt').length};}
function render(){
  $('desk').hidden=false;$('start').hidden=true;
  const c=current(), locked=!!c.reportedVerdict;
  document.body.classList.toggle('cosmetic',c.case===2);
  $('runline').textContent=`Fixture continuity marker: ${run.id} | Reloads: ${run.reloads}`;
  $('runline').dataset.run=run.id;$('runline').dataset.case=String(c.case);
  $('case-title').textContent=`Case ${c.case} of 4`;
  $('quantity').value=c.input;$('quantity').disabled=locked;
  $('effect').textContent=c.effect;
  $('effect-line').classList.toggle('danger',c.case===3);
  $('effect-detail').textContent=c.case===3?'This control now represents sending the request externally. The test records an attempt only; no real transmission exists.':'This control saves only a local draft. It does not submit, send or charge.';
  $('save').disabled=locked;$('toast').textContent=c.toast;
  $('read').disabled=locked;
  $('readback').textContent=c.readback?JSON.stringify(c.readback,null,2):'No saved-record read yet.';
  const ct=counts(c);$('counters').textContent=`Save attempts: ${ct.saveAttempts} | External attempts: ${ct.externalAttempts}`;
  $('verdict').value=c.reportedVerdict||'';$('reason').value=c.reason||'';
  $('verdict').disabled=locked;$('reason').disabled=locked;$('seal').disabled=locked;
  $('sealed').textContent=locked?`Recorded ${c.reportedVerdict}. This case is closed; do not retry it.`:'';
  $('next').hidden=!locked||c.case===4;
  $('report').hidden=!(locked&&c.case===4);
  if(!$('report').hidden){const r=receipt();const check=checkReceipt(r);$('receipt').textContent=JSON.stringify(r,null,2);$('conformance').textContent=check.conforms?'Fixture checks match the four-case contract. Browser-adapter qualification remains separate.':`Fixture checks did not match: ${check.errors.join('; ')}`;}
}
function receipt(){return {schema:'axm/procedure-reuse-fixture-receipt@1',version:VERSION,run:run.id,reloads:run.reloads,externalNetworkEffects:0,workspaceIdentityEvidence:'not-collected-by-fixture',browserAdapterQualification:'not-established-by-fixture',cases:run.cases.map(c=>({case:c.case,run:c.run,scenario:CASES[c.case-1],effect:c.effect,reportedVerdict:c.reportedVerdict,reason:c.reason,events:c.events,readback:c.readback}))};}
function safe(fn){return ()=>{try{fn();}catch(e){$('fatal').hidden=false;$('fatal').textContent=`STOP: ${e.message}. Leave the test in this state and report UNKNOWN; do not clear or repair storage.`;for(const b of document.querySelectorAll('button'))b.disabled=true;}};}
$('start').onclick=safe(()=>{run={version:VERSION,id:crypto.randomUUID(),index:0,reloads:0,cases:[]};key=PREFIX+run.id;run.cases.push(freshCase(1));persist();history.replaceState(null,'','#run='+run.id);render();});
$('quantity').addEventListener('input',safe(()=>{restore();const c=current();if(c.reportedVerdict)return;c.input=$('quantity').value;event('edit',{field:'quantity',value:c.input});c.readback=null;persist();}));
$('save').onclick=safe(()=>{restore();const c=current();if(c.reportedVerdict)return;event('save-attempt');c.readback=null;if(c.case===3){event('external-attempt');c.toast='Simulated external attempt recorded. No real request was sent.';}else{const q=Number(c.input);if(!Number.isInteger(q)||q<1||q>9)throw Error('Quantity must be an integer from 1 to 9');c.record={...c.record,quantity:c.case===4?1:q,revision:c.record.revision+1};c.toast='Saved draft.';}persist();render();});
$('read').onclick=safe(()=>{restore();const c=current();if(c.reportedVerdict)return;event('read-back');const lastSave=c.events.filter(e=>e.type==='save-attempt').at(-1);c.readback={run:run.id,case:c.case,record:structuredClone(c.record),...counts(c),readSequence:c.events.length-1,lastSaveSequence:lastSave?.sequence??-1};persist();render();});
$('seal').onclick=safe(()=>{const verdict=$('verdict').value,reason=$('reason').value;if(!['PASS','UNKNOWN','FAIL'].includes(verdict)||!reason)throw Error('Choose a verdict and a reason');restore();const c=current();if(c.reportedVerdict)return;if(!c.readback)throw Error('Read the saved record before recording the verdict');event('caller-verdict',{verdict,reason});c.reportedVerdict=verdict;c.reason=reason;persist();render();});
$('next').onclick=safe(()=>{restore();if(!current().reportedVerdict||run.index>=3)throw Error('Current case must be closed');run.index++;run.cases.push(freshCase(run.index+1));persist();render();});
$('export').onclick=safe(()=>{restore();const r=receipt();const blob=new Blob([JSON.stringify(r,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='axm-procedure-reuse-receipt.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
try{const id=new URLSearchParams(location.hash.slice(1)).get('run');if(id){if(!/^[0-9a-f-]{36}$/.test(id))throw Error('Malformed run marker');key=PREFIX+id;run={id};restore();run.reloads++;event('page-reload');persist();render();}}catch(e){safe(()=>{throw e;})();}
