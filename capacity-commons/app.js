"use strict";

const SEED = JSON.parse(document.getElementById("seed-data").textContent);
const COMPONENT_REGISTER = JSON.parse(document.getElementById("component-data").textContent);
const STORAGE_KEY = "mw-essential-capacity-v0.1.0-state";
const VIEWS = ["today", "commons", "exchange", "components", "handoff"];
const clone = (value) => JSON.parse(JSON.stringify(value));
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
})[character]);

function defaultState() {
  return {
    schema: "manzanita-works/capacity-runtime-state@0.1",
    release_id: SEED.release.id,
    activeSeat: "steward",
    activeView: "today",
    chainStage: 0,
    intents: clone(SEED.intents),
    commitments: clone(SEED.commitments),
    ledger: clone(SEED.events),
    balances: Object.fromEntries(SEED.credits.accounts.map((account) => [account.agent, account.balance])),
    localAgents: [],
    localCounter: 0,
    lastImportedAt: null,
    lastExportDigest: null
  };
}

function loadState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (parsed && parsed.release_id === SEED.release.id && Array.isArray(parsed.ledger) && Array.isArray(parsed.intents)) {
      return Object.assign(defaultState(), parsed);
    }
  } catch (error) {
    console.warn("Local state could not be restored", error);
  }
  return defaultState();
}

let state = loadState();

const seatActor = {
  member: "agent-contributor-01",
  contributor: "agent-contributor-01",
  pilot: "agent-pilot-01",
  steward: "agent-steward-01",
  successor: "agent-manzanita-works"
};

