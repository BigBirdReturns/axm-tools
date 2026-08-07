# AP-410 runtime-bound hosted qualification carrier

This branch is an execution-only, never-merge carrier for Core issue #38. It contains nine checksum-bound base64 shards for the exact deterministic `AXM-Aperture-G3-Platform-Observation-Kit-v2-Bound-Runtime-v1.tar.gz` archive and one workflow limited to hosted qualification of that archive on Ubuntu 24.04 and Windows 2025.

The workflow first verifies every shard, the concatenated base64 identity, the decoded archive SHA-256, and the decoded byte count. It then extracts from exact bytes, executes the bound-release verifier twice, requires identical normalized output, verifies the self-sealed bound qualification identity, proves all evidence counts remain zero, and retains one receipt per operating system. A separate cold-replay job extracts the same archive twice, compares complete tree identities, and reruns the verifier from both roots.

The archive binds one deterministic nine-surface observation runtime to the frozen AP-400 through AP-409 source coordinates. It has no observed interactions, observed visuals, manual reader passage, AP-410 acceptance, G3 acceptance, hosted-repository acceptance, product authority, or merge authority.

The carrier closes without merge after its artifacts are independently downloaded and verified. The control question is whether the exact runtime binding and all 108 regenerated work-order cells survive Linux, Windows, and cold reconstruction while physical evidence and programme acceptance remain zero.
