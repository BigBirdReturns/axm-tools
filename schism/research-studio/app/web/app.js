"use strict";

(() => {
  const $ = (selector, node = document) => node.querySelector(selector);
  const $$ = (selector, node = document) => Array.from(node.querySelectorAll(selector));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const asArray = value => Array.isArray(value) ? value : value == null ? [] : [value];
  const text = value => typeof value === "string" ? value : value == null ? "" : JSON.stringify(value);
  const pretty = value => text(value).replace(/_/g," ").replace(/-/g," ");
  const number = value => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "Unspecified";
  const fields = value => Object.values(value || {}).map(item => typeof item === "object" ? JSON.stringify(item) : item).join(" ").toLowerCase();
  const state = {catalog:null, view:"overview", query:"", project:"", replayStops:[]};
  const replayCache = new WeakMap();
  const views = {
    overview:["Overview","The current record, its supporting sources, and the work still to close."],
    sources:["Sources & history","Trace each project to retained source material and dated decisions."],
    campaigns:["Recorded campaigns","Inspect execution records with their original scope, outcomes, and source identity."],
    gaps:["Research closure","Follow the dependencies and acceptance criteria that remain with each owner."],
    vendors:["Vendor access","Read the aggregate findings, published evidence and local execution state for each named vendor."]
  };
  const resolveSource = ref => {
    const id = typeof ref === "object" ? ref?.id || ref?.source_ref : ref;
    return (state.catalog?.sources || []).find(source => source.id === id);
  };
  const sourceId = ref => typeof ref === "object" ? ref?.id || ref?.source_ref || "" : String(ref || "");
  const refsFor = record => [...new Set([
    ...asArray(record.evidence_refs), ...asArray(record.source_refs),
    ...asArray(record.source_ref), ...asArray(record.execution_source_ref),
    ...asArray(record.replay?.source_refs), ...asArray(record.replay_context?.source_refs),
    ...Object.values(record.derived_from || {}).map(binding=>binding?.source_ref)
  ].filter(Boolean))];
  const projectFor = record => record.project || record.owner || resolveSource(record.source_ref)?.project || "";
  const matches = record => {
    const refs = refsFor(record).map(resolveSource).filter(Boolean);
    const projectMatch = !state.project || projectFor(record) === state.project || refs.some(source => source.project === state.project) || record.title === state.project || record.id === state.project;
    const referenceText = refs.map(source => fields({id:source.id,title:source.title,project:source.project,kind:source.kind,source_date:source.source_date,path:source.path,notes:source.notes})).join(" ");
    return projectMatch && (!state.query || `${fields(record)} ${referenceText}`.includes(state.query));
  };
  const selected = key => (state.catalog?.[key] || []).filter(matches);
  const date = value => {
    if (!value) return "Undated";
    if (!/^\d{4}-\d{2}-\d{2}T/.test(String(value))) return String(value);
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString(undefined,{year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
  };
  const pill = value => {
    const label = text(value) || "Unspecified";
    const raw = label.toLowerCase();
    let kind = "";
    if (/fail|rejected|invalid|unavailable|missing/.test(raw)) kind="bad";
    else if (/partial|open|blocked|pending|unverified|unknown|unresolved|not |not_|planned/.test(raw)) kind="partial";
    else if (/pass|accepted|verified|executed|available|complete|retained|published/.test(raw)) kind="good";
    return `<span class="pill ${kind}" title="${esc(label)}">${esc(pretty(label))}</span>`;
  };
  const sourcePill = source => source.status === "verified" ? '<span class="pill good" title="verified: retained file identity and declared extraction checked">File identity checked</span>' : pill(source.status);
  const sourceRefs = (refs, compact=false) => {
    const all = asArray(refs).filter(Boolean);
    if (!all.length) return "";
    return `<div class="ref-list">${all.map(ref => {
      const source = resolveSource(ref); const id = sourceId(ref);
      return `<button class="source-chip ${source ? "" : "unresolved"}" data-source="${esc(id)}" title="${esc(source?.title || id)}">${esc(compact ? source?.project || source?.kind || id : source?.title || id)}</button>`;
    }).join("")}</div>`;
  };
  const empty = (title="No matching records", message="Change the search or project filter to see more retained work.") => `<div class="empty"><strong>${esc(title)}</strong><p>${esc(message)}</p></div>`;
  const listNotes = notes => asArray(notes).length ? `<ul class="notes">${asArray(notes).map(note=>`<li>${esc(text(note))}</li>`).join("")}</ul>` : "";
  const sectionHeading = (title,count,action) => `<div class="section-heading"><h2>${esc(title)}</h2>${action ? `<button class="minor-link" data-view="${esc(action)}">View all <span aria-hidden="true">↗</span></button>` : `<small>${number(count)} records</small>`}</div>`;

  function overview() {
    const c=state.catalog, components=selected("components"), campaigns=selected("campaigns"), gaps=selected("gaps"), lineage=selected("lineage");
    const summary = typeof c.summary === "string" ? `<p>${esc(c.summary)}</p>` : Array.isArray(c.summary) ? `<ul class="summary-list">${c.summary.map(item=>`<li>${esc(text(item))}</li>`).join("")}</ul>` : c.summary ? `<p>${esc(text(c.summary))}</p>` : "";
    return `<div class="stat-row">${[["Components",components.length,"Retained project scope"],["Sources",selected("sources").length,"Inspectable provenance"],["Recorded campaigns",campaigns.length,"Kept in original scope"],["Research dependencies",gaps.length,"Owner and acceptance"]].map(([label,value,sub])=>`<div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${number(value)}</div><div class="stat-sub">${sub}</div></div>`).join("")}</div>
      ${summary ? `<section class="overview-summary"><h2>${esc(c.title || "Retained research")}</h2>${summary}</section>` : ""}
      ${sectionHeading("Components carried forward",components.length)}
      ${components.length ? `<section class="component-grid">${components.map(component=>`<article class="component-card"><div class="role-label">${esc(component.role || "Component")}</div><div class="card-top"><h3>${esc(component.title || component.id)}</h3>${pill(component.status)}</div><p>${esc(text(component.summary))}</p>${asArray(component.limitations).length ? `<details class="limits"><summary>Scope and limits · ${component.limitations.length}</summary><ul>${component.limitations.map(item=>`<li>${esc(text(item))}</li>`).join("")}</ul></details>` : ""}${sourceRefs(component.evidence_refs)}</article>`).join("")}</section>` : empty("No matching components")}
      <div class="split-panel"><section>${sectionHeading("Research dependencies",gaps.length,"gaps")}<div class="panel">${gaps.slice(0,5).map(gap=>`<article class="mini-item"><div class="mini-meta">${pill(gap.status)}<span>${esc(gap.owner || "Owner unspecified")}</span></div><h3>${esc(gap.title)}</h3><p>${esc(text(gap.why || gap.acceptance))}</p></article>`).join("") || empty("No matching dependencies")}</div></section><section>${sectionHeading("Source lineage",lineage.length,"sources")}<div class="panel"><div class="timeline">${timeline(lineage.slice(-5)) || empty("No dated lineage supplied","The catalog has not supplied dated project history.")}</div></div></section></div>`;
  }

  function timeline(items) {
    return items.map(item=>`<article class="timeline-item"><time>${esc(date(item.date))}</time><h3>${esc(item.title || "Retained record")}</h3><p>${esc(text(item.description))}</p>${item.date_basis ? `<div class="date-basis">Date basis: ${esc(item.date_basis)}</div>` : ""}${sourceRefs(item.source_refs,true)}</article>`).join("");
  }

  function sourcesView() {
    const sources=selected("sources"), history=selected("lineage");
    return `<div class="history-layout"><section class="panel"><div class="panel-heading"><h2>Retained sources</h2><span class="small-count">${number(sources.length)} records</span></div>${sources.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Source / project</th><th scope="col">Evidence class</th><th scope="col">Source date</th></tr></thead><tbody>${sources.map(source=>`<tr><td><button class="row-title" data-source="${esc(source.id)}">${esc(source.title || source.id)}</button><div class="row-subtitle">${esc(source.project || "Project unspecified")}</div></td><td>${sourcePill(source)}<div class="row-subtitle">${esc(pretty(source.kind || "Unspecified"))}</div></td><td class="date-cell">${esc(date(source.source_date))}</td></tr>`).join("")}</tbody></table></div>` : empty()}</section><section class="panel"><div class="panel-heading"><h2>Project lineage</h2><span class="small-count">${number(history.length)}</span></div><div class="timeline">${timeline(history) || empty("No matching history")}</div></section></div>`;
  }

  function campaignMetrics(campaign) {
    const counts=[["Attempted",campaign.attempted],["Completed",campaign.completed],["Failed",campaign.failed]].filter(([,value])=>value != null);
    const declared=Array.isArray(campaign.metrics) ? campaign.metrics : Object.entries(campaign.metrics || {}).map(([label,value])=>({label,value}));
    return `${counts.length ? `<div class="run-metrics">${counts.map(([label,value])=>`<div class="run-metric"><span>${label}</span><strong>${number(value)}</strong></div>`).join("")}</div>` : ""}${declared.length ? `<div class="declared-metrics"><table class="metrics-table"><thead><tr><th scope="col">Recorded measure</th><th scope="col">Value</th><th scope="col">Scope</th></tr></thead><tbody>${declared.map(metric=>`<tr><td>${esc(metric.label || metric.name || "Measure")}</td><td>${esc(typeof metric.value === "number" ? metric.value.toLocaleString(undefined,{maximumFractionDigits:20}) : text(metric.value) || "Unspecified")}${metric.unit ? ` <span>${esc(metric.unit)}</span>` : ""}</td><td>${esc(text(metric.scope))}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
  }

  function replayUnit(replay,axis) {
    return typeof replay.units === "string" ? (axis === "t" ? "" : replay.units) : text(replay.units?.[axis] || (axis === "t" ? replay.time_unit : replay.position_unit));
  }

  function displayReplay(campaign) {
    if (!campaign.replay) return null;
    if (replayCache.has(campaign)) return replayCache.get(campaign);
    const raw=campaign.replay, context=campaign.replay_context || {};
    let frames, objectCount;
    if (Array.isArray(raw.frames)) {
      frames=raw.frames;
    } else if (Array.isArray(raw.balls) && Number.isInteger(raw.frames) && raw.frames>0 && Number.isFinite(raw.fps) && raw.fps>0) {
      objectCount=raw.balls.length;
      frames=Array.from({length:raw.frames},(_,frameIndex)=>({
        t:frameIndex/raw.fps,
        points:raw.balls.map((ball,ballIndex)=>({id:ball.id ?? `ball-${ballIndex+1}`,x:ball.traj[frameIndex][0],y:ball.traj[frameIndex][1],z:ball.traj[frameIndex][2]}))
      }));
    } else return null;
    const replay={frames,objectCount,
      caption:context.caption ?? raw.caption,
      source_refs:[...new Set([...asArray(raw.source_refs),...asArray(context.source_refs)])],
      units:context.units ?? raw.units,
      position_unit:context.position_unit ?? raw.position_unit,
      time_unit:context.time_unit ?? raw.time_unit
    };
    replayCache.set(campaign,replay);
    return replay;
  }

  function replayView(campaign,index) {
    const replay=displayReplay(campaign);
    if(!replay?.frames.length) return "";
    return `<section class="replay" data-replay-index="${index}"><div class="replay-heading"><strong>Recorded trajectory playback</strong><span>Planar view · X / Y${replayUnit(replay,"x") ? ` · ${esc(replayUnit(replay,"x"))}` : ""}</span></div><canvas aria-label="Recorded planar trajectories for ${esc(campaign.title)}"></canvas><div class="replay-controls"><button data-play>Play</button><input data-frame type="range" min="0" max="${replay.frames.length-1}" value="0" step="1" aria-label="Recorded frame"><output data-time>Frame 1</output></div>${replay.objectCount != null ? `<p class="replay-caption">${number(replay.objectCount)} recorded objects · ${number(replay.frames.length)} frames</p>` : ""}${replay.caption ? `<p class="replay-caption">${esc(text(replay.caption))}</p>` : ""}<p class="replay-caption">Archived sample positions. Playback advances by recorded sample, without executing new dynamics.</p>${sourceRefs(replay.source_refs)}</section>`;
  }

  function campaignsView() {
    const campaigns=selected("campaigns");
    return `<p class="scope-note">Counts belong to each recorded campaign. Replays, superseded runs, and overlapping evidence retain their own identities.</p>${campaigns.length ? `<section class="campaign-list">${campaigns.map((campaign,index)=>`<article class="campaign-card"><div class="campaign-head"><div class="role-label">${esc(campaign.project || "Recorded campaign")} · ${esc(pretty(campaign.record_class || "Class unspecified"))}</div><div class="card-top"><h3>${esc(campaign.title || campaign.id)}</h3>${pill(campaign.status)}</div><p>${esc(text(campaign.scope))}</p></div><div class="campaign-body">${campaignMetrics(campaign)}${listNotes(campaign.notes)}${sourceRefs(refsFor(campaign))}${replayView(campaign,index)}</div></article>`).join("")}</section>` : empty()}`;
  }

  function gapsView() {
    const gaps=selected("gaps");
    return gaps.length ? `<section class="gap-list">${gaps.map(gap=>`<article class="gap-card" id="gap-${esc(gap.id)}"><div class="card-top"><h3>${esc(gap.title || gap.id)}</h3>${pill(gap.status)}</div>${gap.why ? `<p>${esc(text(gap.why))}</p>` : ""}<div class="acceptance"><span class="acceptance-label">Acceptance</span><p>${esc(text(gap.acceptance) || "Acceptance criteria have not been supplied.")}</p></div><div class="gap-meta"><span>Owner: ${esc(gap.owner || "Unspecified")}</span>${asArray(gap.depends_on).length ? `<span>Depends on: ${gap.depends_on.map(dep=>`<button class="dependency" data-dependency="${esc(typeof dep === "object" ? dep.id : dep)}">${esc(typeof dep === "object" ? dep.title || dep.id : (state.catalog.gaps || []).find(item=>item.id===dep)?.title || dep)}</button>`).join(", ")}</span>` : ""}</div>${sourceRefs(gap.source_refs)}</article>`).join("")}</section>` : empty();
  }

  function vendorFindings() {
    return (state.catalog.findings || []).filter(finding=>finding.kind === "vendor-summary").map(finding=>{
      const refs=refsFor(finding);
      const available=refs.length>0 && refs.every(ref=>resolveSource(ref)?.status === "verified") && finding.status !== "source-unverified";
      const metrics=available ? asArray(finding.metrics).filter(metric=>metric && metric.value != null) : [];
      return `<section class="vendor-finding" data-finding="${esc(finding.id)}"><div class="role-label">Full reviewed roster</div><h2>${esc(available ? finding.title || "Vendor finding" : "Finding source unavailable")}</h2>${available ? `${finding.summary ? `<p class="finding-summary">${esc(text(finding.summary))}</p>` : ""}${metrics.length ? `<div class="finding-metrics">${metrics.map(metric=>`<div class="finding-metric"><span>${esc(metric.label || "Recorded measure")}</span><strong>${esc(typeof metric.value === "number" ? number(metric.value) : text(metric.value))}</strong>${metric.scope ? `<small>${esc(text(metric.scope))}</small>` : ""}</div>`).join("")}</div>` : ""}${listNotes(finding.notes)}` : '<p class="finding-summary">The source identity for this finding has not been verified.</p>'}${sourceRefs(refs)}</section>`;
    }).join("");
  }

  function publishedEvidence(vendor) {
    const kind=vendor.documentary_evidence?.published_demonstration?.class;
    const labels={reported_component_substitution:"Component substitution reported",reported_integration:"Integration reported",no_substitution_result_retrieved:"No substitution result retrieved"};
    return esc(labels[kind] || pretty(kind) || "Unspecified");
  }

  function vendorsView() {
    const vendors=selected("vendors");
    return `${vendorFindings()}<p class="scope-note">Each row preserves the catalog's published evidence and local execution state. Search and project filters apply to the vendor rows; aggregate findings retain the full reviewed roster.</p>${vendors.length ? `<section class="panel"><div class="panel-heading"><h2>Vendor evidence</h2><span class="small-count">${number(vendors.length)} entries</span></div><div class="table-scroll"><table class="data-table vendor-table"><thead><tr><th scope="col">Vendor</th><th scope="col">Published evidence</th><th scope="col">Recorded state</th><th scope="col">Evidence and limits</th></tr></thead><tbody>${vendors.map(vendor=>`<tr><td><strong>${esc(vendor.name)}</strong></td><td class="published-evidence">${publishedEvidence(vendor)}</td><td>${pill(vendor.state)}</td><td><div class="vendor-description">${asArray(vendor.notes).map(note=>esc(text(note))).join("<br>")}</div>${sourceRefs(refsFor(vendor))}</td></tr>`).join("")}</tbody></table></div></section>` : empty("No vendor records supplied","This catalog does not establish access to additional vendor implementations.")}`;
  }

  function render() {
    if (!state.catalog) return;
    state.replayStops.forEach(stop=>stop()); state.replayStops=[];
    const [title,description]=views[state.view] || views.overview;
    $("#view-title").textContent=title;
    $("#view-description").textContent=description;
    $("#eyebrow").textContent=state.view === "overview" ? "Research workspace" : "Evidence explorer";
    $$("#nav [data-view]").forEach(button=>{
      const active=button.dataset.view===state.view;
      button.classList.toggle("active",active);
      if(active) button.setAttribute("aria-current","page"); else button.removeAttribute("aria-current");
    });
    $$("[data-count]").forEach(node=>node.textContent=number(selected(node.dataset.count).length));
    const content=$("#content");
    content.innerHTML=({overview,sources:sourcesView,campaigns:campaignsView,gaps:gapsView,vendors:vendorsView}[state.view] || overview)();
    content.insertAdjacentHTML("beforeend",`<p class="catalog-footer">Catalog observation: ${esc(date(state.catalog.generated_at))}</p>`);
    content.setAttribute("aria-busy","false");
    $("#clear-filters").hidden=!state.query&&!state.project;
    $("#filter-note").textContent=state.query||state.project ? "Filtered catalog" : "";
    if(state.view==="campaigns") attachReplays();
  }

  function showSource(id) {
    const source=resolveSource(id), dialog=$("#source-dialog");
    $("#dialog-title").textContent=source?.title || id || "Unresolved source reference";
    $("#dialog-eyebrow").textContent="Source provenance";
    const keys=[["Project","project"],["Kind","kind"],["Status","status"],["Source date","source_date"],["Observed at","observed_at"],["Host","host"],["Source path","path"],["SHA-256","sha256"],["Bytes","bytes"],["Source ID","id"]];
    $("#dialog-content").innerHTML=source ? `<dl class="provenance-grid">${keys.map(([label,key])=>{
      let value=source[key];
      if(key==="bytes") value=typeof value==="number" ? `${number(value)} bytes` : "Unspecified";
      else if(key.includes("date")||key==="observed_at") value=date(value);
      else value=text(value)||"Unspecified";
      return `<dt>${label}</dt><dd>${["path","sha256","id"].includes(key) ? `<code>${esc(value)}</code>` : key==="status" ? sourcePill(source) : esc(value)}</dd>`;
    }).join("")}</dl>${source.notes ? `<div class="dialog-note">${asArray(source.notes).map(note=>esc(text(note))).join("<br>")}</div>` : ""}` : `<p class="dialog-note">This record references ${esc(id)}, but the catalog does not contain its source details.</p>`;
    if(!dialog.open) dialog.showModal();
  }

  function attachReplays() {
    const campaigns=selected("campaigns");
    $$("[data-replay-index]").forEach(element=>{
      const replay=displayReplay(campaigns[Number(element.dataset.replayIndex)]);
      const frames=replay.frames, canvas=$("canvas",element), ctx=canvas.getContext("2d"), slider=$("[data-frame]",element), output=$("[data-time]",element), button=$("[data-play]",element);
      if(!ctx) return;
      const points=frames.flatMap(frame=>asArray(frame.points)).filter(point=>Number.isFinite(point.x)&&Number.isFinite(point.y));
      if(!points.length){element.innerHTML='<p class="replay-caption">The retained playback has no finite planar coordinates.</p>';return;}
      const bounds=points.reduce((b,p)=>[Math.min(b[0],p.x),Math.max(b[1],p.x),Math.min(b[2],p.y),Math.max(b[3],p.y)],[Infinity,-Infinity,Infinity,-Infinity]);
      const ids=[...new Set(points.map(p=>String(p.id ?? "point")))];
      const byFrame=frames.map(frame=>new Map(asArray(frame.points).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)).map(p=>[String(p.id??"point"),p])));
      const trailLength=ids.length>20?18:150;
      const colors=["#14695d","#bd7838","#486b99","#986b97","#657d39","#aa5755"];
      let playing=false,lastTick=0,animation=0,index=0;
      function draw(){
        const rect=canvas.getBoundingClientRect(), dpr=Math.min(window.devicePixelRatio||1,2);
        canvas.width=Math.max(1,Math.round(rect.width*dpr));canvas.height=Math.max(1,Math.round(rect.height*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);
        const w=rect.width,h=rect.height,pad=28,dx=Math.max(bounds[1]-bounds[0],1),dy=Math.max(bounds[3]-bounds[2],1),scale=Math.min((w-2*pad)/dx,(h-2*pad)/dy),cx=(bounds[0]+bounds[1])/2,cy=(bounds[2]+bounds[3])/2;
        const map=p=>[w/2+(p.x-cx)*scale,h/2-(p.y-cy)*scale];
        ctx.fillStyle="#f0f4ed";ctx.fillRect(0,0,w,h);ctx.strokeStyle="#dce6d8";ctx.lineWidth=1;
        for(let k=1;k<8;k++){ctx.beginPath();ctx.moveTo(k*w/8,0);ctx.lineTo(k*w/8,h);ctx.stroke();ctx.beginPath();ctx.moveTo(0,k*h/8);ctx.lineTo(w,k*h/8);ctx.stroke();}
        ids.forEach((id,idIndex)=>{
          ctx.strokeStyle=colors[idIndex%colors.length];ctx.lineWidth=ids.length>20?1:1.7;ctx.globalAlpha=ids.length>20?.4:.65;ctx.beginPath();let started=false;
          for(let i=Math.max(0,index-trailLength);i<=index;i++){
            const point=byFrame[i].get(id);
            if(!point){started=false;continue;}const [x,y]=map(point);if(!started){ctx.moveTo(x,y);started=true;}else ctx.lineTo(x,y);
          }ctx.stroke();ctx.globalAlpha=1;
          const current=byFrame[index].get(id);
          if(current){const [x,y]=map(current);ctx.fillStyle=colors[idIndex%colors.length];ctx.beginPath();ctx.arc(x,y,ids.length>20?2.8:4.5,0,Math.PI*2);ctx.fill();if(ids.length<=12){ctx.font="10px system-ui";ctx.fillText(id,x+8,y-7);}}
        });
        ctx.fillStyle="#728470";ctx.font="10px system-ui";ctx.fillText(`${ids.length} tracked points · ${Math.min(index+1,trailLength+1)} sample trails`,12,h-12);
        const t=frames[index].t;output.textContent=Number.isFinite(t)?`${t.toFixed(2)}${replayUnit(replay,"t") ? " "+replayUnit(replay,"t") : ""} · ${index+1}/${frames.length}`:`${index+1}/${frames.length}`;
        slider.value=String(index);
      }
      function tick(time){if(!playing)return;if(time-lastTick>=80){index=Math.min(index+1,frames.length-1);lastTick=time;draw();if(index===frames.length-1){playing=false;button.textContent="Replay";return;}}animation=requestAnimationFrame(tick);}
      button.addEventListener("click",()=>{playing=!playing;if(playing&&index===frames.length-1)index=0;button.textContent=playing?"Pause":"Play";if(playing){lastTick=0;animation=requestAnimationFrame(tick);}else cancelAnimationFrame(animation);});
      slider.addEventListener("input",()=>{playing=false;cancelAnimationFrame(animation);button.textContent="Play";index=Number(slider.value);draw();});
      const resize=new ResizeObserver(draw);resize.observe(canvas);draw();
      state.replayStops.push(()=>{playing=false;cancelAnimationFrame(animation);resize.disconnect();});
    });
  }

  async function load() {
    $("#refresh").disabled=true;$("#catalog-state").textContent="Loading";
    try{
      const response=await fetch("/api/catalog",{cache:"no-store",headers:{Accept:"application/json"}});
      if(!response.ok)throw new Error(`Catalog request returned ${response.status}`);
      const catalog=await response.json();
      if(!catalog||typeof catalog!=="object")throw new Error("The catalog is not an object.");
      if(catalog.schema&&catalog.schema!=="research-index@1")throw new Error(`Unsupported catalog schema: ${catalog.schema}`);
      for(const key of ["components","sources","campaigns","lineage","gaps","vendors","findings"])if(catalog[key]&&!Array.isArray(catalog[key]))throw new Error(`Catalog field ${key} must be an array.`);
      state.catalog=catalog;
      const projects=[...new Set([...(catalog.sources||[]),...(catalog.campaigns||[])].map(item=>item.project).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
      $("#project").innerHTML='<option value="">All projects</option>'+projects.map(project=>`<option value="${esc(project)}">${esc(project)}</option>`).join("");
      if(!projects.includes(state.project))state.project="";
      $("#project").value=state.project;$("#catalog-time").textContent=date(catalog.generated_at);$("#catalog-state").textContent="Local catalog";
      const requested=location.hash.slice(1);if(views[requested])state.view=requested;
      render();
    }catch(error){
      state.replayStops.forEach(stop=>stop());state.replayStops=[];
      $("#catalog-state").textContent="Unavailable";$("#catalog-time").textContent="Unavailable";$("#content").setAttribute("aria-busy","false");
      $("#content").innerHTML=`<section class="error-card"><h2>Catalog unavailable</h2><p>The local research record could not be read. Existing source files remain with their project owners.</p><code>${esc(error.message)}</code><button id="retry-load">Retry catalog</button></section>`;
      $("#retry-load").addEventListener("click",load);
    }finally{$("#refresh").disabled=false;}
  }
  function navigate(view){if(!views[view])return;state.view=view;history.replaceState(null,"",`#${view}`);render();window.scrollTo({top:0,behavior:"instant"});}
  document.addEventListener("click",event=>{
    const nav=event.target.closest("[data-view]");if(nav){navigate(nav.dataset.view);return;}
    const source=event.target.closest("[data-source]");if(source){showSource(source.dataset.source);return;}
    const dependency=event.target.closest("[data-dependency]");if(dependency){
      const id=dependency.dataset.dependency;const gap=(state.catalog?.gaps||[]).find(item=>item.id===id);
      if(!gap){if(resolveSource(id))showSource(id);return;}
      state.query="";state.project="";$("#search").value="";$("#project").value="";navigate("gaps");
      const target=document.getElementById(`gap-${id}`);target?.scrollIntoView({block:"center",behavior:"smooth"});target?.classList.add("highlight");setTimeout(()=>target?.classList.remove("highlight"),2200);
    }
  });
  $("#search").addEventListener("input",event=>{state.query=event.target.value.trim().toLowerCase();render();});
  $("#project").addEventListener("change",event=>{state.project=event.target.value;render();});
  $("#clear-filters").addEventListener("click",()=>{state.query="";state.project="";$("#search").value="";$("#project").value="";render();});
  $("#refresh").addEventListener("click",load);$("#close-dialog").addEventListener("click",()=>$("#source-dialog").close());
  $("#source-dialog").addEventListener("click",event=>{if(event.target===$("#source-dialog")){const rect=event.target.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)event.target.close();}});
  document.addEventListener("keydown",event=>{if(event.key==="/"&&!/input|textarea|select/i.test(document.activeElement.tagName)&&!$("#source-dialog").open){event.preventDefault();$("#search").focus();}});
  window.addEventListener("hashchange",()=>{const view=location.hash.slice(1);if(views[view]){state.view=view;render();}});
  load();
})();
