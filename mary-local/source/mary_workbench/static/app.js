'use strict';
(() => {
 const $=id=>document.getElementById(id), terminal=new Set(['completed','failed','cancelled','needs_context','paused','interrupted']);
 let token=location.hash.slice(1)||sessionStorage.getItem('mary_token')||'', timer=null, polling=false;
 const active=new Set(), uncertain=new Map();
 if(location.hash) history.replaceState(null,'',location.pathname);
 if(token) sessionStorage.setItem('mary_token',token);
 const notice=(s,bad=false)=>{ $('notice').textContent=s||''; $('notice').className=bad?'error':'notice'; };
 async function api(path,options={},binary=false){
   const control=new AbortController(),timeout=setTimeout(()=>control.abort(),30000);
   const headers={Authorization:'Bearer '+token,...(options.headers||{})};
   let body=options.body;
   if(body!==undefined && !(body instanceof Blob) && !(body instanceof ArrayBuffer)){headers['Content-Type']='application/json';body=JSON.stringify(body);}
   try {
     const response=await fetch(path,{...options,headers,body,signal:control.signal,credentials:'omit',cache:'no-store',redirect:'error'});
     if(!response.ok){let message='Request refused ('+response.status+').';try{const d=await response.json();message=d.error||d.detail||message;}catch(_){};throw new Error(message);}
     return binary?await response.blob():await response.json();
   } finally {clearTimeout(timeout);}
 }
 function tab(name){
   document.querySelectorAll('.tab').forEach(e=>e.classList.toggle('active',e.id===name));
   document.querySelectorAll('[role=tab]').forEach(e=>{e.setAttribute('aria-selected',String(e.dataset.tab===name));e.tabIndex=e.dataset.tab===name?0:-1;});
 }
 document.querySelectorAll('[role=tab]').forEach((b,index,all)=>{
   b.onclick=()=>tab(b.dataset.tab);
   b.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const next=all[(index+(e.key==='ArrowRight'?1:all.length-1))%all.length];next.focus();tab(next.dataset.tab);}};
 });
 function text(tag,value,cls){const e=document.createElement(tag);e.textContent=value??'';if(cls)e.className=cls;return e;}
 function button(label,operation){const b=text('button',label);b.type='button';b.onclick=async()=>{b.disabled=true;try{await operation();}catch(e){notice(e.message,true);}finally{b.disabled=false;}};return b;}
 async function download(path,name){const blob=await api(path,{},true),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function sourceRows(items){
   const selected=new Set([...document.querySelectorAll('#sourceChecks input:checked')].map(x=>x.value));
   $('sourceRows').replaceChildren();$('sourceChecks').replaceChildren();
   for(const source of items){
     const row=document.createElement('tr');for(const v of [source.name,source.status,source.versions,source.format])row.append(text('td',v));
     const actions=document.createElement('td');
     if(source.status==='current'){
       actions.append(button('Open original',()=>download('/api/source/'+source.id+'/original',source.name)));
       actions.append(button('Withdraw',async()=>{if(confirm('Exclude this source from current answers? Its original and history remain in your custody.')){await api('/api/source/'+source.id+'/withdraw',{method:'POST',body:{}});await refresh();}}));
       const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.value=source.id;check.checked=selected.has(source.id);label.append(check,document.createTextNode(source.name));$('sourceChecks').append(label);
     }
     row.append(actions);$('sourceRows').append(row);
   }
   if(!items.length)$('sourceChecks').append(text('p','Add files in Sources. Calculation works without a model or document.','small'));
 }
 function renderResult(card,job){
   const result=job.result;if(!result)return;
   let structured=result.structured;
   if(!structured&&result.text){try{structured=JSON.parse(result.text);}catch(_){}}
   if(structured?.kind==='calculation'){
     card.append(text('h3',structured.exact));card.append(text('p',structured.input+' = '+structured.exact));
     if(structured.decimal!==structured.exact)card.append(text('p','Decimal: '+structured.decimal,'small'));
   }else if(structured?.kind==='equation'){
     card.append(text('h3',structured.status==='conditional'?'Conditional result':'x = '+structured.solutions.join(', ')));
     card.append(text('p',structured.input));if(structured.condition)card.append(text('p',structured.condition));
   }else if(structured?.kind==='table'){
     card.append(text('h3',structured.operation.replaceAll('_',' ')+' · '+(structured.column||'all columns')));
     card.append(text('p',structured.row_count+' rows examined in '+structured.source_name));
     if(structured.metrics?.value!==undefined)card.append(text('p','Result: '+structured.metrics.value));
     if(structured.rows?.length&&structured.rows.length<=100){const t=document.createElement('table'),head=document.createElement('tr'),keys=Object.keys(structured.rows[0]);for(const k of keys)head.append(text('th',k));t.append(head);for(const r of structured.rows){const tr=document.createElement('tr');for(const k of keys)tr.append(text('td',r[k]));t.append(tr);}card.append(t);}
     for(const warning of structured.warnings||[])card.append(text('p',warning,'small'));
   }else if(job.kind==='upload'){
     card.append(text('h3',structured?.name||'Source added'));
     card.append(text('p','Original preserved; verified text is available to current work.'));
     if(structured?.coverage==='partial')card.append(text('p','Extraction is partial. Open the record for coverage details.','error'));
   }else if(job.kind==='import'){
     card.append(text('p',(structured?.admitted||0)+' new sources retained · '+(structured?.reused||0)+' reused · '+(structured?.processed||0)+' examined'));
     if(structured?.errors?.length)card.append(text('p',structured.errors.length+' source errors remain visible in the record.','error'));
   }else if(job.kind==='qualify'){
     const cases=structured?.cases||[],passed=cases.filter(x=>x.passed).length;
     card.append(text('h3',passed+' / '+cases.length+' calibration cases passed'));
     card.append(text('p',structured?.scope||'Task-scoped local model calibration.','small'));
   }else if(job.kind==='prepare-cpu'){
     card.append(text('p','Local CPU worker prepared: '+(structured?.model||'')));
     card.append(text('p',structured?.next||'Run Qualify before semantic work.'));
   }else if(job.kind==='prepare-recovery')card.append(text('p','Encrypted recovery tool prepared. Choose your backup destination and password.'));
   else if(job.kind==='backup'){
     card.append(text('h3','Encrypted context snapshot retained'));
     card.append(text('p',(structured?.files||0)+' files · snapshot '+(structured?.snapshot_id||'').slice(0,12)));
     card.append(text('p','Retain the password separately and test restoration from the backup device.','small'));
   }else if(result.text)card.append(text('pre',result.text));
   const details=document.createElement('details');details.append(text('summary','Evidence, scope and machine-readable record'),text('pre',JSON.stringify(result,null,2)));card.append(details);
 }
 function jobs(items){
   $('jobs').replaceChildren();
   if(!items.length){$('jobs').append(text('p','Your requests, accepted steps and outputs will remain here.','small'));return;}
   for(const job of items.slice(0,30)){
     const card=document.createElement('section');card.className='job'+(terminal.has(job.status)?' terminal':'');card.setAttribute('aria-label','Work '+job.id);
     card.append(text('strong',job.status+' · '+job.phase));card.append(text('div',job.message));card.append(text('div',job.id,'small'));
     if(job.error)card.append(text('p',job.error,'error'));
     renderResult(card,job);
     if(job.result?.standing)card.append(text('p',job.result.standing,'small'));
     const controls=document.createElement('div');controls.className='actions';
     for(const artifact of job.artifacts||[])controls.append(button('Save '+artifact.name,()=>download('/api/artifact/'+job.id+'/'+encodeURIComponent(artifact.name),artifact.name)));
     if(['running','queued'].includes(job.status))controls.append(button('Stop this work',async()=>{await api('/api/work/'+job.id+'/cancel',{method:'POST',body:{}});active.add(job.id);watch();}));
     if(['paused','interrupted','cancelled','failed','needs_context'].includes(job.status)&&job.kind!=='backup')controls.append(button('Resume same work',async()=>{await api('/api/work/'+job.id+'/resume',{method:'POST',body:{}});active.add(job.id);watch();}));
     card.append(controls);$('jobs').append(card);
   }
 }
 function hardware(data){
   const box=$('hardwareView');box.replaceChildren();
   if(!data.system){box.append(text('p','Scan this machine to see current resources and ODS model candidates.'));return;}
   box.append(text('strong',data.system+' '+data.architecture+' · '+data.logical_cpus+' logical CPUs'));
   box.append(text('p',(data.ram_bytes/1073741824).toFixed(1)+' GiB RAM · '+(data.available_ram_bytes/1073741824).toFixed(1)+' GiB currently available'));
   for(const gpu of data.gpus||[])box.append(text('p',(gpu.name||gpu.supplier+' '+gpu.pci_device)+(gpu.vram_mib?' · '+(gpu.vram_mib/1024).toFixed(1)+' GiB device memory':'')));
   const candidate=data.ods_candidate;
   if(candidate?.selected)box.append(text('p','ODS candidate: '+(candidate.selected.name||candidate.selected.id)+'. '+candidate.reason));
   box.append(text('p','A scan or memory-fit estimate does not qualify a task. The selected runtime is tested separately.','small'));
   const details=document.createElement('details');details.append(text('summary','Observed details and provenance'),text('pre',JSON.stringify(data,null,2)));box.append(details);
 }
 async function refresh(){
   if(!token){$('auth').hidden=false;return;}
   try {
     const state=await api('/api/status'),sources=await api('/api/sources');$('auth').hidden=true;$('conn').textContent='Local workspace · '+state.owner;$('conn').className='status ok';
     sourceRows(sources.items||[]);jobs(state.jobs||[]);hardware(state.hardware||{});
     $('fit').textContent=(state.model.configured?'Connected model: '+state.model.model:'No model connected. Exact tools remain available.')+(state.model.qualified?' · calibration passed':' · semantic work requires calibration');
     for(const job of state.jobs||[]){if(['running','queued'].includes(job.status))active.add(job.id);else active.delete(job.id);if(uncertain.has(job.id))uncertain.delete(job.id);}
     watch();
   } catch(e){$('conn').textContent='Connection needs attention';$('conn').className='status bad';$('auth').hidden=false;notice(e.message,true);}
 }
 function watch(){if(timer||!active.size||document.hidden)return;timer=setTimeout(poll,1500);}
 async function poll(){
   timer=null;if(polling||document.hidden||!active.size)return;polling=true;
   try{for(const id of [...active]){const job=await api('/api/work/'+id);if(terminal.has(job.status))active.delete(id);}await refresh();}
   catch(e){active.clear();notice(e.message+' Refresh status before starting a replacement request.',true);}
   finally{polling=false;watch();}
 }
 async function submitOperation(path,payload,label){
   const id=payload.request_id||crypto.randomUUID();payload.request_id=id;uncertain.set(id,{path,payload:Object.fromEntries(Object.entries(payload).filter(([k])=>!['password','api_key'].includes(k)))});
   try{const value=await api(path,{method:'POST',body:payload});uncertain.delete(id);active.add(value.job_id);notice(label+' retained as '+value.job_id);await refresh();tab('work');watch();return value;}
   catch(e){notice(e.message+' Request identity '+id+' is retained in this session. Refresh status before retrying.',true);throw e;}
 }
 $('connect').onclick=async()=>{const b=$('connect');b.disabled=true;try{token=$('token').value.trim();sessionStorage.setItem('mary_token',token);$('token').value='';await refresh();}finally{b.disabled=false;}};
 $('refresh').onclick=()=>refresh();
 $('submitWork').onclick=async()=>{
   const b=$('submitWork');b.disabled=true;
   try{
     const action=$('action').value,options={};
     if(action==='table'){options.operation=$('tableOp').value;if($('column').value)options.column=$('column').value;if($('group').value)options.group_by=$('group').value;if($('sheet').value)options.sheet=$('sheet').value;}
     const message=$('request').value.trim()||(action==='table'?'Analyze the selected table':'');if(!message)throw new Error('Describe the work first.');
     await submitOperation('/api/work',{request_id:crypto.randomUUID(),message,action,source_ids:[...document.querySelectorAll('#sourceChecks input:checked')].map(x=>x.value),options},'Work');
   }catch(e){notice(e.message,true);}finally{b.disabled=false;}
 };
 $('action').onchange=()=>{$('tableOptions').hidden=$('action').value!=='table';};
 async function upload(files){
   $('files').disabled=true;let completed=0;
   try{
     for(const file of files){
       if(file.size>67108864)throw new Error(file.name+' exceeds the 64 MiB file limit.');
       const id=crypto.randomUUID(),bytes=await file.arrayBuffer(),digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
       $('progress').hidden=false;$('progress').value=100*completed/files.length;
       const result=await api('/api/upload',{method:'POST',body:bytes,headers:{'Content-Type':'application/octet-stream','X-Mary-Filename':encodeURIComponent(file.name),'X-Mary-Request-ID':id,'X-Mary-SHA256':digest}});
       active.add(result.job_id);completed++;$('progress').value=100*completed/files.length;
     }
     notice(completed+' files received. Source acceptance is shown in the work records.');await refresh();watch();
   }catch(e){notice(e.message,true);}finally{$('files').disabled=false;$('files').value='';}
 }
 $('files').onchange=e=>upload([...e.target.files]);$('drop').ondragover=e=>e.preventDefault();$('drop').ondrop=e=>{e.preventDefault();upload([...e.dataTransfer.files]);};
 $('import').onclick=async()=>{const b=$('import');b.disabled=true;try{await submitOperation('/api/import',{request_id:crypto.randomUUID(),path:$('importPath').value},'Source import');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('scan').onclick=async()=>{const b=$('scan');b.disabled=true;try{hardware(await api('/api/hardware'));notice('Read-only hardware observation completed.');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('discover').onclick=async()=>{const b=$('discover');b.disabled=true;try{const d=await api('/api/models/discover');$('discovered').replaceChildren();for(const m of d.items||[])$('discovered').append(button(m.model+' · '+m.base_url,()=>{$('base').value=m.base_url;$('model').value=m.model;$('transport').value=m.transport;}));if(!d.items?.length)notice('No direct local runtime answered. Start ODS or the included CPU runtime profile, then discover again.');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('prepareCpu').onclick=async()=>{if(!confirm('Download a pinned local model (about 1.3–2.8 GB) and CPU runtime? Sources stay on this machine. This creates no background service and changes no GPU settings.'))return;const b=$('prepareCpu');b.disabled=true;try{await submitOperation('/api/prepare-local',{request_id:crypto.randomUUID()},'Local CPU worker setup');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('prepareRecovery').onclick=async()=>{if(!confirm('Download the pinned restic recovery tool (about 10 MB)?'))return;const b=$('prepareRecovery');b.disabled=true;try{await submitOperation('/api/prepare-recovery',{request_id:crypto.randomUUID()},'Recovery preparation');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('configure').onclick=async()=>{const b=$('configure');b.disabled=true;try{await api('/api/model',{method:'POST',body:{base_url:$('base').value,model:$('model').value,transport:$('transport').value,api_key:$('apiKey').value,allow_private_network:$('private').checked}});$('apiKey').value='';notice('Local runtime configured. Qualify its semantic task profile next.');await refresh();}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('qualify').onclick=async()=>{const b=$('qualify');b.disabled=true;try{await submitOperation('/api/qualify',{request_id:crypto.randomUUID()},'Qualification');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 $('backup').onclick=async()=>{const b=$('backup');b.disabled=true;const password=$('backupPass').value;$('backupPass').value='';try{await submitOperation('/api/backup',{request_id:crypto.randomUUID(),repository:$('repo').value,password},'Encrypted backup');}catch(e){notice(e.message,true);}finally{b.disabled=false;}};
 document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(timer);timer=null;}else watch();});
 refresh();
})();
