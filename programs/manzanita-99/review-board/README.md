# Manzanita contained multidisciplinary review board

This directory operates the review mechanism named by `JDB99-027`. It does not simulate outside endorsement, appoint a named external person, or convert internal review into release authority. The object is a contained decision system that makes each discipline, question, veto, defect, receipt, and authority boundary reproducible before a Manzanita candidate can advance.

## Actors and authority

The design integrator assembles the review packet and is accountable for the coherence of the whole object. Eleven contained discipline seats examine the same packet through different operating apertures: creative direction; product and interaction; information design; typography; motion; source custody; field operations; accessibility; performance and resilience; security and privacy; and continuity and release governance. The board chair checks coverage and conflict but cannot erase a seat finding. The release authority may admit, hold, reject, or supersede an object after the board record is complete. No review seat can deploy, publish, spend, contact a person, make an adverse decision, or claim that a product has been externally reviewed.

The seats are functions rather than personalities. Any qualified operator or agent may occupy a seat if the resulting review answers the chartered questions, cites retained evidence, states uncertainty, exercises the applicable failure mode, and remains within that seat's authority. A single operator may exercise more than one contained seat, but the records remain separate so disagreement cannot disappear into one blended narrative.

## Mechanism

`BOARD_CHARTER.json` freezes the seat roster, required questions, evidence minimums, veto jurisdiction, decision states, and non-authority boundary. `review-packet.schema.json` defines the object submitted for review. `review-decision.schema.json` defines seat findings, defects, vetoes, holds, and the final board disposition. The activation packet and decision under `cases/` prove the mechanism against a real governance object while expressly carrying no product-release effect.

`validate_review_board.py` validates the charter, packet, decision, evidence paths, exact seat coverage, applicable gates, veto law, authority boundary, and deterministic receipt. It refuses admission when any applicable gate is unknown, any required seat is missing, any critical or high veto remains open, evidence is absent, or the requested decision exceeds the packet's authority. `tests/test_review_board.py` exercises those refusal paths.

The board does not average away defects. A critical veto blocks admission. A high veto blocks admission until resolved or converts the outcome to `hold` or `reject`. Medium and low defects require an owner, acceptance condition, and disposition. A gate marked `not_applicable` requires a reason. A `pass` means only that the named review mechanism and evidence satisfy the charter for the submitted object.

## Operation

From the repository root:

```bash
python -m unittest discover \
  -s programs/manzanita-99/review-board/tests \
  -p "test_*.py"

python programs/manzanita-99/review-board/validate_review_board.py \
  --repo-root . \
  --packet programs/manzanita-99/review-board/cases/M99-RB-PKT-001.json \
  --decision programs/manzanita-99/review-board/cases/M99-RB-DEC-001.json \
  --receipt programs/manzanita-99/review-board/out/BOARD_ACTIVATION_RECEIPT.json
```

The expected result is `PASS` with board status `ACTIVE`, packet disposition `admit_governance_only`, and release effect `none`. The receipt proves that the review machinery is complete and internally consistent. It does not qualify Manzanita, change the historical public route, close the damaged constitutional backlog, or authorize any public or external effect.

`ACTIVATION_STATE.json` records that the mechanism is operational while preserving the constitutional-source boundary established after the original 497-row register was found unrecoverable. The operating fact may be used by later tranches. It does not silently decrement a remembered task total or fabricate a canonical task-row transition.

The controlling question is whether a cold successor can submit one bounded object, receive a separate evidence-backed judgment from every applicable discipline, preserve disagreement and vetoes, and identify exactly who may decide what happens next without mistaking internal review for product or release authority.
