#!/usr/bin/env python3
"""Repair visual donor selection and the modeled Region fallback without lowering the floor."""

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

OLD_DONOR_BLOCK = '''    household_source = donor.get("household") or next(iter(donor.values()))
    property_source = donor.get("property") or list(donor.values())[1]
    rendered = {
        "plant": entropy_crop(household_source, 0.48),
        "household": fit(household_source),
        "property": fit(property_source),
        "street": street_crop(property_source),
        "neighborhood": neighborhood_composite(household_source, property_source),
        "region": region_composite(household_source, property_source),
        "stewardship": stewardship_composite(household_source, property_source),
    }
    classification = {
        "plant": "derived photographic detail",
        "household": "retained photographic donor",
        "property": "retained photographic donor",
        "street": "derived photographic street-edge crop",
        "neighborhood": "derived multi-place analytical composite",
        "region": "derived modeled regional context",
        "stewardship": "derived continuity contact sheet",
    }
'''

NEW_DONOR_BLOCK = '''    household_source = donor.get("household") or next(iter(donor.values()))
    property_source = donor.get("property") or list(donor.values())[1]
    street_source = donor.get("street")
    region_source = donor.get("region")

    household_view = fit(household_source)
    property_view = ImageEnhance.Contrast(
        fit(property_source).filter(ImageFilter.UnsharpMask(radius=3, percent=400, threshold=1))
    ).enhance(1.25)
    street_view = fit(street_source) if street_source is not None else street_crop(property_source)
    region_view = fit(region_source) if region_source is not None else region_composite(household_source, property_source)

    # Stewardship is a continuity object, so show the four retained or derived
    # place views together instead of floating two photographs on a dark field.
    # Thin gutters and numbered sequence marks keep it legible as a contact
    # sheet without pretending the four views are one observed photograph.
    stewardship_view = Image.new("RGB", CANVAS, "#11120f")
    stewardship_view.paste(fit(household_view, (790, 490)), (0, 0))
    stewardship_view.paste(fit(property_view, (790, 490)), (810, 0))
    stewardship_view.paste(fit(street_view, (790, 490)), (0, 510))
    stewardship_view.paste(fit(region_view, (790, 490)), (810, 510))
    stewardship_draw = ImageDraw.Draw(stewardship_view, "RGBA")
    stewardship_draw.line((800, 0, 800, 1000), fill=(244, 239, 227, 220), width=10)
    stewardship_draw.line((0, 500, 1600, 500), fill=(244, 239, 227, 220), width=10)
    stewardship_draw.rectangle((20, 20, 1580, 980), outline=(255, 90, 43, 230), width=6)
    for label, (x, y) in zip(("01", "02", "03", "04"), ((40, 40), (850, 40), (40, 550), (850, 550))):
        stewardship_draw.rectangle((x, y, x + 78, y + 48), fill=(17, 18, 15, 220), outline=(244, 239, 227, 210), width=2)
        stewardship_draw.text((x + 20, y + 14), label, fill=(255, 90, 43, 255))

    rendered = {
        "plant": entropy_crop(household_source, 0.48),
        "household": household_view,
        "property": property_view,
        "street": street_view,
        "neighborhood": neighborhood_composite(household_source, property_source),
        "region": region_view,
        "stewardship": stewardship_view,
    }
    classification = {
        "plant": "derived photographic detail",
        "household": "retained generated household reference view",
        "property": "derived sharpened property reference view",
        "street": "retained generated street reference view" if street_source is not None else "derived photographic street-edge crop",
        "neighborhood": "derived multi-place analytical composite",
        "region": "retained generated regional reference view" if region_source is not None else "derived modeled regional context",
        "stewardship": "derived four-view continuity contact sheet",
    }
'''

text = TARGET.read_text(encoding="utf-8")
if OLD_IMPORT not in text and NEW_IMPORT not in text:
    raise SystemExit("Could not locate the Pillow import")
if OLD_REGION not in text:
    raise SystemExit("Could not locate the low-information Region compositor")
if OLD_DONOR_BLOCK not in text:
    raise SystemExit("Could not locate the two-donor aperture selection block")
text = text.replace(OLD_IMPORT, NEW_IMPORT, 1)
text = text.replace(OLD_REGION, NEW_REGION, 1)
text = text.replace(OLD_DONOR_BLOCK, NEW_DONOR_BLOCK, 1)
TARGET.write_text(text, encoding="utf-8")
print("Four-donor photographic aperture and stewardship repair: APPLIED")
