window.AXM_ORGAN_EVOLUTION_SEED = {
  "format": "axm-organ-evolution/1",
  "estate": {
    "id": "estate.axm",
    "name": "AXM Estate",
    "purpose": "A local-first, evidence-bearing organism whose organs may change implementation, ownership, and supplier without losing function, authority, or reconstructability.",
    "horizon": "2026-2036",
    "constraints": [
      "One accepted authority per decision boundary",
      "External projects are replaceable suppliers of capabilities",
      "Claims, evidence, motives, mandates, and decisions remain separate",
      "A transition must account for preserved, changed, retired, and introduced obligations",
      "A tool or organ may fail, leave, fork, or be replaced without erasing its lineage"
    ]
  },
  "actors": [
    {
      "id": "actor.steward",
      "name": "Estate steward",
      "roles": [
        "author",
        "steward"
      ],
      "authority": [
        "admit architecture changes after review"
      ],
      "interests": [
        {
          "mode": "self_declared",
          "claim": "Preserve architectural coherence and execution velocity.",
          "evidence": "Recorded design and closure decisions."
        }
      ]
    },
    {
      "id": "actor.operator",
      "name": "Operator",
      "roles": [
        "operator",
        "maintainer"
      ],
      "authority": [
        "run qualified procedures",
        "report physical observations"
      ],
      "interests": [
        {
          "mode": "self_declared",
          "claim": "Reduce setup friction and recover cleanly from failure.",
          "evidence": "Operational acceptance records."
        }
      ]
    },
    {
      "id": "actor.reviewer",
      "name": "Independent reviewer",
      "roles": [
        "validator"
      ],
      "authority": [
        "classify evidence sufficiency",
        "preserve dissent"
      ],
      "interests": [
        {
          "mode": "self_declared",
          "claim": "Prevent implementation volume from being mistaken for readiness.",
          "evidence": "Cold audit and regression findings."
        }
      ]
    },
    {
      "id": "actor.consumer",
      "name": "Downstream consumer",
      "roles": [
        "beneficiary",
        "integrator"
      ],
      "authority": [
        "accept or refuse a delivered capability"
      ],
      "interests": [
        {
          "mode": "ascribed",
          "claim": "Prefer a stable interface and low migration burden.",
          "evidence": "Integration constraints; requires confirmation."
        }
      ]
    },
    {
      "id": "actor.supplier",
      "name": "External supplier community",
      "roles": [
        "supplier",
        "maintainer"
      ],
      "authority": [
        "maintain its own project and release line"
      ],
      "interests": [
        {
          "mode": "inferred",
          "claim": "Protect upstream conventions and community priorities.",
          "evidence": "Inference only; not treated as motive truth."
        }
      ]
    }
  ],
  "organs": [
    {
      "id": "organ.genesis",
      "name": "Genesis",
      "class": "kernel",
      "stage": "mature",
      "mission": "Compile and verify signed knowledge shards while keeping domain spokes outside the cryptographic kernel.",
      "functions": [
        {
          "id": "fn.genesis.compile",
          "name": "Canonical compilation",
          "criticality": 5,
          "coverage": 5
        },
        {
          "id": "fn.genesis.verify",
          "name": "Independent verification",
          "criticality": 5,
          "coverage": 5
        },
        {
          "id": "fn.genesis.identity",
          "name": "Stable derived identity",
          "criticality": 5,
          "coverage": 5
        }
      ],
      "inputs": [
        "candidate records",
        "publisher authority",
        "source bytes"
      ],
      "outputs": [
        "signed shard",
        "verification result",
        "derived identity"
      ],
      "dependencies": [],
      "authority": {
        "owns": [
          "shard law",
          "signature and verification law"
        ],
        "forbidden": [
          "domain truth",
          "game outcome",
          "supplier selection"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 5,
        "authority": 5,
        "observability": 5,
        "adaptability": 4,
        "succession": 3,
        "replaceability": 2,
        "efficiency": 4,
        "containment": 5
      },
      "pressures": [
        "post-quantum implementation churn",
        "long-horizon verifier continuity"
      ]
    },
    {
      "id": "organ.core",
      "name": "Core",
      "class": "orchestration",
      "stage": "load-bearing",
      "mission": "Host spokes, mount verified records, query the estate, and keep orchestration separate from the frozen kernel.",
      "functions": [
        {
          "id": "fn.core.host",
          "name": "Spoke hosting",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.core.query",
          "name": "Verified query",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.core.ingest",
          "name": "Structured ingestion",
          "criticality": 3,
          "coverage": 4
        }
      ],
      "inputs": [
        "verified shards",
        "structured documents",
        "spoke registrations"
      ],
      "outputs": [
        "query results",
        "candidate records",
        "mounted views"
      ],
      "dependencies": [
        {
          "target": "organ.genesis",
          "kind": "verification",
          "criticality": 5,
          "replaceability": 1
        }
      ],
      "authority": {
        "owns": [
          "orchestration and query policy"
        ],
        "forbidden": [
          "reimplement Genesis custody",
          "invent spoke evidence"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 4,
        "authority": 4,
        "observability": 4,
        "adaptability": 4,
        "succession": 3,
        "replaceability": 3,
        "efficiency": 3,
        "containment": 4
      },
      "pressures": [
        "spoke growth",
        "plugin drift",
        "pressure to absorb unrelated functions"
      ]
    },
    {
      "id": "organ.embodied",
      "name": "Embodied",
      "class": "evidence",
      "stage": "emerging",
      "mission": "Preserve physical observations, immutable spools, journal continuity, and evidence projections without acquiring action or campaign authority.",
      "functions": [
        {
          "id": "fn.embodied.observe",
          "name": "Physical observation",
          "criticality": 5,
          "coverage": 4
        },
        {
          "id": "fn.embodied.spool",
          "name": "Immutable spool ingestion",
          "criticality": 5,
          "coverage": 4
        },
        {
          "id": "fn.embodied.journal",
          "name": "Hash-chained session journal",
          "criticality": 5,
          "coverage": 4
        }
      ],
      "inputs": [
        "sensor observations",
        "provisional candidates",
        "accepted receipts"
      ],
      "outputs": [
        "verified physical journal",
        "Genesis-facing shard"
      ],
      "dependencies": [
        {
          "target": "organ.genesis",
          "kind": "custody",
          "criticality": 5,
          "replaceability": 1
        },
        {
          "target": "organ.world",
          "kind": "provisional execution",
          "criticality": 4,
          "replaceability": 3
        }
      ],
      "authority": {
        "owns": [
          "physical evidence custody"
        ],
        "forbidden": [
          "accepted game outcome",
          "campaign mutation",
          "semantic interpretation of opaque capture"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 4,
        "authority": 5,
        "observability": 5,
        "adaptability": 4,
        "succession": 3,
        "replaceability": 3,
        "efficiency": 3,
        "containment": 5
      },
      "pressures": [
        "new sensor modalities",
        "clock-domain alignment",
        "physical acceptance backlog"
      ]
    },
    {
      "id": "organ.bloodstream",
      "name": "Bloodstream",
      "class": "circulation",
      "stage": "germinal",
      "mission": "Circulate append-only jobs, claims, advances, completions, and heartbeats across the estate without becoming the authority that decides their substance.",
      "functions": [
        {
          "id": "fn.blood.queue",
          "name": "Append-only job circulation",
          "criticality": 4,
          "coverage": 3
        },
        {
          "id": "fn.blood.heartbeat",
          "name": "Blocked and advanceable state fold",
          "criticality": 3,
          "coverage": 3
        },
        {
          "id": "fn.blood.handoff",
          "name": "Cross-organ handoff visibility",
          "criticality": 4,
          "coverage": 2
        }
      ],
      "inputs": [
        "job",
        "claim",
        "advance",
        "done",
        "heartbeat"
      ],
      "outputs": [
        "current job state",
        "blocked/advanceable report"
      ],
      "dependencies": [],
      "authority": {
        "owns": [
          "circulation record"
        ],
        "forbidden": [
          "auto-admit claims",
          "select suppliers",
          "override human blocks",
          "become the estate scheduler by implication"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 3,
        "authority": 4,
        "observability": 3,
        "adaptability": 4,
        "succession": 2,
        "replaceability": 4,
        "efficiency": 5,
        "containment": 4
      },
      "pressures": [
        "desire for automatic orchestration",
        "parallel-agent coordination",
        "pressure to become a universal control plane"
      ]
    },
    {
      "id": "organ.hinge",
      "name": "Hinge",
      "class": "immune",
      "stage": "emerging",
      "mission": "Expose assumptions, invalidators, triggers, evidence, and human review states without converting review priority into truth or authority.",
      "functions": [
        {
          "id": "fn.hinge.invalidators",
          "name": "Invalidator ledger",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.hinge.review",
          "name": "Attributed human review",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.hinge.impact",
          "name": "Decision-impact linkage",
          "criticality": 3,
          "coverage": 3
        }
      ],
      "inputs": [
        "forecast or plan",
        "assumptions",
        "observables",
        "evidence"
      ],
      "outputs": [
        "hinge ledger",
        "impact record",
        "review queue"
      ],
      "dependencies": [
        {
          "target": "organ.genesis",
          "kind": "optional seal",
          "criticality": 3,
          "replaceability": 1
        }
      ],
      "authority": {
        "owns": [
          "invalidator structure and review state"
        ],
        "forbidden": [
          "autonomous admission",
          "probability claims",
          "semantic decision correctness"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.reviewer"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 4,
        "authority": 5,
        "observability": 4,
        "adaptability": 4,
        "succession": 3,
        "replaceability": 4,
        "efficiency": 4,
        "containment": 5
      },
      "pressures": [
        "pressure to score likelihood",
        "pressure to automate human admission"
      ]
    },
    {
      "id": "organ.tierbench",
      "name": "Tier Bench",
      "class": "metabolism",
      "stage": "load-bearing",
      "mission": "Measure which suppliers and compositions succeed on defined tasks, at what cost and resource footprint, while keeping unmeasured capability labeled as a claim.",
      "functions": [
        {
          "id": "fn.tier.measure",
          "name": "Deterministic qualification",
          "criticality": 5,
          "coverage": 4
        },
        {
          "id": "fn.tier.route",
          "name": "Cost-per-success routing evidence",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.tier.replication",
          "name": "Commodity replication tests",
          "criticality": 4,
          "coverage": 4
        }
      ],
      "inputs": [
        "supplier candidates",
        "tasks",
        "validators",
        "hardware profiles"
      ],
      "outputs": [
        "qualification results",
        "cost-per-success",
        "residual map"
      ],
      "dependencies": [],
      "authority": {
        "owns": [
          "measurement procedure and result ledger"
        ],
        "forbidden": [
          "define domain capability by reputation",
          "promote unmeasured claims",
          "silent routing change"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator",
          "actor.reviewer"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 4,
        "authority": 5,
        "observability": 5,
        "adaptability": 5,
        "succession": 3,
        "replaceability": 4,
        "efficiency": 4,
        "containment": 4
      },
      "pressures": [
        "model churn",
        "hardware heterogeneity",
        "benchmark saturation"
      ]
    },
    {
      "id": "organ.supplier-foundry",
      "name": "Supplier Foundry",
      "class": "fabrication",
      "stage": "emerging",
      "mission": "Acquire, isolate, qualify, transform, package, substitute, and remove external suppliers without allowing the supplier or adapter to define capability, policy, or accepted authority.",
      "functions": [
        {
          "id": "fn.foundry.acquire",
          "name": "Exact supplier acquisition and license custody",
          "criticality": 4,
          "coverage": 3
        },
        {
          "id": "fn.foundry.qualify",
          "name": "Capability conformance and provider comparison",
          "criticality": 5,
          "coverage": 3
        },
        {
          "id": "fn.foundry.ripout",
          "name": "Substitution, fallback, and supplier-independent rip-out",
          "criticality": 5,
          "coverage": 4
        }
      ],
      "inputs": [
        "human-owned capability contract",
        "exact supplier manifests",
        "canonical source product",
        "budgets and license policy"
      ],
      "outputs": [
        "qualified supplier bundle",
        "measurement recommendation",
        "neutral fallback",
        "rip-out verification receipt"
      ],
      "dependencies": [
        {
          "target": "organ.tierbench",
          "kind": "measurement and qualification host",
          "criticality": 4,
          "replaceability": 3
        }
      ],
      "authority": {
        "owns": [
          "supplier acquisition, isolation, qualification, packaging, substitution, and revocation evidence"
        ],
        "forbidden": [
          "define domain capability",
          "choose estate policy",
          "accept evidence or outcomes",
          "mutate Arc law or campaigns",
          "schedule the estate",
          "turn a measured recommendation into a vendor mandate"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator",
          "actor.reviewer"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 3,
        "authority": 5,
        "observability": 5,
        "adaptability": 4,
        "succession": 4,
        "replaceability": 5,
        "efficiency": 3,
        "containment": 5
      },
      "pressures": [
        "supplier and license churn",
        "performance versus product-size tradeoffs",
        "pressure to become a universal package manager or control plane"
      ]
    },
    {
      "id": "organ.arc",
      "name": "Arc",
      "class": "decision",
      "stage": "load-bearing",
      "mission": "Own authored action law, deterministic compilation, accepted action receipts, and campaign consequences.",
      "functions": [
        {
          "id": "fn.arc.author",
          "name": "Action and campaign authoring",
          "criticality": 5,
          "coverage": 5
        },
        {
          "id": "fn.arc.sim",
          "name": "Deterministic action simulation",
          "criticality": 5,
          "coverage": 5
        },
        {
          "id": "fn.arc.receipt",
          "name": "Accepted receipt authority",
          "criticality": 5,
          "coverage": 5
        }
      ],
      "inputs": [
        "cartridge",
        "action profile",
        "input trace"
      ],
      "outputs": [
        "action spec",
        "accepted receipt",
        "campaign consequence"
      ],
      "dependencies": [],
      "authority": {
        "owns": [
          "action law",
          "accepted result",
          "campaign mutation"
        ],
        "forbidden": [
          "physical observation custody",
          "renderer-specific truth"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 5,
        "authority": 5,
        "observability": 5,
        "adaptability": 4,
        "succession": 3,
        "replaceability": 2,
        "efficiency": 4,
        "containment": 5
      },
      "pressures": [
        "pressure to absorb presentation",
        "future non-game policy extraction"
      ]
    },
    {
      "id": "organ.world",
      "name": "World",
      "class": "presentation",
      "stage": "emerging",
      "mission": "Project authored law into browser, Unity, Windows, and Quest execution while returning provisional evidence to Arc.",
      "functions": [
        {
          "id": "fn.world.project",
          "name": "Multi-representation projection",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.world.execute",
          "name": "Provisional real-time execution",
          "criticality": 5,
          "coverage": 4
        },
        {
          "id": "fn.world.return",
          "name": "Trace and candidate return",
          "criticality": 5,
          "coverage": 4
        }
      ],
      "inputs": [
        "action spec",
        "presentation manifest",
        "player input"
      ],
      "outputs": [
        "rendered encounter",
        "input trace",
        "provisional candidate"
      ],
      "dependencies": [
        {
          "target": "organ.arc",
          "kind": "action authority",
          "criticality": 5,
          "replaceability": 1
        },
        {
          "target": "organ.embodied",
          "kind": "physical custody",
          "criticality": 3,
          "replaceability": 3
        }
      ],
      "authority": {
        "owns": [
          "presentation",
          "input sampling",
          "provisional execution"
        ],
        "forbidden": [
          "accepted action result",
          "campaign mutation"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 4,
        "authority": 5,
        "observability": 4,
        "adaptability": 5,
        "succession": 2,
        "replaceability": 4,
        "efficiency": 3,
        "containment": 4
      },
      "pressures": [
        "device diversity",
        "asset production cost",
        "engine and XR churn"
      ]
    },
    {
      "id": "organ.tools",
      "name": "Tools",
      "class": "sensemaking",
      "stage": "load-bearing",
      "mission": "Publish small, self-contained evaluation surfaces that remain useful without servers, accounts, or long-lived dependencies.",
      "functions": [
        {
          "id": "fn.tools.surface",
          "name": "Static evaluation surfaces",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.tools.handoff",
          "name": "Long-horizon succession",
          "criticality": 4,
          "coverage": 4
        },
        {
          "id": "fn.tools.offline",
          "name": "Offline portability",
          "criticality": 4,
          "coverage": 5
        }
      ],
      "inputs": [
        "human-owned data",
        "committed JSON",
        "static source"
      ],
      "outputs": [
        "browser workbench",
        "exported report",
        "plain-text state"
      ],
      "dependencies": [],
      "authority": {
        "owns": [
          "method enforcement and presentation"
        ],
        "forbidden": [
          "discover truth autonomously",
          "silent write-back",
          "production authority"
        ]
      },
      "custodians": {
        "authors": [
          "actor.steward"
        ],
        "maintainers": [
          "actor.operator"
        ],
        "operators": [
          "actor.operator",
          "actor.reviewer"
        ],
        "stewards": [
          "actor.steward"
        ]
      },
      "health": {
        "function": 4,
        "authority": 5,
        "observability": 4,
        "adaptability": 5,
        "succession": 5,
        "replaceability": 5,
        "efficiency": 5,
        "containment": 5
      },
      "pressures": [
        "surface proliferation",
        "method duplication",
        "visual drift"
      ]
    }
  ],
  "evidence": [
    {
      "id": "evidence.audit",
      "title": "Cold integration audit",
      "tier": "reported",
      "independence": "independent",
      "source": "external repository review",
      "claim": "Implementation volume exceeded demonstrated end-to-end readiness until the real cartridge path converged.",
      "limits": "A cold review is bounded by the repository state and workflows it inspected."
    },
    {
      "id": "evidence.blood.readme",
      "title": "Bloodstream v0 contract",
      "tier": "confirmed",
      "independence": "self",
      "source": "axm-bloodstream README",
      "claim": "Bloodstream is an append-only circulation ledger and heartbeat, not yet an autonomous orchestrator.",
      "limits": "Repository claim; operational estate adoption is not independently measured."
    },
    {
      "id": "evidence.core.boundary",
      "title": "Core and Genesis boundary",
      "tier": "confirmed",
      "independence": "self",
      "source": "axm-core README and CI",
      "claim": "Genesis compiles and verifies; Core mounts, queries, and hosts spokes.",
      "limits": "Evidence establishes the intended and tested software boundary, not universal architectural optimality."
    },
    {
      "id": "evidence.tier.measured",
      "title": "Tier Bench measured routing",
      "tier": "measured",
      "independence": "mixed",
      "source": "Tier Bench benchmark receipts",
      "claim": "Supplier routing is based on measured task success and cost rather than brand reputation.",
      "limits": "Only tasks below the current measurement ruler are covered."
    },
    {
      "id": "evidence.action.convergence",
      "title": "Arc-to-World action convergence",
      "tier": "measured",
      "independence": "mixed",
      "source": "exact-head hosted workflows",
      "claim": "A real cartridge crosses deterministic Arc compilation, C# execution, and accepted Arc replay on the hosted path.",
      "limits": "The actual Unity and Quest physical session remains a separate machine-bound gate."
    },
    {
      "id": "evidence.ego.open",
      "title": "Motive attribution remains open",
      "tier": "open",
      "independence": "independent",
      "source": "no admissible source",
      "claim": "A proposed scope expansion is driven by ego or status defense.",
      "limits": "The surface records this as an interest hypothesis only and will not use it as a causal fact."
    },
    {
      "id": "evidence.supplier-foundry.asset-pilot",
      "title": "Supplier Foundry glTF asset commodity pilot",
      "tier": "measured",
      "independence": "mixed",
      "source": "Tier Bench PR #140; workflow 30329697910; artifacts 8676909336 and 8676907830",
      "claim": "Two exact OSS providers produced byte-deterministic, semantically equivalent bounded glTF products under network quarantine; the complete supplier runtime was then removed and the consumer bundle verified with bundled standard-library tools.",
      "limits": "One synthetic static two-triangle fixture on hosted Linux. No production asset, visual, texture, animation, skin, morph, Unity, Quest, browser, or GPU result is established."
    }
  ],
  "candidates": [
    {
      "id": "candidate.blood.harden",
      "organId": "organ.bloodstream",
      "name": "Harden circulation without adding decision authority",
      "action": "harden",
      "summary": "Complete append-only job circulation, producer/consumer visibility, invalidation, and succession while preserving the explicit rule that Bloodstream does not decide, prioritize, or admit work.",
      "changes": {
        "preserve": [
          "append-only jobs.jsonl",
          "blocked_on operator rule",
          "pure fold over rows"
        ],
        "alter": [
          "add explicit producer/consumer edges",
          "add stale-job and invalidation receipts",
          "add estate-level health projection"
        ],
        "retire": [],
        "introduce": [
          "bounded adapter contract",
          "succession and recovery test"
        ]
      },
      "dimensions": {
        "function": 5,
        "authority": 5,
        "reversibility": 5,
        "dependency": 4,
        "adaptability": 4,
        "observability": 5,
        "succession": 4,
        "efficiency": 5,
        "userValue": 4,
        "captureResistance": 5,
        "containment": 5,
        "evidence": 4
      },
      "gates": {
        "function": "pass",
        "authority": "pass",
        "evidence": "pass",
        "migration": "pass",
        "reversibility": "pass"
      },
      "actorLinks": {
        "sponsors": [
          "actor.steward"
        ],
        "validators": [
          "actor.reviewer"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.operator",
          "actor.consumer"
        ]
      },
      "evidenceIds": [
        "evidence.audit",
        "evidence.blood.readme",
        "evidence.core.boundary"
      ],
      "risks": [
        "Circulation may remain too passive for unattended work unless consumers implement their own pull loops."
      ],
      "dissent": [
        "Some operators may prefer one central scheduler even if that increases authority concentration."
      ]
    },
    {
      "id": "candidate.blood.expand",
      "organId": "organ.bloodstream",
      "name": "Expand Bloodstream into the universal estate orchestrator",
      "action": "generalize",
      "summary": "Let the circulation layer prioritize jobs, select suppliers, admit claims, reassign work, and trigger merges across every organ.",
      "changes": {
        "preserve": [
          "jobs ledger"
        ],
        "alter": [
          "turn heartbeat into scheduler",
          "centralize supplier and execution routing"
        ],
        "retire": [
          "consumer-owned pull loops"
        ],
        "introduce": [
          "estate-wide control authority",
          "central policy engine"
        ]
      },
      "dimensions": {
        "function": 4,
        "authority": 1,
        "reversibility": 2,
        "dependency": 2,
        "adaptability": 3,
        "observability": 3,
        "succession": 1,
        "efficiency": 3,
        "userValue": 4,
        "captureResistance": 1,
        "containment": 1,
        "evidence": 1
      },
      "gates": {
        "function": "warn",
        "authority": "fail",
        "evidence": "fail",
        "migration": "open",
        "reversibility": "warn"
      },
      "actorLinks": {
        "sponsors": [
          "actor.steward"
        ],
        "validators": [
          "actor.steward"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.steward",
          "actor.operator"
        ]
      },
      "evidenceIds": [
        "evidence.blood.readme",
        "evidence.ego.open"
      ],
      "risks": [
        "Collapses circulation, prioritization, supplier selection, and admission into one organ.",
        "A failure or capture event gains estate-wide blast radius."
      ],
      "dissent": [
        "The convenience case is real, but the authority transfer is not yet justified by independent evidence."
      ]
    },
    {
      "id": "candidate.blood.merge",
      "organId": "organ.bloodstream",
      "name": "Merge circulation into Core",
      "action": "merge",
      "summary": "Move the jobs ledger and heartbeat into Core so query, orchestration, and circulation share one deployment and maintenance surface.",
      "changes": {
        "preserve": [
          "append-only ledger",
          "blocked state"
        ],
        "alter": [
          "Core becomes circulation host"
        ],
        "retire": [
          "separate Bloodstream repository and release line"
        ],
        "introduce": [
          "Core extension for circulation"
        ]
      },
      "dimensions": {
        "function": 4,
        "authority": 3,
        "reversibility": 3,
        "dependency": 3,
        "adaptability": 3,
        "observability": 4,
        "succession": 4,
        "efficiency": 4,
        "userValue": 3,
        "captureResistance": 3,
        "containment": 2,
        "evidence": 2
      },
      "gates": {
        "function": "pass",
        "authority": "warn",
        "evidence": "warn",
        "migration": "open",
        "reversibility": "warn"
      },
      "actorLinks": {
        "sponsors": [
          "actor.operator"
        ],
        "validators": [
          "actor.reviewer"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.operator"
        ]
      },
      "evidenceIds": [
        "evidence.blood.readme",
        "evidence.core.boundary"
      ],
      "risks": [
        "Core becomes harder to replace and carries a larger failure domain.",
        "Circulation semantics may become implicit inside query/orchestration code."
      ],
      "dissent": [
        "A separate repository may be overhead if the organ never gains independent consumers."
      ]
    },
    {
      "id": "candidate.world.retain",
      "organId": "organ.world",
      "name": "Retain the receiver inside World until physical acceptance",
      "action": "retain",
      "summary": "Keep browser, Unity, Windows, and Quest projection together until one complete physical return proves the seams and the receiver's true reusable boundary.",
      "changes": {
        "preserve": [
          "current qualified receiver",
          "Arc authority split"
        ],
        "alter": [
          "only demonstrated repairs"
        ],
        "retire": [],
        "introduce": [
          "physical acceptance receipts"
        ]
      },
      "dimensions": {
        "function": 5,
        "authority": 5,
        "reversibility": 5,
        "dependency": 3,
        "adaptability": 4,
        "observability": 5,
        "succession": 3,
        "efficiency": 4,
        "userValue": 4,
        "captureResistance": 5,
        "containment": 4,
        "evidence": 5
      },
      "gates": {
        "function": "pass",
        "authority": "pass",
        "evidence": "pass",
        "migration": "pass",
        "reversibility": "pass"
      },
      "actorLinks": {
        "sponsors": [
          "actor.steward"
        ],
        "validators": [
          "actor.reviewer"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.operator",
          "actor.consumer"
        ]
      },
      "evidenceIds": [
        "evidence.audit",
        "evidence.action.convergence"
      ],
      "risks": [
        "Reusable receiver extraction is delayed."
      ],
      "dissent": [
        "Some downstream projects may need the receiver before Quest acceptance is complete."
      ]
    },
    {
      "id": "candidate.world.split",
      "organId": "organ.world",
      "name": "Split a reusable action receiver from World",
      "action": "split",
      "summary": "Extract the action receiver, C# mirror, adapters, and conformance vectors into a separate organ while World remains one presentation product.",
      "changes": {
        "preserve": [
          "Arc action authority",
          "input and trace formats"
        ],
        "alter": [
          "World consumes receiver package"
        ],
        "retire": [
          "duplicated receiver code in presentations"
        ],
        "introduce": [
          "versioned receiver organ",
          "multi-engine adapter contract"
        ]
      },
      "dimensions": {
        "function": 4,
        "authority": 5,
        "reversibility": 3,
        "dependency": 4,
        "adaptability": 5,
        "observability": 4,
        "succession": 3,
        "efficiency": 3,
        "userValue": 5,
        "captureResistance": 5,
        "containment": 4,
        "evidence": 3
      },
      "gates": {
        "function": "warn",
        "authority": "pass",
        "evidence": "warn",
        "migration": "open",
        "reversibility": "warn"
      },
      "actorLinks": {
        "sponsors": [
          "actor.consumer"
        ],
        "validators": [
          "actor.reviewer"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.consumer",
          "actor.supplier"
        ]
      },
      "evidenceIds": [
        "evidence.action.convergence"
      ],
      "risks": [
        "Premature extraction may freeze the wrong interface before the physical run exposes the real seam."
      ],
      "dissent": [
        "The hosted path already demonstrates enough reuse to justify a package boundary."
      ]
    },
    {
      "id": "candidate.foundry.retain-asset-pilot",
      "organId": "organ.supplier-foundry",
      "name": "Retain Supplier Foundry at the proven asset-optimization boundary",
      "action": "retain",
      "summary": "Admit the organ for exact supplier acquisition, bounded asset conformance, provider comparison, neutral fallback, and rip-out while refusing every broader policy or scheduling claim.",
      "changes": {
        "preserve": [
          "asset.optimize.gltf/v1 contract",
          "exact package-lock custody",
          "source fallback",
          "supplier-independent verifier",
          "measurement recommendation only"
        ],
        "alter": [
          "replace synthetic-only evidence with additional governed fixtures before production routing"
        ],
        "retire": [],
        "introduce": [
          "scoped estate observation",
          "successor reconstruction record",
          "consumer adoption receipt"
        ]
      },
      "dimensions": {
        "function": 4,
        "authority": 5,
        "reversibility": 5,
        "dependency": 4,
        "adaptability": 5,
        "observability": 5,
        "succession": 4,
        "efficiency": 4,
        "userValue": 4,
        "captureResistance": 5,
        "containment": 5,
        "evidence": 4
      },
      "gates": {
        "function": "pass",
        "authority": "pass",
        "evidence": "pass",
        "migration": "pass",
        "reversibility": "pass"
      },
      "actorLinks": {
        "sponsors": [
          "actor.steward"
        ],
        "validators": [
          "actor.reviewer"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.operator",
          "actor.consumer"
        ]
      },
      "evidenceIds": [
        "evidence.supplier-foundry.asset-pilot",
        "evidence.tier.measured"
      ],
      "risks": [
        "The current capability evidence may be mistaken for production-asset or runtime performance."
      ],
      "dissent": [
        "A dedicated organ may be unnecessary if asset optimization remains one small Tier Bench experiment."
      ]
    },
    {
      "id": "candidate.foundry.expand-texture-class",
      "organId": "organ.supplier-foundry",
      "name": "Extend Supplier Foundry to texture compression",
      "action": "specialize",
      "summary": "Add a separate texture.compress.ktx2/v1 capability only after a governed image corpus, visual-quality oracle, device decode measurements, license review, fallback, and rip-out plan exist.",
      "changes": {
        "preserve": [
          "asset pilot authority membrane",
          "capability-specific contracts",
          "exact supplier custody",
          "neutral fallback and rip-out"
        ],
        "alter": [
          "generalize provider adapters only where the second capability proves the shared seam"
        ],
        "retire": [],
        "introduce": [
          "texture corpus",
          "visual-quality comparator",
          "device decode and memory receipts",
          "KTX2 fallback contract"
        ]
      },
      "dimensions": {
        "function": 3,
        "authority": 5,
        "reversibility": 4,
        "dependency": 3,
        "adaptability": 4,
        "observability": 3,
        "succession": 3,
        "efficiency": 3,
        "userValue": 5,
        "captureResistance": 5,
        "containment": 4,
        "evidence": 1
      },
      "gates": {
        "function": "warn",
        "authority": "pass",
        "evidence": "open",
        "migration": "open",
        "reversibility": "pass"
      },
      "actorLinks": {
        "sponsors": [
          "actor.steward"
        ],
        "validators": [
          "actor.reviewer"
        ],
        "deciders": [
          "actor.steward"
        ],
        "beneficiaries": [
          "actor.operator",
          "actor.consumer"
        ]
      },
      "evidenceIds": [
        "evidence.supplier-foundry.asset-pilot"
      ],
      "risks": [
        "A file-size win may conceal unacceptable visual loss, decode latency, memory growth, or platform-specific failure."
      ],
      "dissent": [
        "Texture compression may deliver more immediate Quest value than further static-mesh fixtures."
      ]
    }
  ],
  "scenarios": [
    {
      "id": "scenario.steward_exit",
      "name": "Steward exits for one year",
      "description": "No original author is available. A successor must reconstruct purpose, authority, and safe changes from the estate.",
      "dimensions": [
        "succession",
        "observability",
        "reversibility"
      ]
    },
    {
      "id": "scenario.supplier_loss",
      "name": "Primary supplier disappears",
      "description": "A critical upstream project, API, model, or engine becomes unavailable with no migration assistance.",
      "dimensions": [
        "dependency",
        "adaptability",
        "reversibility"
      ]
    },
    {
      "id": "scenario.load_10x",
      "name": "Load rises tenfold",
      "description": "Work volume and downstream demand increase by an order of magnitude without a matching increase in maintainers.",
      "dimensions": [
        "function",
        "efficiency",
        "containment"
      ]
    },
    {
      "id": "scenario.capture",
      "name": "Authority capture attempt",
      "description": "One actor accumulates sponsorship, validation, decision, maintenance, and beneficiary roles around the organ.",
      "dimensions": [
        "authority",
        "captureResistance",
        "observability"
      ]
    },
    {
      "id": "scenario.license",
      "name": "Upstream relicenses",
      "description": "A supplier changes license or distribution terms after the organ depends on its product.",
      "dimensions": [
        "dependency",
        "reversibility",
        "adaptability"
      ]
    },
    {
      "id": "scenario.network",
      "name": "Network and cloud absent",
      "description": "The organ must continue or fail visibly without remote services, accounts, or live package retrieval.",
      "dimensions": [
        "function",
        "containment",
        "observability"
      ]
    },
    {
      "id": "scenario.fork",
      "name": "Institutional fork",
      "description": "Two legitimate successor groups diverge on policy and implementation while claiming the same lineage.",
      "dimensions": [
        "authority",
        "succession",
        "adaptability"
      ]
    }
  ],
  "decision": {
    "organId": "organ.bloodstream",
    "candidateId": "candidate.blood.harden",
    "state": "proposed",
    "decider": "actor.steward",
    "rationale": "Preserve circulation as an independent, low-authority organ and complete its missing producer/consumer and succession surfaces before considering central scheduling.",
    "openQuestions": [
      "Which downstream consumer still cannot advance work without a central scheduler?",
      "Can a second implementation reproduce the jobs fold and heartbeat from the same ledger?",
      "Which authority would be lost or concentrated under a merge or generalization?"
    ]
  }
};
