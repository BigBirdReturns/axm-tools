#!/usr/bin/env python3
"""Materialize provider-neutral independent archive custody evidence.

This script closes only M99-CUSTODY-GAP-002. It does not mutate the external
campaign ledger, public route, release authority, score, or canonical task
count. It is idempotent so repeated pull-request qualification cannot duplicate
or broaden the admitted donor.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any


CUSTODY = Path("programs/manzanita-99/custody")
REGISTER_PATH = CUSTODY / "DONOR_REGISTER.json"
RECEIPT_PATH = CUSTODY / "INDEPENDENT_ARCHIVE_RECEIPT.json"
TEST_PATH = CUSTODY / "tests/test_independent_archive.py"
README_PATH = CUSTODY / "README.md"
DONOR_ID = "p10-independent-archive-001"
GAP_ID = "M99-CUSTODY-GAP-002"
VERIFIED_AT = "2026-08-18T13:51:29Z"


RECEIPT: dict[str, Any] = {
    "schema": "axm-tools/manzanita-independent-archive-receipt@1",
    "receipt_id": "M99-CUSTODY-INDEPENDENT-ARCHIVE-001",
    "gap_id": GAP_ID,
    "verified_at": VERIFIED_AT,
    "source_release": {
        "pull_request": 109,
        "qualified_head": "ed387ac8d27576484c71a13a7d0c8c8194f9b2ed",
        "release_id": "M99-INTERNAL-RC-001",
        "public_release_authorized": False,
    },
    "archive_control": {
        "class": "owner_controlled_private_object_store",
        "repository_independent": True,
        "workflow_retention_independent": True,
        "shared": False,
        "public_discovery": False,
        "permission_class": "owner_only",
        "provider_identifiers_retained_privately": True,
    },
    "objects": [
        {
            "id": "M99-ARCHIVE-OBJECT-CANDIDATE-001",
            "role": "p10_portable_candidate",
            "file_name": "Manzanita_Internal_Release_Candidate_ed387ac8.zip",
            "bytes": 696968,
            "sha256": "73a222505b40ffd74c3c2464a0a313b0fc5c4ff7df9f9b6e996cba8be036e90b",
            "created_at": "2026-08-17T23:51:36.050Z",
            "modified_at": "2026-08-17T23:51:36.050Z",
            "metadata_readback": True,
            "byte_readback": True,
            "zip_integrity": "PASS",
            "unsafe_paths": 0,
            "symbolic_links": 0,
        },
        {
            "id": "M99-ARCHIVE-OBJECT-EVIDENCE-001",
            "role": "p7_p10_complete_evidence",
            "file_name": "manzanita-release-control-ed387ac8-evidence.zip",
            "bytes": 10247061,
            "sha256": "d57f3878f9958b446d2ac55dfdd395ae3881cf9be44fffbfddffd7932cd47454",
            "created_at": "2026-08-17T23:51:27.035Z",
            "modified_at": "2026-08-17T23:51:27.035Z",
            "metadata_readback": True,
            "byte_readback": True,
            "zip_integrity": "PASS",
            "unsafe_paths": 0,
            "symbolic_links": 0,
        },
    ],
    "cold_recovery": {
        "result": "PASS",
        "extracted_to_clean_directory": True,
        "command_class": "python_isolated_mode_standard_library_verifier",
        "verifier": "VERIFY_RELEASE.py",
        "repository_imports": False,
        "private_credentials": False,
        "release_id": "M99-INTERNAL-RC-001",
        "source_commit": "ed387ac8d27576484c71a13a7d0c8c8194f9b2ed",
        "file_count": 24,
        "candidate_manifest_sha256": "72ed850dd354da2bd465383c11a6c114058c2e7ed68a2dc6e183456c1017168d",
        "rollback_manifest_sha256": "099413ab7aeeae06551144b5132710c89a076b7af8869c8ab19185dfe5686e25",
        "evidence_manifest_sha256": "3acde61d8bb73f2e2e32006653f039f31c83b42e546c6291b6bb5a2f6d6163db",
        "manifest_sha256": "35a2b2ffc8be0d51191b40bd45cdd04cbf117cb2176829db91fe5f4402742a74",
    },
    "public_release_authorized": False,
    "external_campaign_effect": "none",
    "public_effect": "none",
    "constitutional_count_effect": "none",
    "claim_boundary": (
        "This receipt proves independently retained P10 candidate and P7-P10 "
        "evidence bytes, private owner-only metadata, exact readback, and a clean "
        "isolated verifier replay. It does not prove a public endpoint, deployed "
        "rollback, human or physical campaign, whole-product release, or canonical "
        "task closure."
    ),
}


DONOR: dict[str, Any] = {
    "id": DONOR_ID,
    "class": "independent_archive",
    "custody_state": "archived_external",
    "archive_scope_ids": [],
    "anchors": {
        "receipt": RECEIPT_PATH.as_posix(),
        "release_head": RECEIPT["source_release"]["qualified_head"],
        "candidate_bytes": RECEIPT["objects"][0]["bytes"],
        "candidate_sha256": RECEIPT["objects"][0]["sha256"],
        "evidence_bytes": RECEIPT["objects"][1]["bytes"],
        "evidence_sha256": RECEIPT["objects"][1]["sha256"],
        "cold_recovery_manifest_sha256": RECEIPT["cold_recovery"]["manifest_sha256"],
    },
    "claim_boundary": (
        "Independent private archive and clean byte-readback/cold-recovery custody "
        "only. Public endpoint, deployed rollback, external-campaign, release, score, "
        "and canonical task-count authority remain held."
    ),
}


TEST_SOURCE = textwrap.dedent(
    '''\
    from __future__ import annotations

    import json
    import unittest
    from pathlib import Path


    CUSTODY = Path(__file__).resolve().parents[1]


    class IndependentArchiveReceiptTests(unittest.TestCase):
        def setUp(self) -> None:
            self.receipt = json.loads(
                (CUSTODY / "INDEPENDENT_ARCHIVE_RECEIPT.json").read_text(encoding="utf-8")
            )
            self.register = json.loads(
                (CUSTODY / "DONOR_REGISTER.json").read_text(encoding="utf-8")
            )
            self.observed = json.loads(
                (CUSTODY / "OBSERVED_EXECUTION_LEDGER.json").read_text(encoding="utf-8")
            )

        def test_receipt_proves_exact_readback_and_clean_recovery(self) -> None:
            self.assertEqual(
                self.receipt["schema"],
                "axm-tools/manzanita-independent-archive-receipt@1",
            )
            self.assertEqual(self.receipt["gap_id"], "M99-CUSTODY-GAP-002")
            self.assertEqual(
                self.receipt["archive_control"]["permission_class"], "owner_only"
            )
            self.assertFalse(self.receipt["archive_control"]["shared"])
            self.assertFalse(self.receipt["archive_control"]["public_discovery"])
            expected = {
                "M99-ARCHIVE-OBJECT-CANDIDATE-001": (
                    696968,
                    "73a222505b40ffd74c3c2464a0a313b0fc5c4ff7df9f9b6e996cba8be036e90b",
                ),
                "M99-ARCHIVE-OBJECT-EVIDENCE-001": (
                    10247061,
                    "d57f3878f9958b446d2ac55dfdd395ae3881cf9be44fffbfddffd7932cd47454",
                ),
            }
            self.assertEqual(
                {row["id"] for row in self.receipt["objects"]}, set(expected)
            )
            for row in self.receipt["objects"]:
                self.assertEqual(
                    (row["bytes"], row["sha256"]), expected[row["id"]]
                )
                self.assertTrue(row["metadata_readback"])
                self.assertTrue(row["byte_readback"])
                self.assertEqual(row["zip_integrity"], "PASS")
                self.assertEqual(row["unsafe_paths"], 0)
                self.assertEqual(row["symbolic_links"], 0)
            recovery = self.receipt["cold_recovery"]
            self.assertEqual(recovery["result"], "PASS")
            self.assertTrue(recovery["extracted_to_clean_directory"])
            self.assertFalse(recovery["repository_imports"])
            self.assertFalse(recovery["private_credentials"])
            self.assertEqual(
                recovery["source_commit"],
                "ed387ac8d27576484c71a13a7d0c8c8194f9b2ed",
            )
            self.assertEqual(recovery["file_count"], 24)
            self.assertEqual(
                recovery["manifest_sha256"],
                "35a2b2ffc8be0d51191b40bd45cdd04cbf117cb2176829db91fe5f4402742a74",
            )

        def test_public_receipt_is_provider_neutral_and_grants_no_effect(self) -> None:
            serialized = json.dumps(self.receipt, sort_keys=True).lower()
            for token in (
                "drive.google",
                "gmail.com",
                "@gmail",
                "1_dsq",
                "1eax",
                "17m4_",
            ):
                self.assertNotIn(token, serialized)
            self.assertFalse(self.receipt["public_release_authorized"])
            self.assertEqual(self.receipt["external_campaign_effect"], "none")
            self.assertEqual(self.receipt["public_effect"], "none")
            self.assertEqual(self.receipt["constitutional_count_effect"], "none")

        def test_register_closes_only_the_independent_archive_gap(self) -> None:
            gaps = {row["id"]: row for row in self.register["gaps"]}
            self.assertEqual(gaps["M99-CUSTODY-GAP-002"]["state"], "closed")
            self.assertTrue(
                gaps["M99-CUSTODY-GAP-002"]["closure_evidence"]
            )
            self.assertEqual(
                sum(row["state"] == "closed" for row in self.register["gaps"]),
                1,
            )
            donor = next(
                row for row in self.register["donors"] if row["id"] == "p10-independent-archive-001"
            )
            self.assertEqual(donor["class"], "independent_archive")
            self.assertEqual(donor["custody_state"], "archived_external")
            self.assertEqual(
                donor["anchors"]["receipt"],
                "programs/manzanita-99/custody/INDEPENDENT_ARCHIVE_RECEIPT.json",
            )

        def test_external_campaign_and_release_hold_remain_unchanged(self) -> None:
            external = self.observed["external_campaign_state"]
            self.assertEqual(external["release_state"], "HOLD")
            self.assertEqual(external["passed_campaigns"], [])
            self.assertEqual(len(external["not_performed_campaigns"]), 10)
            self.assertFalse(external["public_release_authorized"])
            self.assertFalse(self.receipt["public_release_authorized"])


    if __name__ == "__main__":
        unittest.main()
    '''
)


README_OLD = (
    "`DONOR_REGISTER.json` records admitted donors and ten explicit required gaps."
)
README_NEW = (
    "`DONOR_REGISTER.json` records admitted donors and ten explicit required gaps. "
    "`INDEPENDENT_ARCHIVE_RECEIPT.json` closes only the independently controlled "
    "archive and clean readback/cold-recovery gap, leaving nine required gaps open."
)
README_CLOSE_OLD = (
    "Final closure requires zero required gaps, archived donors, an independently "
    "controlled archive and cold recovery, exact public endpoint and deployed "
    "rollback receipts, complete visual and playtest custody, and no attempt to "
    "mutate canonical task counts without the exact row source."
)
README_CLOSE_NEW = (
    "Final closure still requires zero required gaps, archived donors, exact public "
    "endpoint and deployed rollback receipts, complete visual and playtest custody, "
    "and no attempt to mutate canonical task counts without the exact row source. "
    "The independent private archive and clean verifier replay are now retained, "
    "but they do not satisfy public endpoint, deployed rollback, or external-campaign "
    "standing."
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    register = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
    donors = register.get("donors")
    gaps = register.get("gaps")
    require(isinstance(donors, list), "Register donors must be a list")
    require(isinstance(gaps, list), "Register gaps must be a list")

    donor_matches = [row for row in donors if row.get("id") == DONOR_ID]
    gap_matches = [row for row in gaps if row.get("id") == GAP_ID]
    require(len(gap_matches) == 1, f"Expected one {GAP_ID}")
    gap = gap_matches[0]

    if donor_matches:
        require(len(donor_matches) == 1, f"Duplicate donor {DONOR_ID}")
        require(donor_matches[0] == DONOR, f"Existing donor {DONOR_ID} drifted")
        require(gap.get("state") == "closed", f"Existing {GAP_ID} is not closed")
    else:
        require(gap.get("state") == "open", f"Expected open {GAP_ID}")
        donors.append(DONOR)
        gap["state"] = "closed"
        gap["closed_at"] = VERIFIED_AT
        gap["closure_evidence"] = [
            RECEIPT_PATH.as_posix(),
            f"sha256:{RECEIPT['objects'][0]['sha256']}",
            f"sha256:{RECEIPT['objects'][1]['sha256']}",
            f"verifier:{RECEIPT['cold_recovery']['manifest_sha256']}",
        ]

    p10_matches = [row for row in donors if row.get("id") == "pr-109-release_control"]
    require(len(p10_matches) == 1, "Expected one PR #109 donor")
    p10_matches[0]["claim_boundary"] = (
        "Portable internal generated candidate and local rollback proof; release HOLD. "
        "Exact independent archive custody is admitted by "
        "M99-CUSTODY-INDEPENDENT-ARCHIVE-001. Public endpoint, deployed rollback, "
        "standalone-export, and external-campaign standing remain separately held."
    )

    RECEIPT_PATH.write_text(canonical_json(RECEIPT), encoding="utf-8")
    REGISTER_PATH.write_text(canonical_json(register), encoding="utf-8")
    TEST_PATH.write_text(TEST_SOURCE, encoding="utf-8")

    readme = README_PATH.read_text(encoding="utf-8")
    if README_NEW not in readme:
        require(README_OLD in readme, "README register anchor drifted")
        readme = readme.replace(README_OLD, README_NEW, 1)
    if README_CLOSE_NEW not in readme:
        require(README_CLOSE_OLD in readme, "README closure anchor drifted")
        readme = readme.replace(README_CLOSE_OLD, README_CLOSE_NEW, 1)
    README_PATH.write_text(readme, encoding="utf-8")

    open_required = [
        row["id"]
        for row in gaps
        if row.get("required_for_close") and row.get("state") != "closed"
    ]
    require(len(open_required) == 9, f"Expected nine open required gaps: {open_required}")
    require(
        sum(row.get("state") == "closed" for row in gaps) == 1,
        "Independent archive materialization closed more than one gap",
    )
    print(
        canonical_json(
            {
                "result": "PASS",
                "closed_gap": GAP_ID,
                "open_required_gaps": open_required,
                "public_release_authorized": False,
                "external_campaign_effect": "none",
                "constitutional_count_effect": "none",
            }
        ),
        end="",
    )


if __name__ == "__main__":
    main()
