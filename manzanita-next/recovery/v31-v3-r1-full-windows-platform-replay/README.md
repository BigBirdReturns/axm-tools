# Manzanita v31 V3 R1 full Windows platform replay

This bounded object acquires the exact previously sealed `MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip`, verifies its 553,074-byte identity at SHA-256 `2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738`, extracts it into an isolated GitHub-hosted Windows workspace, and executes the package-owned `RUN_WINDOWS_PLATFORM_REPLAY.cmd` campaign.

The replay exercises the complete V3 R1 package rather than a reconstructed source subset. It verifies the exact nested V3 round-trip dependency, prepares the nested recovery controls, resolves a supported Python runtime, exercises the generated `py`, `python`, and `python3` compatibility aliases with hyphenated and space-containing arguments, builds the same synthetic return collection twice, verifies byte identity, and reruns package qualification.

This object does not execute on the operator workstation. It does not read Downloads, browser caches, fixed volumes, raw devices, File Library exports, or any other operator-controlled storage. It materializes zero production inputs, invokes no production admission gate, extracts no accepted parent, creates no v31 product object, mutates no public route, and grants no merge or release authority.

A passing workflow must retain three receipts: exact package acquisition and isolation, package-owned Windows platform replay, and independent replay validation. The sole bounded terminal result is `PASS_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY`. The subsequent origin-workstation campaign remains a separate operator-controlled transaction.
