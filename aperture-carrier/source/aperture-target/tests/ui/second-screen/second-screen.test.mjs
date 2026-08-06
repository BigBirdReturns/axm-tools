import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import test from 'node:test';

import * as secondScreen from '../../../clients/second-screen/index.mjs';
import {
  DEVICE_DIGEST,
  PACKAGE_DIGEST,
  VIEWER_DIGEST,
  connectionObservation,
  delivery,
  pairingProjection,
  readyState,
  request,
  secondScreenSnapshot,
  surface,
  viewportObservation,
} from './fixtures.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE_ROOT = resolve(HERE, '../../../clients/second-screen');
const OTHER_DIGEST = 'e'.repeat(64);

function unpairedProjection(overrides = {}) {
  return pairingProjection({
    viewerProfileId: '',
    viewerProfileDigest: '',
    viewerSelectionReceiptRef: '',
    authState: 'unpaired',
    authorizedScopes: [],
    reasonCode: 'not-paired',
    ...overrides,
  });
}

function revokedProjection(overrides = {}) {
  return pairingProjection({
    pairingRevision: 4,
    viewerProfileId: '',
    viewerProfileDigest: '',
    viewerSelectionReceiptRef: '',
    authState: 'revoked',
    authorizedScopes: [],
    reasonCode: 'pairing-revoked',
    ...overrides,
  });
}

function expiredProjection(overrides = {}) {
  return pairingProjection({
    pairingRevision: 4,
    viewerProfileId: '',
    viewerProfileDigest: '',
    viewerSelectionReceiptRef: '',
    authState: 'expired',
    authorizedScopes: [],
    reasonCode: 'pairing-expired',
    ...overrides,
  });
}

function observeConnection(state, overrides = {}) {
  return secondScreen.reduceSecondScreen(state, {
    type: 'connection-observed',
    observation: connectionObservation(overrides),
  });
}

function observeSnapshot(state, overrides = {}) {
  return secondScreen.reduceSecondScreen(state, {
    type: 'snapshot-observed',
    snapshot: secondScreenSnapshot(overrides),
  });
}

function requestIntent(state, kind, coordinateRef, requestedAt = '2026-08-05T21:00:12Z') {
  return secondScreen.reduceSecondScreen(state, request(kind, coordinateRef, requestedAt));
}

function deepFrozen(value) {
  if (value === null || typeof value !== 'object') return true;
  if (!Object.isFrozen(value)) return false;
  return Object.values(value).every(deepFrozen);
}

function assertThrowsCode(fn, code) {
  assert.throws(fn, (error) => error?.code === code || error?.message === code);
}

// 1
test('paired projection makes device and viewer scope explicit', () => {
  const pairing = secondScreen.validatePairingProjection(pairingProjection());
  assert.equal(pairing.authState, 'paired');
  assert.equal(pairing.deviceId, 'device/handset/001');
  assert.equal(pairing.viewerProfileId, 'viewer/alice');
  assert.equal(pairing.viewerSelectionReceiptRef, 'pairing-selection/001');
  assert.ok(pairing.authorizedScopes.includes('read:anchor'));
});

// 2
test('shared paired device without explicit viewer selection refuses', () => {
  assertThrowsCode(
    () => secondScreen.validatePairingProjection(pairingProjection({ viewerSelectionReceiptRef: '' })),
    'shared_device_explicit_viewer_required',
  );
});

// 3
test('unpaired projection cannot retain API scopes', () => {
  assertThrowsCode(
    () => secondScreen.validatePairingProjection(unpairedProjection({ authorizedScopes: ['read:anchor'] })),
    'unpaired_scope_authority_forbidden',
  );
});

// 4
test('wildcard and unknown pairing scope fail closed', () => {
  assertThrowsCode(
    () => secondScreen.validatePairingProjection(pairingProjection({ authorizedScopes: ['read:anchor', '*'] })),
    'pairing_scope_unsupported',
  );
});

// 5
test('credential-shaped fields are rejected recursively', () => {
  assertThrowsCode(
    () => secondScreen.validatePairingProjection({ ...pairingProjection(), token: 'nope' }),
    'credential_field_forbidden',
  );
});

// 6
test('nonpaired projection cannot retain viewer identity', () => {
  assertThrowsCode(
    () => secondScreen.validatePairingProjection(unpairedProjection({ viewerProfileId: 'viewer/alice', viewerProfileDigest: VIEWER_DIGEST })),
    'nonpaired_viewer_scope_forbidden',
  );
});

