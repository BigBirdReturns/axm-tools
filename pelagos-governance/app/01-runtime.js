'use strict';
const RELEASE = 'DDV-PEL-003/0.3.0';
const WORKSPACE_SCHEMA = 'ddv/pelagos-governance-workspace@3';
const ENCRYPTED_SCHEMA = 'ddv/pelagos-governance-encrypted-backup@1';
const PUBLIC = Object.freeze(window.__PELAGOS_PUBLIC_PARTS__);
const VIEWS = [
  ['today','Today'],['docket','Docket'],['claims','Claims'],['instruments','Instruments'],
  ['evidence','Evidence'],['decisions','Decisions'],['stress','Stress'],['handoff','Handoff'],['lineage','Lineage']
];
const SEV = {Critical:4,High:3,Medium:2,Low:1};
let workspace = null, publicDigest = '', activeView = 'today', subview = {}, currentSearch = '';
let storageMode = 'memory', db = null, importJournal = null;
const $ = (q,root=document) => root.querySelector(q);
const $$ = (q,root=document) => [...root.querySelectorAll(q)];
const clone = x => JSON.parse(JSON.stringify(x));
const now = () => new Date().toISOString();
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const slug = v => String(v||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
const b64 = bytes => {let s='';for(const b of bytes)s+=String.fromCharCode(b);return btoa(s)};
const unb64 = s => Uint8Array.from(atob(s),c=>c.charCodeAt(0));
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v)}
async function sha256Bytes(bytes){const hash=await crypto.subtle.digest('SHA-256',bytes);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('')}
async function sha256Text(text){return sha256Bytes(new TextEncoder().encode(text))}
function toast(message){const t=$('#toast');t.textContent=message;t.classList.remove('sr');setTimeout(()=>t.classList.add('sr'),2200)}
function download(name,text,type='application/json'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},100)}
function csv(rows){if(!rows.length)return '';const keys=[...new Set(rows.flatMap(r=>Object.keys(r).filter(k=>!k.startsWith('_'))))];const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';return [keys.map(q).join(','),...rows.map(r=>keys.map(k=>q(r[k])).join(','))].join('\n')}
function severityTag(v){return `<span class="tag ${slug(v)}">${esc(v||'Open')}</span>`}
function sourceLink(s){if(/^https?:\/\//.test(String(s||'')))return `<a class="source-link" href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(s)}</a>`;return esc(s||'—')}
function blockNetwork(){
  window.fetch = () => Promise.reject(new Error('Network disabled by Pelagos Governance Layer'));
  const deny=()=>{throw new Error('Network disabled by Pelagos Governance Layer')};
  if(window.XMLHttpRequest){XMLHttpRequest.prototype.open=deny}
  window.WebSocket=function(){deny()};window.EventSource=function(){deny()};
}
function blankWorkspace(){return {schema:WORKSPACE_SCHEMA,release:RELEASE,public_digest:publicDigest,instance_id:`WS-${crypto.randomUUID?crypto.randomUUID():Math.random().toString(36).slice(2)}`,created_at:now(),updated_at:now(),role:'founder',aperture:'internal',intake:[],source_receipts:[],corrections:[],decisions:[],authority_assertions:[],qualification_plans:[],stress_runs:[],receipts:[],settings:{retain_text:false,single_writer:true,custodian:'',decision_owner:'',technical_owner:'',communications_owner:''},import_journal:null}}
async function openStorage(){
  if(!('indexedDB' in window)){storageMode='localStorage';return}
  try{db=await new Promise((resolve,reject)=>{const req=indexedDB.open('ddv-pelagos-governance',1);req.onupgradeneeded=()=>req.result.createObjectStore('state');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});storageMode='IndexedDB'}catch(e){storageMode='localStorage'}
}
async function storageRead(){
  if(db)return new Promise(resolve=>{const tx=db.transaction('state');const req=tx.objectStore('state').get('workspace');req.onsuccess=()=>resolve(req.result||null);req.onerror=()=>resolve(null)});
  try{return JSON.parse(localStorage.getItem('ddv-pelagos-governance')||'null')}catch(e){return null}
}
async function storageWrite(){workspace.updated_at=now();if(db)return new Promise(resolve=>{const tx=db.transaction('state','readwrite');tx.objectStore('state').put(workspace,'workspace');tx.oncomplete=resolve;tx.onerror=resolve});try{localStorage.setItem('ddv-pelagos-governance',JSON.stringify(workspace))}catch(e){storageMode='memory'}}
async function appendReceipt(kind,objectId,payload={},actorRole=workspace.role){const prev=workspace.receipts.at(-1)?.hash||null;const body={schema:'ddv/pelagos-receipt@1',sequence:workspace.receipts.length+1,previous_hash:prev,at:now(),actor_role:actorRole,kind,object_id:objectId||null,payload};const hash=await sha256Text(canonical(body));workspace.receipts.push({...body,hash});await storageWrite();return hash}
async function verifyReceipts(){let prev=null;for(const r of workspace.receipts){const {hash,...body}=r;if(body.previous_hash!==prev)return {ok:false,sequence:r.sequence,reason:'previous hash mismatch'};const actual=await sha256Text(canonical(body));if(actual!==hash)return {ok:false,sequence:r.sequence,reason:'receipt hash mismatch'};prev=hash}return {ok:true,count:workspace.receipts.length,head:prev}}
function effectiveCorrection(type,id,field,original){const rows=workspace.corrections.filter(x=>x.object_type===type&&x.object_id===id&&x.field===field);return rows.length?rows.at(-1).proposed_value:original}
function decisionFor(id){return workspace.decisions.filter(x=>x.exception_id===id).at(-1)||null}
function workspaceAdmission(){return workspace.authority_assertions.filter(x=>x.kind==='workspace_admission').at(-1)||null}
function effectiveIntake(){const superseded=new Set(workspace.intake.map(x=>x.supersedes).filter(Boolean));return workspace.intake.filter(x=>!superseded.has(x.id))}
function exceptionOpen(row){const d=decisionFor(row['Exception ID']);return !(d&&d.record_state==='recorded'&&['Close','Accept','Reject','Withdraw','Correct','Proceed'].includes(d.disposition))}
function role(){return PUBLIC.role_profiles.find(x=>x.id===workspace.role)||PUBLIC.role_profiles[0]}
function aperture(){return PUBLIC.apertures.find(x=>x.id===workspace.aperture)||PUBLIC.apertures[0]}
function localVisible(row){if(workspace.aperture==='public')return row.visibility==='public';if(workspace.aperture==='diligence')return row.visibility!=='privileged'&&!row.private_body;if(workspace.aperture==='counsel')return row.visibility==='privileged'||row.visibility==='confidential'||row.counsel===true;return true}
function roleAllows(row){const rp=role();if(rp.domains.includes('*'))return true;const domain=row.Domain||row['Claim class']||row['Object Type']||row.Type||'';return rp.domains.some(d=>String(domain).toLowerCase().includes(String(d).toLowerCase()))}
function renderStatus(){
  const health=runtimeHealth();
  $('#statusline').innerHTML=[
    ['warn',PUBLIC.meta.status],['',`PUBLIC ${publicDigest.slice(0,12)}`],['',`${storageMode}`],
    [health.unexpected_resources.length?'warn':'good',health.unexpected_resources.length?`${health.unexpected_resources.length} unexpected requests`:'zero runtime requests'],
    [workspaceAdmission()?'good':'warn',workspaceAdmission()?'workspace admitted':'workspace candidate'],
    ['',`role: ${role().label}`],['',`aperture: ${aperture().label}`],
    ['',workspace.settings?.custodian?`custodian: ${workspace.settings.custodian}`:'custodian: unassigned']
  ].map(([c,t])=>`<span class="stamp ${c}">${esc(t)}</span>`).join('');
  $('#boundaryText').textContent=PUBLIC.meta.boundary;
}
function renderNav(){const n=$('#nav');n.innerHTML=VIEWS.map(([id,label])=>`<button type="button" data-view="${id}" aria-current="${activeView===id?'page':'false'}">${label}</button>`).join('');$$('button[data-view]',n).forEach(b=>b.onclick=()=>{activeView=b.dataset.view;currentSearch='';render()})}
function viewHead(title,description,actions=''){return `<div class="view-head"><div><div class="kicker">${esc(role().label)} · ${esc(aperture().label)}</div><h2>${esc(title)}</h2><p>${esc(description)}</p></div><div>${actions}</div></div>`}
function metrics(){const open=PUBLIC.exceptions.filter(exceptionOpen);const critical=open.filter(x=>x.Severity==='Critical').length;const high=open.filter(x=>x.Severity==='High').length;const held=PUBLIC.claims.filter(x=>['Critical','High'].includes(x.Risk)).length;return [
  [critical,'critical decisions'],[high,'high decisions'],[held,'high-risk claims'],[PUBLIC.instruments.length,'public instruments'],[effectiveIntake().length,'live local objects'],[workspace.source_receipts.length,'local sources'],[workspace.receipts.length,'local receipts']
].map(([n,l])=>`<div class="metric"><strong>${n}</strong><span>${esc(l)}</span></div>`).join('')}
function bestAction(){const open=PUBLIC.exceptions.filter(exceptionOpen);if(!workspaceAdmission()){const adoption=open.find(x=>x['Exception ID']==='EX-028');if(adoption)return adoption}return open.sort((a,b)=>(SEV[b.Severity]||0)-(SEV[a.Severity]||0))[0]||null}
function renderToday(){const best=bestAction();const secondary=PUBLIC.founder_decisions.filter(d=>!decisionFor(d.Exception.split(';')[0])).slice(0,3);const held=['send email','schedule meeting','sign instrument','publish claim','move money','release controlled data'];const admission=workspaceAdmission();return viewHead('Today','One best next action, the safe secondary moves, and the outside effects still withheld.',admission?'':`<button class="btn safe" id="admitWorkspace">Admit working copy</button>`)+
`<div class="metric-grid">${metrics()}</div>${admission?`<div class="callout good" data-csp-style="csp-c53ea1da2385"><b>Pelagos working copy admitted.</b> ${esc(admission.company_name)} · authority ${esc(admission.authority_source)} · custodian ${esc(admission.custodian||'unassigned')}. The public cartridge remains immutable.</div>`:`<div class="callout stop" data-csp-style="csp-c53ea1da2385"><b>Candidate only.</b> Before private use, a Pelagos decision authority must admit this as a working copy, name the custodian and assign the decision, technical and communications owners.</div>`}<div class="grid two" data-csp-style="csp-c53ea1da2385"><section class="card paper hero-action"><div class="card-body"><div class="kicker">Best next action</div>${best?`<h3>${esc(best['Decision Required'])}</h3><p class="muted">${esc(best['Mechanism / Failure'])}</p><div>${severityTag(best.Severity)} <span class="tag">${esc(best.Domain)}</span> <span class="tag">default ${esc(best.Default)}</span></div><p><b>Owner:</b> ${esc(best['Proposed Owner'])}</p>${best['Exception ID']==='EX-028'&&!admission?`<button class="btn primary" id="admitWorkspace2">Admit working copy</button>`:`<button class="btn primary" data-open-decision="${esc(best['Exception ID'])}">Open bounded decision</button>`}`:'<h3>No unresolved public exceptions</h3><p>The public baseline remains reconstructable and the local workspace carries successor records.</p>'}</div></section>
<section class="card"><div class="card-head"><h3>Can move safely</h3></div><div class="card-body record-list">${secondary.map(x=>`<div class="record"><div class="id">${esc(x.ID)}</div><h3>${esc(x.Decision)}</h3><p>${esc(x.Default)}</p></div>`).join('')||'<p class="muted">No secondary moves.</p>'}</div></section></div>
<div class="grid two" data-csp-style="csp-c53ea1da2385"><section class="card"><div class="card-head"><h3>State separations that keep Pelagos honest</h3></div><div class="card-body">${PUBLIC.invariants.slice(0,10).map(x=>`<div class="receipt"><b>${esc(x.Rule)}</b><br><span class="muted">${esc(x['Failure Mode'])}</span></div>`).join('')}</div></section><section class="card"><div class="card-head"><h3>External-effect firewall</h3></div><div class="card-body"><div class="callout stop">This runtime has zero adapters for email, calendar, payment, publication, signature, procurement, or source-system writeback.</div><div class="record-list">${held.map(x=>`<div class="record"><span class="tag hold">held</span> ${esc(x)}</div>`).join('')}</div></div></section></div>`}
function toolbar(type,extra=''){return `<div class="toolbar"><input id="searchBox" type="search" value="${esc(currentSearch)}" placeholder="Search ${esc(type)}"><button class="btn small" id="clearSearch">Clear</button>${extra}</div>`}