const steps = [
  {
    id: "commitment",
    label: "Create the workshop commitment",
    short: "Match the open facilitation offer to the workshop need.",
    seats: ["contributor"],
    authority: "Contributor accepts the bounded commitment.",
    boundary: "No service has yet been performed.",
    run() {
      state.commitments.push({
        id: "commitment-workshop-001",
        provider: "agent-contributor-01",
        receiver: "agent-manzanita-works",
        project: "project-ebike-workshop",
        satisfies: ["intent-workshop-need", "intent-workshop-offer"],
        resource: "resource-workshop-facilitation",
        quantity: 120,
        unit: "minute",
        state: "accepted"
      });
      setIntentState(["intent-workshop-need", "intent-workshop-offer"], "committed");
      recordEvent("commitment_accepted", {
        actor: "agent-contributor-01",
        project: "project-ebike-workshop",
        authority: "contributor commitment",
        evidence: "commitment-workshop-001",
        note: "Contributor 01 accepted a bounded two-hour workshop commitment. Performance remains unproved."
      });
    }
  },
  {
    id: "tool-reference",
    label: "Record the MyTurn tool hold reference",
    short: "Attach a physical-custody reference without claiming checkout.",
    seats: ["steward"],
    authority: "Steward records an external-system reference.",
    boundary: "The local packet does not check out or reserve the tool.",
    run() {
      setIntentState(["intent-tool-need", "intent-tool-offer"], "externally-referenced");
      recordEvent("external_reference_recorded", {
        actor: "agent-steward-01",
        project: "project-ebike-workshop",
        authority: "steward adapter reconciliation",
        evidence: "evidence-myturn-boundary",
        external_system: "myturn",
        external_reference: "public-safe-placeholder",
        note: "A MyTurn reference was attached for the torque wrench. The event does not claim that MyTurn completed a reservation or checkout."
      });
    }
  },
  {
    id: "performance",
    label: "Record the workshop as performed",
    short: "The contributor records what was actually provided.",
    seats: ["contributor"],
    authority: "Contributor attests performance subject to steward review.",
    boundary: "Self-attestation does not issue credit.",
    run() {
      recordEvent("service_performed", {
        actor: "agent-contributor-01",
        project: "project-ebike-workshop",
        authority: "contributor performance attestation",
        evidence: "commitment-workshop-001",
        quantity: 120,
        unit: "minute",
        note: "Contributor 01 recorded 120 minutes of workshop facilitation. Acceptance is still withheld."
      });
    }
  },
  {
    id: "acceptance",
    label: "Accept the performed contribution",
    short: "A steward separates evidence review from self-attestation.",
    seats: ["steward"],
    authority: "Steward accepts the eligible contribution.",
    boundary: "Acceptance establishes standing; credit issuance is a separate event.",
    run() {
      recordEvent("performance_accepted", {
        actor: "agent-steward-01",
        project: "project-ebike-workshop",
        authority: "steward contribution acceptance",
        evidence: "commitment-workshop-001",
        quantity: 120,
        unit: "minute",
        note: "The steward accepted 120 eligible minutes. No Essential Minutes have yet been issued."
      });
    }
  },
  {
    id: "issue",
    label: "Issue 120 Essential Minutes",
    short: "Mint participation credit only after accepted performance.",
    seats: ["steward"],
    authority: "Steward issues credit under the pilot policy.",
    boundary: "The credit is noncash participation accounting.",
    run() {
      state.balances["agent-contributor-01"] = Number(state.balances["agent-contributor-01"] || 0) + 120;
      recordEvent("credit_issued", {
        actor: "agent-steward-01",
        beneficiary: "agent-contributor-01",
        project: "project-essential-time-pilot",
        authority: "steward credit issuance",
        evidence: latestEventId("performance_accepted"),
        quantity: 120,
        unit: "essential-minute",
        note: "120 Essential Minutes were issued to Contributor 01 against the accepted workshop event."
      });
    }
  },
  {
    id: "redeem",
    label: "Redeem 60 minutes for pilotage",
    short: "Use collective credit with a different provider.",
    seats: ["member"],
    authority: "Member requests redemption against available balance.",
    boundary: "Pilotage remains bounded navigation, not professional substitution.",
    run() {
      const balance = Number(state.balances["agent-contributor-01"] || 0);
      if (balance < 60) throw new Error("Insufficient Essential Minutes for redemption.");
      state.balances["agent-contributor-01"] = balance - 60;
      recordEvent("credit_redeemed", {
        actor: "agent-contributor-01",
        provider: "agent-pilot-01",
        project: "project-essential-time-pilot",
        authority: "member redemption under pilot policy",
        evidence: latestEventId("credit_issued"),
        quantity: 60,
        unit: "essential-minute",
        note: "Contributor 01 redeemed 60 Essential Minutes for bounded navigation from Pilot 01. The provider is not the recipient of the earlier workshop contribution."
      });
    }
  },
  {
    id: "close",
    label: "Close and carry the rehearsal",
    short: "A successor verifies the chain and exports the packet.",
    seats: ["successor"],
    authority: "Successor records local closure after qualification.",
    boundary: "Closure proves the local chain only.",
    run() {
      const qualification = runQualification();
      if (!qualification.every((check) => check.pass)) throw new Error("Contained checks must pass before closure.");
      recordEvent("rehearsal_closed", {
        actor: "agent-manzanita-works",
        project: "project-essential-time-pilot",
        authority: "successor continuity review",
        evidence: "contained-qualification",
        note: "The public-safe N=1 chain passed contained qualification and was closed locally. No external organization was bound."
      });
    }
  }
];

function latestEventId(type) {
  return [...state.ledger].reverse().find((event) => event.event_type === type)?.id || null;
}

function setIntentState(ids, nextState) {
  state.intents.forEach((intent) => {
    if (ids.includes(intent.id)) intent.state = nextState;
  });
}

function recordEvent(eventType, fields) {
  state.localCounter += 1;
  const now = new Date().toISOString();
  const suffix = `${Date.now()}-${String(state.localCounter).padStart(3, "0")}`;
  const event = {
    id: `event-local-${suffix}`,
    event_type: eventType,
    timestamp: now,
    state: "recorded",
    receipt_id: `receipt-local-${suffix}`,
    previous_receipt: state.ledger.at(-1)?.receipt_id || null,
    ...fields
  };
  state.ledger.push(event);
  return event;
}

