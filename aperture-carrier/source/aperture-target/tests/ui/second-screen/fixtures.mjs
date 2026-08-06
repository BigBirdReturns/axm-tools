import * as secondScreen from '../../../clients/second-screen/index.mjs';

export const PACKAGE_DIGEST = 'a'.repeat(64);
export const VIEWER_DIGEST = 'b'.repeat(64);
export const DEVICE_DIGEST = 'c'.repeat(64);
export const COACH_SOURCE_DIGEST = 'd'.repeat(64);

export function pairingProjection(overrides = {}) {
  return {
    version: secondScreen.PAIRING_PROJECTION_VERSION,
    pairingId: 'pairing/household/001',
    pairingRevision: 3,
    deviceId: 'device/handset/001',
    deviceDigest: DEVICE_DIGEST,
    deviceClass: 'handset',
    sharedDevice: true,
    viewerProfileId: 'viewer/alice',
    viewerProfileDigest: VIEWER_DIGEST,
    viewerSelectionReceiptRef: 'pairing-selection/001',
    authState: 'paired',
    authorizedScopes: [
      'read:anchor',
      'read:context',
      'read:coach',
      'read:provenance',
      'request:query',
      'request:selection',
    ],
    issuedAt: '2026-08-05T21:00:00Z',
    expiresAt: '2027-08-05T21:00:00Z',
    reasonCode: '',
    accessReceiptRefs: ['access/pairing/001'],
    ...overrides,
  };
}

export function coachProjection(overrides = {}) {
  return {
    version: secondScreen.SECOND_SCREEN_COACH_PROJECTION_VERSION,
    sourceVersion: 'axm-aperture-coach-view/1',
    projectionId: 'coach-projection/001',
    sourceDigest: COACH_SOURCE_DIGEST,
    storyPackageDigest: PACKAGE_DIGEST,
    viewerProfileDigest: VIEWER_DIGEST,
    status: 'ready',
    reasonCode: '',
    cueId: 'cue/arrival/001',
    cueLabel: 'Arrival at the gate',
    presentationMode: 'motion',
    observationId: 'coach-observation/001',
    pendingIntentIds: [],
    deliveryReceiptIds: [],
    ...overrides,
  };
}

export function surface(state = 'ready', overrides = {}) {
  return {
    state,
    reasonCode: state === 'ready' ? '' : `${state}-surface`,
    label: 'Surface label',
    summary: state === 'ready' ? 'Verified external projection.' : '',
    coordinateRefs: ['coordinate/001'],
    accessReceiptRefs: ['access/surface/001'],
    ...overrides,
  };
}

export function secondScreenSnapshot(overrides = {}) {
  return {
    version: secondScreen.SECOND_SCREEN_SNAPSHOT_VERSION,
    snapshotId: 'snapshot/001',
    sequence: 10,
    storyPackageId: 'story-package/origami/001',
    storyPackageDigest: PACKAGE_DIGEST,
    viewerProfileId: 'viewer/alice',
    viewerProfileDigest: VIEWER_DIGEST,
    deviceId: 'device/handset/001',
    deviceDigest: DEVICE_DIGEST,
    pairingId: 'pairing/household/001',
    pairingRevision: 3,
    state: 'ready',
    reasonCode: '',
    observedAt: '2026-08-05T21:00:10Z',
    anchor: {
      anchorId: 'anchor/001',
      workId: 'work/origami/001',
      positionId: 'position/gate/001',
      confidence: 'exact',
      source: 'provider',
      observedAt: '2026-08-05T21:00:09Z',
    },
    surfaces: {
      anchor: surface('ready', { label: 'Anchor', coordinateRefs: ['anchor-coordinate/001'] }),
      context: surface('ready', { label: 'Context' }),
      query: surface('ready', { label: 'Query', coordinateRefs: ['query-coordinate/001'] }),
      selection: surface('ready', { label: 'Selection', coordinateRefs: ['selection-coordinate/001'] }),
      provenance: surface('ready', { label: 'Provenance' }),
      control: surface('unavailable', {
        label: 'Control',
        reasonCode: 'no-direct-actuation',
        coordinateRefs: ['control-coordinate/001'],
      }),
    },
    coachProjection: coachProjection(),
    accessReceiptRefs: ['access/snapshot/001'],
    ...overrides,
  };
}

export function connectionObservation(overrides = {}) {
  return {
    version: secondScreen.CONNECTION_OBSERVATION_VERSION,
    observationId: 'connection-observation/001',
    connectionSessionId: 'connection-session/001',
    state: 'connected',
    pairingId: 'pairing/household/001',
    pairingRevision: 3,
    deviceDigest: DEVICE_DIGEST,
    viewerProfileDigest: VIEWER_DIGEST,
    observedAt: '2026-08-05T21:00:08Z',
    serverSequence: 10,
    acknowledgedIntentId: '',
    reasonCode: '',
    ...overrides,
  };
}

export function viewportObservation(overrides = {}) {
  return {
    version: secondScreen.VIEWPORT_OBSERVATION_VERSION,
    observationId: 'viewport/001',
    widthCssPx: 390,
    heightCssPx: 844,
    inputMode: 'touch',
    observedAt: '2026-08-05T21:00:00Z',
    ...overrides,
  };
}

export function request(kind, coordinateRef, requestedAt = '2026-08-05T21:00:12Z') {
  return { type: 'request', kind, coordinateRef, requestedAt };
}

export function delivery(intent, overrides = {}) {
  return {
    version: secondScreen.SECOND_SCREEN_DELIVERY_VERSION,
    receiptId: 'delivery/001',
    intentId: intent.intentId,
    connectionSessionId: intent.connectionSessionId,
    status: 'delivered',
    reasonCode: '',
    deliveredAt: '2026-08-05T21:00:13Z',
    ...overrides,
  };
}

export function readyState({
  pairing = pairingProjection(),
  connection = connectionObservation(),
  snapshot = secondScreenSnapshot(),
  viewport = viewportObservation(),
} = {}) {
  let state = secondScreen.createSecondScreenState({ pairing, viewport });
  state = secondScreen.reduceSecondScreen(state, { type: 'connection-observed', observation: connection });
  state = secondScreen.reduceSecondScreen(state, { type: 'snapshot-observed', snapshot });
  return state;
}