// 7
test('initial selected surface is closed to the declared surface vocabulary', () => {
  assert.throws(() => secondScreen.createSecondScreenState({ selectedSurface: 'chat' }), /selected_surface_invalid/);
  const state = secondScreen.createSecondScreenState();
  assert.equal(state.selectedSurface, 'anchor');
});

// 8
test('unpaired view exposes no substantive API surface', () => {
  const state = secondScreen.createSecondScreenState({ pairing: unpairedProjection() });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.pairedScope, null);
  assert.equal(view.substantiveVisible, false);
  assert.equal(view.surfaces, null);
  assert.equal(view.actions.query.enabled, false);
});

// 9
test('connected paired snapshot projects exact scope and anchor', () => {
  const view = secondScreen.projectSecondScreenView(readyState());
  assert.equal(view.dataState, 'ready');
  assert.equal(view.pairedScope.viewerProfileDigest, VIEWER_DIGEST);
  assert.equal(view.identities.storyPackageDigest, PACKAGE_DIGEST);
  assert.equal(view.anchor.anchorId, 'anchor/001');
  assert.equal(view.substantiveVisible, true);
});

// 10
test('snapshot viewer substitution refuses', () => {
  const pairing = pairingProjection();
  assertThrowsCode(
    () => secondScreen.validateSecondScreenSnapshot(secondScreenSnapshot({ viewerProfileId: 'viewer/bob', viewerProfileDigest: OTHER_DIGEST }), secondScreen.validatePairingProjection(pairing)),
    'snapshot_viewer_scope_mismatch',
  );
});

// 11
test('snapshot device substitution refuses', () => {
  const pairing = secondScreen.validatePairingProjection(pairingProjection());
  assertThrowsCode(
    () => secondScreen.validateSecondScreenSnapshot(secondScreenSnapshot({ deviceId: 'device/handset/002', deviceDigest: OTHER_DIGEST }), pairing),
    'snapshot_device_scope_mismatch',
  );
});

// 12
test('snapshot pairing revision substitution refuses', () => {
  const pairing = secondScreen.validatePairingProjection(pairingProjection());
  assertThrowsCode(
    () => secondScreen.validateSecondScreenSnapshot(secondScreenSnapshot({ pairingRevision: 2 }), pairing),
    'snapshot_pairing_scope_mismatch',
  );
});

// 13
test('snapshot without connected observation refuses', () => {
  const state = secondScreen.createSecondScreenState({ pairing: pairingProjection() });
  const next = observeSnapshot(state);
  assert.equal(next.refusal.code, 'snapshot_without_connected_observation');
  assert.equal(next.snapshot, null);
});

// 14
test('snapshot older than connection server sequence refuses', () => {
  let state = secondScreen.createSecondScreenState({ pairing: pairingProjection() });
  state = observeConnection(state, { serverSequence: 11 });
  state = observeSnapshot(state, { sequence: 10 });
  assert.equal(state.refusal.code, 'snapshot_behind_connection_sequence');
});

// 15
test('same sequence with different snapshot identity conflicts', () => {
  let state = readyState();
  state = observeSnapshot(state, { snapshotId: 'snapshot/002', anchor: { ...secondScreenSnapshot().anchor, anchorId: 'anchor/002' } });
  assert.equal(state.refusal.code, 'snapshot_sequence_identity_conflict');
  assert.equal(state.snapshot.snapshotId, 'snapshot/001');
});

// 16
test('same snapshot observation replays idempotently', () => {
  const state = readyState();
  const next = observeSnapshot(state);
  assert.equal(next, state);
});

// 17
test('disconnect preserves the last verified anchor as stale read-only context', () => {
  let state = readyState();
  state = observeConnection(state, {
    observationId: 'connection-observation/002',
    state: 'disconnected',
    reasonCode: 'network-lost',
    observedAt: '2026-08-05T21:01:00Z',
  });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(state.snapshot, null);
  assert.equal(view.offlineUseful, true);
  assert.equal(view.dataState, 'stale');
  assert.equal(view.anchor.anchorId, 'anchor/001');
  assert.equal(view.substantiveVisible, false);
});

// 18
test('disconnected presentation disables query selection and control', () => {
  let state = readyState();
  state = observeConnection(state, {
    observationId: 'connection-observation/002',
    state: 'disconnected',
    reasonCode: 'network-lost',
  });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.actions.query.enabled, false);
  assert.equal(view.actions.selection.enabled, false);
  assert.equal(view.actions.control.enabled, false);
  assert.equal(view.surfaces.context.state, 'stale');
});

