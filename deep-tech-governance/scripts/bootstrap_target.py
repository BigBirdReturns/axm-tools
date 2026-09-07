#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_bytes(path):
    p = Path(path)
    data = p.read_bytes()
    return data, json.loads(data.decode("utf-8"))


def validate_selection(obj):
    required = ["schema","selection_id","target_id","target_label","selected_by","selected_at","sector_pack","automatic_selection"]
    missing = [k for k in required if k not in obj]
    if missing:
        raise ValueError("missing selection fields: " + ",".join(missing))
    if obj["schema"] != "axm/deep-tech-target-selection@1":
        raise ValueError("unsupported selection schema")
    if obj["sector_pack"] != "AXM-DEEPTECH-001":
        raise ValueError("selection receipt binds wrong sector pack")
    if obj["automatic_selection"] is not False:
        raise ValueError("automatic target selection is forbidden")
    for key in ["selection_id","target_id","target_label","selected_by","selected_at"]:
        if not isinstance(obj[key], str) or not obj[key].strip():
            raise ValueError(f"selection field {key} must be nonempty")


def make_state(selection, receipt_sha):
    return {
        "schema":"axm/deep-tech-governed-state@1",
        "target_selection":{
            "target_id":selection["target_id"],
            "target_label":selection["target_label"],
            "selected_by":selection["selected_by"],
            "selection_receipt":f"selection-receipt.json#sha256={receipt_sha}",
            "automatic_selection":False
        },
        "meta":{"as_of":selection["selected_at"],"sector_pack":"AXM-DEEPTECH-001","public_only":True},
        "sources":[],"actors":[],"relationships":[],"instruments":[],"claims":[],"evidence":[],
        "capabilities":[],"rights":[],"authorities":[],"decisions":[],"exceptions":[],
        "qualification_plans":[],"stress_scenarios":[],"lineage":[{
            "id":"LIN-BOOTSTRAP-001","event":"target workspace bootstrapped",
            "selection_id":selection["selection_id"],"selection_receipt_sha256":receipt_sha
        }],"successor_events":[]
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("selection_receipt")
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    raw, selection = load_bytes(args.selection_receipt)
    validate_selection(selection)
    out=Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit("refusing nonempty output directory")
    out.mkdir(parents=True, exist_ok=True)
    receipt_sha=sha256(raw)
    (out/"selection-receipt.json").write_bytes(raw)
    state=make_state(selection,receipt_sha)
    (out/"governed-state.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    receipt={"schema":"axm/deep-tech-bootstrap-receipt@1","status":"PASS","target_id":selection["target_id"],"selection_id":selection["selection_id"],"selection_receipt_sha256":receipt_sha,"state_path":"governed-state.json","public_only":True,"external_effects":0}
    (out/"BOOTSTRAP_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,sort_keys=True))

if __name__=="__main__":
    main()
