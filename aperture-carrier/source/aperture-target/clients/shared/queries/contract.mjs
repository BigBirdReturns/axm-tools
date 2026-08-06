import { createHash } from 'node:crypto';

export const QUERY_CONTEXT_VERSION = 'axm-aperture-query-context/1';
export const QUERY_INPUT_VERSION = 'axm-aperture-query-input/1';
export const QUERY_INTENT_VERSION = 'axm-aperture-query-intent/1';
export const QUERY_DELIVERY_VERSION = 'axm-aperture-query-delivery/1';
export const PLANNER_OBSERVATION_VERSION = 'axm-aperture-planner-observation/1';
export const ANSWER_OBSERVATION_VERSION = 'axm-aperture-answer-observation/1';
export const QUERY_STATE_VERSION = 'axm-aperture-query-state/1';
export const QUERY_VIEW_VERSION = 'axm-aperture-query-view/1';

export const CORE_OPERATIONS = Object.freeze([
  'where_am_i',
  'who_is_this',
  'explain_this',
  'ask',
]);

export const SPOILER_MODES = Object.freeze([
  'scene_only',
  'necessary_antecedents',
  'full_antecedent_chain',
  'known_outcomes',
  'full_continuity',
]);

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

export const FACT_ROLES = Object.freeze([
  'current_scene',
  'necessary_antecedent',
  'identity',
  'motive',
  'outcome',
  'caveat',
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

function assertOptionalIdentifier(value, code) {
  if (value === '') return '';
  return assertIdentifier(value, code);
}

function assertDigest(value, code) {
  return assertString(value, code, { min: 64, max: 64, pattern: DIGEST });
}

function assertReason(value, code, required = false) {
  if (value === '' && !required) return '';
  return assertString(value, code, { max: 128, pattern: REASON });
}

function assertBoolean(value, code) {
  if (typeof value !== 'boolean') fail(code);
  return value;
}

function assertInteger(value, code, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
  return value;
}

function assertEnum(value, allowed, code) {
  if (!allowed.includes(value)) fail(code, { value, allowed });
  return value;
}

function validateUniqueStrings(value, code, { max = 256, identifiers = true, min = 0 } = {}) {
  if (!Array.isArray(value) || value.length < min || value.length > max) fail(code);
  const rows = value.map((entry, index) => identifiers
    ? assertIdentifier(entry, `${code}:${index}`)
    : assertString(entry, `${code}:${index}`, { max: 20_000 }));
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

function validateAnchor(value, contextState) {
  const record = assertRecord(value, 'query_anchor_invalid');
  assertExactKeys(
    record,
    [
      'anchorId',
      'observationId',
      'canonicalPositionUs',
      'clockMode',
      'identityMode',
      'clockConfidencePpm',
      'identityConfidencePpm',
      'state',
      'reasonCode',
    ],
    'query_anchor_fields_invalid',
  );
  const canonicalPositionUs = record.canonicalPositionUs === null
    ? null
    : assertInteger(record.canonicalPositionUs, 'query_anchor_position_invalid');
  const state = assertEnum(
    record.state,
    ['playing', 'paused', 'buffering', 'stopped', 'idle', 'unknown'],
    'query_anchor_state_invalid',
  );
  const result = {
    anchorId: assertIdentifier(record.anchorId, 'query_anchor_id_invalid'),
    observationId: assertIdentifier(record.observationId, 'query_anchor_observation_invalid'),
    canonicalPositionUs,
    clockMode: assertEnum(
      record.clockMode,
      ['direct', 'session', 'acoustic', 'predicted', 'manual', 'none'],
      'query_anchor_clock_mode_invalid',
    ),
    identityMode: assertEnum(
      record.identityMode,
      ['verified', 'matched', 'manual', 'conflict', 'unknown'],
      'query_anchor_identity_mode_invalid',
    ),
    clockConfidencePpm: assertInteger(record.clockConfidencePpm, 'query_anchor_clock_confidence_invalid', 0, 1_000_000),
    identityConfidencePpm: assertInteger(
      record.identityConfidencePpm,
      'query_anchor_identity_confidence_invalid',
      0,
      1_000_000,
    ),
    state,
    reasonCode: assertReason(record.reasonCode, 'query_anchor_reason_invalid', false),
  };
  if (contextState === 'ready') {
    if (result.canonicalPositionUs === null) fail('ready_context_requires_canonical_position');
    if (['conflict', 'unknown'].includes(result.identityMode)) fail('ready_context_identity_not_admitted');
    if (result.clockMode === 'none') fail('ready_context_clock_not_admitted');
  }
  return result;
}

function validateQueryPolicy(value) {
  const record = assertRecord(value, 'query_policy_invalid');
  assertExactKeys(
    record,
    [
      'allowedOperations',
      'allowedSpoilerModes',
      'maximumAnswerFacts',
      'maximumSegmentUs',
      'allowModelRealization',
    ],
    'query_policy_fields_invalid',
  );
  const allowedOperations = validateUniqueStrings(record.allowedOperations, 'query_policy_operations_invalid', {
    max: CORE_OPERATIONS.length,
    min: 1,
  });
  for (const operation of allowedOperations) {
    if (!CORE_OPERATIONS.includes(operation)) fail('query_policy_operation_unsupported', { operation });
  }
  const allowedSpoilerModes = validateUniqueStrings(record.allowedSpoilerModes, 'query_policy_spoilers_invalid', {
    max: SPOILER_MODES.length,
    min: 1,
  });
  for (const mode of allowedSpoilerModes) {
    if (!SPOILER_MODES.includes(mode)) fail('query_policy_spoiler_unsupported', { mode });
  }
  return {
    allowedOperations,
    allowedSpoilerModes,
    maximumAnswerFacts: assertInteger(record.maximumAnswerFacts, 'query_policy_maximum_facts_invalid', 1, 100),
    maximumSegmentUs: assertInteger(record.maximumSegmentUs, 'query_policy_maximum_segment_invalid', 1),
    allowModelRealization: assertBoolean(record.allowModelRealization, 'query_policy_model_invalid'),
  };
}

export function validateQueryContext(value) {
  const record = assertRecord(value, 'query_context_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'contextId',
      'sequence',
      'state',
      'reasonCode',
      'storyPackageId',
      'storyPackageDigest',
      'storyPackageRevision',
      'workId',
      'viewerProfileId',
      'viewerProfileDigest',
      'anchor',
      'queryPolicy',
      'accessReceiptRefs',
    ],
    'query_context_fields_invalid',
  );
  if (record.version !== QUERY_CONTEXT_VERSION) fail('query_context_version_invalid');
  const state = assertEnum(record.state, CONTEXT_STATES, 'query_context_state_invalid');
  const result = {
    version: record.version,
    contextId: assertString(record.contextId, 'query_context_id_invalid', {
      min: 78,
      max: 78,
      pattern: /^querycontext1_[0-9a-f]{64}$/,
    }),
    sequence: assertInteger(record.sequence, 'query_context_sequence_invalid', 1),
    state,
    reasonCode: assertReason(record.reasonCode, 'query_context_reason_invalid', state !== 'ready'),
    storyPackageId: assertIdentifier(record.storyPackageId, 'query_context_package_id_invalid'),
    storyPackageDigest: assertDigest(record.storyPackageDigest, 'query_context_package_digest_invalid'),
    storyPackageRevision: assertIdentifier(record.storyPackageRevision, 'query_context_package_revision_invalid'),
    workId: assertIdentifier(record.workId, 'query_context_work_id_invalid'),
    viewerProfileId: assertIdentifier(record.viewerProfileId, 'query_context_viewer_id_invalid'),
    viewerProfileDigest: assertDigest(record.viewerProfileDigest, 'query_context_viewer_digest_invalid'),
    anchor: validateAnchor(record.anchor, state),
    queryPolicy: validateQueryPolicy(record.queryPolicy),
    accessReceiptRefs: validateUniqueStrings(record.accessReceiptRefs, 'query_context_access_receipts_invalid', { max: 64 }),
  };
  if (contentId('querycontext1_', result, 'contextId') !== result.contextId) fail('query_context_identity_mismatch');
  return cloneOwned(result);
}

export function validateQueryInput(value) {
  const record = assertRecord(value, 'query_input_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'activationId',
      'operation',
      'question',
      'spoilerMode',
      'targetEntityIds',
      'maximumAnswerFacts',
      'allowProse',
    ],
    'query_input_fields_invalid',
  );
  if (record.version !== QUERY_INPUT_VERSION) fail('query_input_version_invalid');
  const operation = assertEnum(record.operation, CORE_OPERATIONS, 'query_input_operation_invalid');
  const question = record.question === null
    ? null
    : assertString(record.question, 'query_input_question_invalid', { max: 4096 });
  const targetEntityIds = validateUniqueStrings(record.targetEntityIds, 'query_input_targets_invalid', { max: 64 });
  if (operation === 'ask' && question === null) fail('free_form_question_required');
  if (operation === 'who_is_this' && targetEntityIds.length === 0) fail('identity_target_required');
  if (operation === 'where_am_i' && targetEntityIds.length !== 0) fail('where_am_i_target_forbidden');
  return cloneOwned({
    version: record.version,
    activationId: assertIdentifier(record.activationId, 'query_input_activation_invalid'),
    operation,
    question,
    spoilerMode: assertEnum(record.spoilerMode, SPOILER_MODES, 'query_input_spoiler_invalid'),
    targetEntityIds,
    maximumAnswerFacts: assertInteger(record.maximumAnswerFacts, 'query_input_maximum_facts_invalid', 1, 100),
    allowProse: assertBoolean(record.allowProse, 'query_input_allow_prose_invalid'),
  });
}

function assertContextReadyForQuery(context) {
  if (context.state !== 'ready') fail('query_context_not_ready', { state: context.state });
  if (context.anchor.canonicalPositionUs === null) fail('query_context_position_unavailable');
}

export function buildQueryIntent(contextValue, inputValue) {
  const context = validateQueryContext(contextValue);
  const input = validateQueryInput(inputValue);
  assertContextReadyForQuery(context);
  if (!context.queryPolicy.allowedOperations.includes(input.operation)) fail('query_operation_not_authorized');
  if (!context.queryPolicy.allowedSpoilerModes.includes(input.spoilerMode)) fail('query_spoiler_mode_not_authorized');
  if (input.maximumAnswerFacts > context.queryPolicy.maximumAnswerFacts) fail('query_fact_budget_exceeded');
  if (input.allowProse && !context.queryPolicy.allowModelRealization) fail('query_prose_not_authorized');

  const queryCore = {
    format: 'axm-aperture-query/1',
    viewer_profile_id: context.viewerProfileId,
    anchor_id: context.anchor.anchorId,
    operation: input.operation,
    question: input.question,
    spoiler_mode: input.spoilerMode,
    target_entity_ids: input.targetEntityIds,
    constraints: {
      maximum_answer_facts: input.maximumAnswerFacts,
      maximum_segment_us: context.queryPolicy.maximumSegmentUs,
      same_work_only: true,
      allow_model_realization: input.allowProse,
    },
  };
  const query = { query_id: contentId('query1_', queryCore), ...queryCore };
  const intentCore = {
    version: QUERY_INTENT_VERSION,
    contextId: context.contextId,
    contextSequence: context.sequence,
    storyPackageId: context.storyPackageId,
    storyPackageDigest: context.storyPackageDigest,
    storyPackageRevision: context.storyPackageRevision,
    viewerProfileId: context.viewerProfileId,
    viewerProfileDigest: context.viewerProfileDigest,
    anchorId: context.anchor.anchorId,
    anchorObservationId: context.anchor.observationId,
    activationId: input.activationId,
    query,
  };
  return cloneOwned({ intentId: contentId('queryintent1_', intentCore), ...intentCore });
}

export function validateQueryIntent(value, contextValue = null) {
  const record = assertRecord(value, 'query_intent_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'intentId',
      'contextId',
      'contextSequence',
      'storyPackageId',
      'storyPackageDigest',
      'storyPackageRevision',
      'viewerProfileId',
      'viewerProfileDigest',
      'anchorId',
      'anchorObservationId',
      'activationId',
      'query',
    ],
    'query_intent_fields_invalid',
  );
  if (record.version !== QUERY_INTENT_VERSION) fail('query_intent_version_invalid');
  const query = assertRecord(record.query, 'query_payload_invalid');
  assertExactKeys(
    query,
    [
      'format',
      'query_id',
      'viewer_profile_id',
      'anchor_id',
      'operation',
      'question',
      'spoiler_mode',
      'target_entity_ids',
      'constraints',
    ],
    'query_payload_fields_invalid',
  );
  if (query.format !== 'axm-aperture-query/1') fail('query_payload_format_invalid');
  const normalizedQuery = {
    query_id: assertString(query.query_id, 'query_id_invalid', { min: 71, max: 71, pattern: /^query1_[0-9a-f]{64}$/ }),
    format: query.format,
    viewer_profile_id: assertIdentifier(query.viewer_profile_id, 'query_viewer_invalid'),
    anchor_id: assertIdentifier(query.anchor_id, 'query_anchor_invalid'),
    operation: assertEnum(query.operation, CORE_OPERATIONS, 'query_operation_invalid'),
    question: query.question === null ? null : assertString(query.question, 'query_question_invalid', { max: 4096 }),
    spoiler_mode: assertEnum(query.spoiler_mode, SPOILER_MODES, 'query_spoiler_invalid'),
    target_entity_ids: validateUniqueStrings(query.target_entity_ids, 'query_targets_invalid', { max: 64 }),
    constraints: (() => {
      const constraints = assertRecord(query.constraints, 'query_constraints_invalid');
      assertExactKeys(
        constraints,
        ['maximum_answer_facts', 'maximum_segment_us', 'same_work_only', 'allow_model_realization'],
        'query_constraints_fields_invalid',
      );
      if (constraints.same_work_only !== true) fail('query_cross_work_forbidden');
      return {
        maximum_answer_facts: assertInteger(constraints.maximum_answer_facts, 'query_maximum_facts_invalid', 1, 100),
        maximum_segment_us: assertInteger(constraints.maximum_segment_us, 'query_maximum_segment_invalid', 1),
        same_work_only: true,
        allow_model_realization: assertBoolean(constraints.allow_model_realization, 'query_model_policy_invalid'),
      };
    })(),
  };
  if (contentId('query1_', normalizedQuery, 'query_id') !== normalizedQuery.query_id) fail('query_identity_mismatch');
  const result = {
    version: record.version,
    intentId: assertString(record.intentId, 'query_intent_id_invalid', {
      min: 77,
      max: 77,
      pattern: /^queryintent1_[0-9a-f]{64}$/,
    }),
    contextId: assertIdentifier(record.contextId, 'query_intent_context_invalid'),
    contextSequence: assertInteger(record.contextSequence, 'query_intent_context_sequence_invalid', 1),
    storyPackageId: assertIdentifier(record.storyPackageId, 'query_intent_package_id_invalid'),
    storyPackageDigest: assertDigest(record.storyPackageDigest, 'query_intent_package_digest_invalid'),
    storyPackageRevision: assertIdentifier(record.storyPackageRevision, 'query_intent_package_revision_invalid'),
    viewerProfileId: assertIdentifier(record.viewerProfileId, 'query_intent_viewer_id_invalid'),
    viewerProfileDigest: assertDigest(record.viewerProfileDigest, 'query_intent_viewer_digest_invalid'),
    anchorId: assertIdentifier(record.anchorId, 'query_intent_anchor_id_invalid'),
    anchorObservationId: assertIdentifier(record.anchorObservationId, 'query_intent_anchor_observation_invalid'),
    activationId: assertIdentifier(record.activationId, 'query_intent_activation_invalid'),
    query: normalizedQuery,
  };
  if (contentId('queryintent1_', result, 'intentId') !== result.intentId) fail('query_intent_identity_mismatch');
  if (
    result.query.viewer_profile_id !== result.viewerProfileId ||
    result.query.anchor_id !== result.anchorId
  ) fail('query_intent_payload_scope_mismatch');
  if (contextValue !== null) {
    const context = validateQueryContext(contextValue);
    if (
      result.contextId !== context.contextId ||
      result.contextSequence !== context.sequence ||
      result.storyPackageId !== context.storyPackageId ||
      result.storyPackageDigest !== context.storyPackageDigest ||
      result.storyPackageRevision !== context.storyPackageRevision ||
      result.viewerProfileId !== context.viewerProfileId ||
      result.viewerProfileDigest !== context.viewerProfileDigest ||
      result.anchorId !== context.anchor.anchorId ||
      result.anchorObservationId !== context.anchor.observationId
    ) fail('query_intent_context_scope_mismatch');
  }
  return cloneOwned(result);
}

