import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import test from 'node:test';
import {
  ANSWER_OBSERVATION_VERSION,
  QUERY_INPUT_VERSION,
  buildQueryIntent,
  canonicalJson,
  contentId,
  createQueryState,
  dismissQuery,
  ingestAnswerObservation,
  ingestPlannerObservation,
  plannerMessage,
  projectQueryView,
  recordQueryDelivery,
  replaceQueryContext,
  requestQuery,
  selectQueryRendering,
  validateAnswerObservation,
  validateAnswerPlan,
  validatePlannerObservation,
  validateQueryContext,
  validateQueryDelivery,
  validateQueryInput,
  validateQueryIntent,
  validateStateIntent,
} from '../../../clients/shared/queries/index.mjs';
import {
  digest,
  makeAnswerObservation,
  makeContext,
  makeDelivery,
  makeInput,
  makeIntent,
  makeKnowledgeSummary,
  makePlan,
  makePlannerObservation,
} from './fixtures.mjs';

function throwsCode(fn, code) {
  assert.throws(fn, (error) => error?.code === code, `expected ${code}`);
}

function plannedState({ context = makeContext(), input = makeInput() } = {}) {
  const intent = makeIntent(context, input);
  const planner = makePlannerObservation(intent, context);
  let state = createQueryState(context);
  state = requestQuery(state, input);
  state = ingestPlannerObservation(state, planner);
  return { state, intent, planner, context, input };
}

function answeredState(options = {}) {
  const setup = plannedState(options);
  const answer = makeAnswerObservation(setup.planner, setup.intent, setup.context);
  return { ...setup, answer, state: ingestAnswerObservation(setup.state, answer) };
}

test('valid context is content-addressed and deeply immutable', () => {
  const context = validateQueryContext(makeContext());
  assert.equal(context.contextId, contentId('querycontext1_', context, 'contextId'));
  assert.equal(Object.isFrozen(context), true);
  assert.equal(Object.isFrozen(context.anchor), true);
  assert.equal(Object.isFrozen(context.queryPolicy.allowedOperations), true);
});

test('unknown context field fails closed', () => {
  throwsCode(() => validateQueryContext({ ...makeContext(), surprise: true }), 'query_context_fields_invalid');
});

test('sensitive context field fails closed', () => {
  const context = makeContext();
  context.anchor.token = 'forbidden';
  throwsCode(() => validateQueryContext(context), 'credential_field_forbidden');
});

test('changed context bytes under one identity fail closed', () => {
  const context = makeContext();
  context.sequence = 8;
  throwsCode(() => validateQueryContext(context), 'query_context_identity_mismatch');
});

test('ready context requires canonical position', () => {
  throwsCode(() => validateQueryContext(makeContext({ anchor: { canonicalPositionUs: null } })), 'ready_context_requires_canonical_position');
});

test('ready context rejects unknown identity', () => {
  throwsCode(() => validateQueryContext(makeContext({ anchor: { identityMode: 'unknown' } })), 'ready_context_identity_not_admitted');
});

test('degraded context may carry null position with explicit reason', () => {
  const context = validateQueryContext(makeContext({
    state: 'ambiguous',
    reasonCode: 'anchor-ambiguous',
    anchor: { canonicalPositionUs: null, identityMode: 'conflict', clockMode: 'none' },
  }));
  assert.equal(context.state, 'ambiguous');
});

test('unsupported operation in policy fails closed', () => {
  throwsCode(() => validateQueryContext(makeContext({ queryPolicy: { allowedOperations: ['bridge_gap'] } })), 'query_policy_operation_unsupported');
});

test('free-form ask requires a question', () => {
  throwsCode(() => validateQueryInput(makeInput({ operation: 'ask', question: null })), 'free_form_question_required');
});

test('who-is-this requires explicit entity target', () => {
  throwsCode(() => validateQueryInput(makeInput({ operation: 'who_is_this', targetEntityIds: [] })), 'identity_target_required');
});

test('where-am-I refuses entity targets', () => {
  throwsCode(
    () => validateQueryInput(makeInput({ operation: 'where_am_i', question: null, targetEntityIds: ['entity:ryland'] })),
    'where_am_i_target_forbidden',
  );
});

test('query intent binds package, viewer, anchor, and revision', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  assert.equal(intent.storyPackageRevision, context.storyPackageRevision);
  assert.equal(intent.viewerProfileDigest, context.viewerProfileDigest);
  assert.equal(intent.anchorObservationId, context.anchor.observationId);
  assert.equal(validateQueryIntent(intent, context).intentId, intent.intentId);
});

