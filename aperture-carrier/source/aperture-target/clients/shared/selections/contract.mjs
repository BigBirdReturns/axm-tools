import { createHash } from 'node:crypto';

export const SELECTION_CONTEXT_VERSION = 'axm-aperture-selection-context/1';
export const SELECTION_RECEIPT_VERSION = 'axm-aperture-selection-receipt/1';
export const SELECTION_INTENT_VERSION = 'axm-aperture-selection-intent/1';
export const SELECTION_DELIVERY_VERSION = 'axm-aperture-selection-delivery/1';
export const ACTUATION_OBSERVATION_VERSION = 'axm-aperture-actuation-observation/1';
export const SELECTION_STATE_VERSION = 'axm-aperture-selection-state/1';
export const SELECTION_VIEW_VERSION = 'axm-aperture-selection-view/1';

export const SELECTION_MODES = Object.freeze(['bridge', 'drop', 'stay', 'barely_seen']);
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
export const SCORE_TERM_KEYS = Object.freeze([
  'uncovered',
  'bridge',
  'recognition',
  'question',
  'entry_cost',
  'repeat_penalty',
  'saturation_penalty',
]);

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:@/+~-]{0,255}$/;
const DIGEST = /^[0-9a-f]{64}$/;
const REASON = /^[a-z0-9][a-z0-9._:-]{0,127}$/;
const ISO_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/;
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

function assertOptionalDigest(value, code) {
  if (value === '') return '';
  return assertDigest(value, code);
}

function assertInstant(value, code) {
  return assertString(value, code, { max: 40, pattern: ISO_INSTANT });
}

function assertReason(value, code, required = false) {
  if (value === '' && !required) return '';
  return assertString(value, code, { max: 128, pattern: REASON });
}

function assertBoolean(value, code) {
  if (typeof value !== 'boolean') fail(code);
  return value;
}

function assertInteger(value, code, min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
  return value;
}

function assertEnum(value, allowed, code) {
  if (!allowed.includes(value)) fail(code, { value, allowed });
  return value;
}

function validateUniqueStrings(value, code, { min = 0, max = 128, digest = false } = {}) {
  if (!Array.isArray(value) || value.length < min || value.length > max) fail(code);
  const rows = value.map((entry, index) => digest
    ? assertDigest(entry, `${code}:${index}`)
    : assertIdentifier(entry, `${code}:${index}`));
  if (new Set(rows).size !== rows.length) fail(`${code}:duplicate`);
  return rows;
}

export function canonicalJson(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
}

export function sha256Json(value) {
  return createHash('sha256').update(canonicalJson(value)).digest('hex');
}

function freezeOwned(value) {
  if (value === null || typeof value !== 'object') return value;
  for (const child of Object.values(value)) freezeOwned(child);
  return Object.freeze(value);
}

export function cloneOwned(value) {
  return freezeOwned(structuredClone(value));
}

function validateAnchor(value) {
  const record = assertRecord(value, 'selection_anchor_invalid');
  assertExactKeys(
    record,
    [
      'anchorId',
      'anchorDigest',
      'sessionId',
      'workId',
      'storyPackageId',
      'canonicalPositionUs',
      'confidence',
      'exact',
      'observedAt',
    ],
    'selection_anchor_fields_invalid',
  );
  const confidence = assertEnum(
    record.confidence,
    ['exact', 'manual', 'predicted', 'acoustic', 'ambiguous', 'conflict'],
    'selection_anchor_confidence_invalid',
  );
  const exact = assertBoolean(record.exact, 'selection_anchor_exact_invalid');
  if (exact !== (confidence === 'exact')) fail('selection_anchor_exactness_conflict');
  return {
    anchorId: assertIdentifier(record.anchorId, 'selection_anchor_id_invalid'),
    anchorDigest: assertDigest(record.anchorDigest, 'selection_anchor_digest_invalid'),
    sessionId: assertIdentifier(record.sessionId, 'selection_anchor_session_invalid'),
    workId: assertIdentifier(record.workId, 'selection_anchor_work_invalid'),
    storyPackageId: assertIdentifier(record.storyPackageId, 'selection_anchor_package_invalid'),
    canonicalPositionUs: assertInteger(record.canonicalPositionUs, 'selection_anchor_position_invalid', 0),
    confidence,
    exact,
    observedAt: assertInstant(record.observedAt, 'selection_anchor_observed_at_invalid'),
  };
}

