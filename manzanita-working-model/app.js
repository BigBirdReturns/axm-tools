(() => {
  'use strict';

  const RELEASE = 'mw-working-model-v1.1.0';
  const STORAGE_KEY = 'mw-working-model-v1.1-draft';
  const stageLabels = Object.freeze({
    signal: 'Need',
    source: 'Evidence',
    authority: 'Decision owner',
    safe_action: 'Safe next step',
    fallback: 'Backup path',
    closure: 'Outcome',
    learning: 'Next improvement'
  });

  const scenarios = {
    wildfire: {
      kicker: 'Wildfire assistance',
      title: 'A resident wants help reducing wildfire exposure without becoming a risk score.',
      summary: 'Public records and maps can focus attention. What the resident reports and verified on-site evidence determine what can be said or done.',
      output: 'A verification and assistance path tied to its evidence.',
      prohibited: 'A parcel score, eligibility decision, work order, or claim that help was delivered.',
      stages: [
        ['signal', 'A resident asks for help with a specific exposure, task, or constraint.'],
        ['source', 'Use public records and maps plus what the resident reports; show gaps, staleness, and contradictions.'],
        ['authority', 'The resident controls what they report and whether they participate. The accountable owner controls the help offered.'],
        ['safe_action', 'Prepare the smallest verification, referral, material, or work path needed.'],
        ['fallback', 'Pause the claim and request one source check, or use clearly labeled map-only context.'],
        ['closure', 'Record accepted, refused, deferred, completed, or blocked without grading the property.'],
        ['learning', 'Count recurring service gaps without identifying or ranking households.']
      ]
    },
    tools: {
      kicker: 'Tools + time',
      title: 'A neighbor needs a tool and enough human help to use it safely.',
      summary: 'The case may require equipment, skill, time, transport, instruction, space, money, or a backup path.',
      output: 'A specific match that names the resource, time, responsible person, and return conditions.',
      prohibited: 'Silent volunteer assignment, inferred inventory, implied availability, or permanent social debt.',
      stages: [
        ['signal', 'A participant states a concrete need or publishes a concrete offer.'],
        ['source', 'Check inventory, availability, training conditions, duration, transport, and space.'],
        ['authority', 'Owners control resources. People control their own time, skill, and participation.'],
        ['safe_action', 'Prepare a match that names the resource, duration, rules, handoff, and responsible person.'],
        ['fallback', 'Try another tool, date, partner, purchase, or instruction path; otherwise close it as unfilled.'],
        ['closure', 'Record the loan, return, contribution, workshop, or declined match with a receipt.'],
        ['learning', 'Repeated unmet needs show what the community should acquire, teach, stock, or partner for.']
      ]
    },
    mobility: {
      kicker: 'Mobility',
      title: 'A community member needs a practical transportation path, not another program directory.',
      summary: 'The case starts with the trip and constraint, then combines equipment, route, repair, funding, storage, and instruction.',
      output: 'A practical mobility plan with responsible people, backup options, acceptance, and unresolved constraints.',
      prohibited: 'Unverified promises of availability, route safety, funding, completed repairs, or whether the option fits the participant.',
      stages: [
        ['signal', 'A person states the trip, cost, access, repair, equipment, or confidence problem.'],
        ['source', 'Use current resource records, public route information, the participant’s own constraints, and provider terms.'],
        ['authority', 'Participants control acceptance. Owners and qualified providers control their resources and work.'],
        ['safe_action', 'Prepare the smallest viable loan, repair, training, route, funding, or combined option.'],
        ['fallback', 'Record why the first mode failed and try another mode, date, provider, or explicit hold.'],
        ['closure', 'Record accepted, refused, completed, deferred, or blocked plus any return obligation.'],
        ['learning', 'Repeated mobility gaps support fleet, repair, storage, training, route, or partnership decisions.']
      ]
    },
    continuity: {
      kicker: 'Handoff and continuity',
      title: 'A good idea should not disappear when the person carrying it gets busy, leaves, or stops replying.',
      summary: 'Interest, decisions, unknowns, permission, and next steps remain separate so enthusiasm never becomes hidden labor.',
      output: 'A portable record another person can reopen without inheriting permission nobody granted.',
      prohibited: 'Turning interest into assignment, silence into rejection, or remembered information into permission to act for the organization.',
      stages: [
        ['signal', 'A meeting, message, offer, question, source, or decision creates something worth preserving.'],
        ['source', 'Keep the literal evidence, date, participants, summary, and unresolved facts.'],
        ['authority', 'Name who may decide, who may prepare, who is affected, and every action still withheld.'],
        ['safe_action', 'Route only the next limited move: recover, ask, draft, prepare, close, or pause.'],
        ['fallback', 'A missing owner, source, budget, boundary, or permission keeps the item unresolved.'],
        ['closure', 'Record the decision, acceptance, expiration, closure, or remaining hold.'],
        ['learning', 'Repeated failures expose missing jobs that need a funded owner.']
      ]
    }
  };

  const byId = (id) => document.getElementById(id);
  const tabs = [...document.querySelectorAll('.scenario-tab')];
  const panel = byId('scenario-panel');
  const stageList = byId('stage-list');
  const textFieldIds = ['pilot-problem', 'pilot-sponsor', 'pilot-operator', 'pilot-basis', 'pilot-stop'];
  const gateKeys = ['problem', 'sponsor', 'operator', 'basis', 'stop'];

  function scenarioFromHash() {
    return location.hash.match(/^#run-(wildfire|tools|mobility|continuity)$/)?.[1];
  }

  function renderScenario(id, { syncForm = true, updateHash = true } = {}) {
    const key = scenarios[id] ? id : 'wildfire';
    const scenario = scenarios[key];
    byId('scenario-kicker').textContent = scenario.kicker;
    byId('scenario-title').textContent = scenario.title;
    byId('scenario-summary').textContent = scenario.summary;
    byId('scenario-output').textContent = scenario.output;
    byId('scenario-prohibited').textContent = scenario.prohibited;

    stageList.replaceChildren(...scenario.stages.map(([stageId, meaning], index) => {
      const item = document.createElement('li');
      const number = document.createElement('b');
      number.textContent = String(index + 1).padStart(2, '0');
      const copy = document.createElement('div');
      const heading = document.createElement('h4');
      heading.textContent = stageLabels[stageId];
      const paragraph = document.createElement('p');
      paragraph.textContent = meaning;
      copy.append(heading, paragraph);
      item.append(number, copy);
      return item;
    }));

    tabs.forEach((tab) => {
      const active = tab.dataset.scenario === key;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active) panel.setAttribute('aria-labelledby', tab.id);
    });

    if (syncForm) {
      byId('pilot-scenario').value = key;
      persistDraft();
    }
    if (updateHash) history.replaceState(null, '', `#run-${key}`);
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

  function currentDraft() {
    return {
      scenario: byId('pilot-scenario').value,
      problem: byId('pilot-problem').value.trim(),
      sponsor: byId('pilot-sponsor').value.trim(),
      operator: byId('pilot-operator').value.trim(),
      basis: byId('pilot-basis').value.trim(),
      stop: byId('pilot-stop').value.trim()
    };
  }

  function gateResolved(key, draft) {
    if (key === 'problem') return Boolean(draft.scenario && draft.problem);
    return Boolean(draft[key]);
  }

  function resolvedKeys(draft) {
    return gateKeys.filter((key) => gateResolved(key, draft));
  }

  function updateFormStatus() {
    const draft = currentDraft();
    const resolved = resolvedKeys(draft);
    const count = resolved.length;
    byId('form-status').textContent = `${count} of 5 facts named.${count === 5 ? ' Ready for accountable review, not execution.' : ` ${5 - count} remain unresolved.`}`;
    byId('packet-standing').textContent = count === 5 ? 'Prepared for review' : 'Incomplete preparation';
    byId('packet-next').textContent = count === 5 ? 'Permission to act is still required.' : 'Name only the missing facts.';

    gateKeys.forEach((key, index) => {
      const resolvedNow = resolved.includes(key);
      const row = document.querySelector(`[data-gate="${key}"]`);
      row.classList.toggle('is-resolved', resolvedNow);
      row.querySelector('em').textContent = resolvedNow ? 'Named' : 'Open';
      document.querySelectorAll('.progress-track i')[index].classList.toggle('is-resolved', resolvedNow);
    });
  }

  function persistDraft() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(currentDraft())); } catch (_) {}
    updateFormStatus();
  }

  function restoreDraft() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!stored || typeof stored !== 'object') return;
      if (typeof stored.scenario === 'string' && (stored.scenario === '' || scenarios[stored.scenario])) byId('pilot-scenario').value = stored.scenario;
      const pairs = [
        ['pilot-problem', stored.problem],
        ['pilot-sponsor', stored.sponsor],
        ['pilot-operator', stored.operator],
        ['pilot-basis', stored.basis],
        ['pilot-stop', stored.stop]
      ];
      pairs.forEach(([id, value]) => { if (typeof value === 'string') byId(id).value = value; });
    } catch (_) {
      try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
    }
  }

  function unresolved(value) {
    return value || 'UNRESOLVED';
  }

  function buildPilotPacket() {
    const draft = currentDraft();
    const named = resolvedKeys(draft).length;
    const scenario = scenarios[draft.scenario] || null;
    return {
      schema: 'manzanita-works/bounded-pilot-preparation@2',
      release: RELEASE,
      generated_at: new Date().toISOString(),
      standing: named === 5 ? 'PREPARED_FOR_ACCOUNTABLE_REVIEW_NOT_ACCEPTED' : 'INCOMPLETE_PREPARATION_HELD',
      organizational_gates: {
        problem: {
          case_type: scenario ? { id: draft.scenario, label: scenario.kicker } : 'UNRESOLVED',
          statement: unresolved(draft.problem),
          complete: Boolean(scenario && draft.problem)
        },
        accountable_sponsor: unresolved(draft.sponsor),
        continuity_operator: unresolved(draft.operator),
        execution_basis: unresolved(draft.basis),
        effect_boundary_and_stop_condition: unresolved(draft.stop),
        named_count: named,
        required_count: 5
      },
      operating_case: scenario ? {
        representative_title: scenario.title,
        intended_output: scenario.output,
        prohibited_consequence: scenario.prohibited,
        grammar: scenario.stages.map(([stageId, meaning], index) => ({
          order: index + 1,
          id: stageId,
          name: stageLabels[stageId],
          meaning
        }))
      } : 'UNRESOLVED',
      invariants: {
        authority: 'Evidence and preparation do not grant access, spend, work, publication, representation, or release authority.',
        adverse_use: 'Assistance and place evidence may not become risk, eligibility, enforcement, resident, property, or other adverse standing.',
        continuity: 'No founder, advisor, volunteer, operator, or builder becomes the permanent owner by default.'
      },
      authority: {
        institutional_acceptance: false,
        participant_consent: false,
        field_authority: false,
        spend_authority: false,
        assignment_authority: false,
        representation_authority: false,
        publication_authority: false,
        release_authority: false,
        external_effect: 'none'
      },
      next_safe_action: named === 5
        ? 'Present this packet for explicit organizational review. Every real-world action still requires explicit permission and acceptance.'
        : 'Resolve only the missing facts. Do not contact, enroll, schedule, spend, inspect, publish, assign, or operate from this packet.'
    };
  }

  function downloadJson(filename, value) {
    const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    const href = link.href;
    link.remove();
    setTimeout(() => URL.revokeObjectURL(href), 0);
  }

  byId('pilot-scenario').addEventListener('change', (event) => {
    if (scenarios[event.target.value]) renderScenario(event.target.value, { syncForm: false });
    persistDraft();
  });
  textFieldIds.forEach((id) => byId(id).addEventListener('input', persistDraft));

  byId('export-pilot').addEventListener('click', () => {
    persistDraft();
    const packet = buildPilotPacket();
    const stamp = new Date().toISOString().slice(0, 10);
    const scenario = currentDraft().scenario || 'unresolved';
    downloadJson(`manzanita-pilot-preparation-${scenario}-${stamp}.json`, packet);
  });

  byId('clear-pilot').addEventListener('click', () => {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
    byId('pilot-form').reset();
    updateFormStatus();
  });

  restoreDraft();
  const initial = scenarioFromHash() || (scenarios[byId('pilot-scenario').value] ? byId('pilot-scenario').value : 'wildfire');
  renderScenario(initial, { syncForm: false, updateHash: false });
  updateFormStatus();

  window.addEventListener('hashchange', () => {
    const next = scenarioFromHash();
    if (next) renderScenario(next);
  });

  window.MW_WORKING_MODEL = Object.freeze({
    release: RELEASE,
    scenarios: Object.keys(scenarios),
    stageLabels,
    buildPilotPacket
  });
})();
