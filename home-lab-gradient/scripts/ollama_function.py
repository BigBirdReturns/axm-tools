#!/usr/bin/env python3
"""Bounded stdlib-only Ollama function adapter used by the first lab contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence


def canonical_sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    try:
        request_body = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2
    prompt = request_body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        print("input requires non-empty prompt", file=sys.stderr)
        return 2

    model_digest = None
    try:
        with urllib.request.urlopen(args.host.rstrip("/") + "/api/tags", timeout=min(args.timeout, 10.0)) as response:
            tags = json.loads(response.read().decode("utf-8"))
        for item in tags.get("models", []):
            if item.get("name") == args.model or item.get("model") == args.model:
                model_digest = item.get("digest")
                break
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        model_digest = None

    provider_request = {
        "model": args.model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": request_body.get("keep_alive", "5m"),
        "options": {
            "temperature": 0,
            "seed": 0,
        },
    }
    encoded = json.dumps(provider_request).encode("utf-8")
    request = urllib.request.Request(
        args.host.rstrip("/") + "/api/generate",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            provider = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ollama invocation failed: {exc}", file=sys.stderr)
        return 3

    text = provider.get("response")
    if not isinstance(text, str) or not text.strip():
        print("ollama returned no response text", file=sys.stderr)
        return 4

    result = {
        "schema": "axm-community-lab/bounded-local-inference-output@1",
        "status": "PASS",
        "model": str(provider.get("model") or args.model),
        "model_digest": model_digest,
        "prompt_sha256": canonical_sha256({"prompt": prompt}),
        "response": text,
        "provider": {
            "done": bool(provider.get("done")),
            "done_reason": provider.get("done_reason"),
            "prompt_eval_count": provider.get("prompt_eval_count"),
            "eval_count": provider.get("eval_count"),
            "total_duration_ns": provider.get("total_duration"),
            "load_duration_ns": provider.get("load_duration"),
            "prompt_eval_duration_ns": provider.get("prompt_eval_duration"),
            "eval_duration_ns": provider.get("eval_duration"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
