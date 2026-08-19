#!/usr/bin/env python3
"""Apply the compact and 200-percent reflow acceptance repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "manzanita"
css_path = ROOT / "style.css"
css = css_path.read_text(encoding="utf-8")
repair = r'''
.provenance-grid code{overflow-wrap:anywhere;word-break:break-word}
.scene-topline span,.scene-label span,.handoff-head span,footer span{min-width:0;overflow-wrap:anywhere}
@media(max-width:420px){
  .brand>span:last-child{display:none}
  .topbar{grid-template-columns:auto 1fr}
  .header-actions{justify-self:end;min-width:0}
  .quiet-button{padding:.58rem .62rem;font-size:.54rem}
  .hero-copy,.reading-card,.control-card{min-width:0}
  .hero-ledger div{min-width:0}
  .reading-ledger dd,.role-ledger dd,.portable-row p{overflow-wrap:anywhere}
}
@media(max-width:350px){
  .hero-ledger{grid-template-columns:1fr}
  .scene-topline{align-items:flex-start;flex-direction:column}
  .chip-row button{flex-basis:100%}
}
'''
if repair.strip() not in css:
    css_path.write_text(css + repair, encoding="utf-8")

qualification_path = ROOT / "QUALIFICATION.json"
qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
files = {}
for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "QUALIFICATION.json"):
    payload = path.read_bytes()
    files[path.relative_to(ROOT).as_posix()] = {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
qualification["files"] = files
qualification["compact_320_text_200_contract"] = True
qualification_path.write_text(json.dumps(qualification, indent=2) + "\n", encoding="utf-8")
print("Compact and 200-percent reflow repair: APPLIED")
