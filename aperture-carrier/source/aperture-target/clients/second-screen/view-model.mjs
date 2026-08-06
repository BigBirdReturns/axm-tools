import {
  SECOND_SCREEN_VIEW_VERSION,
  cloneOwned,
} from './contract.mjs';

function layoutFor(viewport) {
  if (viewport.widthCssPx < 600) return 'compact';
  if (viewport.widthCssPx < 1100) return 'medium';
  return 'large';
}

function scopeFor(kind) {
  if (kind === 'refresh') return 'read:anchor';
  return `request:${kind}`;
}

function surfaceFor(kind) {
  return kind === 'refresh' ? 'anchor' : kind;
}

function actionState(state, kind) {
  const pairing = state.pairing;
  const connection = state.connection;
  const snapshot = state.snapshot;
  if (!pairing || pairing.authState !== 'paired') return { enabled: false, reasonCode: 'pairing-unavailable' };
  if (!connection || connection.state !== 'connected') return { enabled: false, reasonCode: 'connection-unavailable' };
  if (!snapshot) return { enabled: false, reasonCode: 'fresh-snapshot-required' };
  const scope = scopeFor(kind);
  if (!pairing.authorizedScopes.includes(scope)) {
    return { enabled: false, reasonCode: kind === 'control' ? 'no-direct-actuation' : 'scope-unavailable' };
  }
  const surface = snapshot.surfaces[surfaceFor(kind)];
  if (!surface || !['ready', 'partial'].includes(surface.state)) {
    return { enabled: false, reasonCode: kind === 'control' ? 'no-direct-actuation' : 'surface-unavailable' };
  }
  return { enabled: true, reasonCode: '' };
}

export function projectSecondScreenView(state) {
  const pairingState = state.pairing?.authState ?? 'unpaired';
  const connectionState = state.connection?.state ?? 'disconnected';
  const fresh = pairingState === 'paired' && connectionState === 'connected' && Boolean(state.snapshot);
  const staleUseful = pairingState === 'paired' && !fresh && Boolean(state.lastVerifiedSnapshot);
  const displaySnapshot = fresh ? state.snapshot : staleUseful ? state.lastVerifiedSnapshot : null;

  let dataState = 'unavailable';
  let reasonCode = 'pairing-unavailable';
  if (state.refusal) {
    dataState = 'refused';
    reasonCode = state.refusal.code;
  } else if (pairingState === 'revoked' || pairingState === 'expired') {
    dataState = pairingState;
    reasonCode = state.pairing.reasonCode;
  } else if (pairingState !== 'paired') {
    dataState = 'unavailable';
    reasonCode = state.pairing?.reasonCode || 'pairing-unavailable';
  } else if (fresh) {
    dataState = state.snapshot.state;
    reasonCode = state.snapshot.reasonCode;
  } else if (staleUseful) {
    dataState = 'stale';
    reasonCode = state.connection?.reasonCode || 'connection-stale';
  } else {
    dataState = connectionState === 'connected' ? 'partial' : 'disconnected';
    reasonCode = connectionState === 'connected' ? 'fresh-snapshot-required' : 'connection-unavailable';
  }

  const actions = {
    refresh: actionState(state, 'refresh'),
    query: actionState(state, 'query'),
    selection: actionState(state, 'selection'),
    control: actionState(state, 'control'),
  };
  const surfaces = displaySnapshot
    ? Object.fromEntries(
        Object.entries(displaySnapshot.surfaces).map(([surfaceId, surface]) => {
          const action = surfaceId === 'anchor'
            ? actions.refresh
            : surfaceId === 'query'
              ? actions.query
              : surfaceId === 'selection'
                ? actions.selection
                : surfaceId === 'control'
                  ? actions.control
                  : { enabled: fresh, reasonCode: fresh ? '' : 'stale-read-only' };
          return [surfaceId, {
            ...surface,
            state: staleUseful && surface.state === 'ready' ? 'stale' : surface.state,
            interactive: fresh && action.enabled,
          }];
        }),
      )
    : null;

  const alertStates = new Set(['refused', 'conflict', 'revoked', 'expired']);
  return cloneOwned({
    version: SECOND_SCREEN_VIEW_VERSION,
    layoutClass: layoutFor(state.viewport),
    inputMode: state.viewport.inputMode,
    selectedSurface: state.selectedSurface,
    pairingState,
    connectionState,
    dataState,
    reasonCode,
    accessibleRole: alertStates.has(dataState) ? 'alert' : 'status',
    pairedScope: pairingState === 'paired'
      ? {
          pairingId: state.pairing.pairingId,
          pairingRevision: state.pairing.pairingRevision,
          deviceId: state.pairing.deviceId,
          deviceDigest: state.pairing.deviceDigest,
          deviceClass: state.pairing.deviceClass,
          sharedDevice: state.pairing.sharedDevice,
          viewerProfileId: state.pairing.viewerProfileId,
          viewerProfileDigest: state.pairing.viewerProfileDigest,
          viewerSelectionReceiptRef: state.pairing.viewerSelectionReceiptRef,
          authorizedScopes: state.pairing.authorizedScopes,
        }
      : null,
    substantiveVisible: fresh,
    offlineUseful: staleUseful,
    noDirectActuationUseful: Boolean(displaySnapshot && !actions.control.enabled),
    anchor: displaySnapshot?.anchor ?? null,
    coachProjection: displaySnapshot?.coachProjection ?? null,
    surfaces,
    actions,
    focusOrder: [
      'viewer-scope',
      'device-scope',
      'anchor',
      'context',
      'coach',
      'query',
      'selection',
      'provenance',
      'control',
    ],
    pendingIntentIds: state.pendingIntents.map((intent) => intent.intentId),
    expiredIntentIds: state.expiredIntents.map((intent) => intent.intentId),
    deliveryReceiptIds: state.deliveryReceipts.map((receipt) => receipt.receiptId),
    requestRefusal: state.requestRefusal,
    identities: displaySnapshot
      ? {
          snapshotId: displaySnapshot.snapshotId,
          snapshotSequence: displaySnapshot.sequence,
          storyPackageId: displaySnapshot.storyPackageId,
          storyPackageDigest: displaySnapshot.storyPackageDigest,
          anchorId: displaySnapshot.anchor.anchorId,
          coachProjectionId: displaySnapshot.coachProjection.projectionId,
        }
      : null,
  });
}
