import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import test from 'node:test';

import {
  CONTEXT_STATES,
  KNOWLEDGE_ASSUMPTIONS,
  KNOWLEDGE_BASES,
  SPOILER_MODES,
  buildKnowledgeIntent,
  buildSpoilerPolicyIntent,
  canonicalJson,
  factAvailability,
  resolveSpoilerPolicy,
  validateIntentDelivery,
  validateSpoilerContext,
} from '../../../clients/shared/spoilers/contract.mjs';
import {
  createSpoilerState,
  dismissSpoilerIntent,
  recordIntentDelivery,
  replaceSpoilerContext,
  requestKnowledgeChange,
  requestSpoilerPolicyChange,
  selectKnowledgeFact,
} from '../../../clients/shared/spoilers/reducer.mjs';
import { projectSpoilerView } from '../../../clients/shared/spoilers/view-model.mjs';
import {
  DIGESTS,
  deliveryFor,
  knowledgeAction,
  makeContext,
  policyAction,
} from './fixtures.mjs';

function clone(value) {
  return structuredClone(value);
}

function expectCode(fn, code) {
  assert.throws(fn, (error) => error?.code === code);
}

function contextWithResolved(overrides) {
  const context = makeContext(overrides);
  const resolved = resolveSpoilerPolicy(
    context.globalSpoilerMode,
    context.storySpoilerMode,
    context.querySpoilerMode,
  );
  context.resolvedSpoilerMode = resolved.mode;
  context.resolvedSpoilerSource = resolved.source;
  return context;
}

test('valid context is clone-owned and closed', () => {
  const input = makeContext();
  const validated = validateSpoilerContext(input);
  assert.deepEqual(validated, input);
  assert.notEqual(validated, input);
  assert.ok(Object.isFrozen(validated));
  assert.ok(Object.isFrozen(validated.facts[0].history));
});

for (const mode of SPOILER_MODES) {
  test(`global spoiler mode ${mode} resolves from global scope`, () => {
    const context = contextWithResolved({ globalSpoilerMode: mode, storySpoilerMode: null, querySpoilerMode: null });
    const validated = validateSpoilerContext(context);
    assert.equal(validated.resolvedSpoilerMode, mode);
    assert.equal(validated.resolvedSpoilerSource, 'global');
  });
  test(`story spoiler mode ${mode} overrides global scope`, () => {
    const context = contextWithResolved({ globalSpoilerMode: 'scene_only', storySpoilerMode: mode, querySpoilerMode: null });
    const validated = validateSpoilerContext(context);
    assert.equal(validated.resolvedSpoilerMode, mode);
    assert.equal(validated.resolvedSpoilerSource, 'story');
  });
  test(`query spoiler mode ${mode} overrides story and global scope`, () => {
    const context = contextWithResolved({ globalSpoilerMode: 'scene_only', storySpoilerMode: 'known_outcomes', querySpoilerMode: mode });
    const validated = validateSpoilerContext(context);
    assert.equal(validated.resolvedSpoilerMode, mode);
    assert.equal(validated.resolvedSpoilerSource, 'query');
  });
}

for (const state of CONTEXT_STATES) {
  test(`context state ${state} remains machine-distinct`, () => {
    const context = makeContext({
      state,
      reasonCode: state === 'ready' ? '' : `state-${state.replaceAll('_', '-')}`,
      currentPositionUs: state === 'ready' ? 10_000_000 : null,
    });
    const validated = validateSpoilerContext(context);
    assert.equal(validated.state, state);
  });
}

