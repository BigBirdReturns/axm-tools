import {
  CONNECTION_OBSERVATION_VERSION,
  REQUEST_KINDS,
  SECOND_SCREEN_DELIVERY_VERSION,
  SECOND_SCREEN_INTENT_VERSION,
  SECOND_SCREEN_STATE_VERSION,
  SECOND_SCREEN_SURFACES,
  cloneOwned,
  sha256Json,
  validateConnectionObservation,
  validateDeliveryReceipt,
  validatePairingProjection,
  validateSecondScreenSnapshot,
  validateViewportObservation,
} from './contract.mjs';

const DEFAULT_VIEWPORT = Object.freeze({
  version: 'axm-aperture-second-screen-viewport/1',
  observationId: 'viewport/default',
  widthCssPx: 390,
  heightCssPx: 844,
  inputMode: 'touch',
  observedAt: '1970-01-01T00:00:00Z',
});

function withState(state, patch) {
  return cloneOwned({ ...state, ...patch });
}

function refusal(code, details = {}) {
  return { code, details };
}

function refuse(state, code, details = {}) {
  return withState(state, { refusal: refusal(code, details) });
}

function requestRefuse(state, kind, code, details = {}) {
  return withState(state, { requestRefusal: { kind, code, details } });
}

function expirePending(state) {
  return {
    pendingIntents: [],
    expiredIntents: [...state.expiredIntents, ...state.pendingIntents],
  };
}

function pairingIdentity(pairing) {
  return pairing ? sha256Json(pairing) : '';
}

function connectionIdentity(connection) {
  return connection ? sha256Json(connection) : '';
}

function snapshotIdentity(snapshot) {
  return snapshot ? sha256Json(snapshot) : '';
}

export function createSecondScreenState({ pairing = null, viewport = DEFAULT_VIEWPORT, selectedSurface = 'anchor' } = {}) {
  if (!SECOND_SCREEN_SURFACES.includes(selectedSurface)) throw new TypeError('selected_surface_invalid');
  const validatedPairing = pairing === null ? null : validatePairingProjection(pairing);
  const validatedViewport = validateViewportObservation(viewport);
  return cloneOwned({
    version: SECOND_SCREEN_STATE_VERSION,
    pairing: validatedPairing,
    connection: null,
    snapshot: null,
    lastVerifiedSnapshot: null,
    viewport: validatedViewport,
    selectedSurface,
    pendingIntents: [],
    expiredIntents: [],
    deliveryReceipts: [],
    refusal: null,
    requestRefusal: null,
  });
}

function pairingObserved(state, rawPairing) {
  let pairing;
  try {
    pairing = validatePairingProjection(rawPairing);
  } catch (error) {
    return refuse(state, error.code ?? error.message);
  }
  const prior = state.pairing;
  if (prior && pairing.pairingId === prior.pairingId) {
    if (pairing.pairingRevision < prior.pairingRevision) return refuse(state, 'pairing_revision_regression');
    if (pairing.pairingRevision === prior.pairingRevision) {
      if (pairingIdentity(pairing) !== pairingIdentity(prior)) return refuse(state, 'pairing_revision_identity_conflict');
      return state;
    }
  }
  const expired = expirePending(state);
  return withState(state, {
    ...expired,
    pairing,
    connection: null,
    snapshot: null,
    lastVerifiedSnapshot: null,
    selectedSurface: 'anchor',
    requestRefusal: null,
    refusal: null,
  });
}

function connectionObserved(state, rawObservation) {
  let observation;
  try {
    observation = validateConnectionObservation(rawObservation, state.pairing);
  } catch (error) {
    return refuse(state, error.code ?? error.message);
  }
  const prior = state.connection;
  if (prior && observation.connectionSessionId === prior.connectionSessionId) {
    if (observation.observationId === prior.observationId) {
      if (connectionIdentity(observation) !== connectionIdentity(prior)) {
        return refuse(state, 'connection_observation_identity_conflict');
      }
      return state;
    }
    if (observation.serverSequence < prior.serverSequence) return refuse(state, 'connection_sequence_regression');
  }

  const sessionChanged = Boolean(prior && prior.connectionSessionId !== observation.connectionSessionId);
  const expired = sessionChanged ? expirePending(state) : {
    pendingIntents: state.pendingIntents,
    expiredIntents: state.expiredIntents,
  };
  const remainsConnected = observation.state === 'connected';
  const lastVerifiedSnapshot = state.snapshot ?? state.lastVerifiedSnapshot;
  return withState(state, {
    ...expired,
    connection: observation,
    snapshot: remainsConnected && !sessionChanged ? state.snapshot : null,
    lastVerifiedSnapshot,
    requestRefusal: null,
    refusal: null,
  });
}

function snapshotObserved(state, rawSnapshot) {
  if (!state.connection || state.connection.state !== 'connected') {
    return refuse(state, 'snapshot_without_connected_observation');
  }
  let snapshot;
  try {
    snapshot = validateSecondScreenSnapshot(rawSnapshot, state.pairing);
  } catch (error) {
    return refuse(state, error.code ?? error.message);
  }
  if (snapshot.sequence < state.connection.serverSequence) return refuse(state, 'snapshot_behind_connection_sequence');
  const prior = state.snapshot;
  if (prior) {
    if (snapshot.snapshotId === prior.snapshotId) {
      if (snapshotIdentity(snapshot) !== snapshotIdentity(prior)) return refuse(state, 'snapshot_identity_conflict');
      return state;
    }
    if (snapshot.sequence < prior.sequence) return refuse(state, 'snapshot_sequence_regression');
    if (snapshot.sequence === prior.sequence) return refuse(state, 'snapshot_sequence_identity_conflict');
  }
  return withState(state, {
    snapshot,
    lastVerifiedSnapshot: snapshot,
    requestRefusal: null,
    refusal: null,
  });
}

