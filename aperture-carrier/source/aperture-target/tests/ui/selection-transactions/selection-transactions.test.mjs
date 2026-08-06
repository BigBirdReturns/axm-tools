import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';

import {
  CONTEXT_STATES,
  SCORE_TERM_KEYS,
  SELECTION_MODES,
  buildSelectionActivation,
  canonicalJson,
  sha256Json,
  validateActuationObservation,
  validateSelectionContext,
  validateSelectionReceipt,
} from '../../../clients/shared/selections/contract.mjs';
import {
  activateSelection,
  createSelectionState,
  declineSelection,
  dismissSelection,
  ingestActuationObservation,
  ingestSelectionReceipt,
  recordSelectionDelivery,
  replaceSelectionContext,
} from '../../../clients/shared/selections/reducer.mjs';
import { projectSelectionView } from '../../../clients/shared/selections/view-model.mjs';
import {
  D,
  actuationObservation,
  candidate,
  deliveryReceipt,
  mutated,
  selectionContext,
  selectionReceipt,
} from './fixtures.mjs';

function selectedState(context = selectionContext(), receipt = null) {
  const state = createSelectionState(context);
  return ingestSelectionReceipt(state, receipt ?? selectionReceipt(context));
}

function activatedState(context = selectionContext(), receipt = null) {
  return activateSelection(selectedState(context, receipt));
}

function errorCode(fn) {
  try {
    fn();
    return '';
  } catch (error) {
    return error.code ?? error.message;
  }
}

test('ready selection context validates and is deeply frozen', () => {
  const context = validateSelectionContext(selectionContext());
  assert.equal(context.state, 'ready');
  assert.equal(Object.isFrozen(context), true);
  assert.equal(Object.isFrozen(context.anchor), true);
  assert.equal(Object.isFrozen(context.providerMapping), true);
});

for (const state of CONTEXT_STATES) {
  test(`context state remains machine-distinct: ${state}`, () => {
    const context = selectionContext({ state, reasonCode: state === 'ready' ? '' : `${state}-context` });
    const view = projectSelectionView(createSelectionState(context));
    assert.equal(view.state, state === 'ready' ? 'idle' : state);
    assert.equal(view.context.storyPackageDigest, D.package);
  });
}

for (const mode of SELECTION_MODES) {
  test(`selection mode validates and remains visible: ${mode}`, () => {
    const context = selectionContext();
    const receipt = selectionReceipt(context, { mode });
    const validated = validateSelectionReceipt(receipt, context);
    const view = projectSelectionView(selectedState(context, receipt));
    assert.equal(validated.mode, mode);
    assert.equal(view.policy.mode, mode);
  });
}

for (const term of SCORE_TERM_KEYS) {
  test(`score term is visible and contributes to the signed total: ${term}`, () => {
    const context = selectionContext();
    const row = candidate({ terms: { [term]: term.includes('penalty') || term === 'entry_cost' ? -123_456 : 123_456 } });
    const receipt = selectionReceipt(context, { candidates: [row] });
    const validated = validateSelectionReceipt(receipt, context);
    const selected = validated.candidates[0];
    assert.equal(selected.score_terms[term], row.score_terms[term]);
    assert.equal(selected.score, Object.values(selected.score_terms).reduce((sum, value) => sum + value, 0));
    assert.equal(projectSelectionView(selectedState(context, receipt)).selectedCandidate.scoreTerms[term], row.score_terms[term]);
  });
}

for (const term of SCORE_TERM_KEYS) {
  test(`noninteger score term refuses: ${term}`, () => {
    const context = selectionContext();
    const row = candidate();
    row.score_terms[term] = 0.5;
    row.score = Object.values(row.score_terms).reduce((sum, value) => sum + value, 0);
    const receipt = selectionReceipt(context, { candidates: [row] });
    assert.match(errorCode(() => validateSelectionReceipt(receipt, context)), /selection_score_term_invalid/);
  });
}

