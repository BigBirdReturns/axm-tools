from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import MaryError


def canonical_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes suitable for hashing and line records."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_strict(text: str, label: str = "JSON") -> Any:
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicates)
    except json.JSONDecodeError as exc:
        raise MaryError(f"invalid {label}: {exc}") from exc


def load_json(path: Path) -> Any:
    try:
        return loads_strict(path.read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise MaryError(f"cannot read {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    )
    temporary.replace(path)