const contextMutations = [
  ['context unknown field', (row) => { row.transport = {}; }, 'spoiler_context_fields_invalid'],
  ['context authority upgrade', (row) => { row.authority = 'client_authority'; }, 'spoiler_context_authority_invalid'],
  ['context invalid digest', (row) => { row.viewerDigest = 'x'; }, 'spoiler_context_viewer_digest_invalid'],
  ['context invalid sequence', (row) => { row.sequence = -1; }, 'spoiler_context_sequence_invalid'],
  ['ready context without position', (row) => { row.currentPositionUs = null; }, 'ready_context_requires_position'],
  ['resolved mode drift', (row) => { row.resolvedSpoilerMode = 'full_continuity'; }, 'resolved_spoiler_policy_drifted'],
  ['resolved source drift', (row) => { row.resolvedSpoilerSource = 'query'; }, 'resolved_spoiler_policy_drifted'],
  ['invalid global mode', (row) => { row.globalSpoilerMode = 'anything'; }, 'global_spoiler_mode_invalid'],
  ['invalid story mode', (row) => { row.storySpoilerMode = 'anything'; }, 'story_spoiler_mode_invalid'],
  ['invalid query mode', (row) => { row.querySpoilerMode = 'anything'; }, 'query_spoiler_mode_invalid'],
  ['knowledge policy authority upgrade', (row) => { row.knowledgePolicy.authority = 'client'; }, 'knowledge_policy_authority_invalid'],
  ['knowledge policy disables revocation', (row) => { row.knowledgePolicy.userCanRevoke = false; }, 'knowledge_policy_revocation_required'],
  ['knowledge policy disables spoiler recording', (row) => { row.knowledgePolicy.spoilerEffectsRecorded = false; }, 'knowledge_policy_spoiler_recording_required'],
  ['duplicate fact identity', (row) => { row.facts.push(clone(row.facts[0])); }, 'knowledge_fact_duplicate'],
  ['fact ordering drift', (row) => { row.facts.reverse(); }, 'knowledge_facts_not_ordered'],
  ['event identity duplicate', (row) => { row.facts[0].history.push(clone(row.facts[0].history[0])); }, 'knowledge_event_id_duplicate'],
  ['event chronology drift', (row) => { row.facts[0].history.reverse(); }, 'knowledge_history_not_ordered'],
  ['basis projection drift', (row) => { row.facts[0].bases[0].active = false; }, 'knowledge_basis_projection_drifted'],
  ['inference acquires authority', (row) => { row.facts[3].history[0].effect = 'acquire'; row.facts[3].history[0].standing = 'active_assumption'; }, 'model_inference_must_remain_proposal'],
  ['delivery terminal standing conflict', (row) => { row.appliedIntentIds = ['intent:1']; row.rejectedIntentIds = ['intent:1']; }, 'intent_terminal_standing_conflict'],
  ['credential field injection', (row) => { row.credential = 'secret'; }, 'credential_field_forbidden'],
];

for (const [label, mutate, code] of contextMutations) {
  test(`context refuses ${label}`, () => {
    const context = makeContext();
    mutate(context);
    expectCode(() => validateSpoilerContext(context), code);
  });
}

test('explicit events policy admits active explained basis', () => {
  const result = factAvailability(makeContext(), 'fact.alpha');
  assert.equal(result.available, true);
  assert.deepEqual(result.reasons.map((row) => row.basis), ['explained']);
});

test('explicit events policy admits user assertion', () => {
  assert.equal(factAvailability(makeContext(), 'fact.beta').available, true);
});

test('explicit events policy does not admit future fact without events', () => {
  assert.equal(factAvailability(makeContext(), 'fact.future').available, false);
});

test('model proposal does not become available', () => {
  const result = factAvailability(makeContext(), 'fact.inferred');
  assert.equal(result.available, false);
  assert.equal(result.reasons.length, 0);
});

test('outcome-spoiled event remains distinguishable and available', () => {
  const result = factAvailability(makeContext(), 'fact.outcome');
  assert.equal(result.available, true);
  assert.equal(result.reasons[0].basis, 'outcome_spoiled');
});

for (const assumption of KNOWLEDGE_ASSUMPTIONS) {
  test(`knowledge assumption ${assumption} is preserved`, () => {
    const context = makeContext();
    context.knowledgePolicy.defaultSeenAssumption = assumption;
    const validated = validateSpoilerContext(context);
    assert.equal(validated.knowledgePolicy.defaultSeenAssumption, assumption);
  });
}

test('all-prior-positions policy assumes an earlier fact without event', () => {
  const context = makeContext();
  context.knowledgePolicy.defaultSeenAssumption = 'all_prior_positions';
  const result = factAvailability(context, 'fact.inferred');
  assert.equal(result.available, true);
  assert.equal(result.policyAssumed, true);
});

test('all-prior-positions policy does not assume a future fact', () => {
  const context = makeContext();
  context.knowledgePolicy.defaultSeenAssumption = 'all_prior_positions';
  assert.equal(factAvailability(context, 'fact.future').available, false);
});

