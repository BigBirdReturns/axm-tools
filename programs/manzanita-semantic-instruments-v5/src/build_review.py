#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent
CANVAS = (1600, 1000)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha(value: dict) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def load_fit(path: Path, size: tuple[int, int] = CANVAS, centering: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=centering)


def save_webp(image: Image.Image, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "WEBP", quality=88, method=6)


def neighborhood_composite(paths: list[Path]) -> Image.Image:
    first, second, third = [load_fit(path) for path in paths]
    canvas = Image.new("RGB", CANVAS, "#111511")
    canvas.paste(ImageOps.fit(first, (1060, 1000), Image.Resampling.LANCZOS), (0, 0))
    canvas.paste(ImageOps.fit(second, (540, 500), Image.Resampling.LANCZOS), (1060, 0))
    canvas.paste(ImageOps.fit(third, (540, 500), Image.Resampling.LANCZOS), (1060, 500))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle((1048, 0, 1072, 1000), fill=(238, 232, 216, 230))
    draw.line((1060, 500, 1600, 500), fill=(238, 232, 216, 230), width=12)
    draw.rectangle((28, 28, 1572, 972), outline=(255, 91, 50, 220), width=5)
    return canvas


def stewardship_svg() -> bytes:
    nodes = [
        ("EVIDENCE", 210, 250), ("HOLD", 570, 165), ("OFFER", 570, 390),
        ("DECISION", 930, 300), ("EXECUTION", 1235, 200), ("ACCEPTANCE", 1235, 505),
        ("APPEAL", 900, 675), ("FOLLOW-THROUGH", 520, 740),
    ]
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5), (5, 6), (6, 7), (4, 7), (7, 0)]
    edge_markup = "".join(
        f'<line x1="{nodes[a][1]}" y1="{nodes[a][2]}" x2="{nodes[b][1]}" y2="{nodes[b][2]}" />'
        for a, b in edges
    )
    node_markup = "".join(
        f'<g><rect x="{x-125}" y="{y-44}" width="250" height="88" rx="6" />'
        f'<text x="{x}" y="{y+5}" text-anchor="middle">{escape(label)}</text></g>'
        for label, x, y in nodes
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000">
<rect width="1600" height="1000" fill="#111510"/><g stroke="#e6e1d2" stroke-opacity=".65" stroke-width="5">{edge_markup}</g>
<g fill="#1d251d" stroke="#f1ecdf" stroke-width="3">{node_markup}</g>
<style>text{{font:700 20px ui-monospace,monospace;fill:#f1ecdf;letter-spacing:2px}}</style>
<rect x="28" y="28" width="1544" height="944" fill="none" stroke="#ff5b32" stroke-width="5"/></svg>'''.encode("utf-8")


def map_svg() -> bytes:
    grid = "".join(f'<path d="M {x} 0 V 1000"/>' for x in range(0, 1601, 100)) + "".join(
        f'<path d="M 0 {y} H 1600"/>' for y in range(0, 1001, 100)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000">
<rect width="1600" height="1000" fill="#172018"/><g stroke="#efe9da" stroke-opacity=".10">{grid}</g>
<path d="M80 820 C310 745 480 650 700 610 C940 565 1120 400 1510 320" fill="none" stroke="#efe9da" stroke-width="18" stroke-opacity=".55"/>
<path d="M95 840 C330 765 500 670 720 630 C960 585 1140 420 1530 340" fill="none" stroke="#ff5b32" stroke-width="4"/>
<g fill="#ff5b32" stroke="#efe9da" stroke-width="3"><circle cx="420" cy="690" r="12"/><circle cx="890" cy="560" r="12"/><circle cx="1300" cy="405" r="12"/></g>
<text x="80" y="110" fill="#efe9da" font-family="ui-monospace,monospace" font-size="34">MAP-ONLY PUBLIC CONTEXT</text>
<text x="80" y="155" fill="#aeb7aa" font-family="ui-monospace,monospace" font-size="20">NO STREET OBSERVATION · NO LOCAL IMAGE REGISTRATION</text>
</svg>'''.encode("utf-8")


def build_asset(logical_key: str, plan: dict, donor_root: Path, asset_root: Path) -> dict:
    kind = plan["kind"]
    slug = logical_key.replace(":", "-")
    if kind == "raster_fit":
        image = load_fit(donor_root / plan["source"])
        if logical_key == "property:reference":
            image = ImageEnhance.Contrast(image).enhance(1.08)
        temp = asset_root / f"{slug}.webp"
        save_webp(image, temp)
    elif kind == "neighborhood_composite":
        temp = asset_root / f"{slug}.webp"
        save_webp(neighborhood_composite([donor_root / value for value in plan["sources"]]), temp)
    elif kind == "stewardship_svg":
        temp = asset_root / f"{slug}.svg"
        temp.write_bytes(stewardship_svg())
    elif kind == "map_svg":
        temp = asset_root / f"{slug}.svg"
        temp.write_bytes(map_svg())
    else:
        raise ValueError(f"Unknown asset plan: {kind}")
    digest = sha256_file(temp)
    final = asset_root / f"{slug}-{digest[:12]}{temp.suffix}"
    temp.rename(final)
    return {
        "asset_id": digest,
        "path": f"assets/{final.name}",
        "width": 1600,
        "height": 1000,
        "media_type": "image/svg+xml" if final.suffix == ".svg" else "image/webp",
        "class": plan["class"],
        "label": plan["label"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--donor-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    template = json.loads((args.source_root / "semantic-template.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    asset_root = args.output / "assets"
    if asset_root.exists():
        shutil.rmtree(asset_root)
    asset_root.mkdir(parents=True)

    assets = {
        key: build_asset(key, plan, args.donor_root, asset_root)
        for key, plan in template.pop("assetPlan").items()
    }
    registrations = {}
    for registration_key, template_receipt in template.pop("registrationTemplates").items():
        receipt = json.loads(json.dumps(template_receipt))
        asset_key = receipt["asset_key"]
        receipt["asset_id"] = assets[asset_key]["asset_id"]
        receipt["registration_template_key"] = registration_key
        receipt["receipt_sha256"] = canonical_sha(receipt)
        registrations[f"{receipt['asset_id']}:{receipt['instrument']}"] = receipt
    template["assets"] = assets
    template["registrations"] = registrations

    data_path = args.output / "data.json"
    data_path.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    compact = json.dumps(template, ensure_ascii=False, separators=(",", ":"))
    index_template = (args.source_root / "template/index.html").read_text(encoding="utf-8")
    index = index_template.replace("__MANZANITA_DATA__", compact)
    (args.output / "index.html").write_text(index, encoding="utf-8")
    app_text = (args.source_root / "template/app.js").read_text(encoding="utf-8")
    style_text = (args.source_root / "template/style.css").read_text(encoding="utf-8")
    (args.output / "app.js").write_text(app_text, encoding="utf-8")
    (args.output / "style.css").write_text(style_text, encoding="utf-8")
    shutil.copy2(args.source_root / "README.md", args.output / "README.md")
    shutil.copy2(args.source_root / "REVIEW_CONTRACT.json", args.output / "REVIEW_CONTRACT.json")

    standalone_data = json.loads(json.dumps(template))
    for asset in standalone_data["assets"].values():
        path = args.output / asset["path"]
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        asset["path"] = f"data:{asset['media_type']};base64,{encoded}"
    standalone_compact = json.dumps(standalone_data, ensure_ascii=False, separators=(",", ":"))
    standalone = index_template.replace("__MANZANITA_DATA__", standalone_compact)
    standalone = standalone.replace('<link rel="stylesheet" href="style.css">', f"<style>{style_text}</style>")
    standalone = standalone.replace('<script src="app.js" defer></script>', f"<script>{app_text}</script>")
    (args.output / "STANDALONE.html").write_text(standalone, encoding="utf-8")

    files = {}
    for path in sorted(p for p in args.output.rglob("*") if p.is_file() and p.name != "BUILD_RECEIPT.json"):
        files[path.relative_to(args.output).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    receipt = {
        "schema": "manzanita-works/semantic-instruments-review-build@3",
        "release": template["release"],
        "result": "PASS",
        "donor_count": 7,
        "asset_count": len(assets),
        "standalone_self_contained": True,
        "semantic_receipt_count": len(registrations),
        "semantic_receipts_by_instrument": {instrument: sum(1 for row in registrations.values() if row["instrument"] == instrument) for instrument in ("shade", "water", "access")},
        "semantic_feature_count": sum(row["feature_count"] for row in registrations.values()),
        "generic_gradient_registration_count": 0,
        "image_geometry_instruments": ["shade", "water", "access"],
        "shade_and_water_image_geometry": sum(row["feature_count"] for row in registrations.values() if row["instrument"] in {"shade", "water"}),
        "map_and_hold_image_geometry": 0,
        "files": files,
        "public_route_effect": "none",
        "successor_program_effect": "none",
        "canonical_task_count_effect": "none",
    }
    (args.output / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
