#!/usr/bin/env python3
"""Independent stdlib receiver for the pinned Industrial Continuity contract.

This program does not execute or import JavaScript. It independently parses the
six bounded source mappings, optimizes the integer plan, and recomputes every
retained decision. ``packet.engine`` identifies the original contract bytes;
execution receipts separately identify this Python implementation.

Explicit receiver admission boundaries: UTF-8 JSON with unique object members,
safe integer-valued JSON numbers, and calendar-valid, timezone-qualified ISO
timestamps (four-digit year, uppercase T/Z, seconds, optional fractional
seconds). The JavaScript donor accepts some additional Date.parse spellings;
this receiver refuses those explicitly rather than inventing their meaning.
Source raw strings retain their exact text, including Unicode and line endings.
Hashes bind canonical JSON objects, not the whitespace of a JSON transport file.
Execution receipts separately bind the transport file bytes.

No network, model, device, business-system, or operational-control interface is
present. Local output files and unverified reviewer labels confer no authority.
"""
from __future__ import annotations

import argparse
import calendar
import copy
import hashlib
import json
import math
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "axm-industrial-continuity/0.1.0"
RECIPE = "two-product-two-stage-integer-planning/1"
IDS = ("orders", "routing", "capacity", "maintenance", "quality", "procedure")
HEADERS = {
    "orders": ("sku", "demand_units", "contribution_usd_per_unit"),
    "routing": ("sku", "mix_min_per_unit", "pack_min_per_unit"),
    "capacity": ("stage", "available_min"),
    "maintenance": ("job", "part", "serviceable", "allocated", "recovery_mix_min",
                    "repair_cost_usd", "expedite_cost_usd", "supplier_lead_hours",
                    "decision_window_hours"),
    "quality": ("sku", "released"),
    "procedure": ("procedure", "revision", "planning_allowed", "review_role"),
}
DONOR_ENGINE_SHA256 = "130471df834984b42a51719653d754a8ce28e3f24aa45da1dd58adbfb4e1e794"
DONOR_CORE_SHA256 = "0158ea96c0c99a4f479e37573bacf26916348318e2811b75196ce390cab36cdd"
MAX_PACKET_BYTES = 4 * 1024 * 1024
MAX_SAFE_INTEGER = 9007199254740991
JS_WHITESPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
ISO_TIME = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?(Z|[+-][0-9]{2}:[0-9]{2})\Z")


class ContractError(ValueError):
    """A received object or requested transition falls outside this contract."""


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ContractError(message)


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le", "surrogatepass")) // 2


def js_trim(value: str) -> str:
    return value.strip(JS_WHITESPACE)


def _json_string(value: str) -> str:
    # JSON.stringify escapes unpaired UTF-16 surrogates. Python's non-ASCII
    # serializer leaves them in the string, so make that behavior explicit.
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "".join("\\u%04x" % ord(ch) if 0xD800 <= ord(ch) <= 0xDFFF else ch
                   for ch in rendered)