test('same normative query keeps query ID across activation identity', () => {
  const context = makeContext();
  const first = makeIntent(context, makeInput({ activationId: 'activation:one' }));
  const second = makeIntent(context, makeInput({ activationId: 'activation:two' }));
  assert.equal(first.query.query_id, second.query.query_id);
  assert.notEqual(first.intentId, second.intentId);
});

test('operation outside policy is refused before intent construction', () => {
  const context = makeContext({ queryPolicy: { allowedOperations: ['where_am_i'] } });
  throwsCode(() => buildQueryIntent(context, makeInput()), 'query_operation_not_authorized');
});

test('spoiler mode outside policy is refused before intent construction', () => {
  throwsCode(
    () => buildQueryIntent(makeContext(), makeInput({ spoilerMode: 'full_continuity' })),
    'query_spoiler_mode_not_authorized',
  );
});

test('fact budget cannot exceed context policy', () => {
  throwsCode(() => buildQueryIntent(makeContext(), makeInput({ maximumAnswerFacts: 9 })), 'query_fact_budget_exceeded');
});

test('prose cannot be requested when model realization is not admitted', () => {
  throwsCode(
    () => buildQueryIntent(makeContext({ queryPolicy: { allowModelRealization: false } }), makeInput()),
    'query_prose_not_authorized',
  );
});

test('degraded context cannot emit a query intent', () => {
  throwsCode(
    () => buildQueryIntent(makeContext({ state: 'stale', reasonCode: 'anchor-stale' }), makeInput()),
    'query_context_not_ready',
  );
});

test('query ID rejects changed normative content', () => {
  const intent = structuredClone(makeIntent());
  intent.query.question = 'Changed question';
  throwsCode(() => validateQueryIntent(intent), 'query_identity_mismatch');
});

test('intent identity rejects changed activation', () => {
  const intent = structuredClone(makeIntent());
  intent.activationId = 'activation:changed';
  throwsCode(() => validateQueryIntent(intent), 'query_intent_identity_mismatch');
});

test('delivery receipt records transport only', () => {
  const context = makeContext();
  const input = makeInput();
  let state = requestQuery(createQueryState(context), input);
  state = recordQueryDelivery(state, makeDelivery(state.currentIntent));
  assert.equal(state.plannerObservation, null);
  assert.equal(projectQueryView(state).state, 'planning');
  assert.deepEqual(projectQueryView(state).request.deliveryReceiptIds, ['delivery:query:1']);
});

test('delivery bound to unknown request produces bounded refusal', () => {
  const state = recordQueryDelivery(createQueryState(makeContext()), makeDelivery());
  assert.equal(state.requestRefusal.code, 'delivery_intent_unknown');
});

test('delivery cannot bind another intent', () => {
  const intent = makeIntent();
  throwsCode(
    () => validateQueryDelivery(makeDelivery(intent, { intentId: 'queryintent:other' }), intent),
    'query_delivery_intent_mismatch',
  );
});

test('answer plan identity and exact scope validate', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  const plan = validateAnswerPlan(makePlan(intent, context), intent, context);
  assert.equal(plan.plan_id, contentId('answerplan1_', plan, 'plan_id'));
});

test('answer plan refuses changed query', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { query_id: 'query1_' + digest('c') }), intent, context),
    'answer_plan_query_mismatch',
  );
});

test('answer plan refuses changed anchor', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { anchor_id: 'anchor:other' }), intent, context),
    'answer_plan_anchor_mismatch',
  );
});

test('answer plan refuses changed package', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { story_package_id: 'story-package:other' }), intent, context),
    'answer_plan_package_mismatch',
  );
});

test('answer plan refuses changed story digest', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { story_digest: digest('d') }), intent, context),
    'answer_plan_story_digest_mismatch',
  );
});

test('answer plan cannot silently widen spoiler mode', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { spoiler_mode: 'full_continuity' }), intent, context),
    'answer_plan_spoiler_mode_mismatch',
  );
});

test('answer plan enforces fact budget', () => {
  const context = makeContext();
  const input = makeInput({ maximumAnswerFacts: 1 });
  const intent = makeIntent(context, input);
  throwsCode(() => validateAnswerPlan(makePlan(intent, context), intent, context), 'answer_plan_fact_budget_exceeded');
});

