(() => {
  'use strict';

  const RELEASE = 'mw-working-model-v1.0.0';
  const STORAGE_KEY = 'mw-working-model-v1-draft';

  const scenarios = {
    wildfire: {
      kicker: 'Representative case · wildfire assistance',
      title: 'A resident wants help reducing wildfire exposure without becoming a risk score.',
      summary: 'Public context can focus attention. It cannot diagnose the parcel, decide eligibility, or authorize work. The useful output is a source-backed verification and assistance path.',
      output: 'A verification and assistance packet that preserves every unknown, authority boundary, stop condition, and handoff.',
      prohibited: 'No parcel score, eligibility decision, insurance consequence, work order, field finding, or claim that help was delivered.',
      stages: [
        ['Signal', 'A resident, neighbor, or program asks a specific assistance question. Regional fire or weather context may increase attention, but it does not diagnose a specific home.'],
        ['Source', 'Use public fire and weather context, Place Fabric, and resident-supplied facts. Missing, stale, map-only, authored, and contradictory states stay visible.'],
        ['Authority', 'The resident controls lived facts and consent. The program sponsor controls its offer and resources. Qualified field actors control work only inside lawful, accepted scope.'],
        ['Safe action', 'Prepare the minimum verification, assistance, material, or referral path needed to answer the resident’s question. Keep preparation distinct from inspection or work.'],
        ['Fallback', 'If imagery or source coverage is insufficient, hold the claim. Ask for the minimum first-party observation, use map-only context, or route to a human source check.'],
        ['Closure', 'Record whether the requested help reached an accepted outcome, was refused, was deferred, or remains blocked. Do not record a pass/fail grade for the property.'],
        ['Learning', 'Track repeated gaps in assistance, sources, tools, labor, or program design without exposing household identity or creating a penalty.']
      ]
    },
    tools: {
      kicker: 'Representative case · tools + time',
      title: 'A neighbor needs a tool and enough human help to use it safely.',
      summary: 'Inventory is only one resource. The real case may require a tool, a person, time, transport, instruction, space, money, or a fallback. Those resources need different rules but one project context.',
      output: 'A capacity match that states what is needed, what is available, what each provider commits, and what closes the obligation.',
      prohibited: 'No silent assignment of volunteers, no inferred inventory, no promise that a tool or skill is available, and no permanent debt manufactured from participation.',
      stages: [
        ['Signal', 'A participant states a concrete need or someone publishes a concrete offer. The system preserves who said what and whether it is a request, offer, or commitment.'],
        ['Source', 'Check the current inventory or offer record, availability window, skill or training conditions, project context, and any required transport or space.'],
        ['Authority', 'The resource owner controls the tool or space. A person controls their own time and skill. The organization controls only resources and commitments it actually owns.'],
        ['Safe action', 'Prepare a match or commitment that states the resource, duration, rules, handoff, and responsible party. A suggestion remains a suggestion until accepted.'],
        ['Fallback', 'If the first resource is unavailable, route to another tool, date, lending partner, purchase option, or instruction, or record that the need cannot be met.'],
        ['Closure', 'Close the loan, return, contribution, workshop, or declined match with an explicit receipt. Do not leave the obligation living in someone’s memory.'],
        ['Learning', 'Use repeated unmet needs to decide what the community should acquire, teach, stock, schedule, or partner for next.']
      ]
    },
    mobility: {
      kicker: 'Representative case · mobility',
      title: 'A community member needs a practical transportation path, not another program directory.',
      summary: 'The case begins with the actual trip and constraint. Equipment, route, repair, instruction, funding, storage, scheduling, and accessibility can participate without becoming one monolithic service.',
      output: 'A mobility path that keeps the trip need, available resources, responsible people, fallback, acceptance, and unresolved constraints together.',
      prohibited: 'No promise of vehicle availability, route safety, funding eligibility, repair completion, or participant fitness without the actor and evidence that can actually establish it.',
      stages: [
        ['Signal', 'A person states the trip, access, cost, repair, equipment, or confidence problem that is preventing useful mobility.'],
        ['Source', 'Use current resource records, route context, first-party constraints, equipment status, program terms, and provider receipts while preserving their different sources and authority.'],
        ['Authority', 'The participant controls acceptance. Equipment owners control equipment. Program owners control program resources. Qualified providers control repair or instruction inside scope.'],
        ['Safe action', 'Prepare the smallest viable mobility option: a loan, repair path, training session, route question, funding application, or combination with named owners.'],
        ['Fallback', 'If the preferred mode fails, preserve why and route to a different mode, date, provider, funding source, or explicit hold rather than inventing availability.'],
        ['Closure', 'Record the accepted, refused, completed, deferred, or blocked outcome and the return or follow-up obligation, if any.'],
        ['Learning', 'Repeated transportation gaps provide evidence for shared vehicles, repair capacity, route support, storage, training, or partnerships.']
      ]
    },
    continuity: {
      kicker: 'Representative case · continuity',
      title: 'A good idea should not disappear when the person carrying it gets busy, leaves, or stops replying.',
      summary: 'Offers, advice, decisions, unknowns, authority, and next safe actions must remain distinct. Preserving those differences prevents enthusiasm from turning into invisible labor.',
      output: 'A portable working case file that another person can reopen and understand without inheriting unstated authority or private context.',
      prohibited: 'No converting interest into assignment, silence into rejection, a meeting mention into a commitment, or a remembered relationship into institutional authority.',
      stages: [
        ['Signal', 'A meeting, message, source packet, offer, question, or decision creates something that may matter later.'],
        ['Source', 'Preserve the literal evidence, source summary, date, force, parties, and what is still unknown. Do not upgrade an interpretation because it is convenient.'],
        ['Authority', 'Name who can decide, who can prepare, who is affected, and every effect still withheld. Nobody inherits authority by being close to the work.'],
        ['Safe action', 'Route only the next bounded internal move: recover a source, ask one question, draft a disposition, prepare a packet, or explicitly hold.'],
        ['Fallback', 'If the owner, source, budget, scope, or authority is absent, preserve the object as unresolved or expire it under a stated rule. Do not assign the nearest capable person.'],
        ['Closure', 'Record the outcome, source, decision, acceptance, expiration, or remaining hold so another person can reopen the case without reconstruction.'],
        ['Learning', 'Repeated continuity failures expose missing operating functions, bad handoffs, unowned decisions, or work that needs a funded operator rather than heroic memory.']
      ]
    }
  };

  const byId = (id) => document.getElementById(id);
  const tabs = [...document.querySelectorAll('.scenario-tab')];
  const panel = byId('scenario-panel');
  const stageGrid = byId('stage-grid');

  function renderScenario(id, { syncForm = true } = {}) {
    const scenario = scenarios[id] || scenarios.wildfire;
    byId('scenario-kicker').textContent = scenario.kicker;
    byId('scenario-title').textContent = scenario.title;
    byId('scenario-summary').textContent = scenario.summary;
    byId('scenario-output').textContent = scenario.output;
    byId('scenario-prohibited').textContent = scenario.prohibited;
    stageGrid.replaceChildren(...scenario.stages.map((stage, index) => {
      const article = document.createElement('article');
      article.className = 'stage-card';
      const label = document.createElement('span');
      label.textContent = `${String(index + 1).padStart(2, '0')} · ${stage[0]}`;
      const heading = document.createElement('h4');
      heading.textContent = stage[0];
      const copy = document.createElement('p');
      copy.textContent = stage[1];
      article.append(label, heading, copy);
      return article;
    }));

    tabs.forEach((tab) => {
      const active = tab.dataset.scenario === id;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active) panel.setAttribute('aria-labelledby', tab.id);
    });

    if (syncForm && byId('pilot-scenario')) {
      byId('pilot-scenario').value = id;
      persistDraft();
    }
    history.replaceState(null, '', `#run-${id}`);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => renderScenario(tab.dataset.scenario));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft'].includes(event.key)) return;
      event.preventDefault();
      const direction = ['ArrowDown', 'ArrowRight'].includes(event.key) ? 1 : -1;
      const next = (index + direction + tabs.length) % tabs.length;
      tabs[next].focus();
      renderScenario(tabs[next].dataset.scenario);
    });
  });

  const fieldIds = ['pilot-sponsor', 'pilot-operator', 'pilot-venue', 'pilot-resources', 'pilot-stop'];

  function currentDraft() {
    return {
      scenario: byId('pilot-scenario').value,
      sponsor: byId('pilot-sponsor').value.trim(),
      operator: byId('pilot-operator').value.trim(),
      venue: byId('pilot-venue').value.trim(),
      resources: byId('pilot-resources').value.trim(),
      stop: byId('pilot-stop').value.trim()
    };
  }

  function countNamedGates(draft) {
    return ['sponsor', 'operator', 'venue', 'resources', 'stop'].filter((key) => draft[key]).length;
  }

  function updateFormStatus() {
    const draft = currentDraft();
    const count = countNamedGates(draft);
    const status = byId('form-status');
    const unresolved = 5 - count;
    status.textContent = `${count} of 5 pilot decisions complete. ${unresolved ? `${unresolved} remain unresolved.` : 'All five are complete; authority and adoption still require explicit review.'}`;
  }

  function persistDraft() {
    try {
      const draft = currentDraft();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
      updateFormStatus();
    } catch (_) {
      updateFormStatus();
    }
  }

  function restoreDraft() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!stored || typeof stored !== 'object') return;
      if (stored.scenario && scenarios[stored.scenario]) byId('pilot-scenario').value = stored.scenario;
      const pairs = [
        ['pilot-sponsor', stored.sponsor],
        ['pilot-operator', stored.operator],
        ['pilot-venue', stored.venue],
        ['pilot-resources', stored.resources],
        ['pilot-stop', stored.stop]
      ];
      pairs.forEach(([id, value]) => { if (typeof value === 'string') byId(id).value = value; });
    } catch (_) {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function unresolvedValue(value) {
    return value || 'UNRESOLVED';
  }

  function buildPilotPacket() {
    const draft = currentDraft();
    const scenario = scenarios[draft.scenario];
    const named = countNamedGates(draft);
    return {
      schema: 'manzanita-works/bounded-pilot-preparation@1',
      release: RELEASE,
      generated_at: new Date().toISOString(),
      standing: named === 5 ? 'PREPARED_FOR_ACCOUNTABLE_REVIEW_NOT_ACCEPTED' : 'INCOMPLETE_PREPARATION_HELD',
      scenario: {
        id: draft.scenario,
        title: scenario.title,
        intended_output: scenario.output,
        prohibited_consequence: scenario.prohibited,
        operating_grammar: scenario.stages.map(([name, meaning], index) => ({ order: index + 1, name, meaning }))
      },
      organizational_gates: {
        accountable_sponsor: unresolvedValue(draft.sponsor),
        continuity_operator: unresolvedValue(draft.operator),
        venue_or_participant_class: unresolvedValue(draft.venue),
        resource_envelope: unresolvedValue(draft.resources),
        stop_condition: unresolvedValue(draft.stop),
        named_count: named,
        required_count: 5
      },
      invariant: {
        silence_law: 'Silence is not consent, assignment, rejection, or completion.',
        unresolved_law: 'A blank remains unresolved and may not be promoted to implied readiness.',
        adverse_action_boundary: 'Assistance and place evidence may not become insurance, enforcement, eligibility, property, resident, or other punitive standing.',
        continuity_law: 'No founder, advisor, volunteer, operator, or builder becomes the default operator.'
      },
      authority: {
        institutional_acceptance: false,
        participant_consent: false,
        field_authority: false,
        spend_authority: false,
        publication_authority: false,
        assignment_authority: false,
        representation_authority: false,
        release_authority: false,
        external_effect: 'none'
      },
      next_safe_action: named === 5
        ? 'Present this preparation packet to the accountable organization for explicit review. Any external effect requires its own authority and acceptance receipt.'
        : 'Resolve only the missing organizational gates. Do not schedule, assign, spend, contact, enroll, inspect, publish, or operate a field case from this packet.'
    };
  }

  function downloadJson(filename, value) {
    const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
  }

  byId('pilot-scenario').addEventListener('change', (event) => {
    renderScenario(event.target.value, { syncForm: false });
    persistDraft();
  });
  fieldIds.forEach((id) => byId(id).addEventListener('input', persistDraft));

  byId('export-pilot').addEventListener('click', () => {
    persistDraft();
    const packet = buildPilotPacket();
    const stamp = new Date().toISOString().slice(0, 10);
    downloadJson(`manzanita-bounded-pilot-${packet.scenario.id}-${stamp}.json`, packet);
  });

  byId('clear-pilot').addEventListener('click', () => {
    localStorage.removeItem(STORAGE_KEY);
    byId('pilot-form').reset();
    byId('pilot-scenario').value = 'wildfire';
    fieldIds.forEach((id) => { byId(id).value = ''; });
    renderScenario('wildfire', { syncForm: false });
    updateFormStatus();
  });

  function scenarioFromHash() {
    return location.hash.match(/^#run-(wildfire|tools|mobility|continuity)$/)?.[1];
  }

  restoreDraft();
  const initialScenario = scenarioFromHash() || byId('pilot-scenario').value || 'wildfire';
  renderScenario(initialScenario, { syncForm: false });
  updateFormStatus();

  window.addEventListener('hashchange', () => {
    const nextScenario = scenarioFromHash();
    if (!nextScenario) return;
    renderScenario(nextScenario);
  });

  window.MW_WORKING_MODEL = Object.freeze({
    release: RELEASE,
    scenarios: Object.keys(scenarios),
    buildPilotPacket
  });
})();
