#!/usr/bin/env python3
from __future__ import annotations
import hashlib, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
PARTS=[{'path': 'hosted-stage-segments/hosted-stage-00.part', 'bytes': 2300, 'sha256': 'a83802f84e0c77598e98c313281f08b15b912f0887e5a8fdd37d1438f46605cb'}, {'path': 'hosted-stage-segments/hosted-stage-01.part', 'bytes': 2300, 'sha256': 'f9c23eb5bd31578eb9c583c7a8a911cfdedee501bd7908b14cdc8fee9ad65c8e'}, {'path': 'hosted-stage-segments/hosted-stage-02.part', 'bytes': 2300, 'sha256': '98af548b6e7ca023856774d7f6fc91a5110bb5005e353d7b6086630ec4191d80'}, {'path': 'hosted-stage-segments/hosted-stage-03.part', 'bytes': 2136, 'sha256': '64fed397e147a72da7acf4a316b8a01fe5a38f996b85e6f2f1827c4d51e2a41d'}]
EXPECTED_BYTES=9036
EXPECTED_SHA256="35444bbee4444a60622d0c66a5c97979425974c9f72affce6cf3c3352e95ee86"
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
out=bytearray()
for item in PARTS:
 p=ROOT/item["path"]
 if not p.is_file():raise SystemExit(f"REFUSED: missing hosted-stage segment {p}")
 b=p.read_bytes()
 if len(b)!=item["bytes"] or sha(b)!=item["sha256"]:raise SystemExit(f"REFUSED: hosted-stage segment drift {p}")
 out.extend(b)
if len(out)!=EXPECTED_BYTES or sha(out)!=EXPECTED_SHA256:raise SystemExit("REFUSED: reconstructed hosted_stage.py drift")
target=ROOT/"scripts"/"hosted_stage.py";target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
print(f"PASS: reconstructed {target} bytes={len(out)} sha256={sha(out)}")
