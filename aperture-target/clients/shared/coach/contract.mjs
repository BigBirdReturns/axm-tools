import { createHash } from 'node:crypto';

export const COACH_PROGRAM_VERSION = 'axm-aperture-coach-program/1';
export const COACH_OBSERVATION_VERSION = 'axm-aperture-playback-observation/1';
export const COACH_STATE_VERSION = 'axm-aperture-coach-state/1';
export const COACH_INTENT_VERSION = 'axm-aperture-playback-intent/1';
export const COACH_DELIVERY_VERSION = 'axm-aperture-intent-delivery/1';

const DIGEST_RE = /^[a-f0-9]{64}$/;
const ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$/;
const OBSERVATION_STATUSES = new Set([
  'playing',
  'paused',
  'buffering',
  'ended',
  'stopped',
  'unavailable',
]);
const SUMMARY_MODES = new Set(['structured', 'bounded-prose', 'withheld']);

function fail(code, detail = '') {
  const suffix = detail ? `:${detail}` : '';
  throw new Error(`${code}${suffix}`);
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function freezeTree(value) {
  if (value === null || typeof value !== 'object' || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) freezeTree(child);
  return Object.freeze(value);
}

function assertRecord(value, code) {
  if (!isRecord(value)) fail(code);
  return value;
}

function assertClosed(record, allowed, code) {
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) fail(code, key);
  }
}

function assertString(value, code, { nonEmpty = true, maxLength = 8_192 } = {}) {
  if (
    typeof value !== 'string' ||
    (nonEmpty && value.length === 0) ||
    value.length > maxLength
  ) {
    fail(code);
  }
  return value;
}

function assertId(value, code) {
  assertString(value, code);
  if (!ID_RE.test(value)) fail(code, value);
  return value;
}

function assertDigest(value, code) {
  assertString(value, code);
  if (!DIGEST_RE.test(value)) fail(code, value);
  return value;
}

function assertBoolean(value, code) {
  if (typeof value !== 'boolean') fail(code);
  return value;
}

function assertFiniteNumber(value, code, { min = -Infinity, max = Infinity } = {}) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) {
    fail(code, String(value));
  }
  return value;
}

function assertInteger(value, code, bounds = {}) {
  assertFiniteNumber(value, code, bounds);
  if (!Number.isInteger(value)) fail(code, String(value));
  return value;
}

function assertStringArray(value, code, { maxLength = 2_048 } = {}) {
  if (!Array.isArray(value) || value.length > maxLength) fail(code);
  const result = value.map((entry, index) => assertId(entry, `${code}[${index}]`));
  if (new Set(result).size !== result.length) fail(`${code}_duplicate`);
  return result;
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!isRecord(value)) return value;
  const output = {};
  for (const key of Object.keys(value).sort()) output[key] = canonicalize(value[key]);
  return output;
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function sha256Json(value) {
  return createHash('sha256').update(canonicalJson(value)).digest('hex');
}

function validateTimedPosition(value, packageDigest) {
  const record = assertRecord(value, 'timed_position_not_object');
  assertClosed(
    record,
    new Set([
      'positionId',
      'workId',
      'packageDigest',
      'startMs',
      'endMs',
      'canonicalStart',
      'canonicalEnd',
    ]),
    'timed_position_unknown_field',
  );
  const result = {
    positionId: assertId(record.positionId, 'timed_position_id_invalid'),
    workId: assertId(record.workId, 'timed_position_work_invalid'),
    packageDigest: assertDigest(record.packageDigest, 'timed_position_package_digest_invalid'),
    startMs: assertInteger(record.startMs, 'timed_position_start_invalid', { min: 0 }),
    endMs: assertInteger(record.endMs, 'timed_position_end_invalid', { min: 1 }),
    canonicalStart: assertString(record.canonicalStart, 'timed_position_canonical_start_invalid', { maxLength: 512 }),
    canonicalEnd: assertString(record.canonicalEnd, 'timed_position_canonical_end_invalid', { maxLength: 512 }),
  };
  if (result.packageDigest !== packageDigest) fail('timed_position_package_digest_mismatch');
  if (result.endMs <= result.startMs) fail('timed_position_interval_invalid');
  return result;
}

