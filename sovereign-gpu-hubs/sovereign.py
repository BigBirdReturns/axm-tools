#!/usr/bin/env python3
"""Sovereign GPU Hubs: host-local, admission-gated multi-LoRA control plane.

Apache-2.0. stdlib only. Not a public inference gateway or a replacement
for AXM Genesis, Estate admission, identity, or a vLLM engine.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SCHEMA = "axm/sovereign-gpu-hubs@1"
HEX = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
GENESIS = "axm-verify"


class Refusal(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def require_id(s, field):
    if not isinstance(s, str) or not ID.fullmatch(s):
        raise Refusal("BAD_ID", f"{field} requires lowercase letters, digits, _ or -")
    return s


def require_hash(s, field):
    if not isinstance(s, str) or not HEX.fullmatch(s):
        raise Refusal("BAD_DIGEST", f"{field} requires a full SHA-256 hex digest")
    return s


def resolve_owned(root: Path, child: str, field: str) -> Path:
    if not child or not isinstance(child, str):
        raise Refusal("BAD_PATH", field)
    parent = root.resolve(strict=True)
    resolved = Path(child).resolve(strict=True)
    if not resolved.is_relative_to(parent):
        raise Refusal("CUSTODY_ESCAPE", f"{field} outside pinned artifact root")
    return resolved


def check_files(root, dirname, named_hashes, field):
    if not isinstance(named_hashes, dict) or not named_hashes:
        raise Refusal("UNVERIFIED_BYTES", f"{field} requires explicit file hashes")
    directory = resolve_owned(root, dirname, field)
    if not directory.is_dir():
        raise Refusal("BAD_PATH", f"{field} is not a directory")
    for filename, expected in named_hashes.items():
        require_hash(expected, f"{field}/{filename}")
        if not isinstance(filename, str) or not filename or Path(filename).is_absolute() or ".." in Path(filename).parts:
            raise Refusal("BAD_PATH", f"{field}/{filename}")
        f = resolve_owned(directory, str(directory / filename), f"{field}/{filename}")
        if not f.is_file() or digest_file(f) != expected:
            raise Refusal("HASH_MISMATCH", f"{field}/{filename}")
    return directory


def localhost_url(s):
    try:
        parsed = urlsplit(s)
        assert parsed.scheme == "http"
        assert parsed.hostname in ("127.0.0.1", "::1")
        assert parsed.port and not parsed.username and not parsed.password
        assert not parsed.path.strip("/") and not parsed.query and not parsed.fragment
    except (ValueError, AssertionError, TypeError):
        raise Refusal("UNTRUSTED_ADMIN_ENDPOINT", "vLLM administrator API must bind to loopback HTTP")
    return s.rstrip("/")


class Registry:
    def __init__(self, filename: Path):
        self.filename = filename
        data = json.loads(filename.read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            raise Refusal("SCHEMA", f"expected {SCHEMA}")
        self.data = data
        try:
            self.root = Path(data["artifact_root"]).resolve(strict=True)
            self.pools = data["pools"]
            self.tenants = data["tenants"]
            self.adapters = data["adapters"]
        except (KeyError, TypeError, OSError) as e:
            raise Refusal("REGISTRY", str(e)) from e

    def evaluate(self, tenant, adapter, region, *, check_bytes=True):
        require_id(tenant, "tenant")
        require_id(adapter, "adapter")
        require_id(region, "region")
        if not isinstance(self.tenants, dict) or tenant not in self.tenants:
            raise Refusal("TENANT_UNKNOWN", tenant)
        if not isinstance(self.pools, dict) or region not in self.pools:
            raise Refusal("REGION_UNKNOWN", region)
        if not isinstance(self.adapters, dict) or adapter not in self.adapters:
            raise Refusal("ADAPTER_UNKNOWN", adapter)
        t, p, a = self.tenants[tenant], self.pools[region], self.adapters[adapter]
        if region not in t.get("regions", []) or adapter not in t.get("adapters", []):
            raise Refusal("RESIDENCY_DENIED", f"{tenant}/{adapter} not admitted to {region}")
        localhost_url(p.get("admin_url"))
        if a.get("base_model") != p.get("base_model") or a.get("base_revision") != p.get("base_revision"):
            raise Refusal("BASE_MISMATCH", f"{adapter}/{region}")
        require_hash(p.get("tokenizer_sha256"), "pool.tokenizer_sha256")
        if a.get("tokenizer_sha256") != p["tokenizer_sha256"]:
            raise Refusal("TOKENIZER_MISMATCH", f"{adapter}/{region}")
        if a.get("rank", 0) > p.get("max_lora_rank", 0):
            raise Refusal("RANK_EXCEEDED", adapter)
        require_id(p.get("served_model"), "served_model")
        if not isinstance(t.get("max_active", 0), int) or t["max_active"] < 1:
            raise Refusal("TENANT_QUOTA", tenant)
        if check_bytes:
            check_files(self.root, p["base_path"], p["base_files"], "base")
            check_files(self.root, p["tokenizer_path"], p["tokenizer_files"], "tokenizer")
            primary = p["tokenizer_files"][p["tokenizer_primary"]]
            if primary != p["tokenizer_sha256"]:
                raise Refusal("TOKENIZER_PIN", "primary tokenizer digest differs")
            directory = check_files(self.root, a["path"], a["files"], "adapter")
            if "adapter_config.json" not in a["files"] or "adapter_model.safetensors" not in a["files"]:
                raise Refusal("ADAPTER_FILES", "pinned config and safetensors weights required")
            config = json.loads((directory / "adapter_config.json").read_text(encoding="utf-8"))
            if config.get("base_model_name_or_path") != p["base_model"] or config.get("r") != a["rank"]:
                raise Refusal("PEFT_MISMATCH", "adapter_config does not match pinned base/rank")
        else:
            directory = resolve_owned(self.root, a["path"], "adapter")
        alias = f"{tenant}-{adapter}-{a['files']['adapter_model.safetensors'][:12]}"
        shard = a.get("genesis_shard")
        if shard and check_bytes:
            # A future signed destination is allowed during pre-seal validation.
            # Existing ancestors/symlinks still resolve, and production verification
            # refuses an absent or invalid shard.
            dest = Path(shard).resolve(strict=False)
            if not dest.is_relative_to(self.root):
                raise Refusal("CUSTODY_ESCAPE", "genesis_shard outside pinned artifact root")
            shard = str(dest)
        return {"tenant": tenant, "adapter": adapter, "region": region, "alias": alias,
                "path": str(directory), "admin_url": p["admin_url"],
                "served_model": p["served_model"],
                "adapter_sha256": a["files"]["adapter_model.safetensors"],
                "base_revision": p["base_revision"], "tokenizer_sha256": p["tokenizer_sha256"],
                "genesis_shard": shard}


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def events(self):
        previous = "0" * 64
        records = []
        if not self.path.exists():
            return records
        with self.path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                try:
                    r = json.loads(line)
                    obj = {k: v for k, v in r.items() if k != "hash"}
                    if r.get("seq") != i or r.get("prev") != previous:
                        raise ValueError("sequence/previous hash mismatch")
                    actual = hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()
                    if actual != r.get("hash"):
                        raise ValueError("hash mismatch")
                    previous = actual
                    records.append(r)
                except (ValueError, TypeError, KeyError) as e:
                    raise Refusal("LEDGER_CORRUPT", f"line {i}: {e}") from e
        return records

    def append(self, op, subject, **attrs):
        records = self.events()
        item = {
            "seq": len(records) + 1,
            "prev": records[-1]["hash"] if records else "0" * 64,
            "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "op": op, "subject": subject, **attrs,
        }
        item["hash"] = hashlib.sha256(canonical(item).encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(canonical(item) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return item

    def routes(self):
        active, history = {}, {}
        for e in self.events():
            key = e.get("subject")
            if e["op"] in ("ACTIVATED", "ROLLED_BACK"):
                old = active.get(key)
                if old:
                    history.setdefault(key, []).append(old)
                active[key] = e["record"]
            elif e["op"] == "REVOKED":
                old = active.pop(key, None)
                if old:
                    history.setdefault(key, []).append(old)
        return active, history


@contextmanager
def exclusive_state(path):
    lock = Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.write(b"\0")
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def http_json(base, route, payload=None, timeout=35):
    base = localhost_url(base)
    req = Request(base + route, method="POST" if payload is not None else "GET",
                  data=canonical(payload).encode() if payload is not None else None,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            if response.status != 200:
                raise Refusal("ENGINE_STATUS", str(response.status))
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw.decode(errors="replace")
    except (HTTPError, URLError, TimeoutError) as e:
        raise Refusal("ENGINE_UNREACHABLE", str(e)) from e


def server_models(base):
    models = http_json(base, "/v1/models")
    if not isinstance(models, dict) or not isinstance(models.get("data"), list):
        raise Refusal("ENGINE_SCHEMA", "no /v1/models data")
    return {r.get("id") for r in models["data"] if isinstance(r, dict)}


def genesis_binding(record):
    """Exactly the bytes required inside verified Genesis content/source.txt."""
    return {
        "schema": "axm/adapter-release-binding@1",
        "tenant": record["tenant"], "adapter": record["adapter"],
        "region": record["region"], "alias": record["alias"],
        "served_model": record["served_model"],
        "base_revision": record["base_revision"],
        "tokenizer_sha256": record["tokenizer_sha256"],
        "adapter_sha256": record["adapter_sha256"]
    }


def verify_genesis(record, key, binary):
    shard = record.get("genesis_shard")
    if not shard or not key:
        raise Refusal("GENESIS_REQUIRED", "pinned shard and trusted public key required")
    # The actual standalone Genesis verifier checks the shard Merkle root and
    # trusted hybrid signatures, including all bytes of content/source.txt.
    result = subprocess.run([binary, "shard", shard, "--trusted-key", key],
                            capture_output=True, text=True, timeout=90, check=False)
    if result.returncode:
        raise Refusal("GENESIS_REJECTED", result.stderr[-300:] or result.stdout[-300:])
    source = Path(shard) / "content" / "source.txt"
    expected = canonical(genesis_binding(record)).encode("utf-8")
    if not source.is_file() or source.read_bytes() != expected:
        raise Refusal("GENESIS_BINDING_MISMATCH",
                      "valid signature must cover exact adapter/tenant/region/revision/digest binding")
    return True


def subject(tenant, adapter, region):
    return f"{region}/{tenant}/{adapter}"


def activate(reg, ledger, tenant, adapter, region, trusted_key=None, verifier=GENESIS, skip_genesis=False):
    key = subject(tenant, adapter, region)
    with exclusive_state(ledger.path):
        try:
            rec = reg.evaluate(tenant, adapter, region)
            if not skip_genesis:
                verify_genesis(rec, trusted_key, verifier)
            active, _ = ledger.routes()
            if key in active and active[key]["alias"] == rec["alias"]:
                return {"status": "ALREADY_ACTIVE", "record": active[key]}
            quota = reg.tenants[tenant]["max_active"]
            count = sum(1 for r in active.values() if r["tenant"] == tenant)
            if key not in active and count >= quota:
                raise Refusal("TENANT_QUOTA", f"{tenant} has {count}/{quota} active adapters")
            # Recheck presence of the warm base before touching the model server.
            models = server_models(rec["admin_url"])
            if rec["served_model"] not in models:
                raise Refusal("BASE_NOT_RESIDENT", rec["served_model"])
            start = time.perf_counter()
            if rec["alias"] not in models:
                http_json(rec["admin_url"], "/v1/load_lora_adapter",
                          {"lora_name": rec["alias"], "lora_path": rec["path"]}, timeout=65)
            if rec["alias"] not in server_models(rec["admin_url"]):
                raise Refusal("ADAPTER_NOT_VISIBLE", rec["alias"])
            duration_ms = round((time.perf_counter() - start) * 1000, 3)
            receipt = ledger.append("ACTIVATED", key, record=rec, activation_ms=duration_ms,
                                    verified=not skip_genesis,
                                    assertion="ENGINE_ACK_AND_MODELS_VISIBLE")
            return {"status": "ACTIVATED", "activation_ms": duration_ms, "receipt": receipt}
        except (Refusal, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            code = error.code if isinstance(error, Refusal) else "ACTIVATION_ERROR"
            ledger.append("ACTIVATION_FAILED", key, reason=code, detail=str(error)[:240])
            raise


def revoke(ledger, tenant, adapter, region, *, unload=False):
    key = subject(tenant, adapter, region)
    with exclusive_state(ledger.path):
        active, _ = ledger.routes()
        old = active.get(key)
        if not old:
            raise Refusal("NO_ACTIVE_ROUTE", key)
        receipt = ledger.append("REVOKED", key, alias=old["alias"])
        result = {"status": "REVOKED", "receipt": receipt}
        if unload:
            # Route is revoked before any potentially failing engine operation.
            try:
                http_json(old["admin_url"], "/v1/unload_lora_adapter", {"lora_name": old["alias"]})
                result["unloaded"] = True
                ledger.append("UNLOADED", key, alias=old["alias"])
            except Refusal as e:
                result["unloaded"] = False
                ledger.append("UNLOAD_FAILED", key, alias=old["alias"], reason=e.code)
        return result


def rollback(reg, ledger, tenant, adapter, region, trusted_key=None,
             verifier=GENESIS, skip_genesis=False):
    key = subject(tenant, adapter, region)
    with exclusive_state(ledger.path):
        try:
            candidate = reg.evaluate(tenant, adapter, region)
            if not skip_genesis:
                verify_genesis(candidate, trusted_key, verifier)
            active, history = ledger.routes()
            if not history.get(key):
                raise Refusal("NO_ROLLBACK", key)
            previous = history[key][-1]
            if previous["alias"] != candidate["alias"] or previous["adapter_sha256"] != candidate["adapter_sha256"]:
                raise Refusal("ROLLBACK_PIN_MISMATCH", key)
            models = server_models(candidate["admin_url"])
            if previous["alias"] not in models:
                raise Refusal("ROLLBACK_NOT_RESIDENT", previous["alias"])
            receipt = ledger.append("ROLLED_BACK", key, record=candidate,
                                    verified=not skip_genesis,
                                    replaced=active.get(key, {}).get("alias"))
            return {"status": "ROLLED_BACK", "receipt": receipt}
        except (Refusal, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            ledger.append("ROLLBACK_FAILED", key, reason=str(error)[:240])
            raise


def run_cli(args):
    ledger = Ledger(Path(args.ledger))
    if args.action == "verify-ledger":
        events = ledger.events()
        return {"status": "PASS", "events": len(events),
                "head": events[-1]["hash"] if events else "0" * 64}
    reg = Registry(Path(args.registry))
    if args.action == "doctor":
        issues = []
        for pool, cfg in reg.pools.items():
            require_id(pool, "pool")
            localhost_url(cfg["admin_url"])
            if not cfg.get("base_revision"):
                issues.append(f"{pool}: missing base revision")
        return {"status": "PASS" if not issues else "REFUSED", "pools": list(reg.pools), "issues": issues}
    if args.action == "inspect":
        return {"status": "PASS", "routes": ledger.routes()[0]}
    if args.action == "validate":
        r = reg.evaluate(args.tenant, args.adapter, args.region)
        if not args.fixture_mode:
            verify_genesis(r, args.trusted_key, args.verifier)
        return {"status": "VALIDATED", "record": r,
                "production_admitted": not args.fixture_mode}
    if args.action == "binding":
        r = reg.evaluate(args.tenant, args.adapter, args.region)
        return {"status": "BINDING_SOURCE", "source": genesis_binding(r)}
    if args.action == "activate":
        return activate(reg, ledger, args.tenant, args.adapter, args.region,
                        args.trusted_key, args.verifier, skip_genesis=args.fixture_mode)
    if args.action == "resolve":
        r = reg.evaluate(args.tenant, args.adapter, args.region)
        key = subject(args.tenant, args.adapter, args.region)
        active, _ = ledger.routes()
        if key not in active or active[key]["alias"] != r["alias"]:
            raise Refusal("NO_ACTIVE_ROUTE", key)
        latest = next((e for e in reversed(ledger.events()) if e.get("subject") == key
                       and e["op"] in ("ACTIVATED", "ROLLED_BACK", "REVOKED")), None)
        if latest is None or not latest.get("verified"):
            raise Refusal("UNVERIFIED_ROUTE", "fixture admission cannot become a production route")
        # Never route solely on stale durable state after a model-worker restart.
        if r["alias"] not in server_models(r["admin_url"]):
            raise Refusal("ADAPTER_NOT_RESIDENT", "previously admitted adapter is no longer loaded")
        # Clients receive the model alias and intended region, never the admin port.
        return {"status": "ROUTABLE", "region": args.region, "tenant": args.tenant,
                "model": r["alias"], "revision": r["base_revision"]}
    if args.action == "revoke":
        return revoke(ledger, args.tenant, args.adapter, args.region, unload=args.unload)
    if args.action == "rollback":
        return rollback(reg, ledger, args.tenant, args.adapter, args.region,
                        args.trusted_key, args.verifier, skip_genesis=args.fixture_mode)
    raise Refusal("UNKNOWN_OPERATION", args.action)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", default="registry.json")
    p.add_argument("--ledger", default="state/admissions.jsonl")
    p.add_argument("--fixture-mode", action="store_true", help="UNSAFE testing only: bypass Genesis verification")
    p.add_argument("--trusted-key", help="independent Genesis public key")
    p.add_argument("--verifier", default=GENESIS, help="operator-installed axm-verify binary")
    sp = p.add_subparsers(dest="action", required=True)
    for action in ("doctor", "verify-ledger", "inspect", "binding", "validate", "activate",
                   "resolve", "revoke", "rollback"):
        sub = sp.add_parser(action)
        if action in ("binding", "validate", "activate", "resolve", "revoke", "rollback"):
            for f in ("tenant", "adapter", "region"):
                sub.add_argument(f"--{f}", required=True)
        if action == "revoke":
            sub.add_argument("--unload", action="store_true")
    args = p.parse_args(argv)
    try:
        result = run_cli(args)
        print(canonical(result))
        return 0 if result.get("status") != "REFUSED" else 2
    except (Refusal, ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as e:
        code = e.code if isinstance(e, Refusal) else type(e).__name__
        print(canonical({"status": "REFUSED", "reason": code, "detail": str(e)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
