# AXM Aperture .NET SDK 8.0.413 toolchain ferry

This is an execution-only toolchain transaction for the local `BigBirdReturns/axm-aperture` G1 conformance gate. It exists because the local execution container cannot retrieve arbitrary external binaries, while the GitHub-hosted runner can reach Microsoft's official release endpoints.

The workflow resolves SDK `8.0.413` from Microsoft's .NET 8 release metadata, selects the exact `linux-x64` SDK archive, verifies the downloaded archive against the SHA-512 value published in that metadata, extracts it, requires `dotnet --version` to equal `8.0.413`, compiles and runs an original C# smoke program, and emits a deterministic repacked SDK plus complete checksums and a machine receipt.

The artifact may be consumed only after its workflow run succeeds and the downloaded artifact ZIP is independently hashed. This branch and pull request must never merge. It carries no AXM Aperture product source, story data, viewer data, media, model weights, provider credentials, or authority beyond toolchain acquisition.

A passing workflow establishes exact Microsoft-source custody, checksum agreement, extraction, native CLR execution, and C# compilation on the named runner. It does not establish G1 passage by itself. The Aperture repository must still compile and execute its complete C# conformance suite and reconcile Python, TypeScript, C#, schemas, valid vectors, invalid vectors, and compatibility receipts.

The control question is whether the exact SDK used by the Aperture gate can be reconstructed from Microsoft-published metadata and verified bytes without allowing this temporary transport branch to enter either repository's product history.