test('answer plan rejects duplicate facts', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  const base = makePlan(intent, context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { facts: [base.facts[0], base.facts[0]] }), intent, context),
    'answer_plan_duplicate_fact',
  );
});

test('answer plan rejects delivered and withheld overlap', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { withheld_fact_ids: ['fact:current-scene'] }), intent, context),
    'answer_plan_delivered_withheld_overlap',
  );
});

test('answer plan fallback must map one-to-one to delivered facts', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { structured_fallback: ['Only one paragraph.'] }), intent, context),
    'answer_plan_fallback_length_mismatch',
  );
});

test('answer plan model policy may never add facts', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { model_policy: { may_add_facts: true } }), intent, context),
    'answer_plan_model_authority_invalid',
  );
});

test('answer plan cannot authorize a model when query refused prose', () => {
  const context = makeContext();
  const intent = makeIntent(context, makeInput({ allowProse: false }));
  throwsCode(
    () => validateAnswerPlan(makePlan(intent, context, { model_policy: { allowed: true } }), intent, context),
    'answer_plan_model_not_authorized',
  );
});

test('planned observation requires a plan', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  const observation = makePlannerObservation(intent, context, { plan: null });
  throwsCode(() => validatePlannerObservation(observation, intent, context), 'answer_plan_invalid');
});

test('planner refusal cannot carry a plan', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  const observation = makePlannerObservation(intent, context, {
    state: 'refused',
    reasonCode: 'planner-refused',
    plan: makePlan(intent, context),
  });
  throwsCode(() => validatePlannerObservation(observation, intent, context), 'planner_refusal_plan_forbidden');
});

test('planner observation is content-addressed', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  const observation = validatePlannerObservation(makePlannerObservation(intent, context), intent, context);
  assert.equal(observation.observationId, contentId('plannerobs1_', observation, 'observationId'));
});

test('planner refusal produces bounded deterministic copy', () => {
  const context = makeContext();
  const input = makeInput();
  const intent = makeIntent(context, input);
  const planner = makePlannerObservation(intent, context, {
    state: 'refused',
    reasonCode: 'planner-refused',
    plan: null,
  });
  let state = requestQuery(createQueryState(context), input);
  state = ingestPlannerObservation(state, planner);
  const view = projectQueryView(state);
  assert.equal(view.state, 'refused');
  assert.equal(view.refusalMessage, 'The deterministic planner refused this question.');
  assert.equal(view.answer, null);
});

test('unknown planner reason uses bounded fallback, not chatbot prose', () => {
  assert.equal(plannerMessage('unknown-code'), 'The deterministic planner returned a bounded refusal.');
});

test('structured answer exactly preserves plan facts and fallback', () => {
  const { intent, planner, context } = plannedState();
  const answer = validateAnswerObservation(makeAnswerObservation(planner, intent, context), planner, intent, context);
  assert.deepEqual(answer.structured.factIds, ['fact:current-scene', 'fact:necessary-cause']);
  assert.deepEqual(answer.structured.paragraphs, planner.plan.structured_fallback);
});

test('structured answer cannot widen fact set', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.structured.factIds.push('fact:hidden');
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'structured_answer_fact_set_mismatch');
});

test('structured answer cannot change planned paragraph', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.structured.paragraphs[1] = 'A new unplanned claim.';
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'structured_answer_fallback_mismatch');
});

test('structured plain text must derive exactly from paragraphs', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.structured.plainText = 'Different text';
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'structured_answer_plain_text_mismatch');
});

test('validated prose preserves exact planned fact order', () => {
  const { intent, planner, context } = plannedState();
  const answer = validateAnswerObservation(makeAnswerObservation(planner, intent, context), planner, intent, context);
  assert.deepEqual(answer.prose.factIds, answer.structured.factIds);
});

test('validated prose cannot add a hidden fact', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.prose.factIds.push('fact:hidden');
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'prose_answer_fact_set_mismatch');
});

test('validated prose obeys plan character budget', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.prose.text = 'x'.repeat(planner.plan.model_policy.maximum_output_characters + 1);
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'prose_answer_text_invalid');
});

test('prose-refused state retains exact structured fallback', () => {
  const { state, intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context, { state: 'prose_refused' });
  const next = ingestAnswerObservation(state, answer);
  const view = projectQueryView(next);
  assert.equal(view.answer.proseRefused, true);
  assert.equal(view.answer.structured.available, true);
  assert.equal(view.answer.selectedRendering, 'structured');
});

