#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace_once(
        Path("manzanita-working-model/app.js"),
        """  restoreDraft();
  applyTheme(initialTheme());
  const hashScenario = location.hash.match(/^#run-(wildfire|tools|mobility|continuity)$/)?.[1];
  const initialScenario = hashScenario || byId('pilot-scenario').value || 'wildfire';
  renderScenario(initialScenario, { syncForm: false });
  updateFormStatus();

  window.MW_WORKING_MODEL = Object.freeze({
""",
        """  function scenarioFromHash() {
    return location.hash.match(/^#run-(wildfire|tools|mobility|continuity)$/)?.[1];
  }

  restoreDraft();
  applyTheme(initialTheme());
  const initialScenario = scenarioFromHash() || byId('pilot-scenario').value || 'wildfire';
  renderScenario(initialScenario, { syncForm: false });
  updateFormStatus();

  window.addEventListener('hashchange', () => {
    const nextScenario = scenarioFromHash();
    if (!nextScenario) return;
    renderScenario(nextScenario);
  });

  window.MW_WORKING_MODEL = Object.freeze({
""",
        "app initialization block",
    )

    replace_once(
        Path("manzanita-working-model/tests/public_contract_test.py"),
        """    require("UNRESOLVED" in js, "unresolved value law absent")

    require('@import url("style-base.css")' in override_css, "base style import absent")
""",
        """    require("UNRESOLVED" in js, "unresolved value law absent")
    require("function scenarioFromHash()" in js, "hash route parser absent")
    require("window.addEventListener('hashchange'" in js, "same-document hash route listener absent")

    require('@import url("style-base.css")' in override_css, "base style import absent")
""",
        "static hash-route gate insertion",
    )

    replace_once(
        Path("manzanita-working-model/tests/browser_test.py"),
        """        page.reload(wait_until="networkidle")
        assert page.locator("html").get_attribute("data-theme") == changed_theme

        page.set_viewport_size({"width": 390, "height": 844})
""",
        """        page.reload(wait_until="networkidle")
        assert page.locator("html").get_attribute("data-theme") == changed_theme

        # Same-document fragment changes must update the governed scenario;
        # a cold-load-only deep link leaves ordinary in-tab navigation stale.
        page.evaluate("location.hash = '#run-mobility'")
        page.wait_for_function("document.querySelector('[data-scenario=\\\"mobility\\\"]').getAttribute('aria-selected') === 'true'")
        assert "transportation path" in page.locator("#scenario-title").inner_text().lower()

        page.set_viewport_size({"width": 390, "height": 844})
""",
        "local same-document route gate insertion",
    )

    live_path = Path("manzanita-working-model/tests/live_browser_test.py")
    replace_once(
        live_path,
        """        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(target("#run-mobility"), wait_until="networkidle")
        assert page.locator('[data-scenario="mobility"]').get_attribute("aria-selected") == "true"
        assert_no_overflow(page)
""",
        """        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(target("#run-mobility"), wait_until="networkidle")
        page.wait_for_function("document.querySelector('[data-scenario=\\\"mobility\\\"]').getAttribute('aria-selected') === 'true'")
        assert page.locator('[data-scenario="mobility"]').get_attribute("aria-selected") == "true"
        assert_no_overflow(page)
""",
        "live mobility route wait insertion",
    )
    replace_once(
        live_path,
        """        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(target("#run-continuity"), wait_until="networkidle")
        page.evaluate("document.documentElement.style.fontSize='200%'")
""",
        """        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(target("#run-continuity"), wait_until="networkidle")
        page.wait_for_function("document.querySelector('[data-scenario=\\\"continuity\\\"]').getAttribute('aria-selected') === 'true'")
        page.evaluate("document.documentElement.style.fontSize='200%'")
""",
        "live continuity route wait insertion",
    )

    finding = {
        "schema": "manzanita-works/working-model-live-qualification-finding@1",
        "finding_id": "MW-LIVE-ROUTE-001",
        "state": "repaired_pending_requalification",
        "release": "mw-working-model-v1.0.0",
        "observed_source_sha": "eeda33f5ae501bab188e4a98c144ef0fd1c7720f",
        "observed_run_id": 34184162210,
        "evidence": {
            "exact_live_release_bytes": "PASS_EXACT_LIVE_RELEASE_BYTES",
            "root_directory_link": True,
            "live_browser_campaign": "FAIL_SAME_DOCUMENT_HASH_ROUTE_STALE",
        },
        "mechanism": (
            "After the page had already loaded, navigating from one #run-* fragment to another "
            "performed a same-document navigation. Initialization parsed the fragment only once "
            "and no hashchange listener reconciled the selected scenario, so the visible case could "
            "remain stale even though cold deep links worked."
        ),
        "repair": (
            "Centralize fragment parsing, reconcile every valid hashchange through renderScenario, "
            "and require both local and live browser campaigns to exercise same-document route changes."
        ),
        "acceptance": [
            "same-document mobility fragment selects mobility",
            "same-document continuity fragment selects continuity",
            "all four case projections retain seven stages",
            "desktop, 390px mobile, and 320px at 200 percent text remain free of document overflow",
            "public route bytes and root discovery remain exact",
        ],
        "authority": {
            "institutional_acceptance": False,
            "participant_consent": False,
            "field_authority": False,
            "spend_authority": False,
            "assignment_authority": False,
            "representation_authority": False,
            "program_external_effect": "none",
        },
    }
    Path("manzanita-working-model/LIVE_QUALIFICATION_FINDING.json").write_text(
        json.dumps(finding, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