function persist(message) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  updateUrl();
  renderAll();
  if (message) announce(message);
}

function announce(message) {
  const node = document.getElementById("announcement");
  node.textContent = message;
  clearTimeout(announce.timer);
  announce.timer = setTimeout(() => { node.textContent = ""; }, 5000);
}

function activeSeatRecord() {
  return SEED.seats.find((seat) => seat.id === state.activeSeat) || SEED.seats[0];
}

function currentStep() {
  return state.chainStage < steps.length ? steps[state.chainStage] : null;
}

function stageStatus(index) {
  if (index < state.chainStage) return "done";
  if (index === state.chainStage && state.chainStage < steps.length) return "current";
  return "pending";
}

function metrics() {
  const offers = state.intents.filter((intent) => intent.kind === "offer" && !["fulfilled", "expired"].includes(intent.state)).length;
  const needs = state.intents.filter((intent) => intent.kind === "need" && !["fulfilled", "expired"].includes(intent.state)).length;
  const accepted = state.ledger.filter((event) => event.event_type === "performance_accepted").length;
  const issued = state.ledger.filter((event) => event.event_type === "credit_issued").reduce((sum, event) => sum + Number(event.quantity || 0), 0);
  const redeemed = state.ledger.filter((event) => event.event_type === "credit_redeemed").reduce((sum, event) => sum + Number(event.quantity || 0), 0);
  const externalRefs = state.ledger.filter((event) => event.event_type === "external_reference_recorded").length;
  return { offers, needs, accepted, issued, redeemed, externalRefs };
}

function renderSeatSelector() {
  const select = document.getElementById("seat-select");
  select.innerHTML = SEED.seats.map((seat) =>
    `<option value="${escapeHtml(seat.id)}"${seat.id === state.activeSeat ? " selected" : ""}>${escapeHtml(seat.label)}</option>`
  ).join("");
}

function metricMarkup() {
  const value = metrics();
  const entries = [
    ["Offers", value.offers, "available or conditional"],
    ["Needs", value.needs, "open or committed"],
    ["Commitments", state.commitments.length, "agreed future events"],
    ["Accepted", value.accepted, "performed contributions"],
    ["Issued", value.issued, "Essential Minutes"],
    ["Redeemed", value.redeemed, `${value.externalRefs} external tool reference${value.externalRefs === 1 ? "" : "s"}`]
  ];
  return entries.map(([label, number, note]) =>
    `<div class="metric"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(number)}</dd><small>${escapeHtml(note)}</small></div>`
  ).join("");
}

function renderStageList(targetId) {
  const target = document.getElementById(targetId);
  target.innerHTML = steps.map((step, index) => {
    const status = stageStatus(index);
    return `<li class="${status}">
      <span class="stage-number">${status === "done" ? "✓" : index + 1}</span>
      <span class="stage-copy"><strong>${escapeHtml(step.label)}</strong><span>${escapeHtml(step.short)} · ${escapeHtml(step.seats.map((id) => SEED.seats.find((seat) => seat.id === id)?.label || id).join(" / "))}</span></span>
    </li>`;
  }).join("");
}

