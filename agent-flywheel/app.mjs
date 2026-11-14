import { parseEvidence, mergeEvidence, summarizeEvidence, prepareWork, buildHandoff, runResearch, verifyReport } from './engine.mjs';
import { PROVIDER_PRESETS, createClient } from './providers.mjs';
import { SAMPLE_CONFIG, createDemoClient } from './sample.mjs';

const $ = (selector, root = document) => root.querySelector(selector);
const icons = {
  play:'<path d="m8 5 11 7-11 7Z"/>', stop:'<rect x="6" y="6" width="12" height="12" rx="1"/>',
  flask:'<path d="M9 3h6M10 3v7l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V3M8 15h8"/>',
  trace:'<path d="M5 3v12a3 3 0 0 0 3 3h11M5 8h10"/><circle cx="5" cy="3" r="2"/><circle cx="17" cy="8" r="2"/><circle cx="21" cy="18" r="2"/>',
  upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>', download:'<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>', close:'<path d="m6 6 12 12M6 18 18 6"/>',
  check:'<path d="m5 12 4 4L19 6"/>', shield:'<path d="m12 3 8 3v6c0 4-5 8-8 9-3-1-8-5-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>', code:'<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-14-2 24"/>',
  key:'<circle cx="8" cy="8" r="4"/><path d="m11 11 10 10m-4-4 3-3m-6 0 3-3"/>', file:'<path d="M13 3H5v18h14V9Zm0 0v6h6M8 13h8m-8 4h6"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>', arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>', eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  chart:'<path d="M4 3v18h17M9 16v-5m5 5V6m5 10v-7"/>', branch:'<circle cx="6" cy="4" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="6" cy="20" r="2"/><path d="M6 6v12m0-5h7a5 5 0 0 0 5-5"/>',
  chat:'<path d="M4 4h16v12H9l-5 4Z"/><path d="M8 8h8m-8 4h5"/>', terminal:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 8 4 4-4 4m6 0h4"/>',
  layers:'<path d="m12 3 10 5-10 5L2 8Zm-10 10 10 5 10-5M2 18l10 5 10-5"/>', refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M20 12a8 8 0 0 0-14-5M4 12a8 8 0 0 0 14 5"/>',
};
const I = (name, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = value => typeof value === 'string' ? value : value === undefined ? 'Not recorded' : JSON.stringify(value, null, 2);
const count = value => Number.isFinite(Number(value)) ? Number(value).toLocaleString() : '—';
const finite = value => value !== null && value !== undefined && Number.isFinite(Number(value));
const percent = value => finite(value) ? `${(Number(value) * 100).toFixed(Number(value) === 0 || Number(value) === 1 ? 0 : 1)}%` : '—';
const delta = value => finite(value) ? `${Number(value) > 0 ? '+' : ''}${(Number(value) * 100).toFixed(Number.isInteger(Number(value) * 100) ? 0 : 1)} pp` : '—';
const human = value => String(value ?? '').replace(/[_-]+/g, ' ').replace(/^./, c => c.toUpperCase());
const safeURL = value => { try { const u = new URL(value); return u.protocol === 'https:' ? u.href : '#'; } catch { return '#'; } };
const initialPreset = PROVIDER_PRESETS.find(p => p.id === 'sonnet') || PROVIDER_PRESETS[0];
const defaults = () => ({goal:'', taskContract:'', baselinePrompt:'', evidenceText:'', mode:'diagnose', metric:'exact', candidateLimit:2, caseLimit:12, maxCalls:40, seed:17, preset:initialPreset.id, provider:initialPreset.provider, endpoint:initialPreset.endpoint, model:initialPreset.model, effort:initialPreset.effort || '', maxTokens:initialPreset.maxTokens, temperature:initialPreset.temperature ?? '', topP:initialPreset.topP ?? '', timeoutMs:120000, apiKey:''});
const state = {view:'work', form:defaults(), files:[], evidence:null, parseError:'', preparedWork:null, preflight:null, preflightError:'', report:null, verification:null, resultTab:'findings', caseSplit:'all', caseQuery:'', busy:false, controller:null, events:[], runError:'', error:'', handoff:'', demo:false, sampleLoaded:false, runMetadata:null, imported:false};
let toastTimer, parseTimer, preflightTimer, preflightGeneration=0, dialogReturnFocus;

function toast(message) { const el = $('#toast'); el.textContent = message; el.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 3500); }
function setError(message) { state.error = message; const el = $('#work-error'); if (el) { el.textContent = message; el.scrollIntoView({block:'nearest', behavior:'smooth'}); } else toast(message); }
function empty(title, description, action = '') { return `<section class="card empty-state"><span class="empty-icon">${I('flask')}</span><h2>${esc(title)}</h2><p>${esc(description)}</p>${action}</section>`; }
function field(label, id, content, note = '', optional = false, cls = '') { return `<label class="field ${cls}" for="${id}"><span class="field-label">${label}${optional?'<span class="optional">Optional</span>':''}</span>${content}${note?`<span class="field-note">${note}</span>`:''}</label>`; }
function input(id, value, options = '') { return `<input id="${id}" data-field="${id}" value="${esc(value)}" ${options}>`; }
function select(id, options, value) { return `<select id="${id}" data-field="${id}">${options.map(([v,label]) => `<option value="${esc(v)}"${String(value) === String(v)?' selected':''}>${esc(label)}</option>`).join('')}</select>`; }
function textarea(id, value, rows = 3, placeholder = '', cls = '') { return `<textarea id="${id}" data-field="${id}" rows="${rows}" class="${cls}" placeholder="${esc(placeholder)}">${esc(value)}</textarea>`; }
function stat(label, value, note, icon, cls = '') { return `<section class="card metric-card"><div class="metric-top"><span>${esc(label)}</span>${I(icon)}</div><div class="metric-value ${cls}">${esc(value)}</div><div class="metric-note">${esc(note)}</div></section>`; }
function kv(label, value, mono = false) { return `<div class="kv-row"><span>${esc(label)}</span><strong class="${mono?'mono':''}">${esc(value)}</strong></div>`; }
function evidenceSummary() { try { return state.evidence ? summarizeEvidence(state.evidence) : {records:0,labeled:0,documents:0,warnings:[]}; } catch { return {records:0,labeled:0,documents:0,warnings:[]}; } }
function collectEvidence() {
  const parts = state.files.map(f => f.parsed);
  if (state.form.evidenceText.trim()) parts.unshift(parseEvidence(state.form.evidenceText, 'pasted.txt'));
  state.evidence = parts.length ? mergeEvidence(parts) : {records:[], documents:[], warnings:[]};
  state.parseError = '';
  return state.evidence;
}
function updateEvidenceStatus() {
  try { collectEvidence(); } catch (error) { state.parseError = error.message; state.evidence = null; }
  const el = $('#evidence-stats'); if (el) el.innerHTML = evidenceStatus();
  const list = $('#file-list'); if (list) list.innerHTML = fileList();
  schedulePreflight();
}
function evidenceStatus() {
  if (state.parseError) return `<div class="field-error">${esc(state.parseError)}</div>`;
  const s = evidenceSummary();
  return `<div class="evidence-status"><span><strong>${count(s.records)}</strong> records</span><span><strong>${count(s.labeled)}</strong> labeled cases</span><span><strong>${count(s.documents)}</strong> source documents</span></div>${s.warnings?.length?`<div class="warning-list">${s.warnings.map(w=>`<div>${esc(typeof w==='string'?w:pretty(w))}</div>`).join('')}</div>`:''}`;
}
function fileList() { return state.files.map((f,i) => `<div class="file-item">${I('file')}<span title="${esc(f.name)}">${esc(f.name)} · ${count(f.bytes)} bytes</span><button class="icon-button" data-action="remove-file" data-index="${i}" aria-label="Remove ${esc(f.name)}">${I('close')}</button></div>`).join(''); }
function selectedPreset() { return PROVIDER_PRESETS.find(p => p.id === state.form.preset); }
function effortChoices() { const model=state.form.model.toLowerCase();const choices=model.includes('qwen3.8')?['low','medium','xhigh']:model.includes('gemini-3.8')?['low','medium','high']:['low','medium','high','xhigh','max'];return [['','Provider default'],...choices.map(v=>[v,v==='xhigh'?'Extra high':human(v)])]; }
function modelCaption() {
  if (state.demo) return `<div class="model-caption">${I('info')}<div><strong>Deterministic demonstration.</strong> The supplied example adapter returns fixed, inspectable responses. It makes no external model requests.</div></div>`;
  const p = selectedPreset();
  return `<div class="model-caption">${I('info')}<div>${esc(p?.description || 'Use an OpenAI-compatible endpoint and the model identifier it accepts.')} ${p?.sourceUrl?`<a href="${esc(safeURL(p.sourceUrl))}" target="_blank" rel="noopener noreferrer">Model documentation ↗</a>`:''}</div></div>`;
}
function modelSummary() { return state.demo ? 'Deterministic demo adapter' : state.form.model || 'Choose a model'; }
function workView() {
  const f = state.form;
  return `<div class="page-heading"><div><div class="eyebrow">AGENT FLYWHEEL · RESEARCH TOOL</div><h1>Agent research, on demand.</h1><p>Bring the task and the evidence. Choose a model to investigate, propose changes, and measure what improves.</p></div><div class="heading-actions"><button class="button" data-action="sample">${I('flask')}Load example</button><button class="button" data-action="import">${I('upload')}Import report</button></div></div>
  ${state.demo?'<div class="info-strip demo">'+I('info')+`<div><strong>${state.sampleLoaded?'Synthetic example loaded.':'Deterministic demonstration selected.'}</strong> This run uses a fixed demonstration adapter. Select a research model to use your own endpoint.</div></div>`:''}
  <div id="work-error" class="input-error" role="alert">${esc(state.error)}</div>
  <fieldset class="input-fieldset"${state.busy?' disabled':''}><div class="work-grid"><div class="work-inputs">
    <section class="card"><div class="card-header"><div><h2><span class="card-index">01</span>Define the work</h2><p>Describe the agent and the question you want resolved.</p></div>${I('flask')}</div><div class="card-body">
      <div class="mode-switch" aria-label="Research mode"><button type="button" class="mode-option ${f.mode==='diagnose'?'active':''}" data-action="mode" data-mode="diagnose" aria-pressed="${f.mode==='diagnose'}">${I('trace')}Diagnose</button><button type="button" class="mode-option ${f.mode==='improve'?'active':''}" data-action="mode" data-mode="improve" aria-pressed="${f.mode==='improve'}">${I('chart')}Improve & evaluate</button></div>
      <div class="mode-explanation">${f.mode==='improve'?'Compare prompt candidates on development cases, freeze the selection, then evaluate against your held-out labels and regression cases.':'Ask the model to inspect your development evidence, explain failures, and propose testable improvements. Analysis retains its source record IDs.'}</div>
      ${field('Research objective','goal',textarea('goal',f.goal,2,'e.g. Find why our support agent routes billing complaints to technical support.'))}
      ${field('Task contract','taskContract',textarea('taskContract',f.taskContract,3,'What should the agent do? Describe the input, required output, constraints, and what counts as correct.'),'The original task stays attached to the experiment.')}
      ${field('Current agent prompt','baselinePrompt',textarea('baselinePrompt',f.baselinePrompt,3,'Paste the current system instructions or baseline prompt.','code-input'),f.mode==='improve'?'Required for a measured comparison. The chosen model executes both baseline and candidate prompts.':'Include the current instructions when they help explain the behavior.',f.mode==='diagnose')}
    </div></section>
    <section class="card"><div class="card-header"><div><h2><span class="card-index">02</span>Add the evidence</h2><p>Traces, failures, notes, or cases with expected answers.</p></div><span class="pill">JSON · JSONL · CSV · text</span></div><div class="card-body">
      ${field('Paste evidence','evidenceText',textarea('evidenceText',f.evidenceText,7,'{"id":"case-01","input":"...","expected":"...","output":"...","split":"development"}\n\nOr paste task notes and failure descriptions.','code-input'))}
      <label class="file-drop" id="file-drop">${I('upload')}<span><strong>Choose files or drop them here</strong><small>Multiple text, JSON, JSONL, and CSV files accepted.</small></span><input id="evidence-files" type="file" accept=".json,.jsonl,.ndjson,.csv,.txt,.md,text/*,application/json" multiple></label><div class="file-list" id="file-list">${fileList()}</div><div id="evidence-stats">${evidenceStatus()}</div>
      <div class="helper-row"><span class="small-note">Unlabeled notes support analysis. Your supplied labels define correctness.</span><button class="button ghost small" data-action="reset">Reset work</button></div>
    </div></section>
  </div><aside class="card model-panel"><div class="card-header"><div><h2><span class="card-index">03</span>Choose a researcher</h2><p>Your endpoint. Your credentials. Your budget.</p></div>${I('layers')}</div><div class="card-body">
    <div class="model-selector">${field('Model preset','preset',select('preset',[...PROVIDER_PRESETS.map(p=>[p.id,p.label]),['demo','Deterministic demo · synthetic example']],state.demo?'demo':f.preset))}${modelCaption()}</div>
    <div class="model-fields"${state.demo?' hidden':''}>
      ${field('Endpoint','endpoint',input('endpoint',f.endpoint,'type="url" placeholder="https://…/chat/completions" autocomplete="off" spellcheck="false"'))}
      ${field('Model identifier','model',input('model',f.model,'type="text" placeholder="provider/model" autocomplete="off" spellcheck="false"'))}
      ${field('API key','apiKey',`<div class="key-input"><input id="apiKey" type="password" autocomplete="off" spellcheck="false" placeholder="Your key, if required" data-field="apiKey"><button type="button" class="icon-button" data-action="show-key" aria-label="Show API key" aria-pressed="false">${I('eye')}</button></div>`,'Kept in memory for this page. Excluded from all exports.',true)}
    </div>
    <div class="run-controls"><details class="advanced"><summary>Research settings ${I('chevron')}</summary><div class="advanced-content">
      <div class="form-grid">${field('Reasoning effort','effort',select('effort',effortChoices(),f.effort))}${field('Max output tokens','maxTokens',input('maxTokens',f.maxTokens,'type="number" min="256" max="32768" step="256"'))}</div>
      <div class="form-grid">${field('Candidate limit','candidateLimit',input('candidateLimit',f.candidateLimit,'type="number" min="1" max="8" step="1"'))}${field('Evaluation case cap','caseLimit',input('caseLimit',f.caseLimit,'type="number" min="2" max="100" step="1"'))}</div>
      <div class="form-grid">${field('Model call cap','maxCalls',input('maxCalls',f.maxCalls,'type="number" min="1" max="256" step="1"'))}${field('Split seed','seed',input('seed',f.seed,'type="number" min="0" max="2147483647" step="1"'))}</div>
      ${field('Reference evaluator','metric',select('metric',[['exact','Exact text match'],['json','Structured JSON match']],f.metric),'Reference comparisons use your supplied expected values.')}
      <hr class="section-rule"><div class="form-grid">${field('Temperature','temperature',input('temperature',f.temperature,'type="number" min="0" max="2" step="0.05" placeholder="Provider default"'),'',true)}${field('Top P','topP',input('topP',f.topP,'type="number" min="0" max="1" step="0.05" placeholder="Provider default"'),'',true)}</div>
      ${field('Endpoint protocol','provider',select('provider',[['openrouter','OpenRouter'],['compatible','OpenAI compatible']],f.provider))}
      ${field('Per-call timeout (ms)','timeoutMs',input('timeoutMs',f.timeoutMs,'type="number" min="1000" max="300000" step="1000"'))}
    </div></details>
    <div id="run-budget">${budgetSummary()}</div><div class="model-actions"><button class="button primary wide" data-action="run">${I('play')}Run research</button><div class="secondary-actions"><button class="button" data-action="handoff">${I('copy')}Copy agent handoff</button><button class="button" data-action="work-download">${I('download')}Work packet</button></div></div><p class="privacy-note">${state.demo?'The demo makes no network requests.':'Model requests go directly to the chosen endpoint.'}<br>Use the handoff with your existing agent without entering a key.</p>
    </div>
  </div></aside></div></fieldset>
  ${state.busy?'<div class="info-strip" style="margin-top:20px">'+I('info')+'<div>A frozen research run is in progress. <a href="#results">View progress and cancel</a>.</div></div>':''}
  <div class="principles"><div class="principle">${I('trace')}<div><strong>Evidence stays attached</strong><p>Findings cite your source records. Proposed tests remain separate from your labels.</p></div></div><div class="principle">${I('shield')}<div><strong>Selection before evaluation</strong><p>The candidate freezes before held-out comparison. Regression cases preserve prior behavior.</p></div></div><div class="principle">${I('file')}<div><strong>A result you can inspect</strong><p>Download the work, model receipts, reference outcomes, and verified report.</p></div></div></div>`;
}
function budgetSummary() { const f=state.form,w=state.preflight; return `<div class="run-budget"><span>Research model</span><strong>${esc(modelSummary())}</strong><span>Reasoning / output cap</span><strong>${state.demo?'Deterministic':`${esc(f.effort || 'Default')} · ${count(f.maxTokens)} tokens`}</strong><span>Model call cap</span><strong>${count(f.maxCalls)} ${state.demo?'adapter calls':'calls'}</strong><span>Planned calls (ceiling)</span><strong>${w?count(w.plannedCalls):'Awaiting work inputs'}</strong><span>Selected labeled cases</span><strong>${w?count(w.budget?.evaluationCases):'—'}</strong><span>Workflow</span><strong>${f.mode==='improve'?`Up to ${count(f.candidateLimit)} candidates`:'Development evidence diagnosis'}</strong></div>${w&&w.plannedCalls>Number(f.maxCalls)?'<div class="warning-list" style="margin:0 0 15px">The conservative plan exceeds your call cap. Reduce cases or candidates, or increase the cap. The engine stops before evaluation if its final plan still exceeds the cap.</div>':state.preflightError&&f.goal.trim()?`<div class="budget-status">${esc(state.preflightError)}</div>`:''}`; }
function reportModel(report) { const p=report?.provenance || {}; const m=p.model || p.client || p.provider_metadata || p.model_metadata || state.runMetadata; return typeof m==='string'?m:m?.model || p.model_id || 'Recorded in receipts'; }
function reportIsDemo(report) { return /deterministic|demo/i.test(JSON.stringify(report?.provenance || {})); }
function verdictStyle(verdict) { return verdict==='QUALIFIED'?'green':['REJECTED','INCOMPLETE'].includes(verdict)?'red':['NEEDS_EVALUATION'].includes(verdict)?'amber':'blue'; }
const verdictLabels={QUALIFIED:'Candidate qualified',NO_CHANGE:'No change qualified',REJECTED:'Candidate rejected',DIAGNOSED:'Diagnosis complete',NEEDS_EVALUATION:'Evaluation evidence needed',INCOMPLETE:'Research incomplete'};
function reportMetrics(r) {
  const m=r.metrics, scored=m && finite(m.total) && Number(m.total)>0;
  if (scored) return `<div class="metrics-row">${stat('Baseline reference score',`${count(m.baseline_passed)} / ${count(m.total)}`,'Held-out cases evaluated','chart')}${stat('Candidate reference score',`${count(m.candidate_passed)} / ${count(m.total)}`,'Same held-out reference cases','chart')}${stat('Observed change',delta(m.delta),'Percentage points on held-out cases','branch',Number(m.delta)>0?'positive':Number(m.delta)<0?'negative':'')}${stat('Regressions',count(m.regressions),'Held-out and regression cases','shield',m.regressions===0?'positive':'')}</div>`;
  const s=r.work?.stats || {}, a=r.analysis || {};
  return `<div class="metrics-row">${stat('Source records',count(s.records ?? r.work?.evidence?.records?.length ?? 0),'Provided with this work','trace')}${stat('Labeled cases',count(s.labeled ?? 0),'Supplied reference outcomes','shield')}${stat('Proposed changes',count((r.candidates || a.candidates || []).length),'Research proposals, pending evaluation','branch')}${stat('Model calls',count(m?.calls ?? r.receipts?.length ?? 0),'Retained request and response receipts','layers')}</div>`;
}
function stages(events) {
  const map=new Map(); for(const event of events || []) map.set(event.id,event);
  return `<section class="card stage-card"><div class="card-header"><h2>Research stages</h2>${state.busy?'<span class="spinner"></span>':''}</div><div class="stage-list">${map.size?[...map.values()].map(e=>`<div class="stage ${esc(e.status)}"><span class="stage-icon">${I(['completed','passed','done'].includes(e.status)?'check':e.status==='failed'?'close':'flask')}</span><div><div class="stage-label">${esc(e.label || human(e.id))}</div><div class="stage-detail">${esc(e.detail || human(e.status))}</div></div></div>`).join(''):'<p class="small-note">Waiting for the first research event.</p>'}</div></section>`;
}
function activeResult() {
  return `<div class="page-heading result-heading"><div><div class="eyebrow">${state.busy?'RESEARCH IN PROGRESS':'RESEARCH INTERRUPTED'}</div><h1>${esc(state.preparedWork?.goal || 'Research run')}</h1><div class="run-subline"><span>${esc(state.runMetadata?.model || modelSummary())}</span><span>·</span><span>${state.demo?'Deterministic demonstration':'Direct model requests'}</span></div></div><div class="heading-actions">${state.busy?`<button class="button danger" data-action="cancel">${I('stop')}Cancel run</button>`:''}<button class="button" data-action="work-download">${I('download')}Work packet</button></div></div><div class="result-banner ${state.runError?'red':'blue'}">${I(state.runError?'info':'flask')}<div><h2>${state.runError?'The run stopped before a report was returned.':'Executing the frozen work packet'}</h2><p>${esc(state.runError || 'Model calls and evaluation stages appear below as they complete. You can cancel while retaining the partial evidence returned by the engine.')}</p></div></div>${stages(state.events)}`;
}
function resultsView() {
  if(state.busy || (state.runError && !state.report)) return activeResult();
  const r=state.report;
  if(!r) return `<div class="page-heading"><div><div class="eyebrow">RETAINED RESEARCH</div><h1>Results</h1><p>Inspect the reasoning, measurements, and receipts from your research run.</p></div><div class="heading-actions"><button class="button" data-action="import">${I('upload')}Import report</button></div></div>${empty('The evidence will land here.','Run an investigation with your own work, try the deterministic example, or import a verified report from the local runner.','<div class="heading-actions"><a class="button primary" href="#work">'+I('arrow')+'Add your work</a><button class="button" data-action="sample">Load example</button></div>')}`;
  const style=verdictStyle(r.verdict),verified=state.verification?.valid;
  return `<div class="page-heading result-heading"><div><div class="eyebrow">${state.imported?'IMPORTED RESEARCH REPORT':'RESEARCH RESULT'} · ${esc(human(r.status))}</div><h1>${esc(r.goal || 'Research result')}</h1><div class="run-subline"><span class="mono">${esc(r.run_id)}</span><span>·</span><span>${esc(reportModel(r))}</span>${reportIsDemo(r)?'<span class="demo-badge">Deterministic demo</span>':''}</div></div><div class="heading-actions"><button class="button" data-action="report-download">${I('download')}Report & evidence</button><button class="button" data-action="import">${I('upload')}Import</button></div></div>${reportMetrics(r)}
  <div class="tabs" role="tablist" aria-label="Research result">${[['findings','Findings'],['evaluation','Evaluation'],['candidates','Candidates'],['receipts','Receipts']].map(([key,label])=>`<button class="tab-button ${state.resultTab===key?'active':''}" data-action="result-tab" data-tab="${key}" role="tab" aria-selected="${state.resultTab===key}">${label}${key==='receipts'?`<span>${r.receipts?.length || 0}</span>`:key==='candidates'?`<span>${r.candidates?.length || 0}</span>`:''}</button>`).join('')}</div>
  <div class="result-banner ${style==='green'?'':style}">${I(style==='green'?'shield':'info')}<div><h2>${esc(verdictLabels[r.verdict] || human(r.verdict))}</h2><p>${esc(r.summary || r.analysis?.summary || 'Inspect the retained report for the experiment outcome.')}</p>${reportIsDemo(r)?'<p>Deterministic demonstration responses. No external model ran.</p>':''}</div></div>
  ${state.resultTab==='findings'?findingsView(r):state.resultTab==='evaluation'?evaluationView(r):state.resultTab==='candidates'?candidatesView(r):receiptsView(r)}
  <div class="verification-line">${I(verified?'shield':'info')}<span>${verified?'Report integrity and recomputed outcomes verified in this browser.':`Report verification needs review: ${(state.verification?.errors || []).join('; ')}`}</span></div>`;
}
function recordTags(ids, r) { return `<div class="evidence-tags">${(ids || []).map(id=>`<button class="record-chip" data-action="record" data-record="${esc(id)}">${esc(id)}</button>`).join('')}</div>`; }
function findingsView(r) {
  const a=r.analysis || {}, findings=a.findings || [], hypotheses=a.hypotheses || [], tests=a.proposed_tests || [];
  return `<div class="result-layout">${stages(r.events || state.events)}<div class="result-content"><section class="card"><div class="card-header"><h2>Research findings</h2><span class="pill">Development evidence</span></div>${findings.length?findings.map(f=>`<article class="finding"><h3>${esc(f.title)}</h3><p>${esc(f.detail)}</p>${recordTags(f.evidence_ids,r)}</article>`).join(''):`<div class="card-body"><p class="summary-text">${esc(a.summary || r.summary || 'No findings were returned for this work.')}</p></div>`}</section>
  ${hypotheses.length?`<section class="card"><div class="card-header"><h2>Testable hypotheses</h2><span class="pill">${hypotheses.length} proposals</span></div>${hypotheses.map(h=>`<article class="finding"><h3>${esc(h.id || 'Hypothesis')}</h3><p>${esc(h.statement)}</p><div class="hypothesis-test"><strong>Test</strong><br>${esc(h.test)}${h.expected_effect?`<br><br><strong>Expected effect</strong><br>${esc(h.expected_effect)}`:''}</div></article>`).join('')}</section>`:''}
  ${tests.length?`<section class="card"><div class="card-header"><h2>Proposed evaluation cases</h2><span class="pill amber">Unverified proposals</span></div><div class="inset-note">Model-proposed cases and expected answers stay separate from your supplied labels. Review them before using them as reference evidence.</div>${tests.map(t=>`<article class="finding"><h3>${esc(pretty(t.input))}</h3><p>${esc(t.rationale || '')}</p>${t.expected!==undefined?`<div class="hypothesis-test">Proposed expected answer<br><span class="mono">${esc(pretty(t.expected))}</span></div>`:''}</article>`).join('')}</section>`:''}
  <section class="card"><div class="card-header"><h2>Experiment provenance</h2><button class="button small" data-action="report-work-download">${I('download')}Work packet</button></div><div class="kv-table">${kv('Research model',reportModel(r))}${kv('Workflow',human(r.work?.mode || 'Recorded'))}${kv('Reference metric',human(r.work?.metric || 'Recorded'))}${kv('Run identity',r.run_id,true)}${kv('Evidence source',reportIsDemo(r)?'Supplied evidence · deterministic adapter':'Visitor-supplied evidence and selected endpoint')}</div><div class="inset-note">The report retains the original work, model receipts, frozen decisions, checks, and content hashes.</div></section></div></div>`;
}
function filteredCases(r) { return (r.cases || []).map((c,index)=>({...c,_index:index})).filter(c=>(state.caseSplit==='all'||c.split===state.caseSplit)&&(!state.caseQuery||[c.id,pretty(c.input)].some(v=>String(v).toLowerCase().includes(state.caseQuery.toLowerCase())))); }
function outcome(value) { return typeof value!=='boolean'?'<span class="empty-dash">—</span>':`<span class="outcome ${value?'pass':'fail'}">${I(value?'check':'close')}${value?'Pass':'Fail'}</span>`; }
function caseTable(r) { const cases=filteredCases(r); return cases.length?`<div class="table-scroll"><table><thead><tr><th>Input / case</th><th>Split</th><th>Baseline</th><th>Candidate</th><th></th></tr></thead><tbody>${cases.map(c=>`<tr class="clickable" tabindex="0" data-case="${c._index}" aria-label="Inspect case ${esc(c.id)}"><td><span class="table-primary">${esc(pretty(c.input).slice(0,220))}${pretty(c.input).length>220?'…':''}</span><span class="table-secondary mono">${esc(c.id)}</span></td><td class="nowrap">${esc(human(c.split))}</td><td>${outcome(c.baseline_passed)}</td><td>${outcome(c.candidate_passed)}</td><td>${I('chevron')}</td></tr>`).join('')}</tbody></table></div>`:'<div class="table-empty">No evaluated cases match this view.</div>'; }
function evaluationView(r) {
  const m=r.metrics;
  if(!r.cases?.length) return empty('No reference comparison was run.','Diagnosis can use unstructured evidence. A measured improvement requires labeled development and held-out cases, a baseline prompt, and sufficient call budget.','<a class="button" href="#work">Review work and evaluation settings</a>');
  const valid=m && Number(m.total)>0;
  return `${valid?`<section class="card" style="margin-bottom:22px"><div class="card-header"><h2>Held-out reference comparison</h2><span class="pill">${esc(human(r.work?.metric || 'Reference'))} evaluator</span></div><div class="comparison"><div class="chart-label">Supplied reference correctness · frozen candidate</div><div class="compare-row"><span>Baseline</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(0,Math.min(100,Number(m.baseline_passed)/Number(m.total)*100))}%"></div></div><strong>${percent(Number(m.baseline_passed)/Number(m.total))}</strong></div><div class="compare-row"><span>Candidate</span><div class="bar-track"><div class="bar-fill candidate" style="width:${Math.max(0,Math.min(100,Number(m.candidate_passed)/Number(m.total)*100))}%"></div></div><strong>${percent(Number(m.candidate_passed)/Number(m.total))}</strong></div><div class="compare-note"><span>${count(m.total)} held-out cases</span><span class="${Number(m.delta)>0?'positive':''}">${delta(m.delta)} observed change</span></div></div></section>`:''}
  <p class="section-intro">Development cases select the candidate. Held-out cases measure the frozen choice; regression cases check established behavior. Select a row to inspect the original outputs.</p><div class="filter-row"><input class="search-input" id="case-search" placeholder="Search case IDs and inputs" aria-label="Search evaluation cases" value="${esc(state.caseQuery)}"><div class="filter-group">${[['all','All cases'],['development','Development'],['heldout','Held-out'],['regression','Regression']].map(([key,label])=>`<button class="filter-button ${state.caseSplit===key?'active':''}" data-action="case-filter" data-filter="${key}">${label}</button>`).join('')}</div></div><section class="card" id="case-table">${caseTable(r)}</section>`;
}
function candidatesView(r) {
  const list=r.candidates || [];
  if(!list.length) return empty('No candidate prompts retained.','The research outcome records whether no change was needed, evidence was insufficient, or the run ended before a proposal.');
  return `<p class="section-intro">The model proposes prompt changes. Supplied reference outcomes determine selection; proposed test answers do not become ground truth.</p><section class="card"><div class="card-header"><h2>Candidate prompts</h2><span class="pill">${list.length} retained</span></div>${list.map((c,index)=>`<article class="candidate"><div class="candidate-title"><h3>${esc(c.id || `Candidate ${index+1}`)}</h3><span class="pill ${c.selected?'green':''}">${c.selected?'Selected and frozen':finite(c.development_score)?`${percent(c.development_score)} development`:'Proposed'}</span></div><p>${esc(c.rationale || '')}</p>${c.selected && finite(c.development_score)?`<p class="small-note" style="margin-top:8px">Development reference score: ${percent(c.development_score)}</p>`:''}<details${c.selected?' open':''}><summary>Inspect prompt</summary><pre class="code-block light">${esc(c.prompt || '')}</pre></details></article>`).join('')}</section>`;
}
function receiptsView(r) {
  return `<p class="section-intro">Retained requests, responses, model identity, usage and timing make the run inspectable. Report verification checks content hashes and independently recomputes qualification.</p><section class="card"><div class="card-header"><h2>Model call receipts</h2><button class="button small" data-action="report-download">${I('download')}Download all evidence</button></div>${r.receipts?.length?r.receipts.map((receipt,i)=>`<details class="receipt-item"><summary><span>${esc(receipt.stage || receipt.id || `Call ${i+1}`)}</span><span class="receipt-meta">${esc(receipt.model || receipt.response?.model || 'Recorded model')} · ${finite(receipt.elapsedMs)?`${count(receipt.elapsedMs)} ms`:'Retained receipt'}</span></summary><pre class="code-block light">${esc(pretty(receipt))}</pre></details>`).join(''):'<div class="table-empty">This report contains no completed model call receipts.</div>'}</section><section class="card" style="margin-top:20px"><div class="card-header"><h2>Provenance and integrity manifest</h2><span class="pill ${state.verification?.valid?'green':'red'}">${state.verification?.valid?'Verified':'Needs review'}</span></div><div class="card-body"><pre class="code-block light">${esc(pretty({provenance:r.provenance,manifest:r.manifest}))}</pre></div></section>`;
}
function workflowView() {
  return `<div class="page-heading"><div><div class="eyebrow">ONE ENGINE · THREE WAYS TO WORK</div><h1>Use your own workflow.</h1><p>Start in the browser, bring your existing agent, or run the same research engine locally.</p></div><div class="heading-actions"><a class="button" href="README.md" target="_blank" rel="noopener">Read the guide ${I('arrow')}</a><a class="button primary" href="agent-flywheel-kit.zip" download>${I('download')}Download tool kit</a></div></div>
  <div class="workflow-cards"><section class="card workflow-card"><div class="workflow-icon red">${I('chat')}</div><h2>Give it to your agent</h2><p>Copy a research handoff for your existing coding agent. It explains the task, model choice, development evidence, evaluation boundary and runner.</p><button class="button" data-action="handoff">${I('copy')}Copy agent handoff</button></section><section class="card workflow-card"><div class="workflow-icon">${I('terminal')}</div><h2>Run on your machine</h2><p>Export your work and use the dependency-free Node runner. The work packet contains your evidence and experiment settings.</p><button class="button" data-action="work-download">${I('download')}Download work packet</button></section><section class="card workflow-card"><div class="workflow-icon">${I('layers')}</div><h2>Choose a model</h2><p>Use an OpenRouter preset or an OpenAI-compatible endpoint. Endpoint and model identifiers remain editable, including local models.</p><a class="button" href="#work">${I('arrow')}Configure the researcher</a></section></div>
  <div class="two-column"><section class="card"><div class="card-header"><h2>The portable research contract</h2><span class="pill">Inspectable JSON</span></div><div class="steps-content"><div class="numbered-step"><span class="step-number">1</span><div><strong>Prepare the original work</strong><p>Your task, baseline, source evidence, labels and bounded budget travel together. Credentials stay outside the packet.</p></div></div><div class="numbered-step"><span class="step-number">2</span><div><strong>Keep selection separate from qualification</strong><p>The research model sees development evidence. The engine freezes its selection before running the held-out and regression comparisons.</p></div></div><div class="numbered-step"><span class="step-number">3</span><div><strong>Bring back the receipts</strong><p>Import the runner’s report to verify its hashes, recompute its outcomes, and inspect the exact cases and model calls.</p></div></div></div><div class="card-footer"><button class="button small" data-action="import">${I('upload')}Import & verify report</button><span class="small-note">Same report format in every route.</span></div></section>
  <section class="card"><div class="card-header"><h2>Local runner</h2><span class="pill">Node 20+</span></div><div class="workflow-code"><pre class="code-block"># Extract the tool kit, then configure your model.
