#!/usr/bin/env python3
"""Build the exact Manzanita P9 estate-surface disposition register."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CONTRACT_SCHEMA = "axm-tools/manzanita-estate-parity-contract@1"
DISPOSITIONS_SCHEMA = "axm-tools/manzanita-estate-surface-dispositions@1"
INVENTORY_SCHEMA = "axm-tools/resolution-backfill-inventory@1"
BACKFILL_REPORT_SCHEMA = "axm-tools/resolution-backfill-report@1"
BACKFILL_QUALIFICATION_SCHEMA = "axm-tools/resolution-backfill-qualification@1"
P8_REPORT_SCHEMA = "axm-tools/manzanita-resilience-qualification@1"
P8_BOARD_SCHEMA = "axm-tools/manzanita-review-board-receipt@1"
REGISTER_SCHEMA = "axm-tools/manzanita-estate-parity-register@1"
BUILD_SCHEMA = "axm-tools/manzanita-estate-parity-build@1"


class ParityError(ValueError):
    """Raised when a source or disposition violates the P9 contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ParityError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ParityError(f"Cannot load {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def recursive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key).lower())
            found.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(recursive_keys(item))
    return found


def normalized_backfill_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove run timestamps while retaining the evidence-bearing audit result."""
    return {
        key: value
        for key, value in report.items()
        if key not in {"generated_at"}
    }


def normalized_backfill_qualification(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"qualified_at"}
    }


def validate_no_prohibited_keys(
    value: Any,
    prohibited: set[str],
    label: str,
) -> None:
    findings = sorted(recursive_keys(value) & prohibited)
    require(not findings, f"{label} contains prohibited keys: {findings}")


def component_rows(surface: dict[str, Any], source_path: str) -> list[dict[str, Any]]:
    surface_id = str(surface["id"])
    rows: list[dict[str, Any]] = [
        {
            "component_id": f"{surface_id}:surface:000",
            "kind": "surface_epic",
            "source_path": source_path,
            "source_index": 0,
            "source_record": {
                "id": surface["id"],
                "class": surface["class"],
                "paths": surface["paths"],
                "current_claim": surface["current_claim"],
                "claim_evidence": surface["claim_evidence"],
                "resolution_status": surface["resolution_status"],
                "evidence_tier": surface["evidence_tier"],
                "actors": surface["actors"],
                "mechanism": surface["mechanism"],
                "gates": surface["gates"],
                "next_gate": surface["next_gate"],
            },
        }
    ]
    for index, finding in enumerate(surface["findings"], start=1):
        rows.append(
            {
                "component_id": f"{surface_id}:finding:{index:03d}",
                "kind": "finding",
                "source_path": source_path,
                "source_index": index,
                "source_record": finding,
            }
        )
    for index, asset in enumerate(surface["assets_required"], start=1):
        rows.append(
            {
                "component_id": f"{surface_id}:asset:{index:03d}",
                "kind": "required_asset",
                "source_path": source_path,
                "source_index": index,
                "source_record": asset,
            }
        )
    return rows


def validate_p8(
    report: dict[str, Any],
    board: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    successor = contract["successor_candidate"]
    require(report.get("schema") == P8_REPORT_SCHEMA, "Unexpected P8 report schema")
    require(report.get("result") == "PASS", "P8 qualification did not pass")
    require(
        report.get("campaign_count") == successor["required_p8_campaign_count"],
        "P8 campaign count drifted",
    )
    campaigns = report.get("campaigns")
    require(isinstance(campaigns, list), "P8 report lacks campaign rows")
    require(len(campaigns) == report["campaign_count"], "P8 campaign rows drifted")
    require(all(row.get("result") == "PASS" for row in campaigns), "A P8 campaign did not pass")
    for key in (
        "physical_campaigns_performed",
        "real_assistive_technology_claim",
        "real_device_claim",
        "actual_network_claim",
        "private_projection_claim",
        "credentialed_provider_claim",
        "field_operation_claim",
    ):
        require(report.get(key) is False, f"P8 report broadens {key}")
    for key in ("public_effect", "constitutional_count_effect", "release_effect"):
        require(report.get(key) == "none", f"P8 report carries {key}")

    require(board.get("schema") == P8_BOARD_SCHEMA, "Unexpected P8 board receipt schema")
    require(board.get("result") == "PASS", "P8 contained review did not pass")
    require(board.get("packet_id") == successor["required_p8_packet"], "P8 packet identity drifted")
    require(board.get("decision_id") == successor["required_p8_decision"], "P8 decision identity drifted")
    require(board.get("outcome") == "admit_with_holds", "P8 board outcome drifted")
    require(board.get("release_effect") == "internal_candidate_only", "P8 board release boundary drifted")
    require(board.get("constitutional_count_effect") == "none", "P8 board carries count effect")
    require(board.get("seat_count") == 12, "P8 board seat count drifted")
    require(board.get("open_vetoes") == [], "P8 board retains open vetoes")
    require(
        board.get("open_critical_or_high_defects") == [],
        "P8 board retains open critical or high defects",
    )


def build(
    repo_root: Path,
    contract_path: Path,
    dispositions_path: Path,
    inventory_path: Path,
    surface_schema_path: Path,
    backfill_report_path: Path,
    backfill_qualification_path: Path,
    p7_build_path: Path,
    p8_report_path: Path,
    p8_board_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "contract": contract_path.resolve(),
        "dispositions": dispositions_path.resolve(),
        "inventory": inventory_path.resolve(),
        "surface_schema": surface_schema_path.resolve(),
        "backfill_report": backfill_report_path.resolve(),
        "backfill_qualification": backfill_qualification_path.resolve(),
        "p7_build": p7_build_path.resolve(),
        "p8_report": p8_report_path.resolve(),
        "p8_board": p8_board_path.resolve(),
    }
    for label, path in paths.items():
        require(path.is_file(), f"Missing P9 input {label}: {path}")

    contract = load_json(paths["contract"])
    dispositions = load_json(paths["dispositions"])
    inventory = load_json(paths["inventory"])
    surface_schema = load_json(paths["surface_schema"])
    backfill_report = load_json(paths["backfill_report"])
    backfill_qualification = load_json(paths["backfill_qualification"])
    p7_build = load_json(paths["p7_build"])
    p8_report = load_json(paths["p8_report"])
    p8_board = load_json(paths["p8_board"])

    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected parity contract schema")
    require(dispositions.get("schema") == DISPOSITIONS_SCHEMA, "Unexpected disposition schema")
    require(inventory.get("schema") == INVENTORY_SCHEMA, "Unexpected inventory schema")
    require(backfill_report.get("schema") == BACKFILL_REPORT_SCHEMA, "Unexpected backfill report schema")
    require(
        backfill_qualification.get("schema") == BACKFILL_QUALIFICATION_SCHEMA,
        "Unexpected backfill qualification schema",
    )
    for key in ("public_effect", "constitutional_count_effect", "release_effect"):
        require(contract.get(key) == "none", f"Parity contract carries {key}")
        require(dispositions.get(key) == "none", f"Dispositions carry {key}")

    prohibited = set(contract["prohibited_keys"])
    validate_no_prohibited_keys(dispositions, prohibited, "Dispositions")
    validate_p8(p8_report, p8_board, contract)
    require(p7_build.get("result") == "PASS", "P7 build did not pass")
    require(p7_build.get("public_effect") == "none", "P7 build carries a public effect")
    require(
        p7_build.get("constitutional_count_effect") == "none",
        "P7 build carries a count effect",
    )
    require(p7_build.get("release_effect") == "none", "P7 build carries a release effect")

    require(backfill_report.get("result") == "PASS", "Resolution-backfill audit did not pass")
    require(backfill_qualification.get("result") == "PASS", "Backfill qualification did not pass")
    require(
        "does not qualify any underlying product" in backfill_qualification.get("explicit_exclusion", ""),
        "Backfill qualification lost its non-product boundary",
    )

    surface_files = inventory.get("surface_files")
    require(isinstance(surface_files, list), "Inventory surface_files must be a list")
    require(len(surface_files) == contract["expected_surface_count"], "Inventory surface count drifted")
    require(
        backfill_report.get("summary", {}).get("surface_count") == len(surface_files),
        "Backfill report surface count drifted",
    )

    disposition_rows = dispositions.get("surfaces")
    require(isinstance(disposition_rows, list), "Dispositions surfaces must be a list")
    disposition_ids = [str(row.get("surface_id")) for row in disposition_rows]
    require(len(disposition_ids) == len(set(disposition_ids)), "Surface disposition ids are duplicated")
    by_surface = {str(row["surface_id"]): row for row in disposition_rows}

    surfaces: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    disposition_states = set(contract["disposition_states"])
    relationship_states = set(contract["relationship_states"])
    source_resolution_states = set(contract["source_resolution_states"])

    for relative in surface_files:
        source_path = (inventory_path.parent / str(relative)).resolve()
        require(source_path.is_file(), f"Surface file is missing: {source_path}")
        surface = load_json(source_path)
        try:
            Draft202012Validator(surface_schema).validate(surface)
        except Exception as exc:  # jsonschema supplies a detailed message
            raise ParityError(f"Surface schema failure for {source_path}: {exc}") from exc
        validate_no_prohibited_keys(surface, prohibited, f"Surface {surface.get('id')}")

        surface_id = str(surface["id"])
        require(surface_id not in source_ids, f"Duplicate source surface id: {surface_id}")
        source_ids.add(surface_id)
        require(surface_id in by_surface, f"Surface lacks a P9 disposition: {surface_id}")
        disposition = by_surface[surface_id]
        require(
            disposition.get("disposition") in disposition_states,
            f"Invalid disposition for {surface_id}: {disposition.get('disposition')}",
        )
        require(
            disposition.get("relationship") in relationship_states,
            f"Invalid relationship for {surface_id}: {disposition.get('relationship')}",
        )
        require(
            surface.get("resolution_status") in source_resolution_states,
            f"Invalid source resolution status for {surface_id}",
        )
        for field in ("reason", "authority_owner", "acceptance"):
            require(
                isinstance(disposition.get(field), str) and len(disposition[field]) >= 40,
                f"Disposition {surface_id} lacks complete {field}",
            )
        if disposition["disposition"] == "qualified":
            require(
                surface["resolution_status"] == "qualified",
                f"P9 cannot qualify a source surface whose record is {surface['resolution_status']}: {surface_id}",
            )
        if disposition["relationship"] == "historical_public_rollback_donor":
            require(
                disposition["disposition"] == "donor",
                f"Historical rollback donor must be classified donor: {surface_id}",
            )

        source_relative = source_path.relative_to(repo_root).as_posix()
        rows = component_rows(surface, source_relative)
        component_ids: list[str] = []
        for row in rows:
            record = row["source_record"]
            component: dict[str, Any] = {
                **row,
                "surface_id": surface_id,
                "source_resolution_status": surface["resolution_status"],
                "disposition": disposition["disposition"],
                "relationship": disposition["relationship"],
                "reason": disposition["reason"],
                "authority_owner": disposition["authority_owner"],
                "acceptance": disposition["acceptance"],
                "source_record_sha256": sha256_bytes(canonical_bytes(record)),
                "public_effect": "none",
                "constitutional_count_effect": "none",
                "release_effect": "none",
                "claim_boundary": contract["claim_boundary"],
            }
            component["payload_sha256"] = sha256_bytes(canonical_bytes(component))
            components.append(component)
            component_ids.append(component["component_id"])

        surface_row: dict[str, Any] = {
            "id": surface_id,
            "class": surface["class"],
            "paths": surface["paths"],
            "source_path": source_relative,
            "source_sha256": sha256_file(source_path),
            "source_resolution_status": surface["resolution_status"],
            "source_gate_counts": dict(sorted(Counter(surface["gates"].values()).items())),
            "finding_count": len(surface["findings"]),
            "asset_count": len(surface["assets_required"]),
            "component_count": len(rows),
            "component_ids": component_ids,
            "disposition": disposition["disposition"],
            "relationship": disposition["relationship"],
            "reason": disposition["reason"],
            "authority_owner": disposition["authority_owner"],
            "acceptance": disposition["acceptance"],
        }
        surface_row["payload_sha256"] = sha256_bytes(canonical_bytes(surface_row))
        surfaces.append(surface_row)

    require(source_ids == set(by_surface), f"Disposition coverage drifted: {sorted(source_ids ^ set(by_surface))}")
    require(len(components) == contract["expected_component_count"], "Exact source component count drifted")
    component_ids = [row["component_id"] for row in components]
    require(len(component_ids) == len(set(component_ids)), "Component ids are duplicated")
    require(all(row["disposition"] in disposition_states for row in components), "Unknown component disposition remains")

    successor: dict[str, Any] = {
        "id": "manzanita-next-successor",
        "state": contract["successor_candidate"]["state"],
        "classification": "internally_qualified_successor_candidate",
        "p7_build_sha256": sha256_file(paths["p7_build"]),
        "p8_report_sha256": sha256_file(paths["p8_report"]),
        "p8_report_payload_sha256": p8_report["payload_sha256"],
        "p8_board_sha256": sha256_file(paths["p8_board"]),
        "p8_board_payload_sha256": p8_board["payload_sha256"],
        "campaign_count": p8_report["campaign_count"],
        "retained_holds": p8_report.get("retained_holds", []),
        "public_release_authorized": False,
        "external_effect_authorized": False,
        "constitutional_count_effect": "none",
        "relationship_to_public_manzanita": "The qualified internal successor remains separate from the historical public rollback donor until P10 exact public-byte and rollback authority exists.",
    }
    successor["payload_sha256"] = sha256_bytes(canonical_bytes(successor))

    surfaces = sorted(surfaces, key=lambda row: row["id"])
    components = sorted(components, key=lambda row: row["component_id"])
    disposition_counts = dict(sorted(Counter(row["disposition"] for row in surfaces).items()))
    relationship_counts = dict(sorted(Counter(row["relationship"] for row in surfaces).items()))
    source_status_counts = dict(sorted(Counter(row["source_resolution_status"] for row in surfaces).items()))

    register: dict[str, Any] = {
        "schema": REGISTER_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "source_inventory": inventory_path.relative_to(repo_root).as_posix(),
        "source_inventory_sha256": sha256_file(inventory_path),
        "surface_schema": surface_schema_path.relative_to(repo_root).as_posix(),
        "surface_schema_sha256": sha256_file(surface_schema_path),
        "backfill_audit": {
            "result": backfill_report["result"],
            "head_sha": backfill_report.get("head_sha"),
            "summary": backfill_report["summary"],
            "semantic_sha256": sha256_bytes(canonical_bytes(normalized_backfill_report(backfill_report))),
            "qualification_semantic_sha256": sha256_bytes(
                canonical_bytes(normalized_backfill_qualification(backfill_qualification))
            ),
            "meaning": backfill_report["meaning"],
            "explicit_exclusion": backfill_qualification["explicit_exclusion"],
        },
        "surface_count": len(surfaces),
        "component_count": len(components),
        "surfaces": surfaces,
        "components": components,
        "disposition_counts": disposition_counts,
        "relationship_counts": relationship_counts,
        "source_resolution_status_counts": source_status_counts,
        "qualified_public_surfaces": [row["id"] for row in surfaces if row["disposition"] == "qualified"],
        "held_public_surfaces": [row["id"] for row in surfaces if row["disposition"] == "held"],
        "archived_public_surfaces": [row["id"] for row in surfaces if row["disposition"] == "archived"],
        "donor_public_surfaces": [row["id"] for row in surfaces if row["disposition"] == "donor"],
        "successor_candidate": successor,
        "uncovered_surfaces": [],
        "unknown_components": [],
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": contract["claim_boundary"],
        "control_question": contract["control_question"],
    }
    register["payload_sha256"] = sha256_bytes(canonical_bytes(register))
    register_path = output_root / "PARITY_REGISTER.json"
    write_json(register_path, register)

    input_receipts = {
        label: {
            "path": path.relative_to(repo_root).as_posix(),
            "sha256": sha256_file(path),
        }
        for label, path in paths.items()
    }
    receipt: dict[str, Any] = {
        "schema": BUILD_SCHEMA,
        "result": "PASS",
        "input_receipts": input_receipts,
        "register": {
            "path": register_path.name,
            "sha256": sha256_file(register_path),
            "payload_sha256": register["payload_sha256"],
            "surface_count": register["surface_count"],
            "component_count": register["component_count"],
            "disposition_counts": register["disposition_counts"],
            "relationship_counts": register["relationship_counts"],
            "uncovered_surfaces": register["uncovered_surfaces"],
            "unknown_components": register["unknown_components"],
        },
        "successor_candidate_state": successor["state"],
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "release_effect": "none",
        "claim_boundary": contract["claim_boundary"],
        "control_question": contract["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_root / "BUILD_RECEIPT.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path, default=Path("manzanita-next/parity/PARITY_CONTRACT.json"))
    parser.add_argument("--dispositions", type=Path, default=Path("manzanita-next/parity/SURFACE_DISPOSITIONS.json"))
    parser.add_argument("--inventory", type=Path, default=Path("resolution-backfill/inventory.json"))
    parser.add_argument("--surface-schema", type=Path, default=Path("resolution-backfill/contracts/surface.schema.json"))
    parser.add_argument("--backfill-report", type=Path, default=Path("resolution-backfill/out/report.json"))
    parser.add_argument("--backfill-qualification", type=Path, default=Path("resolution-backfill/out/qualification.json"))
    parser.add_argument("--p7-build", type=Path, default=Path("manzanita-next/experience/out/BUILD_RECEIPT.json"))
    parser.add_argument("--p8-report", type=Path, default=Path("manzanita-next/qualification/out/QUALIFICATION_REPORT.json"))
    parser.add_argument("--p8-board", type=Path, default=Path("manzanita-next/qualification/out/BOARD_DECISION_RECEIPT.json"))
    parser.add_argument("--output", type=Path, default=Path("manzanita-next/parity/out"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        args.repo_root,
        args.contract,
        args.dispositions,
        args.inventory,
        args.surface_schema,
        args.backfill_report,
        args.backfill_qualification,
        args.p7_build,
        args.p8_report,
        args.p8_board,
        args.output,
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                **receipt["register"],
                "successor_candidate_state": receipt["successor_candidate_state"],
                "public_effect": receipt["public_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "release_effect": receipt["release_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ParityError as exc:
        raise SystemExit(str(exc)) from exc