export function validateQueryDelivery(value, intentValue) {
  const intent = validateQueryIntent(intentValue);
  const record = assertRecord(value, 'query_delivery_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(record, ['version', 'receiptId', 'intentId', 'status', 'reasonCode'], 'query_delivery_fields_invalid');
  if (record.version !== QUERY_DELIVERY_VERSION) fail('query_delivery_version_invalid');
  if (record.intentId !== intent.intentId) fail('query_delivery_intent_mismatch');
  const status = assertEnum(record.status, ['delivered', 'refused', 'unavailable'], 'query_delivery_status_invalid');
  return cloneOwned({
    version: record.version,
    receiptId: assertIdentifier(record.receiptId, 'query_delivery_receipt_invalid'),
    intentId: record.intentId,
    status,
    reasonCode: assertReason(record.reasonCode, 'query_delivery_reason_invalid', status !== 'delivered'),
  });
}

function validateAnswerFact(value, index) {
  const record = assertRecord(value, `answer_fact_invalid:${index}`);
  assertExactKeys(
    record,
    ['fact_id', 'role', 'provenance_refs', 'already_known', 'delivered'],
    `answer_fact_fields_invalid:${index}`,
  );
  return {
    fact_id: assertIdentifier(record.fact_id, `answer_fact_id_invalid:${index}`),
    role: assertEnum(record.role, FACT_ROLES, `answer_fact_role_invalid:${index}`),
    provenance_refs: validateUniqueStrings(record.provenance_refs, `answer_fact_provenance_invalid:${index}`, { min: 1, max: 64 }),
    already_known: assertBoolean(record.already_known, `answer_fact_known_invalid:${index}`),
    delivered: assertBoolean(record.delivered, `answer_fact_delivered_invalid:${index}`),
  };
}

export function validateAnswerPlan(value, intentValue, contextValue) {
  const intent = validateQueryIntent(intentValue, contextValue);
  const context = validateQueryContext(contextValue);
  const record = assertRecord(value, 'answer_plan_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'format',
      'plan_id',
      'query_id',
      'anchor_id',
      'story_package_id',
      'story_digest',
      'facts',
      'withheld_fact_ids',
      'spoiler_mode',
      'structured_fallback',
      'model_policy',
    ],
    'answer_plan_fields_invalid',
  );
  if (record.format !== 'axm-aperture-answer-plan/1') fail('answer_plan_format_invalid');
  if (record.query_id !== intent.query.query_id) fail('answer_plan_query_mismatch');
  if (record.anchor_id !== intent.anchorId) fail('answer_plan_anchor_mismatch');
  if (record.story_package_id !== context.storyPackageId) fail('answer_plan_package_mismatch');
  if (record.story_digest !== context.storyPackageDigest) fail('answer_plan_story_digest_mismatch');
  if (record.spoiler_mode !== intent.query.spoiler_mode) fail('answer_plan_spoiler_mode_mismatch');
  if (!Array.isArray(record.facts)) fail('answer_plan_facts_invalid');
  const facts = record.facts.map(validateAnswerFact);
  const factIds = facts.map((row) => row.fact_id);
  if (new Set(factIds).size !== factIds.length) fail('answer_plan_duplicate_fact');
  if (facts.length > intent.query.constraints.maximum_answer_facts) fail('answer_plan_fact_budget_exceeded');
  const withheld = validateUniqueStrings(record.withheld_fact_ids, 'answer_plan_withheld_invalid', { max: 10_000 });
  if (withheld.some((factId) => factIds.includes(factId))) fail('answer_plan_delivered_withheld_overlap');
  if (!Array.isArray(record.structured_fallback)) fail('answer_plan_fallback_invalid');
  const fallback = record.structured_fallback.map((entry, index) =>
    assertString(entry, `answer_plan_fallback_invalid:${index}`, { max: 20_000 }));
  const deliveredFacts = facts.filter((row) => row.delivered);
  if (fallback.length !== deliveredFacts.length) fail('answer_plan_fallback_length_mismatch');
  const modelPolicy = assertRecord(record.model_policy, 'answer_plan_model_policy_invalid');
  assertExactKeys(
    modelPolicy,
    ['allowed', 'must_preserve_fact_ids', 'may_add_facts', 'maximum_output_characters'],
    'answer_plan_model_policy_fields_invalid',
  );
  if (modelPolicy.must_preserve_fact_ids !== true || modelPolicy.may_add_facts !== false) {
    fail('answer_plan_model_authority_invalid');
  }
  const normalized = {
    format: record.format,
    plan_id: assertString(record.plan_id, 'answer_plan_id_invalid', {
      min: 76,
      max: 76,
      pattern: /^answerplan1_[0-9a-f]{64}$/,
    }),
    query_id: record.query_id,
    anchor_id: record.anchor_id,
    story_package_id: record.story_package_id,
    story_digest: assertDigest(record.story_digest, 'answer_plan_story_digest_invalid'),
    facts,
    withheld_fact_ids: withheld,
    spoiler_mode: assertEnum(record.spoiler_mode, SPOILER_MODES, 'answer_plan_spoiler_invalid'),
    structured_fallback: fallback,
    model_policy: {
      allowed: assertBoolean(modelPolicy.allowed, 'answer_plan_model_allowed_invalid'),
      must_preserve_fact_ids: true,
      may_add_facts: false,
      maximum_output_characters: assertInteger(
        modelPolicy.maximum_output_characters,
        'answer_plan_model_characters_invalid',
        1,
        20_000,
      ),
    },
  };
  if (normalized.model_policy.allowed && !intent.query.constraints.allow_model_realization) {
    fail('answer_plan_model_not_authorized');
  }
  if (contentId('answerplan1_', normalized, 'plan_id') !== normalized.plan_id) fail('answer_plan_identity_mismatch');
  return cloneOwned(normalized);
}