test('none policy ignores an active seen basis while retaining other explicit bases', () => {
  const context = makeContext();
  context.knowledgePolicy.defaultSeenAssumption = 'none';
  const alpha = context.facts[0];
  alpha.history.push({
    ...clone(alpha.history[0]),
    eventId: 'knowledge1_seen_reaffirm',
    idempotencyKey: '5'.repeat(64),
    effect: 'reaffirm',
    standing: 'active_assumption',
    recordedAtUs: 400,
  });
  alpha.bases = [
    alpha.bases[0],
    {
      basis: 'seen',
      active: true,
      latestEventId: 'knowledge1_seen_reaffirm',
      eventIds: [alpha.history[0].eventId, alpha.history[2].eventId, 'knowledge1_seen_reaffirm'],
    },
  ];
  const result = factAvailability(context, 'fact.alpha');
  assert.equal(result.available, true);
  assert.deepEqual(result.reasons.map((row) => row.basis), ['explained']);
});

test('unknown fact availability refuses', () => {
  expectCode(() => factAvailability(makeContext(), 'fact.missing'), 'knowledge_fact_unknown');
});

for (const scope of ['global', 'story', 'query']) {
  test(`spoiler policy intent emits bounded ${scope} intent`, () => {
    const intent = buildSpoilerPolicyIntent(makeContext(), policyAction({ scope, mode: 'full_continuity' }));
    assert.match(intent.intentId, /^spoilerintent1_[0-9a-f]{64}$/);
    assert.equal(intent.scope, scope);
    assert.equal(intent.mode, 'full_continuity');
    assert.equal(intent.applied, false);
    assert.equal(intent.authority, 'viewer_policy_intent_only');
  });
}

test('query policy intent requires active query identity', () => {
  const context = makeContext({ queryId: null });
  expectCode(() => buildSpoilerPolicyIntent(context, policyAction({ scope: 'query' })), 'query_policy_requires_query');
});

test('spoiler policy intent refuses degraded context', () => {
  const context = makeContext({ state: 'stale', reasonCode: 'stale-context', currentPositionUs: null });
  expectCode(() => buildSpoilerPolicyIntent(context, policyAction()), 'spoiler_policy_context_not_ready');
});

test('spoiler policy intent is deterministic', () => {
  const first = buildSpoilerPolicyIntent(makeContext(), policyAction());
  const second = buildSpoilerPolicyIntent(makeContext(), policyAction());
  assert.deepEqual(first, second);
});

test('spoiler policy action identity changes intent identity', () => {
  const first = buildSpoilerPolicyIntent(makeContext(), policyAction());
  const second = buildSpoilerPolicyIntent(makeContext(), policyAction({ actionId: 'action:policy:2' }));
  assert.notEqual(first.intentId, second.intentId);
});

test('confirm generates one user-attributed active event', () => {
  const intent = buildKnowledgeIntent(makeContext(), knowledgeAction());
  assert.equal(intent.events.length, 1);
  assert.equal(intent.events[0].basis, 'user_asserted');
  assert.equal(intent.events[0].effect, 'acquire');
  assert.equal(intent.events[0].actor, 'viewer:viewer.local');
  assert.equal(intent.applied, false);
});

for (const basis of ['explained', 'user_asserted', 'outcome_spoiled']) {
  test(`active basis ${basis} can be revoked through user-attributed event`, () => {
    const factId = { explained: 'fact.alpha', user_asserted: 'fact.beta', outcome_spoiled: 'fact.outcome' }[basis];
    const intent = buildKnowledgeIntent(
      makeContext(),
      knowledgeAction({ action: 'revoke_basis', factId, basis, reasonCode: 'viewer-revoked' }),
    );
    assert.equal(intent.events[0].effect, 'revoke');
    assert.equal(intent.events[0].basis, basis);
    assert.equal(intent.events[0].standing, 'revoked_assumption');
  });
}

test('revocation requires an active basis', () => {
  expectCode(
    () => buildKnowledgeIntent(makeContext(), knowledgeAction({ action: 'revoke_basis', factId: 'fact.alpha', basis: 'seen' })),
    'knowledge_revoke_requires_active_basis',
  );
});

test('revoked seen basis can be restored through reaffirm event', () => {
  const intent = buildKnowledgeIntent(
    makeContext(),
    knowledgeAction({ action: 'restore_basis', factId: 'fact.alpha', basis: 'seen', reasonCode: 'viewer-restored' }),
  );
  assert.equal(intent.events[0].effect, 'reaffirm');
  assert.equal(intent.events[0].standing, 'active_assumption');
});

