#!/usr/bin/env python3
import argparse, hashlib, json, zipfile
from pathlib import Path
from compile_outputs import compile_outputs

FIXED_TIME = (1980, 1, 1, 0, 0, 0)

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def freeze(state_path, out_path, root=None):
    state_path = Path(state_path)
    root = Path(root or Path(__file__).resolve().parents[1])
    state = load(state_path)
    pack = load(root/"pack.json")
    outputs = compile_outputs(state)
    members = {
        "state.json": canonical(state)+b"\n",
        "pack.json": canonical(pack)+b"\n",
    }
    for name, obj in outputs.items():
        members[name] = canonical(obj)+b"\n"
    manifest_rows = [
        {"path": name, "bytes": len(data), "sha256": sha(data)}
        for name, data in sorted(members.items())
    ]
    manifest = {
        "schema":"axm/deep-tech-release-manifest@1",
        "target_id":state["target_selection"]["target_id"],
        "pack_id":pack["pack_id"],
        "pack_version":pack["version"],
        "members":manifest_rows,
        "manifest_sha256":sha(canonical(manifest_rows))
    }
    members["MANIFEST.json"] = canonical(manifest)+b"\n"
    release = {
        "schema":"axm/deep-tech-release-seal@1",
        "target_id":state["target_selection"]["target_id"],
        "state_sha256":sha(canonical(state)),
        "pack_sha256":sha(canonical(pack)),
        "manifest_sha256":manifest["manifest_sha256"],
        "public_only":state.get("meta",{}).get("public_only") is True,
        "external_effects":0
    }
    members["RELEASE.json"] = canonical(release)+b"\n"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as zf:
        for name, data in sorted(members.items()):
            zi = zipfile.ZipInfo(name, FIXED_TIME)
            zi.compress_type = zipfile.ZIP_STORED
            zi.create_system = 3
            zi.external_attr = 0o100644 << 16
            zf.writestr(zi, data)
    blob = out_path.read_bytes()
    return {"status":"PASS","target_id":release["target_id"],"release_sha256":sha(blob),"bytes":len(blob),"members":len(members),"manifest_sha256":manifest["manifest_sha256"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("state")
    ap.add_argument("--out", required=True)
    ap.add_argument("--root")
    args=ap.parse_args()
    print(json.dumps(freeze(args.state,args.out,args.root), sort_keys=True))

if __name__ == "__main__":
    main()
