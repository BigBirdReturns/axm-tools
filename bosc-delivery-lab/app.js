'use strict';
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=value=>typeof value==='string'?value:JSON.stringify(value,null,2);
const badge=(state,label=state)=>'<span class="status '+esc(state)+'">'+esc(String(label).replaceAll('_',' '))+'</span>';
let D,selectedCase='C07';
const tabs=[...document.querySelectorAll('[role=tab]')];
function showTab(name){
 if(!tabs.some(t=>t.getAttribute('aria-controls')===name))name='workflow';
 tabs.forEach(t=>{const on=t.getAttribute('aria-controls')===name;t.setAttribute('aria-selected',String(on));t.tabIndex=on?0:-1;$(t.getAttribute('aria-controls')).hidden=!on;});
}
function route(){const [name,id]=location.hash.slice(1).split('/');showTab(name||'workflow');if(D&&name==='acceptance'&&id&&D.acceptance.cases.some(c=>c.id===id)){selectedCase=id;$('case-filter').value='';renderCases();selectCase(id);}}
tabs.forEach((tab,i)=>{tab.addEventListener('click',()=>{location.hash=tab.getAttribute('aria-controls');});tab.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const n=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;location.hash=tabs[n].getAttribute('aria-controls');tabs[n].focus();}});});
window.addEventListener('hashchange',route);route();
function renderCases(){const query=$('case-filter').value.trim().toLowerCase();const matches=D.acceptance.cases.filter(c=>(c.id+' '+c.name+' '+c.criterion).toLowerCase().includes(query));$('case-count').textContent=matches.length+' of 19 scenarios';$('case-list').innerHTML=matches.map(c=>'<button class="case-button" type="button" data-case="'+esc(c.id)+'" aria-pressed="'+String(c.id===selectedCase)+'"><span class="code">'+esc(c.id)+'</span><span class="name">'+esc(c.name)+'</span>'+badge(c.status)+'</button>').join('')||(query?'<p class="subtle">No matching scenarios.</p>':'');}
function shortValue(value){if(value&&typeof value==='object'&&value.projection==='summary')return fmt(value);return fmt(value);}
function selectCase(id){const c=D.acceptance.cases.find(x=>x.id===id);if(!c)return;selectedCase=id;$('case-list').querySelectorAll('[data-case]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.case===id)));$('case-detail').innerHTML='<span class="kicker">'+esc(c.id)+' / '+esc(c.group)+' acceptance</span><h3>'+esc(c.name)+'</h3>'+badge(c.status,c.status==='pass'?'Acceptance passed':'Acceptance '+c.status.replaceAll('_',' '))+'<p>'+esc(c.criterion)+'</p><div class="case-meta"><span>'+esc(c.assertion_count)+' assertions</span><span>'+esc(c.operation_count)+' observed operations</span><span>'+esc(c.elapsed_ms)+' ms for this case</span></div><p class="subtle">'+esc(c.boundary)+'</p><ul class="assertion-list">'+c.assertions.map(a=>'<li><div class="assertion-top">'+badge(a.status)+'<strong>'+esc(a.name)+'</strong></div><div class="assertion-values"><span>Expected: '+esc(shortValue(a.expected))+'</span><span>Observed: '+esc(shortValue(a.actual))+'</span></div>'+(a.value_projection==='exact'?'':'<p class="subtle">Bulk state is summarized; original-value hashes remain in the evidence JSON.</p>')+'</li>').join('')+'</ul>';}
const scenarioLabels={book:'Booking',duplicate:'Duplicate request','false-success':'False success',uncertain:'Lost reply'};
function showScenario(id){const s=D.scenarios.find(x=>x.id===id);if(!s)return;$('scenario-choices').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===id)));const o=s.outcome;$('scenario-result').innerHTML='<h2>'+esc(s.name)+'</h2><p class="run-description">'+esc(s.description)+'</p><div class="run-counts"><div><strong>'+o.appointment_count+'</strong><span>Appointments</span></div><div><strong>'+o.command_count+'</strong><span>Committed commands</span></div><div><strong>'+o.human_queue_count+'</strong><span>Human review items</span></div></div><div class="run-bottom">'+badge(o.state)+'<small>'+esc(s.elapsed_ms)+' ms · '+s.checks.filter(check=>check.status==='pass').length+' / '+s.checks.length+' checks passed</small></div><details><summary class="run-receipt-toggle">Inspect the recorded receipt</summary><pre class="assertion-values">'+esc(JSON.stringify({scenario:s.id,outcome:s.outcome,attempts:s.attempts,checks:s.checks,original_receipt_sha256:s.original_receipt_sha256},null,2))+'</pre></details>';}
function safeUrl(value){try{const url=new URL(value);return url.protocol==='https:'?url.href:'#';}catch{return '#';}}
function render(){
 $('metrics').innerHTML=D.metrics.map(m=>'<div class="metric"><div class="metric-label">'+esc(m.label)+'</div><div class="metric-value">'+esc(m.value)+'</div><div class="metric-note">'+esc(m.note)+'</div></div>').join('');
 $('scenario-choices').innerHTML=D.scenarios.map(s=>'<button type="button" data-scenario="'+esc(s.id)+'" aria-pressed="false">'+esc(scenarioLabels[s.id]||s.name)+'</button>').join('');showScenario('book');
 $('workflow-cards').innerHTML=D.workflow.map((s,i)=>'<article class="workflow-card"><div class="stage-index"><span>0'+(i+1)+'</span>'+esc(s.role)+'</div><h3>'+esc(s.title)+'</h3><p>'+esc(s.description)+'</p></article>').join('');
 $('scope-list').innerHTML=D.metadata.scope_list.map(s=>'<li>'+esc(s)+'</li>').join('');
 $('acceptance-caption').textContent=D.acceptance.caption;
 $('negative-control').textContent=D.acceptance.negative_control;
 renderCases();selectCase(selectedCase);
 $('model-caption').textContent=D.model.caption;
 $('failure-input').textContent='“'+D.model.failure.text+'”';
 const wrong=D.model.failure.actual;$('failure-proposal').textContent=wrong.action==='book'?'Book at '+wrong.start.slice(11,16):fmt(wrong);
 $('model-summary').textContent=D.model.summary;
 $('confirmation-summary').textContent=D.confirmation.summary;
 $('confirmation-boundary').textContent=D.confirmation.boundary;
 $('model-rows').innerHTML=D.model.cases.map(c=>'<tr class="'+(c.status==='fail'?'model-fail':'')+'"><td><strong>'+esc(c.id)+'</strong><div class="sub">'+esc(c.text)+'</div></td><td><code>'+esc(fmt(c.expected))+'</code></td><td><code>'+esc(fmt(c.actual))+'</code><div class="sub">'+esc(c.elapsed_ms)+' ms</div></td><td>'+badge(c.status,c.status==='fail'?'Mismatch':'Matched')+'</td></tr>').join('');
 $('confirmation-cases').innerHTML=D.confirmation.cases.map(c=>'<article class="confirmation-item"><h4>'+esc(c.id)+' · '+esc(c.name)+'</h4>'+badge(c.status)+'<p>Result: <strong>'+esc(c.result.state.replaceAll('_',' '))+'</strong> · Worker invoked: <strong>'+String(c.result.worker_invoked)+'</strong> · Appointments: <strong>'+c.before.appointments+' → '+c.after.appointments+'</strong></p></article>').join('');
 $('handover-summary').textContent=D.handover.summary;$('reuse-summary').textContent=D.reuse.summary;
 $('limits').innerHTML=D.limits.map(s=>'<li>'+esc(s)+'</li>').join('');
 $('source-list').innerHTML=D.sources.map((s,i)=>'<article class="source-card"><div class="source-type">'+String(i+1).padStart(2,'0')+' / '+esc(s.classification.replaceAll('_',' '))+'</div><h3>'+esc(s.title)+'</h3><p>'+esc(s.observation)+'</p><a href="'+esc(safeUrl(s.url))+'" target="_blank" rel="noopener noreferrer">Read the primary source ↗</a></article>').join('');
 $('provenance-rows').innerHTML=D.provenance.original_receipts.map(r=>'<tr><td>'+esc(r.artifact)+'</td><td class="hash">'+esc(r.sha256)+'</td></tr>').join('');
 route();document.documentElement.dataset.ready='true';
}
$('scenario-choices').addEventListener('click',event=>{const button=event.target.closest('[data-scenario]');if(button&&D)showScenario(button.dataset.scenario);});
$('case-list').addEventListener('click',event=>{const button=event.target.closest('[data-case]');if(button&&D){selectCase(button.dataset.case);history.replaceState(null,'','#acceptance/'+button.dataset.case);}});
$('case-filter').addEventListener('input',()=>{if(D)renderCases();});
fetch('./evidence.json').then(response=>{if(!response.ok)throw new Error('Evidence request returned '+response.status);return response.json();}).then(data=>{if(data.schema!=='axm.public-evidence-projection/1'||data.acceptance.cases.length!==19||data.model.cases.length!==16)throw new Error('Evidence shape does not match this review');D=data;render();}).catch(error=>{$('load-error').hidden=false;$('load-error').textContent='The retained evidence could not load. Reload the page, or use the evidence JSON and source downloads below. '+error.message;$('scenario-result').innerHTML='<p class="loading">Recorded evidence is currently unavailable.</p>';});
