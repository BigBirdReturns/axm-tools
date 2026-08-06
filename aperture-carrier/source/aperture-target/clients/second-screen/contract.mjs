import { createHash } from 'node:crypto';

export const PAIRING_PROJECTION_VERSION = 'axm-aperture-pairing-projection/1';
export const CONNECTION_OBSERVATION_VERSION = 'axm-aperture-connection-observation/1';
export const SECOND_SCREEN_SNAPSHOT_VERSION = 'axm-aperture-second-screen-snapshot/1';
export const SECOND_SCREEN_COACH_PROJECTION_VERSION = 'axm-aperture-coach-second-screen-projection/1';
export const VIEWPORT_OBSERVATION_VERSION = 'axm-aperture-second-screen-viewport/1';
export const SECOND_SCREEN_STATE_VERSION = 'axm-aperture-second-screen-state/1';
export const SECOND_SCREEN_INTENT_VERSION = 'axm-aperture-second-screen-intent/1';
export const SECOND_SCREEN_DELIVERY_VERSION = 'axm-aperture-second-screen-delivery/1';
export const SECOND_SCREEN_VIEW_VERSION = 'axm-aperture-second-screen-view/1';

export const SECOND_SCREEN_SURFACES = Object.freeze([
  'anchor',
  'context',
  'query',
  'selection',
  'provenance',
  'control',
]);

