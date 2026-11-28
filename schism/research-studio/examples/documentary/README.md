# Public documentary sample

From the extracted Research Studio source folder, run:

```console
python examples/documentary/run.py
```

Open `http://127.0.0.1:8374/` and select **Vendor access**. Python 3.11 or newer and its standard library supply the entire sample. It works without a network connection or account.

The launcher checks `findings.json` and the 17 vendor records against their published SHA-256 checksums, confirms that the vendor records match the aggregate document, creates a local collection specification, extracts the declared findings and vendor fields from those same source bytes, and independently verifies the resulting catalog. It then serves the reader on loopback. The generated catalog and receipt go into a new temporary directory, whose path it prints. Use `--output PATH` to choose a retained directory; use `--port NUMBER` if the default port is occupied. Press Ctrl+C to stop the reader.

To run the verification without starting a server:

```console
python examples/documentary/run.py --check-only --output documentary-run
```

`findings.json` contains an authored public projection of the vendor review dated 27 November 2026 Pacific. Its primary-source addendum retains a 28 November UTC timestamp. It preserves 17 vendor records, their claim scopes, evidence classifications, the aggregate finding, participant accounts and public citation URLs. The source record's digest identifies the retained derivation. The included projection omits private source paths and correspondence.

The sample checks the included documentary file and its extraction. It does not fetch or reverify the cited websites and does not execute a vendor implementation. Three counts vendor records with reported component substitution at mission autonomy; it is not a count of locally executed stacks. The lower-layer result remains bounded to the evidence reviewed. All public citations remain available in the JSON and the public ledger page.

The source and authored sample use the enclosing Apache-2.0 license. The files in this example are steward-owned. Generated catalogs, specifications and verification receipts belong to the person running the example and are created outside this example directory by default.
