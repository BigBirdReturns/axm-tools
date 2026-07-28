function openDialog(mode,id){
  dialogMode={mode,id};const dialog=document.getElementById('editorDialog'),body=document.getElementById('dialogBody'),title=document.getElementById('dialogTitle'),kicker=document.getElementById('dialogKicker');kicker.textContent=mode.startsWith('edit')?'Edit':'Create';
  if(mode==='new-organ'||mode==='edit-organ'){
    const o=mode==='edit-organ'?organ(id):{id:'organ.',name:'',class:'service',stage:'germinal',mission:''};title.textContent=mode==='edit-organ'?'Edit organ':'Add organ';body.innerHTML=`<div class="field"><label>Stable ID</label><input class="input" name="id" value="${esc(o.id)}" ${mode==='edit-organ'?'readonly':''}></div><div class="field"><label>Name</label><input class="input" name="name" value="${esc(o.name)}" required></div><div class="grid two"><div class="field"><label>Class</label><input class="input" name="class" value="${esc(o.class)}"></div><div class="field"><label>Stage</label><select class="select" name="stage">${['germinal','emerging','load-bearing','mature','overloaded','redundant','vestigial','dormant','failing','retired'].map(v=>`<option ${o.stage===v?'selected':''}>${v}</option>`).join('')}</select></div></div><div class="field"><label>Mission</label><textarea class="textarea" name="mission">${esc(o.mission)}</textarea></div>`;
  }else if(mode==='new-candidate'){
    title.textContent='Add evolution candidate';body.innerHTML=`<div class="field"><label>Name</label><input class="input" name="name" required></div><div class="field"><label>Action</label><select class="select" name="action">${ACTIONS.map(v=>`<option>${v}</option>`).join('')}</select></div><div class="field"><label>Summary</label><textarea class="textarea" name="summary"></textarea></div>`;
  }else if(mode==='new-actor'||mode==='edit-actor'){
    const a=mode==='edit-actor'?actor(id):{id:'actor.',name:'',roles:[],authority:[]};title.textContent=mode==='edit-actor'?'Edit actor':'Add actor';body.innerHTML=`<div class="field"><label>Stable ID</label><input class="input" name="id" value="${esc(a.id)}" ${mode==='edit-actor'?'readonly':''}></div><div class="field"><label>Name</label><input class="input" name="name" value="${esc(a.name)}" required></div><div class="field"><label>Roles · comma separated</label><input class="input" name="roles" value="${esc((a.roles||[]).join(', '))}"></div><div class="field"><label>Authority · one per line</label><textarea class="textarea" name="authority">${esc((a.authority||[]).join('\n'))}</textarea></div><div class="field"><label>Self-declared interest</label><textarea class="textarea" name="interest">${esc(a.interests?.[0]?.claim||'')}</textarea></div>`;
  }else if(mode==='new-evidence'){
    title.textContent='Add evidence';body.innerHTML=`<div class="field"><label>Title</label><input class="input" name="title" required></div><div class="grid two"><div class="field"><label>Tier</label><select class="select" name="tier">${['confirmed','measured','reported','derived','judgment','open'].map(v=>`<option>${v}</option>`).join('')}</select></div><div class="field"><label>Independence</label><select class="select" name="independence">${['independent','mixed','self','unknown'].map(v=>`<option>${v}</option>`).join('')}</select></div></div><div class="field"><label>Source</label><input class="input" name="source"></div><div class="field"><label>Supported claim</label><textarea class="textarea" name="claim"></textarea></div><div class="field"><label>Limits</label><textarea class="textarea" name="limits"></textarea></div>`;
  }
  dialog.showModal();
}
function saveDialog(){
  const fd=new FormData(document.getElementById('editorForm'));const mode=dialogMode?.mode,id=dialogMode?.id;
  if(mode==='new-organ'){
    const name=fd.get('name').trim();const rid=(fd.get('id').trim()==='organ.'?'organ.'+slug(name):fd.get('id').trim());if(model.organs.some(o=>o.id===rid))return toast('That organ ID already exists.');
    const o={id:rid,name,class:fd.get('class').trim()||'service',stage:fd.get('stage'),mission:fd.get('mission').trim(),functions:[],inputs:[],outputs:[],dependencies:[],authority:{owns:[],forbidden:[]},custodians:{authors:[],maintainers:[],operators:[],stewards:[]},health:{function:2,authority:2,observability:2,adaptability:2,succession:2,replaceability:2,efficiency:2,containment:2},pressures:[]};model.organs.push(o);selectedOrganId=o.id;selectedCandidateId=null;
  }else if(mode==='edit-organ'){
    const o=organ(id);o.name=fd.get('name').trim();o.class=fd.get('class').trim();o.stage=fd.get('stage');o.mission=fd.get('mission').trim();
  }else if(mode==='new-candidate'){
    const name=fd.get('name').trim();const c={id:'candidate.'+slug(selectedOrganId.split('.').pop()+'.'+name),organId:selectedOrganId,name,action:fd.get('action'),summary:fd.get('summary').trim(),changes:{preserve:[],alter:[],retire:[],introduce:[]},dimensions:Object.fromEntries(DIMENSIONS.map(([k])=>[k,3])),gates:{function:'open',authority:'open',evidence:'open',migration:'open',reversibility:'open'},actorLinks:{sponsors:[],validators:[],deciders:[],beneficiaries:[]},evidenceIds:[],risks:[],dissent:[]};model.candidates.push(c);selectedCandidateId=c.id;
  }else if(mode==='new-actor'){
    const name=fd.get('name').trim();const rid=(fd.get('id').trim()==='actor.'?'actor.'+slug(name):fd.get('id').trim());if(model.actors.some(a=>a.id===rid))return toast('That actor ID already exists.');model.actors.push({id:rid,name,roles:fd.get('roles').split(',').map(x=>x.trim()).filter(Boolean),authority:fd.get('authority').split('\n').map(x=>x.trim()).filter(Boolean),interests:fd.get('interest').trim()?[{mode:'self_declared',claim:fd.get('interest').trim(),evidence:'Entered by the current operator.'}]:[]});
  }else if(mode==='edit-actor'){
    const a=actor(id);a.name=fd.get('name').trim();a.roles=fd.get('roles').split(',').map(x=>x.trim()).filter(Boolean);a.authority=fd.get('authority').split('\n').map(x=>x.trim()).filter(Boolean);a.interests=fd.get('interest').trim()?[{mode:'self_declared',claim:fd.get('interest').trim(),evidence:'Entered by the current operator.'}]:[];
  }else if(mode==='new-evidence'){
    const title=fd.get('title').trim();model.evidence.push({id:'evidence.'+slug(title),title,tier:fd.get('tier'),independence:fd.get('independence'),source:fd.get('source').trim(),claim:fd.get('claim').trim(),limits:fd.get('limits').trim()});
  }
  persist();render();document.getElementById('editorDialog').close();toast('Workspace updated.');
}
function fieldValue(id){return document.getElementById(id)?.value??'';}
function fieldLines(id){return fieldValue(id).split('\n').map(x=>x.trim()).filter(Boolean);}
function updateDecision(){
  const executionState=fieldValue('executionState')||'not_started';
  const execution=executionState==='not_started'?{state:'not_started'}:{state:executionState,authority:fieldValue('executionAuthority').trim(),implementationRefs:fieldLines('executionImplementationRefs'),verificationRefs:fieldLines('executionVerificationRefs')};
  if(['verified','failed'].includes(executionState)){execution.outcome=fieldValue('executionOutcome');execution.completedAt=fieldValue('executionCompletedAt').trim();}
  model.decision={
    organId:selectedOrganId,
    candidateId:fieldValue('decisionCandidate'),
    state:fieldValue('decisionState'),
    decider:fieldValue('decisionDecider'),
    decidedAt:fieldValue('decisionDecidedAt').trim(),
    mandateRef:fieldValue('decisionMandateRef').trim(),
    mandateBasis:fieldValue('decisionMandateBasis').trim(),
    rationale:fieldValue('decisionRationale').trim(),
    openQuestions:fieldLines('decisionQuestions'),
    circulation:{lane:fieldValue('circulationLane'),task:fieldValue('circulationTask').trim(),surface:fieldValue('circulationSurface').trim(),producer:fieldValue('circulationProducer').trim(),consumers:fieldLines('circulationConsumers'),blockedOn:fieldValue('circulationBlockedOn').trim()},
    execution,
  };
  selectedCandidateId=model.decision.candidateId;persist();render();toast('Decision record updated.');
}
function download(name,text,type='application/json'){
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},1000);
}
function exportJson(){download(`${slug(model.estate.name)}-organ-evolution.json`,JSON.stringify(model,null,2)+'\n');}
function exportMemo(){const text=document.getElementById('memo')?.innerText||'';download(`${slug(organ()?.name)}-evolution-memo.md`,text,'text/markdown');}
function exportCsv(){
  const rows=[['organ','candidate','action','posture',...DIMENSIONS.map(d=>d[0]),...GATES.map(g=>'gate_'+g[0]),'evidence_records','independent_anchor']];candidateSet().forEach(c=>{const e=evidenceStrength(c);rows.push([organ(c.organId)?.name,c.name,c.action,posture(c).label,...DIMENSIONS.map(([k])=>c.dimensions?.[k]??0),...GATES.map(([k])=>c.gates?.[k]||'open'),e.rows.length,e.independent])});
  const csv=rows.map(r=>r.map(v=>`"${String(v??'').replaceAll('"','""')}"`).join(',')).join('\n');download(`${slug(organ()?.name)}-candidate-comparison.csv`,csv,'text/csv');
}
async function exportDecisionJob(){
  try{
    const value=await window.AXM_DECISION_JOB.build(model);
    download(`${slug(organ()?.name)}-${slug(candidate()?.name)}-circulation-job.json`,JSON.stringify(value,null,2)+'\n');
    toast(`Circulation job exported: ${value.jobId.slice(0,22)}…`);
  }catch(error){toast(`Job export refused: ${error.message}`);}
}
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');clearTimeout(t._timer);t._timer=setTimeout(()=>t.classList.remove('show'),2200);}
function handleClick(e){
  const organBtn=e.target.closest('[data-organ]');if(organBtn){selectedOrganId=organBtn.dataset.organ;selectedCandidateId=candidateSet()[0]?.id;stressResults=null;render();return;}
  const map=e.target.closest('[data-map-organ]');if(map){selectedOrganId=map.dataset.mapOrgan;selectedCandidateId=candidateSet()[0]?.id;render();return;}
  const tab=e.target.closest('[data-view]');if(tab){currentView=tab.dataset.view;render();return;}
  const jump=e.target.closest('[data-view-jump]');if(jump){currentView=jump.dataset.viewJump;render();return;}
  const cand=e.target.closest('[data-candidate]');if(cand){selectedCandidateId=cand.dataset.candidate;render();return;}
  const addCandidate=e.target.closest('[data-add-candidate]');if(addCandidate){selectedOrganId=addCandidate.dataset.addCandidate;openDialog('new-candidate');return;}
  const editOrgan=e.target.closest('[data-edit-organ]');if(editOrgan){openDialog('edit-organ',editOrgan.dataset.editOrgan);return;}
  const editActor=e.target.closest('[data-edit-actor]');if(editActor){openDialog('edit-actor',editActor.dataset.editActor);return;}
  if(e.target.closest('[data-add-actor]')){openDialog('new-actor');return;}
  if(e.target.closest('[data-add-evidence]')){openDialog('new-evidence');return;}
  const delCand=e.target.closest('[data-delete-candidate]');if(delCand&&confirm('Delete this candidate from the local workspace?')){model.candidates=model.candidates.filter(c=>c.id!==delCand.dataset.deleteCandidate);selectedCandidateId=candidateSet()[0]?.id;persist();render();return;}
  const delEv=e.target.closest('[data-delete-evidence]');if(delEv&&confirm('Delete this evidence record from the local workspace?')){model.evidence=model.evidence.filter(x=>x.id!==delEv.dataset.deleteEvidence);model.candidates.forEach(c=>c.evidenceIds=(c.evidenceIds||[]).filter(id=>id!==delEv.dataset.deleteEvidence));persist();render();return;}
  if(e.target.id==='runStressBtn'){runStress();return;}
  if(e.target.id==='saveDecisionBtn'){updateDecision();return;}
  if(e.target.id==='exportMemoBtn'){exportMemo();return;}
  if(e.target.id==='exportCsvBtn'){exportCsv();return;}
  if(e.target.id==='exportJobBtn'){exportDecisionJob();return;}
}
function handleInput(e){
  const c=candidate();if(e.target.matches('[data-dimension]')&&c){c.dimensions[e.target.dataset.dimension]=Number(e.target.value);e.target.nextElementSibling.textContent=e.target.value;persist();return;}
  if(e.target.matches('[data-change]')&&c){c.changes[e.target.dataset.change]=e.target.value.split('\n').map(x=>x.trim()).filter(Boolean);persist();return;}
}
function handleChange(e){
  const c=candidate();if(e.target.matches('[data-gate]')&&c){c.gates[e.target.dataset.gate]=e.target.value;persist();render();return;}
  if(e.target.matches('[data-actor-link]')&&c){const k=e.target.dataset.actorLink,id=e.target.dataset.actorId;c.actorLinks[k]=c.actorLinks[k]||[];c.actorLinks[k]=e.target.checked?[...new Set([...c.actorLinks[k],id])]:c.actorLinks[k].filter(x=>x!==id);persist();render();return;}
  if(e.target.matches('[data-evidence-link]')&&c){const id=e.target.dataset.evidenceLink;c.evidenceIds=c.evidenceIds||[];c.evidenceIds=e.target.checked?[...new Set([...c.evidenceIds,id])]:c.evidenceIds.filter(x=>x!==id);persist();render();return;}
  if(e.target.id==='evidenceFilter'){document.getElementById('evidenceList').innerHTML=evidenceListHtml(e.target.value);return;}
}

