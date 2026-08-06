import {
  SPOILER_VIEW_VERSION,
  cloneOwned,
  factAvailability,
  validateSpoilerContext,
} from './contract.mjs';

function reasonCopy(context) {
  return {
    ready: 'Spoiler and knowledge controls are ready.',
    unavailable: 'Spoiler controls are unavailable for this source.',
    partial: 'Some policy or knowledge evidence is unavailable.',
    stale: 'The displayed policy and knowledge state is stale.',
    ambiguous: 'The active story or knowledge scope is ambiguous.',
    conflict: 'Conflicting policy or knowledge evidence requires review.',
    refused: 'The daemon refused the current policy or knowledge state.',
    unsupported: 'This surface cannot represent the supplied control state.',
    disconnected: 'The last verified policy is read-only while disconnected.',
  }[context.state];
}

function basisSummary(fact) {
  const active = fact.bases.filter((basis) => basis.active).map((basis) => basis.basis);
  const revoked = fact.bases.filter((basis) => !basis.active).map((basis) => basis.basis);
  const proposals = fact.history.filter((event) => event.standing === 'proposed_only').length;
  return { active, revoked, proposals };
}

export function projectSpoilerView(stateValue) {
  const state = cloneOwned(stateValue);
  const context = validateSpoilerContext(state.context);
  const interactive = context.state === 'ready';
  const facts = context.facts.map((fact) => {
    const availability = factAvailability(context, fact.factId);
    const summary = basisSummary(fact);
    return {
      factId: fact.factId,
      label: fact.label,
      available: availability.available,
      availabilityReasons: availability.reasons,
      policyAssumed: availability.policyAssumed,
      activeBases: summary.active,
      revokedBases: summary.revoked,
      proposalCount: summary.proposals,
      historyCount: fact.history.length,
      firstRevealPositionId: fact.firstRevealPositionId,
      firstRevealPositionUs: fact.firstRevealPositionUs,
    };
  });
  const selectedFact = state.selectedFactId
    ? context.facts.find((fact) => fact.factId === state.selectedFactId) ?? null
    : null;
  const selectedFactView = selectedFact
    ? {
        factId: selectedFact.factId,
        label: selectedFact.label,
        availability: factAvailability(context, selectedFact.factId),
        history: selectedFact.history.map((event) => ({
          eventId: event.eventId,
          effect: event.effect,
          basis: event.basis,
          standing: event.standing,
          actor: event.actor,
          recordedAtUs: event.recordedAtUs,
          sourceRefs: event.sourceRefs,
        })),
      }
    : null;
  return cloneOwned({
    version: SPOILER_VIEW_VERSION,
    contextId: context.contextId,
    sequence: context.sequence,
    state: context.state,
    reasonCode: context.reasonCode,
    statusCopy: reasonCopy(context),
    viewer: { viewerId: context.viewerId, viewerDigest: context.viewerDigest },
    story: {
      workId: context.workId,
      continuityId: context.continuityId,
      storyPackageId: context.storyPackageId,
      storyPackageDigest: context.storyPackageDigest,
      packageRevision: context.packageRevision,
      currentPositionId: context.currentPositionId,
      currentPositionUs: context.currentPositionUs,
    },
    spoilerPolicy: {
      globalMode: context.globalSpoilerMode,
      storyMode: context.storySpoilerMode,
      queryMode: context.querySpoilerMode,
      effectiveMode: context.resolvedSpoilerMode,
      effectiveSource: context.resolvedSpoilerSource,
      visibleBeforeAnswer: true,
      fullContinuityDisclosure: {
        visible: context.resolvedSpoilerMode === 'full_continuity',
        inline: true,
        modalRequired: false,
        coercivePreservation: false,
      },
    },
    knowledgePolicy: context.knowledgePolicy,
    facts,
    selectedFact: selectedFactView,
    pending: {
      policyIntent: state.policyIntent,
      knowledgeIntent: state.knowledgeIntent,
      deliveries: state.deliveries,
      settledIntents: state.settledIntents,
      expiredIntents: state.expiredIntents,
    },
    controls: {
      canChangeGlobalPolicy: interactive,
      canChangeStoryPolicy: interactive,
      canChangeQueryPolicy: interactive && context.queryId !== null,
      canConfirmFact: interactive && selectedFact !== null,
      canCorrectFact: interactive && selectedFact !== null,
      canRevokeBasis: interactive && selectedFact?.bases.some((basis) => basis.active) === true,
      canEraseHistory: false,
      requiresModal: false,
    },
    refusals: {
      context: state.refusal,
      policy: state.policyRefusal,
      knowledge: state.knowledgeRefusal,
      delivery: state.deliveryRefusal,
    },
    authority: {
      client: 'read_only_projection_and_intent_only',
      policy: 'external_daemon_authority',
      knowledge: 'external_ledger_authority',
      story: 'external_story_package_authority',
      appliedLocally: false,
    },
  });
}
