#!/usr/bin/env python3
"""Deterministic capability-gradient planner for the AXM Community Home Lab.

The planner is intentionally small and dependency-free. It does not optimize a
hidden scalar. It applies, in order:

1. evidence-tier and prerequisite admission;
2. removal of already-complete experiments;
3. Pareto fronts over explicit benefit and cost dimensions;
4. a documented lexicographic tie-break within each front.

The same input documents therefore produce the same plan body and digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_TIER_ORDER = [
    "unknown",
    "declared",
    "observed",
    "measured",
    "qualified",
    "accepted",
]


class PlannerError(ValueError):
    """Raised when an input contract is incomplete or internally inconsistent."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlannerError(f"missing input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlannerError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlannerError(f"root must be an object: {path}")
    return value


def require_keys(record: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    missing = [key for key in keys if key not in record]
    if missing:
        raise PlannerError(f"{label} missing keys: {', '.join(missing)}")


@dataclass(frozen=True)
class Requirement:
    capability: str
    tier: str


@dataclass(frozen=True)
class Production:
    capability: str
    tier: str


@dataclass(frozen=True)
class Cost:
    operator_minutes: float
    machine_minutes: float
    new_packages: int
    data_moved_gib: float
    risk: int
    irreversible: int

    @classmethod
    def from_record(cls, value: Mapping[str, Any], label: str) -> "Cost":
        require_keys(
            value,
            [
                "operator_minutes",
                "machine_minutes",
                "new_packages",
                "data_moved_gib",
                "risk",
                "irreversible",
            ],
            label,
        )
        return cls(
            operator_minutes=float(value["operator_minutes"]),
            machine_minutes=float(value["machine_minutes"]),
            new_packages=int(value["new_packages"]),
            data_moved_gib=float(value["data_moved_gib"]),
            risk=int(value["risk"]),
            irreversible=int(value["irreversible"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "operator_minutes": self.operator_minutes,
            "machine_minutes": self.machine_minutes,
            "new_packages": self.new_packages,
            "data_moved_gib": self.data_moved_gib,
            "risk": self.risk,
            "irreversible": self.irreversible,
        }


@dataclass(frozen=True)
class Experiment:
    id: str
    title: str
    class_name: str
    description: str
    requires: tuple[Requirement, ...]
    produces: tuple[Production, ...]
    cost: Cost
    acceptance: tuple[str, ...]
    artifacts: tuple[str, ...]
    commands: tuple[str, ...]


@dataclass(frozen=True)
class Capability:
    id: str
    title: str
    description: str
    dependencies: tuple[str, ...]
    minimum_tier: str


@dataclass(frozen=True)
class Goal:
    id: str
    title: str
    priority: str
    weight: int
    description: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Evaluation:
    experiment: Experiment
    missing: tuple[Requirement, ...]
    complete: bool
    benefits: Mapping[str, int]
    front: int | None = None
    rank: int | None = None


def parse_requirement(value: Any, capability_map: Mapping[str, Capability], label: str) -> Requirement:
    if isinstance(value, str):
        capability = value
        tier = capability_map.get(capability, Capability("", "", "", (), "qualified")).minimum_tier
    elif isinstance(value, Mapping):
        require_keys(value, ["capability", "tier"], label)
        capability = str(value["capability"])
        tier = str(value["tier"])
    else:
        raise PlannerError(f"{label} must be a capability string or object")
    if capability not in capability_map:
        raise PlannerError(f"{label} references unknown capability: {capability}")
    return Requirement(capability=capability, tier=tier)


def parse_production(value: Any, capability_map: Mapping[str, Capability], label: str) -> Production:
    if not isinstance(value, Mapping):
        raise PlannerError(f"{label} must be an object")
    require_keys(value, ["capability", "tier"], label)
    capability = str(value["capability"])
    tier = str(value["tier"])
    if capability not in capability_map:
        raise PlannerError(f"{label} references unknown capability: {capability}")
    return Production(capability=capability, tier=tier)


def parse_inputs(
    goals_doc: Mapping[str, Any], experiments_doc: Mapping[str, Any]
) -> tuple[list[str], dict[str, Capability], list[Goal], list[Experiment]]:
    tier_order = list(goals_doc.get("tier_order") or DEFAULT_TIER_ORDER)
    if len(set(tier_order)) != len(tier_order) or "unknown" not in tier_order:
        raise PlannerError("tier_order must contain unique values including unknown")

    raw_caps = goals_doc.get("capabilities")
    raw_goals = goals_doc.get("goals")
    raw_experiments = experiments_doc.get("experiments")
    if not isinstance(raw_caps, list) or not isinstance(raw_goals, list):
        raise PlannerError("goals document requires capabilities[] and goals[]")
    if not isinstance(raw_experiments, list):
        raise PlannerError("experiment document requires experiments[]")

    capabilities: dict[str, Capability] = {}
    for index, raw in enumerate(raw_caps):
        if not isinstance(raw, Mapping):
            raise PlannerError(f"capabilities[{index}] must be an object")
        require_keys(raw, ["id", "title", "description", "dependencies", "minimum_tier"], f"capabilities[{index}]")
        capability = Capability(
            id=str(raw["id"]),
            title=str(raw["title"]),
            description=str(raw["description"]),
            dependencies=tuple(str(item) for item in raw["dependencies"]),
            minimum_tier=str(raw["minimum_tier"]),
        )
        if capability.id in capabilities:
            raise PlannerError(f"duplicate capability: {capability.id}")
        if capability.minimum_tier not in tier_order:
            raise PlannerError(f"capability {capability.id} uses unknown tier {capability.minimum_tier}")
        capabilities[capability.id] = capability

    for capability in capabilities.values():
        unknown = [item for item in capability.dependencies if item not in capabilities]
        if unknown:
            raise PlannerError(f"capability {capability.id} has unknown dependencies: {unknown}")

    goals: list[Goal] = []
    seen_goals: set[str] = set()
    for index, raw in enumerate(raw_goals):
        if not isinstance(raw, Mapping):
            raise PlannerError(f"goals[{index}] must be an object")
        require_keys(raw, ["id", "title", "priority", "weight", "description", "requires"], f"goals[{index}]")
        goal = Goal(
            id=str(raw["id"]),
            title=str(raw["title"]),
            priority=str(raw["priority"]),
            weight=int(raw["weight"]),
            description=str(raw["description"]),
            requires=tuple(str(item) for item in raw["requires"]),
        )
        if goal.id in seen_goals:
            raise PlannerError(f"duplicate goal: {goal.id}")
        unknown = [item for item in goal.requires if item not in capabilities]
        if unknown:
            raise PlannerError(f"goal {goal.id} has unknown capabilities: {unknown}")
        seen_goals.add(goal.id)
        goals.append(goal)

    experiments: list[Experiment] = []
    seen_experiments: set[str] = set()
    for index, raw in enumerate(raw_experiments):
        if not isinstance(raw, Mapping):
            raise PlannerError(f"experiments[{index}] must be an object")
        label = f"experiments[{index}]"
        require_keys(
            raw,
            [
                "id",
                "title",
                "class",
                "description",
                "requires",
                "produces",
                "cost",
                "acceptance",
                "artifacts",
                "commands",
            ],
            label,
        )
        experiment_id = str(raw["id"])
        if experiment_id in seen_experiments:
            raise PlannerError(f"duplicate experiment: {experiment_id}")
        requires = tuple(
            parse_requirement(item, capabilities, f"{label}.requires[{item_index}]")
            for item_index, item in enumerate(raw["requires"])
        )
        produces = tuple(
            parse_production(item, capabilities, f"{label}.produces[{item_index}]")
            for item_index, item in enumerate(raw["produces"])
        )
        for requirement in requires:
            if requirement.tier not in tier_order:
                raise PlannerError(f"experiment {experiment_id} uses unknown requirement tier {requirement.tier}")
        for production in produces:
            if production.tier not in tier_order:
                raise PlannerError(f"experiment {experiment_id} uses unknown production tier {production.tier}")
        experiments.append(
            Experiment(
                id=experiment_id,
                title=str(raw["title"]),
                class_name=str(raw["class"]),
                description=str(raw["description"]),
                requires=requires,
                produces=produces,
                cost=Cost.from_record(raw["cost"], f"{label}.cost"),
                acceptance=tuple(str(item) for item in raw["acceptance"]),
                artifacts=tuple(str(item) for item in raw["artifacts"]),
                commands=tuple(str(item) for item in raw["commands"]),
            )
        )
        seen_experiments.add(experiment_id)

    return tier_order, capabilities, goals, experiments


def tier_index(tier_order: Sequence[str]) -> dict[str, int]:
    return {tier: index for index, tier in enumerate(tier_order)}


def tier_meets(current: str, required: str, tiers: Mapping[str, int]) -> bool:
    try:
        return tiers[current] >= tiers[required]
    except KeyError as exc:
        raise PlannerError(f"unknown tier: {exc.args[0]}") from exc


def evidence_states(
    evidence_doc: Mapping[str, Any],
    capabilities: Mapping[str, Capability],
    tiers: Mapping[str, int],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    states = {capability_id: "unknown" for capability_id in capabilities}
    record_ids: dict[str, list[str]] = {capability_id: [] for capability_id in capabilities}
    raw_records = evidence_doc.get("records")
    if not isinstance(raw_records, list):
        raise PlannerError("evidence document requires records[]")
    seen: set[str] = set()
    for index, record in enumerate(raw_records):
        if not isinstance(record, Mapping):
            raise PlannerError(f"evidence.records[{index}] must be an object")
        require_keys(record, ["id", "tier", "supports"], f"evidence.records[{index}]")
        record_id = str(record["id"])
        if record_id in seen:
            raise PlannerError(f"duplicate evidence record: {record_id}")
        seen.add(record_id)
        record_tier = str(record["tier"])
        if record_tier not in tiers:
            raise PlannerError(f"evidence {record_id} uses unknown tier {record_tier}")
        supports = record["supports"]
        if not isinstance(supports, list):
            raise PlannerError(f"evidence {record_id}.supports must be an array")
        for item_index, item in enumerate(supports):
            if isinstance(item, str):
                capability = item
                support_tier = record_tier
            elif isinstance(item, Mapping):
                require_keys(item, ["capability"], f"evidence {record_id}.supports[{item_index}]")
                capability = str(item["capability"])
                support_tier = str(item.get("tier", record_tier))
            else:
                raise PlannerError(f"evidence {record_id}.supports[{item_index}] must be a string or object")
            if capability not in capabilities:
                raise PlannerError(f"evidence {record_id} supports unknown capability {capability}")
            if support_tier not in tiers:
                raise PlannerError(f"evidence {record_id} uses unknown support tier {support_tier}")
            if tiers[support_tier] > tiers[states[capability]]:
                states[capability] = support_tier
                record_ids[capability] = [record_id]
            elif tiers[support_tier] == tiers[states[capability]]:
                record_ids[capability].append(record_id)
    return states, record_ids


def requirement_satisfied(requirement: Requirement, states: Mapping[str, str], tiers: Mapping[str, int]) -> bool:
    return tier_meets(states[requirement.capability], requirement.tier, tiers)


def production_satisfied(production: Production, states: Mapping[str, str], tiers: Mapping[str, int]) -> bool:
    return tier_meets(states[production.capability], production.tier, tiers)


def advance_states(
    states: Mapping[str, str], productions: Sequence[Production], tiers: Mapping[str, int]
) -> dict[str, str]:
    advanced = dict(states)
    for production in productions:
        if tiers[production.tier] > tiers[advanced[production.capability]]:
            advanced[production.capability] = production.tier
    return advanced


def compute_benefits(
    experiment: Experiment,
    states: Mapping[str, str],
    tiers: Mapping[str, int],
    goals: Sequence[Goal],
    experiments: Sequence[Experiment],
    capabilities: Mapping[str, Capability],
) -> dict[str, int]:
    produced_gaps = {
        production.capability
        for production in experiment.produces
        if not production_satisfied(production, states, tiers)
    }
    touched_goals: set[str] = set()
    must_goals: set[str] = set()
    direct_gap_weight = 0
    must_gap_weight = 0
    for goal in goals:
        goal_touched = False
        for capability_id in goal.requires:
            required_tier = capabilities[capability_id].minimum_tier
            if capability_id in produced_gaps and not tier_meets(states[capability_id], required_tier, tiers):
                direct_gap_weight += goal.weight
                if goal.priority == "must":
                    must_gap_weight += goal.weight
                goal_touched = True
        if goal_touched:
            touched_goals.add(goal.id)
            if goal.priority == "must":
                must_goals.add(goal.id)

    advanced = advance_states(states, experiment.produces, tiers)
    unlock_count = 0
    unlock_goal_ids: set[str] = set()
    for other in experiments:
        if other.id == experiment.id:
            continue
        before_missing = [req for req in other.requires if not requirement_satisfied(req, states, tiers)]
        after_missing = [req for req in other.requires if not requirement_satisfied(req, advanced, tiers)]
        if before_missing and not after_missing:
            unlock_count += 1
            other_outputs = {item.capability for item in other.produces}
            for goal in goals:
                if other_outputs.intersection(goal.requires):
                    unlock_goal_ids.add(goal.id)

    unlock_goal_weight = sum(goal.weight for goal in goals if goal.id in unlock_goal_ids)
    return {
        "must_gap_weight": must_gap_weight,
        "direct_gap_weight": direct_gap_weight,
        "goal_count": len(touched_goals),
        "must_goal_count": len(must_goals),
        "unlock_count": unlock_count,
        "unlock_goal_weight": unlock_goal_weight,
        "capability_count": len(produced_gaps),
    }


BENEFIT_KEYS = (
    "must_gap_weight",
    "direct_gap_weight",
    "unlock_count",
    "unlock_goal_weight",
    "goal_count",
    "capability_count",
)
COST_KEYS = (
    "operator_minutes",
    "machine_minutes",
    "new_packages",
    "data_moved_gib",
    "risk",
    "irreversible",
)


def dominates(left: Evaluation, right: Evaluation) -> bool:
    left_cost = left.experiment.cost.as_dict()
    right_cost = right.experiment.cost.as_dict()
    benefits_no_worse = all(left.benefits[key] >= right.benefits[key] for key in BENEFIT_KEYS)
    costs_no_worse = all(left_cost[key] <= right_cost[key] for key in COST_KEYS)
    if not benefits_no_worse or not costs_no_worse:
        return False
    benefit_strict = any(left.benefits[key] > right.benefits[key] for key in BENEFIT_KEYS)
    cost_strict = any(left_cost[key] < right_cost[key] for key in COST_KEYS)
    return benefit_strict or cost_strict


def pareto_fronts(evaluations: Sequence[Evaluation]) -> list[list[Evaluation]]:
    remaining = list(evaluations)
    fronts: list[list[Evaluation]] = []
    while remaining:
        front = [candidate for candidate in remaining if not any(dominates(other, candidate) for other in remaining if other is not candidate)]
        if not front:
            raise PlannerError("Pareto front construction stalled")
        fronts.append(front)
        selected = {item.experiment.id for item in front}
        remaining = [item for item in remaining if item.experiment.id not in selected]
    return fronts


def tie_break_key(item: Evaluation) -> tuple[Any, ...]:
    cost = item.experiment.cost
    benefits = item.benefits
    return (
        -benefits["must_gap_weight"],
        -benefits["direct_gap_weight"],
        -benefits["unlock_count"],
        -benefits["unlock_goal_weight"],
        -benefits["goal_count"],
        -benefits["capability_count"],
        cost.operator_minutes,
        cost.machine_minutes,
        cost.new_packages,
        cost.risk,
        cost.irreversible,
        cost.data_moved_gib,
        item.experiment.id,
    )


def shortest_enabling_chain(
    target: Experiment,
    evaluations: Mapping[str, Evaluation],
    experiments: Sequence[Experiment],
    tiers: Mapping[str, int],
    states: Mapping[str, str],
    max_depth: int = 8,
) -> list[str]:
    producers: dict[str, list[Experiment]] = {}
    for experiment in experiments:
        for production in experiment.produces:
            producers.setdefault(production.capability, []).append(experiment)

    visiting: set[str] = set()

    def solve(experiment: Experiment, depth: int) -> list[str] | None:
        evaluation = evaluations[experiment.id]
        if not evaluation.missing:
            return [experiment.id]
        if depth >= max_depth or experiment.id in visiting:
            return None
        visiting.add(experiment.id)
        chain: list[str] = []
        for requirement in evaluation.missing:
            options = [
                producer
                for producer in producers.get(requirement.capability, [])
                if any(
                    production.capability == requirement.capability
                    and tier_meets(production.tier, requirement.tier, tiers)
                    for production in producer.produces
                )
            ]
            best: list[str] | None = None
            for producer in sorted(options, key=lambda item: (item.cost.operator_minutes, item.cost.machine_minutes, item.id)):
                candidate = solve(producer, depth + 1)
                if candidate is not None and (best is None or len(candidate) < len(best) or (len(candidate) == len(best) and candidate < best)):
                    best = candidate
            if best is None:
                visiting.remove(experiment.id)
                return None
            for item in best:
                if item not in chain:
                    chain.append(item)
        visiting.remove(experiment.id)
        if experiment.id not in chain:
            chain.append(experiment.id)
        return chain

    result = solve(target, 0)
    return result or []


def build_plan(
    estate_doc: Mapping[str, Any],
    goals_doc: Mapping[str, Any],
    experiments_doc: Mapping[str, Any],
    evidence_doc: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    tier_order, capabilities, goals, experiments = parse_inputs(goals_doc, experiments_doc)
    tiers = tier_index(tier_order)
    states, record_ids = evidence_states(evidence_doc, capabilities, tiers)

    evaluations: list[Evaluation] = []
    for experiment in experiments:
        missing = tuple(req for req in experiment.requires if not requirement_satisfied(req, states, tiers))
        complete = all(production_satisfied(production, states, tiers) for production in experiment.produces)
        benefits = compute_benefits(experiment, states, tiers, goals, experiments, capabilities)
        evaluations.append(
            Evaluation(
                experiment=experiment,
                missing=missing,
                complete=complete,
                benefits=benefits,
            )
        )

    admissible = [item for item in evaluations if not item.complete and not item.missing]
    fronts = pareto_fronts(admissible) if admissible else []
    ranked: list[Evaluation] = []
    for front_index, front in enumerate(fronts):
        for item in sorted(front, key=tie_break_key):
            ranked.append(
                Evaluation(
                    experiment=item.experiment,
                    missing=item.missing,
                    complete=item.complete,
                    benefits=item.benefits,
                    front=front_index,
                    rank=len(ranked) + 1,
                )
            )

    evaluation_by_id: dict[str, Evaluation] = {item.experiment.id: item for item in evaluations}
    for item in ranked:
        evaluation_by_id[item.experiment.id] = item

    capability_rows = []
    for capability in capabilities.values():
        state = states[capability.id]
        capability_rows.append(
            {
                "id": capability.id,
                "title": capability.title,
                "description": capability.description,
                "state": state,
                "minimum_tier": capability.minimum_tier,
                "satisfied": tier_meets(state, capability.minimum_tier, tiers),
                "dependencies": list(capability.dependencies),
                "evidence_records": record_ids[capability.id],
            }
        )

    goal_rows = []
    for goal in goals:
        required = []
        satisfied_count = 0
        for capability_id in goal.requires:
            capability = capabilities[capability_id]
            current = states[capability_id]
            satisfied = tier_meets(current, capability.minimum_tier, tiers)
            satisfied_count += int(satisfied)
            required.append(
                {
                    "capability": capability_id,
                    "title": capability.title,
                    "state": current,
                    "required_tier": capability.minimum_tier,
                    "satisfied": satisfied,
                }
            )
        goal_rows.append(
            {
                "id": goal.id,
                "title": goal.title,
                "priority": goal.priority,
                "weight": goal.weight,
                "description": goal.description,
                "satisfied": satisfied_count == len(required),
                "satisfied_count": satisfied_count,
                "required_count": len(required),
                "requirements": required,
            }
        )

    def serialize_evaluation(item: Evaluation) -> dict[str, Any]:
        experiment = item.experiment
        return {
            "id": experiment.id,
            "title": experiment.title,
            "class": experiment.class_name,
            "description": experiment.description,
            "status": "complete" if item.complete else ("admissible" if not item.missing else "blocked"),
            "rank": item.rank,
            "pareto_front": item.front,
            "requires": [requirement.__dict__ for requirement in experiment.requires],
            "missing": [requirement.__dict__ for requirement in item.missing],
            "produces": [production.__dict__ for production in experiment.produces],
            "benefits": dict(item.benefits),
            "cost": experiment.cost.as_dict(),
            "acceptance": list(experiment.acceptance),
            "artifacts": list(experiment.artifacts),
            "commands": list(experiment.commands),
        }

    ranked_ids = {item.experiment.id for item in ranked}
    blocked = sorted(
        [item for item in evaluations if not item.complete and item.missing],
        key=lambda item: (
            len(item.missing),
            -item.benefits["must_gap_weight"],
            -item.benefits["direct_gap_weight"],
            item.experiment.cost.operator_minutes,
            item.experiment.id,
        ),
    )
    complete = sorted([item for item in evaluations if item.complete], key=lambda item: item.experiment.id)

    all_serialized = []
    for experiment in experiments:
        evaluation = evaluation_by_id[experiment.id]
        serialized = serialize_evaluation(evaluation)
        if evaluation.missing:
            serialized["enabling_chain"] = shortest_enabling_chain(
                experiment,
                evaluation_by_id,
                experiments,
                tiers,
                states,
            )
        else:
            serialized["enabling_chain"] = [experiment.id]
        all_serialized.append(serialized)

    top = [serialize_evaluation(item) for item in ranked[:3]]
    next_rows = []
    for item in blocked[:6]:
        row = serialize_evaluation(item)
        row["enabling_chain"] = shortest_enabling_chain(item.experiment, evaluation_by_id, experiments, tiers, states)
        next_rows.append(row)

    input_digests = {
        "estate": sha256_json(estate_doc),
        "goals": sha256_json(goals_doc),
        "experiments": sha256_json(experiments_doc),
        "evidence": sha256_json(evidence_doc),
    }
    plan: dict[str, Any] = {
        "schema": "axm-community-lab/capability-gradient-plan@1",
        "generated_at": generated_at,
        "estate_id": estate_doc.get("estate_id"),
        "input_digests": input_digests,
        "method": {
            "admission": "An experiment is admissible only when every required capability meets its declared evidence tier.",
            "completion": "An experiment is complete only when every produced capability already meets the experiment's production tier.",
            "fronts": "Admissible experiments are separated into Pareto fronts over explicit benefit and cost dimensions; no hidden total score is used.",
            "benefits_maximized": list(BENEFIT_KEYS),
            "costs_minimized": list(COST_KEYS),
            "tie_break": [
                "must_gap_weight descending",
                "direct_gap_weight descending",
                "unlock_count descending",
                "unlock_goal_weight descending",
                "goal_count descending",
                "capability_count descending",
                "operator_minutes ascending",
                "machine_minutes ascending",
                "new_packages ascending",
                "risk ascending",
                "irreversible ascending",
                "data_moved_gib ascending",
                "experiment id ascending",
            ],
        },
        "summary": {
            "capability_count": len(capabilities),
            "capabilities_satisfied": sum(1 for row in capability_rows if row["satisfied"]),
            "goal_count": len(goals),
            "goals_satisfied": sum(1 for row in goal_rows if row["satisfied"]),
            "experiment_count": len(experiments),
            "experiments_admissible": len(ranked),
            "experiments_blocked": len(blocked),
            "experiments_complete": len(complete),
        },
        "capabilities": capability_rows,
        "goals": goal_rows,
        "now": top,
        "next": next_rows,
        "ranked_admissible": [serialize_evaluation(item) for item in ranked],
        "blocked": [serialize_evaluation(item) for item in blocked],
        "complete": [serialize_evaluation(item) for item in complete],
        "experiments": all_serialized,
        "control_question": "Which smallest reversible experiment closes a currently required capability gap, unlocks the most valuable downstream work, and produces acceptance evidence without adding a new serial dependency to the estate?",
        "claim_boundary": "The plan ranks bounded experiments from supplied evidence. It does not claim the estate has executed them, that estimated costs are measured, or that a recommended experiment will improve wall clock until its acceptance comparison passes.",
    }
    digest_body = dict(plan)
    digest_body.pop("generated_at", None)
    plan["plan_sha256"] = sha256_json(digest_body)
    return plan


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estate", type=Path, required=True)
    parser.add_argument("--goals", type=Path, required=True)
    parser.add_argument("--experiments", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now", default="2026-08-05T00:00:00Z", help="explicit generation timestamp")
    args = parser.parse_args(argv)

    plan = build_plan(
        read_json(args.estate),
        read_json(args.goals),
        read_json(args.experiments),
        read_json(args.evidence),
        generated_at=args.now,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "plan_sha256": plan["plan_sha256"], "top": [item["id"] for item in plan["now"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
