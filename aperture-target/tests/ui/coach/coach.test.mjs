import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import {
  COACH_DELIVERY_VERSION,
  createCoachState,
  currentCue,
  projectCoachView,
  reduceCoach,
  validateCoachProgram,
} from '../../../clients/shared/coach/index.mjs';
import { coachProgram, observation, PACKAGE_DIGEST, VIEWER_DIGEST } from './fixtures.mjs';

function lastIntent(state) {
  return state.pendingIntents.at(-1);
}

function delivery(overrides = {}) {
  return {
    version: COACH_DELIVERY_VERSION,
    receiptId: 'delivery/001',
    intentId: 'intent/unbound',
    status: 'delivered',
    deliveredAt: '2026-08-05T19:00:01.000Z',
    reasonCode: '',
    ...overrides,
  };
}

test('accepts generic semantic cues and derives presentation only from an external observation', () => {
  const state = createCoachState(coachProgram(), observation({ positionMs: 4_100 }));
  const view = projectCoachView(state);
  assert.equal(currentCue(state).cueId, 'cue/pivot');
  assert.equal(view.presentation.label, 'Rotate through the hinge');
  assert.equal(view.presentation.mode, 'motion');
  assert.equal(view.controls.autoHoldPending, true);
  assert.equal(view.timedPositionId, 'position/demo-turn');
  assert.equal(Object.hasOwn(view, 'storyPosition'), false);
});

test('a pause request emits an intent without claiming the player paused', () => {
  const state = createCoachState(coachProgram(), observation());
  const next = reduceCoach(state, { type: 'request-pause' });
  assert.equal(next.observation.paused, false);
  assert.equal(lastIntent(next).command, 'pause');
  const view = projectCoachView(next);
  assert.equal(view.playback.status, 'playing');
  assert.equal(view.presentation.mode, 'motion');
});

test('scrub and semantic-rail requests do not move narrative state until a matching observation arrives', () => {
  let state = createCoachState(coachProgram(), observation({ positionMs: 500 }));
  state = reduceCoach(state, { type: 'request-seek', targetMs: 8_200 });
  assert.equal(currentCue(state).cueId, 'cue/setup');
  assert.deepEqual(lastIntent(state).parameters, { targetMs: 8_200 });
  state = reduceCoach(state, { type: 'jump-cue', cueId: 'cue/result' });
  assert.equal(currentCue(state).cueId, 'cue/setup');
  assert.deepEqual(lastIntent(state).parameters, { targetMs: 8_000, cueId: 'cue/result' });
  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({ observationId: 'observation/002', positionMs: 8_100 }),
  });
  assert.equal(currentCue(state).cueId, 'cue/result');
});

test('frame step and speed remain bounded command intents', () => {
  let state = createCoachState(coachProgram(), observation({ positionMs: 1_000 }));
  state = reduceCoach(state, { type: 'step-frame', deltaFrames: 2 });
  assert.deepEqual(lastIntent(state).parameters, { targetMs: 1_080, deltaFrames: 2 });
  assert.equal(state.observation.positionMs, 1_000);
  state = reduceCoach(state, { type: 'set-speed', rate: 1.5 });
  assert.deepEqual(lastIntent(state).parameters, { rate: 1.5 });
  assert.equal(state.observation.rate, 1);
});

test('automatic decisive hold is session-scoped and cannot claim pause before observation', () => {
  let state = createCoachState(coachProgram(), observation({ positionMs: 4_100 }));
  const oldIntent = lastIntent(state);
  assert.equal(state.pendingIntents.length, 1);
  assert.equal(oldIntent.reason, 'automatic-decisive-cue-hold');
  assert.equal(oldIntent.parameters.cueId, 'cue/pivot');
  let view = projectCoachView(state);
  assert.equal(view.controls.autoHoldPending, true);
  assert.equal(view.presentation.mode, 'motion');
  assert.equal(view.playback.paused, false);

  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({ observationId: 'observation/002', positionMs: 4_300 }),
  });
  assert.equal(state.pendingIntents.length, 1);

  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({
      observationId: 'observation/003',
      sessionId: 'player-session/002',
      positionMs: 4_300,
    }),
  });
  assert.equal(state.pendingIntents.length, 1);
  assert.equal(state.expiredIntents.length, 1);
  assert.equal(state.expiredIntents[0].intentId, oldIntent.intentId);
  assert.equal(state.expiredIntents[0].expiredReason, 'player-session-changed');
  assert.equal(lastIntent(state).sessionId, 'player-session/002');

  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({
      observationId: 'observation/004',
      sessionId: 'player-session/002',
      status: 'paused',
      paused: true,
      positionMs: 4_300,
    }),
  });
  view = projectCoachView(state);
  assert.equal(view.presentation.mode, 'decisive-frame');
});

