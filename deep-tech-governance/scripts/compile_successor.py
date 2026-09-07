#!/usr/bin/env python3
import argparse, copy, hashlib, json
from pathlib import Path

COLLECTIONS = [
    "actors","relationships","instruments","claims","evidence","capabilities",
    "rights","authorities","decisions","exceptions","qualification_plans",
    "stress_scenarios","lineage","successor_events"
]

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def index_state(state):
    idx = {}
    for collection in COLLECTIONS:
        for obj in state.get(collection, []):
            oid = obj.get("id") or obj.get("event_id")
            if oid:
                if oid in idx:
                    raise ValueError(f"duplicate object id across state: {oid}")
                idx[oid] = (collection, obj)
    return idx

def compile_successor(state, event):
    target_id = state["target_selection"]["target_id"]
    if event.get("target_id") != target_id:
        raise ValueError(f"event target {event.get('target_id')} does not match state target {target_id}")
    if not event.get("source_refs"):
        raise ValueError("successor event requires at least one source reference")
    idx = index_state(state)
    changes = []
    successor = copy.deepcopy(state)
    sidx = index_state(successor)
    for change in event.get("proposed_changes", []):
        oid = change["object_id"]
        if oid not in idx:
            raise ValueError(f"successor event references unknown object: {oid}")
        collection, before_obj = idx[oid]
        current = before_obj.get("state") or before_obj.get("status")
        if current != change["from_state"]:
            raise ValueError(f"{oid} expected from_state {current}, got {change['from_state']}")
        if not change.get("basis"):
            raise ValueError(f"{oid} change basis is empty")
        _, after_obj = sidx[oid]
        field = "state" if "state" in after_obj else "status"
        after_obj[field] = change["to_state"]
        changes.append({
            "object_id": oid,
            "collection": collection,
            "field": field,
            "from_state": current,
            "to_state": change["to_state"],
            "basis": change["basis"]
        })
    successor.setdefault("successor_events", []).append(copy.deepcopy(event))
    lineage_id = "LIN-" + event["event_id"]
    successor.setdefault("lineage", []).append({
        "id": lineage_id,
        "event": "successor event applied",
        "event_id": event["event_id"],
        "prior_state_sha256": digest(state)
    })
    delta = {
        "schema": "axm/deep-tech-successor-delta@1",
        "event_id": event["event_id"],
        "target_id": target_id,
        "event_class": event["event_class"],
        "materiality": event["materiality"],
        "source_refs": event["source_refs"],
        "prior_state_sha256": digest(state),
        "successor_state_sha256": digest(successor),
        "changes": changes,
        "nonclaims": event.get("nonclaims", []),
        "terminal_action": event["terminal_action"]
    }
    return delta, successor

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("state")
    ap.add_argument("event")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    state, event = load(args.state), load(args.event)
    delta, successor = compile_successor(state, event)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out/"successor-delta.json").write_bytes(canonical(delta)+b"\n")
    (out/"successor-state.json").write_bytes(canonical(successor)+b"\n")
    print(json.dumps({"status":"PASS","target_id":delta["target_id"],"event_id":delta["event_id"],"changes":len(delta["changes"]),"successor_state_sha256":delta["successor_state_sha256"]}, sort_keys=True))

if __name__ == "__main__":
    main()
