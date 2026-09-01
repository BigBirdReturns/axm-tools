#!/usr/bin/env python3
"""Build the one-file private-use DDV-PEL-003 application."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "app.css").read_text(encoding="utf-8")

    html = re.sub(
        r'<meta http-equiv="Content-Security-Policy" content="[^"]*">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'unsafe-inline\'; img-src data:; font-src \'none\'; connect-src \'none\'; media-src \'none\'; frame-src \'none\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'">',
        html,
    )
    html = html.replace('<link rel="stylesheet" href="app.css">', '<style>\n' + css + '\n</style>')

    def inline_script(match: re.Match[str]) -> str:
        rel = match.group(1)
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(rel)
        text = path.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
        return f'<script data-source="{rel}">\n{text}\n</script>'

    html = re.sub(r'<script src="([^"]+)"></script>', inline_script, html)
    html = html.replace(
        '<title>DDV-PEL-003 · Pelagos Governance Layer</title>',
        '<title>DDV-PEL-003 · Pelagos Governance Layer · Standalone</title>',
    )
    html = html.replace(
        "</head>",
        '<meta name="ddv-offline-bundle" content="DDV-PEL-003/0.3.0">\n</head>',
    )
    out = ROOT / "standalone.html"
    out.write_text(html, encoding="utf-8")
    print(f"built {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