const scopeCases = [
  ['viewer', (receipt) => { receipt.viewer_id = 'viewer:other'; }],
  ['work', (receipt) => { receipt.work_id = 'work:other'; }],
  ['continuity', (receipt) => { receipt.continuity_id = 'continuity:other'; }],
  ['package', (receipt) => { receipt.story_package_id = 'story-package:other'; }],
  ['anchor digest input', (receipt) => { receipt.input_projection_digests = [D.package, D.exposure, D.knowledge]; }],
];
for (const [label, mutate] of scopeCases) {
  test(`selection receipt scope substitution refuses: ${label}`, () => {
    const context = selectionContext();
    const receipt = selectionReceipt(context);
    mutate(receipt);
    assert.notEqual(errorCode(() => validateSelectionReceipt(receipt, context)), '');
  });
}

const candidateRefusals = [
  ['cross work', (row, context) => { row.work_id = 'work:other'; }, 'selection_cross_work_candidate'],
  ['reverse range', (row) => { row.canonical_end_us = row.canonical_start_us; }, 'selection_candidate_interval_invalid'],
  ['duration above context', (row, context) => { row.canonical_end_us = row.canonical_start_us + context.maximumSegmentUs + 1; }, 'selection_candidate_duration_exceeds_context'],
  ['duplicate identity', null, 'selection_candidate_identity_duplicate'],
  ['score mismatch', (row) => { row.score += 1; }, 'selection_candidate_score_mismatch'],
  ['candidate digest mismatch', null, 'selection_candidate_set_digest_mismatch'],
];
for (const [label, mutate, expected] of candidateRefusals) {
  test(`candidate denominator refuses ${label}`, () => {
    const context = selectionContext();
    let rows = [candidate(), candidate({ id: 'candidate:two', sceneId: 'scene:two', startUs: 80_000_000, endUs: 120_000_000 })];
    if (label === 'duplicate identity') rows[1].candidate_id = rows[0].candidate_id;
    else if (mutate) mutate(rows[0], context);
    const receipt = selectionReceipt(context, { candidates: rows });
    if (label === 'candidate digest mismatch') receipt.candidate_set_digest = 'f'.repeat(64);
    assert.equal(errorCode(() => validateSelectionReceipt(receipt, context)), expected);
  });
}

const tieCases = [
  {
    label: 'higher score wins',
    rows: [
      candidate({ id: 'candidate:low', sceneId: 'scene:low', terms: { uncovered: 1 } }),
      candidate({ id: 'candidate:high', sceneId: 'scene:high', terms: { uncovered: 900_000 } }),
    ],
    expected: 'candidate:high',
  },
  {
    label: 'earlier canonical start breaks equal score',
    rows: [
      candidate({ id: 'candidate:late', sceneId: 'scene:late', startUs: 50_000_000, endUs: 70_000_000 }),
      candidate({ id: 'candidate:early', sceneId: 'scene:early', startUs: 10_000_000, endUs: 30_000_000 }),
    ],
    expected: 'candidate:early',
  },
  {
    label: 'code-point scene identity breaks remaining tie',
    rows: [
      candidate({ id: 'candidate:z', sceneId: 'scene:z', startUs: 10_000_000, endUs: 30_000_000 }),
      candidate({ id: 'candidate:a', sceneId: 'scene:a', startUs: 10_000_000, endUs: 30_000_000 }),
    ],
    expected: 'candidate:a',
  },
];
for (const row of tieCases) {
  test(`deterministic ranking: ${row.label}`, () => {
    const context = selectionContext();
    const receipt = selectionReceipt(context, { candidates: row.rows });
    assert.equal(validateSelectionReceipt(receipt, context).selected_candidate_id, row.expected);
  });
}

