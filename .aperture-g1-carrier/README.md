# AXM Aperture G1 hosted conformance carrier

This directory is a checksum-bound transport used only to compile and execute the
Aperture protocol conformance implementations on a hosted .NET 8 runner. It is
not the normative Aperture repository, cannot confer product authority, and must
never be treated as a substitute for `BigBirdReturns/axm-aperture`.

The materializer verifies the exact two-part archive, rejects traversal and link
members, enforces the declared file and expansion ceilings, and writes one clean
`aperture-program/` directory. The workflow executes Python, TypeScript, and C#
against the same 75-case vector set and requires byte-identical output.

This branch and pull request are execution custody only. They should be closed
without merge after the retained artifact and receipt are verified.
