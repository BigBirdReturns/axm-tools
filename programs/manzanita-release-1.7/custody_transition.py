#!/usr/bin/env python3
"""Apply the admitted public-route custody transition to Manzanita v1.7.0.

The repository already contains the tested v1.6 transition mechanism. This
wrapper imports that mechanism, replaces only release/predecessor identities
with the exact current route donor, invokes its custody mode, and then requires
the ordinary custody builder, validator, adversarial suite, and history audit
to pass. It does not manufacture a missing external campaign or task row.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

RELEASE = "1.7.0"
PREDECESSOR_RELEASE = "1.6.0"
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(("git", *args), cwd=repo, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--predecessor-commit", required=True)
    parser.add_argument("--product-commit", required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    source = repo / "programs/manzanita-public-convergence/release_transition.py"
    require(source.is_file(), f"Retained release-transition mechanism is absent: {source}")
    predecessor_tree = git(repo, "rev-parse", f"{args.predecessor_commit}:manzanita")
    product_tree = git(repo, "rev-parse", f"{args.product_commit}:manzanita")

    spec = importlib.util.spec_from_file_location("manzanita_release_transition_v17", source)
    require(spec is not None and spec.loader is not None, "Could not load retained release-transition mechanism")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    patched: dict[str, tuple[str, str]] = {}
    for name in dir(module):
        if not name.isupper():
            continue
        value = getattr(module, name)
        if not isinstance(value, str):
            continue
        replacement = None
        if value == "1.6.0":
            replacement = RELEASE
        elif value == "1.4.1":
            replacement = PREDECESSOR_RELEASE
        elif "PREDECESSOR" in name and "TREE" in name and HEX40.fullmatch(value):
            replacement = predecessor_tree
        elif "PREDECESSOR" in name and ("COMMIT" in name or "SHA" in name) and HEX40.fullmatch(value):
            replacement = args.predecessor_commit
        elif "PRODUCT" in name and "TREE" in name and HEX40.fullmatch(value):
            replacement = product_tree
        elif "PRODUCT" in name and ("COMMIT" in name or "SHA" in name) and HEX40.fullmatch(value):
            replacement = args.product_commit
        if replacement is not None and replacement != value:
            setattr(module, name, replacement)
            patched[name] = (value, replacement)

    require(any(after == RELEASE for _, after in patched.values()), f"Release identity was not patched; discovered constants: {patched}")
    require(any(after == PREDECESSOR_RELEASE for _, after in patched.values()), f"Predecessor release identity was not patched; discovered constants: {patched}")

    original = sys.argv
    try:
        sys.argv = [str(source), "custody", "--product-commit", args.product_commit]
        module.main()
    finally:
        sys.argv = original

    print({
        "result": "TRANSITION_APPLIED",
        "release": RELEASE,
        "predecessor_release": PREDECESSOR_RELEASE,
        "predecessor_commit": args.predecessor_commit,
        "predecessor_tree": predecessor_tree,
        "product_commit": args.product_commit,
        "product_tree": product_tree,
        "patched_constants": patched,
    })


if __name__ == "__main__":
    main()