test('structured-only state forbids prose payload', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context, { state: 'structured_only' });
  answer.prose = { text: 'Unadmitted prose', factIds: answer.structured.factIds };
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'prose_payload_forbidden_for_state');
});

test('knowledge effect remains external and unapplied', () => {
  const { intent, planner, context } = plannedState();
  const answer = validateAnswerObservation(makeAnswerObservation(planner, intent, context), planner, intent, context);
  assert.equal(answer.knowledgeEffectSummary.authority, 'external_projection_only');
  assert.equal(answer.knowledgeEffectSummary.applied, false);
});

test('knowledge effect cannot claim application', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.knowledgeEffectSummary.applied = true;
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'knowledge_effect_application_forbidden');
});

test('knowledge effect new and known partitions must match plan', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.knowledgeEffectSummary.newlyExplainedFactIds = ['fact:current-scene'];
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'knowledge_new_fact_set_mismatch');
});

test('knowledge event cannot name an unplanned fact', () => {
  const { intent, planner, context } = plannedState();
  const answer = makeAnswerObservation(planner, intent, context);
  answer.knowledgeEffectSummary.projectedEvents[0].factId = 'fact:hidden';
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'knowledge_projected_event_fact_mismatch');
});

test('knowledge event IDs must be unique', () => {
  const context = makeContext();
  const intent = makeIntent(context);
  const plan = makePlan(intent, context, {
    facts: [
      {
        fact_id: 'fact:a', role: 'current_scene', provenance_refs: ['source:a'], already_known: false, delivered: true,
      },
      {
        fact_id: 'fact:b', role: 'necessary_antecedent', provenance_refs: ['source:b'], already_known: false, delivered: true,
      },
    ],
    structured_fallback: ['A', 'B'],
  });
  const planner = makePlannerObservation(intent, context, { plan });
  const answer = makeAnswerObservation(planner, intent, context, {
    structured: {
      format: 'axm-aperture-structured-answer/1',
      planId: plan.plan_id,
      factIds: ['fact:a', 'fact:b'],
      paragraphs: ['A', 'B'],
      plainText: 'A B',
    },
    prose: { text: 'A B', factIds: ['fact:a', 'fact:b'] },
    knowledgeEffectSummary: {
      authority: 'external_projection_only', applied: false,
      deliveredFactIds: ['fact:a', 'fact:b'], newlyExplainedFactIds: ['fact:a', 'fact:b'], alreadyKnownFactIds: [],
      withheldCount: 1,
      projectedEvents: [
        { eventId: 'event:same', factId: 'fact:a', state: 'explained', applied: false },
        { eventId: 'event:same', factId: 'fact:b', state: 'explained', applied: false },
      ],
      effectReceiptRef: 'receipt:effect',
    },
  });
  throwsCode(() => validateAnswerObservation(answer, planner, intent, context), 'knowledge_projected_event_duplicate');
});

test('view displays package revision and exact identity', () => {
  const view = projectQueryView(answeredState().state);
  assert.equal(view.package.storyPackageRevision, 'revision:2026-08-05.1');
  assert.equal(view.package.storyPackageDigest, digest('a'));
});

test('view reports conservative anchor confidence', () => {
  const view = projectQueryView(answeredState().state);
  assert.equal(view.anchor.confidencePpm, 980_000);
  assert.equal(view.anchor.confidenceLabel, 'strong');
});

test('view displays included fact IDs, roles, provenance, and known standing', () => {
  const view = projectQueryView(answeredState().state);
  assert.deepEqual(view.plan.includedFacts[1], {
    factId: 'fact:necessary-cause',
    role: 'necessary_antecedent',
    provenanceRefs: ['source:chapter-4:paragraph-9'],
    alreadyKnown: false,
    paragraph: 'An earlier reviewed event is the necessary cause.',
  });
});

test('view exposes withheld count without withheld identities', () => {
  const view = projectQueryView(answeredState().state);
  assert.equal(view.plan.withheldCount, 1);
  assert.equal(JSON.stringify(view).includes('fact:later-outcome'), false);
});

test('structured fallback is available before optional realization arrives', () => {
  const view = projectQueryView(plannedState().state);
  assert.equal(view.state, 'planned');
  assert.equal(view.answer.structured.available, true);
  assert.equal(view.answer.proseAvailable, false);
});

