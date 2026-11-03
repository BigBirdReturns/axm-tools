#!/usr/bin/env python3
"""Run two independent local witness identities against disagreeing synthetic exports."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from decision_floor.cli import execute
from decision_floor import peer


def run():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    output = a.output.expanduser().resolve()
    if ROOT == output or ROOT in output.parents:
        raise ValueError("Write the synthetic receipt outside the product installation")
    with tempfile.TemporaryDirectory(prefix="decision-peer-two-parties-") as td:
        root = Path(td)
        supplier = root / "supplier"
        buyer = root / "buyer"
        parties = [(supplier, "supplierA", "buyerB"),
                   (buyer, "buyerB", "supplierA")]
        for home, name, _ in parties:
            peer.init_party(home, name)
            shutil.copytree(ROOT / "sample_inputs" / "missed", home / "incoming")
        po = buyer / "incoming" / "procurement_po.csv"
        original = po.read_text()
        old = "PO-908-2,PLANT-07,VALVE-P204,2026-10,12000,"
        assert old in original
        po.write_text(original.replace(old,
                        "PO-908-2,PLANT-07,VALVE-P204,2026-10,7000,"))
        for home, _, _ in parties:
            from argparse import Namespace
            result = execute(Namespace(
                input=str(home / "incoming"),
                config=str(ROOT / "config" / "sources.json"),
                workspace=str(home / "state"),
                out=str(home / "report"), as_of=None))
            assert result["verification"]["status"] == "PASS"
        for home, name, other in parties:
            counterparty = buyer if home == supplier else supplier
            peer.trust_peer(home, other, counterparty / "public.pem")
            peer.install_contract(home, {
                "schema": peer.CONTRACT_SCHEMA,
                "contract_id": "CROSSPARTY-SYNTHETIC-01",
                "party": name, "counterparty": other,
                "scope": {"site": "PLANT-07", "sku": "VALVE-P204",
                          "period": "2026-10"},
                "allowed_kinds": ["decision", "commitment", "floor"],
                "allowed_fields": sorted(peer.REQUIRED), "max_records": 30})
        sent = peer.export_events(supplier, supplier / "state",
                                  "CROSSPARTY-SYNTHETIC-01")
        received = peer.receive(buyer, Path(sent["file"]), buyer / "state")
        assert received["status"] == "VERIFIED_REVIEW_REQUIRED"
        disagrees = [f for f in received["findings"]
                     if f["state"] == "CONTRADICTORY_RECORDED_VALUE"]
        assert [f["record_id"] for f in disagrees] == ["PO-908-2"]
        review = peer.respond(buyer, sent["packet_id"], "contested",
                              "Synthetic procurement controller")
        returned = peer.receive(supplier, Path(review["file"]),
                                supplier / "state")
        assert returned["findings"][0]["disposition"] == "contested"
        with open(sent["file"], "rb") as handle:
            raw = handle.read()
        tampered = json.loads(raw)
        tampered["payload"]["claims"][0]["quantity"] = 1
        tampered["payload_sha256"] = peer._sha(peer._canonical(tampered["payload"]))
        bad = root / "tampered.json"
        bad.write_bytes(peer._canonical(tampered))
        try:
            peer.receive(buyer, bad, buyer / "state")
            raise AssertionError("Tampered packet was incorrectly accepted")
        except ValueError:
            pass
        result = {
            "schema": "axm-decision-peer-demonstration/1",
            "status": "PASS",
            "scenario": "synthetic duplicated case, one intentionally altered buyer PO record",
            "parties": [n for _, n, _ in parties],
            "source_vaults_independent": True,
            "source_bytes_exchanged": 0,
            "signed_evidence_id": sent["packet_id"],
            "claims_disclosed": sent["claims"],
            "receipt": received["status"],
            "disagreements": disagrees,
            "corroborated_records": sum(f["state"] == "CORROBORATED_VALUE"
                                       for f in received["findings"]),
            "human_review_id": review["packet_id"],
            "returned_disposition": returned["findings"][0]["disposition"],
            "signature_tamper_rejected": True,
            "claimed_authority_authenticated_by_erp": False,
            "source_timestamp_externally_attested": False,
            "real_customer_systems_touched": False
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Will not replace an earlier demonstration receipt")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), **result}, indent=2))


if __name__ == "__main__":
    run()