function validateProviderMapping(value) {
  const record = assertRecord(value, 'provider_mapping_invalid');
  assertExactKeys(
    record,
    ['state', 'providerEditionId', 'mapDigest', 'rateNumerator', 'rateDenominator', 'offsetUs', 'reasonCode'],
    'provider_mapping_fields_invalid',
  );
  const state = assertEnum(record.state, ['verified', 'unavailable', 'stale', 'conflict'], 'provider_mapping_state_invalid');
  const providerEditionId = assertOptionalIdentifier(record.providerEditionId, 'provider_edition_invalid');
  const mapDigest = assertOptionalDigest(record.mapDigest, 'provider_map_digest_invalid');
  const rateNumerator = assertInteger(record.rateNumerator, 'provider_rate_numerator_invalid', 0, 1_000_000_000);
  const rateDenominator = assertInteger(record.rateDenominator, 'provider_rate_denominator_invalid', 1, 1_000_000_000);
  const offsetUs = assertInteger(record.offsetUs, 'provider_offset_invalid');
  if (state === 'verified' && (!providerEditionId || !mapDigest || rateNumerator === 0)) {
    fail('verified_provider_mapping_incomplete');
  }
  if (state !== 'verified' && (providerEditionId || mapDigest || rateNumerator !== 0 || offsetUs !== 0)) {
    fail('nonverified_provider_mapping_authority_forbidden');
  }
  return {
    state,
    providerEditionId,
    mapDigest,
    rateNumerator,
    rateDenominator,
    offsetUs,
    reasonCode: assertReason(record.reasonCode, 'provider_mapping_reason_invalid', state !== 'verified'),
  };
}

function validateCapabilities(value) {
  const record = assertRecord(value, 'selection_capabilities_invalid');
  assertExactKeys(record, ['seek'], 'selection_capabilities_fields_invalid');
  return { seek: assertEnum(record.seek, ['exact', 'relative', 'none'], 'selection_seek_capability_invalid') };
}

export function validateSelectionContext(value) {
  const record = assertRecord(value, 'selection_context_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'contextId',
      'sequence',
      'storyPackageId',
      'storyPackageDigest',
      'workId',
      'continuityId',
      'viewerProfileId',
      'viewerProfileDigest',
      'state',
      'reasonCode',
      'anchor',
      'providerMapping',
      'capabilities',
      'maximumSegmentUs',
      'accessReceiptRefs',
    ],
    'selection_context_fields_invalid',
  );
  if (record.version !== SELECTION_CONTEXT_VERSION) fail('selection_context_version_invalid');
  const state = assertEnum(record.state, CONTEXT_STATES, 'selection_context_state_invalid');
  const anchor = validateAnchor(record.anchor);
  const storyPackageId = assertIdentifier(record.storyPackageId, 'selection_context_package_id_invalid');
  const workId = assertIdentifier(record.workId, 'selection_context_work_id_invalid');
  if (anchor.storyPackageId !== storyPackageId || anchor.workId !== workId) fail('selection_context_anchor_scope_mismatch');
  return cloneOwned({
    version: record.version,
    contextId: assertIdentifier(record.contextId, 'selection_context_id_invalid'),
    sequence: assertInteger(record.sequence, 'selection_context_sequence_invalid', 0),
    storyPackageId,
    storyPackageDigest: assertDigest(record.storyPackageDigest, 'selection_context_package_digest_invalid'),
    workId,
    continuityId: assertIdentifier(record.continuityId, 'selection_context_continuity_invalid'),
    viewerProfileId: assertIdentifier(record.viewerProfileId, 'selection_context_viewer_id_invalid'),
    viewerProfileDigest: assertDigest(record.viewerProfileDigest, 'selection_context_viewer_digest_invalid'),
    state,
    reasonCode: assertReason(record.reasonCode, 'selection_context_reason_invalid', state !== 'ready'),
    anchor,
    providerMapping: validateProviderMapping(record.providerMapping),
    capabilities: validateCapabilities(record.capabilities),
    maximumSegmentUs: assertInteger(record.maximumSegmentUs, 'selection_context_maximum_segment_invalid', 1),
    accessReceiptRefs: validateUniqueStrings(record.accessReceiptRefs, 'selection_context_access_receipts_invalid'),
  });
}

function validateScoreTerms(value, index) {
  const record = assertRecord(value, `selection_score_terms_invalid:${index}`);
  assertExactKeys(record, SCORE_TERM_KEYS, `selection_score_term_set_invalid:${index}`);
  return Object.fromEntries(SCORE_TERM_KEYS.map((key) => [
    key,
    assertInteger(record[key], `selection_score_term_invalid:${index}:${key}`, -1_000_000, 1_000_000),
  ]));
}

