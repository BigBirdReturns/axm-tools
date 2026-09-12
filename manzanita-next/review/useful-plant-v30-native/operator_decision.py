#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "OPERATOR_REVIEW_CONTRACT.json"
TEMPLATE_PATH = HERE / "OPERATOR_DECISION_TEMPLATE.json"


class DecisionError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise DecisionError(f"cannot read JSON {path}: {error}") from error


def validate(decision: dict, contract: dict, receipt_root: Path | None = None) -> dict:
    errors: list[str] = []
    expected_ids = [item["id"] for item in contract["criteria"]]
    authority = contract["authority_invariants"]

    if decision.get("schema") != "manzanita/useful-plant-v30-operator-decision@1":
        errors.append("unexpected decision schema")
    if decision.get("candidate") != contract["candidate"]:
        errors.append("candidate does not match contract")

    state = decision.get("decision")
    if state not in contract["decision_states"]:
        errors.append(f"unsupported decision state: {state!r}")

    rows = decision.get("criteria")
    if not isinstance(rows, list):
        rows = []
        errors.append("criteria must be a list")
    observed_ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if observed_ids != expected_ids:
        errors.append("criteria must appear once, in contract order")

    for key, value in authority.items():
        if decision.get(key) != value:
            errors.append(f"authority invariant changed: {key}")

    if state == "PENDING":
        if decision.get("operator_visual_acceptance") != "ABSENT":
            errors.append("pending decision must keep visual acceptance absent")
        if decision.get("operator") is not None:
            errors.append("pending decision cannot name an operator")
        if decision.get("rationale") is not None:
            errors.append("pending decision cannot contain a rationale")
        if decision.get("generated_at") is not None:
            errors.append("pending decision cannot contain a decision timestamp")
        for row in rows:
            if row.get("result") != "PENDING":
                errors.append(f"pending criterion changed: {row.get('id')}")
            if row.get("notes") is not None:
                errors.append(f"pending criterion contains notes: {row.get('id')}")
        if decision.get("reviewed_receipts") not in ({}, None):
            errors.append("pending decision cannot prebind review receipts")
    elif state in {"ACCEPTED", "REVISE", "REJECTED"}:
        operator = decision.get("operator")
        rationale = decision.get("rationale")
        generated_at = decision.get("generated_at")
        if not isinstance(operator, str) or len(operator.strip()) < 2:
            errors.append("recorded decision requires a named operator")
        if not isinstance(rationale, str) or len(rationale.strip()) < 20:
            errors.append("recorded decision requires a substantive rationale")
        if not isinstance(generated_at, str) or "T" not in generated_at:
            errors.append("recorded decision requires an ISO timestamp")

        expected_acceptance = "ACCEPTED" if state == "ACCEPTED" else "NOT_ACCEPTED"
        if decision.get("operator_visual_acceptance") != expected_acceptance:
            errors.append("visual acceptance state does not match the decision")

        allowed_results = {"PASS", "FAIL"}
        results = []
        for row in rows:
            result = row.get("result")
            results.append(result)
            if result not in allowed_results:
                errors.append(f"criterion has unsupported result: {row.get('id')}")
        if state == "ACCEPTED" and any(result != "PASS" for result in results):
            errors.append("accepted decision requires every criterion to pass")
        if state in {"REVISE", "REJECTED"} and all(result == "PASS" for result in results):
            errors.append(f"{state.lower()} decision requires at least one failed criterion")

        receipts = decision.get("reviewed_receipts")
        if not isinstance(receipts, dict):
            receipts = {}
            errors.append("reviewed_receipts must be an object")
        required_names = contract["required_receipts"]
        if list(receipts.keys()) != required_names:
            errors.append("reviewed receipts must appear once, in contract order")
        for name in required_names:
            item = receipts.get(name, {})
            if not isinstance(item, dict):
                errors.append(f"receipt entry is not an object: {name}")
                continue
            digest = item.get("sha256")
            size = item.get("bytes")
            if not isinstance(digest, str) or len(digest) != 64:
                errors.append(f"receipt digest missing or malformed: {name}")
            if not isinstance(size, int) or size <= 0:
                errors.append(f"receipt size missing or malformed: {name}")
            if receipt_root is not None:
                path = receipt_root / name
                if not path.is_file():
                    errors.append(f"review receipt not found: {path}")
                else:
                    if path.stat().st_size != size:
                        errors.append(f"review receipt size drift: {name}")
                    if sha256(path) != digest:
                        errors.append(f"review receipt digest drift: {name}")

    if errors:
        raise DecisionError("; ".join(errors))
    return {
        "schema": "manzanita/useful-plant-v30-operator-decision-validation@1",
        "result": "PASS",
        "decision": state,
        "candidate": contract["candidate"],
        "operator_visual_acceptance": decision.get("operator_visual_acceptance"),
        **authority,
    }


