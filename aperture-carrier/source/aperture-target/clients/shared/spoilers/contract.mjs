import { createHash } from 'node:crypto';

export const SPOILER_CONTEXT_VERSION = 'axm-aperture-spoiler-context/1';
export const SPOILER_STATE_VERSION = 'axm-aperture-spoiler-control-state/1';
export const SPOILER_POLICY_INTENT_VERSION = 'axm-aperture-spoiler-policy-intent/1';
export const KNOWLEDGE_INTENT_VERSION = 'axm-aperture-knowledge-event-intent/1';
export const KNOWLEDGE_DELIVERY_VERSION = 'axm-aperture-knowledge-intent-delivery/1';
export const SPOILER_VIEW_VERSION = 'axm-aperture-spoiler-view/1';

export const SPOILER_MODES = Object.freeze([
  'scene_only',
  'necessary_antecedents',
  'full_antecedent_chain',
  'known_outcomes',
  'full_continuity',
]);

export const KNOWLEDGE_ASSUMPTIONS = Object.freeze([
  'explicit_events_only',
  'all_prior_positions',
  'none',
]);

export const MODEL_INFERENCE_POLICIES = Object.freeze(['disabled', 'proposals_only']);
export const CONTEXT_STATES = Object.freeze([
  'ready',
  'unavailable',
  'partial',
  'stale',
  'ambiguous',
  'conflict',
  'refused',
  'unsupported',
  'disconnected',
]);
export const KNOWLEDGE_BASES = Object.freeze([
  'seen',
  'heard',
  'explained',
  'user_asserted',
  'inferred',
  'outcome_spoiled',
]);
export const KNOWLEDGE_EFFECTS = Object.freeze(['acquire', 'revoke', 'reaffirm', 'propose']);
export const KNOWLEDGE_STANDINGS = Object.freeze([
  'active_assumption',
  'revoked_assumption',
  'proposed_only',
]);
export const POLICY_SCOPES = Object.freeze(['global', 'story', 'query']);
export const KNOWLEDGE_ACTIONS = Object.freeze([
  'confirm',
  'revoke_basis',
  'restore_basis',
  'correct_fact',
]);

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:@/+~-]{0,255}$/;
const DIGEST = /^[0-9a-f]{64}$/;
const REASON = /^[a-z0-9][a-z0-9._:-]{0,127}$/;
const SENSITIVE_FIELD = /^(?:authorization|bearer|certificate|cookie|credential|key|password|secret|token|username)$/i;