function validateCandidate(value, index, scope) {
  const record = assertRecord(value, `selection_candidate_invalid:${index}`);
  assertExactKeys(
    record,
    [
      'candidate_id',
      'work_id',
      'scene_id',
      'canonical_start_us',
      'canonical_end_us',
      'score',
      'score_terms',
    ],
    `selection_candidate_fields_invalid:${index}`,
  );
  const workId = assertIdentifier(record.work_id, `selection_candidate_work_invalid:${index}`);
  if (workId !== scope.workId) fail('selection_cross_work_candidate', { index, workId });
  const canonicalStartUs = assertInteger(record.canonical_start_us, `selection_candidate_start_invalid:${index}`, 0);
  const canonicalEndUs = assertInteger(record.canonical_end_us, `selection_candidate_end_invalid:${index}`, 1);
  if (canonicalEndUs <= canonicalStartUs) fail('selection_candidate_interval_invalid', { index });
  if (canonicalEndUs - canonicalStartUs > scope.maximumSegmentUs) fail('selection_candidate_duration_exceeds_context', { index });
  const scoreTerms = validateScoreTerms(record.score_terms, index);
  const calculated = SCORE_TERM_KEYS.reduce((sum, key) => sum + scoreTerms[key], 0);
  const score = assertInteger(record.score, `selection_candidate_score_invalid:${index}`);
  if (score !== calculated) fail('selection_candidate_score_mismatch', { index, score, calculated });
  return {
    candidate_id: assertIdentifier(record.candidate_id, `selection_candidate_id_invalid:${index}`),
    work_id: workId,
    scene_id: assertIdentifier(record.scene_id, `selection_candidate_scene_invalid:${index}`),
    canonical_start_us: canonicalStartUs,
    canonical_end_us: canonicalEndUs,
    score,
    score_terms: scoreTerms,
  };
}

function compareCandidates(left, right) {
  if (left.score !== right.score) return right.score - left.score;
  if (left.canonical_start_us !== right.canonical_start_us) return left.canonical_start_us - right.canonical_start_us;
  return left.scene_id < right.scene_id ? -1 : left.scene_id > right.scene_id ? 1 : 0;
}

export function validateSelectionReceipt(value, contextValue) {
  const context = validateSelectionContext(contextValue);
  const record = assertRecord(value, 'selection_receipt_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'format',
      'selection_id',
      'policy_id',
      'policy_version',
      'viewer_id',
      'work_id',
      'continuity_id',
      'story_package_id',
      'mode',
      'candidate_set_digest',
      'candidates',
      'selected_candidate_id',
      'reason_codes',
      'input_projection_digests',
      'same_work_only',
      'authority',
    ],
    'selection_receipt_fields_invalid',
  );
  if (record.format !== SELECTION_RECEIPT_VERSION) fail('selection_receipt_version_invalid');
  if (record.authority !== 'selection_receipt_only') fail('selection_receipt_authority_invalid');
  if (record.same_work_only !== true) fail('selection_same_work_proof_required');
  if (
    record.viewer_id !== context.viewerProfileId ||
    record.work_id !== context.workId ||
    record.continuity_id !== context.continuityId ||
    record.story_package_id !== context.storyPackageId
  ) fail('selection_receipt_scope_mismatch');
  const candidatesRaw = record.candidates;
  if (!Array.isArray(candidatesRaw) || candidatesRaw.length < 1 || candidatesRaw.length > 100_000) {
    fail('selection_candidate_denominator_invalid');
  }
  const candidates = candidatesRaw.map((candidate, index) => validateCandidate(candidate, index, context));
  const candidateIds = candidates.map((row) => row.candidate_id);
  if (new Set(candidateIds).size !== candidateIds.length) fail('selection_candidate_identity_duplicate');
  const candidateSetDigest = assertDigest(record.candidate_set_digest, 'selection_candidate_set_digest_invalid');
  if (candidateSetDigest !== sha256Json(candidates)) fail('selection_candidate_set_digest_mismatch');
  const selectedCandidateId = assertIdentifier(record.selected_candidate_id, 'selection_selected_candidate_invalid');
  const selectedRows = candidates.filter((row) => row.candidate_id === selectedCandidateId);
  if (selectedRows.length !== 1) fail('selection_selected_candidate_missing_or_duplicate');
  const ranked = [...candidates].sort(compareCandidates);
  if (ranked[0].candidate_id !== selectedCandidateId) fail('selection_selected_candidate_not_rank_one');
  const inputProjectionDigests = validateUniqueStrings(
    record.input_projection_digests,
    'selection_input_projection_digests_invalid',
    { min: 1, max: 32, digest: true },
  );
  if (!inputProjectionDigests.includes(context.storyPackageDigest) || !inputProjectionDigests.includes(context.anchor.anchorDigest)) {
    fail('selection_input_projection_scope_incomplete');
  }
  const core = {
    format: record.format,
    policy_id: assertIdentifier(record.policy_id, 'selection_policy_id_invalid'),
    policy_version: assertIdentifier(record.policy_version, 'selection_policy_version_invalid'),
    viewer_id: record.viewer_id,
    work_id: record.work_id,
    continuity_id: record.continuity_id,
    story_package_id: record.story_package_id,
    mode: assertEnum(record.mode, SELECTION_MODES, 'selection_mode_invalid'),
    candidate_set_digest: candidateSetDigest,
    candidates,
    selected_candidate_id: selectedCandidateId,
    reason_codes: validateUniqueStrings(record.reason_codes, 'selection_reason_codes_invalid', { min: 1, max: 32 }),
    input_projection_digests: inputProjectionDigests,
    same_work_only: true,
    authority: record.authority,
  };
  const selectionId = assertString(record.selection_id, 'selection_id_invalid', {
    min: 75,
    max: 75,
    pattern: /^selection1_[0-9a-f]{64}$/,
  });
  if (selectionId !== `selection1_${sha256Json(core)}`) fail('selection_id_content_mismatch');
  return cloneOwned({ selection_id: selectionId, ...core });
}

