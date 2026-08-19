(()=>{
const CONFIG=window.MW_DREAMBOARD_CONFIG;
const capMap=Object.fromEntries(CONFIG.capacities.map(x=>[x.id,x]));
const programMap=Object.fromEntries(CONFIG.programs.map(x=>[x.id,x]));
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){
 $('#stickies').innerHTML=CONFIG.inputs.map((x,i)=>`<button class="sticky" style="--r:${[-1.1,.8,-.4,.7,-.8,.5,-.2,1,-.7,.5,-.4,.9][i]}deg" type="button" data-kind="input" data-id="${x.id}" aria-pressed="false">${esc(x.label)}</button>`).join('');
 const left=CONFIG.capacities.slice(0,4),right=CONFIG.capacities.slice(4);
 const capHTML=x=>`<button class="cap" type="button" data-kind="capacity" data-id="${x.id}"><span class="ico">${x.icon}</span><span>${esc(x.label)}</span></button>`;
 $('#cap-left').innerHTML=left.map(capHTML).join(''); $('#cap-right').innerHTML=right.map(capHTML).join('');
 $('#job-list').innerHTML=CONFIG.jobs.map(x=>`<button class="job" type="button" data-kind="job" data-id="${x.id}"><span>${x.icon}</span><b>${esc(x.label)}</b></button>`).join('');
 $('#program-row').innerHTML=CONFIG.programs.map(x=>`<button class="program" type="button" data-kind="program" data-id="${x.id}"><span class="ico">${x.icon}</span><b>${esc(x.label)}</b><small>${esc(x.note)}</small></button>`).join('')+`<button class="dashboard" type="button" data-kind="dashboard" data-id="dashboard"><b>Fundraising dashboard</b><small>Money and support lens</small><em>Important, but only one projection of the whole system.</em></button>`;
 $('#rules').innerHTML=CONFIG.rules.map(x=>`<button class="rule" type="button" data-kind="rule" data-id="${x.id}"><span class="ico">${x.icon}</span><span><b>${esc(x.label)}</b><p>${esc(x.note)}</p></span></button>`).join('');
 $('#proof').innerHTML=CONFIG.receipts.map(x=>{const tag=x.url?'a':'button';const attrs=x.url?`href="${x.url}" target="_blank" rel="noopener"`:`type="button" data-kind="receipt" data-id="${x.id}"`;return `<${tag} class="receipt" ${attrs}><span class="state ${x.state==='LOCAL'||x.state==='REVIEW'?'local':''}">${x.state}</span><span><b>${esc(x.label)}</b><p>${esc(x.note)}</p></span></${tag}>`}).join('');
}
function clearHighlight(){ $$('.active,.dim').forEach(el=>el.classList.remove('active','dim')); $$('.sticky[aria-pressed="true"]').forEach(el=>el.setAttribute('aria-pressed','false')); }
function dimOthers(selector,activeIds){ $$(selector).forEach(el=>{const id=el.dataset.id;if(activeIds.includes(id))el.classList.add('active');else el.classList.add('dim')}) }
function detail(kicker,title,summary,cards){ $('#detail-kicker').textContent=kicker;$('#detail-title').textContent=title;$('#detail-summary').textContent=summary;$('#detail-grid').innerHTML=cards.map(c=>`<div class="detail-card"><span>${esc(c.label)}</span><b>${esc(c.value)}</b></div>`).join(''); }
function select(kind,id,push=true){
 clearHighlight(); let focus=id;
 if(kind==='input'){
  const x=CONFIG.inputs.find(v=>v.id===id);const b=$(`[data-kind="input"][data-id="${id}"]`);b.classList.add('active');b.setAttribute('aria-pressed','true');
  dimOthers('.cap',x.target);dimOthers('.program',x.programs);
  detail('Arrived as',x.label,x.resolution,[{label:'Resolves into',value:x.target.map(v=>capMap[v].label).join(' · ')},{label:'Program organs',value:x.programs.map(v=>programMap[v].label).join(' · ')},{label:'Control question',value:'Which layer owns the fact when the current app changes?'}]);
 } else if(kind==='capacity'){
  const x=capMap[id];const programs=CONFIG.programs.filter(p=>p.capacities.includes(id));dimOthers('.cap',[id]);dimOthers('.program',programs.map(p=>p.id));
  detail('Capacity class',x.label,x.desc,[{label:'Used by',value:programs.map(p=>p.label).join(' · ')},{label:'Canonical question',value:'Who can provide it, who needs it, what authority governs the handoff, and what event proves movement?'},{label:'Accounting',value:'A capacity class is broader than money or bilateral barter.'}]);
 } else if(kind==='program'){
  const x=programMap[id];dimOthers('.program',[id]);dimOthers('.cap',x.capacities);
  detail('Program organ',x.label,x.note,[{label:'Manzanita owns',value:x.own},{label:'Commodity machinery',value:x.commodity},{label:'Next safe action',value:x.next}]);
 } else if(kind==='dashboard'){
  $('.dashboard').classList.add('active');dimOthers('.program',['money']);dimOthers('.cap',['money']);
  detail('Subordinate lens','Fundraising dashboard','The dashboard is valuable only when it projects the institution’s own identity, purpose, project, restriction, processor, and receipt model.',[{label:'Canonical fields',value:'Constituent · purpose · project · restriction · processor · receipt'},{label:'It may do',value:'Visualize dues, rentals, donations, campaigns, grants, restrictions, reconciliation, and gaps.'},{label:'It may not do',value:'Become the organizational database or manufacture authority, acceptance, or identity.'}]);focus='fundraising';
 } else if(kind==='job'){
  const x=CONFIG.jobs.find(v=>v.id===id);$(`[data-kind="job"][data-id="${id}"]`).classList.add('active');
  detail('Institutional architecture',x.label,x.summary,[{label:'Mechanism',value:x.mechanism},{label:'Receipt',value:x.receipt},{label:'Control question',value:'Can the next person reproduce the reasoning without relying on charisma or vendor memory?'}]);
 } else if(kind==='rule'){
  const x=CONFIG.rules.find(v=>v.id===id);$(`[data-kind="rule"][data-id="${id}"]`).classList.add('active');
  detail('Sovereignty rule',x.label,x.note,[{label:'Mechanism',value:x.detail},{label:'Failure mode',value:'A supplier, dashboard, or informal relationship becomes the only place the organization can reconstruct itself.'},{label:'Required property',value:'Portable, source-bound, role-aware, replaceable, and recoverable.'}]);
 } else if(kind==='receipt'){
  const x=CONFIG.receipts.find(v=>v.id===id);$(`[data-kind="receipt"][data-id="${id}"]`)?.classList.add('active');
  detail('Proof of work',x.label,x.note,[{label:'Standing',value:x.state},{label:'What it proves',value:x.id==='commons'?'The method reaches a governed transaction substrate, not only a diagram.':'The method has already been applied to a concrete operating organ.'},{label:'Boundary',value:'A prototype or live public object does not create Manzanita Works organizational acceptance.'}]);
 } else {
  $('#core').classList.add('active');
  detail('Operating fabric','The organization is the system.','The shared substrate connects people, authority, information, technology, physical resources, and money while keeping every supplier replaceable.',[{label:'Own',value:'Identity · authority · projects · semantics · accepted events · receipts'},{label:'Wrap',value:'Inventory · payments · fundraising · scheduling · messaging · hardware'},{label:'Outcome',value:'Programs can share capacity without collapsing their distinct rules.'}]);focus='overview';
 }
 if(push){const u=new URL(location.href);u.searchParams.set('focus',focus);history.replaceState(null,'',u)}
 if(matchMedia('(max-width:760px)').matches) $('#detail').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'nearest'});
}
function exportModel(){const payload={schema:'manzanita-works/operating-dreamboard@0.2',exported_at:new Date().toISOString(),release:CONFIG.release,public_boundary:'Synthetic public-safe architecture. No member, victim-service, payment, custody, credit, or organizational-acceptance records.',model:CONFIG};const blob=new Blob([JSON.stringify(payload,null,2)+'\n'],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='Manzanita_Works_Operating_Fabric_v0.2.0.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}
function focusFromURL(){const f=new URL(location.href).searchParams.get('focus');if(!f||f==='overview')return select('core','core',false);if(f==='fundraising')return select('dashboard','dashboard',false);if(capMap[f])return select('capacity',f,false);if(programMap[f])return select('program',f,false);const input=CONFIG.inputs.find(x=>x.id===f);if(input)return select('input',f,false);const job=CONFIG.jobs.find(x=>x.id===f);if(job)return select('job',f,false);const rule=CONFIG.rules.find(x=>x.id===f);if(rule)return select('rule',f,false);select('core','core',false)}
render();
$('#board').addEventListener('click',e=>{const b=e.target.closest('[data-kind]');if(b)select(b.dataset.kind,b.dataset.id)});
$('#focus-fundraising').onclick=()=>select('dashboard','dashboard');
$('#show-proof').onclick=()=>{$('#proof-band').scrollIntoView({behavior:'smooth'});select('receipt','place')};
$('#reset').onclick=()=>select('core','core');
$('#export').onclick=exportModel;
$('#theme').onclick=()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;localStorage.setItem('mw-dreamboard-theme',next)};
const saved=localStorage.getItem('mw-dreamboard-theme');if(saved)document.documentElement.dataset.theme=saved;else if(matchMedia('(prefers-color-scheme:dark)').matches)document.documentElement.dataset.theme='dark';
$('#share').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);$('#share').textContent='Copied';setTimeout(()=>$('#share').textContent='Copy view',1200)}catch{prompt('Copy this view',location.href)}};
window.addEventListener('popstate',focusFromURL);focusFromURL();
})();
