# Exposure-safety certificate report — `synthetic_repeated_dose`

**Verdict:** `CERTIFIED`  
**Target certified class:** one-compartment, first-order elimination, repeated IV bolus at steady state

## Theorem (model-relative, conditional)

For the declared one-compartment repeated-dose model, the predicted steady-state trough remains above the declared efficacy floor and the predicted peak remains below the declared toxicity ceiling for every parameter value inside the fitted interval box.

## Assumptions

- one-compartment model
- first-order elimination
- fixed dose and interval
- fitted parameter intervals are accepted as inputs
- off-model physiology is out of scope

## Parameter provenance

| Field | Value |
|---|---|
| Model / run | synthetic popPK base model, run 22 |
| Dataset | synthetic PHASE1-MAD cohort |
| Estimation method | FOCEI-style synthetic fit |
| Interval origin | synthetic 90% profile-likelihood interval |

## Proof identity

- verified schema: `Bio.PKPD.RepeatedDose.repeated_dose_window_rational`
- kernel-checked under: Lean 4 + Mathlib
- emitted-artifact SHA-256: `1863f3b853994b30b5d36a3c48df95957a47ecb5bf6c6f17b967553e6352be8a`

## Model-risk note

This is a machine-checked statement about a model under explicitly stated, bounded assumptions. It is not evidence that a drug, dose, taper, or discontinuation is safe for a patient. Model misspecification, interval miscalibration, clinical heterogeneity, adherence, and off-model physiology remain outside the certificate.