function mappedProviderPosition(candidate, mapping) {
  const numerator = BigInt(mapping.rateNumerator);
  const denominator = BigInt(mapping.rateDenominator);
  const canonical = BigInt(candidate.canonical_start_us);
  const offset = BigInt(mapping.offsetUs);
  const product = canonical * numerator;
  if (product % denominator !== 0n) fail('provider_mapping_nonintegral_target');
  const target = product / denominator + offset;
  if (target < 0n || target > BigInt(Number.MAX_SAFE_INTEGER)) fail('provider_mapping_target_out_of_range');
  return Number(target);
}

export function buildSelectionActivation(contextValue, receiptValue) {
  const context = validateSelectionContext(contextValue);
  const receipt = validateSelectionReceipt(receiptValue, context);
  if (context.state !== 'ready') fail('selection_activation_context_not_ready');
  const candidate = receipt.candidates.find((row) => row.candidate_id === receipt.selected_candidate_id);
  const base = {
    version: SELECTION_INTENT_VERSION,
    selectionId: receipt.selection_id,
    contextId: context.contextId,
    storyPackageId: context.storyPackageId,
    storyPackageDigest: context.storyPackageDigest,
    workId: context.workId,
    continuityId: context.continuityId,
    viewerProfileId: context.viewerProfileId,
    viewerProfileDigest: context.viewerProfileDigest,
    anchorId: context.anchor.anchorId,
    anchorDigest: context.anchor.anchorDigest,
    sessionId: context.anchor.sessionId,
    candidateId: candidate.candidate_id,
    sceneId: candidate.scene_id,
    canonicalStartUs: candidate.canonical_start_us,
    canonicalEndUs: candidate.canonical_end_us,
    autoplay: false,
    authority: 'request_intent_only',
  };
  if (context.anchor.exact && context.providerMapping.state === 'verified' && context.capabilities.seek === 'exact') {
    const body = {
      ...base,
      kind: 'exact_seek_request',
      providerEditionId: context.providerMapping.providerEditionId,
      providerMapDigest: context.providerMapping.mapDigest,
      providerPositionUs: mappedProviderPosition(candidate, context.providerMapping),
      fallbackKind: 'none',
    };
    return cloneOwned({ intentId: `selectionintent1_${sha256Json(body)}`, ...body });
  }
  const providerAvailable = context.providerMapping.state === 'verified';
  const body = {
    ...base,
    kind: 'timestamp_fallback',
    providerEditionId: providerAvailable ? context.providerMapping.providerEditionId : '',
    providerMapDigest: providerAvailable ? context.providerMapping.mapDigest : '',
    providerPositionUs: providerAvailable ? mappedProviderPosition(candidate, context.providerMapping) : null,
    fallbackKind: providerAvailable ? 'provider_timestamp' : 'canonical_timestamp',
  };
  return cloneOwned({ intentId: `selectionintent1_${sha256Json(body)}`, ...body });
}

