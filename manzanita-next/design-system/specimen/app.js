(() => {
  "use strict";

  const root = document.documentElement;
  const THEME_KEY = "m99-theme";
  const THEMES = new Set(["auto", "light", "dark"]);

  const APERTURES = Object.freeze({
    plant: {
      label: "PLANT APERTURE",
      title: "Plant aperture authored field",
      description: "An authored plant-scale field with a catnip bowl, care edge, household branch, and registered habitat overlay.",
      geometry: "M99-AUTH-PLANT-001",
      field: "M64 562 C145 509 172 430 240 391 C319 347 372 370 430 309 C486 250 533 172 628 142 C735 108 814 167 886 139 C969 107 1043 55 1144 91 L1164 612 C1012 646 868 627 730 648 C564 672 403 636 245 664 C164 676 96 636 64 562 Z",
      ground: "M64 562 C145 509 172 430 240 391 C319 347 372 370 430 309 C486 250 533 172 628 142 C735 108 814 167 886 139 C969 107 1043 55 1144 91",
      terrain: "M25 615 C162 520 214 496 306 430 C404 360 468 299 565 250 C675 194 772 231 884 185 C995 139 1087 107 1195 124 L1195 700 L25 700 Z",
      contourOne: "M47 535 C161 469 212 391 321 365 C431 339 484 235 611 204 C756 169 833 222 959 169 C1054 129 1113 111 1174 126",
      contourTwo: "M20 606 C160 550 242 501 336 453 C446 397 548 329 664 300 C785 270 885 300 1007 254 C1075 229 1134 219 1190 230",
      register: "M165 568 C272 477 354 420 462 357 C574 292 676 256 789 243 C906 229 1009 185 1102 133",
      branchPrimary: "M427 311 C485 324 521 358 566 414",
      branchSecondary: "M503 346 C571 342 620 318 668 279",
      authorityCut: "M552 392 l28 43",
      nodes: {
        observed: [414, 298],
        authored: [655, 266],
        unknown: [554, 402],
      },
      reading: "The plant aperture reads one catnip bowl as a living object with touch, moisture, pet use, and a household care decision.",
      transform: "Aperture-specific authored plant path set; no source registration claim",
      coverage: "Complete for the demonstrator plant only",
      uncertainty: "Does not describe a real plant, sensor, or care event",
      boundary: "No horticultural diagnosis, inspection, or completed care claim",
      branchLabel: "Water only after touch check",
      cutLabel: "HOUSEHOLD ACCEPTANCE",
    },
    household: {
      label: "HOUSEHOLD APERTURE",
      title: "Household aperture authored field",
      description: "An authored household-scale field showing the plant, patio use, shade, drainage, pet access, and a bounded steward handoff.",
      geometry: "M99-AUTH-HOUSEHOLD-001",
      field: "M58 574 C112 513 166 475 212 401 C264 317 340 269 427 246 C501 226 566 180 638 121 C713 61 816 76 892 134 C973 196 1044 184 1143 132 L1170 614 C1060 649 944 630 832 655 C702 683 573 627 458 650 C336 675 233 626 129 651 C91 641 70 614 58 574 Z",
      ground: "M58 574 C112 513 166 475 212 401 C264 317 340 269 427 246 C501 226 566 180 638 121 C713 61 816 76 892 134 C973 196 1044 184 1143 132",
      terrain: "M18 644 C122 575 212 542 283 459 C362 368 458 330 553 283 C649 236 727 157 827 159 C936 161 1024 231 1192 178 L1192 700 L18 700 Z",
      contourOne: "M39 548 C147 493 192 415 283 357 C372 300 472 293 556 234 C641 174 722 98 827 118 C927 137 1002 207 1164 151",
      contourTwo: "M16 618 C129 579 236 521 321 468 C409 413 508 380 594 329 C696 268 769 221 866 224 C966 226 1057 251 1190 209",
      register: "M126 600 C204 512 274 426 372 360 C467 295 575 273 662 190 C748 108 852 106 935 170 C1001 221 1073 218 1138 182",
      branchPrimary: "M425 248 C479 285 512 332 548 393",
      branchSecondary: "M510 309 C594 321 657 306 721 255",
      authorityCut: "M532 371 l33 48",
      nodes: {
        observed: [413, 235],
        authored: [708, 242],
        unknown: [537, 381],
      },
      reading: "The household aperture adds lived use, shade, drainage, pet access, tools, and the resident-to-steward acceptance boundary.",
      transform: "Aperture-specific authored household path set; plant anchor retained",
      coverage: "Household demonstrator field only; no parcel boundary",
      uncertainty: "No real resident, address, site condition, or private record",
      boundary: "No entry, inspection, scheduling, or household scoring authority",
      branchLabel: "Verify shade and drainage together",
      cutLabel: "STEWARD HANDOFF",
    },
    street: {
      label: "STREET APERTURE",
      title: "Street aperture authored field",
      description: "An authored street-scale corridor with irregular curb, canopy, access, water flow, and a map-only coverage break.",
      geometry: "M99-AUTH-STREET-001",
      field: "M30 532 C113 494 178 501 258 461 C347 416 409 334 503 314 C590 296 662 348 747 327 C841 305 893 219 983 196 C1055 178 1113 196 1180 151 L1180 642 C1067 626 960 658 846 636 C731 615 646 653 530 627 C420 603 336 645 226 625 C143 610 80 582 30 532 Z",
      ground: "M30 532 C113 494 178 501 258 461 C347 416 409 334 503 314 C590 296 662 348 747 327 C841 305 893 219 983 196 C1055 178 1113 196 1180 151",
      terrain: "M0 607 C118 581 208 548 304 507 C419 459 504 402 616 398 C732 394 817 426 929 377 C1032 332 1092 302 1200 270 L1200 700 L0 700 Z",
      contourOne: "M17 501 C129 466 211 471 304 418 C399 364 457 290 552 280 C654 269 715 325 813 291 C907 258 950 186 1034 168 C1097 154 1144 166 1193 138",
      contourTwo: "M0 579 C112 553 219 530 315 484 C421 433 526 386 623 384 C741 381 824 411 932 366 C1021 329 1102 312 1200 283",
      register: "M82 557 C190 520 285 476 371 418 C462 357 552 330 644 341 C746 353 827 336 911 276 C1003 211 1086 200 1152 173",
      branchPrimary: "M503 314 C554 354 596 401 635 455",
      branchSecondary: "M603 395 C694 391 763 367 834 318",
      authorityCut: "M616 434 l34 46",
      nodes: {
        observed: [491, 301],
        authored: [821, 305],
        unknown: [624, 443],
      },
      reading: "The street aperture widens to curb, canopy, access, drainage, neighboring obligations, and the point where imagery coverage stops.",
      transform: "Aperture-specific authored street corridor; no provider panorama attached",
      coverage: "Map-and-design demonstrator with an explicit street-imagery gap",
      uncertainty: "Current curb, canopy, obstruction, and visibility remain unknown",
      boundary: "No street inspection, work order, access finding, or property consequence",
      branchLabel: "Request authorized street capture",
      cutLabel: "COVERAGE STOPS",
    },
    region: {
      label: "REGION APERTURE",
      title: "Region aperture authored field",
      description: "An authored regional basin showing connected heat, water, fire, habitat, service, and authority fields without collapsing them into one score.",
      geometry: "M99-AUTH-REGION-001",
      field: "M18 576 C91 516 139 441 223 404 C315 363 375 292 465 244 C548 201 636 205 718 151 C805 94 900 53 995 92 C1076 126 1129 97 1186 66 L1191 629 C1088 667 979 632 880 655 C762 682 654 634 548 662 C423 695 319 636 211 660 C126 678 58 642 18 576 Z",
      ground: "M18 576 C91 516 139 441 223 404 C315 363 375 292 465 244 C548 201 636 205 718 151 C805 94 900 53 995 92 C1076 126 1129 97 1186 66",
      terrain: "M0 646 C92 579 167 532 255 484 C352 431 443 377 542 341 C660 298 755 270 865 221 C973 174 1087 141 1200 120 L1200 700 L0 700 Z",
      contourOne: "M20 540 C105 480 165 411 255 376 C349 339 418 267 514 227 C607 189 679 198 774 130 C873 59 958 54 1039 93 C1103 124 1146 91 1193 64",
      contourTwo: "M2 608 C99 562 190 515 278 472 C382 421 477 378 575 343 C682 305 789 286 892 232 C1000 176 1100 165 1198 139",
      register: "M73 590 C171 505 255 434 354 380 C463 320 563 292 666 243 C772 193 857 121 957 116 C1046 111 1114 106 1170 82",
      branchPrimary: "M465 244 C533 296 585 352 640 424",
      branchSecondary: "M577 346 C678 344 768 303 850 238",
      authorityCut: "M622 400 l38 51",
      nodes: {
        observed: [453, 231],
        authored: [837, 225],
        unknown: [629, 412],
      },
      reading: "The region aperture relates heat, water, fire, habitat, access, crews, programs, and trusted relays without producing one punitive parcel score.",
      transform: "Aperture-specific authored regional basin; no live regional feed attached",
      coverage: "Regional design demonstrator only; provider and jurisdiction coverage untested",
      uncertainty: "No current incident, forecast, resource availability, or program eligibility",
      boundary: "No insurance, enforcement, eligibility, funding, or regional operations decision",
      branchLabel: "Route hotspots to assistance triage",
      cutLabel: "HUMAN AUTHORITY",
    },
  });

  const OVERLAYS = Object.freeze({
    habitat: {
      label: "HABITAT · AUTHORED",
      reading: "Habitat overlay: living access, canopy relation, and care edge, authored for design demonstration.",
      symbol: "state-authored",
      paths: {
        plant: "M180 536 C263 476 344 421 429 368 C514 316 589 248 681 229 C763 212 828 244 905 219 C936 273 911 330 854 359 C778 397 678 363 601 405 C516 451 440 523 347 552 C285 572 225 565 180 536 Z",
        household: "M147 547 C215 490 280 420 364 372 C450 323 530 307 611 249 C692 191 771 137 853 164 C930 190 967 247 939 305 C900 385 804 389 720 407 C615 429 532 489 438 532 C338 579 231 585 147 547 Z",
        street: "M114 544 C226 505 313 447 407 408 C505 367 600 374 698 356 C805 337 882 270 976 236 C1041 213 1096 220 1135 247 C1089 327 997 365 907 394 C817 423 729 449 630 466 C516 486 405 553 291 574 C221 587 160 571 114 544 Z",
        region: "M95 557 C184 502 268 438 362 393 C456 347 551 319 644 270 C748 215 824 147 920 130 C1002 115 1066 136 1110 178 C1068 253 983 304 891 343 C788 387 685 415 590 462 C488 512 383 569 273 589 C198 603 133 586 95 557 Z",
      },
    },
    heat: {
      label: "HEAT · AUTHORED",
      reading: "Heat overlay: exposure and shade-transition field, authored without a current weather or surface-temperature claim.",
      symbol: "state-authored",
      paths: {
        plant: "M317 493 C363 414 406 337 468 277 C536 212 621 167 710 176 C784 184 840 229 853 292 C867 362 811 416 742 443 C668 471 594 450 521 485 C446 522 370 538 317 493 Z",
        household: "M269 521 C303 426 362 344 445 291 C520 243 602 209 686 160 C766 113 842 109 898 160 C954 212 947 295 898 352 C847 411 765 424 685 451 C581 486 486 551 385 558 C333 562 293 548 269 521 Z",
        street: "M327 510 C389 434 454 380 539 347 C630 311 721 338 809 309 C903 279 962 210 1038 188 C1096 171 1135 184 1152 219 C1114 303 1018 347 927 382 C835 418 750 451 645 469 C539 487 428 563 327 510 Z",
        region: "M399 518 C430 414 494 338 590 291 C692 241 771 163 872 118 C967 76 1054 92 1096 154 C1134 211 1098 282 1026 330 C951 379 853 393 768 431 C665 477 571 552 470 560 C435 562 412 545 399 518 Z",
      },
    },
    water: {
      label: "WATER · AUTHORED",
      reading: "Water overlay: drainage, flow, and shared-catchment relation, authored without a live meter or hydrologic claim.",
      symbol: "state-authored",
      paths: {
        plant: "M132 556 C240 527 305 455 376 392 C455 321 527 292 593 241 C659 190 717 181 752 214 C786 247 765 301 716 346 C648 408 571 433 493 480 C408 531 318 590 224 594 C183 596 150 582 132 556 Z",
        household: "M94 580 C185 535 250 468 319 405 C392 337 467 305 546 263 C626 220 681 167 730 181 C781 195 789 251 753 304 C706 373 623 410 546 453 C454 504 364 575 263 607 C195 629 126 615 94 580 Z",
        street: "M48 570 C146 549 243 512 331 468 C424 422 489 365 572 350 C653 335 705 379 771 371 C849 361 911 303 974 281 C1031 260 1078 270 1095 306 C1057 371 978 411 898 440 C811 472 720 483 625 500 C513 520 420 582 311 608 C206 633 102 618 48 570 Z",
        region: "M40 592 C140 555 236 500 326 451 C423 398 518 373 604 323 C696 270 763 197 843 168 C923 139 992 166 1004 221 C1017 278 960 335 895 373 C815 420 720 438 635 482 C532 535 439 605 330 624 C223 644 104 636 40 592 Z",
      },
    },
    fire: {
      label: "FIRE · AUTHORED",
      reading: "Fire overlay: attention and assistance-routing field, authored without an active-incident, parcel-risk, or insurance claim.",
      symbol: "state-authored",
      paths: {
        plant: "M546 457 C569 381 611 312 671 264 C730 216 801 193 866 219 C924 242 949 301 926 355 C899 418 824 449 758 466 C682 485 606 499 546 457 Z",
        household: "M573 469 C594 382 643 304 713 250 C785 194 866 170 935 208 C1002 245 1018 324 976 389 C929 461 831 476 747 498 C678 516 616 510 573 469 Z",
        street: "M623 489 C650 409 702 352 772 312 C850 268 927 207 1008 198 C1074 190 1127 219 1145 267 C1112 344 1028 398 945 429 C858 461 758 517 672 527 C647 530 631 515 623 489 Z",
        region: "M649 500 C683 401 741 327 821 272 C907 213 980 131 1068 119 C1124 111 1165 137 1181 179 C1159 276 1064 351 977 396 C884 444 789 509 698 539 C675 547 655 532 649 500 Z",
      },
    },
  });

  const ACTORS = Object.freeze({
    resident: {
      title: "Resident aperture",
      evidence: "Touch check, bowl moisture, lived use, pet access, and care history.",
      action: "Act within household care authority and record the next observable condition.",
      authority: "May care for the household object; may not infer street, regional, inspection, or adverse condition.",
      acceptance: "The intended household outcome is observable and the next check or handoff is retained.",
      handoff: "Escalate persistent uncertainty with photos, care history, and a bounded request to the steward.",
    },
    steward: {
      title: "Steward aperture",
      evidence: "Resident record, authored geometry, tool constraints, site-verification needs, and unresolved coverage gaps.",
      action: "Prepare a bounded verification plan before proposing labor, equipment, or material change.",
      authority: "May assess and plan within granted site authority; may not claim inspection, entry, completion, or resident consent without receipts.",
      acceptance: "Work scope, hazards, tools, source limits, resident acceptance, and completion evidence are explicit.",
      handoff: "Return an evidence-backed offer or hold to the resident and route cross-property obligations to the planner.",
    },
    planner: {
      title: "Planner aperture",
      evidence: "Aggregated public context, source health, service coverage, assistance programs, field holds, and jurisdictional authority.",
      action: "Route verified needs toward assistance, coordination, or accountable human review without one punitive score.",
      authority: "May coordinate within lawful program authority; may not infer parcel guilt, insurance action, enforcement, eligibility, or completed remediation.",
      acceptance: "The actor, source, authority, offer, decision, execution, and follow-through remain traceable across the region-to-household handoff.",
      handoff: "Return a bounded program offer or explicit hold to the steward and resident with appeal, refusal, and next-review paths.",
    },
  });

  const elements = {
    fieldFrame: document.querySelector(".field-frame"),
    fieldTitle: document.getElementById("field-title"),
    fieldDesc: document.getElementById("field-desc"),
    clipPath: document.getElementById("clip-path"),
    fieldFill: document.getElementById("field-fill"),
    terrain: document.getElementById("terrain-band"),
    contourOne: document.getElementById("contour-one"),
    contourTwo: document.getElementById("contour-two"),
    registerLine: document.getElementById("register-line"),
    overlayArea: document.getElementById("overlay-area"),
    ground: document.getElementById("ground-contour"),
    branchPrimary: document.getElementById("branch-primary"),
    branchSecondary: document.getElementById("branch-secondary"),
    authorityCut: document.getElementById("authority-cut"),
    nodeObserved: document.getElementById("node-observed"),
    nodeAuthored: document.getElementById("node-authored"),
    nodeUnknown: document.getElementById("node-unknown"),
    nodeAuthorStroke: document.querySelector(".node-author-stroke"),
    apertureLabel: document.getElementById("aperture-label"),
    geometryLabel: document.getElementById("geometry-label"),
    overlayLabel: document.getElementById("overlay-label"),
    branchLabel: document.getElementById("branch-label"),
    cutLabel: document.getElementById("cut-label"),
    apertureReading: document.getElementById("aperture-reading"),
    overlayReading: document.getElementById("overlay-reading"),
    sourceClass: document.getElementById("source-class"),
    sourceGeometry: document.getElementById("source-geometry"),
    sourceTransform: document.getElementById("source-transform"),
    sourceCoverage: document.getElementById("source-coverage"),
    sourceUncertainty: document.getElementById("source-uncertainty"),
    sourceBoundary: document.getElementById("source-boundary"),
    actorTitle: document.getElementById("actor-title"),
    actorEvidence: document.getElementById("actor-evidence"),
    actorAction: document.getElementById("actor-action"),
    actorAuthority: document.getElementById("actor-authority"),
    actorAcceptance: document.getElementById("actor-acceptance"),
    actorHandoff: document.getElementById("actor-handoff"),
  };

  const state = {
    aperture: "plant",
    overlay: "habitat",
    actor: "resident",
    theme: "auto",
  };

  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  function safeReadTheme() {
    try {
      const stored = window.localStorage.getItem(THEME_KEY);
      return THEMES.has(stored) ? stored : "auto";
    } catch (_error) {
      return "auto";
    }
  }

  function safeStoreTheme(theme) {
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch (_error) {
      // The theme still applies for the current session when storage is unavailable.
    }
  }

  function resolvedTheme(theme) {
    if (theme === "auto") {
      return systemDark.matches ? "dark" : "light";
    }
    return theme;
  }

  function updatePressed(selector, attribute, value) {
    document.querySelectorAll(selector).forEach((button) => {
      const selected = button.dataset[attribute] === value;
      button.setAttribute("aria-pressed", String(selected));
    });
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
      safeStoreTheme(theme);
    }
    announceState("theme");
  }

  function setNodePosition(node, position) {
    node.setAttribute("x", String(position[0]));
    node.setAttribute("y", String(position[1]));
  }

  function updateAuthorStroke(position) {
    const [x, y] = position;
    elements.nodeAuthorStroke.setAttribute("d", `M${x + 3} ${y + 20} l18 -16`);
  }

  function applyAperture(apertureId) {
    const aperture = APERTURES[apertureId];
    if (!aperture) {
      return;
    }
    state.aperture = apertureId;
    root.dataset.aperture = apertureId;
    updatePressed("[data-aperture-choice]", "apertureChoice", apertureId);

    elements.fieldTitle.textContent = aperture.title;
    elements.fieldDesc.textContent = aperture.description;
    elements.fieldFrame.setAttribute("aria-label", aperture.title);
    elements.clipPath.setAttribute("d", aperture.field);
    elements.fieldFill.setAttribute("d", aperture.field);
    elements.terrain.setAttribute("d", aperture.terrain);
    elements.contourOne.setAttribute("d", aperture.contourOne);
    elements.contourTwo.setAttribute("d", aperture.contourTwo);
    elements.registerLine.setAttribute("d", aperture.register);
    elements.ground.setAttribute("d", aperture.ground);
    elements.branchPrimary.setAttribute("d", aperture.branchPrimary);
    elements.branchSecondary.setAttribute("d", aperture.branchSecondary);
    elements.authorityCut.setAttribute("d", aperture.authorityCut);
    setNodePosition(elements.nodeObserved, aperture.nodes.observed);
    setNodePosition(elements.nodeAuthored, aperture.nodes.authored);
    setNodePosition(elements.nodeUnknown, aperture.nodes.unknown);
    updateAuthorStroke(aperture.nodes.authored);

    elements.apertureLabel.textContent = aperture.label;
    elements.geometryLabel.textContent = `geometry ${aperture.geometry}`;
    elements.apertureReading.textContent = aperture.reading;
    elements.sourceClass.textContent = "Authored demonstration";
    elements.sourceGeometry.textContent = aperture.geometry;
    elements.sourceTransform.textContent = aperture.transform;
    elements.sourceCoverage.textContent = aperture.coverage;
    elements.sourceUncertainty.textContent = aperture.uncertainty;
    elements.sourceBoundary.textContent = aperture.boundary;
    elements.branchLabel.textContent = aperture.branchLabel;
    elements.cutLabel.textContent = aperture.cutLabel;

    applyOverlay(state.overlay, false);
    announceState("aperture");
  }

  function applyOverlay(overlayId, announce = true) {
    const overlay = OVERLAYS[overlayId];
    if (!overlay) {
      return;
    }
    state.overlay = overlayId;
    root.dataset.overlay = overlayId;
    updatePressed("[data-overlay-choice]", "overlayChoice", overlayId);
    elements.overlayArea.setAttribute("d", overlay.paths[state.aperture]);
    elements.overlayArea.setAttribute("class", `overlay-area ${overlayId}`);
    elements.overlayLabel.textContent = overlay.label;
    elements.overlayLabel.setAttribute("class", `svg-label overlay-label ${overlayId}`);
    elements.overlayReading.innerHTML = `<span class="state-symbol ${overlay.symbol}" aria-hidden="true"></span>${overlay.reading}`;
    if (announce) {
      announceState("overlay");
    }
  }

  function applyActor(actorId) {
    const actor = ACTORS[actorId];
    if (!actor) {
      return;
    }
    state.actor = actorId;
    root.dataset.actor = actorId;
    updatePressed("[data-actor-choice]", "actorChoice", actorId);
    elements.actorTitle.textContent = actor.title;
    elements.actorEvidence.textContent = actor.evidence;
    elements.actorAction.textContent = actor.action;
    elements.actorAuthority.textContent = actor.authority;
    elements.actorAcceptance.textContent = actor.acceptance;
    elements.actorHandoff.textContent = actor.handoff;
    announceState("actor");
  }

  function announceState(reason) {
    const detail = Object.freeze({
      reason,
      aperture: state.aperture,
      overlay: state.overlay,
      actor: state.actor,
      theme: state.theme,
      resolvedTheme: root.dataset.resolvedTheme,
      geometry: APERTURES[state.aperture].geometry,
    });
    window.dispatchEvent(new CustomEvent("manzanita:statechange", { detail }));
  }

  function bindChoiceButtons(selector, attribute, handler) {
    document.querySelectorAll(selector).forEach((button) => {
      button.addEventListener("click", () => handler(button.dataset[attribute]));
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

  bindChoiceButtons("[data-theme-choice]", "themeChoice", (theme) => applyTheme(theme));
  bindChoiceButtons("[data-aperture-choice]", "apertureChoice", applyAperture);
  bindChoiceButtons("[data-overlay-choice]", "overlayChoice", applyOverlay);
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

  state.theme = safeReadTheme();
  applyTheme(state.theme, false);
  applyAperture(state.aperture);
  applyOverlay(state.overlay, false);
  applyActor(state.actor);

  window.__MANZANITA_SPECIMEN__ = Object.freeze({
    version: "1.0.0",
    sourceClass: "authored_demonstration_geometry",
    getState: () => ({ ...state, resolvedTheme: root.dataset.resolvedTheme }),
    apertures: Object.keys(APERTURES),
    overlays: Object.keys(OVERLAYS),
    actors: Object.keys(ACTORS),
    themes: Array.from(THEMES),
  });
})();