function nextActionMarkup() {
  const step = currentStep();
  const seat = activeSeatRecord();
  if (!step) {
    return `<h3>Local chain complete</h3>
      <p>The N=1 rehearsal now separates promise, reference, performance, acceptance, issuance, redemption, and closure.</p>
      <p class="boundary">Next safe move: open Handoff, inspect the contained checks, and export the portable packet. No external execution is implied.</p>
      <button class="secondary-action" type="button" data-go-view="handoff">Open handoff</button>`;
  }
  const authorized = step.seats.includes(state.activeSeat);
  const required = step.seats.map((id) => SEED.seats.find((seat) => seat.id === id)?.label || id).join(" or ");
  return `<h3>${escapeHtml(step.label)}</h3>
    <p>${escapeHtml(step.short)}</p>
    <p><strong>Selected seat:</strong> ${escapeHtml(seat.label)}. <strong>Required seat:</strong> ${escapeHtml(required)}.</p>
    <p class="boundary"><strong>Authority:</strong> ${escapeHtml(step.authority)}<br><strong>Held effect:</strong> ${escapeHtml(step.boundary)}</p>
    <button class="primary-action" type="button" id="run-step-button"${authorized ? "" : " disabled"}>${authorized ? "Record this transition" : `Switch to ${escapeHtml(required)}`}</button>`;
}

function renderToday() {
  document.getElementById("today-metrics").innerHTML = metricMarkup();
  const step = currentStep();
  document.getElementById("next-seat-label").textContent = step ? `stage ${state.chainStage + 1} of ${steps.length}` : "closed locally";
  document.getElementById("next-action").innerHTML = nextActionMarkup();
  renderStageList("today-stage-list");
}

function renderCommons() {
  const intentsByClass = Object.fromEntries(SEED.capacity_classes.map((item) => [item.id, 0]));
  state.intents.forEach((intent) => { intentsByClass[intent.capacity_class] = (intentsByClass[intent.capacity_class] || 0) + 1; });
  document.getElementById("capacity-grid").innerHTML = SEED.capacity_classes.map((item) => `
    <article class="capacity-cell">
      <h3>${escapeHtml(item.label)}</h3>
      <p>${escapeHtml(item.accounting)}</p>
      <span class="count">${escapeHtml(intentsByClass[item.id] || 0)}</span>
      <p>recorded offer${intentsByClass[item.id] === 1 ? " or need" : "s or needs"}</p>
    </article>`).join("");

  document.getElementById("intent-count").textContent = `${state.intents.length} records`;
  document.getElementById("intent-list").innerHTML = state.intents.map((intent) => `
    <article class="intent">
      <div class="meta"><span class="badge ${escapeHtml(intent.kind)}">${escapeHtml(intent.kind)}</span><span>${escapeHtml(intent.capacity_class)}</span><span>${escapeHtml(intent.quantity)} ${escapeHtml(intent.unit)}</span><span>${escapeHtml(intent.state)}</span></div>
      <h4>${escapeHtml(intent.description)}</h4>
      <p>${escapeHtml(projectLabel(intent.project))} · ${escapeHtml(intent.visibility || "local")}</p>
    </article>`).join("");

  document.getElementById("intent-capacity").innerHTML = SEED.capacity_classes.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  document.getElementById("intent-project").innerHTML = SEED.projects.map((project) =>
    `<option value="${escapeHtml(project.id)}">${escapeHtml(project.label)}</option>`
  ).join("");
}

function projectLabel(id) {
  return SEED.projects.find((project) => project.id === id)?.label || id || "No project";
}

function renderExchange() {
  renderStageList("exchange-stage-list");
  document.getElementById("exchange-stage-label").textContent = state.chainStage < steps.length ? `${state.chainStage} completed` : "all completed";
  document.getElementById("exchange-seat-label").textContent = activeSeatRecord().label;
  document.getElementById("exchange-action").innerHTML = nextActionMarkup();
  document.getElementById("credit-balance").textContent = Number(state.balances["agent-contributor-01"] || 0).toLocaleString();
  document.getElementById("ledger-count").textContent = `${state.ledger.length} receipts`;
  document.getElementById("ledger-list").innerHTML = [...state.ledger].reverse().map((event) => `
    <li>
      <div class="ledger-meta"><span>${escapeHtml(new Date(event.timestamp).toLocaleString())}</span><span>${escapeHtml(event.event_type)}</span><span>${escapeHtml(event.receipt_id)}</span></div>
      <strong>${escapeHtml(event.note || event.event_type)}</strong>
      <p>Actor: ${escapeHtml(agentLabel(event.actor))} · Authority: ${escapeHtml(event.authority || "unspecified")}${event.external_system ? ` · External system: ${escapeHtml(event.external_system)}` : ""}</p>
    </li>`).join("");
}

