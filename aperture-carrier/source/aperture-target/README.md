# AP-403 paired second-screen source candidate v2

This eleven-file source candidate implements the frozen AP-403 state law for a future `BigBirdReturns/axm-aperture` repository. It accepts externally validated pairing, connection, snapshot, viewport, and AP-401 Coach projections. It emits deterministic request intents and records delivery receipts without treating either as answer, selection, playback, or operating-system observations.

Shared devices require an explicit viewer selection receipt. Pairing revision, connection sequence, observation identity, snapshot identity, device digest, viewer digest, and package digest are closed and monotonic. Disconnect preserves the last verified anchor, context, provenance, and Coach projection as stale read-only context. Reconnect requires a fresh snapshot at or beyond the observed server sequence before substantive presentation or requests resume.

The target owns no pairing transport, certificate, private key, bearer token, QR authority, LAN listener, trust-on-first-use path, provider credential, biometric inference, local clock, timer, persistence store, browser network call, query execution, selection execution, playback execution, personal history, story authority, package authority, publication authority, or gate authority.

AP-219 remains planned and unexecuted. AP-401 remains a closed-unmerged source candidate. A green source carrier does not accept canonical AP-403, AP-219, G4, authenticated LAN pairing, a native handset, television, console, or closed-app client, accessibility, lifecycle, portability, publication, or the absent dedicated repository.
