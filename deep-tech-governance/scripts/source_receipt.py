#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

CLASSES={"PRIMARY_FIRST_PARTY","INDEPENDENT_PRIMARY","OFFICIAL_RECORD","SECONDARY","DISCOVERY_LEAD"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--source-id",required=True)
    ap.add_argument("--source-class",required=True)
    ap.add_argument("--locator",required=True)
    ap.add_argument("--title",required=True)
    ap.add_argument("--observed-at",required=True)
    ap.add_argument("--authority-scope",required=True)
    ap.add_argument("--nonclaim",action="append",default=[])
    ap.add_argument("--capture")
    args=ap.parse_args()
    if args.source_class not in CLASSES:
        raise SystemExit("unsupported source class")
    root=Path(args.workspace)
    state_path=root/"governed-state.json"
    state=json.loads(state_path.read_text(encoding="utf-8"))
    target_id=state["target_selection"]["target_id"]
    sources=state.setdefault("sources",[])
    if any(s.get("source_id")==args.source_id for s in sources):
        raise SystemExit("duplicate source id")
    receipt={
        "schema":"axm/deep-tech-source-receipt@1","source_id":args.source_id,"target_id":target_id,
        "source_class":args.source_class,"locator":args.locator,"title":args.title,"observed_at":args.observed_at,
        "capture_mode":"METADATA_ONLY","public_source":True,"authority_scope":args.authority_scope,
        "nonclaims":list(args.nonclaim)
    }
    if args.capture:
        p=Path(args.capture)
        data=p.read_bytes()
        receipt["capture_mode"]="LOCAL_BYTES"
        receipt["content_sha256"]=sha256(data)
        receipt["content_bytes"]=len(data)
    sources.append(receipt)
    state_path.write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    receipts=root/"source-receipts"
    receipts.mkdir(exist_ok=True)
    rp=receipts/f"{args.source_id}.json"
    rp.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    result={"status":"PASS","target_id":target_id,"source_id":args.source_id,"capture_mode":receipt["capture_mode"],"receipt_path":str(rp.relative_to(root)),"external_effects":0}
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
