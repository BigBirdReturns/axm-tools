#!/usr/bin/env python3
"""Deterministic static qualification for DDV-PEL-003."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "DDV-PEL-003/0.3.0"
EXPECTED_ARRAY_COUNTS = {
    "founder_decisions": 10,
    "invariants": 40,
    "state_model": 44,
    "counterparties": 18,
    "instruments": 14,
    "claims": 54,
    "evidence": 13,
    "rights": 10,
    "exceptions": 28,
    "intake": 0,
    "sources": 14,
    "role_profiles": 7,
    "apertures": 4,
    "stress_scenarios": 10,
    "lineage": 13,
    "qualification_plans": 26,
}
EXPECTED_PARTS = [
    "meta", "founder_decisions", "invariants", "state_model", "counterparties",
    "instruments", "claims", "evidence", "rights", "exceptions", "intake",
    "sources", "lists", "schema", "role_profiles", "apertures",
    "stress_scenarios", "lineage", "qualification_plans",
]

checks: list[dict[str, object]] = []

def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_public() -> dict:
    js = r"""
const fs=require('fs'),vm=require('vm'),path=require('path');
const root=process.argv[1];
const dir=path.join(root,'data','parts');
const ctx={window:{}}; vm.createContext(ctx);
for(const name of fs.readdirSync(dir).filter(x=>x.endsWith('.js')).sort((a,b)=>a==='bootstrap.js'?-1:b==='bootstrap.js'?1:a.localeCompare(b))){
  vm.runInContext(fs.readFileSync(path.join(dir,name),'utf8'),ctx,{filename:name});
}
process.stdout.write(JSON.stringify(ctx.window.__PELAGOS_PUBLIC_PARTS__||{}));
"""
    out = subprocess.run(
        ["node", "-e", js, str(ROOT)], capture_output=True, text=True
    )
    if out.returncode:
        raise RuntimeError(f"node public-cartridge loader failed: {out.stderr}")
    return json.loads(out.stdout)


def main() -> int:
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    standalone = (ROOT / "standalone.html").read_text(encoding="utf-8")

    refs = re.findall(r'(?:src|href)="([^"]+)"', index)
    local_refs = [r for r in refs if not r.startswith(("http:", "https:", "#", "data:"))]
    missing = [r for r in local_refs if not (ROOT / r).exists()]
    check("all index resources exist", not missing, ", ".join(missing))

    js_files = sorted((ROOT / "app").glob("*.js")) + sorted((ROOT / "data" / "parts").glob("*.js"))
    syntax_failures = []
    for path in js_files:
        proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        if proc.returncode:
            syntax_failures.append(f"{path.relative_to(ROOT)}: {proc.stderr.strip()}")
    check("all JavaScript parses", not syntax_failures, " | ".join(syntax_failures))

    public = load_public()
    check("all required public parts load", list(public.keys()) == EXPECTED_PARTS,
          f"loaded={list(public.keys())}")
    check("schema declares exact required parts",
          public.get("schema", {}).get("required_public_parts") == EXPECTED_PARTS,
          str(public.get("schema", {}).get("required_public_parts")))
    check("release identity exact",
          public.get("meta", {}).get("artifact_id") == "DDV-PEL-003" and
          public.get("meta", {}).get("version") == "0.3.0",
          json.dumps(public.get("meta", {}), sort_keys=True))
    check("zero external-effect adapters declared",
          public.get("meta", {}).get("external_effect_adapters") == 0 and
          public.get("schema", {}).get("external_effect_law") == "All external effects remain absent and held.")
    check("zero committed private source bytes",
          public.get("meta", {}).get("source_bytes_committed") == 0)

    for key, count in EXPECTED_ARRAY_COUNTS.items():
        value = public.get(key)
        check(f"{key} count", isinstance(value, list) and len(value) == count,
              f"expected={count} actual={len(value) if isinstance(value, list) else type(value).__name__}")

    claims = public.get("claims", [])
    risky = [c for c in claims if c.get("Risk") in {"High", "Critical"}]
    plans = public.get("qualification_plans", [])
    plan_ids = {p.get("claim_id") for p in plans}
    missing_plans = [c.get("Claim ID") for c in risky if c.get("Claim ID") not in plan_ids]
    check("every high/critical claim has a prospective qualification plan", not missing_plans,
          ", ".join(filter(None, missing_plans)))

    bounded_fields = ["Allowed External Language", "Prohibited Upgrade", "Review Trigger", "Proposed Owner", "Sources"]
    unbounded = [c.get("Claim ID") for c in claims if any(not str(c.get(k, "")).strip() for k in bounded_fields)]
    check("every claim carries complete publication boundary", not unbounded,
          ", ".join(filter(None, unbounded)))

    # Privacy and public-release boundary. Public founder and partner names are expected;
    # the private introduction bodies, personal email addresses, and private offer text are not.
    public_paths = [ROOT / "index.html", ROOT / "standalone.html", ROOT / "README.md", ROOT / "CONSTITUTION.md", ROOT / "LINEAGE.md", ROOT / "app.css"]
    public_paths += sorted((ROOT / "app").glob("*.js"))
    public_paths += sorted((ROOT / "data" / "parts").glob("*.js"))
    all_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in public_paths)
    forbidden = [
        "jvssandhu@gmail.com", "samuel@pelagosfrontier.com",
        "Jonathan is very smart and more importantly strangely competent",
        "Robi's timing is pretty perfect", "Robi’s timing is pretty perfect",
        "This going to be short. Samuel",
    ]
    leaked = [x for x in forbidden if x.lower() in all_text.lower()]
    check("private introduction and email bodies are absent", not leaked, ", ".join(leaked))

    # Runtime constraints. Source URLs may be displayed as user-clicked links; code may not call them.
    runtime_text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").glob("*.js"))
    check("runtime actively disables network APIs",
          "window.fetch = () => Promise.reject" in runtime_text and
          "XMLHttpRequest.prototype.open=deny" in runtime_text and
          "window.WebSocket=function(){deny()}" in runtime_text)
    prohibited_adapters = ["mailto:", "navigator.sendBeacon", "new WebSocket(", "new EventSource("]
    adapter_hits = [x for x in prohibited_adapters if x in runtime_text]
    check("no send, beacon, socket, or mail adapter", not adapter_hits, ", ".join(adapter_hits))
    check("successor-state intake is present",
          "intake_successor_recorded" in runtime_text and "supersedes:prior?.id||null" in runtime_text)
    check("workspace admission is present",
          "workspace_admitted" in runtime_text and "workspace_admission" in runtime_text)
    check("authority-attributed local object requires authority and source",
          "sources.length)?'authority-attributed':'draft'" in runtime_text)
    check("single-writer boundary is explicit",
          "single_writer:true" in runtime_text and "One custodian holds the current workspace" in runtime_text)

    check("standalone bundle has no local resource dependencies",
          '<script src=' not in standalone and '<link rel="stylesheet"' not in standalone)
    check("standalone bundle identifies exact release",
          'DDV-PEL-003/0.3.0' in standalone and 'ddv-offline-bundle' in standalone)
    check("standalone CSP blocks network",
          "default-src 'none'" in standalone and "connect-src 'none'" in standalone)

    docs = (ROOT / "README.md").read_text(encoding="utf-8") + "\n" + (ROOT / "CONSTITUTION.md").read_text(encoding="utf-8")
    check("operator manual states readiness and admission boundary",
          "ready for immediate founder-controlled use" in docs and "Pelagos admission required" in docs)
    check("constitution preserves successor states",
          "Local object changes create successors, not overwrites" in docs)

    # Hash every release file except the generated qualification record itself.
    tracked = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "QUALIFICATION.json"):
        tracked.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })

    result = {
        "schema": "ddv/pelagos-governance-qualification@1",
        "release": RELEASE,
        "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
        "checks_passed": sum(c["status"] == "PASS" for c in checks),
        "checks_total": len(checks),
        "checks": checks,
        "files": tracked,
        "boundary": "Static qualification proves the committed candidate and its local operating mechanics. It does not create Pelagos admission, validate private instruments, or authorize external effects.",
    }
    out = ROOT / "QUALIFICATION.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"{result['status']} {result['checks_passed']}/{result['checks_total']} static qualification cells")
    for c in checks:
        print(f"[{c['status']}] {c['name']}{': ' + str(c['detail']) if c['detail'] else ''}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