def parse_criterion(values: list[str], expected_ids: list[str]) -> dict[str, tuple[str, str | None]]:
    parsed: dict[str, tuple[str, str | None]] = {}
    for value in values:
        if "=" not in value:
            raise DecisionError(f"criterion must use id=PASS or id=FAIL: {value}")
        criterion_id, rest = value.split("=", 1)
        if criterion_id not in expected_ids:
            raise DecisionError(f"unknown criterion id: {criterion_id}")
        if criterion_id in parsed:
            raise DecisionError(f"criterion repeated: {criterion_id}")
        if ":" in rest:
            result, notes = rest.split(":", 1)
            notes = notes.strip() or None
        else:
            result, notes = rest, None
        result = result.strip().upper()
        if result not in {"PASS", "FAIL"}:
            raise DecisionError(f"unsupported criterion result: {result}")
        parsed[criterion_id] = (result, notes)
    missing = [criterion_id for criterion_id in expected_ids if criterion_id not in parsed]
    if missing:
        raise DecisionError(f"criteria missing: {', '.join(missing)}")
    return parsed


def build_record(args: argparse.Namespace, contract: dict) -> dict:
    expected_ids = [item["id"] for item in contract["criteria"]]
    criterion_results = parse_criterion(args.criterion, expected_ids)
    receipt_root = args.receipt_root.resolve()
    receipts: dict[str, dict[str, object]] = {}
    for name in contract["required_receipts"]:
        path = receipt_root / name
        if not path.is_file():
            raise DecisionError(f"required review receipt not found: {path}")
        receipts[name] = {
            "path": name,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

    state = args.decision.upper()
    return {
        "schema": "manzanita/useful-plant-v30-operator-decision@1",
        "candidate": contract["candidate"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": state,
        "operator": args.operator.strip(),
        "rationale": args.rationale.strip(),
        "reviewed_receipts": receipts,
        "criteria": [
            {
                "id": criterion_id,
                "result": criterion_results[criterion_id][0],
                "notes": criterion_results[criterion_id][1],
            }
            for criterion_id in expected_ids
        ],
        "operator_visual_acceptance": "ACCEPTED" if state == "ACCEPTED" else "NOT_ACCEPTED",
        **contract["authority_invariants"],
        "claim_boundary": contract["explicit_non_authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("decision", type=Path)
    validate_parser.add_argument("--receipt-root", type=Path)
    validate_parser.add_argument("--output", type=Path)

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--decision", choices=["ACCEPTED", "REVISE", "REJECTED"], required=True)
    record_parser.add_argument("--operator", required=True)
    record_parser.add_argument("--rationale", required=True)
    record_parser.add_argument("--criterion", action="append", default=[], required=True)
    record_parser.add_argument("--receipt-root", type=Path, required=True)
    record_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    contract = load_json(CONTRACT_PATH)
    try:
        if args.command == "validate":
            decision = load_json(args.decision)
            receipt_root = args.receipt_root.resolve() if args.receipt_root else None
            result = validate(decision, contract, receipt_root)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            decision = build_record(args, contract)
            validate(decision, contract, args.receipt_root.resolve())
            output = args.output.resolve()
            if HERE in output.parents:
                raise DecisionError("recorded operator decisions must be written outside the candidate source tree")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({
                "result": "PASS_DECISION_RECORDED",
                "output": str(output),
                "decision": decision["decision"],
                "operator_visual_acceptance": decision["operator_visual_acceptance"],
                **contract["authority_invariants"],
            }, indent=2, sort_keys=True))
        return 0
    except DecisionError as error:
        print(json.dumps({"result": "FAIL", "error": str(error)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
