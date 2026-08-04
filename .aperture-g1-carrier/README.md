# AXM Aperture G1 hosted conformance carrier

This directory is a checksum-bound transport used only to compile and execute the
Aperture protocol conformance implementations on a hosted .NET 8 runner. It is
not the normative Aperture repository, cannot confer product authority, and must
never be treated as a substitute for `BigBirdReturns/axm-aperture`.

The materializer verifies the exact two-part archive, rejects traversal and link
members, enforces the declared file and expansion ceilings, and writes one clean
`aperture-program/` directory. The workflow executes Python, TypeScript, and C#
against the same 75-case vector set and requires byte-identical output.

`global.json` is copied into the ephemeral Actions workspace before execution and
pins SDK `8.0.423` with roll-forward disabled. This repairs the first hosted run,
which correctly passed all 75 semantic vectors but selected preinstalled SDK
`10.0.302`; that run is retained as diagnostic evidence rather than exact-toolchain
qualification.

This branch and pull request are execution custody only. They should be closed
without merge after the retained artifact and receipt are verified.