// 19
test('reconnect requires a fresh snapshot before substantive presentation resumes', () => {
  let state = readyState();
  state = observeConnection(state, {
    observationId: 'connection-observation/002',
    state: 'disconnected',
    reasonCode: 'network-lost',
  });
  state = observeConnection(state, {
    observationId: 'connection-observation/003',
    state: 'connected',
    reasonCode: '',
    serverSequence: 11,
    observedAt: '2026-08-05T21:02:00Z',
  });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(state.snapshot, null);
  assert.equal(view.offlineUseful, true);
  assert.equal(view.substantiveVisible, false);
  assert.equal(view.actions.query.reasonCode, 'fresh-snapshot-required');
});

// 20
test('fresh snapshot after reconnect reconciles the updated anchor', () => {
  let state = readyState();
  state = observeConnection(state, {
    observationId: 'connection-observation/002',
    state: 'disconnected',
    reasonCode: 'network-lost',
  });
  state = observeConnection(state, {
    observationId: 'connection-observation/003',
    state: 'connected',
    reasonCode: '',
    serverSequence: 11,
  });
  state = observeSnapshot(state, {
    snapshotId: 'snapshot/002',
    sequence: 11,
    anchor: { ...secondScreenSnapshot().anchor, anchorId: 'anchor/002', positionId: 'position/hall/002' },
  });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.substantiveVisible, true);
  assert.equal(view.anchor.anchorId, 'anchor/002');
  assert.equal(view.dataState, 'ready');
});

// 21
test('connection session replacement expires pending intents', () => {
  let state = readyState();
  state = requestIntent(state, 'query', 'query-coordinate/001');
  const intent = secondScreen.pendingSecondScreenIntent(state, 'query');
  state = observeConnection(state, {
    observationId: 'connection-observation/new-session',
    connectionSessionId: 'connection-session/002',
    serverSequence: 11,
  });
  assert.equal(state.pendingIntents.length, 0);
  assert.ok(state.expiredIntents.some((entry) => entry.intentId === intent.intentId));
  assert.equal(state.snapshot, null);
});

// 22
test('late delivery settles expired evidence without reviving intent', () => {
  let state = readyState();
  state = requestIntent(state, 'query', 'query-coordinate/001');
  const intent = secondScreen.pendingSecondScreenIntent(state, 'query');
  state = observeConnection(state, {
    observationId: 'connection-observation/new-session',
    connectionSessionId: 'connection-session/002',
    serverSequence: 11,
  });
  state = secondScreen.reduceSecondScreen(state, { type: 'intent-delivered', delivery: delivery(intent) });
  assert.equal(state.pendingIntents.length, 0);
  assert.ok(state.expiredIntents.some((entry) => entry.intentId === intent.intentId));
  assert.equal(state.deliveryReceipts.length, 1);
});

// 23
test('query request emits bounded request intent without changing anchor', () => {
  let state = readyState();
  const anchorBefore = state.snapshot.anchor;
  state = requestIntent(state, 'query', 'query-coordinate/001');
  const intent = secondScreen.pendingSecondScreenIntent(state, 'query');
  assert.equal(intent.authority, 'request_only');
  assert.equal(intent.kind, 'query');
  assert.deepEqual(state.snapshot.anchor, anchorBefore);
});

// 24
test('selection request emits bounded intent without selection outcome', () => {
  let state = readyState();
  state = requestIntent(state, 'selection', 'selection-coordinate/001');
  const intent = secondScreen.pendingSecondScreenIntent(state, 'selection');
  assert.equal(intent.authority, 'request_only');
  assert.equal(intent.kind, 'selection');
  assert.equal(Object.hasOwn(intent, 'outcome'), false);
});

// 25
test('missing direct actuation remains useful and control is refused', () => {
  let state = readyState();
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.noDirectActuationUseful, true);
  assert.equal(view.anchor.anchorId, 'anchor/001');
  assert.equal(view.actions.control.enabled, false);
  state = requestIntent(state, 'control', 'control-coordinate/001');
  assert.equal(state.requestRefusal.code, 'direct_actuation_unavailable');
});

