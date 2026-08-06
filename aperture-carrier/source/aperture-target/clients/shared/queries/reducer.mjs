import {
  QUERY_STATE_VERSION,
  buildQueryIntent,
  canonicalJson,
  cloneOwned,
  validateAnswerObservation,
  validatePlannerObservation,
  validateQueryContext,
  validateQueryDelivery,
  validateQueryIntent,
} from './contract.mjs';

function refusal(stage, error) {
  return Object.freeze({
    stage,
    code: error?.code ?? 'query_transaction_refused',
  });
}

function expireIntent(intent, reasonCode) {
  return Object.freeze({ ...structuredClone(intent), expiredReason: reasonCode });
}

export function createQueryState(contextValue) {
  const context = validateQueryContext(contextValue);
  return cloneOwned({
    version: QUERY_STATE_VERSION,
    context,
    currentIntent: null,
    deliveries: [],
    plannerObservation: null,
    answerObservation: null,
    selectedRendering: 'structured',
    expiredIntents: [],
    staleTransaction: null,
    refusal: null,
    requestRefusal: null,
    renderingRefusal: null,
  });
}

export function replaceQueryContext(stateValue, contextValue) {
  const state = cloneOwned(stateValue);
  let context;
  try {
    context = validateQueryContext(contextValue);
  } catch (error) {
    return cloneOwned({ ...state, refusal: refusal('context', error) });
  }
  if (context.contextId === state.context.contextId) {
    if (canonicalJson(context) !== canonicalJson(state.context)) {
      return cloneOwned({ ...state, refusal: { stage: 'context', code: 'context_identity_conflict' } });
    }
    return state;
  }
  if (
    context.storyPackageDigest === state.context.storyPackageDigest &&
    context.viewerProfileDigest === state.context.viewerProfileDigest &&
    context.sequence < state.context.sequence
  ) {
    return cloneOwned({ ...state, refusal: { stage: 'context', code: 'context_sequence_regression' } });
  }
  const hadTransaction = Boolean(state.currentIntent || state.plannerObservation || state.answerObservation);
  const staleTransaction = hadTransaction
    ? {
        context: state.context,
        intent: state.currentIntent,
        plannerObservation: state.plannerObservation,
        answerObservation: state.answerObservation,
        reasonCode: 'context-replaced',
      }
    : state.staleTransaction;
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'context-replaced')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    context,
    currentIntent: null,
    deliveries: [],
    plannerObservation: null,
    answerObservation: null,
    selectedRendering: 'structured',
    expiredIntents,
    staleTransaction,
    refusal: null,
    requestRefusal: null,
    renderingRefusal: null,
  });
}

export function requestQuery(stateValue, inputValue) {
  const state = cloneOwned(stateValue);
  let intent;
  try {
    intent = buildQueryIntent(state.context, inputValue);
  } catch (error) {
    return cloneOwned({ ...state, requestRefusal: refusal('request', error) });
  }
  const expiredIntents = state.currentIntent
    ? [...state.expiredIntents, expireIntent(state.currentIntent, 'superseded-by-new-query')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    currentIntent: intent,
    deliveries: [],
    plannerObservation: null,
    answerObservation: null,
    selectedRendering: 'structured',
    expiredIntents,
    staleTransaction: null,
    refusal: null,
    requestRefusal: null,
    renderingRefusal: null,
  });
}

export function recordQueryDelivery(stateValue, receiptValue) {
  const state = cloneOwned(stateValue);
  const intent = state.currentIntent ?? state.expiredIntents.find((row) => row.intentId === receiptValue?.intentId);
  if (!intent) {
    return cloneOwned({ ...state, requestRefusal: { stage: 'delivery', code: 'delivery_intent_unknown' } });
  }
  let receipt;
  try {
    receipt = validateQueryDelivery(receiptValue, intent);
  } catch (error) {
    return cloneOwned({ ...state, requestRefusal: refusal('delivery', error) });
  }
  if (state.deliveries.some((row) => row.receiptId === receipt.receiptId)) return state;
  return cloneOwned({ ...state, deliveries: [...state.deliveries, receipt], requestRefusal: null });
}

export function ingestPlannerObservation(stateValue, observationValue) {
  const state = cloneOwned(stateValue);
  if (!state.currentIntent) {
    return cloneOwned({ ...state, refusal: { stage: 'planner', code: 'planner_observation_without_request' } });
  }
  let observation;
  try {
    observation = validatePlannerObservation(observationValue, state.currentIntent, state.context);
  } catch (error) {
    return cloneOwned({ ...state, refusal: refusal('planner', error) });
  }
  return cloneOwned({
    ...state,
    plannerObservation: observation,
    answerObservation: null,
    selectedRendering: 'structured',
    refusal: null,
    renderingRefusal: null,
  });
}

export function ingestAnswerObservation(stateValue, observationValue) {
  const state = cloneOwned(stateValue);
  if (!state.currentIntent || !state.plannerObservation) {
    return cloneOwned({ ...state, renderingRefusal: { stage: 'answer', code: 'answer_observation_without_plan' } });
  }
  let observation;
  try {
    observation = validateAnswerObservation(
      observationValue,
      state.plannerObservation,
      state.currentIntent,
      state.context,
    );
  } catch (error) {
    return cloneOwned({ ...state, renderingRefusal: refusal('answer', error) });
  }
  return cloneOwned({
    ...state,
    answerObservation: observation,
    selectedRendering: observation.state === 'validated_prose' ? state.selectedRendering : 'structured',
    renderingRefusal: null,
  });
}

export function selectQueryRendering(stateValue, mode) {
  const state = cloneOwned(stateValue);
  if (!['structured', 'prose'].includes(mode)) {
    return cloneOwned({ ...state, renderingRefusal: { stage: 'presentation', code: 'rendering_mode_unsupported' } });
  }
  if (mode === 'prose' && state.answerObservation?.state !== 'validated_prose') {
    return cloneOwned({ ...state, renderingRefusal: { stage: 'presentation', code: 'validated_prose_unavailable' } });
  }
  return cloneOwned({ ...state, selectedRendering: mode, renderingRefusal: null });
}

export function dismissQuery(stateValue) {
  const state = cloneOwned(stateValue);
  return cloneOwned({
    ...state,
    currentIntent: null,
    deliveries: [],
    plannerObservation: null,
    answerObservation: null,
    selectedRendering: 'structured',
    refusal: null,
    requestRefusal: null,
    renderingRefusal: null,
  });
}

export function validateStateIntent(stateValue) {
  if (stateValue.currentIntent) validateQueryIntent(stateValue.currentIntent, stateValue.context);
  return true;
}
