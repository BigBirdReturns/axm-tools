import {
  ANSWER_OBSERVATION_VERSION,
  PLANNER_OBSERVATION_VERSION,
  QUERY_CONTEXT_VERSION,
  QUERY_DELIVERY_VERSION,
  QUERY_INPUT_VERSION,
  buildQueryIntent,
  contentId,
} from '../../../clients/shared/queries/index.mjs';

export const digest = (character) => character.repeat(64);

export function makeContext(overrides = {}) {
  const core = {
    version: QUERY_CONTEXT_VERSION,
    sequence: 7,
    state: 'ready',
    reasonCode: '',
    storyPackageId: 'story-package:project-hail-mary:v1',
    storyPackageDigest: digest('a'),
    storyPackageRevision: 'revision:2026-08-05.1',
    workId: 'work:project-hail-mary',
    viewerProfileId: 'viewer:jonathan',
    viewerProfileDigest: digest('b'),
    anchor: {
      anchorId: 'anchor:project-hail-mary:scene-12',
      observationId: 'observation:anchor:1007',
      canonicalPositionUs: 1_842_000_000,
      clockMode: 'direct',
      identityMode: 'verified',
      clockConfidencePpm: 980_000,
      identityConfidencePpm: 1_000_000,
      state: 'paused',
      reasonCode: '',
    },
    queryPolicy: {
      allowedOperations: ['where_am_i', 'who_is_this', 'explain_this', 'ask'],
      allowedSpoilerModes: ['scene_only', 'necessary_antecedents', 'full_antecedent_chain'],
      maximumAnswerFacts: 8,
      maximumSegmentUs: 30_000_000,
      allowModelRealization: true,
    },
    accessReceiptRefs: ['access-receipt:query:1'],
    ...overrides,
  };
  if (overrides.anchor) core.anchor = { ...makeContext().anchor, ...overrides.anchor };
  if (overrides.queryPolicy) core.queryPolicy = { ...makeContext().queryPolicy, ...overrides.queryPolicy };
  return { contextId: contentId('querycontext1_', core), ...core };
}

export function makeInput(overrides = {}) {
  return {
    version: QUERY_INPUT_VERSION,
    activationId: 'activation:query:1',
    operation: 'explain_this',
    question: 'Why did this happen?',
    spoilerMode: 'necessary_antecedents',
    targetEntityIds: [],
    maximumAnswerFacts: 4,
    allowProse: true,
    ...overrides,
  };
}

export function makeIntent(context = makeContext(), input = makeInput()) {
  return buildQueryIntent(context, input);
}

export function makePlan(intent = makeIntent(), context = makeContext(), overrides = {}) {
  const core = {
    format: 'axm-aperture-answer-plan/1',
    query_id: intent.query.query_id,
    anchor_id: intent.anchorId,
    story_package_id: context.storyPackageId,
    story_digest: context.storyPackageDigest,
    facts: [
      {
        fact_id: 'fact:current-scene',
        role: 'current_scene',
        provenance_refs: ['source:chapter-12:paragraph-4'],
        already_known: true,
        delivered: true,
      },
      {
        fact_id: 'fact:necessary-cause',
        role: 'necessary_antecedent',
        provenance_refs: ['source:chapter-4:paragraph-9'],
        already_known: false,
        delivered: true,
      },
    ],
    withheld_fact_ids: ['fact:later-outcome'],
    spoiler_mode: intent.query.spoiler_mode,
    structured_fallback: [
      'The current scene establishes the immediate problem.',
      'An earlier reviewed event is the necessary cause.',
    ],
    model_policy: {
      allowed: intent.query.constraints.allow_model_realization,
      must_preserve_fact_ids: true,
      may_add_facts: false,
      maximum_output_characters: 2400,
    },
    ...overrides,
  };
  if (overrides.model_policy) core.model_policy = { ...makePlan(intent, context).model_policy, ...overrides.model_policy };
  return { plan_id: contentId('answerplan1_', core), ...core };
}

export function makePlannerObservation(intent = makeIntent(), context = makeContext(), overrides = {}) {
  const state = overrides.state ?? 'planned';
  const core = {
    version: PLANNER_OBSERVATION_VERSION,
    intentId: intent.intentId,
    queryId: intent.query.query_id,
    state,
    reasonCode: state === 'planned' ? '' : 'planner-refused',
    plannerReceiptRef: 'receipt:ap210:planner:1',
    plan: state === 'planned' ? makePlan(intent, context) : null,
    ...overrides,
  };
  return { observationId: contentId('plannerobs1_', core), ...core };
}

export function makeKnowledgeSummary(plan = makePlan(), overrides = {}) {
  return {
    authority: 'external_projection_only',
    applied: false,
    deliveredFactIds: ['fact:current-scene', 'fact:necessary-cause'],
    newlyExplainedFactIds: ['fact:necessary-cause'],
    alreadyKnownFactIds: ['fact:current-scene'],
    withheldCount: plan.withheld_fact_ids.length,
    projectedEvents: [
      {
        eventId: 'knowledge-event:fact-necessary-cause',
        factId: 'fact:necessary-cause',
        state: 'explained',
        applied: false,
      },
    ],
    effectReceiptRef: 'receipt:knowledge-effect:1',
    ...overrides,
  };
}

export function makeAnswerObservation(
  planner = makePlannerObservation(),
  intent = makeIntent(),
  context = makeContext(),
  overrides = {},
) {
  const plan = planner.plan;
  const state = overrides.state ?? 'validated_prose';
  const deliveredFactIds = plan.facts.filter((row) => row.delivered).map((row) => row.fact_id);
  const core = {
    version: ANSWER_OBSERVATION_VERSION,
    intentId: intent.intentId,
    planId: plan.plan_id,
    state,
    reasonCode: state === 'prose_refused' ? 'model-output-refused' : '',
    renderReceiptRef: 'receipt:ap215:render:1',
    structured: {
      format: 'axm-aperture-structured-answer/1',
      planId: plan.plan_id,
      factIds: [...deliveredFactIds],
      paragraphs: [...plan.structured_fallback],
      plainText: plan.structured_fallback.join(' '),
    },
    prose: state === 'validated_prose'
      ? {
          text: 'The immediate problem exists because the earlier reviewed event caused it.',
          factIds: [...deliveredFactIds],
        }
      : null,
    knowledgeEffectSummary: makeKnowledgeSummary(plan),
    ...overrides,
  };
  return { observationId: contentId('answerobs1_', core), ...core };
}

export function makeDelivery(intent = makeIntent(), overrides = {}) {
  return {
    version: QUERY_DELIVERY_VERSION,
    receiptId: 'delivery:query:1',
    intentId: intent.intentId,
    status: 'delivered',
    reasonCode: '',
    ...overrides,
  };
}