// 26
test('authorized control emits a request but delivery cannot claim actuation', () => {
  const pairing = pairingProjection({
    authorizedScopes: [...pairingProjection().authorizedScopes, 'request:control'],
  });
  const snapshot = secondScreenSnapshot({
    surfaces: {
      ...secondScreenSnapshot().surfaces,
      control: surface('ready', { label: 'Control', coordinateRefs: ['control-coordinate/001'] }),
    },
  });
  let state = readyState({ pairing, snapshot });
  state = requestIntent(state, 'control', 'control-coordinate/001');
  const intent = secondScreen.pendingSecondScreenIntent(state, 'control');
  assert.equal(intent.authority, 'request_only');
  state = secondScreen.reduceSecondScreen(state, { type: 'intent-delivered', delivery: delivery(intent) });
  assert.equal(state.deliveryReceipts[0].status, 'delivered');
  assert.equal(Object.hasOwn(state.deliveryReceipts[0], 'actuation'), false);
});

// 27
test('delivery for unknown intent produces local refusal only', () => {
  const state = readyState();
  const fake = delivery({ intentId: 'second-screen-intent/unknown', connectionSessionId: 'connection-session/001' });
  const next = secondScreen.reduceSecondScreen(state, { type: 'intent-delivered', delivery: fake });
  assert.equal(next.requestRefusal.code, 'delivery_intent_unknown');
  assert.equal(next.deliveryReceipts.length, 0);
});

// 28
test('revoked pairing removes API projection without deleting prior history by claim', () => {
  let state = readyState();
  state = secondScreen.reduceSecondScreen(state, { type: 'pairing-observed', pairing: revokedProjection() });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.pairingState, 'revoked');
  assert.equal(view.pairedScope, null);
  assert.equal(view.surfaces, null);
  assert.equal(Object.hasOwn(state, 'viewerHistory'), false);
});

// 29
test('pairing revision replacement clears connection snapshot and surface preference', () => {
  let state = readyState();
  state = secondScreen.reduceSecondScreen(state, { type: 'surface-selected', surfaceId: 'query' });
  state = secondScreen.reduceSecondScreen(state, {
    type: 'pairing-observed',
    pairing: pairingProjection({ pairingRevision: 4, accessReceiptRefs: ['access/pairing/002'] }),
  });
  assert.equal(state.connection, null);
  assert.equal(state.snapshot, null);
  assert.equal(state.lastVerifiedSnapshot, null);
  assert.equal(state.selectedSurface, 'anchor');
});

// 30
test('stale pairing revision cannot resurrect revoked authority', () => {
  let state = secondScreen.createSecondScreenState({ pairing: revokedProjection() });
  state = secondScreen.reduceSecondScreen(state, { type: 'pairing-observed', pairing: pairingProjection() });
  assert.equal(state.pairing.authState, 'revoked');
  assert.equal(state.refusal.code, 'pairing_revision_regression');
});

// 31
test('same pairing revision with changed scope identity conflicts', () => {
  let state = secondScreen.createSecondScreenState({ pairing: pairingProjection() });
  state = secondScreen.reduceSecondScreen(state, {
    type: 'pairing-observed',
    pairing: pairingProjection({ authorizedScopes: ['read:anchor', 'read:context'] }),
  });
  assert.equal(state.refusal.code, 'pairing_revision_identity_conflict');
});

// 32
test('exact pairing replay is idempotent and cannot clear unrelated refusal', () => {
  let state = secondScreen.createSecondScreenState({ pairing: pairingProjection() });
  state = secondScreen.reduceSecondScreen(state, { type: 'unsupported-event' });
  assert.equal(state.refusal.code, 'event_type_unsupported');
  const replay = secondScreen.reduceSecondScreen(state, { type: 'pairing-observed', pairing: pairingProjection() });
  assert.equal(replay, state);
  assert.equal(replay.refusal.code, 'event_type_unsupported');
});

// 33
test('connection observation with substituted device scope refuses', () => {
  const state = secondScreen.createSecondScreenState({ pairing: pairingProjection() });
  const next = observeConnection(state, { deviceDigest: OTHER_DIGEST });
  assert.equal(next.refusal.code, 'connection_scope_mismatch');
  assert.equal(next.connection, null);
});

// 34
test('malformed pairing becomes bounded refusal while prior authority remains', () => {
  const state = readyState();
  const next = secondScreen.reduceSecondScreen(state, {
    type: 'pairing-observed',
    pairing: { ...pairingProjection(), unexpected: true },
  });
  assert.equal(next.refusal.code, 'pairing_projection_fields_invalid');
  assert.equal(next.pairing.pairingId, state.pairing.pairingId);
  assert.equal(next.snapshot.snapshotId, state.snapshot.snapshotId);
});