export function validateSelectionIntent(value, contextValue, receiptValue) {
  const expected = buildSelectionActivation(contextValue, receiptValue);
  if (canonicalJson(value) !== canonicalJson(expected)) fail('selection_intent_identity_mismatch');
  return expected;
}

export function validateSelectionDelivery(value, intentValue) {
  const intent = cloneOwned(intentValue);
  const record = assertRecord(value, 'selection_delivery_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    ['version', 'receiptId', 'intentId', 'status', 'reasonCode', 'deliveredAt', 'authority'],
    'selection_delivery_fields_invalid',
  );
  if (record.version !== SELECTION_DELIVERY_VERSION) fail('selection_delivery_version_invalid');
  if (record.intentId !== intent.intentId) fail('selection_delivery_intent_mismatch');
  if (record.authority !== 'transport_receipt_only') fail('selection_delivery_authority_invalid');
  const status = assertEnum(record.status, ['delivered', 'refused', 'failed'], 'selection_delivery_status_invalid');
  return cloneOwned({
    version: record.version,
    receiptId: assertIdentifier(record.receiptId, 'selection_delivery_receipt_id_invalid'),
    intentId: record.intentId,
    status,
    reasonCode: assertReason(record.reasonCode, 'selection_delivery_reason_invalid', status !== 'delivered'),
    deliveredAt: assertInstant(record.deliveredAt, 'selection_delivery_time_invalid'),
    authority: record.authority,
  });
}

export function validateActuationObservation(value, intentValue, contextValue) {
  const context = validateSelectionContext(contextValue);
  const intent = cloneOwned(intentValue);
  const record = assertRecord(value, 'actuation_observation_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'observationId',
      'intentId',
      'anchorId',
      'anchorDigest',
      'sessionId',
      'status',
      'reasonCode',
      'observedProviderPositionUs',
      'observedCanonicalPositionUs',
      'positionToleranceUs',
      'authority',
    ],
    'actuation_observation_fields_invalid',
  );
  if (record.version !== ACTUATION_OBSERVATION_VERSION) fail('actuation_observation_version_invalid');
  if (record.intentId !== intent.intentId) fail('actuation_observation_intent_mismatch');
  if (
    record.anchorId !== context.anchor.anchorId ||
    record.anchorDigest !== context.anchor.anchorDigest ||
    record.sessionId !== context.anchor.sessionId
  ) fail('actuation_observation_anchor_scope_mismatch');
  if (record.authority !== 'external_ap212_observation_only') fail('actuation_observation_authority_invalid');
  const status = assertEnum(record.status, ['verified', 'refused', 'failed'], 'actuation_observation_status_invalid');
  const observedProviderPositionUs = record.observedProviderPositionUs === null
    ? null
    : assertInteger(record.observedProviderPositionUs, 'actuation_observed_provider_position_invalid', 0);
  const observedCanonicalPositionUs = record.observedCanonicalPositionUs === null
    ? null
    : assertInteger(record.observedCanonicalPositionUs, 'actuation_observed_canonical_position_invalid', 0);
  const tolerance = assertInteger(record.positionToleranceUs, 'actuation_position_tolerance_invalid', 0, 30_000_000);
  if (intent.kind !== 'exact_seek_request' && status === 'verified') fail('timestamp_fallback_cannot_be_verified_actuation');
  if (status === 'verified') {
    if (observedCanonicalPositionUs === null) fail('verified_actuation_position_required');
    if (Math.abs(observedCanonicalPositionUs - intent.canonicalStartUs) > tolerance) {
      fail('verified_actuation_outside_tolerance');
    }
    if (observedProviderPositionUs === null || Math.abs(observedProviderPositionUs - intent.providerPositionUs) > tolerance) {
      fail('verified_provider_position_outside_tolerance');
    }
  }
  return cloneOwned({
    version: record.version,
    observationId: assertIdentifier(record.observationId, 'actuation_observation_id_invalid'),
    intentId: record.intentId,
    anchorId: record.anchorId,
    anchorDigest: record.anchorDigest,
    sessionId: record.sessionId,
    status,
    reasonCode: assertReason(record.reasonCode, 'actuation_observation_reason_invalid', status !== 'verified'),
    observedProviderPositionUs,
    observedCanonicalPositionUs,
    positionToleranceUs: tolerance,
    authority: record.authority,
  });
}

export function selectedCandidate(receipt) {
  return receipt.candidates.find((row) => row.candidate_id === receipt.selected_candidate_id);
}
