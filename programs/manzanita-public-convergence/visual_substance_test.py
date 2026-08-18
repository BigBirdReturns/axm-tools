#!/usr/bin/env python3
"""Reject flat, duplicated, or non-photographic aperture assets."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

EXPECTED = {"plant", "household", "property", "street", "neighborhood", "region", "stewardship"}


def entropy(image: Image.Image) -> float:
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    return -sum((count / total) * math.log2(count / total) for count in histogram if count)


def edge_density(image: Image.Image) -> float:
    edge = image.convert("L").resize((320, 200)).filter(ImageFilter.FIND_EDGES)
    histogram = edge.histogram()
    total = sum(histogram)
    active = sum(histogram[40:])
    return active / total


def rms_difference(left: Image.Image, right: Image.Image) -> float:
    a = left.resize((160, 100)).convert("RGB")
    b = right.resize((160, 100)).convert("RGB")
    values = []
    for pa, pb in zip(a.getdata(), b.getdata()):
        values.extend((pa[0] - pb[0], pa[1] - pb[1], pa[2] - pb[2]))
    return math.sqrt(sum(value * value for value in values) / len(values))


def main(root: Path, output: Path) -> None:
    assets = {path.stem: path for path in (root / "assets").glob("*.webp")}
    if set(assets) != EXPECTED:
        raise SystemExit(f"Expected seven named aperture assets, found {sorted(assets)}")
    images = {name: Image.open(path).convert("RGB") for name, path in assets.items()}
    rows = {}
    for name, image in images.items():
        row = {
            "path": assets[name].relative_to(root).as_posix(),
            "bytes": assets[name].stat().st_size,
            "sha256": hashlib.sha256(assets[name].read_bytes()).hexdigest(),
            "width": image.width,
            "height": image.height,
            "entropy_bits": round(entropy(image), 4),
            "edge_density": round(edge_density(image), 4),
            "channel_variance": [round(value, 2) for value in ImageStat.Stat(image.resize((320, 200))).var],
        }
        if (image.width, image.height) != (1600, 1000):
            raise SystemExit(f"{name} is not normalized to 1600x1000")
        if row["entropy_bits"] < 5.4:
            raise SystemExit(f"{name} lacks photographic entropy: {row['entropy_bits']}")
        if row["edge_density"] < 0.05:
            raise SystemExit(f"{name} lacks visual edge substance: {row['edge_density']}")
        rows[name] = row

    pairs = {}
    dangerously_similar = []
    for left, right in itertools.combinations(sorted(images), 2):
        value = round(rms_difference(images[left], images[right]), 3)
        pairs[f"{left}:{right}"] = value
        if value < 6.0:
            dangerously_similar.append((left, right, value))
    if dangerously_similar:
        raise SystemExit(f"Aperture assets are visually duplicated: {dangerously_similar}")

    receipt = {
        "schema": "manzanita-works/photographic-substance-audit@1",
        "release": "1.6.0",
        "result": "PASS",
        "asset_count": 7,
        "assets": rows,
        "pairwise_rms": pairs,
        "claim_boundary": "This audit proves visual texture, normalization, and non-duplication. It does not authenticate subject matter, field condition, source rights, or release authority.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("manzanita"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/manzanita-photographic-substance.json"))
    args = parser.parse_args()
    main(args.root, args.output)
