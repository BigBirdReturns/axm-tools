#!/usr/bin/env python3
"""Propose a bounded snap from an authored line to strong local image gradients."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image

SCHEMA = "axm-tools/manzanita-natural-border-registration@1"
CONTRACT_SCHEMA = "axm-tools/manzanita-street-glide-contract@1"
DEMO_SCHEMA = "axm-tools/manzanita-authored-registration-demo@1"

ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT / "STREET_GLIDE_CONTRACT.json"
DEFAULT_DEMO = ROOT / "AUTHORED_REGISTRATION_DEMO.json"
DEFAULT_IMAGE = ROOT.parent / "public-demo" / "out" / "site" / "assets" / "base-imagery.png"
DEFAULT_OUTPUT = ROOT / "out" / "REGISTRATION_RECEIPT.json"


class RegistrationError(ValueError):
    """Raised when a registration request violates the bounded proposal law."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistrationError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistrationError(f"Cannot load valid JSON from {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def normalize_vector(x: float, y: float) -> tuple[float, float]:
    length = math.hypot(x, y)
    require(length > 1e-9, "Candidate polyline contains a zero-length local tangent")
    return x / length, y / length


def tangent(points: list[tuple[float, float]], index: int) -> tuple[float, float]:
    if index == 0:
        return normalize_vector(points[1][0] - points[0][0], points[1][1] - points[0][1])
    if index == len(points) - 1:
        return normalize_vector(points[-1][0] - points[-2][0], points[-1][1] - points[-2][1])
    return normalize_vector(
        points[index + 1][0] - points[index - 1][0],
        points[index + 1][1] - points[index - 1][1],
    )


def sobel(pixel: Any, x: int, y: int, width: int, height: int) -> tuple[float, float, float]:
    x = int(clamp(x, 1, width - 2))
    y = int(clamp(y, 1, height - 2))
    p00 = float(pixel[x - 1, y - 1])
    p10 = float(pixel[x, y - 1])
    p20 = float(pixel[x + 1, y - 1])
    p01 = float(pixel[x - 1, y])
    p21 = float(pixel[x + 1, y])
    p02 = float(pixel[x - 1, y + 1])
    p12 = float(pixel[x, y + 1])
    p22 = float(pixel[x + 1, y + 1])
    gx = (-p00 + p20) + (-2.0 * p01 + 2.0 * p21) + (-p02 + p22)
    gy = (-p00 - 2.0 * p10 - p20) + (p02 + 2.0 * p12 + p22)
    magnitude = math.hypot(gx, gy)
    normalized = min(1.0, magnitude / (4.0 * math.sqrt(2.0) * 255.0))
    return gx, gy, normalized


def confidence_class(mean_strength: float, snapped_fraction: float) -> str:
    if snapped_fraction >= 0.8 and mean_strength >= 0.25:
        return "high_edge_alignment"
    if snapped_fraction >= 0.5 and mean_strength >= 0.12:
        return "medium_edge_alignment"
    if snapped_fraction > 0 and mean_strength > 0:
        return "low_edge_alignment"
    return "no_admissible_snap"


def pixel_points(normalized: list[list[Any]], width: int, height: int) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index, row in enumerate(normalized):
        require(isinstance(row, list) and len(row) == 2, f"Candidate point {index} is not a two-value list")
        require(finite_number(row[0]) and finite_number(row[1]), f"Candidate point {index} is not finite")
        x = float(row[0])
        y = float(row[1])
        require(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0, f"Candidate point {index} is outside normalized image space")
        points.append((x * (width - 1), y * (height - 1)))
    return points


def propose(
    contract: dict[str, Any],
    demo: dict[str, Any],
    image_path: Path,
) -> dict[str, Any]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected Street Glide contract schema")
    require(demo.get("schema") == DEMO_SCHEMA, "Unexpected authored registration demo schema")
    require(demo.get("public_safe") is True and demo.get("private_household") is False, "Registration demo is not public-safe")
    registration = demo.get("registration")
    require(isinstance(registration, dict), "Registration demo lacks a registration object")
    require(registration.get("candidate_source_class") == contract["registration"]["candidate_source_class"], "Candidate source class drifted")
    require(registration.get("image_class") in contract["registration"]["image_classes_allowed"], "Image class is not admitted")
    require(registration.get("coordinate_space") == "normalized_image", "Only normalized image coordinates are accepted")

    points_raw = registration.get("candidate_points")
    require(isinstance(points_raw, list), "Candidate points must be a list")
    require(len(points_raw) >= int(contract["registration"]["minimum_points"]), "Candidate has too few points")
    radius = int(registration.get("search_radius_pixels", contract["registration"]["default_search_radius_pixels"]))
    require(0 <= radius <= int(contract["registration"]["maximum_search_radius_pixels"]), "Search radius exceeds the contract")
    minimum_strength = float(registration.get("minimum_gradient_strength", contract["registration"]["minimum_gradient_strength"]))
    require(0.0 <= minimum_strength <= 1.0, "Minimum gradient strength must be in [0, 1]")
    maximum_mean_displacement = float(
        registration.get(
            "maximum_mean_displacement_pixels",
            contract["registration"]["maximum_mean_displacement_pixels"],
        )
    )
    require(maximum_mean_displacement >= 0.0, "Maximum mean displacement must be nonnegative")
    require(image_path.is_file(), f"Registration image does not exist: {image_path}")

    with Image.open(image_path) as source:
        source_format = source.format or "unknown"
        grayscale = source.convert("L")
        width, height = grayscale.size
        require(width >= 3 and height >= 3, "Registration image is too small for a Sobel gradient")
        pixel = grayscale.load()
        original = pixel_points(points_raw, width, height)
        proposed: list[tuple[float, float]] = []
        receipts: list[dict[str, Any]] = []

        for index, (x, y) in enumerate(original):
            tx, ty = tangent(original, index)
            nx, ny = -ty, tx
            candidates: list[dict[str, Any]] = []
            for offset in range(-radius, radius + 1):
                candidate_x = clamp(x + nx * offset, 1.0, width - 2.0)
                candidate_y = clamp(y + ny * offset, 1.0, height - 2.0)
                rounded_x = int(round(candidate_x))
                rounded_y = int(round(candidate_y))
                gx, gy, magnitude = sobel(pixel, rounded_x, rounded_y, width, height)
                gradient_length = math.hypot(gx, gy)
                if gradient_length > 1e-9:
                    alignment = abs((gx / gradient_length) * nx + (gy / gradient_length) * ny)
                else:
                    alignment = 0.0
                effective = magnitude * alignment
                candidates.append(
                    {
                        "offset": offset,
                        "x": candidate_x,
                        "y": candidate_y,
                        "sample_x": rounded_x,
                        "sample_y": rounded_y,
                        "gradient_magnitude": magnitude,
                        "gradient_alignment": alignment,
                        "effective_strength": effective,
                    }
                )

            best = min(
                candidates,
                key=lambda row: (
                    -row["effective_strength"],
                    abs(row["offset"]),
                    row["offset"],
                    row["sample_y"],
                    row["sample_x"],
                ),
            )
            snapped = best["effective_strength"] >= minimum_strength
            proposed_x = best["x"] if snapped else x
            proposed_y = best["y"] if snapped else y
            displacement = math.hypot(proposed_x - x, proposed_y - y)
            proposed.append((proposed_x, proposed_y))
            receipts.append(
                {
                    "index": index,
                    "original_pixel": [round(x, 4), round(y, 4)],
                    "proposed_pixel": [round(proposed_x, 4), round(proposed_y, 4)],
                    "normal": [round(nx, 6), round(ny, 6)],
                    "selected_offset_pixels": best["offset"] if snapped else 0,
                    "displacement_pixels": round(displacement, 4),
                    "gradient_magnitude": round(best["gradient_magnitude"], 6),
                    "gradient_alignment": round(best["gradient_alignment"], 6),
                    "effective_gradient_strength": round(best["effective_strength"], 6),
                    "snapped": snapped,
                    "no_snap_reason": None if snapped else "No sample along the bounded normal search met the admitted gradient floor.",
                }
            )

    displacements = [row["displacement_pixels"] for row in receipts]
    strengths = [row["effective_gradient_strength"] for row in receipts if row["snapped"]]
    snapped_count = sum(bool(row["snapped"]) for row in receipts)
    mean_displacement = sum(displacements) / len(displacements)
    maximum_displacement = max(displacements)
    mean_strength = sum(strengths) / len(strengths) if strengths else 0.0
    snapped_fraction = snapped_count / len(receipts)
    within_displacement = mean_displacement <= maximum_mean_displacement

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "result": "PASS" if within_displacement else "HOLD",
        "admission_state": (
            "registration_proposal"
            if snapped_count and within_displacement
            else "no_snap_proposal"
            if not snapped_count
            else "displacement_hold"
        ),
        "image": {
            "path": image_path.as_posix(),
            "format": source_format,
            "width": width,
            "height": height,
            "sha256": sha256_file(image_path),
            "image_class": registration["image_class"],
        },
        "candidate": {
            "id": registration["id"],
            "label": registration["label"],
            "source_class": registration["candidate_source_class"],
            "coordinate_space": registration["coordinate_space"],
            "sha256": sha256_bytes(canonical_bytes(registration)),
        },
        "method": {
            "id": "sobel_normal_search_v1",
            "source_class": contract["registration"]["output_source_class"],
            "search_radius_pixels": radius,
            "minimum_gradient_strength": minimum_strength,
            "maximum_mean_displacement_pixels": maximum_mean_displacement,
            "normal_search_only": True,
            "grayscale_gradient": True,
            "feature_identity": "prohibited",
        },
        "original_points": [[round(x, 4), round(y, 4)] for x, y in original],
        "proposed_points": [[round(x, 4), round(y, 4)] for x, y in proposed],
        "point_receipts": receipts,
        "point_count": len(receipts),
        "snapped_point_count": snapped_count,
        "unsnapped_point_count": len(receipts) - snapped_count,
        "snapped_fraction": round(snapped_fraction, 6),
        "mean_displacement_pixels": round(mean_displacement, 4),
        "maximum_displacement_pixels": round(maximum_displacement, 4),
        "mean_gradient_strength": round(mean_strength, 6),
        "confidence_class": confidence_class(mean_strength, snapped_fraction),
        "within_displacement_gate": within_displacement,
        "known": contract["field_and_interpretation_boundary"]["known"],
        "unknown": contract["field_and_interpretation_boundary"]["unknown"],
        "safe_action": contract["field_and_interpretation_boundary"]["safe_action"],
        "authority": contract["field_and_interpretation_boundary"]["authority"],
        "prohibited_consequence": contract["field_and_interpretation_boundary"]["prohibited_consequence"],
        "claim_boundary": (
            registration["claim_boundary"]
            + " "
            + contract["object"]["claim_boundary"]
        ),
        "public_effect": "none",
        "constitutional_count_effect": "none",
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--demo", type=Path, default=DEFAULT_DEMO)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = propose(load_json(args.contract), load_json(args.demo), args.image.resolve())
    write_json(args.output, receipt)
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "admission_state": receipt["admission_state"],
                "points": receipt["point_count"],
                "snapped": receipt["snapped_point_count"],
                "mean_displacement_pixels": receipt["mean_displacement_pixels"],
                "mean_gradient_strength": receipt["mean_gradient_strength"],
                "confidence_class": receipt["confidence_class"],
                "public_effect": receipt["public_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except RegistrationError as exc:
        raise SystemExit(str(exc)) from exc