document.addEventListener('click',handleClick);document.addEventListener('input',handleInput);document.addEventListener('change',handleChange);
document.getElementById('organSearch').addEventListener('input',renderRail);
document.getElementById('themeBtn').addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;localStorage.setItem('axm-organ-evolution-theme',next);});
document.getElementById('newOrganBtn').addEventListener('click',()=>openDialog('new-organ'));
document.getElementById('importBtn').addEventListener('click',()=>document.getElementById('fileInput').click());
document.getElementById('exportBtn').addEventListener('click',exportJson);
document.getElementById('resetBtn').addEventListener('click',()=>{if(confirm('Replace the local workspace with the worked example?')){model=clone(SEED);selectedOrganId=model.decision.organId;selectedCandidateId=model.decision.candidateId;stressResults=null;localStorage.removeItem(STORAGE_KEY);render();toast('Worked example restored.');}});
document.getElementById('fileInput').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const parsed=JSON.parse(await file.text());if(parsed.format!=='axm-organ-evolution/1'||!Array.isArray(parsed.organs)||!Array.isArray(parsed.candidates))throw new Error('unsupported format');model=parsed;selectedOrganId=model.decision?.organId||model.organs[0]?.id;selectedCandidateId=model.decision?.candidateId||model.candidates.find(c=>c.organId===selectedOrganId)?.id;stressResults=null;persist();render();toast(`Imported ${file.name}.`);}catch(err){toast(`Import refused: ${err.message}`);}e.target.value='';});
document.getElementById('editorForm').addEventListener('submit',e=>{e.preventDefault();saveDialog();});
renderTop();renderRail();render();