test('restoration refuses an active basis', () => {
  expectCode(
    () => buildKnowledgeIntent(makeContext(), knowledgeAction({ action: 'restore_basis', factId: 'fact.alpha', basis: 'explained' })),
    'knowledge_restore_requires_revoked_basis',
  );
});

test('correction revokes every active basis and asserts replacement', () => {
  const intent = buildKnowledgeIntent(
    makeContext(),
    knowledgeAction({ action: 'correct_fact', factId: 'fact.alpha', replacementFactId: 'fact.beta', reasonCode: 'viewer-corrected' }),
  );
  assert.equal(intent.events.length, 2);
  assert.equal(intent.events[0].effect, 'revoke');
  assert.equal(intent.events[0].basis, 'explained');
  assert.equal(intent.events[1].factId, 'fact.beta');
  assert.equal(intent.events[1].basis, 'user_asserted');
  assert.equal(intent.events[1].effect, 'acquire');
});

test('correction refuses self replacement', () => {
  expectCode(
    () => buildKnowledgeIntent(makeContext(), knowledgeAction({ action: 'correct_fact', factId: 'fact.alpha', replacementFactId: 'fact.alpha' })),
    'knowledge_correction_self_replacement',
  );
});

test('correction refuses unknown replacement', () => {
  expectCode(
    () => buildKnowledgeIntent(makeContext(), knowledgeAction({ action: 'correct_fact', factId: 'fact.alpha', replacementFactId: 'fact.missing' })),
    'knowledge_correction_replacement_unknown',
  );
});

test('correction refuses fact without active basis', () => {
  expectCode(
    () => buildKnowledgeIntent(makeContext(), knowledgeAction({ action: 'correct_fact', factId: 'fact.future', replacementFactId: 'fact.beta' })),
    'knowledge_correction_requires_active_basis',
  );
});

test('knowledge intent is deterministic for exact action', () => {
  assert.deepEqual(buildKnowledgeIntent(makeContext(), knowledgeAction()), buildKnowledgeIntent(makeContext(), knowledgeAction()));
});

test('knowledge action identity changes event and intent identities', () => {
  const first = buildKnowledgeIntent(makeContext(), knowledgeAction());
  const second = buildKnowledgeIntent(makeContext(), knowledgeAction({ actionId: 'action:knowledge:2' }));
  assert.notEqual(first.intentId, second.intentId);
  assert.notEqual(first.events[0].eventId, second.events[0].eventId);
});

test('knowledge action refuses degraded context', () => {
  const context = makeContext({ state: 'disconnected', reasonCode: 'connection-lost', currentPositionUs: null });
  expectCode(() => buildKnowledgeIntent(context, knowledgeAction()), 'knowledge_action_context_not_ready');
});

test('knowledge intent contains no destructive erase operation', () => {
  const intent = buildKnowledgeIntent(makeContext(), knowledgeAction({ action: 'revoke_basis', factId: 'fact.alpha', basis: 'explained' }));
  assert.equal(canonicalJson(intent).includes('delete'), false);
  assert.equal(canonicalJson(intent).includes('erase'), false);
  assert.equal(intent.events[0].effect, 'revoke');
});

test('spoiler state starts without client-applied mutations', () => {
  const state = createSpoilerState(makeContext());
  assert.equal(state.policyIntent, null);
  assert.equal(state.knowledgeIntent, null);
  assert.deepEqual(state.deliveries, []);
});

test('fact selection is presentation-only', () => {
  const state = selectKnowledgeFact(createSpoilerState(makeContext()), 'fact.alpha');
  assert.equal(state.selectedFactId, 'fact.alpha');
  assert.equal(state.policyIntent, null);
  assert.equal(state.knowledgeIntent, null);
});

test('unknown fact selection becomes bounded refusal', () => {
  const state = selectKnowledgeFact(createSpoilerState(makeContext()), 'fact.missing');
  assert.equal(state.knowledgeRefusal.code, 'knowledge_fact_unknown');
});

test('policy request stores intent without changing external context', () => {
  const initial = createSpoilerState(makeContext());
  const state = requestSpoilerPolicyChange(initial, policyAction());
  assert.equal(state.policyIntent.mode, 'full_continuity');
  assert.equal(state.context.resolvedSpoilerMode, 'necessary_antecedents');
});