function fail(code, details = {}) {
  const error = new TypeError(code);
  error.code = code;
  error.details = details;
  throw error;
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function assertRecord(value, code) {
  if (!isRecord(value)) fail(code);
  return value;
}

function assertExactKeys(value, keys, code) {
  const observed = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (observed.length !== expected.length || observed.some((key, index) => key !== expected[index])) {
    fail(code, { observed, expected });
  }
}

function assertNoSensitiveFields(value, path = '$') {
  if (Array.isArray(value)) {
    value.forEach((child, index) => assertNoSensitiveFields(child, `${path}[${index}]`));
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (SENSITIVE_FIELD.test(key)) fail('credential_field_forbidden', { path: `${path}.${key}` });
    assertNoSensitiveFields(child, `${path}.${key}`);
  }
}

function assertString(value, code, { min = 1, max = 8192, pattern = null, allowEmpty = false } = {}) {
  if (typeof value !== 'string') fail(code);
  if (!allowEmpty && value.length < min) fail(code);
  if (value.length > max) fail(code);
  if (pattern && !pattern.test(value)) fail(code);
  return value;
}

function assertIdentifier(value, code) {
  return assertString(value, code, { max: 256, pattern: IDENTIFIER });
}

function assertDigest(value, code) {
  return assertString(value, code, { min: 64, max: 64, pattern: DIGEST });
}

function assertReason(value, code, required = false) {
  if (value === '' && !required) return '';
  return assertString(value, code, { max: 128, pattern: REASON });
}

function assertInteger(value, code, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
  return value;
}

function assertBoolean(value, code) {
  if (typeof value !== 'boolean') fail(code);
  return value;
}

function assertEnum(value, allowed, code) {
  if (!allowed.includes(value)) fail(code, { value, allowed });
  return value;
}

function validateUniqueStrings(value, code, { min = 0, max = 256, identifiers = true } = {}) {
  if (!Array.isArray(value) || value.length < min || value.length > max) fail(code);
  const rows = value.map((entry, index) => identifiers
    ? assertIdentifier(entry, `${code}:${index}`)
    : assertString(entry, `${code}:${index}`, { max: 4096 }));
  if (new Set(rows).size !== rows.length) fail(`${code}:duplicate`);
  return rows;
}

export function canonicalJson(value) {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && !Number.isSafeInteger(value)) fail('canonical_number_invalid');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
    .join(',')}}`;
}

export function sha256Json(value) {
  return createHash('sha256').update(canonicalJson(value)).digest('hex');
}

export function contentId(prefix, value, idField = null) {
  const core = structuredClone(value);
  if (idField) delete core[idField];
  return `${prefix}${sha256Json(core)}`;
}

function freezeOwned(value) {
  if (value === null || typeof value !== 'object') return value;
  for (const child of Object.values(value)) freezeOwned(child);
  return Object.freeze(value);
}

export function cloneOwned(value) {
  return freezeOwned(structuredClone(value));
}

function validateSourceRefs(value, code) {
  if (!Array.isArray(value) || value.length < 1 || value.length > 64) fail(code);
  const rows = value.map((raw, index) => {
    const row = assertRecord(raw, `${code}:${index}`);
    assertExactKeys(row, ['kind', 'ref', 'sha256'], `${code}:${index}:fields`);
    return {
      kind: assertEnum(
        row.kind,
        ['observation', 'source', 'receipt', 'review', 'user_action', 'policy'],
        `${code}:${index}:kind`,
      ),
      ref: assertString(row.ref, `${code}:${index}:ref`, { max: 1024 }),
      sha256: assertDigest(row.sha256, `${code}:${index}:sha256`),
    };
  });
  const identities = rows.map((row) => `${row.kind}:${row.ref}:${row.sha256}`);
  if (new Set(identities).size !== identities.length) fail(`${code}:duplicate`);
  return rows;
}

function validatePolicy(value) {
  const row = assertRecord(value, 'knowledge_policy_invalid');
  assertExactKeys(
    row,
    ['policyId', 'policyVersion', 'defaultSeenAssumption', 'modelInference', 'spoilerEffectsRecorded', 'userCanRevoke', 'authority'],
    'knowledge_policy_fields_invalid',
  );
  return {
    policyId: assertIdentifier(row.policyId, 'knowledge_policy_id_invalid'),
    policyVersion: assertString(row.policyVersion, 'knowledge_policy_version_invalid', { max: 64 }),
    defaultSeenAssumption: assertEnum(
      row.defaultSeenAssumption,
      KNOWLEDGE_ASSUMPTIONS,
      'knowledge_policy_seen_assumption_invalid',
    ),
    modelInference: assertEnum(row.modelInference, MODEL_INFERENCE_POLICIES, 'knowledge_policy_model_inference_invalid'),
    spoilerEffectsRecorded: row.spoilerEffectsRecorded === true
      ? true
      : fail('knowledge_policy_spoiler_recording_required'),
    userCanRevoke: row.userCanRevoke === true ? true : fail('knowledge_policy_revocation_required'),
    authority: row.authority === 'viewer_policy_only' ? row.authority : fail('knowledge_policy_authority_invalid'),
  };
}

function validateEvent(raw, factId, index) {
  const row = assertRecord(raw, `knowledge_event_invalid:${factId}:${index}`);
  assertExactKeys(
    row,
    ['eventId', 'idempotencyKey', 'effect', 'basis', 'standing', 'actor', 'recordedAtUs', 'sourceRefs'],
    `knowledge_event_fields_invalid:${factId}:${index}`,
  );
  const effect = assertEnum(row.effect, KNOWLEDGE_EFFECTS, `knowledge_event_effect_invalid:${factId}:${index}`);
  const basis = assertEnum(row.basis, KNOWLEDGE_BASES, `knowledge_event_basis_invalid:${factId}:${index}`);
  const standing = assertEnum(row.standing, KNOWLEDGE_STANDINGS, `knowledge_event_standing_invalid:${factId}:${index}`);
  if (basis === 'inferred') {
    if (effect !== 'propose' || standing !== 'proposed_only') fail('model_inference_must_remain_proposal', { factId });
  }
  if (effect === 'propose' && standing !== 'proposed_only') fail('proposal_standing_invalid', { factId });
  if (effect === 'revoke' && standing !== 'revoked_assumption') fail('revocation_standing_invalid', { factId });
  if (['acquire', 'reaffirm'].includes(effect) && standing !== 'active_assumption') {
    fail('active_event_standing_invalid', { factId });
  }
  return {
    eventId: assertIdentifier(row.eventId, `knowledge_event_id_invalid:${factId}:${index}`),
    idempotencyKey: assertDigest(row.idempotencyKey, `knowledge_event_idempotency_invalid:${factId}:${index}`),
    effect,
    basis,
    standing,
    actor: assertString(row.actor, `knowledge_event_actor_invalid:${factId}:${index}`, { max: 256 }),
    recordedAtUs: assertInteger(row.recordedAtUs, `knowledge_event_time_invalid:${factId}:${index}`),
    sourceRefs: validateSourceRefs(row.sourceRefs, `knowledge_event_source_refs_invalid:${factId}:${index}`),
  };
}

function deriveBases(history, factId) {
  const latest = new Map();
  for (const row of history) {
    if (row.effect === 'propose') continue;
    latest.set(row.basis, row);
  }
  return [...latest.entries()]
    .sort(([left], [right]) => left.localeCompare(right, 'en'))
    .map(([basis, row]) => ({
      basis,
      active: row.effect !== 'revoke',
      latestEventId: row.eventId,
      eventIds: history.filter((event) => event.basis === basis).map((event) => event.eventId),
    }));
}

function validateFact(raw, index) {
  const row = assertRecord(raw, `knowledge_fact_invalid:${index}`);
  assertExactKeys(
    row,
    ['factId', 'label', 'firstRevealPositionId', 'firstRevealPositionUs', 'history', 'bases'],
    `knowledge_fact_fields_invalid:${index}`,
  );
  const factId = assertIdentifier(row.factId, `knowledge_fact_id_invalid:${index}`);
  if (!Array.isArray(row.history) || row.history.length > 512) fail(`knowledge_fact_history_invalid:${factId}`);
  const history = row.history.map((entry, eventIndex) => validateEvent(entry, factId, eventIndex));
  const eventIds = history.map((event) => event.eventId);
  if (new Set(eventIds).size !== eventIds.length) fail('knowledge_event_id_duplicate', { factId });
  const idempotencyKeys = history.map((event) => event.idempotencyKey);
  if (new Set(idempotencyKeys).size !== idempotencyKeys.length) fail('knowledge_event_idempotency_duplicate', { factId });
  const sorted = [...history].sort((left, right) => left.recordedAtUs - right.recordedAtUs || left.eventId.localeCompare(right.eventId, 'en'));
  if (canonicalJson(sorted) !== canonicalJson(history)) fail('knowledge_history_not_ordered', { factId });

  const derivedBases = deriveBases(history, factId);
  if (!Array.isArray(row.bases)) fail(`knowledge_fact_bases_invalid:${factId}`);
  const bases = row.bases.map((rawBasis, basisIndex) => {
    const basis = assertRecord(rawBasis, `knowledge_basis_invalid:${factId}:${basisIndex}`);
    assertExactKeys(basis, ['basis', 'active', 'latestEventId', 'eventIds'], `knowledge_basis_fields_invalid:${factId}:${basisIndex}`);
    return {
      basis: assertEnum(basis.basis, KNOWLEDGE_BASES.filter((value) => value !== 'inferred'), `knowledge_basis_name_invalid:${factId}:${basisIndex}`),
      active: assertBoolean(basis.active, `knowledge_basis_active_invalid:${factId}:${basisIndex}`),
      latestEventId: assertIdentifier(basis.latestEventId, `knowledge_basis_latest_event_invalid:${factId}:${basisIndex}`),
      eventIds: validateUniqueStrings(basis.eventIds, `knowledge_basis_events_invalid:${factId}:${basisIndex}`, { min: 1 }),
    };
  });
  if (canonicalJson(bases) !== canonicalJson(derivedBases)) fail('knowledge_basis_projection_drifted', { factId });

  return {
    factId,
    label: assertString(row.label, `knowledge_fact_label_invalid:${index}`, { max: 512 }),
    firstRevealPositionId: assertIdentifier(row.firstRevealPositionId, `knowledge_fact_position_invalid:${index}`),
    firstRevealPositionUs: assertInteger(row.firstRevealPositionUs, `knowledge_fact_reveal_time_invalid:${index}`),
    history,
    bases,
  };
}

export function resolveSpoilerPolicy(globalMode, storyMode, queryMode) {
  const globalSpoilerMode = assertEnum(globalMode, SPOILER_MODES, 'global_spoiler_mode_invalid');
  const storySpoilerMode = storyMode === null ? null : assertEnum(storyMode, SPOILER_MODES, 'story_spoiler_mode_invalid');
  const querySpoilerMode = queryMode === null ? null : assertEnum(queryMode, SPOILER_MODES, 'query_spoiler_mode_invalid');
  if (querySpoilerMode !== null) return cloneOwned({ mode: querySpoilerMode, source: 'query' });
  if (storySpoilerMode !== null) return cloneOwned({ mode: storySpoilerMode, source: 'story' });
  return cloneOwned({ mode: globalSpoilerMode, source: 'global' });
}

export function validateSpoilerContext(value) {
  assertNoSensitiveFields(value);
  const row = assertRecord(value, 'spoiler_context_invalid');
  assertExactKeys(
    row,
    [
      'version', 'contextId', 'sequence', 'state', 'reasonCode', 'viewerId', 'viewerDigest',
      'workId', 'continuityId', 'storyPackageId', 'storyPackageDigest', 'packageRevision',
      'queryId', 'currentPositionId', 'currentPositionUs', 'globalSpoilerMode', 'storySpoilerMode',
      'querySpoilerMode', 'resolvedSpoilerMode', 'resolvedSpoilerSource', 'knowledgePolicy',
      'facts', 'appliedIntentIds', 'rejectedIntentIds', 'accessReceiptRefs', 'authority',
    ],
    'spoiler_context_fields_invalid',
  );
  if (row.version !== SPOILER_CONTEXT_VERSION) fail('spoiler_context_version_invalid');
  const state = assertEnum(row.state, CONTEXT_STATES, 'spoiler_context_state_invalid');
  const currentPositionUs = row.currentPositionUs === null
    ? null
    : assertInteger(row.currentPositionUs, 'spoiler_context_position_us_invalid');
  if (state === 'ready' && currentPositionUs === null) fail('ready_context_requires_position');
  const globalSpoilerMode = assertEnum(row.globalSpoilerMode, SPOILER_MODES, 'global_spoiler_mode_invalid');
  const storySpoilerMode = row.storySpoilerMode === null
    ? null
    : assertEnum(row.storySpoilerMode, SPOILER_MODES, 'story_spoiler_mode_invalid');
  const querySpoilerMode = row.querySpoilerMode === null
    ? null
    : assertEnum(row.querySpoilerMode, SPOILER_MODES, 'query_spoiler_mode_invalid');
  const resolved = resolveSpoilerPolicy(globalSpoilerMode, storySpoilerMode, querySpoilerMode);
  if (row.resolvedSpoilerMode !== resolved.mode || row.resolvedSpoilerSource !== resolved.source) {
    fail('resolved_spoiler_policy_drifted', { expected: resolved, observed: { mode: row.resolvedSpoilerMode, source: row.resolvedSpoilerSource } });
  }
  if (!Array.isArray(row.facts) || row.facts.length > 4096) fail('knowledge_facts_invalid');
  const facts = row.facts.map(validateFact);
  const factIds = facts.map((fact) => fact.factId);
  if (new Set(factIds).size !== factIds.length) fail('knowledge_fact_duplicate');
  const sortedFacts = [...facts].sort((left, right) => left.factId.localeCompare(right.factId, 'en'));
  if (canonicalJson(sortedFacts) !== canonicalJson(facts)) fail('knowledge_facts_not_ordered');
  const appliedIntentIds = validateUniqueStrings(row.appliedIntentIds, 'applied_intent_ids_invalid');
  const rejectedIntentIds = validateUniqueStrings(row.rejectedIntentIds, 'rejected_intent_ids_invalid');
  if (appliedIntentIds.some((intentId) => rejectedIntentIds.includes(intentId))) fail('intent_terminal_standing_conflict');
  return cloneOwned({
    version: row.version,
    contextId: assertIdentifier(row.contextId, 'spoiler_context_id_invalid'),
    sequence: assertInteger(row.sequence, 'spoiler_context_sequence_invalid'),
    state,
    reasonCode: assertReason(row.reasonCode, 'spoiler_context_reason_invalid', state !== 'ready'),
    viewerId: assertIdentifier(row.viewerId, 'spoiler_context_viewer_invalid'),
    viewerDigest: assertDigest(row.viewerDigest, 'spoiler_context_viewer_digest_invalid'),
    workId: assertIdentifier(row.workId, 'spoiler_context_work_invalid'),
    continuityId: assertIdentifier(row.continuityId, 'spoiler_context_continuity_invalid'),
    storyPackageId: assertIdentifier(row.storyPackageId, 'spoiler_context_package_invalid'),
    storyPackageDigest: assertDigest(row.storyPackageDigest, 'spoiler_context_package_digest_invalid'),
    packageRevision: assertInteger(row.packageRevision, 'spoiler_context_package_revision_invalid', 1),
    queryId: row.queryId === null ? null : assertIdentifier(row.queryId, 'spoiler_context_query_invalid'),
    currentPositionId: row.currentPositionId === null ? null : assertIdentifier(row.currentPositionId, 'spoiler_context_position_invalid'),
    currentPositionUs,
    globalSpoilerMode,
    storySpoilerMode,
    querySpoilerMode,
    resolvedSpoilerMode: resolved.mode,
    resolvedSpoilerSource: resolved.source,
    knowledgePolicy: validatePolicy(row.knowledgePolicy),
    facts,
    appliedIntentIds,
    rejectedIntentIds,
    accessReceiptRefs: validateUniqueStrings(row.accessReceiptRefs, 'spoiler_context_access_receipts_invalid'),
    authority: row.authority === 'external_daemon_projection_only'
      ? row.authority
      : fail('spoiler_context_authority_invalid'),
  });
}

export function factAvailability(contextValue, factId) {
  const context = validateSpoilerContext(contextValue);
  const fact = context.facts.find((candidate) => candidate.factId === factId);
  if (!fact) fail('knowledge_fact_unknown', { factId });
  const reasons = [];
  for (const basis of fact.bases) {
    if (!basis.active) continue;
    if (basis.basis === 'seen' && context.knowledgePolicy.defaultSeenAssumption === 'none') continue;
    reasons.push({
      kind: 'active_event_basis',
      basis: basis.basis,
      eventIds: basis.eventIds,
      latestEventId: basis.latestEventId,
    });
  }
  if (
    context.knowledgePolicy.defaultSeenAssumption === 'all_prior_positions' &&
    context.currentPositionUs !== null &&
    fact.firstRevealPositionUs <= context.currentPositionUs
  ) {
    reasons.push({
      kind: 'policy_assumption',
      basis: 'seen',
      eventIds: [],
      latestEventId: '',
    });
  }
  return cloneOwned({
    factId,
    available: reasons.length > 0,
    reasons,
    activeBasisCount: reasons.filter((reason) => reason.kind === 'active_event_basis').length,
    policyAssumed: reasons.some((reason) => reason.kind === 'policy_assumption'),
  });
}

export function buildSpoilerPolicyIntent(contextValue, actionValue) {
  const context = validateSpoilerContext(contextValue);
  if (context.state !== 'ready') fail('spoiler_policy_context_not_ready');
  const action = assertRecord(actionValue, 'spoiler_policy_action_invalid');
  assertExactKeys(action, ['actionId', 'recordedAtUs', 'scope', 'mode', 'reasonCode'], 'spoiler_policy_action_fields_invalid');
  const scope = assertEnum(action.scope, POLICY_SCOPES, 'spoiler_policy_scope_invalid');
  if (scope === 'query' && context.queryId === null) fail('query_policy_requires_query');
  const mode = assertEnum(action.mode, SPOILER_MODES, 'spoiler_policy_mode_invalid');
  const previousMode = {
    global: context.globalSpoilerMode,
    story: context.storySpoilerMode,
    query: context.querySpoilerMode,
  }[scope];
  const core = {
    version: SPOILER_POLICY_INTENT_VERSION,
    contextId: context.contextId,
    contextSequence: context.sequence,
    actionId: assertIdentifier(action.actionId, 'spoiler_policy_action_id_invalid'),
    recordedAtUs: assertInteger(action.recordedAtUs, 'spoiler_policy_action_time_invalid'),
    viewerId: context.viewerId,
    viewerDigest: context.viewerDigest,
    workId: context.workId,
    continuityId: context.continuityId,
    storyPackageId: context.storyPackageId,
    storyPackageDigest: context.storyPackageDigest,
    packageRevision: context.packageRevision,
    queryId: context.queryId,
    scope,
    previousMode,
    mode,
    reasonCode: assertReason(action.reasonCode, 'spoiler_policy_action_reason_invalid'),
    authority: 'viewer_policy_intent_only',
    applied: false,
  };
  return cloneOwned({ intentId: contentId('spoilerintent1_', core), ...core });
}

function buildKnowledgeEvent(context, action, factId, effect, basis, standing, ordinal) {
  const core = {
    format: 'axm-aperture-knowledge-event/1',
    idempotencyKey: sha256Json({ actionId: action.actionId, ordinal, factId, effect, basis }),
    viewerId: context.viewerId,
    storyPackageId: context.storyPackageId,
    packageRevision: context.packageRevision,
    factId,
    effect,
    basis,
    standing,
    actor: `viewer:${context.viewerId}`,
    sourceRefs: [{
      kind: 'user_action',
      ref: action.sourceReceiptRef,
      sha256: action.sourceReceiptSha256,
    }],
    recordedAtUs: action.recordedAtUs,
    authority: 'knowledge_event_only',
  };
  return { eventId: contentId('knowledge1_', core), ...core };
}

export function buildKnowledgeIntent(contextValue, actionValue) {
  const context = validateSpoilerContext(contextValue);
  if (context.state !== 'ready') fail('knowledge_action_context_not_ready');
  const action = assertRecord(actionValue, 'knowledge_action_invalid');
  assertExactKeys(
    action,
    ['actionId', 'recordedAtUs', 'action', 'factId', 'basis', 'replacementFactId', 'reasonCode', 'sourceReceiptRef', 'sourceReceiptSha256'],
    'knowledge_action_fields_invalid',
  );
  const actionKind = assertEnum(action.action, KNOWLEDGE_ACTIONS, 'knowledge_action_kind_invalid');
  const factId = assertIdentifier(action.factId, 'knowledge_action_fact_invalid');
  const fact = context.facts.find((candidate) => candidate.factId === factId);
  if (!fact) fail('knowledge_action_fact_unknown');
  const basis = action.basis === null ? null : assertEnum(action.basis, KNOWLEDGE_BASES.filter((value) => value !== 'inferred'), 'knowledge_action_basis_invalid');
  const replacementFactId = action.replacementFactId === null
    ? null
    : assertIdentifier(action.replacementFactId, 'knowledge_action_replacement_invalid');
  const normalized = {
    actionId: assertIdentifier(action.actionId, 'knowledge_action_id_invalid'),
    recordedAtUs: assertInteger(action.recordedAtUs, 'knowledge_action_time_invalid'),
    sourceReceiptRef: assertString(action.sourceReceiptRef, 'knowledge_action_source_ref_invalid', { max: 1024 }),
    sourceReceiptSha256: assertDigest(action.sourceReceiptSha256, 'knowledge_action_source_sha_invalid'),
  };
  const events = [];
  if (actionKind === 'confirm') {
    if (basis !== null || replacementFactId !== null) fail('knowledge_confirm_fields_invalid');
    events.push(buildKnowledgeEvent(context, normalized, factId, 'acquire', 'user_asserted', 'active_assumption', 0));
  } else if (actionKind === 'revoke_basis') {
    if (basis === null || replacementFactId !== null) fail('knowledge_revoke_fields_invalid');
    const projected = fact.bases.find((row) => row.basis === basis);
    if (!projected?.active) fail('knowledge_revoke_requires_active_basis');
    events.push(buildKnowledgeEvent(context, normalized, factId, 'revoke', basis, 'revoked_assumption', 0));
  } else if (actionKind === 'restore_basis') {
    if (basis === null || replacementFactId !== null) fail('knowledge_restore_fields_invalid');
    const projected = fact.bases.find((row) => row.basis === basis);
    if (!projected || projected.active) fail('knowledge_restore_requires_revoked_basis');
    events.push(buildKnowledgeEvent(context, normalized, factId, 'reaffirm', basis, 'active_assumption', 0));
  } else {
    if (basis !== null || replacementFactId === null) fail('knowledge_correction_fields_invalid');
    const replacement = context.facts.find((candidate) => candidate.factId === replacementFactId);
    if (!replacement) fail('knowledge_correction_replacement_unknown');
    if (replacementFactId === factId) fail('knowledge_correction_self_replacement');
    const activeBases = fact.bases.filter((row) => row.active);
    if (activeBases.length === 0) fail('knowledge_correction_requires_active_basis');
    for (const [index, activeBasis] of activeBases.entries()) {
      events.push(buildKnowledgeEvent(
        context,
        normalized,
        factId,
        'revoke',
        activeBasis.basis,
        'revoked_assumption',
        index,
      ));
    }
    events.push(buildKnowledgeEvent(
      context,
      normalized,
      replacementFactId,
      'acquire',
      'user_asserted',
      'active_assumption',
      activeBases.length,
    ));
  }
  const core = {
    version: KNOWLEDGE_INTENT_VERSION,
    contextId: context.contextId,
    contextSequence: context.sequence,
    actionId: normalized.actionId,
    action: actionKind,
    viewerId: context.viewerId,
    viewerDigest: context.viewerDigest,
    workId: context.workId,
    continuityId: context.continuityId,
    storyPackageId: context.storyPackageId,
    storyPackageDigest: context.storyPackageDigest,
    packageRevision: context.packageRevision,
    factId,
    replacementFactId,
    reasonCode: assertReason(action.reasonCode, 'knowledge_action_reason_invalid', true),
    events,
    authority: 'viewer_knowledge_intent_only',
    applied: false,
  };
  return cloneOwned({ intentId: contentId('knowledgeintent1_', core), ...core });
}

export function validateIntentDelivery(value, intent) {
  const row = assertRecord(value, 'knowledge_delivery_invalid');
  assertExactKeys(row, ['version', 'receiptId', 'intentId', 'state', 'reasonCode', 'authority'], 'knowledge_delivery_fields_invalid');
  if (row.version !== KNOWLEDGE_DELIVERY_VERSION) fail('knowledge_delivery_version_invalid');
  if (row.intentId !== intent.intentId) fail('knowledge_delivery_intent_mismatch');
  const core = {
    version: row.version,
    intentId: row.intentId,
    state: assertEnum(row.state, ['queued', 'delivered', 'refused'], 'knowledge_delivery_state_invalid'),
    reasonCode: assertReason(row.reasonCode, 'knowledge_delivery_reason_invalid', row.state === 'refused'),
    authority: row.authority === 'transport_receipt_only' ? row.authority : fail('knowledge_delivery_authority_invalid'),
  };
  const receiptId = assertIdentifier(row.receiptId, 'knowledge_delivery_receipt_invalid');
  if (receiptId !== contentId('knowledgedelivery1_', core)) fail('knowledge_delivery_identity_invalid');
  return cloneOwned({ receiptId, ...core });
}
