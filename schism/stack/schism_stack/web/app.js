'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const text = (value) => typeof value === 'string' ? value : value == null ? '' : JSON.stringify(value);
  const status = (value) => String(value || 'unknown').toLowerCase();
  const activeJob = (job) => ['queued', 'running'].includes(status(job.status));
  const terminalJob = (job) => ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(status(job.status));
  const human = (value) => String(value || 'Unknown').replace(/[_.-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  const when = (value) => { if (!value) return 'Not recorded'; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(date); };
  const bytes = (value) => { const n = Number(value); if (!Number.isFinite(n)) return 'Not recorded'; if (n < 1024) return `${n} B`; if (n < 1048576) return `${(n / 1024).toFixed(1)} KiB`; return `${(n / 1048576).toFixed(1)} MiB`; };
  const short = (value, length = 14) => { const s = String(value || ''); return s.length > length ? `${s.slice(0, length)}…` : s || 'Not recorded'; };
  const pretty = (value) => JSON.stringify(value, null, 2);
  const sorted = (items, field = 'created_at') => [...items].sort((a, b) => String(b[field] || '').localeCompare(String(a[field] || '')));
  const initialState = {applications:[],releases:[],jobs:[],events:[],trust:[],peers:[]};
  let state = initialState;
  const sessionStorageKey = 'schism.console.session';
  let token = readBootstrapToken();
  let locked = !token;
  let connected = false;
  let loaded = false;
  let lastObserved = null;
  let currentView = 'applications';
  let selectedApp = null;
  let selectedRelease = null;
  let selectedJob = null;
  let packageFilter = null;
  let detailApp = null;
  let detailRelease = null;
  let uploading = false;
  let exporting = false;
  let refreshing = null;
  let fetchingJob = false;
  let pollTimer = null;
  let uncertain = null;
  let notice = null;
  let inspectingPeer = null;
  const watchedJobs = new Map();
  const jobDetails = new Map();
  const inspectedReleases = new Map();
  const pendingRequests = new Map();
  const viewCopy = {
    applications: ['Applications','Manage the software you run, its releases and its history.'],
    packages: ['Packages','Verify a release, choose its publisher authority, then deploy it.'],
    activity: ['Activity','Inspect real jobs, retained output and lifecycle transitions.'],
    trust: ['Publisher trust','Control which publishers may deploy which application IDs.']
  };

  class ApiError extends Error {
    constructor(message, httpStatus = 0, body = null) { super(message); this.name = 'ApiError'; this.status = httpStatus; this.body = body; }
  }

  function readBootstrapToken() {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const supplied = params.get('token');
    if (params.has('token')) {
      params.delete('token');
      const remainder = params.toString();
      history.replaceState(history.state,'',window.location.pathname + window.location.search + (remainder ? '#' + remainder : ''));
      if (typeof supplied === 'string' && /^[A-Za-z0-9_-]{24,256}$/.test(supplied)) {
        try { sessionStorage.setItem(sessionStorageKey,supplied); } catch (_) { /* The current tab can still use its in-memory token. */ }
        return supplied;
      }
      try { sessionStorage.removeItem(sessionStorageKey); } catch (_) { /* An invalid supplied token never reuses an older session. */ }
      return '';
    }
    try { return sessionStorage.getItem(sessionStorageKey) || ''; } catch (_) { return ''; }
  }

  function isSessionRefusal(error) {
    return [401,403,409].includes(error.status) && /session token|token.{0,30}(missing|expired|invalid)|session.{0,30}(missing|expired|invalid)/i.test(error.message);
  }

  function lockConsole() {
    token = ''; locked = true; connected = false; loaded = false; lastObserved = null;
    state = {...initialState}; notice = null; uncertain = null;
    inspectedReleases.clear(); jobDetails.clear(); watchedJobs.clear(); pendingRequests.clear();
    selectedApp = selectedRelease = selectedJob = detailApp = detailRelease = null;
    try { sessionStorage.removeItem(sessionStorageKey); } catch (_) { /* No stored token remains usable. */ }
    clearTimeout(pollTimer); renderNotice(); render();
    announce('Console locked. Open the complete private console URL printed by the current launcher session.');
  }

  async function request(path, options = {}, timeout = 20000) {
    if (!token) throw new ApiError('Open the complete private console URL printed by the SCHISM launcher.',401);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const headers = new Headers(options.headers || {});
      headers.set('X-SCHISM-Token',token);
      const response = await fetch(path, {credentials:'same-origin',cache:'no-store',...options,headers,signal:controller.signal});
      const raw = await response.text();
      let body;
      try { body = raw ? JSON.parse(raw) : {}; }
      catch (_) { throw new ApiError(response.ok ? 'The service returned an unreadable response.' : `The service returned HTTP ${response.status}.`, response.status); }
      if (!response.ok) {
        const detail = body.error || body.message || body.detail || body.reason || `Request refused (HTTP ${response.status}).`;
        const failure = new ApiError(typeof detail === 'string' ? detail : pretty(detail), response.status, body);
        if (isSessionRefusal(failure)) lockConsole();
        throw failure;
      }
      return body;
    } catch (error) {
      if (error.name === 'AbortError') throw new ApiError('The local service did not respond before the request timed out.');
      throw error;
    } finally { clearTimeout(timer); }
  }

  async function getToken() {
    if (!token) { lockConsole(); return null; }
    const result = await request('/api/token');
    if (result.token !== token) { lockConsole(); throw new ApiError('The service did not confirm the current session token.'); }
    return token;
  }

  async function write(path, body, type = 'application/json') {
    return request(path, {method:'POST',headers:{'Content-Type':type},body:type === 'application/json' ? JSON.stringify(body) : body}, type === 'application/json' ? 30000 : 120000);
  }

  function setHTML(node, html) { if (node && node.innerHTML !== html) node.innerHTML = html; }
  function setText(id, value) { const node = $(id); if (node && node.textContent !== String(value ?? '')) node.textContent = String(value ?? ''); }
  function reveal(id, visible) { const node = $(id); if (node) node.classList.toggle('hidden', !visible); }
  function announce(message) { setText('announcer', message); }
  function appById(id) { return state.applications.find((app) => app.id === id); }
  function releases() {
    const records = new Map([...inspectedReleases.entries()]);
    state.releases.forEach((release) => records.set(release.release_id, release));
    return sorted([...records.values()]);
  }
  function releaseById(id) { return state.releases.find((release) => release.release_id === id) || inspectedReleases.get(id); }
  function appJobs(id) { return sorted(state.jobs.filter((job) => job.app_id === id)); }
  function appBusy(id) { return state.jobs.some((job) => job.app_id === id && activeJob(job)) || [...pendingRequests.values()].some((request) => request.appId === id) || [...watchedJobs.values()].some((job) => job.appId === id); }
  function running(app) { return ['running','healthy','starting'].includes(status(app.status)) || Boolean(app.process && app.process.pid && !['stopped','failed','exited','interrupted'].includes(status(app.status))); }
  function trusted(release) {
    if (typeof release.trusted === 'boolean') return release.trusted;
    return state.trust.some((record) => {
      const key = record.key_id || record.publisher?.key_id;
      const scopes = Array.isArray(record.apps) ? record.apps : [];
      return key === release.publisher?.key_id && !record.revoked && scopes.some((scope) => scope === '*' || scope === release.application?.id);
    });
  }
  function activePublisherScopes(release) {
    const record = state.trust.find((item) => (item.key_id || item.publisher?.key_id) === release.publisher?.key_id && !item.revoked && status(item.status) !== 'revoked');
    return record && Array.isArray(record.apps) ? record.apps.filter((scope) => typeof scope === 'string' && scope !== '*') : [];
  }
  function badge(value, label) {
    const s = status(value);
    const cls = ['running','healthy','succeeded','trusted','verified','accepted','active'].includes(s) ? 'good' : ['failed','error','unhealthy','revoked','refused'].includes(s) ? 'bad' : ['queued','starting','interrupted','unknown','untrusted','pending','cancelling'].includes(s) ? 'warn' : ['staged','installed','ready'].includes(s) ? 'info' : '';
    return `<span class="badge ${cls}">${escape(label || human(value))}</span>`;
  }
  function hashRow(value, label = 'Copy identifier') {
    return `<div class="hash-row"><span class="hash">${escape(value || 'Not recorded')}</span>${value ? `<button type="button" class="copy-button" data-action="copy" data-value="${escape(value)}" aria-label="${escape(label)}">Copy</button>` : ''}</div>`;
  }
  function showNotice(kind, title, message = '', jobId = null, source = null) {
    notice = {kind,title,message,jobId,source}; renderNotice();
    announce(`${title}${message ? '. ' + message : ''}`);
  }
  function renderNotice() {
    const node = $('notice');
    if (!notice && !uncertain) { node.classList.add('hidden'); return; }
    const n = uncertain ? {kind:'warning',title:'The request response was interrupted',message:'The operation may already exist. Retry the same request identity or inspect Activity before submitting another operation.',jobId:null} : notice;
    node.className = `notice ${n.kind || ''}`;
    node.innerHTML = `<div><strong>${escape(n.title)}</strong>${n.message ? `<p>${escape(n.message)}</p>` : ''}</div><div class="notice-buttons">${uncertain ? '<button type="button" class="button secondary" data-action="retry-request">Retry same request</button><button type="button" class="button ghost" data-action="show-activity">Inspect activity</button>' : n.jobId ? `<button type="button" class="button secondary" data-action="select-job" data-id="${escape(n.jobId)}">View job</button>` : ''}${!uncertain ? '<button type="button" class="notice-close" data-action="dismiss-notice" aria-label="Dismiss notification">×</button>' : ''}</div>`;
  }

  function setView(view, moveFocus = false) {
    if (!(view in viewCopy)) return;
    currentView = view;
    Object.keys(viewCopy).forEach((name) => reveal(`view-${name}`, name === view));
    document.querySelectorAll('[data-view]').forEach((button) => {
      button.classList.toggle('active', button.dataset.view === view);
      if (button.dataset.view === view) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current');
    });
    setText('view-title', viewCopy[view][0]);
    setText('view-description', viewCopy[view][1]);
    document.title = `${viewCopy[view][0]} · SCHISM`;
    render();
    if (view === 'activity' && selectedJob) refreshJob();
    if (moveFocus) $('main').focus({preventScroll:true});
  }

  function renderChrome() {
    $('connection').className = `connection ${locked ? 'locked' : connected ? 'online' : loaded ? 'offline' : ''}`;
    setText('connection-text', locked ? 'Private session required' : connected ? 'Local service connected' : loaded ? 'Local service unreachable' : 'Connecting to local service');
    setText('operator-name', locked ? 'Workspace locked' : state.identity?.name || (loaded ? 'Local operator' : 'Connecting…'));
    setText('view-title',locked ? 'Workspace locked' : viewCopy[currentView][0]);
    setText('view-description',locked ? 'Use the private console link from the running SCHISM launcher.' : viewCopy[currentView][1]);
    document.querySelectorAll('[data-view]').forEach((button) => { button.disabled = locked; });
    setText('stack-version', state.version ? `SCHISM ${state.version}` : 'SCHISM');
    const platform = typeof state.platform === 'string' ? state.platform : state.platform?.system || state.platform?.name || 'This computer';
    setText('platform-label', platform);
    setText('last-observed', lastObserved ? `${connected ? 'Observed' : 'Last observed'} ${when(lastObserved)}` : 'Waiting for workspace state');
    const active = state.jobs.filter(activeJob).length;
    setText('metric-apps', loaded ? state.applications.length : '…');
    setText('metric-running', loaded ? state.applications.filter((app) => app.kind === 'service' && running(app)).length : '…');
    setText('metric-jobs', loaded ? active : '…');
    setText('metric-packages', loaded ? releases().length : '…');
    setText('nav-app-count', state.applications.length);
    setText('nav-package-count', releases().length);
    setText('nav-job-count', active);
    document.querySelectorAll('button[data-action="import"]').forEach((button) => { button.disabled = !connected || uploading; });
    $('export-evidence').disabled = !connected || exporting;
    $('export-evidence').textContent = exporting ? 'Preparing export…' : 'Export evidence';
    $('drop-zone').classList.toggle('uploading', uploading);
    setText('upload-label', uploading ? 'Verifying the package…' : 'Drop a .schism package here');
    setText('upload-detail', uploading ? 'Checking signed metadata and the complete file inventory. No application code is running.' : 'or choose a file from this computer. Import verifies its signature and inventory without executing it.');
  }

  function renderApplications() {
    const query = $('app-search').value.trim().toLowerCase();
    const list = [...state.applications].sort((a,b) => String(a.name || a.id).localeCompare(String(b.name || b.id)));
    const visible = list.filter((app) => `${app.id} ${app.name} ${app.version}`.toLowerCase().includes(query));
    reveal('app-empty', loaded && !list.length);
    reveal('app-workspace', !loaded || list.length > 0);
    if (!selectedApp || !appById(selectedApp)) selectedApp = list[0]?.id || null;
    setHTML($('app-list'), !loaded ? '<div class="list-placeholder">Loading the application inventory…</div>' : !visible.length ? '<div class="list-placeholder">No applications match this search.</div>' : visible.map((app) => `<button type="button" class="inventory-item ${app.id === selectedApp ? 'selected' : ''}" data-action="select-app" data-id="${escape(app.id)}" aria-pressed="${app.id === selectedApp}"><div class="inventory-item-top"><h3>${escape(app.name || app.id)}</h3>${badge(app.status)}</div><div class="item-id">${escape(app.id)}</div><div class="item-meta"><span>${escape(human(app.kind))}</span><span aria-hidden="true">·</span><span class="version">${escape(app.version || 'No active version')}</span><span aria-hidden="true">·</span><span>Generation ${escape(app.generation ?? 0)}</span></div></button>`).join(''));
    renderAppDetail();
    renderPeers();
  }

  function renderAppDetail() {
    const app = appById(selectedApp);
    const container = $('app-detail');
    if (!app) { detailApp = null; setHTML(container,'<div class="panel-placeholder"><h3>Application state</h3><p>Select an installed application to inspect its current version, lifecycle controls and retained work.</p></div>'); return; }
    if (detailApp !== app.id) {
      detailApp = app.id;
      container.innerHTML = `<div class="detail-header"><div class="detail-heading-row"><div><div class="eyebrow" id="detail-kind"></div><h2 id="detail-name"></h2><div class="subtitle" id="detail-id"></div></div><div id="detail-status"></div></div></div>
        <div class="detail-body"><div class="app-actions"><button type="button" class="button primary" id="primary-app-action"></button><button type="button" class="button secondary" id="stop-app" data-action="stop-app">Stop service</button><button type="button" class="button secondary" data-action="choose-update">Choose update</button><button type="button" class="button secondary" id="rollback-app" data-action="rollback-app">Restore previous code</button><button type="button" class="button ghost" id="recover-app" data-action="recover-app">Recover status</button></div><div id="app-last-error" class="inline-error hidden"></div>
        <dl class="detail-grid"><div><dt>Active version</dt><dd id="detail-version" class="mono"></dd></div><div><dt>Generation</dt><dd id="detail-generation" class="mono"></dd></div><div><dt>Process</dt><dd id="detail-process" class="mono"></dd></div><div><dt>Started</dt><dd id="detail-started"></dd></div><div><dt>Persistent data schema</dt><dd id="detail-schema" class="mono"></dd></div><div><dt>Application type</dt><dd id="detail-type"></dd></div><div class="full"><dt>Active release identity</dt><dd id="detail-release"></dd></div><div class="full" id="previous-release-row"><dt>Retained previous release</dt><dd id="detail-previous"></dd></div><div class="full"><dt>Persistent application data</dt><dd id="detail-data" class="hash"></dd></div><div class="full hidden" id="health-row"><dt>Health endpoint</dt><dd id="detail-health"></dd></div></dl>
        <p class="inline-note" id="app-action-note"></p></div>
        <div class="detail-section"><h3>Latest operation</h3><div id="app-latest-job"></div><div id="app-recent-history" class="app-history-list"></div></div>
        <details class="section-details" id="environment-details"><summary>Private runtime configuration</summary><p>Saving replaces the complete set of runtime overrides. Include every variable needed for the next start or run. Existing values remain hidden and stay outside evidence exports.</p><p id="configured-environment-names"></p><form id="environment-form"><div class="environment-rows" id="environment-rows"></div><div class="environment-form-actions"><button type="button" class="button secondary small" data-action="add-environment">Add variable</button><button type="submit" class="button primary small" id="save-environment">Save replacement configuration</button></div><p class="environment-status">Values are concealed and are cleared from this form after submission.</p></form></details>`;
      addEnvironmentRow();
    }
    const busy = appBusy(app.id);
    const allowed = connected && !busy && !uncertain;
    const task = app.kind === 'task';
    setText('detail-kind', `${task ? 'TASK APPLICATION' : 'SERVICE APPLICATION'} · LOCAL EXECUTION`);
    setText('detail-name', app.name || app.id);
    setText('detail-id', app.id);
    setHTML($('detail-status'),badge(app.status));
    const primary = $('primary-app-action');
    primary.dataset.action = task ? 'run-app' : 'start-app';
    primary.textContent = busy ? 'Operation in progress…' : task ? 'Run task' : running(app) ? 'Service running' : 'Start service';
    primary.disabled = !allowed || (!task && running(app));
    $('stop-app').classList.toggle('hidden', task);
    $('stop-app').disabled = !allowed || !running(app);
    $('rollback-app').disabled = !allowed || !app.previous_release_id;
    $('rollback-app').title = app.previous_release_id ? 'Restore the retained code release. Persistent application data is retained and its schema must remain compatible.' : 'A previous code release becomes available after a successful update.';
    $('recover-app').disabled = !connected || busy || Boolean(uncertain);
    $('recover-app').title = 'Reconcile the retained process and operation state without repeating an interrupted task.';
    $('save-environment').disabled = !allowed;
    setText('configured-environment-names',Array.isArray(app.configured_environment) && app.configured_environment.length ? `Currently configured names: ${app.configured_environment.join(', ')}.` : 'No private runtime overrides are recorded.');
    setText('detail-version', app.version || 'Not active');
    setText('detail-generation', app.generation ?? 0);
    setText('detail-process', app.process?.pid ? `PID ${app.process.pid}` : 'No live process recorded');
    setText('detail-started', app.process?.started_at ? when(app.process.started_at) : 'Not running');
    setText('detail-schema', app.data_schema ?? 'Not declared');
    setText('detail-type', task ? 'Task: explicit execution' : 'Service: persistent process');
    setHTML($('detail-release'),hashRow(app.release_id,'Copy active release identity'));
    reveal('previous-release-row',Boolean(app.previous_release_id));
    setHTML($('detail-previous'),hashRow(app.previous_release_id,'Copy retained release identity'));
    setText('detail-data',app.data_path || 'Managed by the local runtime');
    const release = releaseById(app.release_id);
    const url = release?.application?.health?.type === 'http' ? safeLoopbackUrl(release.application.health.url) : null;
    reveal('health-row',Boolean(url));
    setHTML($('detail-health'),url ? `<a href="${escape(url)}" target="_blank" rel="noopener" class="hash">${escape(url)} <span aria-hidden="true">↗</span></a>` : '');
    setText('app-action-note',task ? 'Installing or updating a task selects its code version. Run task explicitly executes it. Restoring previous code retains persistent application data.' : 'Updates start and check the candidate before activation. Restoring previous code retains persistent application data and requires a compatible data schema.');
    reveal('app-last-error',Boolean(app.last_error));
    setText('app-last-error',text(app.last_error));
    const recent = appJobs(app.id)[0];
    setHTML($('app-latest-job'),recent ? `<div class="compact-job"><div><div class="job-label">${escape(human(recent.operation))} ${badge(recent.status)}</div><small>${escape(when(recent.created_at))}</small></div><button type="button" class="button secondary small" data-action="select-job" data-id="${escape(recent.id)}">Inspect output</button></div>` : '<p class="muted small-text">No retained operations for this application.</p>');
    const events = sorted(state.events.filter((event) => eventApp(event) === app.id),'at').slice(0,4);
    setHTML($('app-recent-history'),events.map((event) => `<div class="app-history-line"><span>${escape(eventKind(event))}</span><time>${escape(when(eventTime(event)))}</time></div>`).join(''));
  }

  function safeLoopbackUrl(value) {
    try { const url = new URL(value); return ['http:','https:'].includes(url.protocol) && ['127.0.0.1','localhost','[::1]'].includes(url.hostname) && !url.username && !url.password ? url.href : null; } catch (_) { return null; }
  }

  function renderPackages() {
    let records = releases();
    if (packageFilter) records = records.filter((release) => release.application?.id === packageFilter);
    if (selectedRelease && !releaseById(selectedRelease)) selectedRelease = null;
    if (!selectedRelease && records.length) selectedRelease = records[0].release_id;
    setText('package-filter-label',packageFilter || 'All applications');
    reveal('clear-package-filter',Boolean(packageFilter));
    setHTML($('package-list'),records.length ? records.map((release) => {
      const app = release.application || {};
      const installed = appById(app.id)?.release_id === release.release_id;
      return `<button type="button" class="inventory-item ${release.release_id === selectedRelease ? 'selected' : ''}" data-action="select-release" data-id="${escape(release.release_id)}" aria-pressed="${release.release_id === selectedRelease}"><div class="inventory-item-top"><h3>${escape(app.name || app.id || 'Application')}</h3>${installed ? badge('active','Current') : badge(trusted(release) ? 'trusted' : 'untrusted',trusted(release) ? 'Trusted' : 'Needs trust')}</div><div class="item-id">${escape(app.id)}</div><div class="item-meta"><span class="version">${escape(app.version)}</span><span aria-hidden="true">·</span><span>${escape(human(app.kind))}</span></div><div class="item-meta mono">${escape(short(release.release_id,20))}</div></button>`;
    }).join('') : `<div class="list-placeholder">${loaded ? packageFilter ? 'No imported packages for this application yet. Import its next release above.' : 'No packages have been imported. Choose a .schism file to begin.' : 'Loading local releases…'}</div>`);
    renderPackageDetail();
  }

  function renderPackageDetail() {
    const release = releaseById(selectedRelease);
    const container = $('package-detail');
    if (!release) { detailRelease = null; setHTML(container,'<div class="panel-placeholder"><span class="empty-emblem small-emblem" aria-hidden="true">◇</span><h3>Inspect a package</h3><p>Choose an available release or import a package to see its application, publisher and execution contract.</p></div>'); return; }
    const app = release.application || {};
    const publisher = release.publisher || {};
    if (detailRelease !== release.release_id) {
      detailRelease = release.release_id;
      const files = Array.isArray(release.files) ? release.files : [];
      const manifest = {application:app,publisher,release_id:release.release_id,created_at:release.created_at};
      container.innerHTML = `<div class="detail-header"><div class="detail-heading-row"><div><div class="eyebrow">SIGNED APPLICATION PACKAGE</div><h2>${escape(app.name || app.id)}</h2><div class="subtitle">${escape(app.id)} · ${escape(app.version)} · ${escape(human(app.kind))}</div></div>${badge('verified','Bytes verified')}</div></div>
        <div class="detail-body"><div class="package-step"><span class="step-number">1</span><div><h3>Inspect the release</h3><p>Import checked the signature and closed inventory. Deployment executes this declared application under your operating-system account.</p></div></div><dl class="detail-grid"><div class="full"><dt>Release identity</dt><dd>${hashRow(release.release_id,'Copy package release identity')}</dd></div><div><dt>Created</dt><dd>${escape(when(release.created_at))}</dd></div><div><dt>Persistent data schema</dt><dd class="mono">${escape(app.data_schema ?? 'Not declared')}</dd></div><div><dt>Declared files</dt><dd>${escape(files.length)}</dd></div><div><dt>Payload size</dt><dd>${escape(bytes(files.reduce((sum,file) => sum + Number(file.size || 0),0)))}</dd></div><div class="full"><dt>Argument-vector entrypoint</dt><dd><pre class="command-block">${escape(pretty(app.command || []))}</pre></dd></div><div><dt>Health check</dt><dd>${escape(app.kind === 'task' ? 'Task exit status' : app.health?.type === 'http' ? 'Loopback HTTP' : 'Process observation')}</dd></div><div><dt>Required secret variables</dt><dd class="mono">${escape(Array.isArray(app.secret_env) && app.secret_env.length ? app.secret_env.join(', ') : 'None declared')}</dd></div></dl></div>
        <div class="detail-section"><div class="package-step"><span class="step-number">2</span><div><h3>Choose publisher authority</h3><p>Compare this fingerprint through a trusted channel. Publisher names are supplied by the signer.</p></div></div><span class="trust-label">${escape(publisher.name || 'Publisher')} · PUBLIC KEY FINGERPRINT</span>${hashRow(publisher.key_id,'Copy publisher fingerprint')}<div id="package-trust-status" class="action-help"></div><div class="scope-row" id="package-trust-controls"><label for="trust-scope">Grant deployment authority for<select id="trust-scope"><option value="application">Only ${escape(app.id)}</option><option value="all">All application IDs</option></select></label><button type="button" class="button primary" id="trust-publisher" data-action="trust-publisher">Trust for this application</button></div><p id="scope-explanation" class="action-help">This grant applies to this publisher and application ID, including future signed releases of that application.</p></div>
        <div class="detail-section"><div class="package-step"><span class="step-number">3</span><div><h3 id="deployment-heading">Deploy the selected release</h3><p id="deployment-description"></p></div></div><div id="package-schema-note" class="inline-note warn hidden"></div><div class="button-row"><button type="button" class="button primary" id="deploy-package" data-action="deploy-package">Deploy release</button><button type="button" class="button secondary" data-action="download-manifest">Download metadata</button></div><p id="deployment-note" class="action-help"></p></div>
        <details class="section-details"><summary>Private configuration before deployment</summary><p>Configure required secrets or local environment overrides before the first deployment. Saving replaces all overrides for this application ID. Include every required value; values are concealed and excluded from evidence exports.</p><form id="package-environment-form" data-app-id="${escape(app.id)}"><div class="environment-rows" id="package-environment-rows"></div><div class="environment-form-actions"><button type="button" class="button secondary small" data-action="add-environment" data-target="package-environment-rows">Add variable</button><button type="submit" class="button primary small" id="save-package-environment">Save private configuration</button></div></form></details>
        <details class="section-details"><summary>Verified file inventory (${escape(files.length)})</summary><div class="inventory-table-wrap"><table class="inventory-table"><thead><tr><th scope="col">Path</th><th scope="col">Size</th><th scope="col">SHA-256</th></tr></thead><tbody>${files.map((file) => `<tr><td>${escape(file.path)}</td><td>${escape(bytes(file.size))}</td><td class="hash">${escape(file.sha256)}</td></tr>`).join('')}</tbody></table></div></details><details class="section-details"><summary>Inspect signed application metadata</summary><pre class="json-block">${escape(pretty(manifest))}</pre></details>`;
      if (Array.isArray(app.secret_env) && app.secret_env.length) app.secret_env.forEach((name) => addEnvironmentRow('package-environment-rows',name));
      else addEnvironmentRow('package-environment-rows');
    }
    const isTrusted = trusted(release);
    const installed = appById(app.id);
    const current = installed?.release_id === release.release_id;
    const busy = appBusy(app.id) || [...pendingRequests.values()].some((request) => request.operation === 'trust') || state.jobs.some((job) => job.operation === 'trust' && activeJob(job)) || [...watchedJobs.values()].some((job) => job.operation === 'trust');
    setHTML($('package-trust-status'),`${badge(isTrusted ? 'trusted' : 'untrusted',isTrusted ? 'Authorized for this application' : 'Deployment authority required')}`);
    reveal('package-trust-controls',!isTrusted);
    $('trust-publisher').disabled = !connected || busy || Boolean(uncertain);
    $('save-package-environment').disabled = !connected || busy || Boolean(uncertain);
    const scope = $('trust-scope').value;
    const retainedScopes = activePublisherScopes(release);
    const resultingScopes = [...new Set([...retainedScopes,app.id])].sort();
    const previousOthers = retainedScopes.filter((id) => id !== app.id);
    $('trust-scope').options[0].textContent = previousOthers.length ? `${app.id} + ${previousOthers.length} existing grant${previousOthers.length === 1 ? '' : 's'}` : `Only ${app.id}`;
    $('trust-publisher').textContent = scope === 'all' ? 'Trust for all applications' : previousOthers.length ? 'Add application scope' : 'Trust for this application';
    setText('scope-explanation',isTrusted ? 'The current publisher grant covers this application. Manage or revoke its scope in Publisher trust.' : scope === 'all' ? 'This broad grant authorizes this publisher to deploy any application ID.' : `Resulting active scope: ${resultingScopes.join(', ')}. Existing active grants are preserved; revoked grants are not restored automatically. Future signed releases within this scope are authorized.`);
    const button = $('deploy-package');
    button.disabled = !connected || !isTrusted || current || busy || Boolean(uncertain);
    button.textContent = busy ? 'Operation in progress…' : current ? 'Current release' : installed ? `Update to ${app.version}` : app.kind === 'task' ? 'Install task application' : 'Deploy and start service';
    setText('deployment-heading',installed && !current ? 'Update the installed application' : 'Deploy the selected release');
    setText('deployment-description',app.kind === 'task' ? 'Activation selects this code version. It runs only when you explicitly select Run task.' : 'The runtime starts this release and performs its declared health check before accepting activation.');
    setText('deployment-note',current ? 'This exact release is already selected for the application.' : `Uses observed generation ${installed?.generation ?? 0}. A concurrent change causes refusal so you can review the new state.`);
    const mismatch = installed && String(installed.data_schema) !== String(app.data_schema);
    reveal('package-schema-note',Boolean(mismatch));
    setText('package-schema-note',mismatch ? `The data schema changes from ${installed.data_schema} to ${app.data_schema}. Existing persistent data is retained; incompatible activation requires an explicit operator migration workflow.` : '');
  }

  function eventKind(event) { return human(event.kind || event.operation || event.op || event.type || 'Event'); }
  function eventTime(event) { return event.at || event.created_at || event.utc || event.timestamp; }
  function eventApp(event) { return event.app_id || event.application_id || event.body?.app_id || event.detail?.app_id || event.subject || ''; }
  function renderActivity() {
    const all = sorted(state.jobs);
    const filter = $('job-filter').value;
    const list = all.filter((job) => filter === 'all' || (filter === 'active' ? activeJob(job) : ['failed','interrupted','cancelled'].includes(status(job.status))));
    if (!selectedJob && all.length) selectedJob = all[0].id;
    setHTML($('job-list'),list.length ? list.map((job) => `<button type="button" class="inventory-item job-item ${job.id === selectedJob ? 'selected' : ''}" data-action="select-job" data-id="${escape(job.id)}" aria-pressed="${job.id === selectedJob}"><div class="inventory-item-top"><span class="operation-name">${escape(human(job.operation))}</span>${badge(job.status)}</div><div class="item-id">${escape(job.app_id || 'Workspace operation')}</div><div class="item-meta">${escape(when(job.created_at))}</div></button>`).join('') : '<div class="list-placeholder">No jobs in this view. Submitted operations and their terminal outcomes will appear here.</div>');
    renderJobDetail();
    const events = [...state.events].sort((a,b) => String(eventTime(b) || '').localeCompare(String(eventTime(a) || '')));
    setHTML($('event-list'),events.length ? events.slice(0,150).map((event) => `<div class="event-row"><time class="event-time">${escape(when(eventTime(event)))}</time><div><div class="event-kind">${escape(eventKind(event))}</div><div class="event-subject">${escape(eventApp(event) || 'Workspace')}</div></div><details><summary>Inspect record</summary><pre class="json-block">${escape(pretty(event))}</pre></details></div>`).join('') : '<div class="list-placeholder">Lifecycle events will appear as work is recorded.</div>');
  }

  function renderJobDetail() {
    const current = state.jobs.find((job) => job.id === selectedJob);
    const retained = jobDetails.get(selectedJob);
    const job = current ? {...retained,...current} : retained;
    $('refresh-log').disabled = !connected || !selectedJob || fetchingJob;
    reveal('cancel-job',Boolean(job && activeJob(job)));
    $('cancel-job').disabled = !connected || Boolean(uncertain);
    if (!job) {
      setText('job-title',selectedJob ? 'Loading job…' : 'Select a job');
      setText('job-subtitle','Execution output appears here.');
      reveal('job-metadata',false); reveal('job-error',false); reveal('job-result-section',false);
      setText('job-log',selectedJob ? 'Retrieving the retained job…' : 'Select a job to inspect its retained output.');
      return;
    }
    setText('job-title',human(job.operation));
    setText('job-subtitle',`${job.app_id || 'Workspace operation'} · ${human(job.status)}`);
    reveal('job-metadata',true);
    setHTML($('job-metadata'),`<div><span>JOB ID</span><strong>${escape(job.id)}</strong></div><div><span>STATUS</span>${badge(job.status)}</div><div><span>CREATED</span><strong>${escape(when(job.created_at))}</strong></div><div><span>ENDED</span><strong>${escape(job.ended_at ? when(job.ended_at) : activeJob(job) ? 'In progress' : 'Not recorded')}</strong></div>`);
    reveal('job-error',Boolean(job.error)); setText('job-error',text(job.error));
    const output = retained?.log;
    const content = typeof output === 'string' ? output || (activeJob(job) ? 'Waiting for process output…' : 'No process output was recorded for this operation.') : 'Select Refresh log to retrieve the retained output.';
    const log = $('job-log');
    if (log.textContent !== content) { log.textContent = content; if ($('follow-log').checked) log.scrollTop = log.scrollHeight; }
    setText('log-label',activeJob(job) ? 'COMBINED OUTPUT · LIVE TAIL' : 'COMBINED OUTPUT · RETAINED TAIL');
    reveal('job-result-section',job.result != null);
    if (job.result != null) setText('job-result',pretty(job.result));
  }

  function renderTrust() {
    const identity = state.identity || {};
    setHTML($('local-identity'),`<div><div class="eyebrow">THIS WORKSPACE</div><h3>${escape(identity.name || 'Local operator')}</h3><p>The local signing identity records this workspace's releases and exported evidence. Private signing material remains in local state.</p></div><div><span class="trust-label">LOCAL PUBLIC KEY FINGERPRINT</span>${hashRow(identity.key_id,'Copy local public key fingerprint')}<p class="action-help">An exported signature verifies integrity under this key. Recipients establish publisher trust separately.</p></div>`);
    setHTML($('trust-list'),state.trust.length ? state.trust.map((record) => {
      const publisher = record.publisher || {};
      const key = record.key_id || publisher.key_id;
      const scopes = Array.isArray(record.apps) ? record.apps : [];
      const revoked = Boolean(record.revoked) || status(record.status) === 'revoked';
      return `<div class="trust-item"><div><h3>${escape(record.label || publisher.name || record.name || 'Publisher')} ${revoked ? badge('revoked') : ''}</h3><div class="key-copy"><span class="hash">${escape(key || 'No key identifier')}</span>${key ? `<button type="button" class="copy-button" data-action="copy" data-value="${escape(key)}" aria-label="Copy publisher fingerprint">Copy</button>` : ''}</div><div class="trust-scope">${scopes.length ? scopes.map((scope) => `<span class="badge ${scope === '*' ? 'warn' : ''}">${escape(scope === '*' ? 'All application IDs' : scope)}</span>`).join('') : '<span class="badge warn">No application scope recorded</span>'}</div></div><button type="button" class="button danger-outline small" data-action="revoke-publisher" data-key="${escape(key)}" ${!connected || !key || revoked || uncertain ? 'disabled' : ''}>Revoke trust</button></div>`;
    }).join('') : '<div class="list-placeholder">No publisher grants are recorded. Import a package to inspect its signing fingerprint and grant a specific application scope.</div>');
  }

  function renderPeers() {
    const peers = Array.isArray(state.peers) ? state.peers : [];
    setHTML($('peer-list'), peers.length ? peers.map((peer) => `<div class="peer-row"><div><h4>${escape(peer.name)}</h4><p>${escape(peer.host || 'Pinned SSH node')} · ${escape(peer.transport || 'SSH')}</p><span class="hash">${escape(peer.key_id || peer.identity?.key_id || 'Key identity not recorded')}</span></div><button type="button" class="button secondary small" data-action="inspect-peer" data-name="${escape(peer.name)}" ${!connected || inspectingPeer ? 'disabled' : ''}>${inspectingPeer === peer.name ? 'Inspecting…' : 'Inspect node'}</button></div>`).join('') : '<div class="list-placeholder">No remote nodes are registered. The local workspace is fully usable on its own. The operator guide covers enrollment through your existing pinned SSH connection.</div>');
  }

  async function inspectPeer(name) {
    if (!connected || inspectingPeer) return;
    inspectingPeer = name; renderPeers();
    try {
      const remote = await request(`/api/peer-state?name=${encodeURIComponent(name)}`,{},60000);
      if (!remote || !Array.isArray(remote.applications)) throw new ApiError('The node did not return an application inventory.');
      const stamp = new Date().toISOString();
      setHTML($('peer-snapshot'),`<div class="panel-heading"><div><h3>${escape(name)} · observed inventory</h3><p class="muted small-text">${escape(when(stamp))}. This snapshot is read-only; use the documented CLI for remote lifecycle operations.</p></div></div>${remote.applications.length ? `<div class="inventory-table-wrap"><table class="inventory-table"><thead><tr><th>Application</th><th>Version</th><th>State</th></tr></thead><tbody>${remote.applications.map((app) => `<tr><td>${escape(app.name || app.id)}<div class="muted">${escape(app.id)}</div></td><td>${escape(app.version)}</td><td>${badge(app.status)}</td></tr>`).join('')}</tbody></table></div>` : '<div class="list-placeholder">This node has no installed applications.</div>'}`);
      reveal('peer-snapshot',true);
      announce(`Retrieved the application inventory from ${name}.`);
    } catch (error) { showNotice('error',`Could not inspect ${name}`,error.message); }
    finally { inspectingPeer = null; renderPeers(); }
  }

  function render() {
    renderChrome();
    reveal('locked-workspace',locked);
    document.querySelector('.metrics').classList.toggle('hidden',locked);
    Object.keys(viewCopy).forEach((name) => reveal(`view-${name}`,!locked && currentView === name));
    if (locked) return;
    if (currentView === 'applications') renderApplications();
    if (currentView === 'packages') renderPackages();
    if (currentView === 'activity') renderActivity();
    if (currentView === 'trust') renderTrust();
  }

  async function refreshState(quiet = true) {
    if (locked || !token) return null;
    if (refreshing) return refreshing;
    refreshing = (async () => {
      try {
        const next = await request('/api/state');
        if (!next || typeof next !== 'object' || ['applications','releases','jobs','events','trust'].some((key) => !Array.isArray(next[key]))) throw new ApiError('The service returned an invalid workspace state.');
        state = next; loaded = true; connected = true; lastObserved = new Date().toISOString();
        if (notice?.source === 'connection') { notice = null; renderNotice(); }
        const completed = [];
        for (const [id, tracking] of watchedJobs) {
          const job = state.jobs.find((item) => item.id === id);
          if (job && terminalJob(job)) { completed.push({job,tracking}); watchedJobs.delete(id); }
        }
        render();
        for (const {job,tracking} of completed) {
          if (status(job.status) === 'succeeded') showNotice('success',`${tracking.label} completed`,'Workspace state has been refreshed.',job.id);
          else showNotice(status(job.status) === 'failed' ? 'error' : 'warning',`${tracking.label}: ${human(job.status).toLowerCase()}`,text(job.error) || 'Inspect the retained job before deciding what to do next.',job.id);
          if (tracking.onComplete) tracking.onComplete(job);
        }
        if (currentView === 'activity' && selectedJob) await refreshJob(true);
        return state;
      } catch (error) {
        if (locked) return null;
        connected = false; renderChrome(); render();
        if (!quiet || !loaded) showNotice('error','The local service is unavailable',`${error.message} Start the SCHISM service or reconnect to this workspace.`,null,'connection');
        return null;
      } finally { refreshing = null; }
    })();
    return refreshing;
  }

  async function refreshJob(quiet = false) {
    if (!selectedJob || !connected || fetchingJob) return;
    fetchingJob = true;
    const requested = selectedJob;
    try {
      const result = await request(`/api/job?id=${encodeURIComponent(requested)}`);
      if (!result || result.id !== requested) throw new ApiError('The service returned a different job identity.');
      jobDetails.set(requested,result);
      if (jobDetails.size > 20) { const oldest = jobDetails.keys().next().value; if (oldest !== selectedJob) jobDetails.delete(oldest); }
      if (requested === selectedJob && currentView === 'activity') renderJobDetail();
    } catch (error) {
      if (locked) return;
      if (!quiet) showNotice('error','Could not retrieve the job output',error.message);
    } finally { fetchingJob = false; if (currentView === 'activity') renderJobDetail(); }
  }

  function requestId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const buffer = new Uint8Array(16); crypto.getRandomValues(buffer);
    return `ui-${Array.from(buffer,(x) => x.toString(16).padStart(2,'0')).join('')}`;
  }

  async function submit(operation, fields, label, options = {}) {
    if (!connected && !options.payload) { showNotice('error','The local service is unavailable','Reconnect before submitting an operation.',null,'connection'); return null; }
    if (uncertain && !options.payload) { renderNotice(); return null; }
    const payload = options.payload || {operation,request_id:requestId(),...fields};
    const appId = fields.app_id || releaseById(fields.release_id)?.application?.id || null;
    pendingRequests.set(payload.request_id,{appId,operation});
    render();
    try {
      const result = await write('/api/action',payload);
      if (typeof result.job_id !== 'string' || !result.job_id) throw new ApiError('The service did not return the submitted job identity.');
      uncertain = null;
      watchedJobs.set(result.job_id,{label,appId,operation,onComplete:options.onComplete});
      selectedJob = result.job_id;
      showNotice('info',`${label} submitted`,'The result is pending. The local worker retains this job independently of this page.',result.job_id);
      pendingRequests.delete(payload.request_id);
      await refreshState();
      if (options.showJob) setView('activity');
      schedulePoll(500);
      return result.job_id;
    } catch (error) {
      if (locked) return null;
      if (!error.status || error.status >= 500 || (error.status >= 200 && error.status < 300)) {
        uncertain = {payload,operation,fields,label,onComplete:options.onComplete,showJob:options.showJob};
        connected = false;
        renderNotice();
        refreshState(true);
      } else showNotice('error',`${label} refused`,error.message);
      return null;
    } finally { pendingRequests.delete(payload.request_id); render(); }
  }

  async function importFile(file) {
    if (!file || uploading) return;
    if (!file.name.toLowerCase().endsWith('.schism')) { showNotice('error','Choose a .schism application package','Use the signed package produced by the SCHISM package builder.'); return; }
    if (!file.size) { showNotice('error','The selected file is empty'); return; }
    if (!connected) { showNotice('error','Connect to the local service before importing'); return; }
    uploading = true; setView('packages'); renderChrome();
    showNotice('info','Inspecting the package',`${file.name} · ${bytes(file.size)}. This operation does not execute application code.`);
    try {
      const release = await write('/api/import',file,'application/octet-stream');
      if (!release || typeof release.release_id !== 'string' || !release.application?.id || !release.publisher?.key_id) throw new ApiError('The import response is missing the verified release metadata.');
      inspectedReleases.set(release.release_id,release);
      selectedRelease = release.release_id; packageFilter = null;
      await refreshState(); renderPackages();
      showNotice('success','Package verified and imported',`${release.application.name || release.application.id} ${release.application.version}. Inspect the publisher and execution contract before deployment.`);
    } catch (error) { if (!locked) showNotice('error','Package import did not complete',error.message); }
    finally { uploading = false; $('package-file').value = ''; renderChrome(); }
  }

  function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url),30000);
  }

  async function exportEvidence() {
    if (!connected || exporting) return;
    exporting = true; renderChrome();
    try {
      const response = await fetch('/api/export',{credentials:'same-origin',cache:'no-store',headers:{'X-SCHISM-Token':token}});
      if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try { const body = await response.json(); detail = text(body.error || body.message || body.detail || detail); } catch (_) { /* Retain the HTTP result. */ }
        const failure = new ApiError(detail,response.status);
        if (isSessionRefusal(failure)) lockConsole();
        throw failure;
      }
      const blob = await response.blob();
      if (!blob.size) throw new ApiError('The evidence archive is empty.');
      const signature = new Uint8Array(await blob.slice(0,4).arrayBuffer());
      if (signature.length < 4 || signature[0] !== 0x50 || signature[1] !== 0x4b) throw new ApiError('The service response is not an evidence ZIP archive.');
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = (match ? match[1].split(/[\\/]/).pop() : `schism-evidence-${new Date().toISOString().slice(0,10)}.zip`).replace(/[^a-zA-Z0-9._-]/g,'_');
      saveBlob(blob,filename);
      showNotice('success','Signed evidence archive downloaded','The export contains public identity, release records, events and jobs. Private keys, secret configuration, logs and application data remain outside this archive.');
    } catch (error) { if (!locked) showNotice('error','Evidence export failed',error.message); }
    finally { exporting = false; renderChrome(); }
  }

  async function copy(value) {
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(value);
      else { const field = document.createElement('textarea'); field.value = value; field.className = 'sr-only'; document.body.appendChild(field); field.select(); const ok = document.execCommand('copy'); field.remove(); if (!ok) throw new Error('Clipboard access is unavailable.'); }
      announce('Identifier copied.');
      showNotice('info','Identifier copied');
    } catch (error) { showNotice('error','Copy unavailable','Select and copy the displayed identifier directly.'); }
  }

  function addEnvironmentRow(target = 'environment-rows', suggestedName = '') {
    const container = $(target);
    if (!container) return;
    const row = document.createElement('div'); row.className = 'environment-row';
    row.innerHTML = '<input class="env-name" type="text" placeholder="VARIABLE_NAME" aria-label="Environment variable name" autocomplete="off" spellcheck="false"><input class="env-value" type="password" placeholder="Private value" aria-label="Environment variable value" autocomplete="new-password" spellcheck="false"><button type="button" class="button ghost small env-remove" data-action="remove-environment" aria-label="Remove environment variable">×</button>';
    row.querySelector('.env-name').value = suggestedName;
    container.appendChild(row);
  }

  async function saveEnvironment(event) {
    event.preventDefault();
    const appId = event.target.dataset.appId || appById(selectedApp)?.id; if (!appId) return;
    const rowsId = event.target.id === 'package-environment-form' ? 'package-environment-rows' : 'environment-rows';
    const environment = {};
    try {
      for (const row of $(rowsId).children) {
        const name = row.querySelector('.env-name').value.trim();
        const value = row.querySelector('.env-value').value;
        if (!name && !value) continue;
        if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) throw new Error('Use a valid environment variable name for each value.');
        if (Object.prototype.hasOwnProperty.call(environment,name)) throw new Error(`Duplicate variable: ${name}`);
        environment[name] = value;
      }
      if (!Object.keys(environment).length) throw new Error('Add at least one named variable before saving.');
      const fields = {app_id:appId,environment};
      const result = await submit('configure',fields,'Save runtime configuration');
      if (result || uncertain) { $(rowsId).replaceChildren(); addEnvironmentRow(rowsId); }
    } catch (error) { showNotice('error','Configuration was not submitted',error.message); }
  }

  async function handleAction(button) {
    if (button.disabled) return;
    const action = button.dataset.action;
    const app = appById(selectedApp);
    const release = releaseById(selectedRelease);
    if (action === 'import') { $('package-file').click(); return; }
    if (action === 'refresh') { await refreshState(false); return; }
    if (action === 'copy') { await copy(button.dataset.value || ''); return; }
    if (action === 'dismiss-notice') { notice = null; renderNotice(); return; }
    if (action === 'show-activity') { setView('activity'); return; }
    if (action === 'retry-request' && uncertain) { const u = uncertain; await submit(u.operation,u.fields,u.label,{payload:u.payload,onComplete:u.onComplete,showJob:u.showJob}); return; }
    if (action === 'select-app') { selectedApp = button.dataset.id; renderApplications(); return; }
    if (action === 'select-release') { selectedRelease = button.dataset.id; renderPackages(); return; }
    if (action === 'select-job') { selectedJob = button.dataset.id; setView('activity'); await refreshJob(); return; }
    if (action === 'clear-package-filter') { packageFilter = null; renderPackages(); return; }
    if (action === 'choose-update' && app) { packageFilter = app.id; selectedRelease = releases().find((item) => item.application?.id === app.id && item.release_id !== app.release_id)?.release_id || app.release_id; setView('packages'); return; }
    if (action === 'refresh-log') { await refreshJob(); return; }
    if (action === 'inspect-peer') { await inspectPeer(button.dataset.name); return; }
    if (action === 'cancel-job' && selectedJob) { await submit('cancel',{job_id:selectedJob},'Cancel job'); return; }
    if (action === 'add-environment') { addEnvironmentRow(button.dataset.target || 'environment-rows'); return; }
    if (action === 'remove-environment') { const container = button.closest('.environment-rows'); button.closest('.environment-row').remove(); if (!container.children.length) addEnvironmentRow(container.id); return; }
    if (action === 'revoke-publisher') { await submit('revoke',{key_id:button.dataset.key},'Revoke publisher trust'); return; }
    if (action === 'trust-publisher' && release) {
      const all = $('trust-scope').value === 'all';
      const apps = all ? ['*'] : [...new Set([...activePublisherScopes(release),release.application.id])].sort();
      await submit('trust',{publisher:release.publisher,apps,label:release.publisher.name || 'Publisher'},'Grant publisher trust'); return;
    }
    if (action === 'deploy-package' && release) {
      const existing = appById(release.application.id);
      await submit('deploy',{release_id:release.release_id,expected_generation:existing?.generation ?? 0},existing ? 'Update application' : 'Deploy application',{onComplete:(job) => { if (status(job.status) === 'succeeded') { selectedApp = release.application.id; } }}); return;
    }
    if (action === 'download-manifest' && release) { saveBlob(new Blob([pretty(release)+'\n'],{type:'application/json'}),`${release.application.id}-${release.application.version}-metadata.json`.replace(/[^a-zA-Z0-9._-]/g,'_')); return; }
    if (app && ['start-app','stop-app','run-app','rollback-app','recover-app'].includes(action)) {
      const operation = {'start-app':'start','stop-app':'stop','run-app':'run','rollback-app':'rollback','recover-app':'recover'}[action];
      const label = {'start-app':'Start service','stop-app':'Stop service','run-app':'Run task','rollback-app':'Restore previous code','recover-app':'Recover application status'}[action];
      const fields = operation === 'recover' ? {app_id:app.id} : {app_id:app.id,expected_generation:app.generation};
      await submit(operation,fields,label,{showJob:operation === 'run'});
    }
  }

  function schedulePoll(delay) {
    clearTimeout(pollTimer);
    if (locked || !token) return;
    const wait = delay ?? (document.hidden ? 15000 : state.jobs.some(activeJob) || watchedJobs.size ? 1500 : state.applications.some(running) ? 4000 : 7000);
    pollTimer = setTimeout(async () => { await refreshState(true); schedulePoll(); },wait);
  }

  document.addEventListener('click',(event) => {
    const view = event.target.closest('button[data-view]');
    if (view) { setView(view.dataset.view); return; }
    const action = event.target.closest('button[data-action]');
    if (action) handleAction(action).catch((error) => showNotice('error','The operation could not be completed',error.message));
  });
  document.addEventListener('submit',(event) => { if (['environment-form','package-environment-form'].includes(event.target.id)) saveEnvironment(event); });
  $('app-search').addEventListener('input',renderApplications);
  $('job-filter').addEventListener('change',renderActivity);
  document.addEventListener('change',(event) => { if (event.target.id === 'trust-scope') renderPackageDetail(); });
  $('package-file').addEventListener('change',(event) => importFile(event.target.files?.[0]));
  $('export-evidence').addEventListener('click',exportEvidence);
  const drop = $('drop-zone');
  drop.addEventListener('dragover',(event) => { event.preventDefault(); if (connected && !uploading) { event.dataTransfer.dropEffect = 'copy'; drop.classList.add('dragging'); } });
  drop.addEventListener('dragleave',() => drop.classList.remove('dragging'));
  drop.addEventListener('drop',(event) => { event.preventDefault(); drop.classList.remove('dragging'); const files = event.dataTransfer.files; if (files.length !== 1) showNotice('error','Import one application package at a time'); else importFile(files[0]); });
  document.addEventListener('visibilitychange',() => { if (!document.hidden) { refreshState(true); schedulePoll(500); } else schedulePoll(); });
  window.addEventListener('online',() => { refreshState(true); schedulePoll(500); });
  window.addEventListener('pagehide',() => clearTimeout(pollTimer));
  window.addEventListener('hashchange',() => {
    if (new URLSearchParams(window.location.hash.slice(1)).has('token')) {
      token = readBootstrapToken(); locked = !token;
      if (token) {
        connected = false; loaded = false; notice = null; lastObserved = null;
        state = {...initialState}; inspectedReleases.clear(); jobDetails.clear(); watchedJobs.clear(); pendingRequests.clear();
        selectedApp = selectedRelease = selectedJob = detailApp = detailRelease = null;
        boot();
      }
      else lockConsole();
    }
  });

  async function boot() {
    render();
    if (locked || !token) { lockConsole(); return; }
    await Promise.allSettled([getToken(),refreshState(false)]);
    schedulePoll();
  }
  boot();
})();
