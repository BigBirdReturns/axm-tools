#!/usr/bin/env python3
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

GENERIC_SUFFIXES = {".json", ".md", ".py", ".html"}
EXCLUDED_GENERIC_PATHS = {"fixtures/reference-01.json", "QUALIFICATION.json"}
EXPECTED_OUTPUTS = ["admission-map.json", "diligence-map.json", "operating-readiness.json", "public-baseline.json"]


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add(checks, name, ok, detail=""):
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def unique(items, key):
    vals = [x[key] for x in items]
    return len(vals) == len(set(vals))


def basic_state_validate(state, checks, prefix):
    required = [
        "schema", "target_selection", "meta", "actors", "relationships", "instruments",
        "claims", "evidence", "capabilities", "rights", "authorities", "decisions",
        "exceptions", "qualification_plans", "stress_scenarios", "lineage", "successor_events"
    ]
    missing = [k for k in required if k not in state]
    add(checks, f"{prefix} required top-level keys", not missing, ",".join(missing))
    add(checks, f"{prefix} pack binding exact", state.get("meta", {}).get("sector_pack") == "AXM-DEEPTECH-001")
    add(checks, f"{prefix} public-only lane", state.get("meta", {}).get("public_only") is True)
    add(checks, f"{prefix} automatic selection false", state.get("target_selection", {}).get("automatic_selection") is False)
    add(checks, f"{prefix} selection receipt present", bool(state.get("target_selection", {}).get("selection_receipt")))
    bad_claims = []
    for c in state.get("claims", []):
        missing_fields = [k for k in ["id", "state", "text", "source_refs", "allowed_language", "prohibited_upgrade"] if k not in c]
        if missing_fields:
            bad_claims.append(f"{c.get('id', '?')}:{','.join(missing_fields)}")
    add(checks, f"{prefix} claims carry publication boundaries", not bad_claims, ";".join(bad_claims))
    bad_evidence = []
    for e in state.get("evidence", []):
        missing_fields = [k for k in ["id", "state", "source_refs", "proves", "does_not_prove"] if k not in e]
        if missing_fields:
            bad_evidence.append(f"{e.get('id', '?')}:{','.join(missing_fields)}")
    add(checks, f"{prefix} evidence carries proof boundaries", not bad_evidence, ";".join(bad_evidence))


