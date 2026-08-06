import {
  QUERY_VIEW_VERSION,
  cloneOwned,
  plannerMessage,
} from './contract.mjs';

function confidenceLabel(ppm) {
  if (ppm === 1_000_000) return 'exact';
  if (ppm >= 900_000) return 'strong';
  if (ppm >= 600_000) return 'limited';
  if (ppm > 0) return 'weak';
  return 'unknown';
}

function activeTransaction(state) {
  if (state.currentIntent || state.plannerObservation || state.answerObservation) {
    return {
      context: state.context,
      intent: state.currentIntent,
      planner: state.plannerObservation,
      answer: state.answerObservation,
      stale: false,
    };
  }
  if (state.staleTransaction) {
    return {
      context: state.staleTransaction.context,
      intent: state.staleTransaction.intent,
      planner: state.staleTransaction.plannerObservation,
      answer: state.staleTransaction.answerObservation,
      stale: true,
    };
  }
  return { context: state.context, intent: null, planner: null, answer: null, stale: false };
}

function transactionState(state, tx) {
  if (state.refusal) return state.refusal.code.includes('conflict') ? 'conflict' : 'refused';
  if (tx.stale) return 'stale';
  if (!tx.intent) return state.context.state === 'ready' ? 'idle' : state.context.state;
  if (!tx.planner) return 'planning';
  if (tx.planner.state === 'refused') return 'refused';
  if (tx.planner.state === 'unresolved') return 'unresolved';
  if (tx.answer) return 'answered';
  return 'planned';
}

function factRows(plan, answer) {
  if (!plan) return [];
  const delivered = plan.facts.filter((row) => row.delivered);
  const paragraphs = answer?.structured.paragraphs ?? plan.structured_fallback;
  return delivered.map((row, index) => ({
    factId: row.fact_id,
    role: row.role,
    provenanceRefs: [...row.provenance_refs],
    alreadyKnown: row.already_known,
    paragraph: paragraphs[index],
  }));
}

function knowledgeSummary(plan, answer) {
  if (!plan) return null;
  if (answer) {
    const effect = answer.knowledgeEffectSummary;
    return {
      available: true,
      authority: effect.authority,
      applied: false,
      deliveredCount: effect.deliveredFactIds.length,
      newlyExplainedCount: effect.newlyExplainedFactIds.length,
      alreadyKnownCount: effect.alreadyKnownFactIds.length,
      withheldCount: effect.withheldCount,
      projectedEventIds: effect.projectedEvents.map((row) => row.eventId),
      effectReceiptRef: effect.effectReceiptRef,
    };
  }
  const delivered = plan.facts.filter((row) => row.delivered);
  return {
    available: false,
    authority: 'external_projection_pending',
    applied: false,
    deliveredCount: delivered.length,
    newlyExplainedCount: delivered.filter((row) => !row.already_known).length,
    alreadyKnownCount: delivered.filter((row) => row.already_known).length,
    withheldCount: plan.withheld_fact_ids.length,
    projectedEventIds: [],
    effectReceiptRef: '',
  };
}

export function projectQueryView(state) {
  const tx = activeTransaction(state);
  const context = tx.context;
  const plan = tx.planner?.state === 'planned' ? tx.planner.plan : null;
  const answer = tx.answer;
  const anchorConfidencePpm = Math.min(
    context.anchor.clockConfidencePpm,
    context.anchor.identityConfidencePpm,
  );
  const stateName = transactionState(state, tx);
  const refusalReason = state.refusal?.code
    ?? state.requestRefusal?.code
    ?? state.renderingRefusal?.code
    ?? tx.planner?.reasonCode
    ?? context.reasonCode
    ?? '';
  const structured = plan
    ? {
        available: true,
        factIds: plan.facts.filter((row) => row.delivered).map((row) => row.fact_id),
        paragraphs: answer?.structured.paragraphs ?? plan.structured_fallback,
        plainText: answer?.structured.plainText ?? plan.structured_fallback.join(' '),
      }
    : { available: false, factIds: [], paragraphs: [], plainText: '' };
  const proseAvailable = answer?.state === 'validated_prose';
  const selectedRendering = proseAvailable && state.selectedRendering === 'prose' ? 'prose' : 'structured';
  const displayText = selectedRendering === 'prose' ? answer.prose.text : structured.plainText;
  const alertStates = new Set(['refused', 'unresolved', 'conflict']);

  return cloneOwned({
    version: QUERY_VIEW_VERSION,
    state: stateName,
    reasonCode: refusalReason,
    accessibleRole: alertStates.has(stateName) ? 'alert' : 'status',
    refusalMessage: tx.planner && ['refused', 'unresolved'].includes(tx.planner.state)
      ? plannerMessage(tx.planner.reasonCode)
      : '',
    package: {
      storyPackageId: context.storyPackageId,
      storyPackageDigest: context.storyPackageDigest,
      storyPackageRevision: context.storyPackageRevision,
      workId: context.workId,
    },
    viewer: {
      viewerProfileId: context.viewerProfileId,
      viewerProfileDigest: context.viewerProfileDigest,
    },
    anchor: {
      anchorId: context.anchor.anchorId,
      observationId: context.anchor.observationId,
      canonicalPositionUs: context.anchor.canonicalPositionUs,
      clockMode: context.anchor.clockMode,
      identityMode: context.anchor.identityMode,
      clockConfidencePpm: context.anchor.clockConfidencePpm,
      identityConfidencePpm: context.anchor.identityConfidencePpm,
      confidencePpm: anchorConfidencePpm,
      confidenceLabel: confidenceLabel(anchorConfidencePpm),
    },
    request: tx.intent
      ? {
          intentId: tx.intent.intentId,
          queryId: tx.intent.query.query_id,
          operation: tx.intent.query.operation,
          question: tx.intent.query.question,
          spoilerMode: tx.intent.query.spoiler_mode,
          targetEntityIds: [...tx.intent.query.target_entity_ids],
          deliveryReceiptIds: state.deliveries.map((row) => row.receiptId),
        }
      : null,
    plan: plan
      ? {
          planId: plan.plan_id,
          plannerReceiptRef: tx.planner.plannerReceiptRef,
          spoilerMode: plan.spoiler_mode,
          includedFacts: factRows(plan, answer),
          includedFactCount: plan.facts.filter((row) => row.delivered).length,
          withheldCount: plan.withheld_fact_ids.length,
          modelAllowed: plan.model_policy.allowed,
        }
      : null,
    answer: plan
      ? {
          structured,
          proseAvailable,
          proseRefused: answer?.state === 'prose_refused',
          selectedRendering,
          displayText,
          renderReceiptRef: answer?.renderReceiptRef ?? '',
          knowledgeEffectSummary: knowledgeSummary(plan, answer),
        }
      : null,
    actions: {
      canSubmit: state.context.state === 'ready' && !tx.stale,
      canSelectStructured: Boolean(plan),
      canSelectProse: proseAvailable && !tx.stale,
      readOnly: tx.stale || state.context.state !== 'ready',
    },
    pendingIntentId: state.currentIntent?.intentId ?? '',
    expiredIntentIds: state.expiredIntents.map((row) => row.intentId),
    stale: tx.stale,
  });
}
