(() => {
  'use strict';

  const scales = [
    {
      id:'plant', label:'Plant', kicker:'Origin object', code:'MW-PL-001', title:'One useful plant reveals the operating system.',
      body:'Fresh catnip joins household value, animal use, water, light, space, cost, care cadence, and memory in one small object.',
      need:'A repeatable growing method that fits the household’s real attention and space.',
      next:'Preserve the use case and test the smallest complete care loop.',
      authority:'The household decides whether the object belongs in its life.',
      caption:'The origin is deliberately small. The system begins where value is immediate and observable.',
      sceneClass:'Illustrative reference', sceneClaim:'Generated origin plate · household utility', scene:scenePlant
    },
    {
      id:'household', label:'Household', kicker:'Lived system', code:'MW-PL-002', title:'The yard is an inhabited operating environment.',
      body:'The place is used by people and animals for rest, movement, food, sensory relief, work, water, shade, and routine care.',
      need:'A view that begins with lived use and burden rather than ornamental category.',
      next:'Map the routines and conditions the place must support before proposing change.',
      authority:'Observation cannot override household consent or invent household capacity.',
      caption:'Household Habitat keeps meals, play, pets, plants, shade, water, access, tools, maintenance, and caregiver attention in the same record.',
      sceneClass:'Illustrative reference', sceneClaim:'Generated household plate · no surveyed geometry', scene:sceneHousehold
    },
    {
      id:'property', label:'Property', kicker:'Visible twin', code:'MW-PL-003', title:'Overlapping conditions stay independently inspectable.',
      body:'Shade, water, access, fuel, habitat, labor, structures, and authority occupy the same physical place without becoming one score.',
      need:'A source-bound property twin whose surfaces and uncertainties remain visible.',
      next:'Attach each claim to a visible edge or bounded zone and retain what is unknown.',
      authority:'A visual interpretation is not a survey, inspection, entry right, or work authorization.',
      caption:'The property twin carries the same place into a plan view so dependencies and natural borders can be inspected together.',
      sceneClass:'Modeled context', sceneClaim:'Reference geometry · not a legal parcel map', scene:sceneProperty
    },
    {
      id:'street', label:'Street', kicker:'Street Glide', code:'MW-PL-004', title:'The public edge is read through natural borders.',
      body:'Curb, canopy, roof, sidewalk, driveway, utility, parcel, and work edges divide responsibility while the street remains one inhabited scene.',
      need:'Registration that follows the visible landscape instead of floating geometry.',
      next:'Read the edge, retain uncertainty, then distinguish household, neighbor, and public responsibilities.',
      authority:'A street observation creates no access, enforcement, ownership, or maintenance authority.',
      caption:'Street Glide snaps analytical lines to the curb, canopy, roof, sidewalk, driveway, utility, and work edge.',
      sceneClass:'Operating illustration', sceneClaim:'Natural-border registration · illustrative street', scene:sceneStreet
    },
    {
      id:'neighborhood', label:'Neighborhood', kicker:'Shared capacity', code:'MW-PL-005', title:'Linked conditions meet unequal capacity.',
      body:'Adjacent households share heat, canopy, water, access, smoke, tools, nurseries, trusted relays, and labor without becoming interchangeable units.',
      need:'Coordination that offers resources before adding obligations.',
      next:'Route the specific capacity gap to the function able to help.',
      authority:'Neighborhood context cannot be converted into a household verdict or reputation score.',
      caption:'The neighborhood plate reveals shared effects and shared capacity while retaining household boundaries.',
      sceneClass:'Modeled context', sceneClaim:'Illustrative block · assistance routing only', scene:sceneNeighborhood
    },
    {
      id:'region', label:'Region', kicker:'Regional Observatory', code:'MW-PL-006', title:'Wide context remains separate from local determination.',
      body:'Heat, air, wildfire, water, access, supply, labor, terrain, and public programs shape many places differently and change over time.',
      need:'A context layer that keeps signal, verified finding, capacity, and completed mitigation separate.',
      next:'Use regional context to prioritize assistance and evidence collection.',
      authority:'No automatic insurance denial, unrelated scoring, or punitive reuse.',
      caption:'The Regional Observatory widens the record without manufacturing parcel certainty from broad signals.',
      sceneClass:'Modeled context', sceneClaim:'Regional relationships · no parcel determination', scene:sceneRegion
    },
    {
      id:'stewardship', label:'Stewardship', kicker:'Continuity', code:'MW-PL-007', title:'The work survives a change of hands.',
      body:'Evidence, rationale, authority, safe preparation, verification, held effects, and unresolved branches remain reconstructable after a role changes.',
      need:'Receipts, bounded decisions, and a cold successor path.',
      next:'Verify the result and export a trustworthy handoff.',
      authority:'External effects require real authority. Internal preparation does not require finding a person.',
      caption:'Manzanita Works and Essential Attention preserve why the condition mattered, what authority existed, what work occurred, and what remains safe.',
      sceneClass:'Operating receipt', sceneClaim:'Governed handoff · external effects held', scene:sceneStewardship
    }
  ];

  const overlays = [
    {id:'habitat', label:'Habitat', cls:'overlay-habitat'},
    {id:'shade', label:'Shade + heat', cls:'overlay-shade'},
    {id:'water', label:'Water', cls:'overlay-water'},
    {id:'fire', label:'Fire', cls:'overlay-fire'},
    {id:'air', label:'Air', cls:'overlay-air'},
    {id:'access', label:'Access', cls:'overlay-access'},
    {id:'labor', label:'Labor + tools', cls:'overlay-labor'},
    {id:'authority', label:'Authority + programs', cls:'overlay-authority'}
  ];

  const roles = [
    {id:'resident', code:'R-01', label:'Resident', body:'What supports daily life and what burden arrives with the work.', need:'Needs: use, consent, cost, care load, recourse.'},
    {id:'nursery', code:'R-02', label:'Nursery or grower', body:'What can be propagated, supplied, maintained, and replaced locally.', need:'Needs: demand, plant fit, timing, logistics, proof of survival.'},
    {id:'crew', code:'R-03', label:'Crew or steward', body:'What work is authorized, accessible, safe, and verifiable.', need:'Needs: scope, access, tools, dependencies, acceptance criteria.'},
    {id:'planner', code:'R-04', label:'Planner or program', body:'Where shared conditions justify resources without inventing parcel certainty.', need:'Needs: context, eligibility, purpose limits, affected interests.'},
    {id:'successor', code:'R-05', label:'Successor', body:'Why the current state exists and what remains safe to continue.', need:'Needs: sources, rationale, authority, receipts, open branches.'}
  ];

  const $ = (selector) => document.querySelector(selector);
  function defaultOverlayIds(scaleIndex){
    return scaleIndex < 2 ? ['habitat','shade'] : scaleIndex < 4 ? ['access','water'] : scaleIndex < 6 ? ['fire','labor'] : ['authority','access'];
  }
  const initialParams = new URLSearchParams(window.location.search);
  const requestedScale = scales.findIndex(s => s.id === initialParams.get('scale'));
  const requestedRole = roles.findIndex(r => r.id === initialParams.get('role'));
  const requestedLayers = initialParams.has('layers')
    ? (initialParams.get('layers') || '').split(',').filter(id => overlays.some(o => o.id === id))
    : null;
  const initialScale = requestedScale >= 0 ? requestedScale : 1;
  const state = {
    scale:initialScale,
    role:requestedRole >= 0 ? requestedRole : 0,
    overlays:new Set(requestedLayers === null ? defaultOverlayIds(initialScale) : requestedLayers)
  };

  function esc(text){ return String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function label(x,y,title,detail,anchor='start'){
    return `<text x="${x}" y="${y}" text-anchor="${anchor}" class="scene-label">${esc(title)}</text>${detail ? `<text x="${x}" y="${y+17}" text-anchor="${anchor}" class="scene-micro">${esc(detail)}</text>`:''}`;
  }

  function scenePlant(){
    return `
      <g data-scene="plant">
        <path d="M0 455H920" class="scene-ink"/>
        <rect x="315" y="244" width="290" height="208" class="scene-base"/>
        <path d="M295 244h330l-38 208H333Z" class="scene-muted"/>
        <path d="M350 244c30-55 64-93 110-132M414 244c4-82 21-135 58-188M488 244c22-74 54-120 97-157M548 244c-6-62-1-105 19-145" class="scene-ink"/>
        <path d="M345 175c35-24 68-22 97 5-30 31-61 34-97-5Zm77-72c31-30 66-33 105-8-21 37-55 43-105 8Zm79 61c31-31 70-33 112-7-26 40-64 42-112 7Zm33-86c29-25 60-26 91-2-25 31-54 31-91 2Z" class="scene-olive"/>
        <g transform="translate(610 374)"><path d="M0 35c3-22 18-34 40-31l9-19 12 20c22 8 30 25 24 48-16 13-51 13-78 2-5-6-7-12-7-20Zm82 13c25 3 40-8 48-31" class="svg-cat"/><circle cx="33" cy="24" r="2.5" class="svg-eye"/></g>
        <path d="M332 452 205 495H80" class="scene-signal" marker-end="url(#arrow)"/>
        ${label(78,484,'HOUSEHOLD USE','CAT · SCENT · PLAY')}
        <path d="M472 96V45H685" class="scene-signal"/>
        ${label(690,44,'CARE LOOP','LIGHT · WATER · RETURN')}
        <text x="63" y="96" class="scene-number">01</text>${label(63,127,'ORIGIN OBJECT','UTILITY BEFORE PREMIUM')}
      </g>`;
  }

  function sceneHousehold(){
    return `
      <g data-scene="household">
        <path d="M0 456c180-30 333-9 470-46s276-24 450-55v205H0Z" class="scene-muted"/>
        <path d="M170 257 382 128 657 272v216H170Z" class="scene-base"/>
        <path d="M148 275 380 106 686 279" class="scene-ink"/>
        <rect x="222" y="309" width="112" height="179" class="scene-muted"/>
        <rect x="422" y="296" width="155" height="110" class="scene-base"/>
        <path d="M435 311h130M435 339h130M435 367h130M477 296v110M522 296v110" class="scene-thin"/>
        <path d="M78 96c92-70 181-42 235 16 76-66 188-53 232 17 80-35 175 6 190 77-85 39-153 52-231 37-55 45-145 45-214 1-98 34-203 5-248-53 0-42 13-72 36-95Z" class="scene-olive"/>
        <path d="M337 223c-13 91-12 176 0 275M332 279c-57 27-92 66-118 114M339 313c58 29 92 65 122 111" class="scene-ink scene-stroke-15"/>
        <ellipse cx="722" cy="344" rx="58" ry="17" class="scene-base"/><rect x="664" y="344" width="116" height="135" class="scene-muted"/><path d="M669 367h106M669 391h106M669 415h106M669 439h106" class="scene-thin"/>
        <path d="M77 463c78-52 153-55 226-5-68 42-147 46-226 5Zm351 17c64-56 137-62 213-10-63 44-134 48-213 10Z" class="scene-base"/>
        <g transform="translate(518 441)"><path d="M0 35c3-22 18-34 40-31l9-19 12 20c22 8 30 25 24 48-16 13-51 13-78 2-5-6-7-12-7-20Zm82 13c25 3 40-8 48-31" class="svg-cat"/><circle cx="33" cy="24" r="2.5" class="svg-eye"/></g>
        <path d="M60 528H856" class="scene-thin"/>
        ${label(70,516,'LIVED SYSTEM','USE · SHADE · WATER · CARE')}
        ${label(849,516,'NO SINGLE SCORE','CONDITIONS REMAIN SEPARATE','end')}
      </g>`;
  }

  function sceneProperty(){
    return `
      <g data-scene="property">
        <path d="M108 64H792V494H108Z" class="scene-base"/>
        <path d="M108 64 792 494M792 64 108 494" class="scene-thin"/>
        <path d="M175 128H575V377H175Z" class="scene-muted"/>
        <path d="M217 165H519V337H217Z" class="scene-base"/>
        <rect x="264" y="208" width="88" height="129" class="scene-muted"/>
        <rect x="400" y="199" width="82" height="63" class="scene-base"/>
        <circle cx="646" cy="151" r="91" class="scene-olive"/>
        <circle cx="658" cy="384" r="58" class="scene-base"/>
        <path d="M646 242v152M575 292h126" class="scene-ink"/>
        <path d="M131 429H769" class="scene-signal"/>
        <path d="M158 81v395M593 81v395" class="scene-thin" stroke-dasharray="7 7"/>
        <path d="M135 452c180-39 358-9 630-34" class="scene-water"/>
        <path d="M170 106c68 27 119 25 182-7M418 105c47 23 92 21 143-6" class="scene-olive"/>
        <text x="127" y="94" class="scene-number">03</text>
        ${label(127,124,'VISIBLE TWIN','ZONES · EDGES · DEPENDENCIES')}
        ${label(731,472,'REFERENCE ONLY','NOT A SURVEY','end')}
        <path d="M644 151 823 94" class="scene-signal"/>${label(828,92,'CANOPY EDGE','VISIBLE · UNCERTAIN')}
        <path d="M658 384 826 365" class="scene-water"/>${label(831,364,'WATER STORE','CAPACITY OPEN')}
      </g>`;
  }

  function sceneStreet(){
    return `
      <g data-scene="street">
        <path d="M0 410H920V560H0Z" class="scene-muted"/>
        <path d="M0 444H920M0 493H920" class="scene-ink"/>
        <path d="M82 410V354H830V410" class="scene-thin"/>
        <path d="M132 354 302 229 505 352V410H132Z" class="scene-base"/>
        <path d="M111 366 300 207 528 358" class="scene-ink"/>
        <path d="M570 312h170v98H570Z" class="scene-base"/>
        <path d="M548 320 651 244 765 322" class="scene-ink"/>
        <path d="M54 188c80-64 166-43 217 6 67-59 169-53 216 12 74-36 166 4 177 71-76 35-137 49-211 35-58 42-145 41-203 0-95 31-191 6-231-47 0-32 12-57 35-77Z" class="scene-olive"/>
        <path d="M266 303v107" class="scene-ink scene-stroke-13"/>
        <path d="M0 443c181-17 312-8 459-19s299-3 461-15" class="scene-signal"/>
        <path d="M81 354c190-18 294-20 443 0" class="scene-signal"/>
        <path d="M520 353c102 9 198 10 310 1" class="scene-violet"/>
        <path d="M85 410c154-2 286 0 427 0" class="scene-water"/>
        <path d="M120 492 184 441 263 492M575 492l73-49 84 49" class="scene-thin"/>
        <text x="45" y="83" class="scene-number">04</text>${label(45,114,'NATURAL BORDER REGISTRATION','CURB · CANOPY · ROOF · WALK · UTILITY')}
        ${label(70,432,'CURB EDGE','PUBLIC EDGE')}${label(773,338,'UTILITY / WORK EDGE','AUTHORITY SEPARATE','end')}
      </g>`;
  }

  function sceneNeighborhood(){
    const parcels=[];
    for(let r=0;r<2;r++) for(let c=0;c<4;c++){
      const x=72+c*195,y=126+r*174;
      parcels.push(`<rect x="${x}" y="${y}" width="164" height="145" class="scene-base"/><path d="M${x+18} ${y+88} ${x+78} ${y+42} ${x+145} ${y+91}v38H${x+18}Z" class="scene-thin"/><circle cx="${x+42+(c%2)*78}" cy="${y+48}" r="25" class="scene-olive"/>`);
    }
    return `
      <g data-scene="neighborhood">
        ${parcels.join('')}
        <path d="M50 290H870M50 465H870" class="scene-ink"/>
        <path d="M120 90H790" class="scene-air"/>
        <path d="M92 488c214-55 445-32 730-2" class="scene-water"/>
        <circle cx="158" cy="302" r="10" class="scene-signal-fill"/><circle cx="458" cy="302" r="10" class="scene-signal-fill"/><circle cx="755" cy="302" r="10" class="scene-signal-fill"/>
        <path d="M158 302H458H755" class="scene-signal" marker-end="url(#arrow)"/>
        <path d="M458 302V88" class="scene-violet"/>
        ${label(458,72,'NURSERY · TOOLS · TRUSTED RELAY','SHARED CAPACITY','middle')}
        <text x="43" y="67" class="scene-number">05</text>${label(43,98,'NEIGHBORHOOD','LINKED CONDITIONS · UNEQUAL CAPACITY')}
      </g>`;
  }

  function sceneRegion(){
    return `
      <g data-scene="region">
        <path d="M0 112c128-73 240-34 329 13 112-103 250-80 345 5 92-56 170-33 246 17V0H0Z" class="scene-muted"/>
        <path d="M0 112c128-73 240-34 329 13 112-103 250-80 345 5 92-56 170-33 246 17M0 169c126-60 251-25 347 23 111-83 235-69 329 5 90-43 172-24 244 20M0 228c126-44 251-15 351 28 110-64 231-55 327 7 89-32 171-17 242 23" class="scene-ink"/>
        <path d="M0 354c154-56 303-22 456 4s296 42 464-20" class="scene-water"/>
        <path d="M35 300c162-50 338-21 485-42s267-14 365 16" class="scene-air"/>
        <path d="M170 95 282 445M434 100 522 462M704 106 652 469" class="scene-thin"/>
        <g class="region-nodes">
          <circle cx="185" cy="323" r="13" class="scene-signal-fill"/><circle cx="342" cy="285" r="11" class="scene-olive"/><circle cx="507" cy="345" r="13" class="scene-signal-fill"/><circle cx="695" cy="303" r="11" class="scene-olive"/><circle cx="802" cy="389" r="13" class="scene-signal-fill"/>
          <path d="M185 323 342 285 507 345 695 303 802 389" class="scene-signal"/>
        </g>
        <path d="M90 478H840" class="scene-ink"/><path d="M90 478v31M260 478v31M430 478v31M600 478v31M770 478v31" class="scene-ink"/>
        ${label(90,532,'HEAT')}${label(260,532,'AIR')}${label(430,532,'FIRE')}${label(600,532,'SUPPLY')}${label(770,532,'PROGRAMS')}
        <text x="42" y="66" class="scene-number">06</text>${label(42,97,'REGIONAL OBSERVATORY','CONTEXT WIDENS · CLAIM FORCE DOES NOT')}
      </g>`;
  }

  function sceneStewardship(){
    const nodes=[['SOURCE','RETAIN'],['MEANING','CLASSIFY'],['ATTENTION','ROUTE'],['AUTHORITY','BOUND'],['WORK','PREPARE'],['OUTCOME','VERIFY'],['HANDOFF','PRESERVE']];
    return `
      <g data-scene="stewardship">
        <path d="M70 278H850" class="scene-ink" marker-end="url(#arrow)"/>
        ${nodes.map((n,i)=>{const x=80+i*124;return `<g transform="translate(${x} 205)"><rect width="104" height="145" class="scene-base"/><text x="12" y="26" class="scene-number">0${i+1}</text><text x="12" y="82" class="scene-label">${n[0]}</text><text x="12" y="102" class="scene-micro">${n[1]}</text>${i===3?'<path d="M12 119h80" class="scene-signal"/>':''}</g>`}).join('')}
        <path d="M144 163V91H350M514 163V91H727" class="scene-thin"/>
        ${label(355,89,'ORIGINAL EVIDENCE','SOURCE FORCE RETAINED')}${label(733,89,'EXTERNAL EFFECT','HELD UNTIL AUTHORIZED')}
        <path d="M70 402H850" class="scene-thin"/><text x="70" y="439" class="scene-label">COLD SUCCESSOR TEST</text><text x="850" y="439" text-anchor="end" class="scene-label">PORTABLE PACKET</text>
        <text x="42" y="66" class="scene-number">07</text>${label(42,97,'CONTINUITY','THE RECORD SURVIVES THE ROLE')}
      </g>`;
  }

  const overlayGeometry = {
    plant:{habitat:['ellipse',460,180,190,90],shade:['path','M280 95c160-65 302-42 390 31'],water:['path','M250 448c170-56 305-38 442-6'],fire:['rect',296,226,326,229],air:['path','M130 130c190-40 392-41 650 4'],access:['path','M94 482H824'],labor:['rect',700,320,120,136],authority:['rect',284,213,350,250]},
    household:{habitat:['ellipse',360,185,286,128],shade:['path','M56 116c210-86 426-57 690 64'],water:['path','M82 488c215-54 433-35 700-10'],fire:['rect',142,104,651,397],air:['path','M57 92c233-47 479-36 768 33'],access:['path','M60 514H847'],labor:['rect',430,415,240,95],authority:['rect',157,117,649,384]},
    property:{habitat:['ellipse',650,160,112,112],shade:['ellipse',650,160,155,132],water:['path','M125 460c214-47 423-23 652-38'],fire:['rect',105,61,690,438],air:['path','M132 112c183-49 403-30 640 10'],access:['path','M125 430H770'],labor:['rect',570,315,175,150],authority:['rect',105,61,690,438]},
    street:{habitat:['path','M42 205c175-90 373-61 646 49'],shade:['path','M30 242c214-56 427-34 665 31'],water:['path','M80 410c172-11 314-5 444 0'],fire:['rect',104,196,682,226],air:['path','M52 126c201-44 475-35 794 34'],access:['path','M0 444H920'],labor:['rect',533,302,272,117],authority:['path','M81 354H831']},
    neighborhood:{habitat:['path','M72 128c218-55 441-48 750 3'],shade:['path','M58 179c240-35 489-31 806 11'],water:['path','M92 488c214-55 445-32 730-2'],fire:['rect',53,119,814,355],air:['path','M120 90H790'],access:['path','M50 290H870'],labor:['path','M158 302H755'],authority:['rect',52,119,815,355]},
    region:{habitat:['path','M43 250c181-79 382-60 598-21s184 12 235 0'],shade:['path','M0 228c126-44 251-15 351 28 110-64 231-55 327 7 89-32 171-17 242 23'],water:['path','M0 354c154-56 303-22 456 4s296 42 464-20'],fire:['path','M117 142 240 450M420 118 535 469M713 133 650 468'],air:['path','M35 300c162-50 338-21 485-42s267-14 365 16'],access:['path','M90 478H840'],labor:['path','M185 323 342 285 507 345 695 303 802 389'],authority:['rect',74,78,780,400]},
    stewardship:{habitat:['rect',63,188,798,180],shade:['path','M70 386H850'],water:['path','M68 414H851'],fire:['rect',428,192,112,168],air:['path','M70 156H850'],access:['path','M70 278H850'],labor:['rect',550,188,238,180],authority:['rect',426,187,116,177]}
  };

  function overlaySvg(scaleId, item, index){
    const g=(overlayGeometry[scaleId]||overlayGeometry.household)[item.id];
    if(!g) return '';
    const cls=`overlay-shape ${item.cls}`;
    let shape='';
    if(g[0]==='ellipse') shape=`<ellipse cx="${g[1]}" cy="${g[2]}" rx="${g[3]}" ry="${g[4]}" class="${cls}"/>`;
    if(g[0]==='rect') shape=`<rect x="${g[1]}" y="${g[2]}" width="${g[3]}" height="${g[4]}" class="${cls}"/>`;
    if(g[0]==='path') shape=`<path d="${g[1]}" class="${cls}"/>`;
    const y=24+index*24;
    return `<g data-overlay="${item.id}">${shape}<rect x="700" y="${y-13}" width="190" height="19" class="svg-panel"/><text x="710" y="${y}" class="overlay-label" fill="currentColor">${esc(item.label)}</text></g>`;
  }

  function buildControls(){
    $('#scaleRail').innerHTML=scales.map((s,i)=>`<button type="button" data-scale="${i}" aria-pressed="${i===state.scale}">${esc(s.label)}</button>`).join('');
    $('#overlayRail').innerHTML=overlays.map(o=>`<button type="button" data-overlay-button="${o.id}" aria-pressed="${state.overlays.has(o.id)}">${esc(o.label)}</button>`).join('');
    $('#roleRail').innerHTML=roles.map((r,i)=>`<button type="button" data-role="${i}" aria-pressed="${i===state.role}">${esc(r.label)}</button>`).join('');
  }

  function renderScale(){
    const s=scales[state.scale];
    document.querySelectorAll('[data-scale]').forEach((b,i)=>b.setAttribute('aria-pressed',String(i===state.scale)));
    $('#visualKicker').textContent=s.kicker; $('#visualCode').textContent=s.code;
    $('#visualTitle').textContent=s.label; $('#visualDescription').textContent=s.caption;
    $('#scaleTitle').textContent=s.title; $('#scaleBody').textContent=s.body; $('#scaleNeed').textContent=s.need; $('#scaleNext').textContent=s.next; $('#scaleAuthority').textContent=s.authority;
    $('#sceneCaption').textContent=s.caption; $('#sceneClass').textContent=s.sceneClass; $('#sceneClaim').textContent=s.sceneClaim;
    $('#scaleScene').innerHTML=s.scene();
    renderOverlays();
  }

  function renderOverlays(){
    const s=scales[state.scale];
    const active=overlays.filter(o=>state.overlays.has(o.id));
    $('#overlayScene').innerHTML=active.map((o,i)=>overlaySvg(s.id,o,i)).join('');
    document.querySelectorAll('[data-overlay-button]').forEach(b=>b.setAttribute('aria-pressed',String(state.overlays.has(b.dataset.overlayButton))));
  }

  function renderRole(){
    const r=roles[state.role];
    document.querySelectorAll('[data-role]').forEach((b,i)=>b.setAttribute('aria-pressed',String(i===state.role)));
    $('#roleCode').textContent=r.code; $('#roleTitle').textContent=r.label; $('#roleBody').textContent=r.body; $('#roleNeed').textContent=r.need;
  }

  function announce(message){
    const region=$('#interactionStatus');
    if(!region)return;
    region.textContent=message;
  }

  function syncUrl(){
    const url=new URL(window.location.href);
    url.searchParams.set('scale',scales[state.scale].id);
    url.searchParams.set('role',roles[state.role].id);
    const active=overlays.filter(o=>state.overlays.has(o.id)).map(o=>o.id);
    url.searchParams.set('layers',active.join(','));
    const query=url.searchParams.toString();
    window.history.replaceState(null,'',`${url.pathname}${query?`?${query}`:''}${url.hash}`);
  }

  function selectScale(index,{resetLayers=true,announceChange=true}={}){
    const numeric=Number(index);
    state.scale=((numeric%scales.length)+scales.length)%scales.length;
    if(resetLayers)state.overlays=new Set(defaultOverlayIds(state.scale));
    renderScale();
    syncUrl();
    if(announceChange)announce(`${scales[state.scale].label} scale selected. ${scales[state.scale].title}`);
  }

  function selectRole(index,{announceChange=true}={}){
    const numeric=Number(index);
    state.role=((numeric%roles.length)+roles.length)%roles.length;
    renderRole();
    syncUrl();
    if(announceChange)announce(`${roles[state.role].label} perspective selected.`);
  }

  function toggleOverlay(id){
    const item=overlays.find(o=>o.id===id);
    if(!item)return;
    const willShow=!state.overlays.has(id);
    willShow?state.overlays.add(id):state.overlays.delete(id);
    renderOverlays();
    syncUrl();
    announce(`${item.label} condition ${willShow?'shown':'hidden'}.`);
  }

  function bindArrowNavigation(container,selector,activate){
    container.addEventListener('keydown',event=>{
      if(!['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(event.key))return;
      const buttons=[...container.querySelectorAll(selector)];
      const current=buttons.indexOf(event.target.closest(selector));
      if(current<0)return;
      event.preventDefault();
      let next=current;
      if(event.key==='Home')next=0;
      else if(event.key==='End')next=buttons.length-1;
      else if(event.key==='ArrowRight'||event.key==='ArrowDown')next=(current+1)%buttons.length;
      else next=(current-1+buttons.length)%buttons.length;
      buttons[next].focus();
      if(activate)activate(buttons[next]);
    });
  }

  function updateThemeControl(){
    const dark=document.documentElement.dataset.theme==='dark';
    $('#themeToggle').setAttribute('aria-pressed',String(dark));
    $('#themeToggle').setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode');
    $('#themeLabel').textContent=dark?'Light':'Dark';
    document.querySelector('meta[name="theme-color"]').setAttribute('content',dark?'#11110f':'#f4f0e8');
  }

  buildControls(); renderScale(); renderRole(); updateThemeControl();

  $('#scaleRail').addEventListener('click',e=>{const b=e.target.closest('[data-scale]');if(!b)return;selectScale(Number(b.dataset.scale));});
  $('#overlayRail').addEventListener('click',e=>{const b=e.target.closest('[data-overlay-button]');if(!b)return;toggleOverlay(b.dataset.overlayButton);});
  $('#roleRail').addEventListener('click',e=>{const b=e.target.closest('[data-role]');if(!b)return;selectRole(Number(b.dataset.role));});
  $('#nextScale').addEventListener('click',()=>{selectScale(state.scale+1);$('#place').scrollIntoView({block:'start'});});
  $('#printSheet').addEventListener('click',()=>window.print());
  $('#themeToggle').addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;localStorage.setItem('manzanita-theme',next);updateThemeControl();});

  bindArrowNavigation($('#scaleRail'),'[data-scale]',button=>selectScale(Number(button.dataset.scale)));
  bindArrowNavigation($('#roleRail'),'[data-role]',button=>selectRole(Number(button.dataset.role)));
  bindArrowNavigation($('#overlayRail'),'[data-overlay-button]',null);
})();