function agentLabel(id) {
  return [...SEED.agents, ...state.localAgents].find((agent) => agent.id === id)?.label || id || "Unspecified";
}

function renderComponents() {
  document.getElementById("component-list").innerHTML = COMPONENT_REGISTER.components.map((component) => `
    <article class="component">
      <div class="component-meta"><span class="badge ${escapeHtml(component.decision)}">${escapeHtml(component.decision)}</span><span>${escapeHtml(component.layer)}</span><span>${escapeHtml(component.kind)}</span></div>
      <h3>${escapeHtml(component.name)}</h3>
      <p>${escapeHtml(component.current_use)}</p>
      <p><strong>Admission:</strong> ${escapeHtml(component.admission_note)}</p>
      <details>
        <summary>Custody and evidence</summary>
        <p><strong>Canonical for:</strong> ${escapeHtml(component.canonical_for.join(", ") || "nothing in this release")}</p>
        <p><strong>Never canonical for:</strong> ${escapeHtml(component.never_canonical_for.join(", ") || "not specified")}</p>
        <p><strong>Replacement test:</strong> ${escapeHtml(component.replacement_test)}</p>
        <ul>${component.evidence.map((item) => {
          const safe = /^https:\/\//.test(item);
          return `<li>${safe ? `<a href="${escapeHtml(item)}" target="_blank" rel="noreferrer">${escapeHtml(item)}</a>` : escapeHtml(item)}</li>`;
        }).join("")}</ul>
      </details>
    </article>`).join("");
}

function runQualification() {
  const ids = [];
  [SEED.agents, SEED.projects, SEED.resources, SEED.evidence, SEED.policies, state.intents, state.commitments, state.ledger].forEach((group) => {
    (group || []).forEach((item) => ids.push(item.id));
  });

  const duplicateIds = ids.filter((id, index) => id && ids.indexOf(id) !== index);
  const acceptedIndex = state.ledger.findIndex((event) => event.event_type === "performance_accepted");
  const issueIndex = state.ledger.findIndex((event) => event.event_type === "credit_issued");
  const issued = state.ledger.filter((event) => event.event_type === "credit_issued").reduce((sum, event) => sum + Number(event.quantity || 0), 0);
  const redeemed = state.ledger.filter((event) => event.event_type === "credit_redeemed").reduce((sum, event) => sum + Number(event.quantity || 0), 0);
  const externalToolEvents = state.ledger.filter((event) => event.event_type === "external_reference_recorded");
  const receiptsComplete = state.ledger.every((event) => event.id && event.timestamp && event.actor && event.authority && event.receipt_id);
  const componentComplete = COMPONENT_REGISTER.components.every((component) => component.decision && component.replacement_test && Array.isArray(component.evidence));
  const sensitivePolicy = SEED.policies.some((policy) => policy.id === "policy-sensitive-services");
  const allSynthetic = SEED.agents.filter((agent) => agent.type === "synthetic_person").every((agent) => agent.public_safe === true);

  return [
    { label: "Schema and release identity match", pass: state.release_id === SEED.release.id && state.schema === "manzanita-works/capacity-runtime-state@0.1" },
    { label: "No duplicate operational identifiers", pass: duplicateIds.length === 0 },
    { label: "Every ledger event carries timestamp, actor, authority, and receipt", pass: receiptsComplete },
    { label: "Credit issuance follows accepted performance", pass: issueIndex === -1 || (acceptedIndex !== -1 && acceptedIndex < issueIndex) },
    { label: "Redemption does not exceed issued participation credit", pass: redeemed <= issued && Number(state.balances["agent-contributor-01"] || 0) >= 0 },
    { label: "Physical-tool entries remain external MyTurn references, not fabricated checkouts", pass: externalToolEvents.every((event) => event.external_system === "myturn" && !/checkout|return_completed/.test(event.event_type)) },
    { label: "Every component has a disposition, evidence trail, and replacement test", pass: componentComplete },
    { label: "Public seed contains synthetic people and a sensitive-service custody rule", pass: allSynthetic && sensitivePolicy }
  ];
}