function viewportObserved(state, rawObservation) {
  try {
    return withState(state, {
      viewport: validateViewportObservation(rawObservation),
      requestRefusal: null,
    });
  } catch (error) {
    return requestRefuse(state, 'viewport', error.code ?? error.message);
  }
}

function selectSurface(state, surfaceId) {
  if (!SECOND_SCREEN_SURFACES.includes(surfaceId)) return requestRefuse(state, 'surface', 'selected_surface_invalid');
  return withState(state, { selectedSurface: surfaceId, requestRefusal: null });
}

function requiredScope(kind) {
  if (kind === 'refresh') return 'read:anchor';
  return `request:${kind}`;
}

function surfaceForKind(kind) {
  return kind === 'refresh' ? 'anchor' : kind;
}

function requestIntent(state, event) {
  const kind = event.kind;
  if (!REQUEST_KINDS.includes(kind)) return requestRefuse(state, 'request', 'request_kind_invalid');
  if (typeof event.coordinateRef !== 'string' || event.coordinateRef.length === 0) {
    return requestRefuse(state, kind, 'request_coordinate_invalid');
  }
  if (typeof event.requestedAt !== 'string') return requestRefuse(state, kind, 'request_time_invalid');
  if (!state.pairing || state.pairing.authState !== 'paired') return requestRefuse(state, kind, 'request_pairing_unavailable');
  if (!state.connection || state.connection.state !== 'connected') return requestRefuse(state, kind, 'request_connection_unavailable');
  if (!state.snapshot) return requestRefuse(state, kind, 'request_snapshot_unavailable');
  const scope = requiredScope(kind);
  if (!state.pairing.authorizedScopes.includes(scope)) {
    return requestRefuse(state, kind, kind === 'control' ? 'direct_actuation_unavailable' : 'request_scope_missing');
  }
  const surfaceId = surfaceForKind(kind);
  const surface = state.snapshot.surfaces[surfaceId];
  if (!surface || !['ready', 'partial'].includes(surface.state)) {
    return requestRefuse(state, kind, kind === 'control' ? 'direct_actuation_unavailable' : 'request_surface_unavailable');
  }
  if (!surface.coordinateRefs.includes(event.coordinateRef)) {
    return requestRefuse(state, kind, 'request_coordinate_not_admitted');
  }
  const identity = {
    version: SECOND_SCREEN_INTENT_VERSION,
    kind,
    coordinateRef: event.coordinateRef,
    requestedAt: event.requestedAt,
    pairingId: state.pairing.pairingId,
    pairingRevision: state.pairing.pairingRevision,
    connectionSessionId: state.connection.connectionSessionId,
    snapshotId: state.snapshot.snapshotId,
    snapshotSequence: state.snapshot.sequence,
    viewerProfileDigest: state.pairing.viewerProfileDigest,
    deviceDigest: state.pairing.deviceDigest,
  };
  const intent = cloneOwned({
    ...identity,
    intentId: `second-screen-intent/${sha256Json(identity)}`,
    authority: 'request_only',
  });
  if (state.pendingIntents.some((entry) => entry.intentId === intent.intentId)) {
    return withState(state, { requestRefusal: null });
  }
  return withState(state, {
    pendingIntents: [...state.pendingIntents, intent],
    requestRefusal: null,
  });
}

function deliveryObserved(state, rawDelivery) {
  let delivery;
  try {
    delivery = validateDeliveryReceipt(rawDelivery);
  } catch (error) {
    return requestRefuse(state, 'delivery', error.code ?? error.message);
  }
  const existing = state.deliveryReceipts.find((entry) => entry.receiptId === delivery.receiptId);
  if (existing) {
    if (sha256Json(existing) !== sha256Json(delivery)) return requestRefuse(state, 'delivery', 'delivery_receipt_identity_conflict');
    return state;
  }
  const pending = state.pendingIntents.find((entry) => entry.intentId === delivery.intentId);
  const expired = state.expiredIntents.find((entry) => entry.intentId === delivery.intentId);
  const intent = pending ?? expired;
  if (!intent) return requestRefuse(state, 'delivery', 'delivery_intent_unknown');
  if (delivery.connectionSessionId !== intent.connectionSessionId) {
    return requestRefuse(state, 'delivery', 'delivery_connection_session_mismatch');
  }
  return withState(state, {
    pendingIntents: state.pendingIntents.filter((entry) => entry.intentId !== delivery.intentId),
    deliveryReceipts: [...state.deliveryReceipts, delivery],
    requestRefusal: null,
  });
}

export function reduceSecondScreen(state, event) {
  if (!state || state.version !== SECOND_SCREEN_STATE_VERSION) throw new TypeError('second_screen_state_invalid');
  if (!event || typeof event !== 'object') return refuse(state, 'event_invalid');
  if (event.type === 'pairing-observed') return pairingObserved(state, event.pairing);
  if (event.type === 'connection-observed') return connectionObserved(state, event.observation);
  if (event.type === 'snapshot-observed') return snapshotObserved(state, event.snapshot);
  if (event.type === 'viewport-observed') return viewportObserved(state, event.observation);
  if (event.type === 'surface-selected') return selectSurface(state, event.surfaceId);
  if (event.type === 'request') return requestIntent(state, event);
  if (event.type === 'intent-delivered') return deliveryObserved(state, event.delivery);
  return refuse(state, 'event_type_unsupported');
}

export function pendingSecondScreenIntent(state, kind) {
  return state.pendingIntents.find((intent) => intent.kind === kind) ?? null;
}
