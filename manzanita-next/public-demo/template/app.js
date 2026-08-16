(() => {
  "use strict";

  const data = window.__MANZANITA_PUBLIC_DEMO__;
  if (!data || data.schema !== "axm-tools/manzanita-public-demo-data@1") {
    throw new Error("The public-demo data contract is missing or invalid.");
  }

  const root = document.documentElement;
  const THEME_KEY = "m99-public-demo-theme";
  const THEMES = new Set(["auto", "light", "dark"]);
  const VIEWS = new Set(Object.keys(data.views || {}));
  const ACTORS = new Set(Object.keys(data.actors || {}));
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
  const sourcesById = new Map((data.sources || []).map((row) => [row.id, row]));

  const state = {
    theme: THEMES.has(data.default_theme) ? data.default_theme : "auto",
    view: VIEWS.has(data.default_view) ? data.default_view : "place",
    actor: ACTORS.has(data.default_actor) ? data.default_actor : "visitor",
  };

  const elements = {
    placeLabel: document.getElementById("place-label"),
    placeId: document.getElementById("place-id"),
    placeCoordinate: document.getElementById("place-coordinate"),
    sourceRun: document.getElementById("source-run"),
    sourceStateSummary: document.getElementById("source-state-summary"),
    baseImagery: document.getElementById("base-imagery"),
    hillshadeImagery: document.getElementById("hillshade-imagery"),
    fieldFrame: document.querySelector(".field-frame"),
    fieldTitle: document.getElementById("field-title"),
    fieldDesc: document.getElementById("field-desc"),
    fieldGround: document.getElementById("field-ground"),
    fieldRegister: document.getElementById("field-register"),
    fieldOverlay: document.getElementById("field-overlay"),
    fieldViewLabel: document.getElementById("field-view-label"),
    fieldSourceLabel: document.getElementById("field-source-label"),
    fieldAuthorityLabel: document.getElementById("field-authority-label"),
    imageStateSymbol: document.getElementById("image-state-symbol"),
    imageStateText: document.getElementById("image-state-text"),
    viewReading: document.getElementById("view-reading"),
    viewSafeAction: document.getElementById("view-safe-action"),
    sourceRailTitle: document.getElementById("source-rail-title"),
    sourceRailList: document.getElementById("source-rail-list"),
    conditionTitle: document.getElementById("condition-title"),
    metricList: document.getElementById("metric-list"),
    viewAuthority: document.getElementById("view-authority"),
    viewProhibited: document.getElementById("view-prohibited"),
    actorTitle: document.getElementById("actor-title"),
    actorEvidence: document.getElementById("actor-evidence"),
    actorAction: document.getElementById("actor-action"),
    actorAuthority: document.getElementById("actor-authority"),
    actorAcceptance: document.getElementById("actor-acceptance"),
    actorHandoff: document.getElementById("actor-handoff"),
    failureList: document.getElementById("failure-list"),
    adverseBoundary: document.getElementById("adverse-boundary"),
    buildIdentity: document.getElementById("build-identity"),
    controlQuestion: document.getElementById("control-question"),
    footerBoundary: document.getElementById("footer-boundary"),
  };

  function safeThemeRead() {
    try {
      const stored = window.localStorage.getItem(THEME_KEY);
      return THEMES.has(stored) ? stored : "auto";
    } catch (_error) {
      return "auto";
    }
  }

  function safeThemeWrite(theme) {
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch (_error) {
      // A session theme remains available when persistent storage is blocked.
    }
  }

  function resolvedTheme(theme) {
    return theme === "auto" ? (systemDark.matches ? "dark" : "light") : theme;
  }

  function updatePressed(selector, dataKey, value) {
    document.querySelectorAll(selector).forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset[dataKey] === value));
    });
  }

  function stateClass(sourceState) {
    const allowed = new Set([
      "ok",
      "empty",
      "stale",
      "skipped_missing_credential",
      "rate_limited",
      "unavailable",
      "terms_blocked",
      "unknown",
    ]);
    return `state-${allowed.has(sourceState) ? sourceState : "unknown"}`;
  }

  function stateLabel(sourceState) {
    return String(sourceState || "unknown").replaceAll("_", " ");
  }

  function makeStateSymbol(sourceState) {
    const symbol = document.createElement("span");
    symbol.className = `state-symbol ${stateClass(sourceState)}`;
    symbol.setAttribute("aria-hidden", "true");
    return symbol;
  }

  function makeSourceState(sourceState) {
    const wrapper = document.createElement("span");
    wrapper.className = "source-state";
    wrapper.append(makeStateSymbol(sourceState));
    const label = document.createElement("span");
    label.className = "source-state-label";
    label.textContent = stateLabel(sourceState);
    wrapper.append(label);
    return wrapper;
  }

  function applyTheme(theme, persist = true) {
    if (!THEMES.has(theme)) {
      return;
    }
    state.theme = theme;
    root.dataset.theme = theme;
    root.dataset.resolvedTheme = resolvedTheme(theme);
    updatePressed("[data-theme-choice]", "themeChoice", theme);
    if (persist) {
      safeThemeWrite(theme);
    }
    announce("theme");
  }

  function sourceTime(row) {
    return row.source_time || row.retrieved_at || "time unavailable";
  }

  function renderSourceRail(view) {
    elements.sourceRailTitle.textContent = `${view.title} source rail`;
    elements.sourceRailList.replaceChildren();
    const rows = view.source_ids
      .map((sourceId) => sourcesById.get(sourceId))
      .filter(Boolean);
    if (!rows.length) {
      const wrapper = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = "Coverage";
      const value = document.createElement("dd");
      value.append(makeSourceState("unknown"));
      value.append(document.createTextNode(" No registered source row entered this view."));
      wrapper.append(term, value);
      elements.sourceRailList.append(wrapper);
      return;
    }

    rows.forEach((row) => {
      const wrapper = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = row.label;
      const value = document.createElement("dd");
      value.append(makeSourceState(row.state));
      const details = document.createElement("span");
      details.className = "source-detail";
      details.textContent = `${sourceTime(row)} · ${row.claim_scope}`;
      value.append(document.createElement("br"), details);
      wrapper.append(term, value);
      elements.sourceRailList.append(wrapper);
    });
  }

  function renderMetrics(view) {
    elements.metricList.replaceChildren();
    view.metrics.forEach((metric) => {
      const row = document.createElement("article");
      row.className = "metric-row";
      const label = document.createElement("p");
      label.className = "label";
      label.textContent = metric.label;
      const value = document.createElement("p");
      value.className = "metric-value";
      value.textContent = metric.value;
      const detail = document.createElement("p");
      detail.className = "metric-detail";
      detail.textContent = metric.detail;
      row.append(label, value, detail);
      elements.metricList.append(row);
    });
  }

  function viewSourceState(view) {
    const rows = view.source_ids
      .map((sourceId) => sourcesById.get(sourceId))
      .filter(Boolean);
    if (!rows.length) {
      return "unknown";
    }
    const priority = [
      "unavailable",
      "terms_blocked",
      "rate_limited",
      "skipped_missing_credential",
      "stale",
      "empty",
      "unknown",
      "ok",
    ];
    return priority.find((candidate) => rows.some((row) => row.state === candidate)) || "unknown";
  }

  function applyView(viewId) {
    const view = data.views[viewId];
    if (!view || !VIEWS.has(viewId)) {
      return;
    }
    state.view = viewId;
    root.dataset.view = viewId;
    updatePressed("[data-view-choice]", "viewChoice", viewId);

    const sourceState = viewSourceState(view);
    elements.fieldFrame.setAttribute("aria-label", `${view.title} evidence aperture`);
    elements.fieldTitle.textContent = `${view.title} public evidence aperture`;
    elements.fieldDesc.textContent = `${view.object}. Authored Forkline registration marks remain subordinate to the public source projection.`;
    elements.fieldGround.setAttribute("d", view.geometry.ground);
    elements.fieldRegister.setAttribute("d", view.geometry.ground);
    elements.fieldOverlay.setAttribute("d", view.geometry.overlay);
    elements.fieldOverlay.setAttribute("class", `overlay-field ${viewId}`);
    elements.fieldViewLabel.textContent = view.geometry.label;
    elements.fieldSourceLabel.textContent = `source state ${stateLabel(sourceState)} · run ${data.source_run_id}`;
    elements.fieldAuthorityLabel.textContent = viewId === "fire" ? "ATTENTION · NO ADVERSE SCORE" : "READ-ONLY PUBLIC CONTEXT";
    elements.viewReading.textContent = view.reading;
    elements.viewSafeAction.textContent = view.safe_action;
    elements.conditionTitle.textContent = view.headline;
    elements.viewAuthority.textContent = view.authority;
    elements.viewProhibited.textContent = view.prohibited_consequence;

    elements.imageStateSymbol.className = `state-symbol ${stateClass(data.media.base_state)}`;
    elements.imageStateText.textContent = `${data.media.base_label} · ${stateLabel(data.media.base_state)}`;
    elements.baseImagery.alt = `${data.media.base_label}. ${data.media.claim_boundary}`;
    elements.hillshadeImagery.hidden = data.media.hillshade_state !== "ok";

    renderSourceRail(view);
    renderMetrics(view);
    announce("view");
  }

  function actorTitle(actorId) {
    if (actorId === "program_operator") {
      return "Program operator aperture";
    }
    return `${actorId.charAt(0).toUpperCase()}${actorId.slice(1)} aperture`;
  }

  function applyActor(actorId) {
    const actor = data.actors[actorId];
    if (!actor || !ACTORS.has(actorId)) {
      return;
    }
    state.actor = actorId;
    root.dataset.actor = actorId;
    updatePressed("[data-actor-choice]", "actorChoice", actorId);
    elements.actorTitle.textContent = actorTitle(actorId);
    elements.actorEvidence.textContent = actor.evidence;
    elements.actorAction.textContent = actor.safe_action;
    elements.actorAuthority.textContent = actor.authority;
    elements.actorAcceptance.textContent = actor.acceptance;
    elements.actorHandoff.textContent = actor.handoff;
    announce("actor");
  }

  function failureMechanism(row) {
    const error = row.error ? String(row.error) : "No additional provider error entered the public projection.";
    const mechanisms = {
      empty: "The provider responded successfully but returned no qualifying item or coverage.",
      stale: "The retained evidence exceeds its admitted maximum age or valid-through condition.",
      skipped_missing_credential: "The outbound request was not attempted because no approved credential was configured.",
      rate_limited: "The provider refused or delayed the request under a quota or rate limit.",
      unavailable: "The provider, network, transform, or required artifact was unavailable.",
      terms_blocked: "Rights, storage, redistribution, or provider terms prohibit inclusion in this public artifact.",
      unknown: "The retained receipt cannot support a more specific source-state classification.",
    };
    return `${mechanisms[row.state] || mechanisms.unknown} ${error}`;
  }

  function failureUnknown(row) {
    if (row.state === "empty") {
      return "Coverage, recency, visibility, or condition outside the returned result remains unknown.";
    }
    if (row.state === "skipped_missing_credential") {
      return "The provider response, coverage, item identity, capture time, and any provider-specific reading remain unknown.";
    }
    if (row.state === "stale") {
      return "Current condition after the retained source time remains unknown.";
    }
    return "Any current substantive condition that would have depended on this source remains unknown.";
  }

  function failureFallback(row) {
    if (["google_street_view", "mapillary", "kartaview", "panoramax"].includes(row.id)) {
      return "Continue in map-only mode and request an authorized source or site capture.";
    }
    if (row.id === "airnow") {
      return "Use retained National Weather Service context and route air-quality needs to an approved public source review.";
    }
    if (row.id === "firms") {
      return "Use retained official incident perimeters and alerts while preserving the absence of satellite thermal detections.";
    }
    return "Use the remaining named sources within their own claim scope and retain this failure receipt.";
  }

  function renderFailures() {
    elements.failureList.replaceChildren();
    const failures = data.failures || [];
    if (!failures.length) {
      const row = document.createElement("article");
      row.className = "failure-row";
      const header = document.createElement("header");
      header.append(makeStateSymbol("ok"));
      const title = document.createElement("h3");
      title.textContent = "No degraded source entered this acquisition bundle";
      header.append(title);
      const text = document.createElement("p");
      text.textContent = "This does not prove permanent provider availability. The next acquisition must rebuild the failure ledger.";
      row.append(header, text);
      elements.failureList.append(row);
      return;
    }

    failures.forEach((source) => {
      const row = document.createElement("article");
      row.className = "failure-row";
      row.dataset.sourceId = source.id;
      row.dataset.sourceState = source.state;
      const header = document.createElement("header");
      header.append(makeStateSymbol(source.state));
      const title = document.createElement("h3");
      title.textContent = `${source.label} · ${stateLabel(source.state)}`;
      header.append(title);

      const ledger = document.createElement("dl");
      const entries = [
        ["What failed", failureMechanism(source)],
        ["What remains known", source.claim_scope],
        ["What is unknown", failureUnknown(source)],
        ["Safe fallback", failureFallback(source)],
        ["Rights and storage", `${source.rights} · ${source.storage_policy}`],
        ["Accountable next action", "Source custody or the program operator reviews the receipt before any stronger claim or external effect."],
      ];
      entries.forEach(([labelText, valueText]) => {
        const wrapper = document.createElement("div");
        const term = document.createElement("dt");
        term.textContent = labelText;
        const value = document.createElement("dd");
        value.textContent = valueText;
        wrapper.append(term, value);
        ledger.append(wrapper);
      });
      row.append(header, ledger);
      elements.failureList.append(row);
    });
  }

  function formatSourceCounts() {
    return Object.entries(data.source_state_counts || {})
      .sort(([first], [second]) => first.localeCompare(second))
      .map(([sourceState, count]) => `${count} ${stateLabel(sourceState)}`)
      .join(" · ");
  }

  function bindChoiceButtons(selector, dataKey, handler) {
    document.querySelectorAll(selector).forEach((button) => {
      button.addEventListener("click", () => handler(button.dataset[dataKey]));
    });
  }

  function bindArrowNavigation() {
    document.querySelectorAll('[role="group"]').forEach((group) => {
      const buttons = Array.from(group.querySelectorAll("button:not([disabled])"));
      group.addEventListener("keydown", (event) => {
        if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"].includes(event.key)) {
          return;
        }
        const activeIndex = buttons.indexOf(document.activeElement);
        if (activeIndex < 0) {
          return;
        }
        event.preventDefault();
        let nextIndex = activeIndex;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          nextIndex = (activeIndex + 1) % buttons.length;
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          nextIndex = (activeIndex - 1 + buttons.length) % buttons.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = buttons.length - 1;
        }
        buttons[nextIndex].focus();
        buttons[nextIndex].click();
      });
    });
  }

  function announce(reason) {
    window.dispatchEvent(
      new CustomEvent("manzanita:public-demo-statechange", {
        detail: Object.freeze({
          reason,
          theme: state.theme,
          resolvedTheme: root.dataset.resolvedTheme,
          view: state.view,
          actor: state.actor,
          sourceRunId: data.source_run_id,
          buildId: data.build_id,
        }),
      }),
    );
  }

  function initializeStaticContent() {
    elements.placeLabel.textContent = data.place.label;
    elements.placeId.textContent = data.place.id;
    elements.placeCoordinate.textContent = `${data.place.latitude.toFixed(data.place.coordinate_precision_decimals)}, ${data.place.longitude.toFixed(data.place.coordinate_precision_decimals)} · public precision`;
    elements.sourceRun.textContent = data.source_run_id;
    elements.sourceStateSummary.textContent = formatSourceCounts();
    elements.adverseBoundary.textContent = data.adverse_action_boundary.prohibited_uses.join(" ");
    elements.buildIdentity.textContent = `${data.build_id} · manifest ${data.source_manifest_sha256}`;
    elements.controlQuestion.textContent = data.control_question;
    elements.footerBoundary.textContent = data.claim_boundary;
    document.title = `${data.place.label} · Manzanita Public-Safe Demonstration`;
    renderFailures();
  }

  bindChoiceButtons("[data-theme-choice]", "themeChoice", applyTheme);
  bindChoiceButtons("[data-view-choice]", "viewChoice", applyView);
  bindChoiceButtons("[data-actor-choice]", "actorChoice", applyActor);
  bindArrowNavigation();

  const systemThemeListener = () => {
    if (state.theme === "auto") {
      applyTheme("auto", false);
    }
  };
  if (typeof systemDark.addEventListener === "function") {
    systemDark.addEventListener("change", systemThemeListener);
  } else if (typeof systemDark.addListener === "function") {
    systemDark.addListener(systemThemeListener);
  }

  state.theme = safeThemeRead();
  initializeStaticContent();
  applyTheme(state.theme, false);
  applyView(state.view);
  applyActor(state.actor);

  window.__MANZANITA_PUBLIC_DEMO_RUNTIME__ = Object.freeze({
    version: data.contract_version,
    sourceRunId: data.source_run_id,
    buildId: data.build_id,
    getState: () => ({ ...state, resolvedTheme: root.dataset.resolvedTheme }),
    views: Array.from(VIEWS),
    actors: Array.from(ACTORS),
    themes: Array.from(THEMES),
    sourceStateCounts: { ...data.source_state_counts },
  });
})();