function renderHandoff() {
  const checks = runQualification();
  const passed = checks.filter((check) => check.pass).length;
  document.getElementById("qualification-summary").textContent = `${passed}/${checks.length} pass`;
  document.getElementById("qualification-list").innerHTML = checks.map((check) => `
    <li><span class="check-state ${check.pass ? "pass" : "fail"}">${check.pass ? "Pass" : "Fail"}</span><span>${escapeHtml(check.label)}</span></li>
  `).join("");
  document.getElementById("packet-receipt").textContent = state.lastExportDigest
    ? `Last exported packet digest: ${state.lastExportDigest}`
    : state.lastImportedAt
      ? `Packet imported locally at ${new Date(state.lastImportedAt).toLocaleString()}.`
      : "No packet exported in this browser session.";
}

function renderAll() {
  renderSeatSelector();
  document.querySelectorAll("[data-view]").forEach((section) => {
    if (!section.classList.contains("view")) return;
    section.hidden = section.dataset.view !== state.activeView;
  });
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.setAttribute("aria-selected", String(button.dataset.viewTarget === state.activeView));
  });
  renderToday();
  renderCommons();
  renderExchange();
  renderComponents();
  renderHandoff();
  bindDynamicActions();
}

function bindDynamicActions() {
  document.querySelectorAll("#run-step-button").forEach((button) => {
    button.addEventListener("click", runCurrentStep);
  });
  document.querySelectorAll("[data-go-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.goView));
  });
}

function runCurrentStep() {
  const step = currentStep();
  if (!step) return;
  if (!step.seats.includes(state.activeSeat)) {
    announce(`Switch to ${step.seats.map((id) => SEED.seats.find((seat) => seat.id === id)?.label || id).join(" or ")}.`);
    return;
  }
  try {
    step.run();
    state.chainStage += 1;
    persist(`${step.label} was recorded locally. No outside act was released.`);
  } catch (error) {
    announce(error.message || "The transition could not be recorded.");
  }
}

function setView(view) {
  if (!VIEWS.includes(view)) return;
  state.activeView = view;
  persist();
  document.getElementById(`view-${view}`).scrollIntoView({ block: "start" });
}

function updateUrl() {
  const url = new URL(location.href);
  url.searchParams.set("view", state.activeView);
  url.searchParams.set("seat", state.activeSeat);
  history.replaceState(null, "", url);
}

function applyUrlState() {
  const params = new URLSearchParams(location.search);
  const view = params.get("view");
  const seat = params.get("seat");
  if (VIEWS.includes(view)) state.activeView = view;
  if (SEED.seats.some((item) => item.id === seat)) state.activeSeat = seat;
}

