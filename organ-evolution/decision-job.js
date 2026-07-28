'use strict';

(() => {
  const MODEL_FORMAT = 'axm-organ-evolution/1';
  const DECISION_FORMAT = 'axm-organ-decision/1';
  const JOB_FORMAT = 'axm-organ-evolution-job/1';
  const EXECUTION_FORMAT = 'axm-organ-execution/1';
  const MAX_TEXT = 32000;
  const MAX_REFERENCES = 256;
  const DIMENSIONS = new Set([
    'function','authority','reversibility','dependency','adaptability','observability',
    'succession','efficiency','userValue','captureResistance','containment','evidence',
  ]);
  const GATES = new Set(['function','authority','evidence','migration','reversibility']);
  const TERMINAL_OUTCOMES = new Set(['done','abandoned','superseded','refused','failed']);
  const EXECUTION_STATES = new Set(['in_progress','verified','failed']);
  const EVIDENCE_TIERS = new Set(['confirmed','measured','reported','derived','judgment','open']);
  const INDEPENDENCE = new Set(['independent','mixed','self','unknown']);
  const DIGEST_RE = /^[a-z0-9]+_[0-9a-f]{64}$/;
  const AUTHORITY = {
    decision: 'external human-owned decision assertion; this compiler does not authenticate the mandate or decider',
    circulation: 'Bloodstream may record, route, block, invalidate, recover, and report the job only',
    execution: 'the owning implementation organ and cited verifiers',
    acceptance: 'the named decision authority under the cited mandate',
    compiler: 'canonical serialization and structural refusal only',
    forbidden: [
      'automatic admission','priority inference','supplier selection','agent scheduling',
      'branch merge','action execution','outcome acceptance','campaign mutation',
    ],
  };

  class DecisionJobError extends Error {}

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function canonicalStringify(value) {
    if (value === null) return 'null';
    if (Array.isArray(value)) return `[${value.map(canonicalStringify).join(',')}]`;
    if (typeof value === 'object') {
      return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalStringify(value[key])}`).join(',')}}`;
    }
    if (typeof value === 'number' && !Number.isInteger(value)) {
      throw new DecisionJobError('floating-point semantic values are not permitted');
    }
    if (!['string','number','boolean'].includes(typeof value)) {
      throw new DecisionJobError(`unsupported JSON semantic value: ${typeof value}`);
    }
    return JSON.stringify(value);
  }

  async function digest(prefix, value) {
    const bytes = new TextEncoder().encode(canonicalStringify(value));
    const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
    return `${prefix}_${[...hash].map(byte => byte.toString(16).padStart(2, '0')).join('')}`;
  }

  function withoutKeys(value, ...keys) {
    const removed = new Set(keys);
    return Object.fromEntries(Object.entries(value).filter(([key]) => !removed.has(key)));
  }

  function exactKeys(value, required, label) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new DecisionJobError(`${label} must be an object`);
    }
    const got = Object.keys(value).sort();
    const wanted = [...required].sort();
    if (got.length !== wanted.length || got.some((key, index) => key !== wanted[index])) {
      const missing = wanted.filter(key => !got.includes(key));
      const extra = got.filter(key => !wanted.includes(key));
      throw new DecisionJobError(`${label} keys differ; missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`);
    }
    return value;
  }

  function validateDepth(value, depth = 0) {
    if (depth > 128) throw new DecisionJobError('JSON nesting exceeds 128');
    if (Array.isArray(value)) {
      if (value.length > 100000) throw new DecisionJobError('JSON array is oversized');
      value.forEach(child => validateDepth(child, depth + 1));
      return;
    }
    if (value && typeof value === 'object') {
      for (const [key, child] of Object.entries(value)) {
        if (key.length > 256) throw new DecisionJobError('JSON object key is invalid or oversized');
        validateDepth(child, depth + 1);
      }
      return;
    }
    if (typeof value === 'string' && value.length > MAX_TEXT) {
      throw new DecisionJobError('JSON text value is oversized');
    }
    if (typeof value === 'number' && !Number.isInteger(value)) {
      throw new DecisionJobError('floating-point semantic values are not permitted');
    }
    if (value !== null && !['string','number','boolean'].includes(typeof value)) {
      throw new DecisionJobError(`unsupported JSON semantic value: ${typeof value}`);
    }
  }

  function indexed(rows, label) {
    if (!Array.isArray(rows)) throw new DecisionJobError(`${label} must be an array`);
    const result = new Map();
    for (const row of rows) {
      if (!row || typeof row !== 'object' || Array.isArray(row) || typeof row.id !== 'string') {
        throw new DecisionJobError(`${label} records require stable string IDs`);
      }
      if (result.has(row.id)) throw new DecisionJobError(`duplicate ${label} ID: ${row.id}`);
      result.set(row.id, row);
    }
    return result;
  }

  function requiredText(value, label, maximum = MAX_TEXT) {
    if (typeof value !== 'string' || !value.trim()) {
      throw new DecisionJobError(`${label} must be a non-empty string`);
    }
    const clean = value.trim();
    if (clean.length > maximum) throw new DecisionJobError(`${label} exceeds ${maximum} characters`);
    return clean;
  }

  function optionalText(value, label, maximum = MAX_TEXT) {
    if (value === undefined || value === null) return '';
    if (typeof value !== 'string' || value.length > maximum) {
      throw new DecisionJobError(`${label} must be bounded text`);
    }
    return value.trim();
  }

  function isoTime(value, label) {
    const text = requiredText(value, label, 128);
    if (!/(Z|[+-]\d\d:\d\d)$/.test(text) || Number.isNaN(Date.parse(text))) {
      throw new DecisionJobError(`${label} must be ISO-8601 with a timezone`);
    }
    return text;
  }

  function stringList(value, label, allowEmpty = true) {
    if (!Array.isArray(value)) throw new DecisionJobError(`${label} must be an array`);
    if (value.length > MAX_REFERENCES) throw new DecisionJobError(`${label} contains too many entries`);
    const result = value.map(item => requiredText(item, label, 4096));
    if (!allowEmpty && !result.length) throw new DecisionJobError(`${label} must not be empty`);
    if (new Set(result).size !== result.length) throw new DecisionJobError(`${label} contains duplicate entries`);
    return result;
  }

  function validateDigest(value, prefix, label) {
    const text = requiredText(value, label, 128);
    if (!text.startsWith(`${prefix}_`) || !DIGEST_RE.test(text)) {
      throw new DecisionJobError(`${label} is not a supported ${prefix} identity`);
    }
    return text;
  }

  function normalizeEvidence(value) {
    if (!Array.isArray(value) || !value.length) {
      throw new DecisionJobError('decision.evidence must be a non-empty array');
    }
    if (value.length > MAX_REFERENCES) throw new DecisionJobError('decision.evidence contains too many records');
    const required = new Set(['id','title','tier','independence','source','claim','limits']);
    const seen = new Set();
    const rows = value.map(raw => {
      const row = exactKeys(raw, required, 'decision evidence record');
      const id = requiredText(row.id, 'evidence.id', 256);
      if (seen.has(id)) throw new DecisionJobError(`duplicate decision evidence ID: ${id}`);
      seen.add(id);
      const tier = requiredText(row.tier, `${id}.tier`, 64);
      const independence = requiredText(row.independence, `${id}.independence`, 64);
      if (!EVIDENCE_TIERS.has(tier)) throw new DecisionJobError(`${id} has unsupported tier ${tier}`);
      if (!INDEPENDENCE.has(independence)) throw new DecisionJobError(`${id} has unsupported independence ${independence}`);
      return {
        id,
        title: requiredText(row.title, `${id}.title`),
        tier,
        independence,
        source: requiredText(row.source, `${id}.source`),
        claim: requiredText(row.claim, `${id}.claim`),
        limits: requiredText(row.limits, `${id}.limits`),
      };
    }).sort((a, b) => a.id.localeCompare(b.id));
    const independent = rows.some(row => row.independence === 'independent' && ['confirmed','measured','reported'].includes(row.tier));
    if (!independent) {
      throw new DecisionJobError('accepted circulation requires at least one independent confirmed, measured, or reported evidence record');
    }
    return rows;
  }

  function normalizeMigration(value) {
    const row = exactKeys(value, new Set(['preserve','alter','retire','introduce']), 'decision.migration');
    return Object.fromEntries(['preserve','alter','retire','introduce'].map(key => [key, stringList(row[key], `decision.migration.${key}`)]));
  }

  function normalizeDimensions(value) {
    const row = exactKeys(value, DIMENSIONS, 'decision.dimensions');
    return Object.fromEntries([...DIMENSIONS].sort().map(key => {
      const score = row[key];
      if (!Number.isInteger(score) || score < 0 || score > 5) {
        throw new DecisionJobError(`decision dimension ${key} must be integer 0..5`);
      }
      return [key, score];
    }));
  }

  function normalizeGates(value) {
    const row = exactKeys(value, GATES, 'decision.gates');
    if ([...GATES].some(key => row[key] !== 'pass')) {
      throw new DecisionJobError('only a decision with every hard gate passing may circulate');
    }
    return Object.fromEntries([...GATES].sort().map(key => [key, 'pass']));
  }

  function normalizeCirculation(value) {
    const row = exactKeys(value, new Set(['lane','task','surface','producer','consumers','blockedOn']), 'job.circulation');
    if (!['A','B'].includes(row.lane)) throw new DecisionJobError('job.circulation.lane must be A or B');
    return {
      lane: row.lane,
      task: requiredText(row.task, 'job.circulation.task'),
      surface: requiredText(row.surface, 'job.circulation.surface', 1024),
      producer: requiredText(row.producer, 'job.circulation.producer', 1024),
      consumers: stringList(row.consumers, 'job.circulation.consumers', false),
      blockedOn: optionalText(row.blockedOn, 'job.circulation.blockedOn', 256),
    };
  }

  function sourceCirculation(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new DecisionJobError('decision.circulation must be an object');
    }
    return normalizeCirculation({
      lane: value.lane,
      task: value.task,
      surface: value.surface,
      producer: value.producer,
      consumers: value.consumers,
      blockedOn: value.blockedOn ?? '',
    });
  }

  function sourceExecution(value) {
    if (value === undefined || value === null) return null;
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new DecisionJobError('decision.execution must be an object');
    }
    const state = value.state ?? 'not_started';
    if (state === 'not_started') {
      const extra = Object.keys(value).filter(key => key !== 'state');
      if (extra.length) throw new DecisionJobError(`not-started execution cannot carry evidence fields: ${JSON.stringify(extra.sort())}`);
      return null;
    }
    if (!EXECUTION_STATES.has(state)) throw new DecisionJobError(`unsupported execution state: ${JSON.stringify(state)}`);
    const implementationRefs = stringList(value.implementationRefs ?? [], 'decision.execution.implementationRefs');
    const verificationRefs = stringList(value.verificationRefs ?? [], 'decision.execution.verificationRefs');
    const result = {
      state,
      authority: requiredText(value.authority, 'decision.execution.authority'),
      implementationRefs,
      verificationRefs,
    };
    if (['verified','failed'].includes(state)) {
      if (!TERMINAL_OUTCOMES.has(value.outcome)) {
        throw new DecisionJobError(`terminal execution requires a supported outcome`);
      }
      if (!implementationRefs.length || !verificationRefs.length) {
        throw new DecisionJobError('terminal execution requires implementation and verification references');
      }
      result.outcome = value.outcome;
      result.completedAt = isoTime(value.completedAt, 'decision.execution.completedAt');
    } else if (value.outcome !== undefined || value.completedAt !== undefined) {
      throw new DecisionJobError('in-progress execution cannot carry a terminal outcome or completion time');
    }
    return result;
  }

  async function buildExecution(value, jobId) {
    const record = {format: EXECUTION_FORMAT, jobId, ...value};
    record.executionId = await digest('organexec1', record);
    await verifyExecution(record, jobId);
    return record;
  }

  async function verifyExecution(value, jobId) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new DecisionJobError('job.execution must be an object');
    }
    const base = new Set(['format','jobId','state','authority','implementationRefs','verificationRefs','executionId']);
    if (['verified','failed'].includes(value.state)) {
      base.add('outcome');
      base.add('completedAt');
    }
    const row = exactKeys(value, base, 'job.execution');
    if (row.format !== EXECUTION_FORMAT) throw new DecisionJobError(`job.execution must use ${EXECUTION_FORMAT}`);
    if (row.jobId !== jobId) throw new DecisionJobError('execution does not bind the enclosing job identity');
    const source = {
      state: row.state,
      authority: row.authority,
      implementationRefs: row.implementationRefs,
      verificationRefs: row.verificationRefs,
    };
    if (['verified','failed'].includes(row.state)) {
      source.outcome = row.outcome;
      source.completedAt = row.completedAt;
    }
    const normalized = sourceExecution(source);
    if (!normalized) throw new DecisionJobError('job.execution cannot be not_started');
    const expected = {format: EXECUTION_FORMAT, jobId, ...normalized};
    expected.executionId = await digest('organexec1', expected);
    if (canonicalStringify(row) !== canonicalStringify(expected)) {
      throw new DecisionJobError('execution record is not canonical or its identity mismatches');
    }
    return row;
  }

  async function buildDecision(model) {
    if (model.format !== MODEL_FORMAT) throw new DecisionJobError(`model must use ${MODEL_FORMAT}`);
    if (!model.estate || typeof model.estate !== 'object' || Array.isArray(model.estate)) {
      throw new DecisionJobError('model.estate must be an object');
    }
    const estateId = requiredText(model.estate.id, 'estate.id', 256);
    const organs = indexed(model.organs, 'organ');
    const candidates = indexed(model.candidates, 'candidate');
    const actors = indexed(model.actors, 'actor');
    const evidence = indexed(model.evidence, 'evidence');
    const source = model.decision;
    if (!source || typeof source !== 'object' || Array.isArray(source)) throw new DecisionJobError('model.decision must be an object');
    if (source.state !== 'accepted') throw new DecisionJobError('only an accepted decision may enter circulation');
    const organId = requiredText(source.organId, 'decision.organId', 256);
    const candidateId = requiredText(source.candidateId, 'decision.candidateId', 256);
    const deciderId = requiredText(source.decider, 'decision.decider', 256);
    const organ = organs.get(organId);
    const candidate = candidates.get(candidateId);
    const decider = actors.get(deciderId);
    if (!organ) throw new DecisionJobError(`decision references unknown organ ${organId}`);
    if (!candidate || candidate.organId !== organId) throw new DecisionJobError(`decision candidate ${candidateId} does not belong to ${organId}`);
    if (!decider) throw new DecisionJobError(`decision references unknown actor ${deciderId}`);
    const declaredDeciders = candidate.actorLinks?.deciders ?? [];
    if (!declaredDeciders.includes(deciderId)) throw new DecisionJobError(`decision actor ${deciderId} is not a declared decider for ${candidateId}`);
    const evidenceRows = stringList(candidate.evidenceIds ?? [], 'candidate.evidenceIds', false).map(id => {
      const row = evidence.get(id);
      if (!row) throw new DecisionJobError(`candidate references unknown evidence ${id}`);
      return {id, title: row.title, tier: row.tier, independence: row.independence, source: row.source, claim: row.claim, limits: row.limits};
    });
    const decision = {
      format: DECISION_FORMAT,
      estateId,
      organId,
      organName: requiredText(organ.name, 'organ.name'),
      candidateId,
      candidateName: requiredText(candidate.name, 'candidate.name'),
      action: requiredText(candidate.action, 'candidate.action', 128),
      state: 'accepted',
      posture: 'admissible',
      decider: {id: deciderId, name: requiredText(decider.name, 'decider.name')},
      decidedAt: isoTime(source.decidedAt, 'decision.decidedAt'),
      mandate: {
        ref: requiredText(source.mandateRef, 'decision.mandateRef', 2048),
        basis: requiredText(source.mandateBasis, 'decision.mandateBasis'),
        authentication: 'not performed by the compiler',
      },
      rationale: requiredText(source.rationale, 'decision.rationale'),
      openQuestions: stringList(source.openQuestions ?? [], 'decision.openQuestions'),
      gates: normalizeGates(candidate.gates),
      dimensions: normalizeDimensions(candidate.dimensions),
      migration: normalizeMigration(candidate.changes),
      evidence: normalizeEvidence(evidenceRows),
    };
    decision.decisionId = await digest('orgdec1', decision);
    await verifyDecision(decision);
    return decision;
  }

  async function verifyDecision(value) {
    const required = new Set([
      'format','estateId','organId','organName','candidateId','candidateName','action','state','posture',
      'decider','decidedAt','mandate','rationale','openQuestions','gates','dimensions','migration','evidence','decisionId',
    ]);
    const row = exactKeys(value, required, 'job.decision');
    if (row.format !== DECISION_FORMAT) throw new DecisionJobError(`job.decision must use ${DECISION_FORMAT}`);
    if (row.state !== 'accepted' || row.posture !== 'admissible') throw new DecisionJobError('job decision is not accepted and admissible');
    requiredText(row.estateId, 'decision.estateId', 256);
    requiredText(row.organId, 'decision.organId', 256);
    requiredText(row.organName, 'decision.organName');
    requiredText(row.candidateId, 'decision.candidateId', 256);
    requiredText(row.candidateName, 'decision.candidateName');
    requiredText(row.action, 'decision.action', 128);
    const decider = exactKeys(row.decider, new Set(['id','name']), 'decision.decider');
    requiredText(decider.id, 'decision.decider.id', 256);
    requiredText(decider.name, 'decision.decider.name');
    isoTime(row.decidedAt, 'decision.decidedAt');
    const mandate = exactKeys(row.mandate, new Set(['ref','basis','authentication']), 'decision.mandate');
    requiredText(mandate.ref, 'decision.mandate.ref', 2048);
    requiredText(mandate.basis, 'decision.mandate.basis');
    if (mandate.authentication !== 'not performed by the compiler') throw new DecisionJobError('decision mandate authentication claim is unsupported');
    requiredText(row.rationale, 'decision.rationale');
    stringList(row.openQuestions, 'decision.openQuestions');
    normalizeGates(row.gates);
    normalizeDimensions(row.dimensions);
    normalizeMigration(row.migration);
    normalizeEvidence(row.evidence);
    const expected = await digest('orgdec1', withoutKeys(row, 'decisionId'));
    if (row.decisionId !== expected) throw new DecisionJobError('decision identity mismatch');
    validateDigest(row.decisionId, 'orgdec1', 'decision.decisionId');
    return row;
  }

  async function build(model) {
    validateDepth(model);
    const decision = await buildDecision(model);
    const sourceDecision = model.decision;
    const bundle = {
      format: JOB_FORMAT,
      source: {
        modelFormat: MODEL_FORMAT,
        estateId: decision.estateId,
        modelDigest: await digest('orgmodel1', model),
      },
      decision,
      circulation: sourceCirculation(sourceDecision.circulation),
      authority: clone(AUTHORITY),
      limits: [
        'The compiler validates structure and declared decision geometry; it does not authenticate the mandate, decider, cited evidence, implementation, or outcome.',
        'Bloodstream may preserve and report this job but cannot admit it, prioritize it, execute it, or accept its outcome.',
        'Any consumer must verify cited implementation and verification references independently when that distinction matters.',
      ],
    };
    bundle.jobId = await digest('organjob1', bundle);
    const executionSource = sourceExecution(sourceDecision.execution);
    if (executionSource) bundle.execution = await buildExecution(executionSource, bundle.jobId);
    await verify(bundle);
    return bundle;
  }

  async function verify(value) {
    validateDepth(value);
    const required = new Set(['format','source','decision','circulation','authority','limits','jobId']);
    if (Object.prototype.hasOwnProperty.call(value, 'execution')) required.add('execution');
    const bundle = exactKeys(value, required, 'job bundle');
    if (bundle.format !== JOB_FORMAT) throw new DecisionJobError(`job bundle must use ${JOB_FORMAT}`);
    const source = exactKeys(bundle.source, new Set(['modelFormat','estateId','modelDigest']), 'job.source');
    if (source.modelFormat !== MODEL_FORMAT) throw new DecisionJobError('job source model format is unsupported');
    requiredText(source.estateId, 'job.source.estateId', 256);
    validateDigest(source.modelDigest, 'orgmodel1', 'job.source.modelDigest');
    const decision = await verifyDecision(bundle.decision);
    if (source.estateId !== decision.estateId) throw new DecisionJobError('job source and decision estate identities differ');
    const circulation = normalizeCirculation(bundle.circulation);
    if (canonicalStringify(circulation) !== canonicalStringify(bundle.circulation)) throw new DecisionJobError('circulation record is not canonical');
    if (canonicalStringify(bundle.authority) !== canonicalStringify(AUTHORITY)) throw new DecisionJobError('job authority membrane differs from the compiler contract');
    const limits = stringList(bundle.limits, 'job.limits', false);
    if (canonicalStringify(limits) !== canonicalStringify(bundle.limits)) throw new DecisionJobError('job limits are not canonical');
    const expectedJob = await digest('organjob1', withoutKeys(bundle, 'jobId', 'execution'));
    if (bundle.jobId !== expectedJob) throw new DecisionJobError('job identity mismatch');
    validateDigest(bundle.jobId, 'organjob1', 'job.jobId');
    if (bundle.execution) await verifyExecution(bundle.execution, bundle.jobId);
    return bundle;
  }

  window.AXM_DECISION_JOB = {
    MODEL_FORMAT,
    DECISION_FORMAT,
    JOB_FORMAT,
    EXECUTION_FORMAT,
    AUTHORITY: clone(AUTHORITY),
    DecisionJobError,
    canonicalStringify,
    digest,
    build,
    verify,
  };
})();