def run_projection_battery(root, fixture_path, checks):
    state = load(root / fixture_path)
    label = state["target_selection"]["target_id"]
    basic_state_validate(state, checks, label)
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            [sys.executable, str(root / "scripts/compile_outputs.py"), str(root / fixture_path), "--out", td],
            capture_output=True, text=True
        )
        names = sorted(p.name for p in Path(td).glob("*.json"))
        ok = proc.returncode == 0 and names == EXPECTED_OUTPUTS
        add(checks, f"{label} compiles four projections", ok, "" if ok else (proc.stderr or str(names)))
        if proc.returncode == 0:
            admission = load(Path(td) / "admission-map.json")
            readiness = load(Path(td) / "operating-readiness.json")
            add(checks, f"{label} admission gaps remain explicit", bool(admission.get("required_company_controlled_record_classes")), str(admission.get("required_company_controlled_record_classes")))
            add(checks, f"{label} external effects remain held", readiness.get("ready_for_external_effects") is False)

    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a.zip"
        b = Path(td) / "b.zip"
        pa = subprocess.run([sys.executable, str(root / "scripts/freeze.py"), str(root / fixture_path), "--out", str(a), "--root", str(root)], capture_output=True, text=True)
        pb = subprocess.run([sys.executable, str(root / "scripts/freeze.py"), str(root / fixture_path), "--out", str(b), "--root", str(root)], capture_output=True, text=True)
        same = pa.returncode == 0 and pb.returncode == 0 and a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()
        detail = "" if same else ((pa.stderr or "") + (pb.stderr or ""))
        add(checks, f"{label} deterministic release rebuild", same, detail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--state")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    checks = []

    pack = load(root / "pack.json")
    add(checks, "pack identity exact", (pack.get("pack_id"), pack.get("version")) == ("AXM-DEEPTECH-001", "1.0.0"))
    ts = pack.get("target_selection", {})
    add(checks, "human target selection required", ts.get("human_required") is True and ts.get("automatic_discovery") is False and ts.get("machine_may_rank_unselected_targets") is False)
    add(checks, "zero external-effect adapters", pack.get("public_boundary", {}).get("external_effect_adapters") == 0)
    add(checks, "four product projections declared", [x["name"] for x in pack.get("outputs", [])] == ["Public Baseline", "Diligence Map", "Admission Map", "Operating Readiness"])
    add(checks, "eleven independent state tracks", len(pack.get("state_tracks", [])) == 11 and len(set(pack["state_tracks"])) == 11)
    add(checks, "transfer-control ids unique", unique(pack.get("transfer_controls", []), "id"))
    add(checks, "minimum transfer-control coverage", len(pack.get("transfer_controls", [])) >= 24, str(len(pack.get("transfer_controls", []))))
    add(checks, "successor event ids unique", unique(pack.get("successor_event_classes", []), "id"))
    add(checks, "nine successor event classes", len(pack.get("successor_event_classes", [])) == 9)
    add(checks, "portability gate ids unique", unique(pack.get("portability_acceptance_gates", []), "id"))
    add(checks, "ten portability gates", len(pack.get("portability_acceptance_gates", [])) == 10)

    fixture_paths = pack.get("synthetic_portability_fixtures", [])
    add(checks, "four synthetic portability shapes declared", len(fixture_paths) == 4 and len(set(fixture_paths)) == 4, str(fixture_paths))
    add(checks, "one reference fixture declared", pack.get("reference_fixtures") == ["fixtures/reference-01.json"])
    add(checks, "successor test fixture declared", pack.get("successor_test_fixture") == "fixtures/synthetic-successor-event.json")

    required_files = [
        "README.md", "CONSTITUTION.md", "PORTABILITY_ACCEPTANCE.md", "pack.json",
        "schemas/governed-state.schema.json", "schemas/technical-evidence.schema.json",
        "schemas/authority-rights.schema.json", "schemas/successor-event.schema.json",
        "templates/empty-target.json", "fixtures/reference-01.json",
        "fixtures/synthetic-target.json", "fixtures/synthetic-aerial.json",
        "fixtures/synthetic-defense-hardware.json", "fixtures/synthetic-industrial-robotics.json",
        "fixtures/synthetic-successor-event.json", "scripts/compile_outputs.py",
        "scripts/compile_successor.py", "scripts/freeze.py", "scripts/qualify_browser.py",
        "scripts/validate.py", "workbench.html", "BROWSER_QUALIFICATION.json",
    ]
    missing = [p for p in required_files if not (root / p).is_file()]
    add(checks, "required pack files present", not missing, ",".join(missing))

    for schema_path in [
        "schemas/governed-state.schema.json",
        "schemas/technical-evidence.schema.json",
        "schemas/authority-rights.schema.json",
        "schemas/successor-event.schema.json",
    ]:
        obj = load(root / schema_path)
        add(checks, f"{schema_path} parses and identifies schema", bool(obj.get("$schema") and obj.get("$id")), obj.get("$id", ""))

    successor_schema = load(root / "schemas/successor-event.schema.json")
    add(checks, "successor events bind exact target", "target_id" in successor_schema.get("required", []))

    ref = load(root / "fixtures/reference-01.json")
    forbidden_generic = [x.lower() for x in ref.get("forbidden_generic_tokens", [])]
    leaks = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in GENERIC_SUFFIXES:
            continue
        rel = p.relative_to(root).as_posix()
        if rel in EXCLUDED_GENERIC_PATHS or rel.startswith("fixtures/"):
            continue
        text = p.read_text(encoding="utf-8").lower()
        for token in forbidden_generic:
            if token in text:
                leaks.append(f"{rel}:{token}")
    add(checks, "generic code and policy contain no reference-target names", not leaks, ",".join(leaks))
    add(checks, "reference fixture isolates target-specific facts", ref.get("target_specific_code_required_by_pack") is False and ref.get("private_state_admitted") is False)
    add(checks, "reference fixture binds exact frozen commit and tree", bool(ref.get("frozen_demo_commit")) and bool(ref.get("frozen_demo_tree")))

    browser_receipt = load(root / "BROWSER_QUALIFICATION.json")
    add(checks, "browser qualification passes", browser_receipt.get("status") == "PASS" and browser_receipt.get("checks_passed") == browser_receipt.get("checks_total") == 24)
    add(checks, "browser external network and errors zero", not browser_receipt.get("external_runtime_network_requests") and not browser_receipt.get("browser_errors"))
    workbench = (root / "workbench.html").read_text(encoding="utf-8")
    add(checks, "workbench exposes four product views", all(x in workbench for x in ["Public Baseline", "Diligence Map", "Admission Map", "Operating Readiness"]))
    add(checks, "workbench contains no external URL literals", "http://" not in workbench and "https://" not in workbench)

    for fixture_path in fixture_paths:
        run_projection_battery(root, fixture_path, checks)

    event_path = root / pack["successor_test_fixture"]
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            [sys.executable, str(root / "scripts/compile_successor.py"), str(root / fixture_paths[0]), str(event_path), "--out", td],
            capture_output=True, text=True
        )
        delta_path, state_path = Path(td) / "successor-delta.json", Path(td) / "successor-state.json"
        ok = proc.returncode == 0 and delta_path.is_file() and state_path.is_file()
        add(checks, "material successor event compiles", ok, "" if ok else proc.stderr)
        if ok:
            delta = load(delta_path)
            successor = load(state_path)
            claim = next(c for c in successor["claims"] if c["id"] == "CLM-002")
            add(checks, "successor event target binding preserved", delta.get("target_id") == successor["target_selection"]["target_id"] == "SYNTHETIC-NMR-001")
            add(checks, "successor changes only declared prior state", len(delta.get("changes", [])) == 1 and claim.get("state") == "CORROBORATED")
            add(checks, "successor nonclaims retained", len(delta.get("nonclaims", [])) >= 2)
            add(checks, "successor lineage appended", any(x.get("event_id") == delta.get("event_id") for x in successor.get("lineage", [])))

    with tempfile.TemporaryDirectory() as td:
        bad_event = load(event_path)
        bad_event["target_id"] = "WRONG-TARGET"
        bad_path = Path(td) / "bad-event.json"
        bad_path.write_bytes(canonical(bad_event) + b"\n")
        proc = subprocess.run(
            [sys.executable, str(root / "scripts/compile_successor.py"), str(root / fixture_paths[0]), str(bad_path), "--out", str(Path(td) / "out")],
            capture_output=True, text=True
        )
        add(checks, "cross-target successor event fails closed", proc.returncode != 0)

    if args.state:
        basic_state_validate(load(Path(args.state)), checks, "supplied state")

    status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    manifest = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "QUALIFICATION.json":
            rel = p.relative_to(root).as_posix()
            if "__pycache__" in p.parts or p.suffix.lower() == ".pyc":
                continue
            if p.suffix.lower() == ".json":
                data = canonical(load(p))
                manifest.append({"path": rel, "canonical_json_bytes": len(data), "sha256": sha256_bytes(data), "hash_mode": "canonical_json"})
            else:
                data = p.read_bytes()
                manifest.append({"path": rel, "bytes": len(data), "sha256": sha256_bytes(data), "hash_mode": "raw_bytes"})
    qualification = {
        "schema": "axm/deep-tech-governance-qualification@1",
        "pack_id": "AXM-DEEPTECH-001",
        "version": "1.0.0",
        "status": status,
        "checks_passed": sum(c["status"] == "PASS" for c in checks),
        "checks_total": len(checks),
        "checks": checks,
        "manifest": manifest,
        "manifest_sha256": sha256_bytes(canonical(manifest)),
        "boundary": "Qualification proves target-neutral pack structure, four-shape portability, deterministic release construction, bounded successor transitions, reference-fixture isolation, and the public-only boundary. It does not select or qualify a real company."
    }
    if args.write:
        (root / "QUALIFICATION.json").write_text(json.dumps(qualification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "checks_passed": qualification["checks_passed"], "checks_total": qualification["checks_total"], "manifest_sha256": qualification["manifest_sha256"]}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