// 35
test('malformed viewport becomes bounded request refusal', () => {
  const state = readyState();
  const next = secondScreen.reduceSecondScreen(state, {
    type: 'viewport-observed',
    observation: viewportObservation({ widthCssPx: 100 }),
  });
  assert.equal(next.requestRefusal.kind, 'viewport');
  assert.equal(next.requestRefusal.code, 'viewport_width_invalid');
  assert.equal(next.viewport.widthCssPx, state.viewport.widthCssPx);
});

// 36
test('same connection session cannot regress server sequence', () => {
  let state = readyState();
  state = observeConnection(state, {
    observationId: 'connection-observation/002',
    serverSequence: 9,
  });
  assert.equal(state.refusal.code, 'connection_sequence_regression');
});

// 37
test('one connection observation identity cannot carry changed content', () => {
  let state = readyState();
  state = observeConnection(state, {
    observationId: 'connection-observation/001',
    serverSequence: 11,
  });
  assert.equal(state.refusal.code, 'connection_observation_identity_conflict');
});

// 38
test('one snapshot identity cannot carry changed content', () => {
  let state = readyState();
  state = observeSnapshot(state, {
    snapshotId: 'snapshot/001',
    anchor: { ...secondScreenSnapshot().anchor, positionId: 'position/changed' },
  });
  assert.equal(state.refusal.code, 'snapshot_identity_conflict');
  assert.equal(state.snapshot.anchor.positionId, 'position/gate/001');
});

// 39
test('compact touch viewport produces compact touch layout', () => {
  const view = secondScreen.projectSecondScreenView(readyState());
  assert.equal(view.layoutClass, 'compact');
  assert.equal(view.inputMode, 'touch');
});

// 40
test('surface interactivity follows authorization and surface availability', () => {
  const view = secondScreen.projectSecondScreenView(readyState());
  assert.equal(view.surfaces.query.interactive, true);
  assert.equal(view.surfaces.selection.interactive, true);
  assert.equal(view.surfaces.control.interactive, false);
  assert.equal(view.actions.control.reasonCode, 'no-direct-actuation');
});

// 41
test('revoked and unpaired views withhold viewer identity', () => {
  const revoked = secondScreen.projectSecondScreenView(secondScreen.createSecondScreenState({ pairing: revokedProjection() }));
  const unpaired = secondScreen.projectSecondScreenView(secondScreen.createSecondScreenState({ pairing: unpairedProjection() }));
  assert.equal(revoked.pairedScope, null);
  assert.equal(unpaired.pairedScope, null);
});

// 42
test('medium keyboard viewport produces medium layout', () => {
  const state = readyState({ viewport: viewportObservation({ widthCssPx: 800, inputMode: 'keyboard' }) });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.layoutClass, 'medium');
  assert.equal(view.inputMode, 'keyboard');
});

// 43
test('large controller layout retains stable focus order', () => {
  const state = readyState({ viewport: viewportObservation({ widthCssPx: 1440, heightCssPx: 900, inputMode: 'controller' }) });
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(view.layoutClass, 'large');
  assert.equal(view.inputMode, 'controller');
  assert.deepEqual(view.focusOrder, [
    'viewer-scope', 'device-scope', 'anchor', 'context', 'coach', 'query', 'selection', 'provenance', 'control',
  ]);
});

// 44
test('pairing lifecycle states remain machine-distinct', () => {
  const paired = secondScreen.projectSecondScreenView(secondScreen.createSecondScreenState({ pairing: pairingProjection() }));
  const unpaired = secondScreen.projectSecondScreenView(secondScreen.createSecondScreenState({ pairing: unpairedProjection() }));
  const revoked = secondScreen.projectSecondScreenView(secondScreen.createSecondScreenState({ pairing: revokedProjection() }));
  const expired = secondScreen.projectSecondScreenView(secondScreen.createSecondScreenState({ pairing: expiredProjection() }));
  assert.deepEqual(new Set([paired.pairingState, unpaired.pairingState, revoked.pairingState, expired.pairingState]), new Set(['paired', 'unpaired', 'revoked', 'expired']));
  assert.equal(revoked.accessibleRole, 'alert');
  assert.equal(expired.accessibleRole, 'alert');
});

// 45
test('ready and every degraded snapshot state remain distinct', () => {
  const states = secondScreen.DATA_STATES;
  const projected = states.map((dataState, index) => {
    const snapshot = secondScreenSnapshot({
      snapshotId: `snapshot/state/${index}`,
      state: dataState,
      reasonCode: dataState === 'ready' ? '' : `${dataState}-snapshot`,
    });
    return secondScreen.projectSecondScreenView(readyState({ snapshot })).dataState;
  });
  assert.deepEqual(projected, states);
});

