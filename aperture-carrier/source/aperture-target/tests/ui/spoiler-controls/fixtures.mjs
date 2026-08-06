import { contentId, sha256Json } from '../../../clients/shared/spoilers/contract.mjs';

export const DIGESTS = Object.freeze({
  viewer: '1'.repeat(64),
  package: '2'.repeat(64),
  source: '3'.repeat(64),
  action: '4'.repeat(64),
});

export function makeSourceRefs(label = 'knowledge') {
  return [{ kind: 'receipt', ref: `receipt:${label}`, sha256: DIGESTS.source }];
}

export function makeEvent({
  factId,
  effect,
  basis,
  standing,
  actor = 'daemon:knowledge',
  recordedAtUs,
  ordinal = 0,
}) {
  const core = {
    idempotencyKey: sha256Json({ factId, effect, basis, recordedAtUs, ordinal }),
    effect,
    basis,
    standing,
    actor,
    recordedAtUs,
    sourceRefs: makeSourceRefs(`${factId}:${ordinal}`),
  };
  return { eventId: contentId('knowledge1_', { factId, ...core }), ...core };
}

function basesFrom(history) {
  const latest = new Map();
  for (const event of history) {
    if (event.effect === 'propose') continue;
    latest.set(event.basis, event);
  }
  return [...latest.entries()]
    .sort(([left], [right]) => left.localeCompare(right, 'en'))
    .map(([basis, event]) => ({
      basis,
      active: event.effect !== 'revoke',
      latestEventId: event.eventId,
      eventIds: history.filter((row) => row.basis === basis).map((row) => row.eventId),
    }));
}

export function makeFact({ factId, label, firstRevealPositionUs, history = [] }) {
  return {
    factId,
    label,
    firstRevealPositionId: `position:${factId}`,
    firstRevealPositionUs,
    history,
    bases: basesFrom(history),
  };
}

export function makeFacts() {
  const alphaHistory = [
    makeEvent({ factId: 'fact.alpha', effect: 'acquire', basis: 'seen', standing: 'active_assumption', recordedAtUs: 100, ordinal: 0 }),
    makeEvent({ factId: 'fact.alpha', effect: 'acquire', basis: 'explained', standing: 'active_assumption', recordedAtUs: 200, ordinal: 1 }),
    makeEvent({ factId: 'fact.alpha', effect: 'revoke', basis: 'seen', standing: 'revoked_assumption', recordedAtUs: 300, ordinal: 2 }),
  ];
  const betaHistory = [
    makeEvent({ factId: 'fact.beta', effect: 'acquire', basis: 'user_asserted', standing: 'active_assumption', actor: 'viewer:viewer.local', recordedAtUs: 150, ordinal: 0 }),
  ];
  const inferredHistory = [
    makeEvent({ factId: 'fact.inferred', effect: 'propose', basis: 'inferred', standing: 'proposed_only', actor: 'model:qwen', recordedAtUs: 120, ordinal: 0 }),
  ];
  const outcomeHistory = [
    makeEvent({ factId: 'fact.outcome', effect: 'acquire', basis: 'outcome_spoiled', standing: 'active_assumption', recordedAtUs: 170, ordinal: 0 }),
  ];
  return [
    makeFact({ factId: 'fact.alpha', label: 'Alpha entered the vault.', firstRevealPositionUs: 1_000_000, history: alphaHistory }),
    makeFact({ factId: 'fact.beta', label: 'Beta carries the key.', firstRevealPositionUs: 2_000_000, history: betaHistory }),
    makeFact({ factId: 'fact.future', label: 'The future outcome.', firstRevealPositionUs: 50_000_000, history: [] }),
    makeFact({ factId: 'fact.inferred', label: 'A model inferred motive.', firstRevealPositionUs: 3_000_000, history: inferredHistory }),
    makeFact({ factId: 'fact.outcome', label: 'The outcome was spoiled.', firstRevealPositionUs: 40_000_000, history: outcomeHistory }),
  ];
}

export function makeContext(overrides = {}) {
  const core = {
    version: 'axm-aperture-spoiler-context/1',
    contextId: 'spoiler-context:1',
    sequence: 10,
    state: 'ready',
    reasonCode: '',
    viewerId: 'viewer.local',
    viewerDigest: DIGESTS.viewer,
    workId: 'work.golden',
    continuityId: 'continuity.golden',
    storyPackageId: 'story.golden',
    storyPackageDigest: DIGESTS.package,
    packageRevision: 7,
    queryId: 'query:current',
    currentPositionId: 'position:current',
    currentPositionUs: 10_000_000,
    globalSpoilerMode: 'necessary_antecedents',
    storySpoilerMode: null,
    querySpoilerMode: null,
    resolvedSpoilerMode: 'necessary_antecedents',
    resolvedSpoilerSource: 'global',
    knowledgePolicy: {
      policyId: 'policy.knowledge.local',
      policyVersion: '1.0.0',
      defaultSeenAssumption: 'explicit_events_only',
      modelInference: 'proposals_only',
      spoilerEffectsRecorded: true,
      userCanRevoke: true,
      authority: 'viewer_policy_only',
    },
    facts: makeFacts(),
    appliedIntentIds: [],
    rejectedIntentIds: [],
    accessReceiptRefs: ['access:knowledge:1'],
    authority: 'external_daemon_projection_only',
  };
  return structuredClone({ ...core, ...overrides });
}

export function policyAction(overrides = {}) {
  return {
    actionId: 'action:policy:1',
    recordedAtUs: 1_700_000_000_000_000,
    scope: 'story',
    mode: 'full_continuity',
    reasonCode: 'viewer-selected',
    ...overrides,
  };
}

export function knowledgeAction(overrides = {}) {
  return {
    actionId: 'action:knowledge:1',
    recordedAtUs: 1_700_000_000_000_001,
    action: 'confirm',
    factId: 'fact.future',
    basis: null,
    replacementFactId: null,
    reasonCode: 'viewer-confirmed',
    sourceReceiptRef: 'user-action:1',
    sourceReceiptSha256: DIGESTS.action,
    ...overrides,
  };
}

export function deliveryFor(intent, overrides = {}) {
  const core = {
    version: 'axm-aperture-knowledge-intent-delivery/1',
    intentId: intent.intentId,
    state: 'delivered',
    reasonCode: '',
    authority: 'transport_receipt_only',
  };
  return {
    receiptId: contentId('knowledgedelivery1_', core),
    ...core,
    ...overrides,
  };
}