export function validatePlannerObservation(value, intentValue, contextValue) {
  const intent = validateQueryIntent(intentValue, contextValue);
  const record = assertRecord(value, 'planner_observation_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    ['version', 'observationId', 'intentId', 'queryId', 'state', 'reasonCode', 'plannerReceiptRef', 'plan'],
    'planner_observation_fields_invalid',
  );
  if (record.version !== PLANNER_OBSERVATION_VERSION) fail('planner_observation_version_invalid');
  if (record.intentId !== intent.intentId || record.queryId !== intent.query.query_id) {
    fail('planner_observation_request_mismatch');
  }
  const state = assertEnum(record.state, ['planned', 'refused', 'unresolved'], 'planner_observation_state_invalid');
  const plan = state === 'planned'
    ? validateAnswerPlan(record.plan, intent, contextValue)
    : (() => {
        if (record.plan !== null) fail('planner_refusal_plan_forbidden');
        return null;
      })();
  const core = {
    version: record.version,
    observationId: assertString(record.observationId, 'planner_observation_id_invalid', {
      min: 76,
      max: 76,
      pattern: /^plannerobs1_[0-9a-f]{64}$/,
    }),
    intentId: record.intentId,
    queryId: record.queryId,
    state,
    reasonCode: assertReason(record.reasonCode, 'planner_observation_reason_invalid', state !== 'planned'),
    plannerReceiptRef: assertIdentifier(record.plannerReceiptRef, 'planner_observation_receipt_invalid'),
    plan,
  };
  if (contentId('plannerobs1_', core, 'observationId') !== core.observationId) {
    fail('planner_observation_identity_mismatch');
  }
  return cloneOwned(core);
}

