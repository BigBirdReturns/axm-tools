from __future__ import annotations

import argparse
import html
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .core import Acquisition
from .spatial import acquire_osm, acquire_usgs_imagery, acquire_usgs_water
from .street import acquire_kartaview, acquire_keyed_sources, acquire_panoramax
from .weather_fire import acquire_calfire, acquire_nws


def build_report(out_dir: Path, place: dict, manifest: list[dict]) -> None:
    rows = []
    for item in manifest:
        payload = item["payload"]
        status = item["status"]
        rows.append(
            f"<tr><td>{html.escape(item['source_id'])}</td><td class='{status}'>{html.escape(status)}</td>"
            f"<td>{payload['bytes']}</td><td>{html.escape(str(item['response'].get('http_status')))}</td>"
            f"<td>{html.escape(item['claim_scope'])}</td><td>{html.escape(item.get('error') or '')}</td></tr>"
        )
    image_cards = []
    for source_id in ("usgs_imagery", "usgs_3dep_hillshade", "panoramax_thumbnail"):
        path = out_dir / "payloads" / f"{source_id}.png"
        if not path.exists():
            path = out_dir / "payloads" / f"{source_id}.jpg"
        if path.exists():
            image_cards.append(f"<figure><img src='{path.relative_to(out_dir).as_posix()}' alt='{source_id}'><figcaption>{source_id}</figcaption></figure>")
    report = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Manzanita v1.6 source foundation</title><style>
body{{font-family:ui-monospace,monospace;margin:2rem;background:#f4f0e8;color:#111}}h1{{font:900 3rem/1 system-ui,sans-serif;letter-spacing:-.04em}}table{{border-collapse:collapse;width:100%;font-size:.8rem}}th,td{{border:1px solid #aaa;padding:.55rem;vertical-align:top}}th{{text-align:left;background:#111;color:#fff}}.ok{{color:#087f23;font-weight:800}}.failed{{color:#b42318;font-weight:800}}.empty,.degraded{{color:#9a6700;font-weight:800}}.skipped_missing_credential{{color:#555}}.plates{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem;margin:2rem 0}}figure{{margin:0;border:1px solid #111;background:#fff}}img{{display:block;width:100%;height:auto}}figcaption{{padding:.6rem;border-top:1px solid #111}}code{{background:#fff;padding:.15rem .35rem}}
</style></head><body><p>MANZANITA WORKS · SOURCE FOUNDATION</p><h1>Real sources before interface claims.</h1>
<p>Place: <strong>{html.escape(place['label'])}</strong>. Retrieval run: <code>{datetime.now(timezone.utc).isoformat()}</code>.</p>
<div class='plates'>{''.join(image_cards)}</div>
<table><thead><tr><th>Source</th><th>Status</th><th>Bytes</th><th>HTTP</th><th>Claim scope</th><th>Error</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    (out_dir / "report.html").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--place", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    place = json.loads(args.place.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "place.json").write_text(json.dumps(place, indent=2) + "\n", encoding="utf-8")
    (args.out / "source-registry.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    acq = Acquisition(args.out, registry)
    failures: list[str] = []
    for name, function in (
        ("nws", lambda: acquire_nws(acq, place)),
        ("calfire", lambda: acquire_calfire(acq)),
        ("usgs_imagery", lambda: acquire_usgs_imagery(acq, place)),
        ("usgs_water", lambda: acquire_usgs_water(acq, place)),
        ("osm", lambda: acquire_osm(acq, place)),
        ("kartaview", lambda: acquire_kartaview(acq, place)),
        ("panoramax", lambda: acquire_panoramax(acq, place)),
        ("keyed", lambda: acquire_keyed_sources(acq, place)),
    ):
        try:
            function()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {exc}")

    manifest = {
        "schema": "manzanita-works/source-acquisition-manifest@1",
        "place_id": place["place_id"],
        "run_id": uuid.uuid4().hex,
        "generated_at": acq.now(),
        "entries": acq.manifest,
        "required_failures": failures,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    build_report(args.out, place, acq.manifest)
    if failures:
        print("Required acquisition failures:", *failures, sep="\n- ", file=sys.stderr)
        return 2
    print(f"Acquired {len(acq.manifest)} source receipts into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
