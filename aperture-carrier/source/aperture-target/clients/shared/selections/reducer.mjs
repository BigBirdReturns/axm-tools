import {
  SELECTION_STATE_VERSION,
  buildSelectionActivation,
  canonicalJson,
  cloneOwned,
  validateActuationObservation,
  validateSelectionContext,
  validateSelectionDelivery,
  validateSelectionReceipt,
} from './contract.mjs';

function refusal(stage, error) {
  return Object.freeze({ stage, code: error?.code ?? 'selection_transaction_refused' });
}

function expireIntent(intent, reasonCode) {
  return Object.freeze({ ...structuredClone(intent), expiredReason: reasonCode });
}

export function createSelectionState(contextValue) {
  const context = validateSelectionContext(contextValue);
  return cloneOwned({
    version: SELECTION_STATE_VERSION,
    context,
    selection: null,
    declinedSelectionIds: [],
    currentIntent: null,
    fallback: null,
    deliveries: [],
    actuationObservation: null,
    expiredIntents: [],
    staleTransaction: null,
    refusal: null,
    activationRefusal: null,
  });
}

export function replaceSelectionContext(stateValue, contextValue) {
  const state = cloneOwned(stateValue);
  let context;
  try {
    context = validateSelectionContext(contextValue);
  } catch (error) {
    return cloneOwned({ ...state, refusal: refusal('context', error) });
  }
  if (context.contextId === state.context.contextId) {
    if (canonicalJson(context) !== canonicalJson(state.context)) {
      return cloneOwned({ ...state, refusal: { stage: 'context', code: 'selection_context_identity_conflict' } });
    }
    return state;
  }
  if (
    context.storyPackageDigest === state.context.storyPackageDigest &&
    context.viewerProfileDigest === state.context.viewerProfileDigest &&
    context.sequence < state.context.sequence
  ) {
    return cloneOwned({ ...state, refusal: { stage: 'context', code: 'selection_context_sequence_regression' } });
  }
  const staleTransaction = state.selection
    ? {
        context: state.context,
        selection: state.selection,
        intent: state.currentIntent,
        fallback: state.fallback,
        deliveries: state.deliveries,
        actuationObservation: state.actuationObservation,
        reasonCode: 'context-replaced',
      }
    : state.staleTransaction;
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'context-replaced')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    context,
    selection: null,
    currentIntent: null,
    fallback: null,
    deliveries: [],
    actuationObservation: null,
    expiredIntents,
    staleTransaction,
    refusal: null,
    activationRefusal: null,
  });
}

export function ingestSelectionReceipt(stateValue, receiptValue) {
  const state = cloneOwned(stateValue);
  let receipt;
  try {
    receipt = validateSelectionReceipt(receiptValue, state.context);
  } catch (error) {
    return cloneOwned({ ...state, refusal: refusal('selection', error) });
  }
  if (state.selection?.selection_id === receipt.selection_id) {
    if (canonicalJson(state.selection) !== canonicalJson(receipt)) {
      return cloneOwned({ ...state, refusal: { stage: 'selection', code: 'selection_identity_conflict' } });
    }
    return state;
  }
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'selection-replaced')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    selection: receipt,
    currentIntent: null,
    fallback: null,
    deliveries: [],
    actuationObservation: null,
    expiredIntents,
    staleTransaction: null,
    refusal: null,
    activationRefusal: null,
  });
}

export function declineSelection(stateValue) {
  const state = cloneOwned(stateValue);
  if (!state.selection) {
    return cloneOwned({ ...state, activationRefusal: { stage: 'decline', code: 'selection_missing' } });
  }
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'viewer-declined')]
    : state.expiredIntents;
  const declinedSelectionIds = state.declinedSelectionIds.includes(state.selection.selection_id)
    ? state.declinedSelectionIds
    : [...state.declinedSelectionIds, state.selection.selection_id];
  return cloneOwned({
    ...state,
    declinedSelectionIds,
    currentIntent: null,
    fallback: null,
    deliveries: [],
    actuationObservation: null,
    expiredIntents,
    activationRefusal: null,
  });
}

export function activateSelection(stateValue) {
  const state = cloneOwned(stateValue);
  if (!state.selection) {
    return cloneOwned({ ...state, activationRefusal: { stage: 'activation', code: 'selection_missing' } });
  }
  let activation;
  try {
    activation = buildSelectionActivation(state.context, state.selection);
  } catch (error) {
    return cloneOwned({ ...state, activationRefusal: refusal('activation', error) });
  }
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'activation-replaced')]
    : state.expiredIntents;
  if (activation.kind === 'timestamp_fallback') {
    return cloneOwned({
      ...state,
      currentIntent: null,
      fallback: activation,
      deliveries: [],
      actuationObservation: null,
      expiredIntents,
      activationRefusal: null,
    });
  }
  return cloneOwned({
    ...state,
    currentIntent: activation,
    fallback: null,
    deliveries: [],
    actuationObservation: null,
    expiredIntents,
    activationRefusal: null,
  });
}

export function recordSelectionDelivery(stateValue, receiptValue) {
  const state = cloneOwned(stateValue);
  const intent = state.currentIntent ?? state.expiredIntents.find((row) => row.intentId === receiptValue?.intentId);
  if (!intent) {
    return cloneOwned({ ...state, activationRefusal: { stage: 'delivery', code: 'selection_delivery_intent_unknown' } });
  }
  let receipt;
  try {
    receipt = validateSelectionDelivery(receiptValue, intent);
  } catch (error) {
    return cloneOwned({ ...state, activationRefusal: refusal('delivery', error) });
  }
  if (state.deliveries.some((row) => row.receiptId === receipt.receiptId)) return state;
  return cloneOwned({ ...state, deliveries: [...state.deliveries, receipt], activationRefusal: null });
}

export function ingestActuationObservation(stateValue, observationValue) {
  const state = cloneOwned(stateValue);
  if (!state.currentIntent) {
    return cloneOwned({ ...state, activationRefusal: { stage: 'actuation', code: 'actuation_observation_without_active_intent' } });
  }
  let observation;
  try {
    observation = validateActuationObservation(observationValue, state.currentIntent, state.context);
  } catch (error) {
    return cloneOwned({ ...state, activationRefusal: refusal('actuation', error) });
  }
  return cloneOwned({ ...state, actuationObservation: observation, activationRefusal: null });
}

export function dismissSelection(stateValue) {
  const state = cloneOwned(stateValue);
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'selection-dismissed')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    selection: null,
    currentIntent: null,
    fallback: null,
    deliveries: [],
    actuationObservation: null,
    expiredIntents,
    refusal: null,
    activationRefusal: null,
  });
}
