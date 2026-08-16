#!/usr/bin/env python3
"""Build seven distinct, source-bounded Manzanita aperture records."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "axm-tools/manzanita-seven-aperture-build@1"
BUNDLE_SCHEMA = "axm-tools/manzanita-seven-aperture-bundle@1"
CONTRACT_SCHEMA = "axm-tools/manzanita-seven-aperture-contract@1"
AUTHORED_SCHEMA = "axm-tools/manzanita-authored-aperture-demo@1"
PUBLIC_DATA_SCHEMA = "axm-tools/manzanita-public-demo-data@1"
PROJECTION_SCHEMA = "axm-tools/manzanita-public-projection-receipt@1"
CONSTITUTION_SCHEMA = "axm-tools/manzanita-design-constitution@1"

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DEFAULT_CONTRACT = ROOT / "APERTURE_CONTRACT.json"
DEFAULT_AUTHORED = ROOT / "AUTHORED_DEMO.json"
DEFAULT_PUBLIC_DEMO = REPO_ROOT / "manzanita-next" / "public-demo" / "out"
DEFAULT_CONSTITUTION = REPO_ROOT / "manzanita-next" / "design-system" / "CONSTITUTION.json"
DEFAULT_OUTPUT = ROOT / "out"

EXPECTED_APERTURES = (
    "plant",
    "household",
    "property",
    "street",
    "neighborhood",
    "region",
    "stewardship",
)
ALLOWED_STATES = {
    "ok",
    "empty",
    "stale",
    "skipped_missing_credential",
    "rate_limited",
    "unavailable",
    "terms_blocked",
    "unknown",
    "authored",
}
STATE_PRIORITY = (
    "unavailable",
    "terms_blocked",
    "rate_limited",
    "skipped_missing_credential",
    "stale",
    "empty",
    "unknown",
    "ok",
    "authored",
)
PROHIBITED_KEYS = {
    "address",
    "street_address",
    "resident",
    "resident_name",
    "owner_name",
    "email",
    "phone",
    "account",
    "account_id",
    "token",
    "access_token",
    "api_key",
    "secret",
    "credential",
    "password",
}

GEOMETRY = {
    "plant": {
        "path": "M70 570 C154 522 191 438 258 389 C333 334 397 352 455 291 C515 228 556 157 649 130 C745 102 817 159 898 128 C986 94 1061 63 1142 88",
        "branch": "M455 291 C516 318 553 361 595 421",
        "cut": "M578 396 l31 45",
    },
    "household": {
        "path": "M58 584 C123 514 171 472 219 394 C271 309 349 261 438 239 C520 218 584 169 659 111 C739 49 836 74 909 137 C986 204 1053 188 1144 135",
        "branch": "M438 239 C496 278 536 330 573 396",
        "cut": "M557 370 l34 49",
    },
    "property": {
        "path": "M45 579 C115 530 181 489 254 431 C340 363 421 320 505 278 C599 231 690 224 775 182 C870 135 960 92 1047 103 C1090 108 1131 95 1170 72",
        "branch": "M505 278 C571 318 618 367 662 429",
        "cut": "M645 404 l35 49",
    },
    "street": {
        "path": "M31 535 C113 497 181 503 261 461 C352 414 414 331 507 311 C596 292 666 347 751 323 C845 297 899 215 989 191 C1061 172 1117 192 1180 148",
        "branch": "M507 311 C561 352 603 399 641 456",
        "cut": "M624 430 l35 49",
    },
    "neighborhood": {
        "path": "M24 566 C105 517 161 449 242 411 C332 369 398 303 484 262 C576 218 657 226 744 182 C834 136 915 91 1002 104 C1073 115 1127 95 1183 66",
        "branch": "M484 262 C552 303 604 357 650 424",
        "cut": "M634 398 l35 50",
    },
    "region": {
        "path": "M18 576 C91 516 139 441 223 404 C315 363 375 292 465 244 C548 201 636 205 718 151 C805 94 900 53 995 92 C1076 126 1129 97 1186 66",
        "branch": "M465 244 C533 296 585 352 640 424",
        "cut": "M622 400 l38 51",
    },
    "stewardship": {
        "path": "M40 602 C126 535 206 485 294 439 C389 389 475 337 566 301 C658 264 742 253 825 207 C913 159 987 104 1074 107 C1114 108 1150 96 1186 78",
        "branch": "M566 301 C642 344 701 396 757 458 M668 365 C758 353 834 316 907 258",
        "cut": "M741 432 l37 52",
    },
}


class ApertureError(ValueError):
    """Raised when an aperture bundle would exceed its evidence or authority."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ApertureError(message)


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
        raise ApertureError(f"Cannot load valid JSON from {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(recursive_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def source_evidence(row: dict[str, Any]) -> dict[str, Any]:
    state = str(row.get("state", "unknown"))
    require(state in ALLOWED_STATES - {"authored"}, f"Invalid public source state: {state}")
    return {
        "id": row.get("id"),
        "evidence_class": "public_source",
        "label": row.get("label"),
        "state": state,
        "source_time": row.get("source_time"),
        "retrieved_at": row.get("retrieved_at"),
        "payload_sha256": row.get("payload_sha256"),
        "attribution": row.get("attribution"),
        "rights": row.get("rights"),
        "storage_policy": row.get("storage_policy"),
        "claim_scope": row.get("claim_scope"),
        "uncertainty": (
            row.get("error")
            or "The public source retains its own scope and does not establish a private or local condition."
        ),
        "receipt_path": row.get("receipt_path"),
    }


def missing_source_evidence(source_id: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "evidence_class": "public_source",
        "label": source_id.replace("_", " ").title(),
        "state": "unknown",
        "source_time": None,
        "retrieved_at": None,
        "payload_sha256": None,
        "attribution": "Registered source absent from the consumed public dossier",
        "rights": "Unknown because the registered source row is absent",
        "storage_policy": "No payload retained in the aperture bundle",
        "claim_scope": "No substantive claim permitted until source custody is restored",
        "uncertainty": "The registered source row is absent from the exact public-demo build.",
        "receipt_path": None,
    }


def authored_evidence(row: dict[str, Any]) -> dict[str, Any]:
    require(row.get("state") == "authored", f"Authored record is not labeled authored: {row.get('id')}")
    return {
        "id": row.get("id"),
        "evidence_class": str(row.get("class")),
        "label": row.get("label"),
        "state": "authored",
        "source_time": row.get("authored_time"),
        "retrieved_at": None,
        "payload_sha256": sha256_bytes(canonical_bytes(row)),
        "attribution": "Manzanita design integrator",
        "rights": row.get("rights"),
        "storage_policy": "Repository-retained authored demonstration record",
        "claim_scope": row.get("claim_scope"),
        "uncertainty": row.get("uncertainty"),
        "receipt_path": "manzanita-next/apertures/AUTHORED_DEMO.json",
    }


def aperture_state(evidence: list[dict[str, Any]]) -> str:
    states = {str(row.get("state", "unknown")) for row in evidence}
    for state in STATE_PRIORITY:
        if state in states:
            return state
    return "unknown"


def distinct(rows: list[dict[str, Any]], field: str) -> None:
    values = [row.get(field) for row in rows]
    require(len(values) == len(set(values)), f"Apertures do not have distinct {field}")


def build_bundle(
    contract: dict[str, Any],
    authored: dict[str, Any],
    public_data: dict[str, Any],
    projection: dict[str, Any],
    constitution: dict[str, Any],
) -> dict[str, Any]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected aperture contract schema")
    require(authored.get("schema") == AUTHORED_SCHEMA, "Unexpected authored demo schema")
    require(public_data.get("schema") == PUBLIC_DATA_SCHEMA, "Unexpected public-demo data schema")
    require(projection.get("schema") == PROJECTION_SCHEMA, "Unexpected public projection receipt schema")
    require(constitution.get("schema") == CONSTITUTION_SCHEMA, "Unexpected design constitution schema")
    require(contract.get("object", {}).get("public_effect") == "none", "Aperture contract requests a public effect")
    require(contract.get("object", {}).get("constitutional_count_effect") == "none", "Aperture contract requests a constitutional count effect")
    require(public_data.get("place", {}).get("public_safe") is True, "Apertures require a public-safe canonical place")
    require(authored.get("public_safe") is True and authored.get("private_household") is False, "Authored cartridge is not public-safe")
    require(projection.get("result") == "PASS", "Consumed public projection did not pass")
    require(projection.get("place_id") == public_data.get("place", {}).get("id"), "Public projection and place identity disagree")

    source_by_id = {
        str(row.get("id")): row
        for row in public_data.get("sources", [])
        if isinstance(row, dict) and row.get("id")
    }
    authored_by_id: dict[str, dict[str, Any]] = {}
    for aperture_id, records in authored.get("records", {}).items():
        require(aperture_id in {"plant", "household", "stewardship"}, f"Unknown authored aperture: {aperture_id}")
        require(isinstance(records, list), f"Authored records for {aperture_id} must be a list")
        for row in records:
            require(isinstance(row, dict) and row.get("id"), f"Invalid authored record in {aperture_id}")
            require(row["id"] not in authored_by_id, f"Duplicate authored record id: {row['id']}")
            authored_by_id[row["id"]] = row

    contract_rows = contract.get("apertures", [])
    require(isinstance(contract_rows, list), "Aperture contract lacks aperture rows")
    require(tuple(row.get("id") for row in contract_rows) == EXPECTED_APERTURES, "Aperture order or identity drifted")
    require([row.get("order") for row in contract_rows] == list(range(1, 8)), "Aperture order must be one through seven")

    apertures: list[dict[str, Any]] = []
    previous_id: str | None = None
    for contract_row in contract_rows:
        aperture_id = str(contract_row["id"])
        geometry = GEOMETRY[aperture_id]
        require(contract_row["geometry_id"] == f"M99-APERTURE-{aperture_id.upper()}-001", f"Geometry id drifted for {aperture_id}")

        evidence: list[dict[str, Any]] = []
        missing_sources: list[str] = []
        for source_id in contract_row.get("source_ids", []):
            source_row = source_by_id.get(source_id)
            if source_row is None:
                evidence.append(missing_source_evidence(source_id))
                missing_sources.append(source_id)
            else:
                evidence.append(source_evidence(source_row))
        for record_id in contract_row.get("authored_record_ids", []):
            require(record_id in authored_by_id, f"Missing authored record {record_id} for {aperture_id}")
            evidence.append(authored_evidence(authored_by_id[record_id]))
        require(evidence, f"Aperture {aperture_id} has no evidence rows")

        aperture = {
            "id": aperture_id,
            "order": contract_row["order"],
            "parent_aperture": previous_id,
            "place_id": public_data["place"]["id"],
            "source_run_id": public_data["source_run_id"],
            "object_class": contract_row["object_class"],
            "geometry": {
                "id": contract_row["geometry_id"],
                "class": contract_row["geometry_class"],
                "source_class": "authored_aperture_registration",
                "path": geometry["path"],
                "branch": geometry["branch"],
                "authority_cut": geometry["cut"],
                "claim_boundary": "Authored registration geometry for aperture operation; not surveyed, observed, provider, or field geometry.",
            },
            "primary_actor": contract_row["primary_actor"],
            "state": aperture_state(evidence),
            "evidence": evidence,
            "source_ids": list(contract_row.get("source_ids", [])),
            "authored_record_ids": list(contract_row.get("authored_record_ids", [])),
            "missing_source_ids": missing_sources,
            "reading": contract_row["reading"],
            "safe_action": contract_row["safe_action"],
            "authority": contract_row["authority"],
            "acceptance": contract_row["acceptance"],
            "handoff": contract_row["handoff"],
            "prohibited_consequence": contract_row["prohibited_consequence"],
            "evidence_count": len(evidence),
            "degraded_evidence_count": sum(row["state"] not in {"ok", "authored"} for row in evidence),
        }
        aperture["payload_sha256"] = sha256_bytes(canonical_bytes(aperture))
        apertures.append(aperture)
        previous_id = aperture_id

    for field in (
        "object_class",
        "reading",
        "safe_action",
        "authority",
        "acceptance",
        "handoff",
        "prohibited_consequence",
    ):
        distinct(apertures, field)
    distinct([row["geometry"] for row in apertures], "id")
    distinct([row["geometry"] for row in apertures], "path")

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "bundle_id": f"{public_data['place']['id']}-{public_data['source_run_id']}-seven-apertures",
        "place": public_data["place"],
        "public_demo_build_id": public_data["build_id"],
        "source_run_id": public_data["source_run_id"],
        "source_manifest_sha256": public_data["source_manifest_sha256"],
        "public_projection_receipt_sha256": projection.get("payload_sha256"),
        "design_constitution_version": constitution.get("version"),
        "authored_cartridge_id": authored["cartridge_id"],
        "aperture_count": len(apertures),
        "aperture_order": list(EXPECTED_APERTURES),
        "apertures": apertures,
        "state_counts": dict(sorted(Counter(row["state"] for row in apertures).items())),
        "evidence_state_counts": dict(
            sorted(Counter(evidence["state"] for row in apertures for evidence in row["evidence"]).items())
        ),
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "adverse_action_boundary": contract["adverse_action_boundary"],
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    prohibited = recursive_keys(bundle) & PROHIBITED_KEYS
    require(not prohibited, f"Aperture bundle contains prohibited keys: {sorted(prohibited)}")
    bundle["payload_sha256"] = sha256_bytes(canonical_bytes(bundle))
    return bundle


def build(
    repo_root: Path,
    contract_path: Path,
    authored_path: Path,
    public_demo_root: Path,
    constitution_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = contract_path.resolve()
    authored_path = authored_path.resolve()
    public_demo_root = public_demo_root.resolve()
    constitution_path = constitution_path.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    public_data_path = public_demo_root / "PUBLIC_DATA.json"
    projection_path = public_demo_root / "PUBLIC_PROJECTION_RECEIPT.json"
    public_build_path = public_demo_root / "BUILD_RECEIPT.json"
    require(public_data_path.is_file(), f"Missing public-demo data: {public_data_path}")
    require(projection_path.is_file(), f"Missing public projection receipt: {projection_path}")
    require(public_build_path.is_file(), f"Missing public-demo build receipt: {public_build_path}")

    contract = load_json(contract_path)
    authored = load_json(authored_path)
    public_data = load_json(public_data_path)
    projection = load_json(projection_path)
    public_build = load_json(public_build_path)
    constitution = load_json(constitution_path)
    require(public_build.get("result") == "PASS", "Consumed public-demo build did not pass")
    require(public_build.get("release_effect") == "none", "Consumed public-demo build carries a release effect")
    require(public_build.get("constitutional_count_effect") == "none", "Consumed public-demo build carries a count effect")

    bundle = build_bundle(contract, authored, public_data, projection, constitution)
    bundle_path = output_root / "APERTURE_BUNDLE.json"
    write_json(bundle_path, bundle)

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "result": "PASS",
        "inputs": {
            "contract": {
                "path": contract_path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(contract_path),
            },
            "authored_demo": {
                "path": authored_path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(authored_path),
            },
            "public_data": {
                "path": public_data_path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(public_data_path),
                "payload_sha256": public_data.get("payload_sha256"),
            },
            "public_projection_receipt": {
                "path": projection_path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(projection_path),
                "payload_sha256": projection.get("payload_sha256"),
            },
            "public_demo_build": {
                "path": public_build_path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(public_build_path),
                "payload_sha256": public_build.get("payload_sha256"),
            },
            "design_constitution": {
                "path": constitution_path.relative_to(repo_root).as_posix(),
                "version": constitution.get("version"),
                "sha256": sha256_file(constitution_path),
            },
        },
        "bundle": {
            "path": "APERTURE_BUNDLE.json",
            "sha256": sha256_file(bundle_path),
            "payload_sha256": bundle["payload_sha256"],
            "aperture_count": bundle["aperture_count"],
            "aperture_order": bundle["aperture_order"],
            "state_counts": bundle["state_counts"],
            "evidence_state_counts": bundle["evidence_state_counts"],
        },
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_root / "BUILD_RECEIPT.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--authored", type=Path, default=DEFAULT_AUTHORED)
    parser.add_argument("--public-demo-root", type=Path, default=DEFAULT_PUBLIC_DEMO)
    parser.add_argument("--constitution", type=Path, default=DEFAULT_CONSTITUTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        args.repo_root,
        args.contract,
        args.authored,
        args.public_demo_root,
        args.constitution,
        args.output,
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "apertures": receipt["bundle"]["aperture_count"],
                "order": receipt["bundle"]["aperture_order"],
                "states": receipt["bundle"]["state_counts"],
                "evidence_states": receipt["bundle"]["evidence_state_counts"],
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
    except ApertureError as exc:
        raise SystemExit(str(exc)) from exc