const denominatorCases = [
  ['empty candidate set', (receipt) => { receipt.candidates = []; receipt.candidate_set_digest = sha256Json([]); }, 'selection_candidate_denominator_invalid'],
  ['missing selected candidate', (receipt) => { receipt.selected_candidate_id = 'candidate:missing'; }, 'selection_selected_candidate_missing_or_duplicate'],
  ['non-rank-one selected candidate', (receipt) => { receipt.selected_candidate_id = receipt.candidates.at(-1).candidate_id; }, 'selection_selected_candidate_not_rank_one'],
  ['same-work proof removed', (receipt) => { receipt.same_work_only = false; }, 'selection_same_work_proof_required'],
];
for (const [label, mutate, expected] of denominatorCases) {
  test(`selection denominator refuses ${label}`, () => {
    const context = selectionContext();
    const receipt = selectionReceipt(context);
    mutate(receipt);
    assert.equal(errorCode(() => validateSelectionReceipt(receipt, context)), expected);
  });
}

test('exact anchor, verified mapping, and exact capability emit seek request intent', () => {
  const state = activatedState();
  assert.equal(state.currentIntent.kind, 'exact_seek_request');
  assert.equal(state.currentIntent.autoplay, false);
  assert.equal(state.currentIntent.providerPositionUs, state.currentIntent.canonicalStartUs + 2_000_000);
  assert.equal(state.fallback, null);
});

test('missing exact seek produces verified provider timestamp fallback', () => {
  const context = selectionContext({ capabilities: { seek: 'none' } });
  const state = activatedState(context);
  assert.equal(state.currentIntent, null);
  assert.equal(state.fallback.kind, 'timestamp_fallback');
  assert.equal(state.fallback.fallbackKind, 'provider_timestamp');
  assert.equal(state.fallback.authority, 'request_intent_only');
});

test('missing provider mapping produces canonical timestamp fallback', () => {
  const context = selectionContext({
    providerMapping: {
      state: 'unavailable',
      providerEditionId: '',
      mapDigest: '',
      rateNumerator: 0,
      rateDenominator: 1,
      offsetUs: 0,
      reasonCode: 'mapping-unavailable',
    },
    capabilities: { seek: 'none' },
  });
  const state = activatedState(context);
  assert.equal(state.fallback.fallbackKind, 'canonical_timestamp');
  assert.equal(state.fallback.providerPositionUs, null);
});

test('manual anchor cannot authorize exact seek', () => {
  const context = selectionContext({ anchor: { confidence: 'manual', exact: false } });
  const activation = buildSelectionActivation(context, selectionReceipt(context));
  assert.equal(activation.kind, 'timestamp_fallback');
  assert.equal(activation.fallbackKind, 'provider_timestamp');
});

test('non-ready context refuses activation', () => {
  const context = selectionContext({ state: 'stale', reasonCode: 'anchor-stale' });
  const state = activateSelection(selectedState(context));
  assert.equal(state.currentIntent, null);
  assert.equal(state.activationRefusal.code, 'selection_activation_context_not_ready');
});

test('every activation path explicitly disables autoplay', () => {
  const exact = activatedState().currentIntent;
  const fallback = activatedState(selectionContext({ capabilities: { seek: 'none' } })).fallback;
  assert.equal(exact.autoplay, false);
  assert.equal(fallback.autoplay, false);
});

test('delivery receipt cannot become actuation success', () => {
  let state = activatedState();
  state = recordSelectionDelivery(state, deliveryReceipt(state.currentIntent));
  const view = projectSelectionView(state);
  assert.equal(view.state, 'request_delivered_unverified');
  assert.equal(view.transport.delivered, true);
  assert.equal(view.transport.verifiedActuation, false);
});

test('duplicate delivery receipt is idempotent', () => {
  let state = activatedState();
  const receipt = deliveryReceipt(state.currentIntent);
  state = recordSelectionDelivery(state, receipt);
  const replay = recordSelectionDelivery(state, receipt);
  assert.equal(canonicalJson(replay), canonicalJson(state));
  assert.equal(replay.deliveries.length, 1);
});