function validateStructuredAnswer(value, plan) {
  const record = assertRecord(value, 'structured_answer_invalid');
  assertExactKeys(
    record,
    ['format', 'planId', 'factIds', 'paragraphs', 'plainText'],
    'structured_answer_fields_invalid',
  );
  if (record.format !== 'axm-aperture-structured-answer/1') fail('structured_answer_format_invalid');
  if (record.planId !== plan.plan_id) fail('structured_answer_plan_mismatch');
  const expectedFactIds = plan.facts.filter((row) => row.delivered).map((row) => row.fact_id);
  const factIds = validateUniqueStrings(record.factIds, 'structured_answer_fact_ids_invalid', { max: 100 });
  if (canonicalJson(factIds) !== canonicalJson(expectedFactIds)) fail('structured_answer_fact_set_mismatch');
  if (!Array.isArray(record.paragraphs)) fail('structured_answer_paragraphs_invalid');
  const paragraphs = record.paragraphs.map((entry, index) =>
    assertString(entry, `structured_answer_paragraph_invalid:${index}`, { max: 20_000 }));
  if (canonicalJson(paragraphs) !== canonicalJson(plan.structured_fallback)) {
    fail('structured_answer_fallback_mismatch');
  }
  const plainText = assertString(record.plainText, 'structured_answer_plain_text_invalid', { max: 20_000 });
  if (plainText !== paragraphs.join(' ')) fail('structured_answer_plain_text_mismatch');
  return { format: record.format, planId: record.planId, factIds, paragraphs, plainText };
}

