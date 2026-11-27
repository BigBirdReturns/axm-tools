#!/usr/bin/env python3
"""Finite differential/adversarial qualification for the independent receiver.

Run from any directory with ``python -B /path/runtime/test_receiver.py``.
Python's standard library and Node are the only test dependencies. Node serves
as the original contract oracle and never runs inside receiver.py. Synthetic
inputs exercise integer optimization, receipts, historical replay, corrections,
admission boundaries and refusal. All generated files live in temporary dirs.
These finite cases establish the reported bounded behavior, not an exhaustive
proof, authenticated identity, physical performance or production authority.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("independent_receiver", HERE / "receiver.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
ENGINE = ROOT / "vendor" / "engine.js"
CORE = ROOT / "vendor" / "commons-core.js"
EXPECTED_ENGINE = "f7cb1a8810a4a0c9af406c241fed7bfada2704c6f68ab9053f13af86cafc0e5d"
OBSERVED = "2026-11-16T16:00:00-08:00"
NEXT = "2026-11-16T16:20:00-08:00"

# This transport bridge drives the unmodified, pinned donor implementation.
# Native source receipts are built from independent test inputs, not copied
# decisions; the donor supplies its own canonicalization, calculation and hashes.
BRIDGE = r"""
const fs = require('node:fs');
globalThis.crypto = require('node:crypto').webcrypto;
const E = require(process.argv[1]);
const C = require(process.argv[2]);
const p = JSON.parse(fs.readFileSync(0, 'utf8'));
(async () => {
 let output;
 if (p.mode === 'calculate') output = p.cases.map(records => E.calculate(records));
 else if (p.mode === 'canonical') output = await Promise.all(p.values.map(async x => ({text:C.canonical(x),sha256:await E.digest(x)})));
 else if (p.mode === 'dates') output = p.values.map(x => Date.parse(x));
 else if (p.mode === 'restore') output = await Promise.all(p.packets.map(async packet => {
  try {const s=await E.restore(packet,p.engine);return {accepted:true,current:E.current(s),review_status:E.reviewStatus(s),packet:await E.seal(s)};}
  catch (e) {return {accepted:false,error:e.message};}
 }));
 else if (p.mode === 'build') {
  const sources=[];
  for (const id of E.IDS) {
   const body={schema:'axm-process-source/1',source:id,revision:1,previous:null,evidence_class:'synthetic-fixture',observed_at:p.observed,raw:p.raws[id]};
   sources.push({...body,sha256:await E.digest(body)});
  }
  let s={schema:E.VERSION,engine:p.engine,recipe:E.RECIPE,sources,decisions:[],reviews:[]};
  if (p.evaluate !== false) s=await E.evaluate(s);
  if (p.reviewer) s=await E.review(s,p.reviewer,'shift-planner');
  output=await E.seal(s);
 }
 else if (p.mode === 'continue') {
  let s=await E.restore(p.packet,p.engine);
  for (const c of (p.changes || [])) s=await E.change(s,c.source,c.raw,{kind:c.kind || 'operator-supplied-unverified',observed:c.observed});
  if (p.evaluate !== false) s=await E.evaluate(s);
  if (p.reviewer) s=await E.review(s,p.reviewer,s.decisions.at(-1).result.review_role);
  output=await E.seal(s);
 }
 else throw Error('Unknown test mode');
 process.stdout.write(JSON.stringify(output));
})().catch(e => {process.stderr.write(e.stack+'\n');process.exit(1);});
"""


def node(mode: str, **arguments):
    completed = subprocess.run(
        ["node", "-e", BRIDGE, str(ENGINE), str(CORE)],
        input=json.dumps({"mode": mode, "engine": EXPECTED_ENGINE, **arguments}, ensure_ascii=True),
        text=True, capture_output=True, timeout=40, check=False)
    if completed.returncode:
        raise AssertionError("Native donor oracle failed: " + completed.stderr)
    return json.loads(completed.stdout)


def money(cents: int) -> str:
    return str(cents // 100) + "." + str(cents % 100).zfill(2)


def raws(*, demand=(80, 60), margin=(5500, 4000), mix=(2, 1), pack=(1, 2),
         capacity=(160, 150), released=(1, 1), serviceable=2, allocated=1,
         recovery=80, cost=15000, expedite=20000, lead=7, window=4,
         allowed=1, revision=3) -> dict[str, str]:
    """Independent synthetic fixture generator; all money enters as integer cents."""
    data = {
        "orders": [["A", demand[0], money(margin[0])], ["B", demand[1], money(margin[1])]],
        "routing": [["A", mix[0], pack[0]], ["B", mix[1], pack[1]]],
        "capacity": [["mix", capacity[0]], ["pack", capacity[1]]],
        "maintenance": [["WO-101", "SEAL-17", serviceable, allocated, recovery,
                         money(cost), money(expedite), lead, window]],
        "quality": [["A", released[0]], ["B", released[1]]],
        "procedure": [["Planning-review", revision, allowed, "shift-planner"]],
    }
    return {source: ",".join(R.HEADERS[source]) + "\n" +
            "\n".join(",".join(map(str, row)) for row in data[source]) + "\n"
            for source in R.IDS}


def records(source_raws: dict) -> list[dict]:
    return [{"source": source, "raw": source_raws[source]} for source in R.IDS]


def rehash(value: dict) -> dict:
    value["sha256"] = R.digest({k: v for k, v in value.items() if k != "sha256"})
    return value


def add_review(state: dict, reviewer="Native recipient", role="shift-planner") -> dict:
    state = copy.deepcopy(state)
    body = {"schema": "axm-process-review/1", "decision": state["decisions"][-1]["sha256"],
            "reviewer": reviewer, "role": role, "identity_status": "unverified-label",
            "operational_authority": False}
    state["reviews"].append(rehash(body))
    return state


class ReceiverQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("node") is None:
            raise RuntimeError("Qualification requires Node to execute the pinned donor oracle.")
        cls.base_raws = raws()
        cls.baseline = node("build", raws=cls.base_raws, observed=OBSERVED,
                            reviewer="Original receiving reviewer")
        cls.base_state = R.restore(cls.baseline)
        changed = raws(margin=(5500, 12000))["orders"]
        cls.pending = node("continue", packet=cls.baseline,
                           changes=[{"source": "orders", "raw": changed, "observed": NEXT}],
                           evaluate=False)
        cls.completed = node("continue", packet=cls.pending)

    def assert_rejected(self, packet, pattern=None):
        with self.assertRaises(R.ContractError) as caught:
            R.restore(packet)
        if pattern:
            self.assertIn(pattern, str(caught.exception))

    def assert_both_reject(self, packets):
        for index, packet in enumerate(packets):
            with self.subTest(adversary=index):
                self.assert_rejected(packet)
        outcomes = node("restore", packets=packets)
        self.assertTrue(all(not result["accepted"] for result in outcomes), outcomes)

    def test_01_exact_source_identity_and_release_fixture_register(self):
        self.assertEqual(R.contract_identity()["engine_sha256"], EXPECTED_ENGINE)
        register = json.loads((ROOT / "data" / "case-register.json").read_text())
        for case in register["required"]:
            packet = R.loads((ROOT / "data" / "cases" / case["file"]).read_bytes())
            with self.subTest(case=case["file"]):
                if case["accept"]:
                    R.restore(packet)
                else:
                    self.assert_rejected(packet)
        pending = R.loads((ROOT / "data" / "cases" / register["resume"]["input"]).read_bytes())
        expected = R.loads((ROOT / "data" / "cases" / register["resume"]["expected"]).read_bytes())
        result, transition = R.resume(pending)
        self.assertEqual(result, expected)
        self.assertEqual(result["sha256"], register["resume"]["expected_sha256"])
        self.assertEqual(transition["appended_decisions"], 1)
        original = R.loads((ROOT / "data" / "original-handoff.json").read_bytes())
        self.assertEqual(len(R.restore(original)["decisions"]), 2)

    def test_02_canonical_unicode_ordering_escape_and_integer_parity(self):
        values = [None, True, False, 0, -0.0, -5, R.MAX_SAFE_INTEGER,
                  {"\ue000": 1, "\U00010000": 2, "\uffff": 3, "a": 4},
                  "e\u0301 é \u2028 \u2029 \u0000 \b \f \n \r \t \\",
                  ["\ud800", "\udfff", "\U0001f419", {"2": "two", "10": "ten"}],
                  {"reviewer": "Receiving analyst \U0001f419 \ufeff", "value": 1.0}]
        native = node("canonical", values=values)
        for value, expected in zip(values, native):
            with self.subTest(value=repr(value)):
                self.assertEqual(R.canonical(value), expected["text"])
                self.assertEqual(R.digest(value), expected["sha256"])
        for label in ["\U0001f419", "a\ud800", "é reviewer", "x" * 80]:
            packet = node("build", raws=self.base_raws, observed=OBSERVED, reviewer=label)
            self.assertEqual(R.seal(R.restore(packet)), packet)

    def test_03_240_generated_calculations_match_the_native_donor(self):
        generator = random.Random(9074)
        cases = []
        for _ in range(240):
            available = generator.randrange(0, 5)
            cases.append(records(raws(
                demand=(generator.randrange(0, 23), generator.randrange(0, 23)),
                margin=(generator.choice([0, 1, 99, 100, 101, 5577, 10000000]),
                        generator.choice([0, 1, 99, 100, 101, 5577, 10000000])),
                mix=(generator.randrange(1, 8), generator.randrange(1, 8)),
                pack=(generator.randrange(1, 8), generator.randrange(1, 8)),
                capacity=(generator.randrange(0, 100), generator.randrange(0, 100)),
                released=(generator.randrange(2), generator.randrange(2)),
                serviceable=available, allocated=generator.randrange(available + 1),
                recovery=generator.randrange(0, 101), cost=generator.randrange(0, 30001),
                expedite=generator.randrange(0, 30001), lead=generator.randrange(0, 12),
                window=generator.randrange(0, 12), allowed=generator.randrange(2))))
        expected = node("calculate", cases=cases)
        for index, (case, result) in enumerate(zip(cases, expected)):
            with self.subTest(seed_case=index):
                self.assertEqual(R.calculate(case), result)
                self.assertEqual(R.canonical(R.calculate(case)), R.canonical(result))

    def test_04_extreme_integer_money_and_tie_outcomes(self):
        variants = [
            raws(demand=(500, 500), margin=(10000000, 10000000), capacity=(1000000, 1000000),
                 mix=(1000, 1000), pack=(1000, 1000), recovery=1000000,
                 cost=100000000, expedite=100000000, serviceable=10000, allocated=10000,
                 lead=8760, window=168, revision=9999),
            raws(demand=(0, 0), margin=(0, 0), capacity=(0, 0), cost=0, expedite=0),
            raws(demand=(5, 5), margin=(0, 0), mix=(1, 1), pack=(1, 1),
                 capacity=(4, 4), recovery=0, cost=0, expedite=0, lead=0),
            raws(demand=(5, 5), margin=(100, 100), mix=(1, 1), pack=(1, 1),
                 capacity=(4, 4), recovery=0, cost=0, expedite=0, lead=0),
            raws(demand=(500, 500), margin=(1, 99), capacity=(1, 1), recovery=0),
            raws(capacity=(0, 150), recovery=80, cost=0, expedite=0, lead=0),
            raws(released=(0, 0), cost=100000000, expedite=100000000),
        ]
        native = node("calculate", cases=[records(value) for value in variants])
        for value, result in zip(variants, native):
            self.assertEqual(R.calculate(records(value)), result)
        self.assertEqual(native[2]["plan"]["a"], 0)
        self.assertEqual(native[2]["plan"]["b"], 4)
        self.assertEqual(native[2]["chosen"], "existing-capacity")
        self.assertEqual(native[5]["chosen"], "expedited-recovery")

    def test_05_optimizer_matches_exhaustive_feasible_set(self):
        generator = random.Random(218)
        for iteration in range(120):
            products = [{"demand": generator.randrange(8), "released": generator.randrange(2),
                         "margin": generator.randrange(5), "mix": generator.randrange(1, 5),
                         "pack": generator.randrange(1, 5)} for _ in range(2)]
            capacity = {"mix": generator.randrange(20), "pack": generator.randrange(20)}
            cost = generator.randrange(10)
            feasible = []
            for a in range(products[0]["demand"] * products[0]["released"] + 1):
                for b in range(products[1]["demand"] * products[1]["released"] + 1):
                    used = {stage: a * products[0][stage] + b * products[1][stage] for stage in capacity}
                    if all(used[stage] <= capacity[stage] for stage in capacity):
                        gross = a * products[0]["margin"] + b * products[1]["margin"]
                        feasible.append((gross - cost, a + b, -a, -b))
            optimum = max(feasible)
            actual = R.solve(products, capacity, cost)
            with self.subTest(iteration=iteration):
                self.assertEqual((actual["net_cents"], actual["units"], -actual["a"], -actual["b"]), optimum)

    def test_06_inconclusive_numeric_ranges_and_issue_order_are_native(self):
        cases = []
        mutations = [
            ("orders", "A,80,55.00", "A,,55.00"),
            ("orders", "A,80,55.00", "A,080,55.00"),
            ("orders", "A,80,55.00", "A,501,100000.01"),
            ("orders", "A,80,55.00", "A,80,1.001"),
            ("orders", "A,80,55.00", "A,80,+1"),
            ("orders", "A,80,55.00", "A,80,１.00"),
            ("orders", "A,80,55.00", "A," + "9" * 4500 + ",55.00"),
            ("routing", "A,2,1", "A,0,1001"),
            ("capacity", "pack,150", "pack,"),
            ("capacity", "mix,160", "mix,1000001"),
            ("maintenance", "SEAL-17,2,1", "SEAL-17,2,3"),
            ("maintenance", "150.00,200.00,7,4", "1000000.01,NaN,8761,169"),
            ("maintenance", "WO-101", "WO 101"),
            ("quality", "A,1", "A,2"),
            ("procedure", "Planning-review,3,1,shift-planner", "bad label,0,2,role space"),
        ]
        for source, old, new in mutations:
            case = dict(self.base_raws)
            case[source] = case[source].replace(old, new)
            cases.append(records(case))
        combined = dict(self.base_raws)
        combined["orders"] = combined["orders"].replace("A,80,55.00", "A,,1.001")
        combined["quality"] = combined["quality"].replace("A,1", "A,2")
        cases.append(records(combined))
        for case, expected in zip(cases, node("calculate", cases=cases)):
            self.assertEqual(R.calculate(case), expected)
            self.assertEqual(expected["status"], "INCONCLUSIVE")

    def test_07_raw_csv_line_endings_unicode_whitespace_and_structural_errors(self):
        good = []
        for replacement in ["\r\n", "\n"]:
            case = {key: value.replace("\n", replacement) for key, value in self.base_raws.items()}
            case["orders"] = case["orders"].replace("A,80,55.00", "\ufeffA ,\u00a080\ufeff,\u200355.00\u2003")
            good.append(case)
        # The pinned JS header comparison joins with a pipe. Preserve that exact
        # established behavior without guessing a different CSV dialect.
        alias = dict(self.base_raws)
        alias["orders"] = alias["orders"].replace("sku,demand_units,", "sku|demand_units,")
        good.append(alias)
        for case, expected in zip(good, node("calculate", cases=[records(c) for c in good])):
            self.assertEqual(R.calculate(records(case)), expected)
            self.assertEqual(expected["status"], "COMPUTED")
        broken = []
        for replacement in ["\x00", "\x0b", ",extra", "\nA,10,10", "\r"]:
            case = dict(self.base_raws)
            case["orders"] = case["orders"].replace("A,80,55.00", "A,80,55.00" + replacement)
            broken.append(records(case))
        for case, expected in zip(broken, node("calculate", cases=broken)):
            self.assertEqual(R.calculate(case), expected)
        oversize = self.base_raws["orders"].replace("55.00", "\U0001f419" * 16400)
        with self.assertRaisesRegex(R.ContractError, "oversized"):
            R.csv("orders", oversize)

    def test_08_timestamp_millisecond_and_timezone_parity_with_explicit_refusal(self):
        dates = [OBSERVED, "2026-11-17T00:00:00Z", "2026-11-17T00:00:00.0009Z",
                 "2024-02-29T23:59:59.999999+05:45", "0001-01-01T00:00:00Z",
                 "9999-12-31T23:59:59.999-23:59", "1969-12-31T23:59:59.999Z"]
        self.assertEqual([R.timestamp(value) for value in dates], node("dates", values=dates))
        unsupported = ["2026-11-16", "2026-02-30T00:00:00Z", "2026-11-16T24:00:00Z",
                       "2026-11-16T16:00:00", "2026-11-16t16:00:00z", 1794873600000]
        for value in unsupported:
            with self.subTest(value=value), self.assertRaises(R.ContractError):
                R.timestamp(value)
        self.assertIsInstance(node("dates", values=[unsupported[0]])[0], int)
        packet = copy.deepcopy(self.baseline)
        packet["sources"][0]["observed_at"] = "2026-11-16"
        rehash(packet["sources"][0])
        packet["decisions"], packet["reviews"] = [], []
        rehash(packet)
        self.assert_rejected(packet, "alternate Date.parse")
        self.assertTrue(node("restore", packets=[packet])[0]["accepted"])

    def test_09_new_correction_is_byte_exact_js_python_js_continuation(self):
        python_packet, transition = R.resume(self.pending)
        self.assertEqual(python_packet, self.completed)
        self.assertEqual(transition["review_status"], "STALE")
        self.assertEqual(transition["appended_decisions"], 1)
        native = node("restore", packets=[python_packet])[0]
        self.assertTrue(native["accepted"])
        self.assertEqual(native["packet"], python_packet)
        correction = raws(released=(0, 1))["quality"]
        python_again, _ = R.resume(python_packet, source="quality", raw=correction,
                                   observed="2026-11-16T16:30:00-08:00")
        native_again = node("continue", packet=python_packet,
                            changes=[{"source": "quality", "raw": correction,
                                      "observed": "2026-11-16T16:30:00-08:00"}])
        self.assertEqual(python_again, native_again)
        self.assertTrue(node("restore", packets=[python_again])[0]["accepted"])
        self.assertEqual(python_again["decisions"][-1]["result"]["plan"]["a"], 0)
        self.assertEqual(python_again["sources"][-1]["evidence_class"], "operator-supplied-unverified")
        self.assertEqual(python_again["engine"], EXPECTED_ENGINE)
        self.assertFalse(python_again["decisions"][-1]["result"]["operational_authority"])

    def test_10_idempotence_and_inconclusive_to_corrected_continuation(self):
        same, transition = R.resume(self.baseline)
        self.assertEqual(same, self.baseline)
        self.assertEqual(transition["appended_decisions"], 0)
        blank = self.base_raws["capacity"].replace("pack,150", "pack,")
        incomplete, _ = R.resume(self.baseline, source="capacity", raw=blank, observed=NEXT)
        self.assertEqual(incomplete["decisions"][-1]["result"]["status"], "INCONCLUSIVE")
        self.assertEqual(R.review_status(incomplete), "STALE")
        recovered, transition = R.resume(incomplete, source="capacity",
                                        raw=self.base_raws["capacity"], observed=NEXT)
        self.assertEqual(recovered["decisions"][-1]["result"]["status"], "COMPUTED")
        self.assertEqual(transition["historical_decisions_recomputed"], 2)
        self.assertEqual(len(recovered["sources"]), 8)
        expected = node("continue", packet=incomplete,
                        changes=[{"source": "capacity", "raw": self.base_raws["capacity"], "observed": NEXT}])
        self.assertEqual(recovered, expected)
        # A new declared time alone does not invent a new content revision.
        no_change, transition = R.resume(recovered, source="capacity", raw=self.base_raws["capacity"],
                                         observed="2026-11-16T17:00:00-08:00")
        self.assertEqual(no_change, recovered)
        self.assertEqual(transition["appended_sources"], 0)

    def test_11_rehashed_favorable_current_and_historical_results_are_refused(self):
        adversaries = []
        for decision_index in [0, 1]:
            packet = copy.deepcopy(self.completed)
            decision = packet["decisions"][decision_index]
            old_hash = decision["sha256"]
            decision["result"]["plan"]["net_cents"] += 100000000
            decision["result"]["incremental_net_cents"] += 100000000
            rehash(decision)
            for review in packet["reviews"]:
                if review["decision"] == old_hash:
                    review["decision"] = decision["sha256"]
                    rehash(review)
            adversaries.append(rehash(packet))
        packet = copy.deepcopy(self.baseline)
        packet["decisions"][0]["result"]["operational_authority"] = True
        rehash(packet["decisions"][0])
        adversaries.append(rehash(packet))
        self.assert_both_reject(adversaries)
        for packet in adversaries:
            self.assert_rejected(packet, "independent recomputation")

    def test_12_changed_raw_source_and_orphan_fork_chronology_are_refused(self):
        adversaries = []
        changed = copy.deepcopy(self.pending)
        changed["sources"][-1]["raw"] += " "
        adversaries.append(rehash(changed))
        for key, value in [("previous", "0" * 64), ("revision", 1),
                           ("observed_at", "2026-11-16T15:59:59-08:00")]:
            packet = copy.deepcopy(self.pending)
            packet["sources"][-1][key] = value
            rehash(packet["sources"][-1])
            adversaries.append(rehash(packet))
        duplicate = copy.deepcopy(self.pending)
        duplicate["sources"].append(copy.deepcopy(duplicate["sources"][-1]))
        adversaries.append(rehash(duplicate))
        missing = copy.deepcopy(self.pending)
        missing["sources"] = [source for source in missing["sources"] if source["source"] != "quality"]
        adversaries.append(rehash(missing))
        self.assert_both_reject(adversaries)

    def test_13_frontier_order_completeness_chronology_and_sequence_are_enforced(self):
        adversaries = []
        for mutation in ["duplicate", "reverse", "regress", "sequence"]:
            packet = copy.deepcopy(self.completed)
            if mutation == "duplicate":
                packet["decisions"][-1]["frontier"][0] = packet["decisions"][-1]["frontier"][1]
            elif mutation == "reverse":
                packet["decisions"][-1]["frontier"].reverse()
            elif mutation == "regress":
                older = copy.deepcopy(packet["decisions"][0])
                older["sequence"] = 3
                packet["decisions"].append(rehash(older))
            else:
                packet["decisions"][-1]["sequence"] = 99
            rehash(packet["decisions"][-1])
            adversaries.append(rehash(packet))
        # All referenced receipts exist, yet this mixed frontier never existed
        # at a source-history prefix; a digest alone cannot authorize it.
        state = R.restore(self.completed)
        state = R.change(state, "quality", raws(released=(0, 1))["quality"], observed=NEXT)
        state = R.evaluate(state)
        packet = R.seal(state)
        decision = packet["decisions"][-1]
        decision["frontier"][0] = packet["sources"][0]["sha256"]
        lookup = {source["sha256"]: source for source in packet["sources"]}
        decision["result"] = R.calculate([lookup[sha] for sha in decision["frontier"]])
        rehash(decision)
        adversaries.append(rehash(packet))
        self.assert_both_reject(adversaries)

    def test_14_rehashed_authority_identity_role_and_review_limits_are_refused(self):
        adversaries = []
        for key, value in [("operational_authority", True), ("identity_status", "authenticated"),
                           ("role", "plant-controller"), ("reviewer", "x"),
                           ("reviewer", "\U0001f419" * 41), ("decision", "f" * 64)]:
            packet = copy.deepcopy(self.baseline)
            packet["reviews"][0][key] = value
            rehash(packet["reviews"][0])
            adversaries.append(rehash(packet))
        blank = self.base_raws["capacity"].replace("pack,150", "pack,")
        state = R.change(self.base_state, "capacity", blank, observed=NEXT)
        state = add_review(R.evaluate(state))
        adversaries.append(R.seal(state))
        self.assert_both_reject(adversaries)
        retained = R.restore(self.completed)
        self.assertEqual(R.review_status(retained), "STALE")
        self.assertEqual(retained["reviews"], self.base_state["reviews"])

    def test_15_schema_recipe_engine_and_bounded_history_are_enforced(self):
        adversaries = []
        for key, value in [("engine", "1" * 64), ("recipe", R.RECIPE + "-changed"),
                           ("invented_authority", True)]:
            packet = copy.deepcopy(self.baseline)
            packet[key] = value
            adversaries.append(rehash(packet))
        for location in ["sources", "decisions", "reviews"]:
            packet = copy.deepcopy(self.baseline)
            packet[location][0]["invented"] = True
            rehash(packet[location][0])
            adversaries.append(rehash(packet))
        for location, count in [("sources", 201), ("decisions", 65), ("reviews", 65)]:
            packet = copy.deepcopy(self.baseline)
            packet[location] = [copy.deepcopy(packet[location][0]) for _ in range(count)]
            adversaries.append(rehash(packet))
        self.assert_both_reject(adversaries)
        full = copy.deepcopy(self.base_state)
        full["decisions"] *= 64
        with self.assertRaisesRegex(R.ContractError, "history limit"):
            R.evaluate(full)
        full = copy.deepcopy(self.base_state)
        full["sources"] = [full["sources"][0]] * 200
        with self.assertRaisesRegex(R.ContractError, "history limit"):
            R.change(full, "orders", self.base_raws["orders"], observed=NEXT)

    def test_16_transport_and_changed_donor_admission_fail_closed(self):
        for raw in [b'{"a":1,"a":2}', b'{"n":NaN}', b'{"n":Infinity}',
                    b'{"n":1.5}', b'{"n":9007199254740992}', b'"\xff"',
                    b'{"n":' + b'9' * 4500 + b'}',
                    b'[' * 2000 + b']' * 2000, b' ' * (R.MAX_PACKET_BYTES + 1)]:
            with self.subTest(prefix=raw[:50]), self.assertRaises(R.ContractError):
                R.loads(raw)
        with tempfile.TemporaryDirectory(prefix="schism-contract-admission-") as temp:
            location = Path(temp)
            (location / "engine.js").write_bytes(ENGINE.read_bytes() + b"\n")
            (location / "commons-core.js").write_bytes(CORE.read_bytes())
            with self.assertRaisesRegex(R.ContractError, "explicit contract requalification"):
                R.contract_identity(location)

    def test_17_cli_verification_receipts_bind_actual_files_and_distinct_executor(self):
        with tempfile.TemporaryDirectory(prefix="schism-native-receiver-") as temp:
            directory = Path(temp)
            source = directory / "pending.json"
            source.write_text(json.dumps(self.pending, ensure_ascii=True, indent=2) + "\n")
            output, receipt_path = directory / "resumed.json", directory / "execution.json"
            command = [sys.executable, "-B", str(HERE / "receiver.py"), "resume", str(source),
                       "--out", str(output), "--receipt", str(receipt_path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt, json.loads(result.stdout))
            self.assertEqual(receipt["schema"], "schism-independent-receiver-execution/1")
            self.assertEqual(receipt["input"]["file_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(receipt["output"]["file_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(receipt["executor"]["receiver_sha256"], hashlib.sha256((HERE / "receiver.py").read_bytes()).hexdigest())
            self.assertEqual(receipt["contract"]["engine_sha256"], EXPECTED_ENGINE)
            self.assertNotEqual(receipt["executor"]["receiver_sha256"], receipt["contract"]["engine_sha256"])
            self.assertEqual(receipt["decisions_recomputed"], 2)
            self.assertEqual(receipt["transition"]["appended_decisions"], 1)
            for key in ["operational_authority", "external_effects"]:
                self.assertIs(receipt[key], False)
            self.assertIs(receipt["executor"]["javascript_executed"], False)
            self.assertEqual(receipt["network_requests"], 0)
            self.assertEqual(receipt["model_calls"], 0)
            self.assertEqual(rehash(copy.deepcopy(receipt)), receipt)
            self.assertEqual(json.loads(output.read_text()), self.completed)
            self.assertTrue(node("restore", packets=[json.loads(output.read_text())])[0]["accepted"])
            # No overwrite path is available, including collision with input.
            before = output.read_bytes()
            repeat = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(repeat.returncode, 1)
            self.assertEqual(output.read_bytes(), before)
            verification = directory / "verify.json"
            verified = subprocess.run([sys.executable, "-B", str(HERE / "receiver.py"), "verify", str(output),
                                       "--receipt", str(verification)], capture_output=True, text=True, timeout=20)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verification.read_text())["decisions_recomputed"], 2)

    def test_18_cli_correction_inconclusive_and_rejection_emit_no_completed_packet(self):
        with tempfile.TemporaryDirectory(prefix="schism-native-correction-") as temp:
            directory = Path(temp)
            source, correction = directory / "baseline.json", directory / "capacity.csv"
            source.write_text(json.dumps(self.baseline))
            correction.write_bytes(self.base_raws["capacity"].replace("pack,150", "pack,").encode())
            output = directory / "incomplete.json"
            command = [sys.executable, "-B", str(HERE / "receiver.py"), "resume", str(source),
                       "--source", "capacity", "--csv", str(correction), "--observed", NEXT, "--out", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(output.read_text())
            self.assertEqual(packet["decisions"][-1]["result"]["status"], "INCONCLUSIVE")
            self.assertEqual(json.loads(result.stdout)["status"], "PASS")
            self.assertTrue(Path(str(output) + ".receipt.json").exists())
            # PASS denotes verified handling of the INCONCLUSIVE result.
            forged = copy.deepcopy(self.baseline)
            forged["reviews"][0]["operational_authority"] = True
            rehash(forged["reviews"][0])
            source.write_text(json.dumps(rehash(forged)))
            refused_output = directory / "must-not-exist.json"
            refused = subprocess.run([sys.executable, "-B", str(HERE / "receiver.py"), "resume", str(source),
                                      "--out", str(refused_output)], capture_output=True, text=True, timeout=20)
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(json.loads(refused.stderr)["status"], "FAIL")
            self.assertFalse(refused_output.exists())
            self.assertFalse(Path(str(refused_output) + ".receipt.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