test('delivery for unknown intent becomes bounded refusal', () => {
  const state = recordSelectionDelivery(createSelectionState(selectionContext()), deliveryReceipt({ intentId: 'selectionintent1_' + '7'.repeat(64) }));
  assert.equal(state.activationRefusal.code, 'selection_delivery_intent_unknown');
});

test('separate AP-212 observation is required for verified actuation', () => {
  let state = activatedState();
  state = recordSelectionDelivery(state, deliveryReceipt(state.currentIntent));
  state = ingestActuationObservation(state, actuationObservation(state.currentIntent));
  assert.equal(projectSelectionView(state).state, 'actuation_verified');
  assert.equal(state.actuationObservation.authority, 'external_ap212_observation_only');
});

test('verified actuation outside tolerance refuses', () => {
  const state = activatedState();
  const observation = actuationObservation(state.currentIntent, state.context, {
    observedCanonicalPositionUs: state.currentIntent.canonicalStartUs + 1_000_000,
  });
  assert.equal(errorCode(() => validateActuationObservation(observation, state.currentIntent, state.context)), 'verified_actuation_outside_tolerance');
});

test('timestamp fallback cannot be promoted to verified actuation', () => {
  const context = selectionContext({ capabilities: { seek: 'none' } });
  const activation = buildSelectionActivation(context, selectionReceipt(context));
  const observation = actuationObservation(activation, context, { observedProviderPositionUs: activation.providerPositionUs });
  assert.equal(errorCode(() => validateActuationObservation(observation, activation, context)), 'timestamp_fallback_cannot_be_verified_actuation');
});

test('initial state contains no selection or actuation', () => {
  const state = createSelectionState(selectionContext());
  assert.equal(state.selection, null);
  assert.equal(state.currentIntent, null);
  assert.equal(projectSelectionView(state).state, 'idle');
});

test('selection receipt becomes inspectable without actuation', () => {
  const state = selectedState();
  const view = projectSelectionView(state);
  assert.equal(view.state, 'selected');
  assert.equal(view.policy.candidateCount, 3);
  assert.equal(view.canInspect, true);
  assert.equal(view.canActivate, true);
  assert.equal(state.currentIntent, null);
});

test('viewer decline records preference without actuation', () => {
  const state = declineSelection(selectedState());
  assert.equal(projectSelectionView(state).state, 'declined');
  assert.equal(state.currentIntent, null);
  assert.equal(state.declinedSelectionIds.length, 1);
});

test('context replacement makes prior selection stale and read-only', () => {
  const state = replaceSelectionContext(selectedState(), selectionContext({ contextId: 'selection-context:2', sequence: 8 }));
  const view = projectSelectionView(state);
  assert.equal(view.state, 'stale');
  assert.equal(view.stale, true);
  assert.equal(view.canActivate, false);
  assert.equal(state.selection, null);
});

test('context sequence regression refuses', () => {
  const state = replaceSelectionContext(createSelectionState(selectionContext()), selectionContext({ contextId: 'selection-context:older', sequence: 6 }));
  assert.equal(state.refusal.code, 'selection_context_sequence_regression');
});

test('same context identity with changed content conflicts', () => {
  const state = replaceSelectionContext(createSelectionState(selectionContext()), selectionContext({ maximumSegmentUs: 500_000_000 }));
  assert.equal(state.refusal.code, 'selection_context_identity_conflict');
});

test('same selection receipt replay is idempotent', () => {
  const context = selectionContext();
  const receipt = selectionReceipt(context);
  const state = selectedState(context, receipt);
  const replay = ingestSelectionReceipt(state, receipt);
  assert.equal(canonicalJson(replay), canonicalJson(state));
});

test('dismiss clears active projection but retains expired intent evidence', () => {
  const active = activatedState();
  const state = dismissSelection(active);
  assert.equal(state.selection, null);
  assert.equal(state.currentIntent, null);
  assert.equal(state.expiredIntents.length, 1);
  assert.equal(projectSelectionView(state).state, 'idle');
});