function validateProse(value, plan) {
  const record = assertRecord(value, 'prose_answer_invalid');
  assertExactKeys(record, ['text', 'factIds'], 'prose_answer_fields_invalid');
  const expectedFactIds = plan.facts.filter((row) => row.delivered).map((row) => row.fact_id);
  const factIds = validateUniqueStrings(record.factIds, 'prose_answer_fact_ids_invalid', { max: 100 });
  if (canonicalJson(factIds) !== canonicalJson(expectedFactIds)) fail('prose_answer_fact_set_mismatch');
  return {
    text: assertString(record.text, 'prose_answer_text_invalid', {
      max: plan.model_policy.maximum_output_characters,
    }),
    factIds,
  };
}

function validateKnowledgeEffectSummary(value, plan) {
  const record = assertRecord(value, 'knowledge_effect_summary_invalid');
  assertExactKeys(
    record,
    [
      'authority',
      'applied',
      'deliveredFactIds',
      'newlyExplainedFactIds',
      'alreadyKnownFactIds',
      'withheldCount',
      'projectedEvents',
      'effectReceiptRef',
    ],
    'knowledge_effect_summary_fields_invalid',
  );
  if (record.authority !== 'external_projection_only') fail('knowledge_effect_authority_invalid');
  if (record.applied !== false) fail('knowledge_effect_application_forbidden');
  const delivered = plan.facts.filter((row) => row.delivered);
  const expectedDelivered = delivered.map((row) => row.fact_id);
  const expectedNew = delivered.filter((row) => !row.already_known).map((row) => row.fact_id);
  const expectedKnown = delivered.filter((row) => row.already_known).map((row) => row.fact_id);
  const deliveredFactIds = validateUniqueStrings(record.deliveredFactIds, 'knowledge_delivered_fact_ids_invalid', { max: 100 });
  const newlyExplainedFactIds = validateUniqueStrings(record.newlyExplainedFactIds, 'knowledge_new_fact_ids_invalid', { max: 100 });
  const alreadyKnownFactIds = validateUniqueStrings(record.alreadyKnownFactIds, 'knowledge_known_fact_ids_invalid', { max: 100 });
  if (canonicalJson(deliveredFactIds) !== canonicalJson(expectedDelivered)) fail('knowledge_delivered_fact_set_mismatch');
  if (canonicalJson(newlyExplainedFactIds) !== canonicalJson(expectedNew)) fail('knowledge_new_fact_set_mismatch');
  if (canonicalJson(alreadyKnownFactIds) !== canonicalJson(expectedKnown)) fail('knowledge_known_fact_set_mismatch');
  if (record.withheldCount !== plan.withheld_fact_ids.length) fail('knowledge_withheld_count_mismatch');
  if (!Array.isArray(record.projectedEvents) || record.projectedEvents.length !== expectedNew.length) {
    fail('knowledge_projected_events_invalid');
  }
  const eventIds = new Set();
  const events = record.projectedEvents.map((entry, index) => {
    const event = assertRecord(entry, `knowledge_projected_event_invalid:${index}`);
    assertExactKeys(event, ['eventId', 'factId', 'state', 'applied'], `knowledge_projected_event_fields_invalid:${index}`);
    if (event.factId !== expectedNew[index]) fail('knowledge_projected_event_fact_mismatch', { index });
    if (event.state !== 'explained' || event.applied !== false) fail('knowledge_projected_event_authority_invalid', { index });
    const eventId = assertIdentifier(event.eventId, `knowledge_projected_event_id_invalid:${index}`);
    if (eventIds.has(eventId)) fail('knowledge_projected_event_duplicate');
    eventIds.add(eventId);
    return { eventId, factId: event.factId, state: event.state, applied: false };
  });
  return {
    authority: record.authority,
    applied: false,
    deliveredFactIds,
    newlyExplainedFactIds,
    alreadyKnownFactIds,
    withheldCount: record.withheldCount,
    projectedEvents: events,
    effectReceiptRef: assertIdentifier(record.effectReceiptRef, 'knowledge_effect_receipt_invalid'),
  };
}

