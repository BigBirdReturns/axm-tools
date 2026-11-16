#!/usr/bin/env python3
"""Qualified-real-engine LoRA mechanics test. Separate from signed production admission.

No model files are bundled. This helper starts and stops only the vLLM process it
creates, and runs with an explicit CUDA GPU UUID and localhost-only controller.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sovereign import SCHEMA, digest_file, canonical


def request(url, body=None, timeout=10):
    req = Request(url, data=canonical(body).encode() if body is not None else None,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def commands(python, registry, ledger, mode, adapter="quality"):
    args = [str(python), str(ROOT / "sovereign.py"), "--fixture-mode",
            "--registry", str(registry), "--ledger", str(ledger),
            mode, "--tenant", "probe", "--adapter", adapter, "--region", "us-west"]
    if mode == "revoke":
        args.append("--unload")
    result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=90)
    try:
        data = json.loads(result.stdout)
    except Exception:
        raise RuntimeError(f"{mode} failed: {result.stdout} {result.stderr}") from None
    if result.returncode or data.get("status") == "REFUSED":
        raise RuntimeError(f"{mode} refused: {data}")
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--adapter-dir", type=Path, required=True)
    p.add_argument("--venv", type=Path, required=True)
    p.add_argument("--gpu-uuid", required=True)
    p.add_argument("--port", type=int, default=18416)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if not (1 <= a.repeats <= 10) or not (1025 <= a.port <= 65535):
        p.error("bounded test requires 1-10 repeats and an unprivileged port")
    assert a.gpu_uuid.startswith("GPU-")
    base, adapter = a.model_dir.resolve(), a.adapter_dir.resolve()
    for fn in ("model.safetensors", "tokenizer.json"):
        if not (base / fn).is_file():
            raise RuntimeError(f"missing model source {fn}")
    for fn in ("adapter_model.safetensors", "adapter_config.json"):
        if not (adapter / fn).is_file():
            raise RuntimeError(f"missing adapter source {fn}")
    config = json.loads((adapter / "adapter_config.json").read_text())
    if config.get("base_model_name_or_path") != "Qwen/Qwen3-0.6B":
        raise RuntimeError("adapter source model mismatch")
    a.out.mkdir(parents=True, exist_ok=True)
    state = a.out / "state"
    state.mkdir(exist_ok=True)
    registry_file = state / "fixture_registry.json"
    token_hash = digest_file(base / "tokenizer.json")
    model_hash = digest_file(base / "model.safetensors")
    adapter_hash = digest_file(adapter / "adapter_model.safetensors")
    base_revision = "sha256:" + model_hash
    manifest = {
        "schema": SCHEMA, "artifact_root": os.path.commonpath([str(base), str(adapter)]),
        "pools": {"us-west": {
            "admin_url": f"http://127.0.0.1:{a.port}",
            "base_model": "Qwen/Qwen3-0.6B",
            "base_revision": base_revision,
            "served_model": "qwen3-06b-lab",
            "base_path": str(base),
            "base_files": {"model.safetensors": model_hash},
            "tokenizer_path": str(base),
            "tokenizer_files": {"tokenizer.json": token_hash},
            "tokenizer_primary": "tokenizer.json",
            "tokenizer_sha256": token_hash,
            "max_lora_rank": 16}},
        "tenants": {"probe": {"regions": ["us-west"], "adapters": ["quality"], "max_active": 1}},
        "adapters": {"quality": {
            "path": str(adapter), "base_model": "Qwen/Qwen3-0.6B",
            "base_revision": base_revision,
            "tokenizer_sha256": token_hash, "rank": config["r"],
            "files": {"adapter_config.json": digest_file(adapter / "adapter_config.json"),
                      "adapter_model.safetensors": adapter_hash}}}
    }
    registry_file.write_text(canonical(manifest))
    ledger = state / "admissions.jsonl"
    if ledger.exists():
        raise RuntimeError("refuse to reuse a prior test's ledger; choose fresh --out")
    try:
        request(f"http://127.0.0.1:{a.port}/v1/models", timeout=1)
        raise RuntimeError("requested port already has a server; never take it over")
    except (HTTPError, URLError, TimeoutError):
        pass
    command = [str(a.venv / "bin" / "vllm"), "serve", str(base),
               "--served-model-name", "qwen3-06b-lab",
               "--host", "127.0.0.1", "--port", str(a.port),
               "--dtype", "float16", "--max-model-len", "2048",
               "--max-num-seqs", "8", "--gpu-memory-utilization", "0.30",
               "--enable-prefix-caching", "--enforce-eager",
               "--enable-lora", "--max-loras", "4", "--max-cpu-loras", "8",
               "--max-lora-rank", "16"]
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": a.gpu_uuid, "VLLM_ALLOW_RUNTIME_LORA_UPDATING": "True",
                "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    log = (a.out / "vllm-server.log").open("w", encoding="utf-8")
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                               env=env, start_new_session=True)
    start = time.monotonic()
    rows = []
    failed = None
    try:
        while time.monotonic() - start < 130:
            if process.poll() is not None:
                raise RuntimeError(f"vLLM exited {process.returncode} before becoming healthy")
            try:
                with urlopen(f"http://127.0.0.1:{a.port}/health", timeout=3) as h:
                    if h.status == 200:
                        break
            except (HTTPError, URLError, TimeoutError):
                time.sleep(1)
        else:
            raise RuntimeError("vLLM did not become healthy in 130 seconds")
        warm_seconds = round(time.monotonic() - start, 3)
        for i in range(a.repeats):
            activated = commands(a.venv / "bin" / "python", registry_file, ledger, "activate")
            rec = activated["receipt"]["record"]
            t0 = time.perf_counter()
            answer = request(f"http://127.0.0.1:{a.port}/v1/completions",
                             {"model": rec["alias"], "prompt": "Name one measurable system property.",
                              "temperature": 0, "max_tokens": 32}, timeout=60)
            request_ms = round((time.perf_counter() - t0) * 1000, 3)
            if answer.get("model") != rec["alias"] or not answer.get("choices"):
                raise RuntimeError("adapter-specific generation did not return a valid result")
            usage = answer.get("usage", {})
            revoked = commands(a.venv / "bin" / "python", registry_file, ledger, "revoke")
            rows.append({
                "iteration": i + 1,
                "activation_ms": activated["activation_ms"],
                "generation_ms": request_ms,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "revoked_and_unloaded": bool(revoked.get("unloaded")),
                "adapter_alias": rec["alias"]
            })
            if not revoked.get("unloaded"):
                raise RuntimeError("adapter revocation succeeded but engine unload did not")
        from sovereign import Ledger
        evidence = Ledger(ledger).events()
        result = {
            "schema": "axm/sovereign-gpu-live-smoke@1",
            "status": "PASS",
            "model": "Qwen/Qwen3-0.6B",
            "source_adapter": "phh/Qwen3-0.6B-TLDR-Lora",
            "gpu_uuid_redacted": True,
            "gpu_name": "Quadro RTX 8000",
            "vllm_version": "0.33.0",
            "base_sha256": model_hash,
            "tokenizer_sha256": token_hash,
            "adapter_sha256": adapter_hash,
            "source_notice": "Public Apache-2.0 adapter; weights not redistributed",
            "admission_mode": "FIXTURE_ONLY; unsigned; not routable",
            "base_warm_seconds": warm_seconds,
            "runs": rows,
            "mean_activation_ms": round(statistics.mean(r["activation_ms"] for r in rows), 3),
            "max_activation_ms": max(r["activation_ms"] for r in rows),
            "journal_events": len(evidence),
            "journal_head": evidence[-1]["hash"] if evidence else None,
            "qualification": "real local engine mechanics; no enterprise IAM or sovereign multi-region certification"
        }
        (a.out / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
    except Exception as e:
        failed = str(e)
        (a.out / "FAILED.txt").write_text(failed)
        print("SMOKE_FAILED:", failed, flush=True)
        print((a.out / "vllm-server.log").read_text(errors="replace")[-5000:], flush=True)
        raise
    finally:
        # Terminate only this child process group, never unrelated engine services.
        import signal
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        log.close()


if __name__ == "__main__":
    main()
