"""Offline bilateral evidence envelopes. Source vaults never leave their owner's control.

Trust requires a manually pinned counterparty public key and a reciprocal,
scoped contract. Ed25519 signs the canonical disclosure. Signatures authenticate
the signing key, not an ERP, origin clock, or the underlying source's truth.
OpenSSL 3 or newer is required only for the peer-exchange commands; the core
investigator continues to use the Python standard library alone.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import base64
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile

from .core import parse_time

SCHEMA = "axm-decision-peer/1"
CONTRACT_SCHEMA = "axm-decision-peer-contract/1"
FIELDS = {"kind", "record_id", "quantity", "occurred_at", "recorded_at",
          "source_digest", "locator", "system", "authority", "status"}
REQUIRED = {"kind", "record_id", "quantity", "occurred_at", "recorded_at",
            "source_digest", "locator"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
DOMAIN = b"axm-decision-peer/1\x00"
MAX_PACKET = 250_000
MAX_RECORDS = 100


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write_new(path: Path, body: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _openssl():
    env = os.environ.get("DF_OPENSSL")
    if env:
        p = Path(env)
        if not p.is_file():
            raise RuntimeError("DF_OPENSSL does not point to a file")
        return str(p)
    found = shutil.which("openssl")
    if found:
        return found
    on_windows = Path("C:/Program Files/Git/usr/bin/openssl.exe")
    if on_windows.is_file():
        return str(on_windows)
    raise RuntimeError("The peer signing path requires a local OpenSSL executable")


def _run(args):
    p = subprocess.run([_openssl(), *map(str, args)], capture_output=True,
                       text=True, timeout=20)
    if p.returncode:
        raise ValueError("OpenSSL operation rejected the input: " +
                         p.stderr.strip()[:500])
    return p.stdout


def public_fingerprint(path: Path):
    if not path.is_file():
        raise ValueError("Public key file missing")
    # Hash the normalized DER SubjectPublicKeyInfo, not whitespace in PEM.
    with tempfile.TemporaryDirectory(prefix="df-key-") as folder:
        der = Path(folder) / "public.der"
        _run(["pkey", "-pubin", "-in", path, "-outform", "DER", "-out", der])
        return _sha(der.read_bytes())


def init_party(root: Path, party: str):
    root = Path(root)
    if not ID.fullmatch(party):
        raise ValueError("Invalid party identifier")
    if (root / "identity.json").exists() or (root / "private.pem").exists():
        raise FileExistsError("Party identity already initialized")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="df-init-") as temp:
        private = Path(temp) / "private.pem"
        public = Path(temp) / "public.pem"
        _run(["genpkey", "-algorithm", "ED25519", "-out", private])
        _run(["pkey", "-in", private, "-pubout", "-out", public])
        _write_new(root / "private.pem", private.read_bytes())
        _write_new(root / "public.pem", public.read_bytes())
    record = {"schema": SCHEMA, "party": party,
              "public_fingerprint": public_fingerprint(root / "public.pem")}
    _write_new(root / "identity.json", _canonical(record) + b"\n")
    return record


def _identity(root: Path):
    value = _json_file(root / "identity.json")
    if value.get("schema") != SCHEMA or not ID.fullmatch(value.get("party", "")):
        raise ValueError("Invalid local identity")
    if value.get("public_fingerprint") != public_fingerprint(root / "public.pem"):
        raise ValueError("Local identity public key changed")
    return value


def trust_peer(root: Path, party: str, public: Path):
    root = Path(root)
    my = _identity(root)
    if not ID.fullmatch(party) or party == my["party"]:
        raise ValueError("Invalid remote party")
    contents = Path(public).read_bytes()
    with tempfile.TemporaryDirectory(prefix="df-peer-") as tmp:
        p = Path(tmp) / "key.pem"
        p.write_bytes(contents)
        fingerprint = public_fingerprint(p)
    destination = root / "trust" / (party + ".pem")
    if destination.exists():
        if public_fingerprint(destination) != fingerprint:
            raise ValueError("Pinned counterparty key changed; explicit recovery needed")
        return {"party": party, "fingerprint": fingerprint, "existing": True}
    _write_new(destination, contents)
    return {"party": party, "fingerprint": fingerprint, "existing": False}


def install_contract(root: Path, config: dict):
    root = Path(root)
    me = _identity(root)
    if not isinstance(config, dict) or config.get("schema") != CONTRACT_SCHEMA:
        raise ValueError("Unsupported contract schema")
    for field in ("contract_id", "party", "counterparty"):
        if not ID.fullmatch(str(config.get(field, ""))):
            raise ValueError("Invalid contract identity: " + field)
    if config["party"] != me["party"] or config["counterparty"] == me["party"]:
        raise ValueError("Contract parties must be distinct and locally authorized")
    trust = root / "trust" / (config["counterparty"] + ".pem")
    if not trust.is_file():
        raise ValueError("Enroll the counterparty public key before the contract")
    scope = config.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"site", "sku", "period"}:
        raise ValueError("Contract scope must identify site, sku, period exactly")
    if any(not isinstance(v, str) or not 1 <= len(v) <= 120 for v in scope.values()):
        raise ValueError("Invalid scope values")
    kinds = config.get("allowed_kinds")
    if not isinstance(kinds, list) or not kinds or len(kinds) != len(set(kinds)):
        raise ValueError("Contract requires unique allowed record kinds")
    if not set(kinds) <= {"forecast", "decision", "promise", "plan", "commitment",
                         "floor", "outcome", "inventory_target", "unit_cost",
                         "sales_actual"}:
        raise ValueError("Unsupported record kind")
    fields = config.get("allowed_fields", [])
    if not isinstance(fields, list) or len(fields) != len(set(fields)) or not REQUIRED <= set(fields) <= FIELDS:
        raise ValueError("Contract needs mandatory receipt fields and explicit optional fields")
    cap = config.get("max_records", MAX_RECORDS)
    if type(cap) is not int or not (1 <= cap <= MAX_RECORDS):
        raise ValueError("Invalid disclosure maximum")
    # Store only the compact, validated contract, not arbitrary instructions.
    normalized = {"schema": CONTRACT_SCHEMA, "contract_id": config["contract_id"],
                  "party": me["party"], "counterparty": config["counterparty"],
                  "scope": scope, "allowed_kinds": kinds,
                  "allowed_fields": fields, "max_records": cap}
    path = root / "contracts" / (config["contract_id"] + ".json")
    value = _canonical(normalized) + b"\n"
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError("Existing contract cannot be overwritten")
        return normalized
    _write_new(path, value)
    return normalized


def _contract(root, contract_id):
    if not ID.fullmatch(contract_id):
        raise ValueError("Invalid contract identifier")
    c = _json_file(root / "contracts" / (contract_id + ".json"))
    install_contract(root, c)  # Revalidate identity, key enrollment, scope and fields.
    return c


def _sign(root, payload: bytes):
    with tempfile.TemporaryDirectory(prefix="df-sign-") as folder:
        message = Path(folder) / "message.bin"
        signed = Path(folder) / "signature.bin"
        message.write_bytes(DOMAIN + payload)
        _run(["pkeyutl", "-sign", "-rawin", "-inkey", root / "private.pem",
              "-in", message, "-out", signed])
        signature = signed.read_bytes()
    if len(signature) != 64:
        raise ValueError("Expected Ed25519 signature")
    return base64.b64encode(signature).decode("ascii")


def _verify(public: Path, payload: bytes, signature: str):
    try:
        raw = base64.b64decode(signature, validate=True)
    except Exception as exc:
        raise ValueError("Malformed signature") from exc
    if len(raw) != 64:
        raise ValueError("Unexpected signature size")
    with tempfile.TemporaryDirectory(prefix="df-check-") as folder:
        message = Path(folder) / "message.bin"
        sig = Path(folder) / "signature.bin"
        message.write_bytes(DOMAIN + payload)
        sig.write_bytes(raw)
        _run(["pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", public,
              "-in", message, "-sigfile", sig])


def _next_predecessor(root: Path, contract_id: str, recipient: str):
    folder = root / "outbox"
    found = []
    if folder.is_dir():
        for path in folder.glob("*.json"):
            packet = _json_file(path)
            p = packet.get("payload", {})
            if p.get("contract_id") == contract_id and p.get("recipient") == recipient:
                found.append((p.get("created_at", ""), packet["payload_sha256"]))
    return sorted(found)[-1][1] if found else None


def _envelope(root: Path, payload: dict):
    identity = _identity(root)
    if payload["sender"] != identity["party"]:
        raise ValueError("Cannot sign for another party")
    raw = _canonical(payload)
    signature = _sign(root, raw)
    _verify(root / "public.pem", raw, signature)
    return {"schema": SCHEMA, "payload": payload, "payload_sha256": _sha(raw),
            "public_fingerprint": identity["public_fingerprint"],
            "algorithm": "Ed25519", "signature": signature}


def _save_outbox(root, packet):
    path = root / "outbox" / (packet["payload_sha256"] + ".json")
    _write_new(path, _canonical(packet) + b"\n")
    return path


def export_events(root: Path, workspace: Path, contract_id: str):
    root = Path(root)
    c = _contract(root, contract_id)
    dbpath = Path(workspace) / "evidence.sqlite3"
    if not dbpath.is_file():
        raise FileNotFoundError("Source evidence index is missing; ingest before disclosure")
    with closing(sqlite3.connect(dbpath)) as db:
        db.row_factory = sqlite3.Row
        scope = c["scope"]
        matches = [dict(row) for row in db.execute(
            "SELECT * FROM events WHERE site=? AND sku=? AND period=? "
            "ORDER BY occurred_at,recorded_at,id",
            (scope["site"], scope["sku"], scope["period"]))]
    allowed = set(c["allowed_kinds"])
    fields = set(c["allowed_fields"])
    selected = [r for r in matches if r["kind"] in allowed]
    if len(selected) > c["max_records"]:
        raise ValueError("Scope exceeds contract disclosure ceiling")
    if not selected:
        raise ValueError("No eligible records under contract")
    claims = []
    for event in selected:
        sh = event["source_digest"]
        source = Path(workspace) / "vault" / "objects" / sh
        if not HEX.fullmatch(sh) or not source.is_file() or _sha(source.read_bytes()) != sh:
            raise ValueError("Original source missing or altered; export refused")
        claim = {name: event[name] for name in sorted(fields)}
        claims.append(claim)
    payload = {"schema": SCHEMA, "type": "evidence",
               "sender": c["party"], "recipient": c["counterparty"],
               "contract_id": c["contract_id"], "scope": c["scope"],
               "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds"),
               "nonce": secrets.token_hex(12),
               "predecessor": _next_predecessor(root, contract_id, c["counterparty"]),
               "claims": claims}
    packet = _envelope(root, payload)
    path = _save_outbox(root, packet)
    return {"packet_id": packet["payload_sha256"], "file": str(path),
            "claims": len(claims), "scope": c["scope"],
            "source_bytes_disclosed": 0}


def _validated(root: Path, raw: bytes, expected_type=None):
    if len(raw) > MAX_PACKET:
        raise ValueError("Packet too large")
    packet = json.loads(raw)
    if not isinstance(packet, dict) or set(packet) != {
            "schema", "payload", "payload_sha256", "public_fingerprint",
            "algorithm", "signature"}:
        raise ValueError("Invalid envelope keys")
    if packet["schema"] != SCHEMA or packet["algorithm"] != "Ed25519":
        raise ValueError("Unsupported signed envelope")
    payload = packet["payload"]
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("Unsupported payload")
    if expected_type and payload.get("type") != expected_type:
        raise ValueError("Unexpected payload kind")
    identity = _identity(root)
    sender, recipient = payload.get("sender"), payload.get("recipient")
    if not isinstance(sender, str) or not ID.fullmatch(sender) or recipient != identity["party"]:
        raise ValueError("Recipient or sender identity mismatch")
    contract_id = payload.get("contract_id")
    c = _contract(root, contract_id)
    if sender != c["counterparty"] or recipient != c["party"]:
        raise ValueError("Counterparty outside contract")
    public = root / "trust" / (sender + ".pem")
    if packet["public_fingerprint"] != public_fingerprint(public):
        raise ValueError("Counterparty key not pinned")
    if payload.get("scope") != c["scope"]:
        raise ValueError("Scope outside authorized contract")
    if not isinstance(payload.get("created_at"), str) or not parse_time(payload["created_at"]):
        raise ValueError("Created time requires timezone")
    if not isinstance(payload.get("nonce"), str) or not re.fullmatch("[0-9a-f]{24}", payload["nonce"]):
        raise ValueError("Invalid nonce")
    prev = payload.get("predecessor")
    if prev is not None and (not isinstance(prev, str) or not HEX.fullmatch(prev)):
        raise ValueError("Invalid predecessor")
    if payload.get("type") == "evidence":
        if set(payload) != {"schema", "type", "sender", "recipient", "contract_id",
                            "scope", "created_at", "nonce", "predecessor", "claims"}:
            raise ValueError("Invalid evidence payload")
        claims = payload["claims"]
        if not isinstance(claims, list) or not (1 <= len(claims) <= c["max_records"]):
            raise ValueError("Invalid disclosed record count")
        for claim in claims:
            if not isinstance(claim, dict) or set(claim) != set(c["allowed_fields"]):
                raise ValueError("Evidence fields depart from the local disclosure contract")
            if claim["kind"] not in c["allowed_kinds"]:
                raise ValueError("Disallowed claim category")
            if not isinstance(claim["record_id"], str) or len(claim["record_id"]) > 256:
                raise ValueError("Invalid event identifier")
            if not HEX.fullmatch(str(claim["source_digest"])):
                raise ValueError("Invalid source digest")
            if not isinstance(claim["locator"], str) or len(claim["locator"]) > 200:
                raise ValueError("Invalid source locator")
            for t in ("occurred_at", "recorded_at"):
                if claim[t] is not None:
                    parse_time(claim[t])
            if claim["recorded_at"] and (parse_time(claim["recorded_at"]) < parse_time(claim["occurred_at"])):
                raise ValueError("Recorded clock predates claimed event")
            q = claim["quantity"]
            if q is not None and (type(q) not in (float, int) or not math.isfinite(q)):
                raise ValueError("Invalid quantity")
    elif payload.get("type") == "review":
        if set(payload) != {"schema", "type", "sender", "recipient", "contract_id",
                            "scope", "created_at", "nonce", "predecessor",
                            "reply_to", "disposition", "authority"}:
            raise ValueError("Invalid review payload")
        if not HEX.fullmatch(str(payload["reply_to"])):
            raise ValueError("Invalid review reference")
        if payload["disposition"] not in ("acknowledged", "contested", "evidence_required"):
            raise ValueError("Unsupported human disposition")
        if not isinstance(payload["authority"], str) or not 1 <= len(payload["authority"]) <= 120:
            raise ValueError("Review must name accountable human authority")
    else:
        raise ValueError("Unknown packet type")
    canonical = _canonical(payload)
    if _sha(canonical) != packet["payload_sha256"]:
        raise ValueError("Signed payload digest differs")
    _verify(public, canonical, packet["signature"])
    return packet, c


def _compare(workspace, c, packet):
    dbpath = Path(workspace) / "evidence.sqlite3" if workspace is not None else None
    if dbpath is None or not dbpath.is_file():
        return [{"finding": "NO_LOCAL_INDEX", "state": "evidence_required"}]
    scope = c["scope"]
    with closing(sqlite3.connect(dbpath)) as db:
        db.row_factory = sqlite3.Row
        local = [dict(row) for row in db.execute(
            "SELECT kind,record_id,occurred_at,quantity,source_digest FROM events "
            "WHERE site=? AND sku=? AND period=?",
            (scope["site"], scope["sku"], scope["period"]))]
    index = {}
    for event in local:
        key = (event["kind"], event["record_id"], event["occurred_at"])
        index.setdefault(key, []).append(event)
    findings = []
    for claim in packet["payload"]["claims"]:
        key = (claim["kind"], claim["record_id"], claim["occurred_at"])
        ours = index.get(key, [])
        if not ours:
            status = "NO_IDENTICAL_LOCAL_EVENT"
        elif any(v["quantity"] == claim["quantity"] for v in ours):
            status = "CORROBORATED_VALUE"
        else:
            status = "CONTRADICTORY_RECORDED_VALUE"
        findings.append({"kind": claim["kind"], "record_id": claim["record_id"],
                         "occurred_at": claim["occurred_at"],
                         "state": status, "local_matches": len(ours),
                         "remote_source_digest": claim["source_digest"]})
    return findings


def receive(root: Path, source: Path, workspace: Path | None = None):
    root = Path(root)
    raw = Path(source).read_bytes()
    packet, c = _validated(root, raw)
    payload = packet["payload"]
    msg = packet["payload_sha256"]
    path = root / "inbox" / (msg + ".json")
    if path.exists():
        if path.read_bytes() != _canonical(packet) + b"\n":
            raise ValueError("Immutable inbox packet changed")
        return {"status": "DUPLICATE", "packet_id": msg}
    prev = payload["predecessor"]
    prior = []
    for existing in (root / "inbox").glob("*.json") if (root / "inbox").is_dir() else []:
        item, _ = _validated(root, existing.read_bytes())
        if existing.stem != item["payload_sha256"]:
            raise ValueError("Prior inbox envelope hash changed")
        earlier = item["payload"]
        if earlier.get("sender") == payload["sender"] and earlier.get("contract_id") == payload["contract_id"]:
            prior.append((earlier.get("created_at", ""), item["payload_sha256"]))
    expected = sorted(prior)[-1][1] if prior else None
    if prev != expected:
        raise ValueError("Exchange chain gap or fork; prior signed packet is not the current predecessor")
    if payload["type"] == "review":
        if not (root / "outbox" / (payload["reply_to"] + ".json")).exists():
            raise ValueError("Human review references an unknown local outbound packet")
        findings = [{"state": "HUMAN_DISPOSITION", "disposition": payload["disposition"],
                     "authority": payload["authority"], "reply_to": payload["reply_to"]}]
    else:
        findings = _compare(workspace, c, packet)
    # The immutable original envelope is stored apart from the independently
    # computed local reconciliation, which can change after new evidence.
    _write_new(path, _canonical(packet) + b"\n")
    _write_new(root / "findings" / (msg + ".json"),
               _canonical({"packet_id": msg, "findings": findings,
                           "computed_at": dt.datetime.now(dt.timezone.utc).isoformat()}) + b"\n")
    return {"status": "VERIFIED_REVIEW_REQUIRED" if any(
                x.get("state") in ("CONTRADICTORY_RECORDED_VALUE",
                                   "NO_IDENTICAL_LOCAL_EVENT", "evidence_required")
                for x in findings) else "VERIFIED_RECORDED",
            "packet_id": msg, "message_type": payload["type"],
            "findings": findings, "source_bytes_imported": 0}


def respond(root: Path, message_id: str, disposition: str, authority: str):
    root = Path(root)
    if not HEX.fullmatch(message_id):
        raise ValueError("Invalid message ID")
    if disposition not in ("acknowledged", "contested", "evidence_required"):
        raise ValueError("Invalid human review disposition")
    if not isinstance(authority, str) or not 1 <= len(authority) <= 120:
        raise ValueError("Named decision authority required")
    original = root / "inbox" / (message_id + ".json")
    if not original.is_file():
        raise ValueError("Review requires a previously received packet")
    packet = _json_file(original)
    payload = packet["payload"]
    if payload.get("type") != "evidence":
        raise ValueError("Review responds only to evidence")
    c = _contract(root, payload["contract_id"])
    review = {"schema": SCHEMA, "type": "review", "sender": c["party"],
              "recipient": c["counterparty"], "contract_id": c["contract_id"],
              "scope": c["scope"],
              "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds"),
              "nonce": secrets.token_hex(12),
              "predecessor": _next_predecessor(root, c["contract_id"], c["counterparty"]),
              "reply_to": message_id, "disposition": disposition, "authority": authority}
    envelope = _envelope(root, review)
    return {"file": str(_save_outbox(root, envelope)),
            "packet_id": envelope["payload_sha256"],
            "type": "human_review", "disposition": disposition}


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline sovereign decision-witness exchange")
    subs = p.add_subparsers(dest="command", required=True)
    for name in ("init", "trust", "contract", "export", "receive", "review"):
        sub = subs.add_parser(name)
        sub.add_argument("--root", required=True, type=Path)
        if name == "init":
            sub.add_argument("--party", required=True)
        elif name == "trust":
            sub.add_argument("--party", required=True)
            sub.add_argument("--key", required=True, type=Path)
        elif name == "contract":
            sub.add_argument("--file", required=True, type=Path)
        elif name == "export":
            sub.add_argument("--workspace", required=True, type=Path)
            sub.add_argument("--contract", required=True)
        elif name == "receive":
            sub.add_argument("--file", required=True, type=Path)
            sub.add_argument("--workspace", type=Path)
        elif name == "review":
            sub.add_argument("--reply-to", required=True)
            sub.add_argument("--disposition", required=True,
                             choices=["acknowledged", "contested", "evidence_required"])
            sub.add_argument("--authority", required=True)
    args = p.parse_args(argv)
    if args.command == "init": result = init_party(args.root, args.party)
    elif args.command == "trust": result = trust_peer(args.root, args.party, args.key)
    elif args.command == "contract": result = install_contract(args.root, _json_file(args.file))
    elif args.command == "export": result = export_events(args.root, args.workspace, args.contract)
    elif args.command == "receive": result = receive(args.root, args.file, args.workspace)
    elif args.command == "review": result = respond(args.root, args.reply_to,
                                                    args.disposition, args.authority)
    else: raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