# Keep the API key in your environment.
export FLYWHEEL_ENDPOINT='https://openrouter.ai/api/v1/chat/completions'
export FLYWHEEL_MODEL='${esc(initialPreset.model)}'
export FLYWHEEL_API_KEY='YOUR_KEY'

node scripts/run.mjs \\
  --request work.json \\
  --output result.json</pre><p class="small-note">Use your downloaded work packet as <code>work.json</code>. The guide covers model settings and local endpoints. Browser transport errors can be resolved by running the same packet locally.</p></div><div class="card-footer"><a class="subtle-link" href="SOURCES.json" target="_blank" rel="noopener">Preset sources and provenance ↗</a><a class="subtle-link" href="https://github.com/BigBirdReturns/axm-tools/tree/main/agent-flywheel" target="_blank" rel="noopener noreferrer">Source code ↗</a></div></section></div>
  ${state.handoff?`<section class="card handoff-preview"><div class="card-header"><h2>Prepared agent handoff</h2><button class="button small" data-action="copy-handoff-existing">${I('copy')}Copy again</button></div><pre class="code-block">${esc(state.handoff)}</pre></section>`:''}`;
}
function render() {
  $('#main').innerHTML = state.view==='results'?resultsView():state.view==='workflow'?workflowView():workView();
  if($('#apiKey')) $('#apiKey').value = state.form.apiKey;
  for(const el of document.querySelectorAll('.nav-item')) { const active=el.dataset.view===state.view; el.classList.toggle('active',active); if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current'); }
  $('#result-dot').hidden = !state.report && !state.busy;
  document.title = `${state.view==='work'?'Agent research':state.view==='results'?'Research results':'Your workflow'} · Agent Flywheel · AXM Tools`;
  bindDropZone();
}
function route() { const view=location.hash.slice(1).split('?')[0]; state.view=['work','results','workflow'].includes(view)?view:'work'; render(); closeNavigation(); }
function navigate(view) { if(state.view===view)render();else location.hash=view; }
function closeNavigation() { $('#sidebar').classList.remove('open'); $('#nav-backdrop').classList.remove('open'); $('#menu-button').setAttribute('aria-expanded','false'); }
function invalidateWork() { state.preparedWork=null; state.preflight=null; state.preflightError=''; state.handoff=''; state.error=''; schedulePreflight(); }
function modelConfig() { const f=state.form,config={provider:f.provider,endpoint:f.endpoint.trim(),model:f.model.trim(),apiKey:f.apiKey,effort:f.effort || undefined,maxTokens:Number(f.maxTokens),timeoutMs:Number(f.timeoutMs)}; if(f.temperature!=='')config.temperature=Number(f.temperature);if(f.topP!=='')config.topP=Number(f.topP);return config; }
function workConfig() { const evidence=collectEvidence(),f=state.form;if(!f.goal.trim())throw new Error('Add a research objective so the model has a concrete question to investigate.');return {goal:f.goal,taskContract:f.taskContract,baselinePrompt:f.baselinePrompt,evidence,mode:f.mode,metric:f.metric,candidateLimit:Number(f.candidateLimit),caseLimit:Number(f.caseLimit),maxCalls:Number(f.maxCalls),seed:Number(f.seed)}; }
function schedulePreflight() {
  clearTimeout(preflightTimer);const generation=++preflightGeneration;
  if(state.busy)return;
  preflightTimer=setTimeout(async()=>{try{const work=await prepareWork(workConfig());if(generation!==preflightGeneration)return;state.preflight=work;state.preflightError='';}catch(error){if(generation!==preflightGeneration)return;state.preflight=null;state.preflightError=error.message || String(error);}const target=$('#run-budget');if(target)target.innerHTML=budgetSummary();},140);
}
async function prepareCurrent() {
  const work=await prepareWork(workConfig());
  state.preparedWork=work;state.preflight=work;state.preflightError='';const target=$('#run-budget');if(target)target.innerHTML=budgetSummary();return work;
}
async function prepareOrShowError() { try { return await prepareCurrent(); } catch(error) { if(state.view!=='work'){state.view='work';location.hash='work';render();}setError(error.message || String(error));return null;} }
async function copyText(text, message) {
  try { if(!navigator.clipboard?.writeText)throw new Error('Clipboard unavailable'); await navigator.clipboard.writeText(text); }
  catch { const area=document.createElement('textarea');area.value=text;area.style.position='fixed';area.style.left='-10000px';document.body.append(area);area.select();const copied=document.execCommand('copy');area.remove();if(!copied){openDialog('Copy this handoff',`<pre class="code-block light">${esc(text)}</pre>`,'Clipboard access is unavailable in this browser.');return;} }
  toast(message || 'Copied');
}
function downloadJSON(value, filename) { const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000); }
async function handoff() { const work=await prepareOrShowError();if(!work)return;state.handoff=await buildHandoff(work);await copyText(state.handoff,'Agent handoff copied. Attach the work packet for the runner.');if(state.view==='workflow')render(); }
async function startRun() {
  if(state.busy)return;
  const work=await prepareOrShowError();if(!work)return;
  let client;try{client=state.demo?createDemoClient():createClient(modelConfig());if(!state.demo&&state.form.provider==='openrouter'&&!state.form.apiKey.trim())throw new Error('Enter your OpenRouter API key, choose another endpoint, or use Copy agent handoff with your existing agent.');}catch(error){setError(error.message || String(error));return;}
  state.controller=new AbortController();state.busy=true;state.runError='';state.error='';state.events=[];state.report=null;state.verification=null;state.runMetadata=client.metadata;state.imported=false;state.resultTab='findings';state.caseSplit='all';state.caseQuery='';navigate('results');
  try {
    const report=await runResearch(work,{client,signal:state.controller.signal,onEvent:event=>{state.events.push(event);if(state.view==='results')render();}});
    state.report=report;state.verification=await verifyReport(report);
  } catch(error) { state.runError=error.message || String(error); }
  finally { state.busy=false;state.controller=null;render();toast(state.report?(verdictLabels[state.report.verdict] || human(state.report.verdict)):state.runError); }
}
function loadSample() {
  if(state.busy)return;
  const keepKey=state.form.apiKey;
  state.form={...defaults(),...Object.fromEntries(['goal','taskContract','baselinePrompt','mode','metric','candidateLimit','caseLimit','maxCalls','seed'].filter(k=>SAMPLE_CONFIG[k]!==undefined).map(k=>[k,SAMPLE_CONFIG[k]])),evidenceText:SAMPLE_CONFIG.evidenceText || JSON.stringify(SAMPLE_CONFIG.evidence?.records || [],null,2),apiKey:keepKey};
  state.demo=true;state.sampleLoaded=true;state.files=[];state.evidence=null;state.error='';state.parseError='';invalidateWork();updateEvidenceStatus();navigate('work');toast('Synthetic example loaded with the deterministic demo adapter.');
}
async function addFiles(files) {
  if(state.busy)return;
  for(const file of files){try{if(file.size>10*1024*1024)throw new Error(`${file.name} exceeds the 10 MB file limit.`);const text=await file.text();const parsed=parseEvidence(text,file.name);state.files.push({name:file.name,bytes:file.size,parsed});}catch(error){setError(error.message || String(error));}}
  state.sampleLoaded=false;invalidateWork();updateEvidenceStatus();
}
function bindDropZone() { const drop=$('#file-drop');if(!drop)return;for(const type of ['dragenter','dragover'])drop.addEventListener(type,event=>{event.preventDefault();drop.classList.add('dragover');});for(const type of ['dragleave','drop'])drop.addEventListener(type,event=>{event.preventDefault();drop.classList.remove('dragover');});drop.addEventListener('drop',event=>addFiles(event.dataTransfer.files)); }
async function importReport(file) {
  if(!file || state.busy)return;
  try { if(file.size>64*1024*1024)throw new Error('The report exceeds the 64 MB browser import limit.');const report=JSON.parse(await file.text());const verification=await verifyReport(report);if(!verification.valid)throw new Error(`Report verification failed: ${verification.errors.join('; ')}`);state.report=report;state.verification=verification;state.imported=true;state.runError='';state.resultTab='findings';state.caseSplit='all';state.caseQuery='';state.runMetadata=null;navigate('results');toast('Report imported. Hashes and measured outcomes verified.'); }
  catch(error) { toast(error.message || String(error));openDialog('Report import needs attention',`<p class="summary-text">${esc(error.message || String(error))}</p>`,'The existing result remains available.'); }
}
function openDialog(title,body,subline='') { dialogReturnFocus=document.activeElement;$('#dialog-root').innerHTML=`<div class="dialog-backdrop" data-action="close-dialog"></div><section class="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><header class="dialog-header"><div><div class="eyebrow">RESEARCH EVIDENCE</div><h2 id="dialog-title">${esc(title)}</h2>${subline?`<p>${esc(subline)}</p>`:''}</div><button class="icon-button" data-action="close-dialog" aria-label="Close evidence inspector">${I('close')}</button></header><div class="dialog-body">${body}</div></section>`;document.body.style.overflow='hidden';$('.dialog [data-action="close-dialog"]').focus(); }
function closeDialog() { if(!$('.dialog'))return;$('#dialog-root').innerHTML='';document.body.style.overflow='';if(dialogReturnFocus?.isConnected)dialogReturnFocus.focus(); }
function showRecord(id) { const e=state.report?.work?.evidence || state.evidence;const record=[...(e?.records || []),...(e?.documents || [])].find(r=>String(r.id)===id);openDialog(id,`<pre class="code-block light">${esc(record?pretty(record):'The cited record is retained in the report work packet.')}</pre>`,'Original source record'); }
function showCase(index) { const c=state.report?.cases?.[index];if(!c)return;openDialog(c.id,`<h3>Input</h3><pre class="code-block light">${esc(pretty(c.input))}</pre><h3>Supplied reference outcome</h3><pre class="code-block light">${esc(pretty(c.expected))}</pre><h3>Measured outputs</h3><div class="output-grid"><div class="output-box"><header><span>Baseline</span>${outcome(c.baseline_passed)}</header><pre>${esc(pretty(c.baseline_output))}</pre></div><div class="output-box"><header><span>Candidate</span>${outcome(c.candidate_passed)}</header><pre>${esc(pretty(c.candidate_output))}</pre></div></div>`,`${human(c.split)} · ${human(state.report?.work?.metric || 'reference')} evaluator`); }