test('knowledge request stores intent without changing fact history', () => {
  const initial = createSpoilerState(makeContext());
  const before = canonicalJson(initial.context.facts);
  const state = requestKnowledgeChange(initial, knowledgeAction());
  assert.equal(state.knowledgeIntent.events.length, 1);
  assert.equal(canonicalJson(state.context.facts), before);
});

test('new policy request expires the prior policy intent', () => {
  let state = requestSpoilerPolicyChange(createSpoilerState(makeContext()), policyAction());
  state = requestSpoilerPolicyChange(state, policyAction({ actionId: 'action:policy:2', mode: 'scene_only' }));
  assert.equal(state.expiredIntents.length, 1);
  assert.equal(state.expiredIntents[0].expiredReason, 'superseded-by-policy-intent');
});

test('new knowledge request expires the prior knowledge intent', () => {
  let state = requestKnowledgeChange(createSpoilerState(makeContext()), knowledgeAction());
  state = requestKnowledgeChange(state, knowledgeAction({ actionId: 'action:knowledge:2' }));
  assert.equal(state.expiredIntents.length, 1);
  assert.equal(state.expiredIntents[0].expiredReason, 'superseded-by-knowledge-intent');
});

test('same context replay is idempotent', () => {
  const state = createSpoilerState(makeContext());
  assert.deepEqual(replaceSpoilerContext(state, makeContext()), state);
});

test('same context identity with changed content conflicts', () => {
  const state = createSpoilerState(makeContext());
  const changed = makeContext({ reasonCode: 'changed' });
  const next = replaceSpoilerContext(state, changed);
  assert.equal(next.refusal.code, 'context_identity_conflict');
});

test('same scope context sequence cannot regress', () => {
  const state = createSpoilerState(makeContext());
  const nextContext = makeContext({ contextId: 'spoiler-context:2', sequence: 9 });
  const next = replaceSpoilerContext(state, nextContext);
  assert.equal(next.refusal.code, 'context_sequence_regression');
});

test('applied intent settles only after external context records it', () => {
  let state = requestSpoilerPolicyChange(createSpoilerState(makeContext()), policyAction());
  const intentId = state.policyIntent.intentId;
  const context = contextWithResolved({
    contextId: 'spoiler-context:2',
    sequence: 11,
    storySpoilerMode: 'full_continuity',
    appliedIntentIds: [intentId],
  });
  state = replaceSpoilerContext(state, context);
  assert.equal(state.policyIntent, null);
  assert.equal(state.settledIntents.at(-1).standing, 'applied');
  assert.equal(state.context.resolvedSpoilerMode, 'full_continuity');
});

test('rejected intent settles without changing external policy', () => {
  let state = requestSpoilerPolicyChange(createSpoilerState(makeContext()), policyAction());
  const intentId = state.policyIntent.intentId;
  const context = makeContext({ contextId: 'spoiler-context:2', sequence: 11, rejectedIntentIds: [intentId] });
  state = replaceSpoilerContext(state, context);
  assert.equal(state.policyIntent, null);
  assert.equal(state.settledIntents.at(-1).standing, 'rejected');
  assert.equal(state.context.resolvedSpoilerMode, 'necessary_antecedents');
});

test('viewer replacement expires pending intents and selected fact', () => {
  let state = selectKnowledgeFact(createSpoilerState(makeContext()), 'fact.alpha');
  state = requestKnowledgeChange(state, knowledgeAction());
  const context = makeContext({
    contextId: 'spoiler-context:viewer-2',
    sequence: 1,
    viewerId: 'viewer.other',
    viewerDigest: '6'.repeat(64),
  });
  state = replaceSpoilerContext(state, context);
  assert.equal(state.knowledgeIntent, null);
  assert.equal(state.selectedFactId, 'fact.alpha');
  assert.equal(state.expiredIntents.at(-1).expiredReason, 'authority-scope-replaced');
});

test('package replacement expires pending intents and drops unknown selected fact', () => {
  let state = selectKnowledgeFact(createSpoilerState(makeContext()), 'fact.alpha');
  state = requestSpoilerPolicyChange(state, policyAction());
  const context = makeContext({
    contextId: 'spoiler-context:package-2',
    sequence: 1,
    storyPackageId: 'story.other',
    storyPackageDigest: '7'.repeat(64),
    facts: makeContext().facts.filter((fact) => fact.factId !== 'fact.alpha'),
  });
  state = replaceSpoilerContext(state, context);
  assert.equal(state.policyIntent, null);
  assert.equal(state.selectedFactId, null);
});