function validateAnswerPlan(value, packageDigest, positionId) {
  const record = assertRecord(value, 'answer_plan_not_object');
  assertClosed(
    record,
    new Set([
      'planId',
      'packageDigest',
      'positionId',
      'factIds',
      'summaryMode',
      'effectSummary',
      'receiptId',
    ]),
    'answer_plan_unknown_field',
  );
  const result = {
    planId: assertId(record.planId, 'answer_plan_id_invalid'),
    packageDigest: assertDigest(record.packageDigest, 'answer_plan_package_digest_invalid'),
    positionId: assertId(record.positionId, 'answer_plan_position_invalid'),
    factIds: assertStringArray(record.factIds, 'answer_plan_fact_ids_invalid'),
    summaryMode: assertString(record.summaryMode, 'answer_plan_summary_mode_invalid'),
    effectSummary: assertString(record.effectSummary, 'answer_plan_effect_summary_invalid', {
      nonEmpty: false,
      maxLength: 4_096,
    }),
    receiptId: assertId(record.receiptId, 'answer_plan_receipt_invalid'),
  };
  if (result.packageDigest !== packageDigest) fail('answer_plan_package_digest_mismatch');
  if (result.positionId !== positionId) fail('answer_plan_position_mismatch');
  if (!SUMMARY_MODES.has(result.summaryMode)) fail('answer_plan_summary_mode_unsupported');
  return result;
}

function validateCue(value, index, timedPosition, factIds) {
  const record = assertRecord(value, `cue_not_object[${index}]`);
  assertClosed(
    record,
    new Set([
      'cueId',
      'label',
      'atMs',
      'holdMs',
      'decisive',
      'explanation',
      'frameRef',
      'diagramRef',
      'factIds',
    ]),
    `cue_unknown_field[${index}]`,
  );
  const result = {
    cueId: assertId(record.cueId, `cue_id_invalid[${index}]`),
    label: assertString(record.label, `cue_label_invalid[${index}]`, { maxLength: 256 }),
    atMs: assertInteger(record.atMs, `cue_at_invalid[${index}]`, {
      min: timedPosition.startMs,
      max: timedPosition.endMs,
    }),
    holdMs: assertInteger(record.holdMs, `cue_hold_invalid[${index}]`, { min: 0, max: 60_000 }),
    decisive: assertBoolean(record.decisive, `cue_decisive_invalid[${index}]`),
    explanation: assertString(record.explanation, `cue_explanation_invalid[${index}]`, { maxLength: 4_096 }),
    frameRef: assertId(record.frameRef, `cue_frame_ref_invalid[${index}]`),
    diagramRef: assertId(record.diagramRef, `cue_diagram_ref_invalid[${index}]`),
    factIds: assertStringArray(record.factIds, `cue_fact_ids_invalid[${index}]`),
  };
  for (const factId of result.factIds) {
    if (!factIds.has(factId)) fail(`cue_fact_not_in_answer_plan[${index}]`, factId);
  }
  return result;
}

function validateAutoHold(value, cues) {
  const record = assertRecord(value, 'auto_hold_not_object');
  assertClosed(record, new Set(['enabled', 'cueIds']), 'auto_hold_unknown_field');
  const result = {
    enabled: assertBoolean(record.enabled, 'auto_hold_enabled_invalid'),
    cueIds: assertStringArray(record.cueIds, 'auto_hold_cue_ids_invalid'),
  };
  const cueById = new Map(cues.map((cue) => [cue.cueId, cue]));
  for (const cueId of result.cueIds) {
    const cue = cueById.get(cueId);
    if (!cue) fail('auto_hold_unknown_cue', cueId);
    if (!cue.decisive) fail('auto_hold_non_decisive_cue', cueId);
  }
  return result;
}