test('knowledge summary remains visibly pending before external effect projection', () => {
  const view = projectQueryView(plannedState().state);
  assert.equal(view.answer.knowledgeEffectSummary.available, false);
  assert.equal(view.answer.knowledgeEffectSummary.applied, false);
  assert.equal(view.answer.knowledgeEffectSummary.newlyExplainedCount, 1);
});

test('validated prose may be selected without replacing structured fallback', () => {
  const setup = answeredState();
  const state = selectQueryRendering(setup.state, 'prose');
  const view = projectQueryView(state);
  assert.equal(view.answer.selectedRendering, 'prose');
  assert.equal(view.answer.proseAvailable, true);
  assert.equal(view.answer.structured.available, true);
});

test('prose cannot be selected before validation', () => {
  const state = selectQueryRendering(plannedState().state, 'prose');
  assert.equal(state.renderingRefusal.code, 'validated_prose_unavailable');
  assert.equal(projectQueryView(state).answer.selectedRendering, 'structured');
});

test('malformed answer becomes bounded rendering refusal and leaves structured fallback', () => {
  const setup = plannedState();
  const answer = makeAnswerObservation(setup.planner, setup.intent, setup.context);
  answer.prose.factIds.push('fact:hidden');
  const state = ingestAnswerObservation(setup.state, answer);
  assert.equal(state.renderingRefusal.code, 'prose_answer_fact_set_mismatch');
  assert.equal(projectQueryView(state).answer.structured.available, true);
});

test('context replacement expires request and preserves result only as stale read-only', () => {
  const setup = answeredState();
  const nextContext = makeContext({ sequence: 8, anchor: { observationId: 'observation:anchor:1008', canonicalPositionUs: 1_900_000_000 } });
  const state = replaceQueryContext(setup.state, nextContext);
  const view = projectQueryView(state);
  assert.equal(view.state, 'stale');
  assert.equal(view.actions.readOnly, true);
  assert.equal(view.actions.canSelectProse, false);
  assert.deepEqual(view.expiredIntentIds, [setup.intent.intentId]);
});

test('same context replay is idempotent', () => {
  const state = createQueryState(makeContext());
  assert.deepEqual(replaceQueryContext(state, makeContext()), state);
});

test('same context identity with changed bytes becomes conflict', () => {
  const state = createQueryState(makeContext());
  const changed = structuredClone(makeContext());
  changed.reasonCode = 'changed';
  const next = replaceQueryContext(state, changed);
  assert.equal(next.refusal.code, 'query_context_identity_mismatch');
});

test('context sequence regression fails closed', () => {
  const state = createQueryState(makeContext({ sequence: 9 }));
  const next = replaceQueryContext(state, makeContext({ sequence: 8, anchor: { observationId: 'observation:anchor:1008' } }));
  assert.equal(next.refusal.code, 'context_sequence_regression');
});

test('package replacement cannot reuse prior result', () => {
  const setup = answeredState();
  const next = replaceQueryContext(setup.state, makeContext({
    sequence: 8,
    storyPackageId: 'story-package:other',
    storyPackageDigest: digest('e'),
  }));
  assert.equal(next.currentIntent, null);
  assert.equal(projectQueryView(next).stale, true);
});

test('viewer replacement cannot reuse prior result', () => {
  const setup = answeredState();
  const next = replaceQueryContext(setup.state, makeContext({
    sequence: 8,
    viewerProfileId: 'viewer:other',
    viewerProfileDigest: digest('f'),
  }));
  assert.equal(next.currentIntent, null);
  assert.equal(projectQueryView(next).viewer.viewerProfileId, 'viewer:jonathan');
});

test('anchor replacement cannot attach prior answer to new position', () => {
  const setup = answeredState();
  const nextContext = makeContext({ sequence: 8, anchor: { anchorId: 'anchor:new', observationId: 'observation:new' } });
  const next = replaceQueryContext(setup.state, nextContext);
  const view = projectQueryView(next);
  assert.equal(view.anchor.anchorId, setup.context.anchor.anchorId);
  assert.equal(view.stale, true);
});

test('new request supersedes prior request deterministically', () => {
  const context = makeContext();
  let state = requestQuery(createQueryState(context), makeInput({ activationId: 'activation:first' }));
  const first = state.currentIntent;
  state = requestQuery(state, makeInput({ activationId: 'activation:second' }));
  assert.equal(state.expiredIntents[0].intentId, first.intentId);
  assert.equal(state.expiredIntents[0].expiredReason, 'superseded-by-new-query');
});