test('valid delivery records transport standing only', () => {
  let state = requestKnowledgeChange(createSpoilerState(makeContext()), knowledgeAction());
  const delivery = deliveryFor(state.knowledgeIntent);
  state = recordIntentDelivery(state, delivery);
  assert.equal(state.deliveries.length, 1);
  assert.equal(state.deliveries[0].authority, 'transport_receipt_only');
  assert.equal(state.context.facts[2].history.length, 0);
});

test('unknown delivery intent becomes bounded refusal', () => {
  const state = recordIntentDelivery(createSpoilerState(makeContext()), {
    ...deliveryFor(buildKnowledgeIntent(makeContext(), knowledgeAction())),
    intentId: 'knowledgeintent1_missing',
  });
  assert.equal(state.deliveryRefusal.code, 'delivery_intent_unknown');
});

test('exact delivery replay is idempotent', () => {
  let state = requestKnowledgeChange(createSpoilerState(makeContext()), knowledgeAction());
  const delivery = deliveryFor(state.knowledgeIntent);
  state = recordIntentDelivery(state, delivery);
  const replay = recordIntentDelivery(state, clone(delivery));
  assert.deepEqual(replay, state);
});

test('delivery identity with changed content conflicts', () => {
  let state = requestKnowledgeChange(createSpoilerState(makeContext()), knowledgeAction());
  const delivery = deliveryFor(state.knowledgeIntent);
  state = recordIntentDelivery(state, delivery);
  const changed = { ...delivery, state: 'queued' };
  const replay = recordIntentDelivery(state, changed);
  assert.equal(replay.deliveryRefusal.code, 'knowledge_delivery_identity_invalid');
});

test('delivery validator refuses intent substitution', () => {
  const intent = buildKnowledgeIntent(makeContext(), knowledgeAction());
  const delivery = deliveryFor(intent, { intentId: 'knowledgeintent1_other' });
  expectCode(() => validateIntentDelivery(delivery, intent), 'knowledge_delivery_intent_mismatch');
});

test('dismiss policy intent leaves knowledge intent intact', () => {
  let state = requestSpoilerPolicyChange(createSpoilerState(makeContext()), policyAction());
  state = requestKnowledgeChange(state, knowledgeAction());
  state = dismissSpoilerIntent(state, 'policy');
  assert.equal(state.policyIntent, null);
  assert.ok(state.knowledgeIntent);
});

test('dismiss knowledge intent leaves policy intent intact', () => {
  let state = requestSpoilerPolicyChange(createSpoilerState(makeContext()), policyAction());
  state = requestKnowledgeChange(state, knowledgeAction());
  state = dismissSpoilerIntent(state, 'knowledge');
  assert.ok(state.policyIntent);
  assert.equal(state.knowledgeIntent, null);
});

test('unsupported dismiss kind becomes bounded refusal', () => {
  const state = dismissSpoilerIntent(createSpoilerState(makeContext()), 'everything');
  assert.equal(state.refusal.code, 'intent_kind_unsupported');
});

test('view always exposes effective policy and scope', () => {
  const view = projectSpoilerView(createSpoilerState(makeContext()));
  assert.equal(view.spoilerPolicy.visibleBeforeAnswer, true);
  assert.equal(view.spoilerPolicy.effectiveMode, 'necessary_antecedents');
  assert.equal(view.spoilerPolicy.effectiveSource, 'global');
});

test('full continuity uses inline disclosure without modal coercion', () => {
  const context = contextWithResolved({ querySpoilerMode: 'full_continuity' });
  const view = projectSpoilerView(createSpoilerState(context));
  assert.deepEqual(view.spoilerPolicy.fullContinuityDisclosure, {
    visible: true,
    inline: true,
    modalRequired: false,
    coercivePreservation: false,
  });
  assert.equal(view.controls.requiresModal, false);
});

test('non-full-continuity policy hides only the full-continuity disclosure', () => {
  const view = projectSpoilerView(createSpoilerState(makeContext()));
  assert.equal(view.spoilerPolicy.fullContinuityDisclosure.visible, false);
  assert.equal(view.spoilerPolicy.visibleBeforeAnswer, true);
});

