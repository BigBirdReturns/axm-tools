# AP-410 Kit v2 trusted hosted qualification

This permanent workflow closes the hosted source-portability requirement for the AP-410 Platform Observation Kit v2 without merging Aperture source into Tools product history.

The source is retained on never-merge evidence commit `54a13c6212e18b3a191448ff28452d0f9cf1b6c0` as a 120,040-byte base64 envelope. The workflow verifies envelope SHA-256 `237b9d98dafed780c35fbfa5b1d8a0b20e3c724556f2473bc14dc9d60c59a313`, decodes the exact 90,028-byte source archive, verifies archive SHA-256 `71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74`, validates tar safety, and only then executes source law.

## Invocation

The workflow is trusted because it lives on the default branch. It runs only through a manual `workflow_dispatch` or an exact issue comment on Tools issue #71:

```text
/qualify-ap410-kit-v2
```

The issue-command path requires the comment actor to equal the repository owner. Other comments and issues fail authorization before source checkout.

## Denominator

The workflow runs the unchanged 49-contract source denominator and package verifier on Ubuntu 24.04 and Windows 2025 with Node 22.16.0 and Python 3.13. A separate Ubuntu job reconstructs and executes the source twice in clean roots, retains the exact envelope and decoded archive, and issues a source-only hosted receipt. A final job downloads that retained artifact, verifies its checksums, and independently executes the 49-contract denominator again.

Issue #71 closes only after all operating-system, cold-root, custody, and downloaded-artifact jobs pass. The terminal witness records exact job IDs, conclusions, artifact IDs, sizes, available artifact digests, trusted default-branch head, source evidence commit, source custody receipt, source archive identity, and source tree identity.

## Authority boundary

The source remains fixture-free at the runtime-binding boundary and must report:

```text
progress status        BLOCKED
reason                  runtime_binding_missing
runtime binding         absent
observed interactions  0
observed visuals       0
observed reader groups 0
canonical AP-410       false
canonical G3           false
accepted gates         []
```

A pass establishes hosted source portability only. It does not create Runtime v2, admit a Windows process, produce physical evidence, pass a manual reader group, accept AP-410, accept G3, publish the dedicated repository, or give Tools product authority.
