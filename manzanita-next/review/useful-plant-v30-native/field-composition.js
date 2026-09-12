(() => {
  "use strict";

  const MODES = {
    recognize: {
      label: "Recognize",
      title: "Recognize what is already here",
      copy: "Start with the retained place and the plant already present. Confirm identity before recommending purchase, removal, or treatment.",
      look: "Leaf, branch, habit, season, and immediate surroundings.",
      stop: "Identity is uncertain enough that action would become substitution.",
      next: "place",
      nextLabel: "Place it gently",
      zone: "identity"
    },
    place: {
      label: "Place",
      title: "Choose the smallest reversible placement",
      copy: "Use the actual light, access, drainage, people, animals, and shared edges visible in the place. Prefer a trial position over a permanent intervention.",
      look: "Morning and afternoon light, drainage path, foot traffic, pets, and maintenance reach.",
      stop: "The proposal needs excavation, irreversible hardware, or authority the household did not grant.",
      next: "tend",
      nextLabel: "Set a care floor",
      zone: "placement"
    },
    tend: {
      label: "Tend",
      title: "Set the minimum viable care floor",
      copy: "Make the next care action small enough to survive a hard week. Record what the plant needs today without turning household attention into a premium service.",
      look: "Soil moisture, heat exposure, recent stress, water access, and the household effort ceiling.",
      stop: "Care exceeds the agreed effort ceiling or depends on a product substitution.",
      next: "observe",
      nextLabel: "Observe the response",
      zone: "care"
    },
    observe: {
      label: "Observe",
      title: "Keep evidence proportional to the decision",
      copy: "Notice change over time before escalating. A photograph, a dated observation, and the household account can be enough for a reversible next step.",
      look: "New growth, wilt, discoloration, browsing, pests, heat injury, and recovery after care.",
      stop: "The evidence would be reused to punish, price, deny coverage, or infer household behavior beyond the stated purpose.",
      next: "use",
      nextLabel: "Use what is ready",
      zone: "care"
    },
    use: {
      label: "Use",
      title: "Take the useful return without extracting the object",
      copy: "Harvest shade, scent, food, habitat, cooling, learning, or pleasure at the scale the living object can continue to support.",
      look: "Readiness, safe handling, household need, wildlife use, and what must remain on the plant.",
      stop: "Use becomes depletion, unsafe identification, or a claim the available evidence cannot support.",
      next: "return",
      nextLabel: "Return value to the place",
      zone: "yield"
    },
    return: {
      label: "Return",
      title: "Return material, knowledge, and choice to the place",
      copy: "Close the loop locally. Compost what is safe, share only what the household permits, record what worked, and leave the next decision reversible.",
      look: "Mulch, seed, cuttings, compost, neighbor benefit, local knowledge, and household preference.",
      stop: "Return would expose private observations, spread uncertain material, or transfer authority away from the household.",
      next: "recognize",
      nextLabel: "Recognize the next condition",
      zone: "return"
    }
  };

  const SEATS = {
    household: {
      label: "Household",
      authority: "Sets purpose, privacy, effort ceiling, substitution refusal, and final stop state."
    },
    grower: {
      label: "Grower",
      authority: "Proposes reversible placement and care, records uncertainty, and cannot override household stops."
    },
    neighbor: {
      label: "Neighbor",
      authority: "Coordinates shared edges and reciprocal benefit without acquiring household authority or private evidence."
    },
    ecologist: {
      label: "Ecologist",
      authority: "Interprets habitat function, season, and uncertainty while keeping claims proportional to observed evidence."
    },
    responder: {
      label: "Responder",
      authority: "Uses bounded condition evidence for assistance-first triage and cannot convert triage into denial, pricing, or punishment."
    }
  };

  const ZONES = {
    identity: {
      label: "Identity",
      title: "Identity zone",
      copy: "Read visible form and context before naming the living object. Keep uncertainty explicit.",
      look: "Leaf arrangement, branch form, growth habit, season, and adjacent objects.",
      stop: "A name would be more confident than the evidence."
    },
    placement: {
      label: "Placement",
      title: "Placement zone",
      copy: "Use the place itself to test light, access, drainage, conflict, and reversibility.",
      look: "Sun path, water path, walking path, shared edge, and maintenance reach.",
      stop: "Placement requires permanent work or ungranted authority."
    },
    care: {
      label: "Care",
      title: "Care zone",
      copy: "Keep care local, small, and observable. The next action should fit the household effort ceiling.",
      look: "Moisture, heat, soil condition, stress, recovery, and available attention.",
      stop: "The care plan depends on premium inputs or an unverified substitute."
    },
    yield: {
      label: "Yield",
      title: "Yield zone",
      copy: "Use only what is ready and leave the living object able to continue its household and habitat work.",
      look: "Readiness, safe identity, household need, habitat use, and regenerative margin.",
      stop: "Harvest would deplete the plant or outrun identification confidence."
    },
    return: {
      label: "Return",
      title: "Return zone",
      copy: "Return safe material and learning to the place without exporting private household evidence.",
      look: "Compost, mulch, seed, cuttings, shared benefit, and a reversible next decision.",
      stop: "Return would spread uncertainty, pests, private evidence, or unwanted obligation."
    }
  };

  const DEFAULT_STATE = {
    mode: "recognize",
    seat: "household",
    zone: "identity",
    zoneRevealed: false,
    stops: {
      pause: false,
      private: false,
      substitution: false
    }
  };

  const state = structuredClone(DEFAULT_STATE);
  const body = document.body;
  const root = document.documentElement;
  const fieldDetail = document.querySelector("#field-detail");
  const detailTitle = document.querySelector("#detail-title");
  const detailCopy = document.querySelector("#detail-copy");
  const detailLook = document.querySelector("#detail-look");
  const detailStop = document.querySelector("#detail-stop");
  const stageIndex = document.querySelector("#stage-index");
  const seatLabel = document.querySelector("#seat-label");
  const seatAuthority = document.querySelector("#seat-authority");
  const menuSummary = document.querySelector("#menu-summary");
  const nextAction = document.querySelector("#next-action");
  const fieldStatus = document.querySelector("#field-status");
  const localBoundary = document.querySelector("#local-boundary");
  const menuToggle = document.querySelector("#field-menu-toggle");
  const householdToggle = document.querySelector("#household-toggle");

  const modeKeys = Object.keys(MODES);
  const panelReturnFocus = new Map();

  function parseBoolean(value) {
    return value === "1" || value === "true";
  }

  function hydrateFromUrl() {
    const params = new URLSearchParams(location.search);
    const mode = params.get("mode");
    const seat = params.get("seat");
    const zone = params.get("zone");

    if (mode && MODES[mode]) state.mode = mode;
    if (seat && SEATS[seat]) state.seat = seat;
    if (zone && ZONES[zone]) {
      state.zone = zone;
      state.zoneRevealed = parseBoolean(params.get("zone_revealed"));
    } else {
      state.zone = MODES[state.mode].zone;
    }

    for (const stop of Object.keys(state.stops)) {
      state.stops[stop] = parseBoolean(params.get(stop));
    }
  }

  function writeUrl() {
    const params = new URLSearchParams();
    params.set("mode", state.mode);
    params.set("seat", state.seat);
    params.set("zone", state.zone);
    if (state.zoneRevealed) params.set("zone_revealed", "1");
    for (const [stop, active] of Object.entries(state.stops)) {
      if (active) params.set(stop, "1");
    }
    const nextUrl = `${location.pathname}?${params.toString()}${location.hash}`;
    history.replaceState({ ...state }, "", nextUrl);
  }

  function setPressed(selector, key, value) {
    document.querySelectorAll(selector).forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset[key] === value));
    });
  }

  function activeStopLabels() {
    const labels = [];
    if (state.stops.pause) labels.push("paused locally");
    if (state.stops.private) labels.push("private");
    if (state.stops.substitution) labels.push("substitution rejected");
    return labels;
  }

  function render() {
    const mode = MODES[state.mode];
    const seat = SEATS[state.seat];
    const zone = ZONES[state.zone];
    const modeIndex = modeKeys.indexOf(state.mode) + 1;

    body.dataset.mode = state.mode;
    body.dataset.seat = state.seat;
    body.dataset.zone = state.zone;
    body.dataset.zoneRevealed = String(state.zoneRevealed);
    for (const [stop, active] of Object.entries(state.stops)) {
      body.dataset[`stop${stop[0].toUpperCase()}${stop.slice(1)}`] = String(active);
    }

    const showingZone = state.zoneRevealed;
    detailTitle.textContent = showingZone ? zone.title : mode.title;
    detailCopy.textContent = showingZone ? zone.copy : mode.copy;
    detailLook.textContent = showingZone ? zone.look : mode.look;
    detailStop.textContent = showingZone ? zone.stop : mode.stop;
    stageIndex.textContent = `${modeIndex} of ${modeKeys.length}`;
    seatLabel.textContent = `${seat.label} seat`;
    seatAuthority.textContent = seat.authority;
    menuSummary.textContent = `${seat.label} · ${mode.label}`;
    nextAction.textContent = mode.nextLabel;

    setPressed("[data-mode]", "mode", state.mode);
    setPressed("[data-seat]", "seat", state.seat);
    setPressed("[data-zone]", "zone", state.zone);

    document.querySelectorAll("[data-zone]").forEach((button) => {
      button.dataset.revealed = String(
        state.zoneRevealed && button.dataset.zone === state.zone
      );
    });

    document.querySelectorAll("[data-stop]").forEach((button) => {
      const active = state.stops[button.dataset.stop];
      button.setAttribute("aria-pressed", String(active));
    });

    const activeStops = activeStopLabels();
    householdToggle.setAttribute(
      "aria-label",
      activeStops.length
        ? `Household controls, ${activeStops.join(", ")}`
        : "Household controls, no local stop active"
    );

    localBoundary.textContent = activeStops.length
      ? `Active local boundary: ${activeStops.join(", ")}. No state leaves this browser.`
      : "No household stop is active. This prototype performs no network write and grants no merge or release authority.";

    fieldStatus.textContent = activeStops.length
      ? `Local review · ${activeStops.join(" · ")} · operator acceptance absent`
      : "Local review · operator acceptance absent · no public effect";

    writeUrl();
  }

  function closePanels(exceptId = null) {
    document.querySelectorAll("#field-menu, #household-panel").forEach((panel) => {
      if (panel.id === exceptId || panel.hidden) return;
      panel.hidden = true;
      const trigger = panelReturnFocus.get(panel.id);
      if (panel.id === "field-menu") menuToggle.setAttribute("aria-expanded", "false");
      if (panel.id === "household-panel") householdToggle.setAttribute("aria-expanded", "false");
      panelReturnFocus.delete(panel.id);
      if (trigger && document.contains(trigger)) trigger.focus({ preventScroll: true });
    });
  }

  function openPanel(panelId, trigger) {
    closePanels(panelId);
    const panel = document.getElementById(panelId);
    if (!panel) return;
    const opening = panel.hidden;
    if (!opening) {
      closePanels();
      return;
    }
    panel.hidden = false;
    panelReturnFocus.set(panelId, trigger);
    trigger.setAttribute("aria-expanded", "true");
    const focusTarget = panel.querySelector("button, [href], [tabindex]:not([tabindex='-1'])");
    focusTarget?.focus({ preventScroll: true });
  }

  menuToggle.addEventListener("click", () => openPanel("field-menu", menuToggle));
  householdToggle.addEventListener("click", () => openPanel("household-panel", householdToggle));

  document.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => closePanels());
  });

  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.mode;
      if (!MODES[mode]) return;
      state.mode = mode;
      state.zone = MODES[mode].zone;
      state.zoneRevealed = false;
      render();
      closePanels();
      fieldDetail.focus({ preventScroll: true });
    });
  });

  document.querySelectorAll("[data-seat]").forEach((button) => {
    button.addEventListener("click", () => {
      const seat = button.dataset.seat;
      if (!SEATS[seat]) return;
      state.seat = seat;
      render();
    });
  });

  document.querySelectorAll("[data-zone]").forEach((button) => {
    button.addEventListener("click", () => {
      const zone = button.dataset.zone;
      if (!ZONES[zone]) return;
      state.zone = zone;
      state.zoneRevealed = true;
      render();
      fieldDetail.focus({ preventScroll: true });
    });
  });

  document.querySelectorAll("[data-stop]").forEach((button) => {
    button.addEventListener("click", () => {
      const stop = button.dataset.stop;
      if (!(stop in state.stops)) return;
      state.stops[stop] = !state.stops[stop];
      render();
    });
  });

  nextAction.addEventListener("click", () => {
    state.mode = MODES[state.mode].next;
    state.zone = MODES[state.mode].zone;
    state.zoneRevealed = false;
    render();
    fieldDetail.focus({ preventScroll: true });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanels();
  });

  window.addEventListener("popstate", () => {
    Object.assign(state, structuredClone(DEFAULT_STATE));
    hydrateFromUrl();
    render();
  });

  hydrateFromUrl();
  render();
  root.dataset.ready = "true";

  window.__USEFUL_PLANT_FIELD__ = Object.freeze({
    schema: "manzanita/useful-plant-v30-field-composition-state@1",
    getState: () => structuredClone(state),
    modes: Object.keys(MODES),
    seats: Object.keys(SEATS),
    zones: Object.keys(ZONES),
    operatorVisualAcceptance: "ABSENT",
    mergeAuthorized: false,
    releaseAuthorized: false,
    publicRouteEffect: "none",
    pagesDeploymentEffect: "none",
    externalEffect: "none"
  });
})();
