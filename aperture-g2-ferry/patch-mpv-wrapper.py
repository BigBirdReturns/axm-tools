#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch-mpv-wrapper.py <mpv-portable>")
    path = Path(sys.argv[1])
    source = path.read_text(encoding="utf-8")
    additions = [
        '  "$ROOT/lib/x86_64-linux-gnu/pulseaudio" \\',
        '  "$ROOT/usr/lib/x86_64-linux-gnu/pulseaudio" \\',
    ]
    if all(line in source for line in additions):
        path.chmod(0o755)
        return 0

    lines = source.splitlines()
    anchor = '  "$ROOT/usr/lib/x86_64-linux-gnu" \\'
    try:
        index = lines.index(anchor)
    except ValueError as exc:
        raise SystemExit("portable wrapper search-path seam changed") from exc
    lines[index + 1:index + 1] = additions
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