export function validateAnswerObservation(value, plannerValue, intentValue, contextValue) {
  const planner = validatePlannerObservation(plannerValue, intentValue, contextValue);
  if (planner.state !== 'planned' || planner.plan === null) fail('answer_without_planned_result');
  const record = assertRecord(value, 'answer_observation_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'observationId',
      'intentId',
      'planId',
      'state',
      'reasonCode',
      'renderReceiptRef',
      'structured',
      'prose',
      'knowledgeEffectSummary',
    ],
    'answer_observation_fields_invalid',
  );
  if (record.version !== ANSWER_OBSERVATION_VERSION) fail('answer_observation_version_invalid');
  if (record.intentId !== planner.intentId || record.planId !== planner.plan.plan_id) {
    fail('answer_observation_plan_scope_mismatch');
  }
  const state = assertEnum(
    record.state,
    ['structured_only', 'validated_prose', 'prose_refused'],
    'answer_observation_state_invalid',
  );
  const structured = validateStructuredAnswer(record.structured, planner.plan);
  let prose = null;
  if (state === 'validated_prose') {
    if (!planner.plan.model_policy.allowed) fail('prose_not_allowed_by_plan');
    prose = validateProse(record.prose, planner.plan);
  } else if (record.prose !== null) {
    fail('prose_payload_forbidden_for_state');
  }
  const core = {
    version: record.version,
    observationId: assertString(record.observationId, 'answer_observation_id_invalid', {
      min: 75,
      max: 75,
      pattern: /^answerobs1_[0-9a-f]{64}$/,
    }),
    intentId: record.intentId,
    planId: record.planId,
    state,
    reasonCode: assertReason(record.reasonCode, 'answer_observation_reason_invalid', state === 'prose_refused'),
    renderReceiptRef: assertIdentifier(record.renderReceiptRef, 'answer_observation_receipt_invalid'),
    structured,
    prose,
    knowledgeEffectSummary: validateKnowledgeEffectSummary(record.knowledgeEffectSummary, planner.plan),
  };
  if (contentId('answerobs1_', core, 'observationId') !== core.observationId) {
    fail('answer_observation_identity_mismatch');
  }
  return cloneOwned(core);
}

export const PLANNER_MESSAGES = Object.freeze({
  'planner-refused': 'The deterministic planner refused this question.',
  'unresolved-evidence': 'The reviewed package does not contain enough admissible evidence for this question.',
  'anchor-unavailable': 'A reviewed canonical position is required before this question can be answered.',
  'continuity-boundary': 'The requested answer would cross the selected continuity.',
  'spoiler-mode-refused': 'The requested spoiler depth is outside the admitted policy.',
});

export function plannerMessage(reasonCode) {
  return PLANNER_MESSAGES[reasonCode] ?? 'The deterministic planner returned a bounded refusal.';
}
