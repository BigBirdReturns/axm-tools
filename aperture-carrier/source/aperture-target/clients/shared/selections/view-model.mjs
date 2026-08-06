import {
  SCORE_TERM_KEYS,
  SELECTION_VIEW_VERSION,
  cloneOwned,
  selectedCandidate,
} from './contract.mjs';

function activeTransaction(state) {
  if (state.selection) {
    return {
      context: state.context,
      selection: state.selection,
      intent: state.currentIntent,
      fallback: state.fallback,
      deliveries: state.deliveries,
      actuation: state.actuationObservation,
      stale: false,
    };
  }
  if (state.staleTransaction) {
    return {
      context: state.staleTransaction.context,
      selection: state.staleTransaction.selection,
      intent: state.staleTransaction.intent,
      fallback: state.staleTransaction.fallback,
      deliveries: state.staleTransaction.deliveries,
      actuation: state.staleTransaction.actuationObservation,
      stale: true,
    };
  }
  return {
    context: state.context,
    selection: null,
    intent: null,
    fallback: null,
    deliveries: [],
    actuation: null,
    stale: false,
  };
}

function selectionState(state, tx) {
  if (state.refusal) return state.refusal.code.includes('conflict') ? 'conflict' : 'refused';
  if (tx.stale) return 'stale';
  if (!tx.selection) return state.context.state === 'ready' ? 'idle' : state.context.state;
  if (state.declinedSelectionIds.includes(tx.selection.selection_id)) return 'declined';
  if (tx.fallback) return 'timestamp_fallback';
  if (!tx.intent) return 'selected';
  if (tx.actuation?.status === 'verified') return 'actuation_verified';
  if (tx.actuation?.status === 'refused') return 'actuation_refused';
  if (tx.actuation?.status === 'failed') return 'actuation_failed';
  if (tx.deliveries.some((row) => row.status === 'delivered')) return 'request_delivered_unverified';
  if (tx.deliveries.some((row) => row.status === 'refused')) return 'request_refused';
  if (tx.deliveries.some((row) => row.status === 'failed')) return 'request_failed';
  return 'request_pending';
}

function candidateView(candidate, selectedId) {
  return {
    candidateId: candidate.candidate_id,
    sceneId: candidate.scene_id,
    workId: candidate.work_id,
    canonicalStartUs: candidate.canonical_start_us,
    canonicalEndUs: candidate.canonical_end_us,
    durationUs: candidate.canonical_end_us - candidate.canonical_start_us,
    score: candidate.score,
    scoreTerms: Object.fromEntries(SCORE_TERM_KEYS.map((key) => [key, candidate.score_terms[key]])),
    selected: candidate.candidate_id === selectedId,
  };
}

export function projectSelectionView(state) {
  const tx = activeTransaction(state);
  const selection = tx.selection;
  const candidate = selection ? selectedCandidate(selection) : null;
  const stateName = selectionState(state, tx);
  const exactSeekAvailable = Boolean(
    !tx.stale &&
    tx.context.state === 'ready' &&
    tx.context.anchor.exact &&
    tx.context.providerMapping.state === 'verified' &&
    tx.context.capabilities.seek === 'exact',
  );
  const activation = tx.fallback
    ? {
        kind: tx.fallback.fallbackKind,
        requestIntentId: '',
        autoplay: false,
        providerPositionUs: tx.fallback.providerPositionUs,
        canonicalPositionUs: tx.fallback.canonicalStartUs,
        authority: 'presentation_only',
      }
    : tx.intent
      ? {
          kind: 'exact_seek_request',
          requestIntentId: tx.intent.intentId,
          autoplay: false,
          providerPositionUs: tx.intent.providerPositionUs,
          canonicalPositionUs: tx.intent.canonicalStartUs,
          authority: 'request_intent_only',
        }
      : {
          kind: exactSeekAvailable ? 'exact_seek_available' : (
            tx.context.providerMapping.state === 'verified' ? 'provider_timestamp_available' : 'canonical_timestamp_available'
          ),
          requestIntentId: '',
          autoplay: false,
          providerPositionUs: null,
          canonicalPositionUs: candidate?.canonical_start_us ?? null,
          authority: 'presentation_only',
        };
  return cloneOwned({
    version: SELECTION_VIEW_VERSION,
    state: stateName,
    reasonCode: state.refusal?.code ?? state.activationRefusal?.code ?? tx.context.reasonCode,
    stale: tx.stale,
    context: {
      contextId: tx.context.contextId,
      sequence: tx.context.sequence,
      storyPackageId: tx.context.storyPackageId,
      storyPackageDigest: tx.context.storyPackageDigest,
      workId: tx.context.workId,
      continuityId: tx.context.continuityId,
      viewerProfileId: tx.context.viewerProfileId,
      viewerProfileDigest: tx.context.viewerProfileDigest,
      anchorId: tx.context.anchor.anchorId,
      anchorDigest: tx.context.anchor.anchorDigest,
      anchorConfidence: tx.context.anchor.confidence,
      anchorExact: tx.context.anchor.exact,
      providerMappingState: tx.context.providerMapping.state,
      seekCapability: tx.context.capabilities.seek,
    },
    policy: selection
      ? {
          selectionId: selection.selection_id,
          policyId: selection.policy_id,
          policyVersion: selection.policy_version,
          mode: selection.mode,
          candidateSetDigest: selection.candidate_set_digest,
          candidateCount: selection.candidates.length,
          sameWorkOnly: selection.same_work_only,
          reasonCodes: [...selection.reason_codes],
          candidates: selection.candidates.map((row) => candidateView(row, selection.selected_candidate_id)),
        }
      : null,
    selectedCandidate: candidate ? candidateView(candidate, selection.selected_candidate_id) : null,
    activation,
    transport: {
      receipts: tx.deliveries.map((row) => ({
        receiptId: row.receiptId,
        status: row.status,
        reasonCode: row.reasonCode,
        authority: row.authority,
      })),
      delivered: tx.deliveries.some((row) => row.status === 'delivered'),
      verifiedActuation: tx.actuation?.status === 'verified',
    },
    actuationObservation: tx.actuation
      ? {
          observationId: tx.actuation.observationId,
          status: tx.actuation.status,
          reasonCode: tx.actuation.reasonCode,
          authority: tx.actuation.authority,
        }
      : null,
    canInspect: Boolean(selection),
    canDecline: Boolean(selection && !tx.stale),
    canActivate: Boolean(selection && !tx.stale && tx.context.state === 'ready'),
    authority: {
      scheduler: 'external_ap211_receipt_only',
      actuation: 'external_ap212_observation_only',
      transport: 'delivery_receipt_only',
      client: 'read_only_projection_and_request_intent',
    },
  });
}