async function sha256(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function exportPacket() {
  const checks = runQualification();
  const packetWithoutDigest = {
    schema: "manzanita-works/capacity-portable-packet@0.1",
    release_id: SEED.release.id,
    exported_at: new Date().toISOString(),
    authority_boundary: SEED.authority_boundary,
    state: clone(state),
    core_snapshot: SEED,
    component_register: COMPONENT_REGISTER,
    qualification: checks,
    digest_algorithm: "sha-256"
  };
  const canonical = JSON.stringify(packetWithoutDigest, null, 2);
  const digest = await sha256(canonical);
  const packet = { ...packetWithoutDigest, digest };
  const blob = new Blob([JSON.stringify(packet, null, 2) + "\n"], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `manzanita-essential-capacity-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  state.lastExportDigest = digest;
  persist(`Portable packet exported with SHA-256 ${digest.slice(0, 12)}…`);
}

function validateImportedPacket(packet) {
  if (!packet || packet.schema !== "manzanita-works/capacity-portable-packet@0.1") throw new Error("Unsupported packet schema.");
  if (packet.release_id !== SEED.release.id) throw new Error("Packet release does not match this runtime.");
  if (!packet.state || !Array.isArray(packet.state.ledger) || !Array.isArray(packet.state.intents)) throw new Error("Packet state is incomplete.");
  if (packet.state.chainStage < 0 || packet.state.chainStage > steps.length) throw new Error("Packet chain stage is outside the admitted range.");
}

async function importPacket(file) {
  const text = await file.text();
  const packet = JSON.parse(text);
  validateImportedPacket(packet);
  if (packet.digest) {
    const { digest, ...withoutDigest } = packet;
    const computed = await sha256(JSON.stringify(withoutDigest, null, 2));
    if (computed !== digest) throw new Error("Packet digest does not match its contents.");
  }
  state = Object.assign(defaultState(), clone(packet.state));
  state.lastImportedAt = new Date().toISOString();
  state.lastExportDigest = packet.digest || null;
  persist("Portable packet imported locally. No outside system was contacted.");
}

function saveLocalIntent(form) {
  const data = new FormData(form);
  state.localCounter += 1;
  const actorId = `agent-local-${Date.now()}-${state.localCounter}`;
  const intentId = `intent-local-${Date.now()}-${state.localCounter}`;
  const actor = {
    id: actorId,
    type: "local_alias",
    label: String(data.get("actor")).trim(),
    standing: "local draft actor",
    public_safe: false
  };
  state.localAgents.push(actor);
  state.intents.push({
    id: intentId,
    kind: data.get("kind"),
    project: data.get("project"),
    capacity_class: data.get("capacity_class"),
    resource: null,
    quantity: Number(data.get("quantity")),
    unit: String(data.get("unit")).trim(),
    provider: data.get("kind") === "offer" ? actorId : null,
    receiver: data.get("kind") === "need" ? actorId : null,
    description: String(data.get("description")).trim(),
    state: "local-draft",
    visibility: "private-local"
  });
  recordEvent("intent_drafted", {
    actor: actorId,
    project: data.get("project"),
    authority: `${state.activeSeat} local drafting`,
    evidence: intentId,
    note: `${actor.label} drafted a local ${data.get("kind")} for ${data.get("quantity")} ${data.get("unit")}. No publication or matching occurred.`
  });
  persist("Local intent saved. It remains private to this browser and portable packet.");
}

document.querySelectorAll("[data-view-target]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});

document.getElementById("seat-select").addEventListener("change", (event) => {
  state.activeSeat = event.target.value;
  persist(`Functional seat changed to ${activeSeatRecord().label}.`);
});

document.getElementById("theme-button").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("mw-capacity-theme", next);
  announce(`${next[0].toUpperCase() + next.slice(1)} theme applied.`);
});

document.getElementById("print-button").addEventListener("click", () => window.print());
document.getElementById("export-button").addEventListener("click", () => exportPacket().catch((error) => announce(error.message)));
document.getElementById("import-file").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  importPacket(file).catch((error) => announce(error.message || "Import failed."));
  event.target.value = "";
});
document.getElementById("reset-button").addEventListener("click", () => {
  if (!confirm("Reset the local rehearsal, draft intents, receipts, and onboarding state for this release?")) return;
  localStorage.removeItem(STORAGE_KEY);
  state = defaultState();
  applyUrlState();
  persist("Local rehearsal reset to the committed public-safe seed.");
});
document.getElementById("intent-form").addEventListener("submit", (event) => {
  event.preventDefault();
  saveLocalIntent(event.currentTarget);
});

applyUrlState();
renderAll();
updateUrl();