test('enabling automatic hold at a decisive observed cue emits one bounded intent', () => {
  const program = coachProgram({
    autoHold: { enabled: false, cueIds: ['cue/pivot', 'cue/result'] },
  });
  let state = createCoachState(program, observation({ positionMs: 4_100 }));
  assert.equal(state.pendingIntents.length, 0);
  state = reduceCoach(state, { type: 'set-auto-hold', enabled: true });
  assert.equal(state.pendingIntents.length, 1);
  assert.equal(lastIntent(state).reason, 'automatic-decisive-cue-hold');
});

test('delivery receipt records transport only and cannot upgrade observed playback', () => {
  let state = createCoachState(coachProgram(), observation());
  state = reduceCoach(state, { type: 'request-pause' });
  const intent = lastIntent(state);
  state = reduceCoach(state, {
    type: 'record-delivery',
    receipt: delivery({ intentId: intent.intentId }),
  });
  assert.equal(state.observation.paused, false);
  assert.equal(state.observation.status, 'playing');
  assert.equal(state.pendingIntents.length, 0);
  assert.equal(state.deliveryReceipts.length, 1);
  const view = projectCoachView(state);
  assert.equal(view.presentation.mode, 'motion');
  assert.equal(view.deliveries[0].receiptId, 'delivery/001');
  assert.equal(view.deliveries[0].intentId, intent.intentId);
});

test('late delivery may settle an expired session intent without reviving it', () => {
  let state = createCoachState(coachProgram(), observation({ positionMs: 4_100 }));
  const expiredIntentId = lastIntent(state).intentId;
  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({
      observationId: 'observation/new-session',
      sessionId: 'player-session/002',
      positionMs: 4_200,
    }),
  });
  state = reduceCoach(state, {
    type: 'record-delivery',
    receipt: delivery({ receiptId: 'delivery/late', intentId: expiredIntentId }),
  });
  assert.equal(state.expiredIntents.length, 1);
  assert.equal(state.pendingIntents.length, 1);
  assert.equal(state.pendingIntents[0].sessionId, 'player-session/002');
  assert.equal(state.deliveryReceipts[0].intentId, expiredIntentId);
});

test('delivery receipts require one identity and a reason for refusal or failure', () => {
  let state = createCoachState(coachProgram(), observation());
  state = reduceCoach(state, { type: 'request-pause' });
  const intent = lastIntent(state);
  state = reduceCoach(state, {
    type: 'record-delivery',
    receipt: delivery({ intentId: intent.intentId, status: 'failed' }),
  });
  assert.equal(state.refusal.code, 'intent_delivery_reason_required');

  let accepted = createCoachState(coachProgram(), observation());
  accepted = reduceCoach(accepted, { type: 'request-pause' });
  const acceptedIntent = lastIntent(accepted);
  const receipt = delivery({ intentId: acceptedIntent.intentId });
  accepted = reduceCoach(accepted, { type: 'record-delivery', receipt });
  accepted = reduceCoach(accepted, { type: 'record-delivery', receipt });
  assert.equal(accepted.refusal.code, 'intent_delivery_duplicate_receipt');
});

test('disconnect preserves the last externally verified cue as stale and disables commands', () => {
  let state = createCoachState(coachProgram(), observation({ positionMs: 8_100 }));
  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({
      observationId: 'observation/offline',
      status: 'unavailable',
      connected: false,
      paused: true,
      positionMs: 8_100,
    }),
  });
  const view = projectCoachView(state);
  assert.equal(view.status, 'stale');
  assert.equal(view.presentation.cueId, 'cue/result');
  assert.equal(view.controls.enabled, false);
  const refused = reduceCoach(state, { type: 'request-play' });
  assert.equal(refused.status, 'refused');
  assert.equal(refused.refusal.code, 'coach_player_unavailable');
});

test('reconnect reconciles from the new observation and rejects package or viewer substitution', () => {
  let state = createCoachState(
    coachProgram(),
    observation({ connected: false, status: 'unavailable', paused: true }),
  );
  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({
      observationId: 'observation/reconnected',
      sessionId: 'player-session/reconnected',
      positionMs: 8_100,
    }),
  });
  assert.equal(state.status, 'ready');
  assert.equal(currentCue(state).cueId, 'cue/result');
  const packageMismatch = reduceCoach(state, {
    type: 'observe',
    observation: observation({ packageDigest: '3'.repeat(64) }),
  });
  assert.equal(packageMismatch.refusal.code, 'observation_package_mismatch');
  const viewerMismatch = reduceCoach(state, {
    type: 'observe',
    observation: observation({ viewerProfileDigest: '4'.repeat(64) }),
  });
  assert.equal(viewerMismatch.refusal.code, 'observation_viewer_mismatch');
});