export const DATA_STATES = Object.freeze([
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

export const PAIRING_STATES = Object.freeze(['paired', 'unpaired', 'revoked', 'expired']);
export const CONNECTION_STATES = Object.freeze(['connected', 'disconnected', 'reconnecting', 'unavailable']);
export const INPUT_MODES = Object.freeze(['touch', 'keyboard', 'controller']);
export const REQUEST_KINDS = Object.freeze(['refresh', 'query', 'selection', 'control']);
export const AUTHORIZED_SCOPES = Object.freeze([
  'read:anchor',
  'read:context',
  'read:coach',
  'read:provenance',
  'request:query',
  'request:selection',
  'request:control',
]);

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:@/+~-]{0,255}$/;
const DIGEST = /^[0-9a-f]{64}$/;
const ISO_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/;
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

function assertString(value, code, { min = 1, max = 512, pattern = null, allowEmpty = false } = {}) {
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

function assertReason(value, code, required) {
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

function validateIdentifierArray(value, code, max = 64) {
  if (!Array.isArray(value) || value.length > max) fail(code);
  const output = value.map((entry, index) => assertIdentifier(entry, `${code}:${index}`));
  if (new Set(output).size !== output.length) fail(`${code}:duplicate`);
  return output;
}

function validateAuthorizedScopes(value, authState) {
  if (!Array.isArray(value) || value.length > AUTHORIZED_SCOPES.length) fail('pairing_scopes_invalid');
  const scopes = value.map((entry, index) => assertString(entry, `pairing_scope_invalid:${index}`, { max: 64 }));
  if (new Set(scopes).size !== scopes.length) fail('pairing_scope_duplicate');
  for (const scope of scopes) {
    if (!AUTHORIZED_SCOPES.includes(scope)) fail('pairing_scope_unsupported', { scope });
  }
  if (authState !== 'paired' && scopes.length !== 0) fail('unpaired_scope_authority_forbidden');
  if (authState === 'paired' && !scopes.includes('read:anchor')) fail('paired_anchor_scope_required');
  return scopes.sort();
}

export function canonicalJson(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
    .join(',')}}`;
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

export function validatePairingProjection(value) {
  const record = assertRecord(value, 'pairing_projection_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'pairingId',
      'pairingRevision',
      'deviceId',
      'deviceDigest',
      'deviceClass',
      'sharedDevice',
      'viewerProfileId',
      'viewerProfileDigest',
      'viewerSelectionReceiptRef',
      'authState',
      'authorizedScopes',
      'issuedAt',
      'expiresAt',
      'reasonCode',
      'accessReceiptRefs',
    ],
    'pairing_projection_fields_invalid',
  );
  if (record.version !== PAIRING_PROJECTION_VERSION) fail('pairing_projection_version_invalid');
  const authState = assertEnum(record.authState, PAIRING_STATES, 'pairing_auth_state_invalid');
  const sharedDevice = assertBoolean(record.sharedDevice, 'pairing_shared_device_invalid');
  const viewerProfileId = assertOptionalIdentifier(record.viewerProfileId, 'pairing_viewer_id_invalid');
  const viewerProfileDigest = assertOptionalDigest(record.viewerProfileDigest, 'pairing_viewer_digest_invalid');
  const viewerSelectionReceiptRef = assertOptionalIdentifier(
    record.viewerSelectionReceiptRef,
    'pairing_viewer_selection_receipt_invalid',
  );
  if (Boolean(viewerProfileId) !== Boolean(viewerProfileDigest)) fail('pairing_viewer_identity_partial');
  if (authState === 'paired' && (!viewerProfileId || !viewerProfileDigest || !viewerSelectionReceiptRef)) {
    fail(sharedDevice ? 'shared_device_explicit_viewer_required' : 'paired_viewer_scope_not_explicit');
  }
  if (authState !== 'paired' && (viewerProfileId || viewerProfileDigest || viewerSelectionReceiptRef)) {
    fail('nonpaired_viewer_scope_forbidden');
  }
  const issuedAt = assertInstant(record.issuedAt, 'pairing_issued_at_invalid');
  const expiresAt = assertInstant(record.expiresAt, 'pairing_expires_at_invalid');
  if (expiresAt <= issuedAt) fail('pairing_expiry_invalid');
  return cloneOwned({
    version: record.version,
    pairingId: assertIdentifier(record.pairingId, 'pairing_id_invalid'),
    pairingRevision: assertInteger(record.pairingRevision, 'pairing_revision_invalid', 1),
    deviceId: assertIdentifier(record.deviceId, 'pairing_device_id_invalid'),
    deviceDigest: assertDigest(record.deviceDigest, 'pairing_device_digest_invalid'),
    deviceClass: assertEnum(
      record.deviceClass,
      ['handset', 'tablet', 'television', 'console', 'desktop-companion'],
      'pairing_device_class_invalid',
    ),
    sharedDevice,
    viewerProfileId,
    viewerProfileDigest,
    viewerSelectionReceiptRef,
    authState,
    authorizedScopes: validateAuthorizedScopes(record.authorizedScopes, authState),
    issuedAt,
    expiresAt,
    reasonCode: assertReason(record.reasonCode, 'pairing_reason_invalid', authState !== 'paired'),
    accessReceiptRefs: validateIdentifierArray(record.accessReceiptRefs, 'pairing_access_receipts_invalid'),
  });
}

export function validateConnectionObservation(value, pairing) {
  const record = assertRecord(value, 'connection_observation_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'observationId',
      'connectionSessionId',
      'state',
      'pairingId',
      'pairingRevision',
      'deviceDigest',
      'viewerProfileDigest',
      'observedAt',
      'serverSequence',
      'acknowledgedIntentId',
      'reasonCode',
    ],
    'connection_observation_fields_invalid',
  );
  if (record.version !== CONNECTION_OBSERVATION_VERSION) fail('connection_observation_version_invalid');
  if (!pairing || pairing.authState !== 'paired') fail('connection_without_paired_scope');
  if (
    record.pairingId !== pairing.pairingId ||
    record.pairingRevision !== pairing.pairingRevision ||
    record.deviceDigest !== pairing.deviceDigest ||
    record.viewerProfileDigest !== pairing.viewerProfileDigest
  ) {
    fail('connection_scope_mismatch');
  }
  const state = assertEnum(record.state, CONNECTION_STATES, 'connection_state_invalid');
  return cloneOwned({
    version: record.version,
    observationId: assertIdentifier(record.observationId, 'connection_observation_id_invalid'),
    connectionSessionId: assertIdentifier(record.connectionSessionId, 'connection_session_id_invalid'),
    state,
    pairingId: record.pairingId,
    pairingRevision: record.pairingRevision,
    deviceDigest: record.deviceDigest,
    viewerProfileDigest: record.viewerProfileDigest,
    observedAt: assertInstant(record.observedAt, 'connection_observed_at_invalid'),
    serverSequence: assertInteger(record.serverSequence, 'connection_server_sequence_invalid'),
    acknowledgedIntentId: assertOptionalIdentifier(record.acknowledgedIntentId, 'connection_acknowledged_intent_invalid'),
    reasonCode: assertReason(record.reasonCode, 'connection_reason_invalid', state !== 'connected'),
  });
}

function validateSurface(value, surfaceId) {
  const record = assertRecord(value, `surface_record_invalid:${surfaceId}`);
  assertExactKeys(
    record,
    ['state', 'reasonCode', 'label', 'summary', 'coordinateRefs', 'accessReceiptRefs'],
    `surface_fields_invalid:${surfaceId}`,
  );
  const state = assertEnum(record.state, DATA_STATES, `surface_state_invalid:${surfaceId}`);
  return {
    state,
    reasonCode: assertReason(record.reasonCode, `surface_reason_invalid:${surfaceId}`, state !== 'ready'),
    label: assertString(record.label, `surface_label_invalid:${surfaceId}`, { max: 120 }),
    summary: assertString(record.summary, `surface_summary_invalid:${surfaceId}`, { max: 800, allowEmpty: true }),
    coordinateRefs: validateIdentifierArray(record.coordinateRefs, `surface_coordinate_refs_invalid:${surfaceId}`),
    accessReceiptRefs: validateIdentifierArray(record.accessReceiptRefs, `surface_access_refs_invalid:${surfaceId}`),
  };
}

function validateAnchor(value) {
  const record = assertRecord(value, 'anchor_invalid');
  assertExactKeys(record, ['anchorId', 'workId', 'positionId', 'confidence', 'source', 'observedAt'], 'anchor_fields_invalid');
  return {
    anchorId: assertIdentifier(record.anchorId, 'anchor_id_invalid'),
    workId: assertIdentifier(record.workId, 'anchor_work_id_invalid'),
    positionId: assertIdentifier(record.positionId, 'anchor_position_id_invalid'),
    confidence: assertEnum(
      record.confidence,
      ['exact', 'manual', 'predicted', 'acoustic', 'ambiguous', 'conflict'],
      'anchor_confidence_invalid',
    ),
    source: assertEnum(record.source, ['provider', 'manual', 'acoustic', 'prediction'], 'anchor_source_invalid'),
    observedAt: assertInstant(record.observedAt, 'anchor_observed_at_invalid'),
  };
}

export function validateCoachProjection(value, scope) {
  const record = assertRecord(value, 'coach_projection_invalid');
  assertExactKeys(
    record,
    [
      'version',
      'sourceVersion',
      'projectionId',
      'sourceDigest',
      'storyPackageDigest',
      'viewerProfileDigest',
      'status',
      'reasonCode',
      'cueId',
      'cueLabel',
      'presentationMode',
      'observationId',
      'pendingIntentIds',
      'deliveryReceiptIds',
    ],
    'coach_projection_fields_invalid',
  );
  if (record.version !== SECOND_SCREEN_COACH_PROJECTION_VERSION) fail('coach_projection_version_invalid');
  if (record.sourceVersion !== 'axm-aperture-coach-view/1') fail('coach_source_version_invalid');
  if (record.storyPackageDigest !== scope.storyPackageDigest) fail('coach_package_scope_mismatch');
  if (record.viewerProfileDigest !== scope.viewerProfileDigest) fail('coach_viewer_scope_mismatch');
  const status = assertEnum(record.status, DATA_STATES, 'coach_status_invalid');
  return cloneOwned({
    version: record.version,
    sourceVersion: record.sourceVersion,
    projectionId: assertIdentifier(record.projectionId, 'coach_projection_id_invalid'),
    sourceDigest: assertDigest(record.sourceDigest, 'coach_source_digest_invalid'),
    storyPackageDigest: assertDigest(record.storyPackageDigest, 'coach_story_package_digest_invalid'),
    viewerProfileDigest: assertDigest(record.viewerProfileDigest, 'coach_viewer_profile_digest_invalid'),
    status,
    reasonCode: assertReason(record.reasonCode, 'coach_reason_invalid', status !== 'ready'),
    cueId: assertIdentifier(record.cueId, 'coach_cue_id_invalid'),
    cueLabel: assertString(record.cueLabel, 'coach_cue_label_invalid', { max: 180 }),
    presentationMode: assertEnum(
      record.presentationMode,
      ['motion', 'decisive-frame', 'stale', 'unavailable'],
      'coach_presentation_mode_invalid',
    ),
    observationId: assertIdentifier(record.observationId, 'coach_observation_id_invalid'),
    pendingIntentIds: validateIdentifierArray(record.pendingIntentIds, 'coach_pending_intents_invalid'),
    deliveryReceiptIds: validateIdentifierArray(record.deliveryReceiptIds, 'coach_delivery_receipts_invalid'),
  });
}

export function validateSecondScreenSnapshot(value, pairing) {
  const record = assertRecord(value, 'second_screen_snapshot_invalid');
  assertNoSensitiveFields(record);
  assertExactKeys(
    record,
    [
      'version',
      'snapshotId',
      'sequence',
      'storyPackageId',
      'storyPackageDigest',
      'viewerProfileId',
      'viewerProfileDigest',
      'deviceId',
      'deviceDigest',
      'pairingId',
      'pairingRevision',
      'state',
      'reasonCode',
      'observedAt',
      'anchor',
      'surfaces',
      'coachProjection',
      'accessReceiptRefs',
    ],
    'second_screen_snapshot_fields_invalid',
  );
  if (record.version !== SECOND_SCREEN_SNAPSHOT_VERSION) fail('second_screen_snapshot_version_invalid');
  if (!pairing || pairing.authState !== 'paired') fail('snapshot_without_paired_scope');
  if (record.viewerProfileId !== pairing.viewerProfileId || record.viewerProfileDigest !== pairing.viewerProfileDigest) {
    fail('snapshot_viewer_scope_mismatch');
  }
  if (record.deviceId !== pairing.deviceId || record.deviceDigest !== pairing.deviceDigest) {
    fail('snapshot_device_scope_mismatch');
  }
  if (record.pairingId !== pairing.pairingId || record.pairingRevision !== pairing.pairingRevision) {
    fail('snapshot_pairing_scope_mismatch');
  }
  const state = assertEnum(record.state, DATA_STATES, 'snapshot_state_invalid');
  const surfaces = assertRecord(record.surfaces, 'snapshot_surfaces_invalid');
  assertExactKeys(surfaces, SECOND_SCREEN_SURFACES, 'snapshot_surface_set_invalid');
  const storyPackageDigest = assertDigest(record.storyPackageDigest, 'snapshot_story_package_digest_invalid');
  const viewerProfileDigest = assertDigest(record.viewerProfileDigest, 'snapshot_viewer_digest_invalid');
  return cloneOwned({
    version: record.version,
    snapshotId: assertIdentifier(record.snapshotId, 'snapshot_id_invalid'),
    sequence: assertInteger(record.sequence, 'snapshot_sequence_invalid'),
    storyPackageId: assertIdentifier(record.storyPackageId, 'snapshot_story_package_id_invalid'),
    storyPackageDigest,
    viewerProfileId: record.viewerProfileId,
    viewerProfileDigest,
    deviceId: record.deviceId,
    deviceDigest: record.deviceDigest,
    pairingId: record.pairingId,
    pairingRevision: record.pairingRevision,
    state,
    reasonCode: assertReason(record.reasonCode, 'snapshot_reason_invalid', state !== 'ready'),
    observedAt: assertInstant(record.observedAt, 'snapshot_observed_at_invalid'),
    anchor: validateAnchor(record.anchor),
    surfaces: Object.fromEntries(
      SECOND_SCREEN_SURFACES.map((surfaceId) => [surfaceId, validateSurface(surfaces[surfaceId], surfaceId)]),
    ),
    coachProjection: validateCoachProjection(record.coachProjection, { storyPackageDigest, viewerProfileDigest }),
    accessReceiptRefs: validateIdentifierArray(record.accessReceiptRefs, 'snapshot_access_receipts_invalid'),
  });
}

export function validateViewportObservation(value) {
  const record = assertRecord(value, 'viewport_observation_invalid');
  assertExactKeys(
    record,
    ['version', 'observationId', 'widthCssPx', 'heightCssPx', 'inputMode', 'observedAt'],
    'viewport_observation_fields_invalid',
  );
  if (record.version !== VIEWPORT_OBSERVATION_VERSION) fail('viewport_observation_version_invalid');
  return cloneOwned({
    version: record.version,
    observationId: assertIdentifier(record.observationId, 'viewport_observation_id_invalid'),
    widthCssPx: assertInteger(record.widthCssPx, 'viewport_width_invalid', 240, 8192),
    heightCssPx: assertInteger(record.heightCssPx, 'viewport_height_invalid', 240, 8192),
    inputMode: assertEnum(record.inputMode, INPUT_MODES, 'viewport_input_mode_invalid'),
    observedAt: assertInstant(record.observedAt, 'viewport_observed_at_invalid'),
  });
}

export function validateDeliveryReceipt(value) {
  const record = assertRecord(value, 'delivery_receipt_invalid');
  assertExactKeys(
    record,
    ['version', 'receiptId', 'intentId', 'connectionSessionId', 'status', 'reasonCode', 'deliveredAt'],
    'delivery_receipt_fields_invalid',
  );
  if (record.version !== SECOND_SCREEN_DELIVERY_VERSION) fail('delivery_receipt_version_invalid');
  const status = assertEnum(record.status, ['delivered', 'refused', 'failed'], 'delivery_status_invalid');
  return cloneOwned({
    version: record.version,
    receiptId: assertIdentifier(record.receiptId, 'delivery_receipt_id_invalid'),
    intentId: assertIdentifier(record.intentId, 'delivery_intent_id_invalid'),
    connectionSessionId: assertIdentifier(record.connectionSessionId, 'delivery_connection_session_invalid'),
    status,
    reasonCode: assertReason(record.reasonCode, 'delivery_reason_invalid', status !== 'delivered'),
    deliveredAt: assertInstant(record.deliveredAt, 'delivery_delivered_at_invalid'),
  });
}
