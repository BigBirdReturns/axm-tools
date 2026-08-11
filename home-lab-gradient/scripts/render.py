#!/usr/bin/env python3
"""Build the standalone Home Lab Capability Gradient interface."""

from __future__ import annotations

import base64
import gzip
import html
import json
from pathlib import Path
from typing import Any, Mapping


def _compressed_payload(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode("ascii")


def build_page(
    *,
    estate: Mapping[str, Any],
    goals: Mapping[str, Any],
    experiments: Mapping[str, Any],
    evidence: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> str:
    title = "Home Lab Capability Gradient"
    embedded = {
        "estate": estate,
        "goals": goals,
        "experiments": experiments,
        "evidence": evidence,
        "plan": plan,
    }
    payload = _compressed_payload(embedded)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="A local, evidence-tiered planner that selects the smallest reversible home-lab experiment that advances hard orchestration goals.">
<meta name="axm-plan-sha256" content="{html.escape(str(plan['plan_sha256']))}">
<script>
document.documentElement.dataset.theme=localStorage.getItem("home-lab-gradient-theme")||
  (matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
</script>
<style>
:root{{
  --paper:#f4f2ec;--panel:#fffdf8;--ink:#181a1d;--muted:#61656b;--line:#d9d5ca;
  --accent:#235d5b;--accent2:#9a5a2d;--good:#28643f;--hold:#8b5b17;--bad:#923b35;
  --soft:#e9ece7;--shadow:0 10px 30px rgba(27,31,36,.08);--code:#eef0eb;
}}
:root[data-theme="dark"]{{
  --paper:#17191b;--panel:#202326;--ink:#ece8df;--muted:#aaa79f;--line:#383c40;
  --accent:#75b8b3;--accent2:#dda071;--good:#7fc997;--hold:#e1b468;--bad:#e49189;
  --soft:#292e31;--shadow:0 10px 30px rgba(0,0,0,.24);--code:#171a1c;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.52 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
button,input,select{{font:inherit}}
a{{color:var(--accent)}}
.shell{{max-width:1240px;margin:0 auto;padding:24px}}
header{{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:end;padding:18px 0 22px;border-bottom:1px solid var(--line)}}
.eyebrow{{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--accent);font-weight:750}}
h1{{font-size:clamp(30px,5vw,56px);line-height:1.02;letter-spacing:-.045em;margin:8px 0 10px;max-width:900px}}
.lede{{font-size:17px;color:var(--muted);max-width:860px;margin:0}}
.header-actions{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}}
button,.button{{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:8px 11px;cursor:pointer;text-decoration:none}}
button:hover,.button:hover{{border-color:var(--accent)}}
button.primary{{background:var(--accent);color:var(--paper);border-color:var(--accent)}}
.summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}}
.metric{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px;box-shadow:var(--shadow)}}
.metric b{{display:block;font-size:27px;letter-spacing:-.03em}}
.metric span{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}}
.layout{{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;align-items:start}}
main{{min-width:0}}
aside{{position:sticky;top:14px}}
section{{margin:24px 0}}
.section-head{{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:10px}}
h2{{font-size:22px;letter-spacing:-.02em;margin:0}}
h3{{font-size:17px;margin:0}}
.subtle{{color:var(--muted);font-size:13px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow)}}
.card+.card{{margin-top:10px}}
.hero-card{{border-top:4px solid var(--accent);padding:20px}}
.rank{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
.description{{color:var(--muted);margin:7px 0 12px}}
.badges{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}}
.badge{{font-size:11px;border:1px solid var(--line);border-radius:99px;padding:3px 7px;background:var(--soft)}}
.badge.good{{border-color:color-mix(in srgb,var(--good),transparent 45%);color:var(--good)}}
.badge.hold{{border-color:color-mix(in srgb,var(--hold),transparent 45%);color:var(--hold)}}
.vector{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:12px 0}}
.vector div{{background:var(--soft);border-radius:7px;padding:8px}}
.vector b{{display:block;font-size:14px}}
.vector span{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
.callout{{background:color-mix(in srgb,var(--accent),transparent 91%);border-left:3px solid var(--accent);padding:12px 14px;border-radius:7px;margin:12px 0}}
.details{{border-top:1px solid var(--line);margin-top:12px;padding-top:12px}}
details summary{{cursor:pointer;font-weight:650}}
ul,ol{{padding-left:20px}}
li+li{{margin-top:5px}}
.command{{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:start;background:var(--code);border:1px solid var(--line);padding:9px;border-radius:8px;margin-top:7px}}
code{{font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}}
.command button{{padding:4px 7px;font-size:11px}}
.chain{{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-top:9px}}
.chain span{{font:11px ui-monospace,SFMono-Regular,Consolas,monospace;background:var(--soft);padding:4px 7px;border-radius:6px}}
.chain i{{color:var(--muted);font-style:normal}}
.goal{{margin-bottom:13px}}
.goal-head{{display:flex;justify-content:space-between;gap:12px;font-size:13px}}
.progress{{height:7px;background:var(--soft);border-radius:99px;overflow:hidden;margin-top:6px}}
.progress span{{display:block;height:100%;background:var(--accent);border-radius:99px}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}}
table{{width:100%;border-collapse:collapse;min-width:760px}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);position:sticky;top:0;background:var(--panel)}}
tr:last-child td{{border-bottom:0}}
.state{{font-weight:700}}
.state.unknown{{color:var(--muted)}}.state.declared{{color:var(--hold)}}.state.observed,.state.measured,.state.qualified,.state.accepted{{color:var(--good)}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}
.toolbar input,.toolbar select{{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px 10px}}
.toolbar input{{flex:1;min-width:210px}}
.side-card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px;margin-bottom:10px}}
.side-card h3{{font-size:14px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:8px}}
.kv{{display:grid;grid-template-columns:auto 1fr;gap:5px 10px;font-size:12px}}
.kv dt{{color:var(--muted)}}.kv dd{{margin:0;overflow-wrap:anywhere}}
.boundary{{font-size:12px;color:var(--muted)}}
.empty{{padding:18px;color:var(--muted);text-align:center}}
footer{{border-top:1px solid var(--line);margin-top:28px;padding:18px 0;color:var(--muted);font-size:12px}}
.sr-only{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
@media(max-width:900px){{.layout{{grid-template-columns:1fr}}aside{{position:static}}.summary{{grid-template-columns:repeat(2,1fr)}}header{{grid-template-columns:1fr}}.header-actions{{justify-content:flex-start}}}}
@media(max-width:540px){{.shell{{padding:15px}}.summary{{grid-template-columns:1fr 1fr}}.vector{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="shell">
<header>
  <div>
    <div class="eyebrow">AXM Community Home Lab</div>
    <h1>Capability Gradient</h1>
    <p class="lede">Turn the three-host CPU, RAM, storage, iGPU, and dGPU estate into a measured function fabric by taking the smallest reversible experiment that unlocks the next hard capability.</p>
  </div>
  <div class="header-actions">
    <label class="button" for="plan-import">Load plan JSON</label>
    <input class="sr-only" id="plan-import" type="file" accept="application/json,.json">
    <button id="theme-button" type="button">Toggle theme</button>
  </div>
</header>
<div id="summary" class="summary"></div>
<div class="layout">
<main>
  <section id="action-section">
    <div class="section-head"><div><h2>Action chain</h2><div class="subtle">The current Pareto-admissible work, ordered by the published tie-break.</div></div></div>
    <div id="action-chain"></div>
  </section>
  <section>
    <div class="section-head"><div><h2>Hard goals</h2><div class="subtle">Progress is per required capability. One strong dimension cannot cancel an absent one.</div></div></div>
    <div id="goals"></div>
  </section>
  <section>
    <div class="section-head"><div><h2>Capability ledger</h2><div class="subtle">Only named evidence support changes a capability tier.</div></div></div>
    <div class="table-wrap"><table><thead><tr><th>Capability</th><th>State</th><th>Required</th><th>Dependencies</th><th>Evidence</th></tr></thead><tbody id="capabilities"></tbody></table></div>
  </section>
  <section>
    <div class="section-head"><div><h2>Experiment floor</h2><div class="subtle">Search every bounded experiment, including blocked enabling chains.</div></div></div>
    <div class="toolbar"><input id="search" type="search" placeholder="Search experiment, capability, or class"><select id="status-filter"><option value="all">All statuses</option><option value="admissible">Admissible</option><option value="blocked">Blocked</option><option value="complete">Complete</option></select></div>
    <div id="experiments"></div>
  </section>
</main>
<aside>
  <div class="side-card"><h3>Estate seed</h3><dl id="estate" class="kv"></dl></div>
  <div class="side-card"><h3>Planning law</h3><div id="method" class="boundary"></div></div>
  <div class="side-card"><h3>Receipt boundary</h3><p id="boundary" class="boundary"></p></div>
  <div class="side-card"><h3>Control question</h3><p id="control-question"></p></div>
</aside>
</div>
<footer>This page makes no network request and carries no execution authority. Importing a plan changes only this browser projection. Authoritative evidence and receipts remain in the operator-selected state directory outside the source tree.</footer>
</div>
<script id="embedded-data" type="application/octet-stream">{payload}</script>
<script>
(async() => {{
  if (!("DecompressionStream" in window)) {{
    document.body.innerHTML='<div style="max-width:760px;margin:3rem auto;font:16px system-ui">This standalone page requires a current Chromium, Edge, Firefox, or Safari build with DecompressionStream support.</div>';
    return;
  }}
  const encoded=document.getElementById('embedded-data').textContent.trim();
  const compressed=Uint8Array.from(atob(encoded),character=>character.charCodeAt(0));
  const stream=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
  const embedded=JSON.parse(await new Response(stream).text());
  let plan=embedded.plan;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
  const pct=(a,b)=>b?Math.round(a/b*100):100;
  const fmt=n=>Number.isInteger(Number(n))?String(n):Number(n).toFixed(1);
  const copy=async text=>{{try{{await navigator.clipboard.writeText(text)}}catch(_e){{const t=document.createElement('textarea');t.value=text;document.body.append(t);t.select();document.execCommand('copy');t.remove()}}}};
  const badge=(text,kind='')=>`<span class="badge ${{kind}}">${{esc(text)}}</span>`;
  function costVector(cost){{return `<div class="vector">
    <div><b>${{fmt(cost.operator_minutes)}} min</b><span>operator</span></div>
    <div><b>${{fmt(cost.machine_minutes)}} min</b><span>machine</span></div>
    <div><b>${{fmt(cost.data_moved_gib)}} GiB</b><span>movement</span></div>
    <div><b>${{cost.new_packages}}</b><span>new packages</span></div>
    <div><b>${{cost.risk}}</b><span>risk class</span></div>
    <div><b>${{cost.irreversible}}</b><span>irreversible</span></div>
  </div>`}}
  function commands(rows){{return (rows||[]).map(command=>`<div class="command"><code>${{esc(command)}}</code><button data-copy="${{encodeURIComponent(command)}}">Copy</button></div>`).join('')}}
  function chain(items){{return `<div class="chain">${{(items||[]).map((item,i)=>`${{i?'<i>→</i>':''}}<span>${{esc(item)}}</span>`).join('')}}</div>`}}
  function experimentCard(item,hero=false){{
    const statusKind=item.status==='admissible'?'good':item.status==='blocked'?'hold':'';
    const why=`Closes ${{item.benefits.capability_count}} capability gap${{item.benefits.capability_count===1?'':'s'}}, touches ${{item.benefits.goal_count}} goal${{item.benefits.goal_count===1?'':'s'}}, and directly unlocks ${{item.benefits.unlock_count}} experiment${{item.benefits.unlock_count===1?'':'s'}}.`;
    return `<article class="card ${{hero?'hero-card':''}}" data-search="${{esc((item.id+' '+item.title+' '+item.class+' '+item.description).toLowerCase())}}" data-status="${{esc(item.status)}}">
      <div class="rank">${{item.rank?`Rank ${{item.rank}} · Pareto front ${{item.pareto_front}}`:`${{item.status}}`}}</div>
      <h3>${{esc(item.title)}}</h3>
      <div class="badges">${{badge(item.class)}}${{badge(item.status,statusKind)}}${{(item.produces||[]).map(p=>badge(`${{p.capability}} → ${{p.tier}}`)).join('')}}</div>
      <p class="description">${{esc(item.description)}}</p>
      ${{hero?`<div class="callout">${{esc(why)}}</div>`:''}}
      ${{costVector(item.cost)}}
      ${{item.missing?.length?`<div class="callout"><b>Blocked by:</b> ${{item.missing.map(x=>esc(`${{x.capability}} @ ${{x.tier}}`)).join(', ')}}${{chain(item.enabling_chain)}}</div>`:''}}
      <div class="details"><details ${{hero?'open':''}}><summary>Acceptance and execution</summary>
        <ol>${{(item.acceptance||[]).map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ol>
        ${{commands(item.commands)}}
      </details></div>
    </article>`;
  }}
  function render(nextPlan){{
    plan=nextPlan;
    if(plan.schema!=='axm-community-lab/capability-gradient-plan@1') throw new Error('Unsupported plan schema');
    const s=plan.summary;
    document.getElementById('summary').innerHTML=[
      [s.capabilities_satisfied+' / '+s.capability_count,'capabilities satisfied'],
      [s.experiments_admissible,'admissible now'],
      [s.experiments_blocked,'blocked experiments'],
      [s.goals_satisfied+' / '+s.goal_count,'hard goals satisfied']
    ].map(([n,l])=>`<div class="metric"><b>${{esc(n)}}</b><span>${{esc(l)}}</span></div>`).join('');
    document.getElementById('action-chain').innerHTML=plan.now.length?plan.now.map((x,i)=>experimentCard(x,i===0)).join(''):'<div class="empty">No experiment is currently admissible. Inspect the first blocked enabling chain.</div>';
    document.getElementById('goals').innerHTML=plan.goals.map(g=>`<div class="card goal"><div class="goal-head"><b>${{esc(g.title)}}</b><span>${{g.satisfied_count}} / ${{g.required_count}} · ${{esc(g.priority)}}</span></div><p class="description">${{esc(g.description)}}</p><div class="progress"><span style="width:${{pct(g.satisfied_count,g.required_count)}}%"></span></div><div class="badges">${{g.requirements.map(r=>badge(`${{r.capability}}: ${{r.state}}`,r.satisfied?'good':'hold')).join('')}}</div></div>`).join('');
    document.getElementById('capabilities').innerHTML=plan.capabilities.map(c=>`<tr><td><b>${{esc(c.title)}}</b><div class="subtle"><code>${{esc(c.id)}}</code></div></td><td><span class="state ${{esc(c.state)}}">${{esc(c.state)}}</span></td><td>${{esc(c.minimum_tier)}}</td><td>${{c.dependencies.length?c.dependencies.map(x=>`<code>${{esc(x)}}</code>`).join('<br>'):'none'}}</td><td>${{c.evidence_records.length?c.evidence_records.map(x=>`<code>${{esc(x)}}</code>`).join('<br>'):'none'}}</td></tr>`).join('');
    document.getElementById('experiments').innerHTML=plan.experiments.map(x=>experimentCard(x,false)).join('');
    const es=embedded.estate.summary;
    document.getElementById('estate').innerHTML=`<dt>Estate</dt><dd>${{esc(embedded.estate.label)}}</dd><dt>Hosts</dt><dd>${{esc(es.cpu_pools)}}</dd><dt>RAM pools</dt><dd>${{esc(es.ram_pools)}}</dd><dt>Accelerators</dt><dd>${{esc(es.igpu_count+es.dgpu_count)}} total</dd><dt>Discrete</dt><dd>${{es.dgpus.map(esc).join('<br>')}}</dd><dt>Plan</dt><dd><code>${{esc(plan.plan_sha256)}}</code></dd>`;
    document.getElementById('method').innerHTML=`<p>${{esc(plan.method.admission)}}</p><p>${{esc(plan.method.fronts)}}</p><p><b>Tie-break:</b> ${{plan.method.tie_break.map(esc).join('; ')}}.</p>`;
    document.getElementById('boundary').textContent=plan.claim_boundary;
    document.getElementById('control-question').textContent=plan.control_question;
    filter();
  }}
  function filter(){{
    const query=document.getElementById('search').value.trim().toLowerCase();
    const status=document.getElementById('status-filter').value;
    document.querySelectorAll('#experiments > article').forEach(card=>{{
      const matchText=!query||card.dataset.search.includes(query);
      const matchStatus=status==='all'||card.dataset.status===status;
      card.hidden=!(matchText&&matchStatus);
    }});
  }}
  document.addEventListener('click',event=>{{
    const button=event.target.closest('[data-copy]');
    if(button){{copy(decodeURIComponent(button.dataset.copy));const old=button.textContent;button.textContent='Copied';setTimeout(()=>button.textContent=old,900)}}
  }});
  document.getElementById('search').addEventListener('input',filter);
  document.getElementById('status-filter').addEventListener('change',filter);
  document.getElementById('theme-button').addEventListener('click',()=>{{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;localStorage.setItem('home-lab-gradient-theme',next)}});
  document.getElementById('plan-import').addEventListener('change',async event=>{{
    const file=event.target.files[0];if(!file)return;
    try{{const imported=JSON.parse(await file.text());render(imported)}}catch(error){{alert('Plan rejected: '+error.message)}}finally{{event.target.value=''}}
  }});
  render(plan);
}})();
</script>
</body>
</html>
'''


def write_page(path: Path, **kwargs: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_page(**kwargs), encoding="utf-8")
