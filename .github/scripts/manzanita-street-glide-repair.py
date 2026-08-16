#!/usr/bin/env python3
"""Apply bounded corrections to the Street Glide resolver and registration receipt."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


resolver_path = Path("manzanita-next/street-glide/resolve_scene.py")
resolver = resolver_path.read_text(encoding="utf-8")
resolver_anchor = '''    candidates = demo.get("scene_candidates", [])
    require(isinstance(candidates, list), "Scene candidates must be a list")
'''
resolver_replacement = '''    candidates = demo.get("scene_candidates", [])
    require(isinstance(candidates, list), "Scene candidates must be a list")
    prohibited_input = recursive_keys(candidates) & PROHIBITED_KEYS
    require(
        not prohibited_input,
        f"Scene input contains prohibited keys: {sorted(prohibited_input)}",
    )
'''
if "prohibited_input = recursive_keys(candidates)" not in resolver:
    require(resolver_anchor in resolver, "Cannot locate the scene-candidate admission boundary")
    resolver = resolver.replace(resolver_anchor, resolver_replacement, 1)
require(
    "Scene input contains prohibited keys" in resolver,
    "The prohibited-input refusal did not apply",
)
resolver_path.write_text(resolver, encoding="utf-8")

registration_path = Path("manzanita-next/street-glide/register_natural_border.py")
registration = registration_path.read_text(encoding="utf-8")
portable_anchor = '''def load_json(path: Path) -> dict[str, Any]:
'''
portable_function = '''def portable_path(path: Path) -> str:
    """Return a stable non-absolute receipt path without inventing source custody."""
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        relative = Path(path.name)
    return relative.as_posix()


'''
if "def portable_path(path: Path)" not in registration:
    require(portable_anchor in registration, "Cannot locate the registration path boundary")
    registration = registration.replace(portable_anchor, portable_function + portable_anchor, 1)
registration = registration.replace(
    '            "path": image_path.as_posix(),',
    '            "path": portable_path(image_path),',
)
require("portable_path(image_path)" in registration, "Portable image receipt did not apply")
registration_path.write_text(registration, encoding="utf-8")
