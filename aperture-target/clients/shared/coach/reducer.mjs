import {
  COACH_INTENT_VERSION,
  COACH_STATE_VERSION,
  refusalFrom,
  sha256Json,
  validateCoachProgram,
  validateIntentDelivery,
  validatePlaybackObservation,
} from './contract.mjs';

const EVENT_TYPES = new Set([
  'observe',
  'request-play',
  'request-pause',
  'request-seek',
  'step-frame',
  'set-speed',
  'jump-cue',
  'set-auto-hold',
  'record-delivery',
]);

function freezeTree(value) {
  if (value === null || typeof value !== 'object' || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) freezeTree(child);
  return Object.freeze(value);
}

function cueAt(program, absoluteMs) {
  let current = program.cues[0];
  for (const cue of program.cues) {
    if (absoluteMs < cue.atMs) break;
    current = cue;
  }
  return current;
}

function createIntent(state, command, parameters, reason) {
  const sequence = state.sequence + 1;
  const body = {
    version: COACH_INTENT_VERSION,
    programId: state.program.programId,
    packageDigest: state.program.storyPackageDigest,
    viewerProfileDigest: state.program.viewerProfileDigest,
    positionId: state.program.timedPosition.positionId,
    sessionId: state.observation?.sessionId ?? 'no-active-session',
    sequence,
    command,
    parameters,
    reason,
  };
  const intentId = `coach-intent/${sha256Json(body)}`;
  return freezeTree({ ...body, intentId });
}

function deriveStatus(observation, refusal) {
  if (refusal) return 'refused';
  if (!observation) return 'unavailable';
  if (!observation.connected) return 'stale';
  if (observation.status === 'unavailable') return 'unavailable';
  if (observation.status === 'buffering') return 'partial';
  return 'ready';
}

function maybeAutoHold(state) {
  const observation = state.observation;
  if (!observation || !observation.connected || observation.paused || observation.status !== 'playing') {
    return state;
  }
  if (!state.autoHoldEnabled) return state;
  const cue = cueAt(state.program, state.program.timedPosition.startMs + observation.positionMs);
  if (!state.program.autoHold.cueIds.includes(cue.cueId)) return state;
  const key = `${observation.sessionId}:${cue.cueId}`;
  if (state.autoHoldLedger.includes(key)) return state;
  const intent = createIntent(
    state,
    'pause',
    { atMs: observation.positionMs, cueId: cue.cueId },
    'automatic-decisive-cue-hold',
  );
  return freezeTree({
    ...state,
    sequence: intent.sequence,
    pendingIntents: [...state.pendingIntents, intent],
    autoHoldLedger: [...state.autoHoldLedger, key],
  });
}

function requireCommandable(state) {
  if (state.refusal) throw new Error('coach_state_refused');
  if (!state.observation || !state.observation.connected) throw new Error('coach_player_unavailable');
  if (state.observation.status === 'unavailable') throw new Error('coach_player_unavailable');
}

function appendIntent(state, command, parameters, reason) {
  requireCommandable(state);
  const intent = createIntent(state, command, parameters, reason);
  return freezeTree({
    ...state,
    sequence: intent.sequence,
    pendingIntents: [...state.pendingIntents, intent],
  });
}

