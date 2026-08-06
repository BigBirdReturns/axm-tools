# AP-406 spoiler and knowledge controls source candidate

This source candidate implements global, story, and per-query spoiler policy projection; knowledge-assumption policy inspection; fact availability reasons; append-only user-attributed correction, confirmation, revocation, and restoration intents; and non-destructive fact history inspection.

The client is a pure read-only projection and intent constructor. The AXM Aperture daemon remains authoritative for viewer policy, Knowledge Ledger admission, event timestamps, event persistence, story packages, and query planning. The source has no transport, credential, provider, model execution, local clock, persistence, playback, story, package, publication, or gate authority.

A full-continuity policy is always shown inline with its exact scope before an answer. The client never requires a modal to preserve spoilers. Revocation and correction generate user-attributed append-only event intents; they never erase prior history.