test('contradictory player observations fail closed', () => {
  const pausedConflict = createCoachState(
    coachProgram(),
    observation({ status: 'paused', paused: false }),
  );
  assert.equal(pausedConflict.refusal.code, 'observation_paused_flag_conflict');
  const disconnectedConflict = createCoachState(
    coachProgram(),
    observation({ connected: false, status: 'playing', paused: false }),
  );
  assert.equal(disconnectedConflict.refusal.code, 'observation_disconnected_status_invalid');
  const unavailableConflict = createCoachState(
    coachProgram(),
    observation({ connected: true, status: 'unavailable', paused: false }),
  );
  assert.equal(unavailableConflict.refusal.code, 'observation_terminal_paused_conflict');
});

test('answer-plan and timed-position identities are closed and mutually bound', () => {
  const invalid = coachProgram();
  invalid.answerPlan.packageDigest = '5'.repeat(64);
  assert.throws(() => validateCoachProgram(invalid), /answer_plan_package_digest_mismatch/);
  const unknown = coachProgram();
  unknown.cues[0].mystery = true;
  assert.throws(() => validateCoachProgram(unknown), /cue_unknown_field/);
  const lateFirstCue = coachProgram();
  lateFirstCue.cues[0].atMs += 1;
  assert.throws(() => validateCoachProgram(lateFirstCue), /coach_program_first_cue_not_at_start/);
});

test('validated state and projected view are deeply immutable', () => {
  const state = createCoachState(coachProgram(), observation());
  const view = projectCoachView(state);
  assert.equal(Object.isFrozen(state), true);
  assert.equal(Object.isFrozen(state.program.cues), true);
  assert.equal(Object.isFrozen(state.program.cues[0]), true);
  assert.equal(Object.isFrozen(view), true);
  assert.equal(Object.isFrozen(view.semanticRail), true);
  assert.equal(Object.isFrozen(view.semanticRail[0]), true);
  assert.throws(() => {
    state.program.cues[0].label = 'mutated';
  }, TypeError);
  assert.throws(() => {
    view.semanticRail.push({ cueId: 'cue/mutated' });
  }, TypeError);
});

test('a refusal can be cleared only by a new valid external observation', () => {
  let state = createCoachState(coachProgram(), observation());
  state = reduceCoach(state, { type: 'set-speed', rate: 9 });
  assert.equal(state.status, 'refused');
  assert.throws(() => reduceCoach(state, { type: 'clear-refusal' }), /coach_event_unsupported/);
  state = reduceCoach(state, {
    type: 'observe',
    observation: observation({ observationId: 'observation/recovery' }),
  });
  assert.equal(state.status, 'ready');
  assert.equal(state.refusal, null);
});

test('implementation contains no manual phase constants, local playback clock, transport, or player calls', async () => {
  const sources = await Promise.all(
    ['contract.mjs', 'reducer.mjs', 'view-model.mjs', 'index.mjs'].map((name) =>
      readFile(new URL(`../../../clients/shared/coach/${name}`, import.meta.url), 'utf8'),
    ),
  );
  const text = sources.join('\n');
  for (const forbidden of [
    /setInterval\s*\(/,
    /setTimeout\s*\(/,
    /requestAnimationFrame\s*\(/,
    /Date\.now\s*\(/,
    /performance\.now\s*\(/,
    /new Date\s*\(/,
    /currentTime\s*=/,
    /\.play\s*\(/,
    /\.pause\s*\(/,
    /\bfetch\s*\(/,
    /WebSocket\s*\(/,
    /localStorage/,
    /sessionStorage/,
    /HTMLMediaElement/,
    /\bdocument\./,
    /\bwindow\./,
    /\bnavigator\./,
    /\bSTART\b/,
    /\bMOVE\b/,
    /\bCHECK\b/,
  ]) {
    assert.doesNotMatch(text, forbidden);
  }
});

test('intent IDs are deterministic for the same exact event history', () => {
  const first = reduceCoach(createCoachState(coachProgram(), observation()), {
    type: 'request-pause',
  });
  const second = reduceCoach(createCoachState(coachProgram(), observation()), {
    type: 'request-pause',
  });
  assert.equal(lastIntent(first).intentId, lastIntent(second).intentId);
  assert.equal(first.program.storyPackageDigest, PACKAGE_DIGEST);
  assert.equal(first.program.viewerProfileDigest, VIEWER_DIGEST);
});