test('context replacement expires active intent', () => {
  const active = activatedState();
  const state = replaceSelectionContext(active, selectionContext({ contextId: 'selection-context:2', sequence: 8 }));
  assert.equal(state.currentIntent, null);
  assert.equal(state.expiredIntents.at(-1).expiredReason, 'context-replaced');
});

test('decline expires active intent', () => {
  const state = declineSelection(activatedState());
  assert.equal(state.currentIntent, null);
  assert.equal(state.expiredIntents.at(-1).expiredReason, 'viewer-declined');
});

test('new selection expires prior active intent', () => {
  const active = activatedState();
  const replacement = selectionReceipt(active.context, { mode: 'bridge' });
  const state = ingestSelectionReceipt(active, replacement);
  assert.equal(state.currentIntent, null);
  assert.equal(state.expiredIntents.at(-1).expiredReason, 'selection-replaced');
});

test('late delivery settles evidence but cannot revive expired intent', () => {
  const active = activatedState();
  const intent = active.currentIntent;
  let state = replaceSelectionContext(active, selectionContext({ contextId: 'selection-context:2', sequence: 8 }));
  state = recordSelectionDelivery(state, deliveryReceipt(intent));
  assert.equal(state.currentIntent, null);
  assert.equal(state.deliveries.length, 1);
  assert.equal(projectSelectionView(state).state, 'stale');
});

test('validated context owns and freezes its input tree', () => {
  const input = selectionContext();
  const validated = validateSelectionContext(input);
  input.anchor.anchorId = 'anchor:mutated';
  assert.equal(validated.anchor.anchorId, 'anchor:fixture');
  assert.equal(Object.isFrozen(validated.anchor), true);
});

test('validated receipt owns and freezes candidate rows', () => {
  const context = selectionContext();
  const input = selectionReceipt(context);
  const validated = validateSelectionReceipt(input, context);
  input.candidates[0].scene_id = 'scene:mutated';
  assert.equal(validated.candidates[0].scene_id, 'scene:entry');
  assert.equal(Object.isFrozen(validated.candidates[0].score_terms), true);
});

test('reducer state is deeply immutable', () => {
  const state = activatedState();
  assert.equal(Object.isFrozen(state), true);
  assert.equal(Object.isFrozen(state.context), true);
  assert.equal(Object.isFrozen(state.selection), true);
  assert.equal(Object.isFrozen(state.currentIntent), true);
});

test('activation intent is content-addressed and immutable', () => {
  const context = selectionContext();
  const receipt = selectionReceipt(context);
  const intent = buildSelectionActivation(context, receipt);
  assert.match(intent.intentId, /^selectionintent1_[0-9a-f]{64}$/);
  assert.equal(Object.isFrozen(intent), true);
  const changed = selectionReceipt(context, { mode: 'bridge' });
  assert.notEqual(buildSelectionActivation(context, changed).intentId, intent.intentId);
});

test('projected view is deeply immutable', () => {
  const view = projectSelectionView(activatedState());
  assert.equal(Object.isFrozen(view), true);
  assert.equal(Object.isFrozen(view.policy.candidates), true);
  assert.equal(Object.isFrozen(view.selectedCandidate.scoreTerms), true);
  assert.equal(Object.isFrozen(view.authority), true);
});

