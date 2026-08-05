import {
  COACH_OBSERVATION_VERSION,
  COACH_PROGRAM_VERSION,
} from '../../../clients/shared/coach/index.mjs';

export const PACKAGE_DIGEST = '1'.repeat(64);
export const VIEWER_DIGEST = '2'.repeat(64);

export function coachProgram(overrides = {}) {
  const base = {
    version: COACH_PROGRAM_VERSION,
    programId: 'coach/demo-turn/1',
    storyPackageId: 'story/demo/1',
    storyPackageDigest: PACKAGE_DIGEST,
    viewerProfileId: 'viewer/demo',
    viewerProfileDigest: VIEWER_DIGEST,
    timedPosition: {
      positionId: 'position/demo-turn',
      workId: 'work/demo',
      packageDigest: PACKAGE_DIGEST,
      startMs: 10_000,
      endMs: 20_000,
      canonicalStart: 'chapter-2:turn-4',
      canonicalEnd: 'chapter-2:turn-5',
    },
    answerPlan: {
      planId: 'answer-plan/demo-turn',
      packageDigest: PACKAGE_DIGEST,
      positionId: 'position/demo-turn',
      factIds: ['fact/setup', 'fact/pivot', 'fact/result'],
      summaryMode: 'structured',
      effectSummary: 'No knowledge mutation. Presentation only.',
      receiptId: 'answer-receipt/demo-turn',
    },
    cues: [
      {
        cueId: 'cue/setup',
        label: 'Establish the grip',
        atMs: 10_000,
        holdMs: 0,
        decisive: false,
        explanation: 'Keep the reference edge visible before the turn.',
        frameRef: 'frame/setup',
        diagramRef: 'diagram/setup',
        factIds: ['fact/setup'],
      },
      {
        cueId: 'cue/pivot',
        label: 'Rotate through the hinge',
        atMs: 14_000,
        holdMs: 650,
        decisive: true,
        explanation: 'The hinge passes the centerline without losing the reference edge.',
        frameRef: 'frame/pivot',
        diagramRef: 'diagram/pivot',
        factIds: ['fact/pivot'],
      },
      {
        cueId: 'cue/result',
        label: 'Verify the landed geometry',
        atMs: 18_000,
        holdMs: 900,
        decisive: true,
        explanation: 'The reference edge and hinge now share the declared final alignment.',
        frameRef: 'frame/result',
        diagramRef: 'diagram/result',
        factIds: ['fact/result'],
      },
    ],
    frameRate: 25,
    allowedRates: [0.5, 1, 1.5],
    autoHold: {
      enabled: true,
      cueIds: ['cue/pivot', 'cue/result'],
    },
  };
  return structuredClone({ ...base, ...overrides });
}

export function observation(overrides = {}) {
  return {
    version: COACH_OBSERVATION_VERSION,
    observationId: 'observation/001',
    sessionId: 'player-session/001',
    packageDigest: PACKAGE_DIGEST,
    viewerProfileDigest: VIEWER_DIGEST,
    positionId: 'position/demo-turn',
    status: 'playing',
    positionMs: 1_000,
    durationMs: 10_000,
    rate: 1,
    paused: false,
    connected: true,
    observedAt: '2026-08-05T19:00:00.000Z',
    ...overrides,
  };
}
