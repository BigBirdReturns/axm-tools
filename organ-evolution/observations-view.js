'use strict';

const ORGAN_OBSERVATIONS = window.AXM_ORGAN_OBSERVATIONS || {
  format: 'axm-organ-observations/1',
  generatedAt: null,
  sourceDigest: null,
  organs: [],
  unavailable: [],
};

const BAD_WORKFLOW_CONCLUSIONS = ['failure', 'timed_out', 'cancelled', 'action_required', 'startup_failure'];

function organObservation(id = selectedOrganId) {
  return (ORGAN_OBSERVATIONS.organs || []).find(row => row.organId === id) || null;
}

function observationSeverityTone(severity) {
  if (severity === 'critical') return 'high';
  if (severity === 'context') return 'context';
  return severity === 'attention' ? '' : 'good';
}

function workflowTone(workflow) {
  if (BAD_WORKFLOW_CONCLUSIONS.includes(workflow.conclusion)) return 'red';
  if (workflow.status && workflow.status !== 'completed') return 'gold';
  return workflow.conclusion === 'success' ? 'green' : 'gold';
}

function workflowRoleText(workflow) {
  const role = cap(workflow.role || 'unknown');
  const lifecycle = cap(workflow.lifecycle || 'current');
  const obligation = workflow.required ? 'required' : 'advisory';
  const source = workflow.roleSource === 'declared' ? 'declared' : 'unclassified';
  return `${role} · ${lifecycle} · ${obligation} · ${source}`;
}

function observationSummary() {
  const organs = ORGAN_OBSERVATIONS.organs || [];
  const repositories = organs.flatMap(row => row.repositories || []);
  const workflows = repositories.flatMap(repo => repo.workflows || []);
  const findings = organs.flatMap(row => row.findings || []);
  const currentRed = workflows.filter(workflow =>
    BAD_WORKFLOW_CONCLUSIONS.includes(workflow.conclusion) &&
    (workflow.lifecycle || 'current') === 'current' &&
    (workflow.required || workflow.roleSource === 'unclassified')
  ).length;
  return {
    organs: organs.filter(row => (row.repositories || []).length || (row.localObservations || []).length).length,
    repositories: repositories.length,
    currentRed,
    roleGaps: workflows.filter(workflow => workflow.roleSource !== 'declared').length,
    critical: findings.filter(row => row.severity === 'critical').length,
    attention: findings.filter(row => row.severity === 'attention').length,
    context: findings.filter(row => row.severity === 'context').length,
  };
}

function shortSha(value) {
  return value ? String(value).slice(0, 9) : 'unavailable';
}

function observationDate(value) {
  if (!value) return 'not yet observed';
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
  } catch {
    return value;
  }
}

function repositoryObservationHtml(repository) {
  const workflows = repository.workflows || [];
  const pulls = repository.openPullRequests || [];
  const signals = repository.signals || {};
  return `<article class="repo-observation">
    <div class="repo-head">
      <div><a href="${esc(repository.url || '#')}" target="_blank" rel="noreferrer"><b>${esc(repository.fullName)}</b></a><span>${esc(repository.observedRef || repository.defaultBranch || '')}</span></div>
      <code>${esc(shortSha(repository.headSha))}</code>
    </div>
    <dl class="repo-facts">
      <div><dt>Head</dt><dd>${esc(observationDate(repository.headAt))}${Number.isInteger(repository.headAgeDays) ? ` · ${repository.headAgeDays}d` : ''}</dd></div>
      <div><dt>Release</dt><dd>${esc(repository.latestTag || 'no observed tag')}</dd></div>
      <div><dt>License</dt><dd>${esc(repository.license || 'not exposed')}</dd></div>
      <div><dt>Open PRs</dt><dd>${pulls.length}</dd></div>
    </dl>
    <div class="tagrow repo-signals">
      <span class="tag ${signals.readme ? 'green' : 'red'}">README ${signals.readme ? 'present' : 'absent'}</span>
      <span class="tag ${signals.license || repository.license ? 'green' : 'gold'}">license ${signals.license || repository.license ? 'present' : 'open'}</span>
      <span class="tag ${(signals.successionFiles || []).length ? 'green' : 'gold'}">succession ${(signals.successionFiles || []).length ? 'present' : 'open'}</span>
    </div>
    <div class="workflow-list">${workflows.length ? workflows.map(workflow => `<a class="workflow-row" href="${esc(workflow.url || repository.url || '#')}" target="_blank" rel="noreferrer" title="${esc(workflow.roleBasis || '')}"><span class="pulse ${workflowTone(workflow) === 'red' ? 'fail' : workflowTone(workflow) === 'gold' ? 'warn' : ''}"></span><span><b>${esc(workflow.name)}</b><small>${esc(workflowRoleText(workflow))}</small><small>${esc(workflow.status || '')} · ${esc(workflow.conclusion || 'pending')}</small></span><code>${esc(shortSha(workflow.headSha))}</code></a>`).join('') : '<div class="empty">No workflow receipt observed.</div>'}</div>
  </article>`;
}