export function validateCoachProgram(value) {
  const record = assertRecord(value, 'coach_program_not_object');
  assertClosed(
    record,
    new Set([
      'version',
      'programId',
      'storyPackageId',
      'storyPackageDigest',
      'viewerProfileId',
      'viewerProfileDigest',
      'timedPosition',
      'answerPlan',
      'cues',
      'frameRate',
      'allowedRates',
      'autoHold',
    ]),
    'coach_program_unknown_field',
  );
  if (record.version !== COACH_PROGRAM_VERSION) fail('coach_program_version_unsupported');
  const storyPackageDigest = assertDigest(
    record.storyPackageDigest,
    'coach_program_package_digest_invalid',
  );
  const timedPosition = validateTimedPosition(record.timedPosition, storyPackageDigest);
  const answerPlan = validateAnswerPlan(
    record.answerPlan,
    storyPackageDigest,
    timedPosition.positionId,
  );
  if (!Array.isArray(record.cues) || record.cues.length < 2 || record.cues.length > 512) {
    fail('coach_program_cues_invalid');
  }
  const answerFactIds = new Set(answerPlan.factIds);
  const cues = record.cues.map((cue, index) =>
    validateCue(cue, index, timedPosition, answerFactIds),
  );
  if (cues[0].atMs !== timedPosition.startMs) fail('coach_program_first_cue_not_at_start');
  const cueIds = new Set();
  let previousAt = -1;
  for (const cue of cues) {
    if (cueIds.has(cue.cueId)) fail('coach_program_duplicate_cue', cue.cueId);
    cueIds.add(cue.cueId);
    if (cue.atMs <= previousAt) fail('coach_program_cue_order_invalid', cue.cueId);
    previousAt = cue.atMs;
  }
  const frameRate = assertFiniteNumber(record.frameRate, 'coach_program_frame_rate_invalid', {
    min: 1,
    max: 240,
  });
  if (!Array.isArray(record.allowedRates) || record.allowedRates.length === 0) {
    fail('coach_program_allowed_rates_invalid');
  }
  const allowedRates = record.allowedRates.map((rate, index) =>
    assertFiniteNumber(rate, `coach_program_allowed_rate_invalid[${index}]`, {
      min: 0.1,
      max: 4,
    }),
  );
  if (new Set(allowedRates).size !== allowedRates.length) fail('coach_program_duplicate_rate');
  const result = {
    version: COACH_PROGRAM_VERSION,
    programId: assertId(record.programId, 'coach_program_id_invalid'),
    storyPackageId: assertId(record.storyPackageId, 'coach_program_package_id_invalid'),
    storyPackageDigest,
    viewerProfileId: assertId(record.viewerProfileId, 'coach_program_viewer_id_invalid'),
    viewerProfileDigest: assertDigest(
      record.viewerProfileDigest,
      'coach_program_viewer_digest_invalid',
    ),
    timedPosition,
    answerPlan,
    cues,
    frameRate,
    allowedRates,
    autoHold: validateAutoHold(record.autoHold, cues),
  };
  return freezeTree(result);
}