def canonical(value: Any) -> str:
    """Match donor canonical JSON for the admitted finite integer contract."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        require(not isinstance(value, float) or (math.isfinite(value) and value.is_integer()),
                "Receiver admits only finite integer-valued JSON numbers.")
        require(abs(value) <= MAX_SAFE_INTEGER, "JSON number exceeds the receiver's exact integer boundary.")
        return str(int(value))
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "JSON object keys must be strings.")
        keys = sorted(value, key=lambda key: key.encode("utf-16-be", "surrogatepass"))
        return "{" + ",".join(_json_string(key) + ":" + canonical(value[key]) for key in keys) + "}"
    raise ContractError("Unsupported value in canonical JSON.")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def byte_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON member is outside receiver admission: " + key)
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ContractError("Non-finite JSON constant is outside receiver admission: " + value)


def _integer_token(value: str) -> int:
    # Reject before Python attempts a potentially enormous decimal conversion.
    # Every admitted integer has at most sixteen significant decimal digits.
    require(len(value.lstrip("-")) <= 16,
            "JSON integer token exceeds the receiver's exact integer boundary.")
    number = int(value)
    require(abs(number) <= MAX_SAFE_INTEGER,
            "JSON number exceeds the receiver's exact integer boundary.")
    return number


def loads(raw: bytes | str) -> Any:
    require(len(raw if isinstance(raw, bytes) else raw.encode("utf-8")) <= MAX_PACKET_BYTES,
            "Handoff exceeds 4 MiB.")
    try:
        text = raw.decode("utf-8", "strict") if isinstance(raw, bytes) else raw
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant,
                           parse_int=_integer_token)
        canonical(value)  # Reject unsupported numeric values before processing.
        return value
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContractError("Invalid UTF-8 JSON handoff: " + str(exc)) from exc


def exact(value: Any, keys: tuple | list) -> bool:
    return isinstance(value, dict) and set(value) == set(keys)


def is_hex(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def is_integer(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        not isinstance(value, float) or (math.isfinite(value) and value.is_integer()))


def timestamp(value: Any) -> int:
    """UTC milliseconds; refuse ambiguous or normalized-invalid Date.parse forms."""
    require(isinstance(value, str), "Observation time must be a timezone-qualified ISO string.")
    match = ISO_TIME.fullmatch(value)
    require(match is not None,
            "Receiver requires a calendar-valid timezone-qualified ISO timestamp with seconds; alternate Date.parse spellings are unsupported.")
    y, mo, day, hour, minute, second = map(int, match.groups()[:6])
    fraction, zone = match.group(7), match.group(8)
    require(1 <= y <= 9999 and 1 <= mo <= 12 and 0 <= hour <= 23 and
            0 <= minute <= 59 and 0 <= second <= 59,
            "Observation time is outside the receiver's ISO calendar boundary.")
    require(1 <= day <= calendar.monthrange(y, mo)[1],
            "Receiver refuses calendar-invalid dates rather than normalizing them.")
    offset = 0
    if zone != "Z":
        zh, zm = int(zone[1:3]), int(zone[4:6])
        require(zh <= 23 and zm <= 59, "Invalid ISO timezone offset.")
        offset = (zh * 60 + zm) * (1 if zone[0] == "+" else -1)
    millis = int(((fraction or "") + "000")[:3])
    local = datetime(y, mo, day, hour, minute, second)
    delta = local - datetime(1970, 1, 1)
    return (delta.days * 86400 + delta.seconds - offset * 60) * 1000 + millis


def contract_identity(vendor_dir: Path | None = None) -> dict:
    vendor = vendor_dir or Path(__file__).resolve().parent.parent / "vendor"
    engine, core = (vendor / "engine.js").read_bytes(), (vendor / "commons-core.js").read_bytes()
    engine_sha, core_sha = byte_digest(engine), byte_digest(core)
    require(engine_sha == DONOR_ENGINE_SHA256 and core_sha == DONOR_CORE_SHA256,
            "Changed donor source: this independent receiver requires explicit contract requalification.")
    combined = byte_digest(b"axm-industrial-engine/1\0" + engine + b"\0" + core)
    return {"engine_sha256": combined, "engine_file_sha256": engine_sha,
            "commons_core_file_sha256": core_sha, "recipe": RECIPE,
            "identity_meaning": "Pinned donor contract; Python does not execute JavaScript."}


def csv(source: str, raw: str) -> list[dict[str, str]]:
    require(source in IDS and isinstance(raw, str) and utf16_length(raw) <= 32768,
            "Unknown source or oversized CSV.")
    require(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", raw) is None,
            "Control characters are not accepted.")
    lines = raw.replace("\r\n", "\n").rstrip(JS_WHITESPACE).split("\n")
    require(2 <= len(lines) <= 20, "Expected a header and bounded data rows.")
    require("|".join(lines[0].split(",")) == "|".join(HEADERS[source]),
            "CSV headers do not match the declared " + source + " mapping.")
    rows = []
    for line in lines[1:]:
        values = line.split(",")
        require(len(values) == len(HEADERS[source]),
                "Quoted/extra CSV fields are outside this bounded mapping.")
        rows.append(dict(zip(HEADERS[source], (js_trim(v) for v in values))))
    require(len(rows) == (1 if source in ("maintenance", "procedure") else 2),
            "This recipe expects two products, two stages and one maintenance/review record.")
    if source in ("orders", "routing", "quality"):
        require(sorted(row["sku"] for row in rows) == ["A", "B"],
                "This pinned example accepts unique products A and B.")
    if source == "capacity":
        require(sorted(row["stage"] for row in rows) == ["mix", "pack"],
                "Expected unique mix and pack stages.")
    return rows


def numeric(value: str, name: str, issues: list[str], *, maximum: int = 1000000,
            minimum: int = 0, money: bool = False) -> int | None:
    if value == "":
        issues.append(name + ": missing")
        return None
    pattern = r"(0|[1-9][0-9]*)(\.[0-9]{1,2})?" if money else r"(0|[1-9][0-9]*)"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        issues.append(name + ": invalid")
        return None
    # Bounded decimal parsing avoids float rounding and Python's giant-int limit.
    whole, _, fraction = value.partition(".")
    if len(whole) > len(str(maximum)):
        issues.append(name + ": outside declared range")
        return None
    number = int(whole)
    if money:
        cents = number * 100 + int((fraction + "00")[:2])
        if not minimum * 100 <= cents <= maximum * 100:
            issues.append(name + ": outside declared range")
            return None
        return cents
    if not minimum <= number <= maximum:
        issues.append(name + ": outside declared range")
        return None
    return number


def input_from(records: list[dict]) -> dict:
    issues: list[str] = []
    rows: dict[str, list[dict]] = {}
    for source in IDS:
        record = next((r for r in records if r.get("source") == source), None)
        if record is None:
            issues.append(source + ": missing source")
            continue
        try:
            rows[source] = csv(source, record["raw"])
        except ContractError as exc:
            issues.append(source + ": " + str(exc))
    if issues:
        return {"issues": issues}
    products = []
    for sku in ("A", "B"):
        order = next(r for r in rows["orders"] if r["sku"] == sku)
        route = next(r for r in rows["routing"] if r["sku"] == sku)
        quality = next(r for r in rows["quality"] if r["sku"] == sku)
        products.append({
            "sku": sku,
            "demand": numeric(order["demand_units"], sku + " demand", issues, maximum=500),
            "margin": numeric(order["contribution_usd_per_unit"], sku + " contribution", issues, money=True, maximum=100000),
            "mix": numeric(route["mix_min_per_unit"], sku + " mix minutes", issues, minimum=1, maximum=1000),
            "pack": numeric(route["pack_min_per_unit"], sku + " pack minutes", issues, minimum=1, maximum=1000),
            "released": numeric(quality["released"], sku + " quality release", issues, maximum=1),
        })
    capacity = {r["stage"]: numeric(r["available_min"], r["stage"] + " capacity", issues)
                for r in rows["capacity"]}
    m, p = rows["maintenance"][0], rows["procedure"][0]
    maintenance = {
        "job": m["job"], "part": m["part"],
        "serviceable": numeric(m["serviceable"], "serviceable parts", issues, maximum=10000),
        "allocated": numeric(m["allocated"], "allocated parts", issues, maximum=10000),
        "recovery": numeric(m["recovery_mix_min"], "recovery minutes", issues),
        "cost": numeric(m["repair_cost_usd"], "repair cost", issues, money=True),
        "expedite": numeric(m["expedite_cost_usd"], "expedite cost", issues, money=True),
        "lead": numeric(m["supplier_lead_hours"], "supplier lead hours", issues, maximum=8760),
        "window": numeric(m["decision_window_hours"], "decision window hours", issues, maximum=168),
    }
    if maintenance["allocated"] is not None and maintenance["serviceable"] is not None and maintenance["allocated"] > maintenance["serviceable"]:
        issues.append("Allocated parts exceed serviceable parts.")
    label = lambda value: re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value) is not None
    if not label(m["job"]) or not label(m["part"]):
        issues.append("Maintenance identifiers invalid.")
    procedure = {
        "id": p["procedure"],
        "revision": numeric(p["revision"], "procedure revision", issues, minimum=1, maximum=9999),
        "allowed": numeric(p["planning_allowed"], "procedure planning scope", issues, maximum=1),
        "role": p["review_role"],
    }
    if not label(p["procedure"]) or not label(p["review_role"]):
        issues.append("Procedure/role labels invalid.")
    return {"issues": issues, "products": products, "capacity": capacity,
            "maintenance": maintenance, "procedure": procedure}


def solve(products: list[dict], capacity: dict, cost: int) -> dict:
    """Independent optimizer: one-dimensional feasible-bound enumeration.

    All margins are nonnegative and unit times positive. For each A quantity,
    the largest feasible B quantity maximizes margin, and then unit count.
    Scanning A in ascending order preserves the donor's final equal-score tie.
    """
    a_product, b_product = products
    a_max = a_product["demand"] if a_product["released"] else 0
    b_max = b_product["demand"] if b_product["released"] else 0
    best = None
    for a in range(a_max + 1):
        mix_left = capacity["mix"] - a * a_product["mix"]
        pack_left = capacity["pack"] - a * a_product["pack"]
        if mix_left < 0 or pack_left < 0:
            continue
        b = min(b_max, mix_left // b_product["mix"], pack_left // b_product["pack"])
        gross = a * a_product["margin"] + b * b_product["margin"]
        net, units = gross - cost, a + b
        if best is not None and (net, units) <= (best["net_cents"], best["units"]):
            continue
        used = {"mix": a * a_product["mix"] + b * b_product["mix"],
                "pack": a * a_product["pack"] + b * b_product["pack"]}
        best = {"a": a, "b": b, "units": units, "gross_cents": gross,
                "cost_cents": cost, "net_cents": net, "used": used,
                "available": copy.deepcopy(capacity),
                "slack": {key: capacity[key] - used[key] for key in ("mix", "pack")}}
    require(best is not None, "No feasible zero-unit plan inside the admitted contract.")
    return best


def calculate(records: list[dict]) -> dict:
    parsed = input_from(records)
    base = {"recipe": RECIPE, "scope": "Record-based planning only",
            "operational_authority": False, "external_effects": False}
    if parsed["issues"]:
        return {**base, "status": "INCONCLUSIVE", "issues": parsed["issues"]}
    products, capacity = parsed["products"], parsed["capacity"]
    m, p = parsed["maintenance"], parsed["procedure"]
    candidates = [
        {"id": "existing-capacity", "label": "Use existing capacity", "eligible": True,
         "cost": 0, "recovery": 0, "reason": "Plan inside the current two-stage envelope."},
        {"id": "planned-recovery", "label": "Recover mixing capacity",
         "eligible": bool(p["allowed"]) and m["serviceable"] - m["allocated"] >= 1,
         "cost": m["cost"], "recovery": m["recovery"],
         "reason": "Procedure is outside planning scope." if not p["allowed"] else
                   "No unallocated serviceable part on record." if m["serviceable"] - m["allocated"] < 1 else
                   "One part available; recovery remains a planning assumption."},
        {"id": "expedited-recovery", "label": "Expedite a replacement part",
         "eligible": bool(p["allowed"]) and m["lead"] <= m["window"],
         "cost": m["cost"] + m["expedite"], "recovery": m["recovery"],
         "reason": "Procedure is outside planning scope." if not p["allowed"] else
                   "Supplier arrival falls after the decision window." if m["lead"] > m["window"] else
                   "Arrival fits the declared window; supplier performance is unverified."},
    ]
    for option in candidates:
        option["plan"] = solve(products, {"mix": capacity["mix"] + option["recovery"], "pack": capacity["pack"]}, option["cost"]) if option["eligible"] else None
    chosen = min((option for option in candidates if option["eligible"]),
                 key=lambda option: (-option["plan"]["net_cents"], option["cost"], option["id"]))
    plan = chosen["plan"]
    demand_met = all(plan["a" if i == 0 else "b"] >= (product["demand"] if product["released"] else 0)
                     for i, product in enumerate(products))
    mix_slack, pack_slack = plan["slack"]["mix"], plan["slack"]["pack"]
    limiting = ("released demand" if demand_met else "mix + pack" if mix_slack == pack_slack == 0 else
                "mix" if mix_slack == 0 else "pack" if pack_slack == 0 else "integer product mix")
    baseline = candidates[0]["plan"]["net_cents"]
    return {**base, "status": "COMPUTED", "input": parsed, "chosen": chosen["id"],
            "plan": plan, "candidates": candidates, "baseline_net_cents": baseline,
            "incremental_net_cents": plan["net_cents"] - baseline, "limiting": limiting,
            "review_role": p["role"],
            "explanation": "The released order mix is best served within the existing capacity envelope. Extra asset capacity does not improve this objective after cost." if chosen["id"] == "existing-capacity" else
                           "The declared recovery increases planned contribution after intervention cost. Physical recovery and customer outcomes remain unobserved."}


def latest(state: dict) -> list[dict]:
    by = {source["source"]: source for source in state["sources"]}
    return [by[source] for source in IDS if source in by]


def frontier(state: dict) -> list[str]:
    return [source["sha256"] for source in latest(state)]


def current(state: dict) -> bool:
    return bool(state["decisions"]) and frontier(state) == state["decisions"][-1]["frontier"]


def review_status(state: dict) -> str:
    if not state["reviews"]:
        return "UNREVIEWED"
    return "RECORDED_LABEL_ONLY" if current(state) and state["reviews"][-1]["decision"] == state["decisions"][-1]["sha256"] else "STALE"


def verify_source(source: dict) -> None:
    require(exact(source, ("schema", "source", "revision", "previous", "evidence_class", "observed_at", "raw", "sha256")) and source["schema"] == "axm-process-source/1", "Invalid source schema.")
    require(is_integer(source["revision"]) and 1 <= source["revision"] <= 200, "Invalid source revision.")
    require(source["previous"] is None or is_hex(source["previous"]), "Invalid predecessor.")
    require(source["evidence_class"] in ("synthetic-fixture", "operator-supplied-unverified"), "Invalid evidence class/time.")
    timestamp(source["observed_at"])
    csv(source["source"], source["raw"])
    require(source["sha256"] == digest({key: value for key, value in source.items() if key != "sha256"}),
            "Changed source bytes or metadata: " + source["source"])


def restore(packet: dict, expected_engine: str | None = None) -> dict:
    identity = contract_identity()
    expected = identity["engine_sha256"]
    require(expected_engine is None or expected_engine == expected, "Requested engine is outside this receiver's pinned contract.")
    require(exact(packet, ("schema", "engine", "recipe", "sources", "decisions", "reviews", "sha256")) and packet["schema"] == VERSION and packet["recipe"] == RECIPE,
            "Unknown handoff schema/recipe.")
    require(packet["engine"] == expected and is_hex(expected), "Different engine: explicit migration and requalification required.")
    require(isinstance(packet["sources"], list) and 6 <= len(packet["sources"]) <= 200 and
            isinstance(packet["decisions"], list) and len(packet["decisions"]) <= 64 and
            isinstance(packet["reviews"], list) and len(packet["reviews"]) <= 64,
            "Invalid or oversized handoff.")
    state = {key: value for key, value in packet.items() if key != "sha256"}
    require(packet["sha256"] == digest(state), "Handoff digest mismatch.")
    by: dict = {}
    seen: dict = {}
    prefixes: list[list[str]] = []
    for source in state["sources"]:
        verify_source(source)
        previous = by.get(source["source"])
        require(source["sha256"] not in seen, "Duplicate source receipt.")
        require((source["previous"] == previous["sha256"] and source["revision"] == previous["revision"] + 1)
                if previous else (source["previous"] is None and source["revision"] == 1),
                "Orphan or forked source revision.")
        if previous:
            require(timestamp(source["observed_at"]) >= timestamp(previous["observed_at"]), "Successor observation predates predecessor.")
        by[source["source"]] = source
        seen[source["sha256"]] = source
        prefixes.append([by[s]["sha256"] for s in IDS if s in by])
    require(all(source in by for source in IDS), "Missing source family.")
    last_prefix = -1
    decisions: dict[str, dict] = {}
    for index, decision in enumerate(state["decisions"]):
        require(exact(decision, ("schema", "sequence", "engine", "frontier", "result", "sha256")) and
                decision["schema"] == "axm-process-decision/1" and is_integer(decision["sequence"]) and
                decision["sequence"] == index + 1 and decision["engine"] == expected, "Decision contract mismatch.")
        df = decision["frontier"]
        require(isinstance(df, list) and len(df) == 6 and all(is_hex(h) for h in df) and len(set(df)) == 6,
                "Incomplete or duplicate decision frontier.")
        prefix_index = next((i for i, item in enumerate(prefixes) if item == df), -1)
        require(prefix_index >= last_prefix and prefix_index >= 0, "Decision uses an impossible or regressing source frontier.")
        last_prefix = prefix_index
        require(all(h in seen for h in df), "Missing decision dependency.")
        rebuilt = calculate([seen[h] for h in df])
        require(canonical(rebuilt) == canonical(decision["result"]), "Saved conclusion differs from independent recomputation.")
        require(decision["sha256"] == digest({key: value for key, value in decision.items() if key != "sha256"}), "Decision digest mismatch.")
        decisions[decision["sha256"]] = decision
    for review in state["reviews"]:
        require(exact(review, ("schema", "decision", "reviewer", "role", "identity_status", "operational_authority", "sha256")) and review["schema"] == "axm-process-review/1", "Invalid review contract.")
        require(isinstance(review["decision"], str), "Invalid review decision reference.")
        decision = decisions.get(review["decision"])
        reviewer = review["reviewer"]
        require(decision is not None and decision["result"]["status"] == "COMPUTED" and
                review["role"] == decision["result"]["review_role"] and
                review["identity_status"] == "unverified-label" and review["operational_authority"] is False and
                isinstance(reviewer, str) and utf16_length(js_trim(reviewer)) >= 2 and utf16_length(reviewer) <= 80,
                "Invalid review scope or invented authority.")
        require(review["sha256"] == digest({key: value for key, value in review.items() if key != "sha256"}), "Review digest mismatch.")
    return copy.deepcopy(state)


def make_source(source: str, raw: str, previous: dict | None, observed: str,
                kind: str = "operator-supplied-unverified") -> dict:
    csv(source, raw)
    require(kind in ("synthetic-fixture", "operator-supplied-unverified"), "Unknown evidence class.")
    timestamp(observed)
    body = {"schema": "axm-process-source/1", "source": source,
            "revision": int(previous["revision"]) + 1 if previous else 1,
            "previous": previous["sha256"] if previous else None,
            "evidence_class": kind, "observed_at": observed, "raw": raw}
    return {**body, "sha256": digest(body)}


def change(state: dict, source: str, raw: str, *, observed: str,
           kind: str = "operator-supplied-unverified") -> dict:
    require(len(state["sources"]) < 200, "Source history limit reached.")
    previous = next((s for s in latest(state) if s["source"] == source), None)
    require(previous is not None, "Source not present.")
    require(timestamp(observed) >= timestamp(previous["observed_at"]), "A successor cannot predate its predecessor.")
    successor = make_source(source, raw, previous, observed, kind)
    result = copy.deepcopy(state)
    if raw != previous["raw"] or kind != previous["evidence_class"]:
        result["sources"].append(successor)
    return result


def evaluate(state: dict) -> dict:
    require(len(state["decisions"]) < 64, "Decision history limit reached.")
    body = {"schema": "axm-process-decision/1", "sequence": len(state["decisions"]) + 1,
            "engine": state["engine"], "frontier": frontier(state), "result": calculate(latest(state))}
    result = copy.deepcopy(state)
    result["decisions"].append({**body, "sha256": digest(body)})
    return result


def seal(state: dict) -> dict:
    require("sha256" not in state, "seal expects restored state, not an already sealed packet.")
    return {**copy.deepcopy(state), "sha256": digest(state)}


def resume(packet: dict, *, source: str | None = None, raw: str | None = None,
           observed: str | None = None) -> tuple[dict, dict]:
    state = restore(packet)
    before_sources, before_decisions = len(state["sources"]), len(state["decisions"])
    if source is not None:
        require(raw is not None and observed is not None, "A correction requires source, CSV and observation time.")
        state = change(state, source, raw, observed=observed)
    else:
        require(raw is None and observed is None, "CSV and observation time require a source correction.")
    if not current(state):
        state = evaluate(state)
    output = seal(state)
    restore(output)  # Independently revalidate every historical and new result.
    transition = {"appended_sources": len(state["sources"]) - before_sources,
                  "appended_decisions": len(state["decisions"]) - before_decisions,
                  "historical_decisions_recomputed": before_decisions,
                  "latest_current": current(state), "review_status": review_status(state)}
    return output, transition


def execution_receipt(action: str, packet: dict, input_bytes: bytes,
                      output: dict | None = None, output_bytes: bytes | None = None,
                      transition: dict | None = None) -> dict:
    state = output or packet
    body = {
        "schema": "schism-independent-receiver-execution/1", "status": "PASS", "action": action,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "executor": {"name": "independent-python-stdlib-receiver", "python": platform.python_version(),
                     "receiver_sha256": byte_digest(Path(__file__).read_bytes()),
                     "javascript_executed": False,
                     "calculation": "Independent one-dimensional integer optimization and complete historical recomputation."},
        "contract": contract_identity(),
        "input": {"file_sha256": byte_digest(input_bytes), "packet_sha256": packet["sha256"]},
        "output": {"file_sha256": byte_digest(output_bytes), "packet_sha256": output["sha256"]} if output is not None and output_bytes is not None else None,
        "sources": len(state["sources"]), "decisions": len(state["decisions"]), "reviews": len(state["reviews"]),
        "decisions_recomputed": len(state["decisions"]),
        "latest_current": current(state), "review_status": review_status(state),
        "transition": transition,
        "admission": {"json": "UTF-8, unique members, finite safe integer-valued numbers",
                      "dates": "Calendar-valid timezone-qualified ISO with seconds; alternate Date.parse forms refused explicitly",
                      "timestamp_authority": "unverified source declaration"},
        "conclusions": [{"sequence": d["sequence"], "status": d["result"]["status"],
                         "chosen": d["result"].get("chosen"), "net_cents": d["result"].get("plan", {}).get("net_cents")}
                        for d in state["decisions"]],
        "operational_authority": False, "physical_truth": "unverified",
        "external_effects": False, "network_requests": 0, "model_calls": 0,
        "scope": "Civilian record calculation, local file output and transport integrity only.",
    }
    return {**body, "sha256": digest(body)}


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    verify = actions.add_parser("verify", help="Independently recompute every retained decision.")
    verify.add_argument("packet", type=Path)
    verify.add_argument("--receipt", type=Path)
    continuation = actions.add_parser("resume", help="Append an optional source correction, then evaluate a pending frontier.")
    continuation.add_argument("packet", type=Path)
    continuation.add_argument("--source", choices=IDS)
    continuation.add_argument("--csv", type=Path)
    continuation.add_argument("--observed")
    continuation.add_argument("--out", type=Path, required=True)
    continuation.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        require(args.packet.stat().st_size <= MAX_PACKET_BYTES, "Handoff exceeds 4 MiB.")
        input_bytes = args.packet.read_bytes()
        packet = loads(input_bytes)
        if args.action == "verify":
            restore(packet)
            receipt = execution_receipt("verify", packet, input_bytes)
            if args.receipt is not None:
                write_new(args.receipt, (canonical(receipt) + "\n").encode("utf-8"))
        else:
            if args.source is None:
                require(args.csv is None and args.observed is None, "--csv and --observed require --source.")
                raw = None
            else:
                require(args.csv is not None and args.observed is not None, "A correction requires --source, --csv and --observed.")
                require(args.csv.stat().st_size <= 131072, "Source CSV exceeds the bounded transport allowance.")
                raw = args.csv.read_bytes().decode("utf-8", "strict")
            out, transition = resume(packet, source=args.source, raw=raw, observed=args.observed)
            out_bytes = (canonical(out) + "\n").encode("utf-8")
            require(len(out_bytes) <= MAX_PACKET_BYTES, "Resumed handoff exceeds 4 MiB.")
            receipt_path = args.receipt or Path(str(args.out) + ".receipt.json")
            require(args.out.resolve() != receipt_path.resolve(), "Packet and execution receipt need different paths.")
            require(not args.out.exists() and not receipt_path.exists(), "Output packet or receipt already exists; original files are retained.")
            receipt = execution_receipt("resume", packet, input_bytes, out, out_bytes, transition)
            write_new(args.out, out_bytes)
            write_new(receipt_path, (canonical(receipt) + "\n").encode("utf-8"))
        print(json.dumps(receipt, ensure_ascii=True, indent=2))
        return 0
    except (ContractError, OSError, UnicodeError, RecursionError, TypeError, KeyError, OverflowError) as exc:
        print(json.dumps({"schema": "schism-independent-receiver-execution/1", "status": "FAIL",
                          "error": str(exc), "operational_authority": False,
                          "external_effects": False, "model_calls": 0}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