// 46
test('validated state and projected view are deeply immutable', () => {
  const state = readyState();
  const view = secondScreen.projectSecondScreenView(state);
  assert.equal(deepFrozen(state), true);
  assert.equal(deepFrozen(view), true);
  assert.throws(() => { state.pairing.deviceId = 'mutated'; }, TypeError);
  assert.throws(() => { view.actions.query.enabled = false; }, TypeError);
});

// 47
test('transitions own cloned input trees', () => {
  const rawPairing = pairingProjection();
  const state = secondScreen.createSecondScreenState({ pairing: rawPairing });
  rawPairing.deviceId = 'device/mutated';
  rawPairing.authorizedScopes.push('request:control');
  assert.equal(state.pairing.deviceId, 'device/handset/001');
  assert.equal(state.pairing.authorizedScopes.includes('request:control'), false);
});

// 48
test('intent identity is deterministic for exact history and changes with activation identity', () => {
  const first = requestIntent(readyState(), 'query', 'query-coordinate/001');
  const second = requestIntent(readyState(), 'query', 'query-coordinate/001');
  const changed = requestIntent(readyState(), 'query', 'query-coordinate/001', '2026-08-05T21:00:13Z');
  assert.equal(secondScreen.pendingSecondScreenIntent(first, 'query').intentId, secondScreen.pendingSecondScreenIntent(second, 'query').intentId);
  assert.notEqual(secondScreen.pendingSecondScreenIntent(first, 'query').intentId, secondScreen.pendingSecondScreenIntent(changed, 'query').intentId);
});

// 49
test('unadmitted coordinate is refused without widening authority', () => {
  const state = readyState();
  const next = requestIntent(state, 'query', 'coordinate/not-admitted');
  assert.equal(next.requestRefusal.code, 'request_coordinate_not_admitted');
  assert.equal(next.pendingIntents.length, 0);
  assert.deepEqual(next.snapshot, state.snapshot);
});

// 50
test('surface selection changes only presentation preference', () => {
  const state = readyState();
  const next = secondScreen.reduceSecondScreen(state, { type: 'surface-selected', surfaceId: 'provenance' });
  assert.equal(next.selectedSurface, 'provenance');
  assert.equal(next.snapshot.anchor.anchorId, state.snapshot.anchor.anchorId);
  assert.equal(next.pendingIntents.length, 0);
});

// 51
test('source contains no transport credential persistence biometric or player authority', () => {
  const source = ['contract.mjs', 'reducer.mjs', 'view-model.mjs', 'index.mjs']
    .map((name) => readFileSync(resolve(SOURCE_ROOT, name), 'utf8'))
    .join('\n');
  const forbidden = [
    /\bfetch\s*\(/,
    /\bWebSocket\b/,
    /\bXMLHttpRequest\b/,
    /\blocalStorage\b/,
    /\bsessionStorage\b/,
    /\bindexedDB\b/,
    /\bsetTimeout\s*\(/,
    /\bsetInterval\s*\(/,
    /\bcreateServer\s*\(/,
    /\bnet\.connect\s*\(/,
    /\bchild_process\b/,
    /\bexecFile\s*\(/,
    /\bspawn\s*\(/,
    /\bHTMLMediaElement\b/,
    /\.play\s*\(/,
    /\.pause\s*\(/,
    /\bbiometric\w*\s*:/i,
    /\bface(?:print|Id)\b/i,
    /\bvoiceprint\b/i,
  ];
  for (const pattern of forbidden) assert.doesNotMatch(source, pattern);
});

// 52
test('pure warm projection remains beneath the five millisecond P95 source budget', () => {
  const state = readyState();
  const samples = [];
  for (let index = 0; index < 3000; index += 1) {
    const start = performance.now();
    const view = secondScreen.projectSecondScreenView(state);
    assert.equal(view.version, secondScreen.SECOND_SCREEN_VIEW_VERSION);
    samples.push(performance.now() - start);
  }
  samples.sort((left, right) => left - right);
  const p95 = samples[Math.floor(samples.length * 0.95)];
  console.log(`SECOND_SCREEN_WARM_P95_MS=${p95.toFixed(6)}`);
  assert.ok(p95 < 5, `warm projection P95 ${p95}ms exceeded 5ms source budget`);
});
