(() => {
  "use strict";

  const data = window.__MANZANITA_WHOLE_EXPERIENCE__;
  if (!data || data.schema !== "axm-tools/manzanita-whole-experience-data@1") {
    throw new Error("The governed whole-experience data object is unavailable or invalid.");
  }

  const byId = (rows) => new Map(rows.map((row) => [row.id, row]));
  const apertureById = byId(data.apertures);
  const overlayById = byId(data.overlays);
  const roleById = byId(data.roles);
  const sourceById = byId(data.source_summary.sources);
  const state = {
    aperture: apertureById.has(data.defaults.aperture) ? data.defaults.aperture : data.aperture_order[0],
    overlay: overlayById.has(data.defaults.overlay) ? data.defaults.overlay : data.overlay_order[0],
    role: roleById.has(data.defaults.role) ? data.defaults.role : data.role_order[0],
    theme: ["auto", "light", "dark"].includes(localStorage.getItem("manzanita-theme"))
      ? localStorage.getItem("manzanita-theme")
      : data.defaults.theme,
    section: "overview",
    sourceFilter: "all",
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value ?? ""; };
  const html = (selector, value) => { const node = $(selector); if (node) node.innerHTML = value; };
  const escapeHTML = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const labelFor = (value) => String(value ?? "unknown").replaceAll("_", " ");
  const shortDigest = (value) => value ? `${String(value).slice(0, 12)}…${String(value).slice(-8)}` : "not retained";
  const stateClass = (value) => `state-${String(value ?? "unknown").replaceAll(" ", "_")}`;
  const stateStamp = (value) => `<span class="state-stamp ${stateClass(value)}">${escapeHTML(labelFor(value))}</span>`;
  const definitionRows = (rows) => rows.map(([term, value]) => `<div><dt>${escapeHTML(term)}</dt><dd>${escapeHTML(value ?? "Unknown")}</dd></div>`).join("");

  function announce(message) {
    text("#announcer", message);
  }

  function renderTheme() {
    document.documentElement.dataset.theme = state.theme;
    $$('[data-theme-choice]').forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === state.theme));
    });
  }

  function renderSourceRail() {
    text("#rail-place", data.place.label);
    text("#rail-place-id", data.place.id);
    text("#rail-source-run", data.source_run_id);
    text("#rail-source-time", data.source_reference_time || data.generated_at || "Source time unavailable");
    html("#rail-source-counts", Object.entries(data.source_summary.state_counts).map(([name, count]) => (
      `<div><dt>${escapeHTML(labelFor(name))}</dt><dd>${count}</dd></div>`
    )).join(""));
    text("#rail-receipt", shortDigest(data.payload_sha256));
  }

  function renderStatus() {
    const aperture = apertureById.get(state.aperture);
    const overlay = overlayById.get(state.overlay);
    const role = roleById.get(state.role);
    html("#global-status", [
      `<span class="status-chip ${stateClass(aperture.state)}">Scale: ${escapeHTML(aperture.id)} · ${escapeHTML(labelFor(aperture.state))}</span>`,
      `<span class="status-chip ${stateClass(overlay.state)}">Instrument: ${escapeHTML(overlay.id)} · ${escapeHTML(labelFor(overlay.state))}</span>`,
      `<span class="status-chip ${stateClass(role.state)}">Seat: ${escapeHTML(role.label)} · ${escapeHTML(labelFor(role.state))}</span>`,
      `<span class="status-chip ${stateClass(data.scene.selected_mode)}">Street: ${escapeHTML(labelFor(data.scene.selected_mode))}</span>`,
      `<span class="status-chip ${stateClass(data.registration.admission_state)}">Registration: ${escapeHTML(labelFor(data.registration.admission_state))}</span>`,
    ].join(""));
  }

  function controlButton(id, label, group, current, stateValue) {
    return `<button type="button" data-${group}="${escapeHTML(id)}" aria-pressed="${id === current}" class="${stateClass(stateValue)}">${escapeHTML(label)}</button>`;
  }

  function renderControls() {
    html("#aperture-controls", data.apertures.map((row) => controlButton(row.id, labelFor(row.id), "aperture", state.aperture, row.state)).join(""));
    html("#overlay-controls", data.overlays.map((row) => controlButton(row.id, labelFor(row.id), "overlay", state.overlay, row.state)).join(""));
    html("#role-controls", data.roles.map((row) => controlButton(row.id, row.label, "role", state.role, row.state)).join(""));
    bindDynamicControls();
  }

  function svgNode(name, attributes = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function renderApertureGeometry(aperture) {
    const geometry = aperture.geometry || {};
    const scale = "scale(1.333333 1.538462)";
    const ground = $("#aperture-ground");
    const branch = $("#aperture-branch");
    const cut = $("#aperture-cut");
    ground.setAttribute("d", geometry.path || "");
    branch.setAttribute("d", geometry.branch || "");
    cut.setAttribute("d", geometry.authority_cut || "");
    [ground, branch, cut].forEach((node) => node.setAttribute("transform", scale));
  }

  function normalizedPoint(pair) {
    return [Number(pair[0]) * 1600, Number(pair[1]) * 1000];
  }

  function renderOverlayGeometry(overlay) {
    const group = $("#overlay-geometry");
    group.replaceChildren();
    const geometry = overlay.geometry || {};
    const points = (geometry.coordinates || []).map(normalizedPoint);
    if (!points.length) return;
    const pointString = points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
    if (geometry.geometry_type === "polygon") {
      group.append(svgNode("polygon", { points: pointString, "data-geometry-id": geometry.id }));
    } else if (geometry.geometry_type === "polyline") {
      group.append(svgNode("polyline", { points: pointString, fill: "none", "data-geometry-id": geometry.id }));
    } else if (geometry.geometry_type === "multipoint") {
      points.forEach(([cx, cy], index) => group.append(svgNode("rect", {
        x: cx - 10, y: cy - 10, width: 20, height: 20, class: "node", "data-node-index": index,
      })));
    } else if (geometry.geometry_type === "graph") {
      (geometry.edges || []).forEach(([start, end]) => {
        const [x1, y1] = points[start];
        const [x2, y2] = points[end];
        group.append(svgNode("line", { x1, y1, x2, y2, "data-edge": `${start}-${end}` }));
      });
      points.forEach(([cx, cy], index) => group.append(svgNode("rect", {
        x: cx - 9, y: cy - 9, width: 18, height: 18, class: "node", "data-node-index": index,
      })));
    }
  }

  function renderRegistrationPoints() {
    const group = $("#registration-points");
    group.replaceChildren();
    const image = data.registration.image || {};
    const width = Number(image.width || 1600);
    const height = Number(image.height || 1000);
    const original = data.registration.original_points || [];
    const proposed = data.registration.proposed_points || [];
    original.forEach((point, index) => {
      const px = Number(point[0]) * (1600 / width);
      const py = Number(point[1]) * (1000 / height);
      const candidate = proposed[index] || point;
      const qx = Number(candidate[0]) * (1600 / width);
      const qy = Number(candidate[1]) * (1000 / height);
      if (Math.abs(px - qx) + Math.abs(py - qy) > .1) {
        group.append(svgNode("line", { x1: px, y1: py, x2: qx, y2: qy, class: "link" }));
      }
      group.append(svgNode("rect", { x: px - 8, y: py - 8, width: 16, height: 16, class: "original" }));
      group.append(svgNode("rect", { x: qx - 5, y: qy - 5, width: 10, height: 10, class: "proposed" }));
    });
  }

  function compositeOperatingView(aperture, overlay, role) {
    const unavailable = [...new Set([
      ...(overlay.missing_source_ids || []),
      ...(role.evidence.unavailable_source_ids || []),
    ])];
    return {
      title: `${role.label}: ${labelFor(aperture.id)} through ${labelFor(overlay.id)}`,
      objectClass: `${aperture.object_class} · ${overlay.object_class} · ${role.object_class}`,
      reading: `${aperture.reading} ${overlay.reading} ${role.reading}`,
      uncertainty: `${aperture.uncertainty} ${overlay.uncertainty}${unavailable.length ? ` Unavailable source identities: ${unavailable.join(", ")}.` : ""}`,
      action: role.safe_actions[0] || overlay.safe_action,
      authority: role.authority,
      acceptance: role.acceptance,
      handoff: role.handoff,
      prohibited: `${overlay.prohibited_consequence} ${role.prohibited_consequence}`,
    };
  }

  function renderOverview() {
    const aperture = apertureById.get(state.aperture);
    const overlay = overlayById.get(state.overlay);
    const role = roleById.get(state.role);
    const view = compositeOperatingView(aperture, overlay, role);

    text("#stage-title", `${labelFor(aperture.id)} · ${labelFor(overlay.id)}`);
    html("#stage-state", `${stateStamp(aperture.state)} ${stateStamp(overlay.state)}`);
    renderApertureGeometry(aperture);
    renderOverlayGeometry(overlay);
    renderRegistrationPoints();
    text("#map-mode", data.scene.selected_mode === "map_only"
      ? `MAP-ONLY · ${data.scene.safe_action}`
      : `${String(data.scene.selected_provider || "scene").toUpperCase()} · retained street scene`);
    text("#stage-caption", `${overlay.geometry.claim_boundary} ${data.registration.claim_boundary}`);

    text("#operating-title", view.title);
    text("#operating-object", view.objectClass);
    text("#operating-reading", view.reading);
    text("#operating-uncertainty", view.uncertainty);
    text("#operating-action", view.action);
    text("#operating-authority", view.authority);
    text("#operating-acceptance", view.acceptance);
    text("#operating-handoff", view.handoff);
    text("#operating-prohibited", view.prohibited);
    html("#role-action-list", role.controls.map((control) => `<li>${escapeHTML(control)}</li>`).join(""));

    const degraded = data.source_summary.sources.filter((row) => row.state !== "ok");
    text("#degraded-count", String(degraded.length));
    html("#degraded-ledger", degraded.length ? degraded.map((row) => (
      `<article class="ledger-row"><strong>${escapeHTML(row.id)}<br>${stateStamp(row.state)}</strong><p>${escapeHTML(row.error || row.claim_scope || "No stronger claim is available.")}</p></article>`
    )).join("") : '<p class="ledger-row">No degraded source states in this run.</p>');

    const conflictRows = (overlay.conflicts_with || []).map((otherId) => {
      const other = overlayById.get(otherId);
      return `<article class="ledger-row"><strong>${escapeHTML(overlay.id)} ↔ ${escapeHTML(otherId)}</strong><p>${escapeHTML(overlay.conflict_behavior)} ${escapeHTML(other?.uncertainty || "")}</p></article>`;
    });
    html("#conflict-list", conflictRows.length ? conflictRows.join("") : '<p class="ledger-row">The selected instrument declares no direct conflict pair.</p>');
  }

  function renderPlace() {
    text("#place-heading", data.place.label);
    html("#place-details", definitionRows([
      ["Place ID", data.place.id],
      ["Projection", data.place.projection],
      ["Coordinate precision", `${data.place.coordinate_precision_decimals} decimal places`],
      ["Source run", data.source_run_id],
      ["Reference time", data.source_reference_time || data.generated_at],
      ["Public safe", data.place.public_safe ? "Yes" : "No"],
    ]));
    html("#scene-details", `
      ${stateStamp(data.scene.selected_mode)}
      <p><strong>Provider:</strong> ${escapeHTML(data.scene.selected_provider)}</p>
      <p>${escapeHTML(data.scene.safe_action)}</p>
      <p><strong>Authority:</strong> ${escapeHTML(data.scene.authority)}</p>
    `);
    html("#registration-details", `
      ${stateStamp(data.registration.admission_state)}
      <p><strong>Confidence:</strong> ${escapeHTML(labelFor(data.registration.confidence_class))}</p>
      <p><strong>Points:</strong> ${escapeHTML(data.registration.point_count ?? "unknown")} · <strong>Mean displacement:</strong> ${escapeHTML(data.registration.mean_displacement_pixels ?? "unknown")} px</p>
      <p>${escapeHTML(data.registration.claim_boundary)}</p>
    `);
    html("#donor-details", definitionRows(Object.entries(data.donor_digests).map(([key, value]) => [labelFor(key), shortDigest(value)])));
  }

  function registerRow(row, kind) {
    const current = state[kind] === row.id;
    const stateValue = row.state || "unknown";
    const reading = row.reading || row.operating_purpose;
    const secondary = kind === "role" ? row.authority : row.safe_action;
    return `<article class="register-row" role="listitem" aria-current="${current}">
      <div><h3>${escapeHTML(kind === "role" ? row.label : labelFor(row.id))}</h3><p class="row-meta">${escapeHTML(row.object_class)}</p></div>
      <div>${stateStamp(stateValue)}</div>
      <div><p>${escapeHTML(reading)}</p></div>
      <div class="register-actions"><p>${escapeHTML(secondary)}</p><button type="button" data-select-kind="${kind}" data-select-id="${escapeHTML(row.id)}">Use this ${kind === "role" ? "seat" : kind}</button></div>
    </article>`;
  }

  function renderRegisters() {
    html("#scale-register", data.apertures.map((row) => registerRow(row, "aperture")).join(""));
    html("#instrument-register", data.overlays.map((row) => registerRow(row, "overlay")).join(""));
    html("#seat-register", data.roles.map((row) => registerRow(row, "role")).join(""));
    const currentRole = roleById.get(state.role);
    html("#handoff-edges", currentRole.handoff_to.map((targetId) => {
      const target = roleById.get(targetId);
      return `<div class="handoff-edge"><strong>${escapeHTML(currentRole.label)}</strong><span class="arrow" aria-hidden="true">→</span><span><strong>${escapeHTML(target?.label || labelFor(targetId))}</strong><br>${escapeHTML(currentRole.handoff)}</span></div>`;
    }).join(""));
    $$('[data-select-kind]').forEach((button) => button.addEventListener("click", () => {
      state[button.dataset.selectKind] = button.dataset.selectId;
      state.section = "overview";
      renderAll();
      focusControl(button.dataset.selectKind, button.dataset.selectId);
    }));
  }

  function renderFab() {
    const fab = data.fab_handoff;
    const proposal = fab.proposal || {};
    const evidence = fab.evidence || {};
    const firewall = fab.effect_firewall || {};
    html("#fab-record", `
      <section><p class="panel-label">Target</p><h3>${escapeHTML(fab.target_system)}</h3><p>${escapeHTML(fab.target_object)}</p><p class="receipt">${escapeHTML(shortDigest(fab.payload_sha256))}</p></section>
      <section><p class="panel-label">Prepared question</p><h3>${escapeHTML(proposal.question || "No question")}</h3><p><strong>Authority:</strong> ${escapeHTML(proposal.authority)}</p><p><strong>Acceptance:</strong> ${escapeHTML(proposal.acceptance)}</p></section>
      <section><p class="panel-label">Affected actor control</p><h3>Correction, refusal, narrowing, deferral, appeal</h3><p>${escapeHTML(proposal.refusal_and_appeal)}</p><p>${escapeHTML(proposal.resident_boundary)}</p></section>
      <section><p class="panel-label">Evidence state</p><h3>${escapeHTML(labelFor(evidence.state))}</h3><p>${escapeHTML(evidence.degraded_evidence_count)} degraded evidence rows · ${escapeHTML((evidence.missing_source_ids || []).length)} missing identities</p></section>
      <section><p class="panel-label">Effect firewall</p><div class="firewall-grid">${Object.entries(firewall).map(([key, value]) => `<div class="firewall-item"><strong>${escapeHTML(labelFor(key))}</strong><span>${escapeHTML(labelFor(value))}</span></div>`).join("")}</div></section>
      <section><p class="panel-label">Claim boundary</p><p>${escapeHTML(fab.claim_boundary)}</p><p><strong>Release state:</strong> ${escapeHTML(labelFor(fab.release_state))}</p></section>
    `);
  }

  function renderSourceFilters() {
    const states = ["all", ...Object.keys(data.source_summary.state_counts)];
    html("#source-filters", states.map((value) => `<button type="button" data-source-filter="${escapeHTML(value)}" aria-pressed="${state.sourceFilter === value}">${escapeHTML(labelFor(value))}</button>`).join(""));
    $$('[data-source-filter]').forEach((button) => button.addEventListener("click", () => {
      state.sourceFilter = button.dataset.sourceFilter;
      renderSources();
      renderSourceFilters();
    }));
  }

  function renderSources() {
    const rows = data.source_summary.sources.filter((row) => state.sourceFilter === "all" || row.state === state.sourceFilter);
    html("#source-register", rows.map((row) => `<article class="source-row">
      <div><h3>${escapeHTML(row.label)}</h3><p class="receipt">${escapeHTML(row.id)} · ${escapeHTML(shortDigest(row.payload_sha256))}</p></div>
      <div>${stateStamp(row.state)}<p>${escapeHTML(row.source_time || row.retrieved_at || "No source time")}</p></div>
      <div><p><strong>Claim:</strong> ${escapeHTML(row.claim_scope)}</p><p><strong>Rights:</strong> ${escapeHTML(row.rights)}</p>${row.error ? `<p><strong>State detail:</strong> ${escapeHTML(row.error)}</p>` : ""}</div>
    </article>`).join("") || '<p>No sources match this filter.</p>');
  }

  function helpMarkup() {
    const controls = data.help.controls.map((row) => `<li><strong>${escapeHTML(labelFor(row.id))}:</strong> ${escapeHTML(row.meaning)}</li>`).join("");
    const holds = data.help.release_holds.map((row) => `<li>${escapeHTML(row)}</li>`).join("");
    const prohibited = data.help.adverse_action_boundary.prohibited_uses.map((row) => `<li>${escapeHTML(row)}</li>`).join("");
    return `<div class="help-grid">
      <section class="help-topic"><h3>Object and actors</h3><p>${escapeHTML(data.help.object.claim_boundary)}</p><p>The design integrator composes the internal candidate. Source custody preserves evidence. Residents, stewards, programs, and the cold successor retain separate authority.</p></section>
      <section class="help-topic"><h3>Operating controls</h3><ul>${controls}</ul></section>
      <section class="help-topic"><h3>Failure states</h3><ul>${data.failure_states.map((row) => `<li>${escapeHTML(row)}</li>`).join("")}</ul></section>
      <section class="help-topic"><h3>Release holds</h3><ul>${holds}</ul></section>
      <section class="help-topic"><h3>Prohibited uses</h3><ul>${prohibited}</ul></section>
      <section class="help-topic"><h3>Human control</h3><p>${escapeHTML(data.help.adverse_action_boundary.required_human_control)}</p><p><strong>Control question:</strong> ${escapeHTML(data.control_question)}</p></section>
    </div>`;
  }

  function renderHelp() {
    const markup = helpMarkup();
    html("#help-content", markup);
    html("#help-dialog-content", markup);
  }

  function renderSections() {
    $$('[data-section-panel]').forEach((panel) => { panel.hidden = panel.dataset.sectionPanel !== state.section; });
    $$('[data-section]').forEach((button) => {
      if (button.dataset.section === state.section) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
  }

  function currentSnapshot() {
    const aperture = apertureById.get(state.aperture);
    const overlay = overlayById.get(state.overlay);
    const role = roleById.get(state.role);
    return {
      schema: "axm-tools/manzanita-whole-experience-snapshot@1",
      experience_id: data.experience_id,
      place: data.place,
      source_run_id: data.source_run_id,
      selected: { aperture: state.aperture, overlay: state.overlay, role: state.role, theme: state.theme },
      aperture,
      overlay,
      role,
      fab_handoff: data.fab_handoff,
      donor_digests: data.donor_digests,
      source_state_counts: data.source_summary.state_counts,
      export_law: data.export_law,
      public_effect: "none",
      constitutional_count_effect: "none",
      release_state: "not_authorized",
      claim_boundary: data.claim_boundary,
      control_question: data.control_question,
    };
  }

  function exportSnapshot() {
    const snapshot = currentSnapshot();
    const blob = new Blob([`${JSON.stringify(snapshot, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `manzanita-${state.aperture}-${state.overlay}-${state.role}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    announce("Bounded local snapshot exported. No external effect occurred.");
  }

  function focusControl(kind, id) {
    const selector = kind === "role" ? `[data-role="${CSS.escape(id)}"]` : `[data-${kind}="${CSS.escape(id)}"]`;
    const control = $(selector);
    if (control) control.focus();
  }

  function select(kind, id, { announceChange = true } = {}) {
    const collection = kind === "aperture" ? apertureById : kind === "overlay" ? overlayById : roleById;
    if (!collection.has(id)) return;
    state[kind] = id;
    renderAll();
    if (announceChange) announce(`${labelFor(kind)} changed to ${kind === "role" ? collection.get(id).label : labelFor(id)}.`);
  }

  function bindDynamicControls() {
    $$('[data-aperture]').forEach((button) => button.addEventListener("click", () => select("aperture", button.dataset.aperture)));
    $$('[data-overlay]').forEach((button) => button.addEventListener("click", () => select("overlay", button.dataset.overlay)));
    $$('[data-role]').forEach((button) => button.addEventListener("click", () => select("role", button.dataset.role)));
    $$('[data-control-group]').forEach((fieldset) => {
      if (fieldset.dataset.keyboardBound === "true") return;
      fieldset.dataset.keyboardBound = "true";
      fieldset.addEventListener("keydown", (event) => {
        if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
        const buttons = $$('button', fieldset);
        if (!buttons.length) return;
        const current = Math.max(0, buttons.indexOf(document.activeElement));
        let next = current;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (current + 1) % buttons.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (current - 1 + buttons.length) % buttons.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = buttons.length - 1;
        const target = buttons[next];
        const kind = target.hasAttribute("data-aperture")
          ? "aperture"
          : target.hasAttribute("data-overlay")
            ? "overlay"
            : target.hasAttribute("data-role")
              ? "role"
              : null;
        const id = kind ? target.dataset[kind] : null;
        if (!kind || !id) return;
        event.preventDefault();
        select(kind, id);
        focusControl(kind, id);
      });
    });
  }

  function bindStaticControls() {
    $$('[data-theme-choice]').forEach((button) => button.addEventListener("click", () => {
      state.theme = button.dataset.themeChoice;
      localStorage.setItem("manzanita-theme", state.theme);
      renderTheme();
      announce(`Theme changed to ${state.theme}.`);
    }));
    $$('[data-section]').forEach((button) => button.addEventListener("click", () => {
      state.section = button.dataset.section;
      renderSections();
      const panel = $(`[data-section-panel="${CSS.escape(state.section)}"]`);
      const heading = panel?.querySelector("h2");
      if (heading) heading.setAttribute("tabindex", "-1"), heading.focus();
    }));
    $("#export-button").addEventListener("click", exportSnapshot);
    $("#help-button").addEventListener("click", () => $("#help-dialog").showModal());
  }

  function renderAll() {
    renderTheme();
    renderSourceRail();
    renderStatus();
    renderControls();
    renderOverview();
    renderPlace();
    renderRegisters();
    renderFab();
    renderSourceFilters();
    renderSources();
    renderHelp();
    renderSections();
    text("#masthead-summary", `${data.place.label}. ${data.claim_boundary}`);
    window.__MANZANITA_WHOLE_EXPERIENCE_RUNTIME__ = {
      version: data.contract_version,
      experienceId: data.experience_id,
      placeId: data.place.id,
      sourceRunId: data.source_run_id,
      getState: () => ({ ...state }),
      snapshot: currentSnapshot,
      select,
    };
  }

  bindStaticControls();
  renderAll();
})();
