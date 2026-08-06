import {
  SELECTION_CONTEXT_VERSION,
  SELECTION_RECEIPT_VERSION,
  SELECTION_DELIVERY_VERSION,
  ACTUATION_OBSERVATION_VERSION,
  sha256Json,
} from '../../../clients/shared/selections/contract.mjs';

export const D = Object.freeze({
  package: '1'.repeat(64),
  viewer: '2'.repeat(64),
  anchor: '3'.repeat(64),
  map: '4'.repeat(64),
  exposure: '5'.repeat(64),
  knowledge: '6'.repeat(64),
});

export function selectionContext(overrides = {}) {
  const base = {
    version: SELECTION_CONTEXT_VERSION,
    contextId: 'selection-context:1',
    sequence: 7,
    storyPackageId: 'story-package:fixture',
    storyPackageDigest: D.package,
    workId: 'work:fixture',
    continuityId: 'continuity:fixture',
    viewerProfileId: 'viewer:fixture',
    viewerProfileDigest: D.viewer,
    state: 'ready',
    reasonCode: '',
    anchor: {
      anchorId: 'anchor:fixture',
      anchorDigest: D.anchor,
      sessionId: 'session:fixture',
      workId: 'work:fixture',
      storyPackageId: 'story-package:fixture',
      canonicalPositionUs: 40_000_000,
      confidence: 'exact',
      exact: true,
      observedAt: '2026-08-06T00:00:00Z',
    },
    providerMapping: {
      state: 'verified',
      providerEditionId: 'provider-edition:fixture',
      mapDigest: D.map,
      rateNumerator: 1,
      rateDenominator: 1,
      offsetUs: 2_000_000,
      reasonCode: '',
    },
    capabilities: { seek: 'exact' },
    maximumSegmentUs: 600_000_000,
    accessReceiptRefs: ['access:selection'],
  };
  return deepMerge(base, overrides);
}

export function candidate({
  id = 'candidate:entry',
  sceneId = 'scene:entry',
  startUs = 10_000_000,
  endUs = 70_000_000,
  workId = 'work:fixture',
  terms = {},
  score = null,
} = {}) {
  const scoreTerms = {
    uncovered: 800_000,
    bridge: 100_000,
    recognition: 50_000,
    question: 25_000,
    entry_cost: -50_000,
    repeat_penalty: -10_000,
    saturation_penalty: -5_000,
    ...terms,
  };
  const calculated = Object.values(scoreTerms).reduce((sum, value) => sum + value, 0);
  return {
    candidate_id: id,
    work_id: workId,
    scene_id: sceneId,
    canonical_start_us: startUs,
    canonical_end_us: endUs,
    score: score ?? calculated,
    score_terms: scoreTerms,
  };
}

export function selectionReceipt(context = selectionContext(), overrides = {}) {
  const candidates = overrides.candidates ?? [
    candidate(),
    candidate({
      id: 'candidate:bridge',
      sceneId: 'scene:bridge',
      startUs: 80_000_000,
      endUs: 140_000_000,
      terms: { uncovered: 400_000, bridge: 250_000, entry_cost: -20_000 },
    }),
    candidate({
      id: 'candidate:repeat',
      sceneId: 'scene:repeat',
      startUs: 150_000_000,
      endUs: 210_000_000,
      terms: { uncovered: 100_000, repeat_penalty: -300_000, saturation_penalty: -200_000 },
    }),
  ];
  const selected = [...candidates].sort((left, right) => {
    if (left.score !== right.score) return right.score - left.score;
    if (left.canonical_start_us !== right.canonical_start_us) return left.canonical_start_us - right.canonical_start_us;
    return left.scene_id < right.scene_id ? -1 : left.scene_id > right.scene_id ? 1 : 0;
  })[0];
  const core = {
    format: SELECTION_RECEIPT_VERSION,
    policy_id: 'selection-policy:fixture',
    policy_version: 'selection-policy-version:1',
    viewer_id: context.viewerProfileId,
    work_id: context.workId,
    continuity_id: context.continuityId,
    story_package_id: context.storyPackageId,
    mode: 'drop',
    candidate_set_digest: sha256Json(candidates),
    candidates,
    selected_candidate_id: selected.candidate_id,
    reason_codes: ['uncovered', 'same-work'],
    input_projection_digests: [context.storyPackageDigest, context.anchor.anchorDigest, D.exposure, D.knowledge],
    same_work_only: true,
    authority: 'selection_receipt_only',
    ...Object.fromEntries(Object.entries(overrides).filter(([key]) => key !== 'candidates')),
  };
  return { selection_id: `selection1_${sha256Json(core)}`, ...core };
}

export function deliveryReceipt(intent, overrides = {}) {
  return {
    version: SELECTION_DELIVERY_VERSION,
    receiptId: 'delivery:fixture',
    intentId: intent.intentId,
    status: 'delivered',
    reasonCode: '',
    deliveredAt: '2026-08-06T00:00:01Z',
    authority: 'transport_receipt_only',
    ...overrides,
  };
}

export function actuationObservation(intent, context = selectionContext(), overrides = {}) {
  return {
    version: ACTUATION_OBSERVATION_VERSION,
    observationId: 'actuation-observation:fixture',
    intentId: intent.intentId,
    anchorId: context.anchor.anchorId,
    anchorDigest: context.anchor.anchorDigest,
    sessionId: context.anchor.sessionId,
    status: 'verified',
    reasonCode: '',
    observedProviderPositionUs: intent.providerPositionUs,
    observedCanonicalPositionUs: intent.canonicalStartUs,
    positionToleranceUs: 250_000,
    authority: 'external_ap212_observation_only',
    ...overrides,
  };
}

export function deepMerge(base, overrides) {
  if (overrides === undefined) return structuredClone(base);
  if (base === null || overrides === null || typeof base !== 'object' || typeof overrides !== 'object') {
    return structuredClone(overrides);
  }
  if (Array.isArray(base) || Array.isArray(overrides)) return structuredClone(overrides);
  const out = structuredClone(base);
  for (const [key, value] of Object.entries(overrides)) {
    out[key] = key in out ? deepMerge(out[key], value) : structuredClone(value);
  }
  return out;
}

export function mutated(value, mutator) {
  const copy = structuredClone(value);
  mutator(copy);
  return copy;
}
