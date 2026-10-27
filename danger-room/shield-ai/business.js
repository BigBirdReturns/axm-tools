/* Deterministic synthetic commercial governance. No external source systems or predictive model. */
(function (root) {
  'use strict';
  const provenance = 'Synthetic demonstration data; no Shield AI customer, CRM, personnel, pricing or procurement information.';
  const caveats = ['Stage weights are illustrative policy, not calibrated probabilities.', 'Bookings, open pipeline and recognized revenue are distinct; recognized revenue is not supplied.', 'A technically passing demonstration does not establish budget, buyer authority, procurement or customer acceptance.', 'External evidence marked verified is an operator assertion, not independent verification.'];
  const weights = Object.freeze({ Lead: 0.05, Discovery: 0.15, Qualified: 0.3, 'Technical validation': 0.5, 'Commercial review': 0.7, 'Closed won': 1, 'Closed lost': 0 });
  function normalizeStage(stage) {
    const aliases = { demo: 'Technical validation', negotiation: 'Commercial review', lead: 'Lead', discovery: 'Discovery', qualified: 'Qualified', 'technical validation': 'Technical validation', 'commercial review': 'Commercial review', 'closed won': 'Closed won', 'closed lost': 'Closed lost' };
    return aliases[String(stage || '').trim().toLowerCase()] || 'Lead';
  }
  function amount(opp) { return Number.isFinite(opp.amount) && opp.amount >= 0 ? opp.amount : 0; }
  function activeOpportunities(state) { return (state.opportunities || []).filter(o => !o.duplicateOf && normalizeStage(o.stage) !== 'Closed lost'); }
  function technicalStatus(opp, state) {
    const requiredScope = state.quality && state.quality.requiredScope || 'timing';
    if (opp.technical === 'external') {
      const passed = opp.externalEvidence === 'verified';
      return { passed, status: passed ? 'verified-assertion' : 'pending', label: passed ? 'External evidence: operator-asserted verified' : 'External evidence pending', blockers: passed ? [] : ['External evidence has not been marked verified by the operator'], requiredScope, evidenceScope: 'external operator assertion', provenance: 'Operator assertion; the workbench has not independently inspected external evidence.' };
    }
    const accepted = state.quality && state.quality.accepted;
    const blockers = [];
    if (!accepted) blockers.push('No accepted browser evaluation');
    else {
      if (accepted.scope !== requiredScope) blockers.push('Accepted scope does not match current required scope');
      if (!accepted.allPassed) blockers.push('Required evaluation contains failed or incomplete cases');
      if (!accepted.verified) blockers.push('Accepted evaluation integrity is not verified');
      if (!Array.isArray(accepted.runIds) || !accepted.runIds.length) blockers.push('Accepted evaluation has no run references');
    }
    const passed = blockers.length === 0;
    return { passed, status: passed ? 'passed' : 'blocked', label: passed ? 'Accepted browser evidence for current scope' : 'Browser acceptance blocked', blockers, requiredScope, evidenceScope: accepted ? accepted.scope : null, provenance: 'Browser reference experiment only; no real-product or field qualification.' };
  }
  function futureClose(opp, state) {
    const close = /^\d{4}-\d{2}-\d{2}$/.test(opp.closeDate || '') ? Date.parse(opp.closeDate + 'T00:00:00Z') : NaN;
    const asOf = Date.parse(String(state.asOf || '') + 'T00:00:00Z');
    return Number.isFinite(close) && Number.isFinite(asOf) && new Date(close).toISOString().slice(0, 10) === opp.closeDate && close > asOf;
  }
  function forecastOne(opp, state) {
    const stage = normalizeStage(opp.stage), technical = technicalStatus(opp, state), blockers = [];
    if (!opp.owner) blockers.push('No accountable owner');
    if (!opp.buyer) blockers.push('Buyer authority unconfirmed');
    if (!opp.budget) blockers.push('Budget unconfirmed');
    if (!opp.procurement) blockers.push('Procurement evidence missing');
    if (!opp.customerAcceptance) blockers.push('Customer acceptance missing');
    if (!futureClose(opp, state)) blockers.push('Close date is missing, invalid, today or stale');
    if (!technical.passed) blockers.push(...technical.blockers);
    const excluded = !!opp.duplicateOf || stage === 'Closed lost';
    if (opp.duplicateOf) blockers.push('Duplicate record of ' + opp.duplicateOf);
    if (stage === 'Closed lost') blockers.push('Closed lost');
    const open = !excluded && stage !== 'Closed won';
    let category = 'pipeline';
    if (excluded) category = 'excluded';
    else if (stage === 'Closed won') category = 'closed-won';
    else if (stage === 'Commercial review' && blockers.length === 0) category = 'commit';
    else if (['Qualified', 'Technical validation', 'Commercial review'].includes(stage) && opp.owner && opp.buyer && opp.budget && futureClose(opp, state)) category = 'best-case';
    if (open && stage !== 'Commercial review') blockers.push('Stage is not Commercial review');
    const value = amount(opp), probability = excluded ? 0 : weights[stage];
    return { id: opp.id, included: !excluded, category, stage, amount: value, weightedAmount: open ? value * probability : 0, probability, blockers, technical, open, bookings: !excluded && stage === 'Closed won' ? value : 0 };
  }
  function metrics(state) {
    const forecast = (state.opportunities || []).map(o => forecastOne(o, state));
    const sum = fn => forecast.reduce((n, f) => n + fn(f), 0);
    const m = { openPipeline: sum(f => f.open ? f.amount : 0), weightedPipeline: sum(f => f.weightedAmount), commit: sum(f => f.category === 'commit' ? f.amount : 0), bestCase: sum(f => f.category === 'best-case' ? f.amount : 0), pipeline: sum(f => f.category === 'pipeline' ? f.amount : 0), closedWonBookings: sum(f => f.bookings), recognizedRevenue: null, openCount: forecast.filter(f => f.open).length, closedWonCount: forecast.filter(f => f.category === 'closed-won').length, activeCount: forecast.filter(f => f.included).length, excludedCount: forecast.filter(f => !f.included).length, forecast, provenance, caveats: [...caveats] };
    m.bookings = m.closedWonBookings;
    return m;
  }
  function reconcile(state) {
    const changes = [], seen = new Map();
    let normalizedCount = 0, duplicateCount = 0;
    for (const opp of state.opportunities || []) {
      const normalized = normalizeStage(opp.stage);
      if (normalized !== opp.stage) { changes.push({ id: opp.id, field: 'stage', from: opp.stage, to: normalized, reason: 'Legacy-to-unified stage mapping' }); opp.stage = normalized; normalizedCount++; }
      // Keep source records and IDs; first explicitly canonical record wins a stable import-order tie.
      if (opp.duplicateOf) { duplicateCount++; continue; }
      if (opp.canonicalKey) {
        if (seen.has(opp.canonicalKey)) { const canonicalId = seen.get(opp.canonicalKey); changes.push({ id: opp.id, field: 'duplicateOf', from: opp.duplicateOf || null, to: canonicalId, reason: 'Same explicit canonical opportunity key; source record preserved' }); opp.duplicateOf = canonicalId; duplicateCount++; }
        else seen.set(opp.canonicalKey, opp.id);
      }
    }
    if (!state.integration) state.integration = {};
    state.integration.reconciled = true;
    return { changes, duplicateCount, normalizedCount, reconciled: true, provenance };
  }
  function coverage(state) {
    const open = activeOpportunities(state).filter(o => normalizeStage(o.stage) !== 'Closed won');
    const people = (state.people || []).map(p => {
      const assigned = open.filter(o => o.owner === p.id || o.owner === p.name).map(o => o.id);
      return { ...p, capacity: Number.isFinite(p.capacity) ? p.capacity : 0, load: assigned.length, overloaded: assigned.length > (Number.isFinite(p.capacity) ? p.capacity : 0), assigned };
    });
    const known = value => !!value && people.some(p => p.id === value || p.name === value);
    const uncovered = open.filter(o => !known(o.owner));
    const backupGaps = open.filter(o => !known(o.backup) || o.backup === o.owner);
    return { total: open.length, covered: open.length - uncovered.length, coveragePct: open.length ? 100 * (open.length - uncovered.length) / open.length : 0, uncovered, backupGaps, people, provenance };
  }
  function rankAccounts(state) {
    return activeOpportunities(state).filter(o => normalizeStage(o.stage) !== 'Closed won').map(o => {
      const segment = String(o.segment || '').toLowerCase();
      const segmentFit = /prime|government|defen[cs]e|training|integrator|lsi/.test(segment) ? 30 : /enterprise|industrial/.test(segment) ? 25 : 15;
      const components = { segmentFit, buyerEvidence: o.buyer ? 15 : 0, budgetEvidence: o.budget ? 15 : 0, procurementEvidence: o.procurement ? 10 : 0, coverage: o.owner ? 10 : 0, technicalEvidence: technicalStatus(o, state).passed ? 10 : 0, futureClose: futureClose(o, state) ? 10 : 0 };
      return { id: o.id, name: o.name, score: Object.values(components).reduce((a, b) => a + b, 0), components, opportunity: o, rationale: 'Disclosed illustrative ICP policy: segment fit plus recorded readiness; no external market-size or account-intelligence claims.', provenance };
    }).sort((a, b) => b.score - a.score || String(a.id).localeCompare(String(b.id)));
  }
  function commercialBrief(state, oppId) {
    const opp = (state.opportunities || []).find(o => o.id === oppId);
    if (!opp) return { error: 'Opportunity not found', id: oppId, provenance, caveats: [...caveats] };
    const forecast = forecastOne(opp, state);
    return { asOf: state.asOf, id: opp.id, name: opp.name, region: opp.region, segment: opp.segment, product: opp.product, partner: opp.partner, amount: amount(opp), stage: normalizeStage(opp.stage), owner: opp.owner, backup: opp.backup, closeDate: opp.closeDate, qualification: { buyer: !!opp.buyer, budget: !!opp.budget, procurement: !!opp.procurement, customerAcceptance: !!opp.customerAcceptance }, technical: forecast.technical, forecast, blockers: [...forecast.blockers], actions: (state.actions || []).filter(a => a.oppId === opp.id || a.opportunityId === opp.id), provenance, caveats: [...caveats, 'Product bundles and delivery interfaces are illustrative proposals unless separately evidenced.'] };
  }
  function operatingReview(state) {
    return { asOf: state.asOf, title: 'Synthetic international simulation operating review', integration: { ...(state.integration || {}) }, metrics: metrics(state), coverage: coverage(state), rankedAccounts: rankAccounts(state), pursuits: activeOpportunities(state).map(o => commercialBrief(state, o.id)), quality: { requiredScope: state.quality && state.quality.requiredScope, accepted: state.quality && state.quality.accepted || null, runCount: state.quality && state.quality.runs ? state.quality.runs.length : 0, suiteCount: state.quality && state.quality.suites ? state.quality.suites.length : 0 }, actions: state.actions || [], events: state.events || [], provenance, caveats: [...caveats, 'This snapshot cannot establish forecast accuracy, growth, win-rate change or deal-velocity improvement without dated cohorts.'] };
  }
  const api = Object.freeze({ normalizeStage, activeOpportunities, technicalStatus, forecastOne, metrics, reconcile, coverage, rankAccounts, commercialBrief, operatingReview, weights, provenance });
  root.SDModel = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
