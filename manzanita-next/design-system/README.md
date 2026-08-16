# Manzanita design constitution v1.0

This directory operates the design-constitution tranche associated with `JDB99-004` through `JDB99-011`. It defines the recognizable form, typography, light and dark materials, symbols, image and evidence classes, motion semantics, content hierarchy, and representative production components that must exist before whole-page successor production resumes.

The object is an internal design constitution and specimen, not a public Manzanita release. The design integrator owns coherence across the system. The contained review board examines the exact candidate through separate creative, product, information, typography, motion, source, field, accessibility, performance, security, and continuity apertures. Release authority may admit the constitution for internal production use. It cannot infer product qualification, public deployment, external review, or authority for an external effect.

## Recognizable form

The form language is named **Forkline Field**. Its invariant is a source-bound ground contour that follows the natural or measured edge of the object. A branch line leaves that contour only to identify an actor, action, or handoff. A node marks evidence, uncertainty, or a receipt. A cut marks a boundary in authority or source coverage. A register line shows that two layers share one coordinate or decision frame.

Forkline Field prohibits the shortcut that failed the earlier successor work: drawing a generic polygon or card over a landscape and calling it registered. Main contours must be derived from the geometry of the represented object or explicitly labeled as authored demonstration geometry. An annotation snaps to a retained vertex or measured station. When the source is absent, the line stops and the absence remains visible.

The form can be recognized in an unlabeled crop through five recurring properties: terrain-following edges, a forked branch mark, square evidence nodes, consequence-color cuts, and a narrow source rail. It is intentionally usable in maps, street scenes, editorial pages, mobile controls, printouts, and failure receipts without reducing every object to one card layout.

## Typography and materials

The type system separates display, editorial, operational, label, data, and compact roles. It uses durable local font stacks and does not depend on a network font. Display and editorial roles carry the human and place narrative. Operational, label, and data roles carry source, time, authority, state, and action. Compact mode changes measure and rhythm rather than merely shrinking desktop type.

Light and dark modes contain the same semantic materials. Paper, ink, bark, leaf, water, sun, uncertainty, and failure retain the same role, contrast floor, line hierarchy, and consequence order in both modes. Neither mode is a decorative recoloring of the other. Auto, Light, and Dark are the only product-facing theme labels.

## Source and image classes

Observed, provider-rendered, captured, authored, modeled, generated, derived, unavailable, and redacted states are separate classes. Every class carries a permitted claim, required label, rights or custody requirement, and prohibited substitution. Generated imagery may explain, prototype, redact, or demonstrate. It may not replace available street imagery, public geospatial evidence, current conditions, household observations, or completed-work receipts.

The specimen uses authored demonstration geometry and says so in the visible source rail. It does not pretend to be a surveyed property, a live incident, or one of the retained source-foundation payloads.

## Motion and interaction

Motion must explain a change in scale, source, registration, state, or handoff. It cannot animate a crop while leaving the underlying object unchanged. Reduced motion preserves the same before-and-after states, evidence, and authority. Controls in the specimen change the actual contour set, evidence objects, safe action, and authority aperture. Theme controls change materials only and preserve identical content.

## Operation

The constitution is machine-readable in `CONSTITUTION.json`. The self-contained specimen is under `specimen/`. Static and browser tests are under `tests/`. The contained board packet and decision are under `review/`.

From the repository root:

```bash
python -m unittest discover \
  -s manzanita-next/design-system/tests \
  -p "test_*.py"

python manzanita-next/design-system/tests/browser_test.py \
  --root manzanita-next/design-system/specimen \
  --out manzanita-next/design-system/out

python programs/manzanita-99/review-board/validate_review_board.py \
  --repo-root . \
  --packet manzanita-next/design-system/review/M99-RB-PKT-002.json \
  --decision manzanita-next/design-system/review/M99-RB-DEC-002.json \
  --receipt manzanita-next/design-system/out/BOARD_DECISION_RECEIPT.json
```

A passing constitution workflow proves only that the exact internal design system, representative components, adversarial tests, full-state captures, and contained board decision agree. It does not prove the seven production apertures, eight live overlays, five operating seats, provider operations, field use, public endpoint, or cold-successor release campaign.

The controlling question is whether an unlabeled fragment remains recognizably Manzanita while still exposing the source, actor, mechanism, authority, uncertainty, next safe action, and the exact boundary beyond which the object has no standing.
