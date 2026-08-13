# V11 Qualification Report

## Result

**PASS**

The standalone demonstrator passed static integrity, JavaScript parsing, JSON-schema, browser, scenario, authority-separation, receipt, and mobile-layout checks.

## Browser qualification

| Scenario | Gate | Pass | Margin | Breach risk | Restoration | N-1 | Holdouts | Load |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| Qualified entry | operate | true | 24.0 mo | 0.006% | 100.0% | true | 0 | 0.23x |
| Hidden holdout | hold | false | -5.1 mo | 95.0% | 100.0% | false | 1 | 0.76x |
| N-1 ambiguity | operate | true | 24.0 mo | 0.006% | 100.0% | true | 0 | 0.46x |
| Saturation | hold | false | -38.8 mo | 95.0% | 100.0% | true | 0 | 9.66x |

The authority-failure path generated three rejected attempts. The attempts were logged and did not create valid target-state transitions.

## Integrity checks

- The HTML contains no remote script, remote stylesheet, runtime `fetch`, `XMLHttpRequest`, or WebSocket dependency.
- The JavaScript parses under Node 22.
- The SHA-256 fallback returns the standard digest for `abc`.
- Four embedded scenarios validate against `BP-SCENARIO/1.0`.
- Four retained receipts validate against the receipt schema.
- The public-source ledger contains nine official or institutional source routes.
- No prohibited weapon-design instruction pattern was detected.
- Desktop and 390-pixel mobile layouts produced no browser error; mobile body width equals viewport width.

## Evidence boundary

Passing this suite demonstrates internal consistency of the synthetic institutional workflow. It does not establish the throughput, legal authority, political reliability, or classified-data performance of any real institution.

## Residual defects

1. The gate risk function remains a synthetic deterministic estimate rather than a calibrated empirical model.
2. Scenario truth is embedded in the browser and exported in receipts. A real exercise must separate facilitator truth from participant and public views.
3. The action system is sequential and does not yet model genuinely concurrent human teams or asynchronous negotiation.
4. Resource use is represented as bounded counters and load, rather than measured queue-service distributions.
5. External institutions have not reviewed the role map or timing assumptions.
