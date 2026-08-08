# AP-410 Kit v2 Git-blob dispatch data

This unmerged branch is a transport object for the exact 90,028-byte Kit v2
source archive. Five content-addressed Git blobs are exposed as ordered binary
parts. The verifier recomputes every Git blob identity, concatenates the parts
once, requires the exact aggregate SHA-256 and byte count, and validates the
internal source authority before qualification.

The branch is not Tools product history, a runtime package, physical evidence,
AP-410 acceptance, G3 acceptance, or hosted-repository standing.