test('planner observation without request is bounded refusal', () => {
  const state = ingestPlannerObservation(createQueryState(makeContext()), makePlannerObservation());
  assert.equal(state.refusal.code, 'planner_observation_without_request');
});

test('answer observation without plan is bounded refusal', () => {
  const state = ingestAnswerObservation(createQueryState(makeContext()), {});
  assert.equal(state.renderingRefusal.code, 'answer_observation_without_plan');
});

test('dismiss clears active transaction but retains context', () => {
  const setup = answeredState();
  const state = dismissQuery(setup.state);
  assert.equal(state.currentIntent, null);
  assert.equal(projectQueryView(state).state, 'idle');
  assert.equal(state.context.contextId, setup.context.contextId);
});

test('validated state retains exact current intent scope', () => {
  const setup = answeredState();
  assert.equal(validateStateIntent(setup.state), true);
});

test('validated inputs are clone-owned from caller mutation', () => {
  const source = makeContext();
  const state = createQueryState(source);
  source.anchor.canonicalPositionUs = 1;
  assert.equal(state.context.anchor.canonicalPositionUs, 1_842_000_000);
});

test('reducer states are deeply immutable', () => {
  const state = answeredState().state;
  assert.equal(Object.isFrozen(state), true);
  assert.equal(Object.isFrozen(state.answerObservation.knowledgeEffectSummary.projectedEvents), true);
});

test('query views are deeply immutable', () => {
  const view = projectQueryView(answeredState().state);
  assert.equal(Object.isFrozen(view), true);
  assert.equal(Object.isFrozen(view.plan.includedFacts), true);
  assert.equal(Object.isFrozen(view.answer.knowledgeEffectSummary), true);
});

test('source contains no transport, model execution, persistence, or ledger mutation authority', () => {
  const source = [
    readFileSync(new URL('../../../clients/shared/queries/contract.mjs', import.meta.url), 'utf8'),
    readFileSync(new URL('../../../clients/shared/queries/reducer.mjs', import.meta.url), 'utf8'),
    readFileSync(new URL('../../../clients/shared/queries/view-model.mjs', import.meta.url), 'utf8'),
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
    /process\.env\.(?:TOKEN|SECRET|PASSWORD)/i,
    /\.realize\s*\(/,
    /knowledge_events_from_plan/,
    /applyKnowledge/i,
    /commitKnowledge/i,
    /play\s*\(/,
    /pause\s*\(/,
    /seek\s*\(/,
  ];
  for (const pattern of forbidden) assert.equal(pattern.test(source), false, String(pattern));
});

test('pure warm view projection remains beneath five millisecond P95 source-candidate budget', () => {
  const state = answeredState().state;
  const samples = [];
  for (let index = 0; index < 2_000; index += 1) {
    const start = performance.now();
    projectQueryView(state);
    samples.push(performance.now() - start);
  }
  samples.sort((a, b) => a - b);
  const p95 = samples[Math.floor(samples.length * 0.95)];
  console.log(`QUERY_TRANSACTION_WARM_P95_MS=${p95.toFixed(6)}`);
  assert.ok(p95 < 5, `warm P95 ${p95}ms exceeds candidate budget`);
});

test('canonical JSON is stable across key insertion order', () => {
  assert.equal(canonicalJson({ b: 2, a: 1 }), canonicalJson({ a: 1, b: 2 }));
});

test('AP-404 receipt is closed and preserves predecessor authority', () => {
  const receipt = JSON.parse(readFileSync(new URL('../../../receipts/AP-404.json', import.meta.url), 'utf8'));
  assert.equal(receipt.transaction, 'AP-404');
  assert.equal(receipt.canonical_ap404_accepted, false);
  assert.equal(receipt.canonical_g3_accepted, false);
  assert.equal(receipt.hosted_repository_accepted, false);
  assert.equal(receipt.predecessors.AP_210.issue_receipt_sha256, '3188324f334e2f79b77455e22dddd2db06730592b6d2ef3e79e4e74d0efc1c64');
  assert.equal(receipt.predecessors.AP_215.issue_receipt_sha256, '720ae9703b4afac04a2bbcea3a74460ee37c167aca93f874d236664593e1bfb6');
  assert.equal(receipt.predecessors.AP_402.artifact_id, 8950448870);
  assert.equal(receipt.predecessors.AP_403.artifact_id, 8954499976);
});