test('view explains why each available fact is available', () => {
  const view = projectSpoilerView(createSpoilerState(makeContext()));
  const alpha = view.facts.find((fact) => fact.factId === 'fact.alpha');
  assert.equal(alpha.available, true);
  assert.equal(alpha.availabilityReasons[0].kind, 'active_event_basis');
  assert.equal(alpha.availabilityReasons[0].basis, 'explained');
});

test('view exposes revoked history without erasing it', () => {
  const state = selectKnowledgeFact(createSpoilerState(makeContext()), 'fact.alpha');
  const view = projectSpoilerView(state);
  assert.equal(view.selectedFact.history.length, 3);
  assert.equal(view.selectedFact.history.some((event) => event.effect === 'revoke'), true);
  assert.equal(view.controls.canEraseHistory, false);
});

test('view keeps model proposals separate from availability', () => {
  const view = projectSpoilerView(createSpoilerState(makeContext()));
  const inferred = view.facts.find((fact) => fact.factId === 'fact.inferred');
  assert.equal(inferred.available, false);
  assert.equal(inferred.proposalCount, 1);
});

for (const stateName of CONTEXT_STATES) {
  test(`view control standing follows context state ${stateName}`, () => {
    const context = makeContext({
      state: stateName,
      reasonCode: stateName === 'ready' ? '' : `state-${stateName}`,
      currentPositionUs: stateName === 'ready' ? 10_000_000 : null,
    });
    const view = projectSpoilerView(createSpoilerState(context));
    assert.equal(view.state, stateName);
    assert.equal(view.controls.canChangeGlobalPolicy, stateName === 'ready');
  });
}

test('view authority keeps all mutations external', () => {
  const view = projectSpoilerView(createSpoilerState(makeContext()));
  assert.deepEqual(view.authority, {
    client: 'read_only_projection_and_intent_only',
    policy: 'external_daemon_authority',
    knowledge: 'external_ledger_authority',
    story: 'external_story_package_authority',
    appliedLocally: false,
  });
});

test('validated context and view are deeply immutable', () => {
  const context = validateSpoilerContext(makeContext());
  const view = projectSpoilerView(createSpoilerState(context));
  assert.throws(() => { context.facts[0].label = 'changed'; }, TypeError);
  assert.throws(() => { view.facts.push({}); }, TypeError);
});

test('input mutation after validation cannot change owned context', () => {
  const input = makeContext();
  const state = createSpoilerState(input);
  input.facts[0].label = 'mutated';
  assert.notEqual(state.context.facts[0].label, 'mutated');
});

test('source contains no transport persistence clock model or destructive history authority', () => {
  const source = [
    readFileSync(new URL('../../../clients/shared/spoilers/contract.mjs', import.meta.url), 'utf8'),
    readFileSync(new URL('../../../clients/shared/spoilers/reducer.mjs', import.meta.url), 'utf8'),
    readFileSync(new URL('../../../clients/shared/spoilers/view-model.mjs', import.meta.url), 'utf8'),
  ].join('\n');
  const forbidden = [
    /\bfetch\s*\(/,
    /WebSocket/,
    /XMLHttpRequest/,
    /localStorage/,
    /sessionStorage/,
    /indexedDB/,
    /setTimeout\s*\(/,
    /setInterval\s*\(/,
    /Date\.now\s*\(/,
    /\.play\s*\(/,
    /\.pause\s*\(/,
    /\.seek\s*\(/,
    /deleteKnowledge/i,
    /eraseHistory\s*\(/i,
    /commitKnowledge/i,
    /applyKnowledge/i,
    /model\.realize/i,
  ];
  for (const pattern of forbidden) assert.equal(pattern.test(source), false, String(pattern));
});

test('pure warm spoiler projection remains beneath five millisecond P95 source budget', () => {
  const state = createSpoilerState(makeContext());
  const samples = [];
  for (let index = 0; index < 2_000; index += 1) {
    const start = performance.now();
    projectSpoilerView(state);
    samples.push(performance.now() - start);
  }
  samples.sort((left, right) => left - right);
  const p95 = samples[Math.floor(samples.length * 0.95)];
  console.log(`SPOILER_CONTROL_WARM_P95_MS=${p95.toFixed(6)}`);
  assert.ok(p95 < 5, `observed ${p95}ms`);
});