const forbiddenPatterns = [
  ['network fetch', /\bfetch\s*\(/],
  ['websocket', /WebSocket/],
  ['xhr', /XMLHttpRequest/],
  ['local storage', /localStorage/],
  ['local clock', /Date\.now\s*\(/],
  ['timer', /setTimeout\s*\(/],
  ['model scoring', /modelScore|engagementScore|engagement_metric/i],
  ['coordinate click', /coordinateClick|screen\.click|mouse\.click/i],
  ['player actuation', /\.play\s*\(|\.pause\s*\(|\.seek\s*\(/],
];
for (const [label, pattern] of forbiddenPatterns) {
  test(`source contains no forbidden authority: ${label}`, () => {
    const source = [
      readFileSync(new URL('../../../clients/shared/selections/contract.mjs', import.meta.url), 'utf8'),
      readFileSync(new URL('../../../clients/shared/selections/reducer.mjs', import.meta.url), 'utf8'),
      readFileSync(new URL('../../../clients/shared/selections/view-model.mjs', import.meta.url), 'utf8'),
    ].join('\n');
    assert.equal(pattern.test(source), false, String(pattern));
  });
}

test('pure warm selection projection remains beneath five millisecond P95 source budget', () => {
  const state = activatedState();
  const samples = [];
  for (let index = 0; index < 2_000; index += 1) {
    const start = performance.now();
    projectSelectionView(state);
    samples.push(performance.now() - start);
  }
  samples.sort((left, right) => left - right);
  const p95 = samples[Math.floor(samples.length * 0.95)];
  console.log(`SELECTION_TRANSACTION_WARM_P95_MS=${p95.toFixed(6)}`);
  assert.ok(p95 < 5, `warm P95 ${p95}ms exceeds candidate budget`);
});

test('AP-405 receipt remains closed and predecessor-bound', () => {
  const receipt = JSON.parse(readFileSync(new URL('../../../receipts/AP-405.json', import.meta.url), 'utf8'));
  assert.equal(receipt.transaction, 'AP-405');
  assert.equal(receipt.canonical_ap405_accepted, false);
  assert.equal(receipt.canonical_g3_accepted, false);
  assert.equal(receipt.hosted_repository_accepted, false);
  assert.equal(receipt.predecessors.AP_211.issue_receipt_sha256, 'ea8fabb8918f126b0391ebc3fec7a5734860c1c1df71b09c5a39779cc09297f0');
  assert.equal(receipt.predecessors.AP_212.issue_receipt_sha256, 'a3f7de18b71fac5bf3838562fe3f1309bcebd81aa365dca1a0e5d6ba82c31290');
  assert.equal(receipt.predecessors.AP_402.artifact_id, 8950448870);
  assert.equal(receipt.predecessors.AP_403.artifact_id, 8954499976);
});

test('canonical JSON is stable across object key insertion order', () => {
  assert.equal(canonicalJson({ b: 2, a: 1 }), canonicalJson({ a: 1, b: 2 }));
});

test('nonintegral provider target refuses exact activation', () => {
  const context = selectionContext({ providerMapping: { rateNumerator: 1, rateDenominator: 3, offsetUs: 0 } });
  const row = candidate({ startUs: 10_000_001, endUs: 20_000_001 });
  const receipt = selectionReceipt(context, { candidates: [row] });
  assert.equal(errorCode(() => buildSelectionActivation(context, receipt)), 'provider_mapping_nonintegral_target');
});

test('nonverified provider mapping cannot retain mapping identity', () => {
  const context = selectionContext({
    providerMapping: {
      state: 'stale',
      providerEditionId: 'provider-edition:fixture',
      mapDigest: D.map,
      rateNumerator: 1,
      rateDenominator: 1,
      offsetUs: 0,
      reasonCode: 'mapping-stale',
    },
  });
  assert.equal(errorCode(() => validateSelectionContext(context)), 'nonverified_provider_mapping_authority_forbidden');
});

test('candidate array ordering is part of the complete denominator identity', () => {
  const context = selectionContext();
  const receipt = selectionReceipt(context);
  const reversed = selectionReceipt(context, { candidates: [...receipt.candidates].reverse() });
  assert.notEqual(reversed.candidate_set_digest, receipt.candidate_set_digest);
  assert.notEqual(reversed.selection_id, receipt.selection_id);
});

test('selected view exposes the complete candidate denominator and policy rationale', () => {
  const view = projectSelectionView(selectedState());
  assert.equal(view.policy.candidateCount, view.policy.candidates.length);
  assert.deepEqual(view.policy.reasonCodes, ['uncovered', 'same-work']);
  assert.equal(view.policy.candidates.filter((row) => row.selected).length, 1);
  assert.equal(view.policy.sameWorkOnly, true);
});