document.addEventListener('input',event=>{
  const fieldName=event.target.dataset.field;
  if(fieldName&&fieldName!=='preset'){state.form[fieldName]=event.target.value;if(!['apiKey','endpoint','model','effort','maxTokens','temperature','topP','timeoutMs','provider'].includes(fieldName))invalidateWork();if(['goal','taskContract','baselinePrompt','evidenceText'].includes(fieldName))state.sampleLoaded=false;if(fieldName==='evidenceText'){clearTimeout(parseTimer);parseTimer=setTimeout(updateEvidenceStatus,180);}const budget=$('#run-budget');if(budget)budget.innerHTML=budgetSummary();}
  if(event.target.id==='case-search'){state.caseQuery=event.target.value;$('#case-table').innerHTML=caseTable(state.report);}
});
document.addEventListener('change',event=>{
  if(event.target.id==='preset'){const id=event.target.value;state.demo=id==='demo';if(!state.demo){const p=PROVIDER_PRESETS.find(p=>p.id===id);Object.assign(state.form,{preset:p.id,provider:p.provider,endpoint:p.endpoint,model:p.model,effort:p.effort || '',maxTokens:p.maxTokens,temperature:p.temperature ?? '',topP:p.topP ?? ''});}render();}
  if(event.target.id==='evidence-files'){addFiles(event.target.files);event.target.value='';}
  if(event.target.id==='report-file'){importReport(event.target.files[0]);event.target.value='';}
});
document.addEventListener('click',async event=>{
  const row=event.target.closest('[data-case]');if(row){showCase(Number(row.dataset.case));return;}
  const el=event.target.closest('[data-action]');if(!el || el.disabled)return;
  switch(el.dataset.action){
    case 'mode':state.form.mode=el.dataset.mode;invalidateWork();render();break;
    case 'sample':loadSample();break;
    case 'reset':if(state.busy)break;state.form=defaults();state.files=[];state.evidence=null;state.demo=false;state.sampleLoaded=false;state.parseError='';invalidateWork();render();toast('Work cleared. Credentials removed from memory.');break;
    case 'remove-file':state.files.splice(Number(el.dataset.index),1);invalidateWork();updateEvidenceStatus();break;
    case 'show-key':{const key=$('#apiKey');key.type=key.type==='password'?'text':'password';el.setAttribute('aria-label',key.type==='password'?'Show API key':'Hide API key');el.setAttribute('aria-pressed',String(key.type==='text'));break;}
    case 'handoff':await handoff();break;
    case 'copy-handoff-existing':await copyText(state.handoff,'Agent handoff copied');break;
    case 'work-download':{const work=state.busy?state.preparedWork:await prepareOrShowError();if(work)downloadJSON(work,'work.json');break;}
    case 'report-work-download':if(state.report?.work)downloadJSON(state.report.work,'work.json');break;
    case 'run':await startRun();break;
    case 'cancel':if(state.controller){state.controller.abort();toast('Cancellation requested. Retaining partial research evidence.');}break;
    case 'import':if(!state.busy)$('#report-file').click();break;
    case 'report-download':if(state.report)downloadJSON(state.report,`${state.report.run_id || 'agent-flywheel'}-report.json`);break;
    case 'result-tab':state.resultTab=el.dataset.tab;render();break;
    case 'case-filter':state.caseSplit=el.dataset.filter;render();break;
    case 'record':showRecord(el.dataset.record);break;
    case 'close-dialog':closeDialog();break;
  }
});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){closeDialog();closeNavigation();}if(event.key==='Enter'&&event.target.matches('[data-case]'))showCase(Number(event.target.dataset.case));if(event.key==='Tab'&&$('.dialog')){const nodes=[...$('.dialog').querySelectorAll('button,a,input,select,textarea,[tabindex="0"]')].filter(x=>!x.disabled);const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
$('#menu-button').addEventListener('click',()=>{const open=!$('#sidebar').classList.contains('open');$('#sidebar').classList.toggle('open',open);$('#nav-backdrop').classList.toggle('open',open);$('#menu-button').setAttribute('aria-expanded',String(open));});
$('#nav-backdrop').addEventListener('click',closeNavigation);
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload',event=>{if(state.busy){event.preventDefault();event.returnValue='';}});
updateEvidenceStatus();route();
