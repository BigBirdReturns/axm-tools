# AP-410 Platform Observation Kit v2 source custody

This branch is an evidence-only Git ref for the exact base64 envelope and decoded source archive used by the permanent trusted qualification workflow. It keeps the source outside Tools `main` while making the archive durably reachable by an exact Git commit.

```text
encoded file
AXM-Aperture-G3-Platform-Observation-Kit-v2.tar.gz.b64

encoded bytes
120040

encoded SHA-256
237b9d98dafed780c35fbfa5b1d8a0b20e3c724556f2473bc14dc9d60c59a313

decoded archive bytes
90028

decoded archive SHA-256
71f4a03b50138c4f37e1fc5bce16a211f1e72f06ad5338700db1f5eaaf19bf74

kit
g3observationkit2_6a0784236b71e0c78d22a6087aa837764eadddee17cc58e9522e909358eda9a1

qualification
g3observationqualification2_14f759a2212a911e6d9f0ae81e0e7f9a5937ceddcbe1e2b00864e51380bd4ec

blocked progress
uiprogress2_6073d7e2855ec35fece231f86e0cc0aa94ed9499d1b7a44d7fdbd5d1f2837cf2
```

A consumer must verify the envelope hash and length, decode base64, verify the archive hash and length, and validate the tar before executing source contracts. This branch must never merge. It has no Tools product, runtime, physical-observation, canonical AP-410, G3, publication, or accepted-gate authority.
