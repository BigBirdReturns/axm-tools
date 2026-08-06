import {
  SPOILER_STATE_VERSION,
  buildKnowledgeIntent,
  buildSpoilerPolicyIntent,
  canonicalJson,
  cloneOwned,
  validateIntentDelivery,
  validateSpoilerContext,
} from './contract.mjs';

function refusal(stage, error) {
  return Object.freeze({ stage, code: error?.code ?? 'spoiler_control_refused' });
}

function expireIntent(intent, reasonCode) {
  return Object.freeze({ ...structuredClone(intent), expiredReason: reasonCode });
}

export function createSpoilerState(contextValue) {
  const context = validateSpoilerContext(contextValue);
  return cloneOwned({
    version: SPOILER_STATE_VERSION,
    context,
    selectedFactId: null,
    policyIntent: null,
    knowledgeIntent: null,
    deliveries: [],
    expiredIntents: [],
    settledIntents: [],
    staleContext: null,
    refusal: null,
    policyRefusal: null,
    knowledgeRefusal: null,
    deliveryRefusal: null,
  });
}

export function replaceSpoilerContext(stateValue, contextValue) {
  const state = cloneOwned(stateValue);
  let context;
  try {
    context = validateSpoilerContext(contextValue);
  } catch (error) {
    return cloneOwned({ ...state, refusal: refusal('context', error) });
  }
  if (context.contextId === state.context.contextId) {
    if (canonicalJson(context) !== canonicalJson(state.context)) {
      return cloneOwned({ ...state, refusal: { stage: 'context', code: 'context_identity_conflict' } });
    }
    return state;
  }
  const sameAuthorityScope =
    context.viewerDigest === state.context.viewerDigest &&
    context.storyPackageDigest === state.context.storyPackageDigest;
  if (sameAuthorityScope && context.sequence < state.context.sequence) {
    return cloneOwned({ ...state, refusal: { stage: 'context', code: 'context_sequence_regression' } });
  }

  const activeIntents = [state.policyIntent, state.knowledgeIntent].filter(Boolean);
  const settled = [];
  const retained = [];
  const expired = [];
  for (const intent of activeIntents) {
    if (context.appliedIntentIds.includes(intent.intentId)) {
      settled.push({ intent, standing: 'applied' });
    } else if (context.rejectedIntentIds.includes(intent.intentId)) {
      settled.push({ intent, standing: 'rejected' });
    } else if (!sameAuthorityScope) {
      expired.push(expireIntent(intent, 'authority-scope-replaced'));
    } else {
      retained.push(intent);
    }
  }
  const retainedPolicy = retained.find((intent) => intent.version === 'axm-aperture-spoiler-policy-intent/1') ?? null;
  const retainedKnowledge = retained.find((intent) => intent.version === 'axm-aperture-knowledge-event-intent/1') ?? null;
  const selectedFactId = state.selectedFactId && context.facts.some((fact) => fact.factId === state.selectedFactId)
    ? state.selectedFactId
    : null;
  return cloneOwned({
    ...state,
    context,
    selectedFactId,
    policyIntent: retainedPolicy,
    knowledgeIntent: retainedKnowledge,
    deliveries: sameAuthorityScope ? state.deliveries : [],
    expiredIntents: [...state.expiredIntents, ...expired],
    settledIntents: [...state.settledIntents, ...settled],
    staleContext: sameAuthorityScope ? state.staleContext : state.context,
    refusal: null,
    policyRefusal: null,
    knowledgeRefusal: null,
    deliveryRefusal: null,
  });
}

export function selectKnowledgeFact(stateValue, factId) {
  const state = cloneOwned(stateValue);
  if (factId === null) return cloneOwned({ ...state, selectedFactId: null });
  if (!state.context.facts.some((fact) => fact.factId === factId)) {
    return cloneOwned({ ...state, knowledgeRefusal: { stage: 'selection', code: 'knowledge_fact_unknown' } });
  }
  return cloneOwned({ ...state, selectedFactId: factId, knowledgeRefusal: null });
}

export function requestSpoilerPolicyChange(stateValue, actionValue) {
  const state = cloneOwned(stateValue);
  let intent;
  try {
    intent = buildSpoilerPolicyIntent(state.context, actionValue);
  } catch (error) {
    return cloneOwned({ ...state, policyRefusal: refusal('policy', error) });
  }
  const expiredIntents = state.policyIntent
    ? [...state.expiredIntents, expireIntent(state.policyIntent, 'superseded-by-policy-intent')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    policyIntent: intent,
    expiredIntents,
    policyRefusal: null,
    deliveryRefusal: null,
  });
}

export function requestKnowledgeChange(stateValue, actionValue) {
  const state = cloneOwned(stateValue);
  let intent;
  try {
    intent = buildKnowledgeIntent(state.context, actionValue);
  } catch (error) {
    return cloneOwned({ ...state, knowledgeRefusal: refusal('knowledge', error) });
  }
  const expiredIntents = state.knowledgeIntent
    ? [...state.expiredIntents, expireIntent(state.knowledgeIntent, 'superseded-by-knowledge-intent')]
    : state.expiredIntents;
  return cloneOwned({
    ...state,
    knowledgeIntent: intent,
    expiredIntents,
    knowledgeRefusal: null,
    deliveryRefusal: null,
  });
}

export function recordIntentDelivery(stateValue, deliveryValue) {
  const state = cloneOwned(stateValue);
  const intents = [
    state.policyIntent,
    state.knowledgeIntent,
    ...state.expiredIntents,
    ...state.settledIntents.map((row) => row.intent),
  ].filter(Boolean);
  const intent = intents.find((candidate) => candidate.intentId === deliveryValue?.intentId);
  if (!intent) {
    return cloneOwned({ ...state, deliveryRefusal: { stage: 'delivery', code: 'delivery_intent_unknown' } });
  }
  let delivery;
  try {
    delivery = validateIntentDelivery(deliveryValue, intent);
  } catch (error) {
    return cloneOwned({ ...state, deliveryRefusal: refusal('delivery', error) });
  }
  const existing = state.deliveries.find((row) => row.receiptId === delivery.receiptId);
  if (existing) {
    if (canonicalJson(existing) !== canonicalJson(delivery)) {
      return cloneOwned({ ...state, deliveryRefusal: { stage: 'delivery', code: 'delivery_identity_conflict' } });
    }
    return state;
  }
  return cloneOwned({
    ...state,
    deliveries: [...state.deliveries, delivery],
    deliveryRefusal: null,
  });
}

export function dismissSpoilerIntent(stateValue, kind) {
  const state = cloneOwned(stateValue);
  if (kind === 'policy') return cloneOwned({ ...state, policyIntent: null, policyRefusal: null });
  if (kind === 'knowledge') return cloneOwned({ ...state, knowledgeIntent: null, knowledgeRefusal: null });
  return cloneOwned({ ...state, refusal: { stage: 'dismiss', code: 'intent_kind_unsupported' } });
}
