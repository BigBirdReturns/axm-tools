#!/usr/bin/env python3
import argparse, json
from pathlib import Path

HIGH = {"high", "critical"}

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def compile_outputs(state):
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    instruments = state.get("instruments", [])
    rights = state.get("rights", [])
    authorities = state.get("authorities", [])
    capabilities = state.get("capabilities", [])
    exceptions = state.get("exceptions", [])
    qplans = state.get("qualification_plans", [])

    public_baseline = {
        "schema": "axm/public-baseline@1",
        "target_selection": state["target_selection"],
        "as_of": state["meta"]["as_of"],
        "claims": [
            {"id": c["id"], "state": c["state"], "text": c["text"],
             "source_refs": c.get("source_refs", []),
             "allowed_language": c.get("allowed_language", ""),
             "prohibited_upgrade": c.get("prohibited_upgrade", "")}
            for c in claims if c.get("state") != "WITHDRAWN"
        ],
        "evidence": [
            {"id": e["id"], "state": e["state"], "source_refs": e.get("source_refs", []),
             "proves": e.get("proves", []), "does_not_prove": e.get("does_not_prove", [])}
            for e in evidence
        ],
        "nonclaims": [
            "Public observation is not private company truth.",
            "Unknown state remains visible.",
            "No output grants corporate authority or creates an external effect."
        ]
    }

    diligence_map = {
        "schema": "axm/diligence-map@1",
        "target_id": state["target_selection"]["target_id"],
        "held_or_stale_claims": [c for c in claims if c.get("state") in {"HELD","STALE"}],
        "high_risk_claims": [c for c in claims if c.get("risk") in HIGH],
        "open_high_critical_exceptions": [
            e for e in exceptions
            if e.get("status") in {"OPEN","HELD"} and e.get("severity") in HIGH
        ],
        "instruments": instruments,
        "rights": rights,
        "authorities": authorities,
        "qualification_plans": qplans
    }

    gap_classes = []
    if any(i.get("state") in {"UNKNOWN","SIGNED_REPORTED","REPORTED"} for i in instruments):
        gap_classes.append("executed_private_instruments")
    if any(r.get("state") in {"UNKNOWN","REPORTED"} for r in rights):
        gap_classes.append("rights_and_chain_of_title")
    if any(a.get("state") in {"UNKNOWN","ASSERTED"} for a in authorities):
        gap_classes.append("actual_delegated_authority")
    if any(c.get("state") in {"HELD","SOURCE_ONLY"} and c.get("risk") in HIGH for c in claims):
        gap_classes.append("company_controlled_evidence_for_high_risk_claims")
    if any(e.get("status") in {"OPEN","HELD"} and e.get("severity") in HIGH for e in exceptions):
        gap_classes.append("exception_resolution_records")

    admission_map = {
        "schema": "axm/admission-map@1",
        "target_id": state["target_selection"]["target_id"],
        "required_company_controlled_record_classes": sorted(set(gap_classes)),
        "authority_rule": "Admission requires an attributable source and an operator with authority to admit that class of record.",
        "public_baseline_mutation": "forbidden; admitted facts create successor state"
    }

    operating_readiness = {
        "schema": "axm/operating-readiness@1",
        "target_id": state["target_selection"]["target_id"],
        "capabilities": capabilities,
        "authority_gaps": [a for a in authorities if a.get("state") in {"UNKNOWN","ASSERTED"}],
        "high_critical_exceptions": [e for e in exceptions if e.get("severity") in HIGH and e.get("status") != "CLOSED"],
        "technical_evidence_minimum": [
            "hardware_revision","software_revision","model_or_policy_revision",
            "sensor_and_calibration_refs","environment","procedure","telemetry_refs",
            "acceptance_criteria","result","limitations","authority_ref","source_refs"
        ],
        "ready_for_external_effects": False
    }

    return {
        "public-baseline.json": public_baseline,
        "diligence-map.json": diligence_map,
        "admission-map.json": admission_map,
        "operating-readiness.json": operating_readiness,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("state")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    state = load(args.state)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    compiled = compile_outputs(state)
    for name, obj in compiled.items():
        (out/name).write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"status":"PASS","outputs":sorted(compiled),"target_id":state["target_selection"]["target_id"]}, sort_keys=True))

if __name__ == "__main__":
    main()