export function validatePlaybackObservation(value, program) {
  const record = assertRecord(value, 'observation_not_object');
  assertClosed(
    record,
    new Set([
      'version',
      'observationId',
      'sessionId',
      'packageDigest',
      'viewerProfileDigest',
      'positionId',
      'status',
      'positionMs',
      'durationMs',
      'rate',
      'paused',
      'connected',
      'observedAt',
    ]),
    'observation_unknown_field',
  );
  if (record.version !== COACH_OBSERVATION_VERSION) fail('observation_version_unsupported');
  const result = {
    version: COACH_OBSERVATION_VERSION,
    observationId: assertId(record.observationId, 'observation_id_invalid'),
    sessionId: assertId(record.sessionId, 'observation_session_id_invalid'),
    packageDigest: assertDigest(record.packageDigest, 'observation_package_digest_invalid'),
    viewerProfileDigest: assertDigest(
      record.viewerProfileDigest,
      'observation_viewer_digest_invalid',
    ),
    positionId: assertId(record.positionId, 'observation_position_id_invalid'),
    status: assertString(record.status, 'observation_status_invalid'),
    positionMs: assertInteger(record.positionMs, 'observation_position_ms_invalid', { min: 0 }),
    durationMs: assertInteger(record.durationMs, 'observation_duration_ms_invalid', { min: 1 }),
    rate: assertFiniteNumber(record.rate, 'observation_rate_invalid', { min: 0.1, max: 4 }),
    paused: assertBoolean(record.paused, 'observation_paused_invalid'),
    connected: assertBoolean(record.connected, 'observation_connected_invalid'),
    observedAt: assertString(record.observedAt, 'observation_observed_at_invalid'),
  };
  if (!OBSERVATION_STATUSES.has(result.status)) fail('observation_status_unsupported');
  if (Number.isNaN(Date.parse(result.observedAt))) fail('observation_observed_at_invalid');
  if (result.positionMs > result.durationMs) fail('observation_position_out_of_range');
  if (!result.connected && result.status !== 'unavailable') {
    fail('observation_disconnected_status_invalid');
  }
  if (result.status === 'playing' && result.paused) fail('observation_playing_paused_conflict');
  if (result.status === 'paused' && !result.paused) fail('observation_paused_flag_conflict');
  if (new Set(['ended', 'stopped', 'unavailable']).has(result.status) && !result.paused) {
    fail('observation_terminal_paused_conflict');
  }
  if (result.packageDigest !== program.storyPackageDigest) fail('observation_package_mismatch');
  if (result.viewerProfileDigest !== program.viewerProfileDigest) {
    fail('observation_viewer_mismatch');
  }
  if (result.positionId !== program.timedPosition.positionId) fail('observation_position_mismatch');
  const declaredDuration = program.timedPosition.endMs - program.timedPosition.startMs;
  if (result.durationMs !== declaredDuration) fail('observation_duration_mismatch');
  return freezeTree(result);
}

export function validateIntentDelivery(value) {
  const record = assertRecord(value, 'intent_delivery_not_object');
  assertClosed(
    record,
    new Set(['version', 'receiptId', 'intentId', 'status', 'deliveredAt', 'reasonCode']),
    'intent_delivery_unknown_field',
  );
  if (record.version !== COACH_DELIVERY_VERSION) fail('intent_delivery_version_unsupported');
  const status = assertString(record.status, 'intent_delivery_status_invalid');
  if (!new Set(['delivered', 'refused', 'failed']).has(status)) {
    fail('intent_delivery_status_unsupported');
  }
  const deliveredAt = assertString(record.deliveredAt, 'intent_delivery_time_invalid');
  if (Number.isNaN(Date.parse(deliveredAt))) fail('intent_delivery_time_invalid');
  const reasonCode = assertString(record.reasonCode, 'intent_delivery_reason_invalid', {
    nonEmpty: false,
    maxLength: 512,
  });
  if (status !== 'delivered' && reasonCode.length === 0) {
    fail('intent_delivery_reason_required');
  }
  return freezeTree({
    version: COACH_DELIVERY_VERSION,
    receiptId: assertId(record.receiptId, 'intent_delivery_receipt_id_invalid'),
    intentId: assertId(record.intentId, 'intent_delivery_intent_id_invalid'),
    status,
    deliveredAt,
    reasonCode,
  });
}

export function refusalFrom(error) {
  const message = error instanceof Error ? error.message : String(error);
  const [code, ...detail] = message.split(':');
  return freezeTree({ code, detail: detail.join(':') });
}
