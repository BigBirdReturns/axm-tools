#!/usr/bin/env python3
"""Repair the modeled Region aperture without lowering the visual floor."""

from __future__ import annotations

from pathlib import Path

TARGET = Path("programs/manzanita-public-convergence/build_public.py")

OLD_IMPORT = "from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat"
NEW_IMPORT = "from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat"

OLD_REGION = '''def region_composite(household: Image.Image, prop: Image.Image) -> Image.Image:
    a = fit(household)
    b = fit(prop)
    blended = Image.blend(a, b, 0.52).filter(ImageFilter.GaussianBlur(radius=7))
    blended = ImageEnhance.Color(blended).enhance(0.58)
    blended = ImageEnhance.Contrast(blended).enhance(1.18)
    return blended
'''

NEW_REGION = '''def region_composite(household: Image.Image, prop: Image.Image) -> Image.Image:
    """Build an edge-rich modeled regional aperture from classified donors.

    Four visibly separate photographic context cells retain source texture.
    Authored contours and relay marks make the regional object legible while
    preserving its classification as modeled context rather than observation.
    """
    household_full = fit(household)
    property_full = fit(prop)
    tiles = [
        ImageEnhance.Contrast(fit(household_full.crop((0, 0, 1120, 720)), (800, 500))).enhance(1.08),
        ImageEnhance.Color(fit(property_full.crop((480, 0, 1600, 720)), (800, 500))).enhance(0.82),
        ImageEnhance.Color(fit(property_full.crop((0, 280, 1120, 1000)), (800, 500))).enhance(0.72),
        ImageEnhance.Contrast(fit(household_full.crop((480, 280, 1600, 1000)), (800, 500))).enhance(1.16),
    ]
    canvas = Image.new("RGB", CANVAS, "#151712")
    canvas.paste(tiles[0], (0, 0))
    canvas.paste(tiles[1], (800, 0))
    canvas.paste(tiles[2], (0, 500))
    canvas.paste(tiles[3], (800, 500))

    analytical = Image.alpha_composite(
        canvas.convert("RGBA"), Image.new("RGBA", CANVAS, (17, 20, 15, 50))
    )
    draw = ImageDraw.Draw(analytical, "RGBA")
    draw.line((800, 0, 800, 1000), fill=(244, 239, 227, 178), width=5)
    draw.line((0, 500, 1600, 500), fill=(244, 239, 227, 178), width=5)

    contours = [
        [(0, 176), (180, 126), (360, 158), (548, 86), (736, 142), (928, 92), (1112, 132), (1320, 72), (1600, 118)],
        [(0, 342), (174, 282), (356, 318), (526, 248), (720, 296), (902, 236), (1104, 270), (1304, 210), (1600, 254)],
        [(0, 710), (190, 650), (388, 688), (566, 620), (760, 660), (952, 604), (1150, 638), (1360, 578), (1600, 616)],
        [(0, 886), (194, 824), (382, 858), (584, 790), (780, 832), (980, 764), (1170, 802), (1378, 742), (1600, 772)],
    ]
    for index, points in enumerate(contours):
        draw.line(points, fill=(229, 223, 207, 196 - index * 18), width=6)

    nodes = [(228, 258), (604, 194), (1032, 316), (1372, 194), (382, 728), (932, 696), (1286, 798)]
    for x, y in nodes:
        draw.ellipse(
            (x - 12, y - 12, x + 12, y + 12),
            fill=(255, 90, 43, 235),
            outline=(244, 239, 227, 238),
            width=3,
        )
    draw.line(nodes[:4], fill=(255, 90, 43, 238), width=8, joint="curve")
    draw.rectangle((28, 28, 1572, 972), outline=(244, 239, 227, 205), width=5)
    return analytical.convert("RGB")
'''

text = TARGET.read_text(encoding="utf-8")
if OLD_IMPORT not in text and NEW_IMPORT not in text:
    raise SystemExit("Could not locate the Pillow import")
if OLD_REGION not in text:
    raise SystemExit("Could not locate the low-information Region compositor")
text = text.replace(OLD_IMPORT, NEW_IMPORT, 1)
text = text.replace(OLD_REGION, NEW_REGION, 1)
TARGET.write_text(text, encoding="utf-8")
print("Edge-rich modeled Region aperture repair: APPLIED")
