(() => {
  "use strict";

  const root = document.documentElement;
  const runtimeState = document.querySelector("#runtime-state");
  const sceneFrame = document.querySelector(".scene-frame");
  const modeButtons = [...document.querySelectorAll("[data-mode]")].filter((node) => node.matches("button"));
  const seatButtons = [...document.querySelectorAll(".seat-button")];
  const hotspots = [...document.querySelectorAll(".hotspot")];
  const loopItems = [...document.querySelectorAll(".use-loop li")];
  const stopButtons = [...document.querySelectorAll("[data-stop]")];

  const state = {
    mode: "recognize",
    seat: "household",
    zone: "identity",
    stops: new Set(),
  };

  const modes = {
    recognize: {
      kicker: "Recognition state",
      title: "Start with the organism, not the score.",
      copy: "The surface identifies what is present, separates observation from inference, and keeps every recommendation subordinate to household purpose.",
      condition: ["watch", "steady", "clear", "local"],
    },
    place: {
      kicker: "Placement state",
      title: "Fit the plant to the household landscape.",
      copy: "Placement joins sunlight, water, access, growth room, wildfire condition, and household use without converting the parcel into a punitive score.",
      condition: ["fit", "shade", "route", "bounded"],
    },
    tend: {
      kicker: "Care state",
      title: "Make the care burden visible before assigning it.",
      copy: "Water, pruning, pest observation, seasonal work, and expected effort remain attached to a person who can accept, defer, simplify, or stop.",
      condition: ["due", "stable", "open", "scheduled"],
    },
    observe: {
      kicker: "Observation state",
      title: "Record change without inventing certainty.",
      copy: "Household observations can strengthen the record while remaining distinct from source provenance, ecological interpretation, and bounded recommendations.",
      condition: ["logged", "measured", "clear", "retained"],
    },
    use: {
      kicker: "Use state",
      title: "Show the return that makes the work worth doing.",
      copy: "Food, medicine, shade, scent, habitat, learning, and neighborhood exchange are treated as operational returns rather than decorative side effects.",
      condition: ["ready", "safe", "shared", "useful"],
    },
    return: {
      kicker: "Return state",
      title: "Close the loop through soil, seed, habitat, and knowledge.",
      copy: "The surface keeps what returns to the household and place visible, including compost, propagation, habitat value, and reusable local knowledge.",
      condition: ["cycled", "cooler", "open", "renewed"],
    },
  };

  const zones = {
    identity: {
      title: "Plant identity",
      tier: "direct observation",
      claim: "A living plant is present in the registered image area.",
      verification: "Photograph and source path are available for inspection.",
      decision: "Confirm identity before assigning placement or care.",
      stop: "Unknown identity or household disagreement.",
    },
    placement: {
      title: "Placement boundary",
      tier: "bounded recommendation",
      claim: "This location may satisfy access, shade, water, and growth-room constraints.",
      verification: "Inspect the actual edge, path, utilities, canopy, and seasonal sun.",
      decision: "Offer a reversible placement with reasons and alternatives.",
      stop: "Blocked access, utility conflict, or household rejection.",
    },
    care: {
      title: "Care burden",
      tier: "household observation",
      claim: "Current condition may require a bounded care action.",
      verification: "Check soil, leaf condition, weather, and recent household work.",
      decision: "Assign only the smallest useful action within the effort ceiling.",
      stop: "No available steward, uncertain need, or cost above the household ceiling.",
    },
    yield: {
      title: "Useful yield",
      tier: "source-linked provenance",
      claim: "The plant may provide a household, habitat, or neighborhood return.",
      verification: "Confirm species, safe use, season, handling, and intended recipient.",
      decision: "Harvest, share, preserve, or leave in place according to purpose.",
      stop: "Unsafe identification, contamination, or no desired use.",
    },
    return: {
      title: "Ecological return",
      tier: "bounded recommendation",
      claim: "Material or knowledge may be returned to soil, habitat, or the local commons.",
      verification: "Observe whether the return actually improves continuity without spreading harm.",
      decision: "Compost, propagate, document, or share through a reversible local action.",
      stop: "Pest transmission, invasive spread, privacy conflict, or unverified benefit.",
    },
  };

  const seats = {
    household: {
      title: "Household",
      authority: "final stop authority",
      copy: "Sets purpose, privacy, effort ceiling, and the point at which the system stops asking for more.",
    },
    grower: {
      title: "Grower",
      authority: "care proposal authority",
      copy: "Proposes placement, care, harvest, and return actions while exposing burden, evidence, and reversibility.",
    },
    neighbor: {
      title: "Neighbor",
      authority: "shared-edge coordination",
      copy: "Coordinates shade, access, smoke, water, and shared habitat at the property edge without acquiring household control.",
    },
    ecologist: {
      title: "Ecologist",
      authority: "interpretation authority",
      copy: "Interprets habitat function, uncertainty, and evidence limits without converting advice into compulsory household action.",
    },
    responder: {
      title: "Responder",
      authority: "assistance-first triage",
      copy: "Uses bounded condition evidence to prioritize help and remediation while remaining firewalled from denial, ranking, and punishment.",
    },
  };

  function setPressed(group, active, matcher) {
    group.forEach((node) => {
      const selected = matcher(node) === active;
      node.classList.toggle("is-active", selected);
      node.setAttribute("aria-pressed", String(selected));
    });
  }

  function renderMode(mode) {
    if (!modes[mode]) return;
    state.mode = mode;
    const data = modes[mode];
    setPressed(modeButtons, mode, (node) => node.dataset.mode);
    sceneFrame.dataset.mode = mode;
    document.querySelector("#scene-kicker").textContent = data.kicker;
    document.querySelector("#scene-caption-title").textContent = data.title;
    document.querySelector("#scene-caption-copy").textContent = data.copy;
    document.querySelector("#loop-progress").textContent = `${Object.keys(modes).indexOf(mode) + 1} / 6`;
    loopItems.forEach((node) => node.classList.toggle("is-current", node.dataset.loop === mode));
    [...document.querySelectorAll(".condition-card strong")].forEach((node, index) => {
      node.textContent = data.condition[index];
    });
    updateRuntime();
  }

  function renderSeat(seat) {
    if (!seats[seat]) return;
    state.seat = seat;
    const data = seats[seat];
    setPressed(seatButtons, seat, (node) => node.dataset.seat);
    document.querySelector("#seat-title").textContent = data.title;
    document.querySelector("#seat-authority").textContent = data.authority;
    document.querySelector("#seat-copy").textContent = data.copy;
    updateRuntime();
  }

  function renderZone(zone) {
    if (!zones[zone]) return;
    state.zone = zone;
    const data = zones[zone];
    setPressed(hotspots, zone, (node) => node.dataset.zone);
    document.querySelector("#object-title").textContent = data.title;
    document.querySelector("#evidence-tier").textContent = data.tier;
    document.querySelector("#object-claim").textContent = data.claim;
    document.querySelector("#object-verification").textContent = data.verification;
    document.querySelector("#object-decision").textContent = data.decision;
    document.querySelector("#object-stop").textContent = data.stop;
    updateRuntime();
  }

  function renderStops() {
    const pressed = new Set();
    stopButtons.forEach((node) => {
      const active = state.stops.has(node.dataset.stop);
      node.setAttribute("aria-pressed", String(active));
      if (active) pressed.add(node.dataset.stop);
    });
    root.dataset.paused = String(pressed.has("pause"));
    root.dataset.private = String(pressed.has("private"));
    root.dataset.substitution = pressed.has("substitution") ? "rejected" : "open";
    const label = document.querySelector("#stop-state");
    if (!pressed.size) {
      label.textContent = "No stop control is active. Controls affect this local review only.";
    } else {
      const names = [...pressed].map((value) => ({
        pause: "recommendations paused",
        private: "image held private",
        substitution: "substitution rejected",
      })[value]);
      label.textContent = `${names.join(" · ")}. State remains local to this review.`;
    }
    updateRuntime();
  }

  function updateRuntime() {
    const stops = state.stops.size ? [...state.stops].sort().join(",") : "none";
    runtimeState.textContent = `mode=${state.mode} · seat=${state.seat} · zone=${state.zone} · stops=${stops}`;
    const fragment = new URLSearchParams({ mode: state.mode, seat: state.seat, zone: state.zone });
    if (state.stops.size) fragment.set("stops", [...state.stops].sort().join(","));
    history.replaceState(null, "", `#${fragment.toString()}`);
  }

  function restoreFromHash() {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    renderMode(params.get("mode") || state.mode);
    renderSeat(params.get("seat") || state.seat);
    renderZone(params.get("zone") || state.zone);
    const stops = (params.get("stops") || "").split(",").filter((value) => ["pause", "private", "substitution"].includes(value));
    state.stops = new Set(stops);
    renderStops();
  }

  async function measureDonor() {
    const output = document.querySelector("#donor-digest");
    try {
      const response = await fetch(document.querySelector("#plant-image").getAttribute("src"), { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const bytes = await response.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const hex = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
      output.textContent = `sha256:${hex} · ${bytes.byteLength} bytes`;
      output.dataset.measured = "true";
    } catch (error) {
      output.textContent = `measurement unavailable: ${error.message}`;
      output.dataset.measured = "false";
    }
  }

  modeButtons.forEach((node) => node.addEventListener("click", () => renderMode(node.dataset.mode)));
  seatButtons.forEach((node) => node.addEventListener("click", () => renderSeat(node.dataset.seat)));
  hotspots.forEach((node) => node.addEventListener("click", () => renderZone(node.dataset.zone)));
  stopButtons.forEach((node) => node.addEventListener("click", () => {
    const key = node.dataset.stop;
    state.stops.has(key) ? state.stops.delete(key) : state.stops.add(key);
    renderStops();
  }));

  const evidenceDrawer = document.querySelector("#evidence-drawer");
  const evidenceToggle = document.querySelector("#evidence-toggle");
  const evidenceClose = document.querySelector("#evidence-close");
  function setEvidence(open) {
    evidenceDrawer.hidden = !open;
    evidenceToggle.setAttribute("aria-expanded", String(open));
    if (open) evidenceDrawer.scrollIntoView({ block: "nearest" });
  }
  evidenceToggle.addEventListener("click", () => setEvidence(evidenceDrawer.hidden));
  evidenceClose.addEventListener("click", () => { setEvidence(false); evidenceToggle.focus(); });

  window.addEventListener("hashchange", restoreFromHash);
  restoreFromHash();
  measureDonor();
})();
