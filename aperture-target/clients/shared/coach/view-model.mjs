import { currentCue } from './reducer.mjs';

function freezeTree(value) {
  if (value === null || typeof value !== 'object' || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) freezeTree(child);
  return Object.freeze(value);
}

export function projectCoachView(state) {
  const cue = currentCue(state);
  const observation = state.observation;
  const autoHoldPending = state.pendingIntents.some(
    (intent) =>
      intent.sessionId === observation?.sessionId &&
      intent.command === 'pause' &&
      intent.reason === 'automatic-decisive-cue-hold' &&
      intent.parameters.cueId === cue.cueId,
  );
  const showDecisiveFrame = Boolean(
    cue.decisive && (observation?.paused || observation?.status === 'paused'),
  );
  const status = state.status;
  return freezeTree({
    version: 'axm-aperture-coach-view/1',
    status,
    reasonCode: state.refusal?.code ?? '',
    programId: state.program.programId,
    storyPackageId: state.program.storyPackageId,
    storyPackageDigest: state.program.storyPackageDigest,
    viewerProfileId: state.program.viewerProfileId,
    viewerProfileDigest: state.program.viewerProfileDigest,
    timedPositionId: state.program.timedPosition.positionId,
    answerPlan: {
      planId: state.program.answerPlan.planId,
      receiptId: state.program.answerPlan.receiptId,
      factIds: [...state.program.answerPlan.factIds],
      summaryMode: state.program.answerPlan.summaryMode,
      effectSummary: state.program.answerPlan.effectSummary,
    },
    playback: {
      observationId: observation?.observationId ?? '',
      sessionId: observation?.sessionId ?? '',
      connected: observation?.connected ?? false,
      status: observation?.status ?? 'unavailable',
      positionMs: observation?.positionMs ?? 0,
      durationMs:
        observation?.durationMs ??
        state.program.timedPosition.endMs - state.program.timedPosition.startMs,
      rate: observation?.rate ?? 1,
      paused: observation?.paused ?? true,
      observedAt: observation?.observedAt ?? '',
    },
    presentation: {
      mode: status === 'stale' ? 'stale' : showDecisiveFrame ? 'decisive-frame' : 'motion',
      cueId: cue.cueId,
      label: cue.label,
      explanation: cue.explanation,
      frameRef: cue.frameRef,
      diagramRef: cue.diagramRef,
      factIds: [...cue.factIds],
      decisive: cue.decisive,
      holdMs: cue.holdMs,
    },
    semanticRail: state.program.cues.map((candidate) => ({
      cueId: candidate.cueId,
      label: candidate.label,
      atMs: candidate.atMs - state.program.timedPosition.startMs,
      decisive: candidate.decisive,
      current: candidate.cueId === cue.cueId,
    })),
    controls: {
      enabled: Boolean(
        observation?.connected && observation.status !== 'unavailable' && !state.refusal,
      ),
      autoHoldEnabled: state.autoHoldEnabled,
      autoHoldPending,
      frameRate: state.program.frameRate,
      allowedRates: [...state.program.allowedRates],
    },
    intents: state.pendingIntents.map((intent) => ({
      intentId: intent.intentId,
      sessionId: intent.sessionId,
      command: intent.command,
      parameters: intent.parameters,
      reason: intent.reason,
    })),
    expiredIntents: state.expiredIntents.map((intent) => ({
      intentId: intent.intentId,
      sessionId: intent.sessionId,
      command: intent.command,
      parameters: intent.parameters,
      reason: intent.reason,
      expiredByObservationId: intent.expiredByObservationId,
      expiredReason: intent.expiredReason,
    })),
    deliveries: state.deliveryReceipts.map((receipt) => ({
      receiptId: receipt.receiptId,
      intentId: receipt.intentId,
      status: receipt.status,
      deliveredAt: receipt.deliveredAt,
      reasonCode: receipt.reasonCode,
    })),
  });
}