function renderObservationPanel() {
  const row = organObservation();
  const generated = ORGAN_OBSERVATIONS.generatedAt;
  const digestValue = ORGAN_OBSERVATIONS.sourceDigest;
  if (!row) {
    return `<div class="section-title"><div><h2>Observed implementation state</h2><p>Machine observations remain separate from human-entered anatomy, scores, gates, motives, mandates, and decisions.</p></div></div>
      <section class="card observation-panel"><div class="empty">No observation pack covers ${esc(organ()?.name || selectedOrganId)} yet. The organ remains evaluable from its declared anatomy, but its current implementation state is unobserved.</div></section>`;
  }
  const findings = row.findings || [];
  const local = row.localObservations || [];
  const shortDigest = digestValue ? shortSha(digestValue.replace(/^organobs1_/, '')) : 'unsealed';
  return `<div class="section-title"><div><h2>Observed implementation state</h2><p>Collected facts may create attention findings. Workflow role and lifecycle are declared separately from workflow result. Neither record changes the organ health envelope, candidate dimensions, hard gates, motive claims, or decision. This is not a health or readiness verdict.</p></div><div class="right"><span class="tag cyan">organobs1_${esc(shortDigest)}</span></div></div>
    <section class="card observation-panel">
      <div class="observation-custody"><div><span>Collected</span><b>${esc(observationDate(generated))}</b></div><div><span>Repositories</span><b>${(row.repositories || []).length}</b></div><div><span>Local observations</span><b>${local.length}</b></div><div><span>Attention findings</span><b>${findings.filter(f => f.severity !== 'context').length}</b></div></div>
      <div class="observation-digest"><span>Complete observation identity</span><code>${esc(digestValue || 'unsealed observation')}</code></div>
      <div class="repo-grid">${(row.repositories || []).map(repositoryObservationHtml).join('') || '<div class="empty">Every configured repository was unavailable during collection.</div>'}</div>
      <div class="grid two observation-lower">
        <div><h3>Attention findings</h3><div class="flag-list">${findings.length ? findings.map(finding => `<div class="flag ${observationSeverityTone(finding.severity)}"><b>${esc(cap(finding.code))}</b><p>${esc(finding.summary)}</p></div>`).join('') : '<div class="flag good"><b>No observation finding</b><p>The collector found no configured structural attention condition. This is not a health or readiness verdict.</p></div>'}</div></div>
        <div><h3>Attributed local observations</h3><div class="flag-list">${local.length ? local.map(item => `<div class="flag"><b>${esc(item.kind)} · ${esc(item.state)}</b><p>${esc(item.claim)}</p><p><i>${esc(item.source)} · ${esc(item.limits)}</i></p></div>`).join('') : '<div class="empty">No operator or device observation is present for this organ.</div>'}</div></div>
      </div>
    </section>`;
}

const renderTopWithoutObservations = renderTop;
renderTop = function renderTopWithObservations() {
  renderTopWithoutObservations();
  const summary = observationSummary();
  document.getElementById('topStats').insertAdjacentHTML('beforeend', [
    ['observed organs', summary.organs],
    ['observed repos', summary.repositories],
    ['current red gates', summary.currentRed],
    ['workflow role gaps', summary.roleGaps],
    ['critical findings', summary.critical],
  ].map(([label, value]) => `<div class="statpill"><strong>${value}</strong> ${label}</div>`).join(''));
};

const renderAnatomyWithoutObservations = renderAnatomy;
renderAnatomy = function renderAnatomyWithObservations() {
  return renderAnatomyWithoutObservations() + renderObservationPanel();
};