function expirePriorSessionIntents(state, observation) {
  if (!state.observation || state.observation.sessionId === observation.sessionId) {
    return {
      pendingIntents: state.pendingIntents,
      expiredIntents: state.expiredIntents,
    };
  }
  const stillCurrent = [];
  const newlyExpired = [];
  for (const intent of state.pendingIntents) {
    if (intent.sessionId === observation.sessionId) {
      stillCurrent.push(intent);
      continue;
    }
    newlyExpired.push(
      freezeTree({
        ...intent,
        expiredByObservationId: observation.observationId,
        expiredReason: 'player-session-changed',
      }),
    );
  }
  return {
    pendingIntents: stillCurrent,
    expiredIntents: [...state.expiredIntents, ...newlyExpired],
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function createCoachState(programInput, observationInput = null) {
  const program = validateCoachProgram(programInput);
  let observation = null;
  let refusal = null;
  if (observationInput !== null) {
    try {
      observation = validatePlaybackObservation(observationInput, program);
    } catch (error) {
      refusal = refusalFrom(error);
    }
  }
  const state = freezeTree({
    version: COACH_STATE_VERSION,
    program,
    observation,
    autoHoldEnabled: program.autoHold.enabled,
    autoHoldLedger: [],
    pendingIntents: [],
    expiredIntents: [],
    deliveryReceipts: [],
    refusal,
    status: deriveStatus(observation, refusal),
    sequence: 0,
  });
  return maybeAutoHold(state);
}

export function reduceCoach(state, event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) {
    throw new Error('coach_event_not_object');
  }
  if (!EVENT_TYPES.has(event.type)) throw new Error(`coach_event_unsupported:${event.type}`);
  try {
    if (event.type === 'observe') {
      const observation = validatePlaybackObservation(event.observation, state.program);
      const sessionIntents = expirePriorSessionIntents(state, observation);
      const observed = freezeTree({
        ...state,
        ...sessionIntents,
        observation,
        refusal: null,
        status: deriveStatus(observation, null),
      });
      return maybeAutoHold(observed);
    }
    if (event.type === 'record-delivery') {
      const receipt = validateIntentDelivery(event.receipt);
      if (state.deliveryReceipts.some((candidate) => candidate.receiptId === receipt.receiptId)) {
        throw new Error('intent_delivery_duplicate_receipt');
      }
      if (state.deliveryReceipts.some((candidate) => candidate.intentId === receipt.intentId)) {
        throw new Error('intent_delivery_duplicate_intent');
      }
      const knownPending = state.pendingIntents.some((intent) => intent.intentId === receipt.intentId);
      const knownExpired = state.expiredIntents.some((intent) => intent.intentId === receipt.intentId);
      if (!knownPending && !knownExpired) throw new Error('intent_delivery_unknown_intent');
      return freezeTree({
        ...state,
        deliveryReceipts: [...state.deliveryReceipts, receipt],
        pendingIntents: state.pendingIntents.filter((intent) => intent.intentId !== receipt.intentId),
      });
    }
    if (event.type === 'set-auto-hold') {
      if (typeof event.enabled !== 'boolean') throw new Error('auto_hold_event_invalid');
      return maybeAutoHold(freezeTree({ ...state, autoHoldEnabled: event.enabled }));
    }
    if (event.type === 'request-play') {
      return appendIntent(state, 'play', {}, 'viewer-play-request');
    }
    if (event.type === 'request-pause') {
      return appendIntent(state, 'pause', {}, 'viewer-pause-request');
    }
    if (event.type === 'request-seek') {
      if (!Number.isFinite(event.targetMs)) throw new Error('seek_target_invalid');
      requireCommandable(state);
      const targetMs = Math.round(clamp(event.targetMs, 0, state.observation.durationMs));
      return appendIntent(state, 'seek', { targetMs }, 'viewer-scrub-request');
    }
    if (event.type === 'step-frame') {
      if (!Number.isInteger(event.deltaFrames) || event.deltaFrames === 0) {
        throw new Error('frame_step_delta_invalid');
      }
      requireCommandable(state);
      const frameMs = 1000 / state.program.frameRate;
      const targetMs = Math.round(
        clamp(
          state.observation.positionMs + event.deltaFrames * frameMs,
          0,
          state.observation.durationMs,
        ),
      );
      return appendIntent(
        state,
        'seek',
        { targetMs, deltaFrames: event.deltaFrames },
        'viewer-frame-step-request',
      );
    }
    if (event.type === 'set-speed') {
      if (!state.program.allowedRates.includes(event.rate)) throw new Error('playback_rate_not_allowed');
      return appendIntent(state, 'set-rate', { rate: event.rate }, 'viewer-rate-request');
    }
    if (event.type === 'jump-cue') {
      const cue = state.program.cues.find((candidate) => candidate.cueId === event.cueId);
      if (!cue) throw new Error('cue_jump_unknown_cue');
      const targetMs = cue.atMs - state.program.timedPosition.startMs;
      return appendIntent(
        state,
        'seek',
        { targetMs, cueId: cue.cueId },
        'viewer-semantic-rail-request',
      );
    }
  } catch (error) {
    const refusal = refusalFrom(error);
    return freezeTree({ ...state, refusal, status: deriveStatus(state.observation, refusal) });
  }
  return state;
}

export function currentCue(state) {
  if (!state.observation) return state.program.cues[0];
  const absoluteMs = state.program.timedPosition.startMs + state.observation.positionMs;
  return cueAt(state.program, absoluteMs);
}
