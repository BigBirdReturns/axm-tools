#!/usr/bin/env python3
"""Seal an admitted adapter binding through the *existing* AXM Genesis CLI.

The private key is supplied by its owner; this tool never invents a publisher key,
copies it, logs it or publishes it. The signed source and candidate ledger are
compiled by axm-build, and verified by the independent axm-verify.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sovereign import Registry, canonical, genesis_binding, Refusal


def within_existing_root(root: Path, target: Path):
    root = root.resolve(strict=True)
    target = target.resolve(strict=False)
    if not target.is_relative_to(root):
        raise Refusal("CUSTODY_ESCAPE", "sealed destination outside artifact root")
    return target


def seal(registry, tenant, adapter, region, private_key, trusted_key, axm_build, axm_verify):
    reg = Registry(registry)
    # Verify every weight, config and tokenizer byte first. Only the future
    # shard output path may be absent before signing.
    record = reg.evaluate(tenant, adapter, region)
    target = record.get("genesis_shard")
    if not target:
        raise Refusal("GENESIS_REQUIRED", "registry must declare genesis_shard destination")
    target = within_existing_root(reg.root, Path(target))
    if target.exists():
        raise Refusal("SHARD_EXISTS", "never overwrite an existing signed shard")
    if not Path(private_key).is_file() or not Path(trusted_key).is_file():
        raise Refusal("KEY_MISSING", "supply existing publisher key and independent trusted public key")
    if target.parent.resolve(strict=True) != target.parent:
        raise Refusal("SHARD_PARENT", "provide an existing canonical output parent")
    source = canonical(genesis_binding(record)).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="adapter-release-", dir=target.parent) as scratch:
        workspace = Path(scratch)
        content = workspace / "content"
        content.mkdir()
        (content / "source.txt").write_bytes(source)
        (workspace / "candidates.jsonl").write_text(canonical({
            "type": "entity", "namespace": "adapter-release",
            "label": record["alias"], "entity_type": "artifact",
        }) + "\n" + canonical({
            "type": "claim",
            "subject_label": record["alias"],
            "predicate": "has-verified-release-binding",
            "object_label": record["adapter_sha256"],
            "object_type": "literal:string",
            "tier": 4,
            "evidence": {
                "source_file": "source.txt", "byte_start": 0,
                "byte_end": len(source), "text": source.decode("utf-8")
            }
        }) + "\n", encoding="utf-8")
        out = workspace / "sealed"
        command = [
            axm_build, "compile", str(workspace / "candidates.jsonl"),
            str(content), str(out), "--private-key", str(private_key),
            "--namespace", f"sovereign/{record['region']}/{record['tenant']}/{record['adapter']}",
            "--title", f"Signed adapter admission: {record['alias']}",
            "--created-at", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "--license-spdx", "Apache-2.0",
        ]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=150)
        if compiled.returncode:
            raise Refusal("GENESIS_COMPILATION", compiled.stderr[-500:] or compiled.stdout[-500:])
        verified = subprocess.run([axm_verify, "shard", str(out), "--trusted-key", str(trusted_key)],
                                  capture_output=True, text=True, timeout=90)
        if verified.returncode:
            raise Refusal("GENESIS_VERIFICATION", verified.stderr[-500:] or verified.stdout[-500:])
        sealed_source = out / "content" / "source.txt"
        if not sealed_source.is_file() or sealed_source.read_bytes() != source:
            raise Refusal("GENESIS_SOURCE_MISMATCH",
                          "compiler must preserve exact canonical release binding")
        out.rename(target)
    return {"status": "SEALED_AND_VERIFIED", "path": str(target),
            "binding": genesis_binding(record), "verifier": "axm-verify"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--private-key", type=Path, required=True)
    ap.add_argument("--trusted-key", type=Path, required=True)
    ap.add_argument("--axm-build", default="axm-build")
    ap.add_argument("--axm-verify", default="axm-verify")
    a = ap.parse_args()
    try:
        print(canonical(seal(a.registry, a.tenant, a.adapter, a.region,
                             a.private_key, a.trusted_key, a.axm_build, a.axm_verify)))
    except (Refusal, OSError, RuntimeError, KeyError, ValueError, subprocess.TimeoutExpired) as e:
        print(canonical({"status": "REFUSED", "reason": str(e)[:500]}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
