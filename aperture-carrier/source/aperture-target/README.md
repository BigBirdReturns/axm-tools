# AP-404 core context and question source candidate

This source candidate exposes four bounded question transactions: `where_am_i`, `who_is_this`, `explain_this`, and free-form `ask`. The client constructs a content-addressed normative query, emits a request intent, consumes an externally observed AP-210 answer plan, and consumes an externally validated AP-215 structured or prose realization. It never runs the planner, model, renderer, knowledge ledger, provider, or transport.

Structured fallback remains available as soon as a valid plan arrives. Optional prose must preserve the exact planned fact set and order. Planner refusal produces deterministic bounded refusal copy rather than a generic chatbot answer. Withheld fact identities remain internal and are represented to the view only as a count. Knowledge effects are an external unapplied projection; the client displays the summary but cannot create or commit knowledge events.

The candidate is transport and qualification evidence for the absent `BigBirdReturns/axm-aperture` repository. It does not accept canonical AP-404, AP-402, AP-403, G3, model execution, query execution, or hosted repository standing.
