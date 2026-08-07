# AP-410 observation-kit v2 hosted qualification carrier

This branch is a temporary, never-merge execution carrier for the exact source archive `AXM-Aperture-G3-Platform-Observation-Kit-v2.tar.gz`, 90,028 bytes, SHA-256 `71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74`.

Each job retrieves five recently created repository Git blobs through the authenticated Git Data API, decodes their base64 payloads, and admits exactly one blob whose byte count and SHA-256 match the frozen source archive. The source is not regenerated, patched, or promoted into Tools product history.

The workflow must reproduce 49 contracts, package verification, the exact kit and qualification identities, absence of `RUNTIME_BINDING.json`, and `BLOCKED` progress with `runtime_binding_missing` and zero physical evidence. A green run proves transport and source portability only. It cannot accept AP-410, G3, a hosted repository, publication, or any gate.
