#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from playwright.sync_api import sync_playwright


def add(checks, name, ok, detail=""):
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    html_text = (root / "workbench.html").read_text(encoding="utf-8")
    fixture = root / "fixtures/synthetic-target.json"
    checks, errors, external_network = [], [], []

    with sync_playwright() as p:
        launch = {"headless": True}
        if Path("/usr/bin/chromium").exists():
            launch["executable_path"] = "/usr/bin/chromium"
        browser = p.chromium.launch(**launch)

        def exercise(width, height, prefix):
            page = browser.new_page(viewport={"width": width, "height": height}, accept_downloads=True)
            page.on("console", lambda msg: errors.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
            page.on("request", lambda req: external_network.append(req.url) if req.url.startswith(("http://", "https://")) else None)
            page.set_content(html_text, wait_until="load")
            add(checks, f"{prefix} title renders", page.title() == "AXM Deep-Tech Governance Workbench", page.title())
            add(checks, f"{prefix} four tabs render", page.locator(".tab").count() == 4, str(page.locator('.tab').count()))
            page.locator("#fileInput").set_input_files(str(fixture))
            page.wait_for_function("document.getElementById('targetLabel').textContent.includes('Northstar')")
            add(checks, f"{prefix} target loads", "Northstar Maritime Robotics" in page.locator("#targetLabel").inner_text())
            add(checks, f"{prefix} claim metric exact", page.locator("#claimCount").inner_text() == "2", page.locator("#claimCount").inner_text())
            add(checks, f"{prefix} evidence metric exact", page.locator("#evidenceCount").inner_text() == "2", page.locator("#evidenceCount").inner_text())
            add(checks, f"{prefix} public boundary renders", "do not upgrade to" in page.locator("#public").inner_text().lower())
            page.locator('[data-tab="diligence"]').click()
            add(checks, f"{prefix} diligence renders exceptions", "Open high / critical exceptions" in page.locator("#diligence").inner_text())
            page.locator('[data-tab="admission"]').click()
            add(checks, f"{prefix} admission renders company-controlled gaps", "Company-controlled records still required" in page.locator("#admission").inner_text())
            page.locator('[data-tab="readiness"]').click()
            readiness_text = page.locator("#readiness").inner_text()
            add(checks, f"{prefix} readiness holds external effects", "external effects" in readiness_text.lower() and "held" in readiness_text.lower())
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            add(checks, f"{prefix} no horizontal overflow", overflow is False, str(overflow))
            if prefix == "desktop":
                with page.expect_download() as di:
                    page.locator("#exportBtn").click()
                dl = di.value
                add(checks, "desktop export names current projection", dl.suggested_filename.endswith("-readiness.json"), dl.suggested_filename)
                views = page.evaluate("window.__AXM_WORKBENCH__.getViews()")
                add(checks, "browser derives four governed views", sorted(views.keys()) == ["admission", "diligence", "public", "readiness"], str(sorted(views.keys())))
            page.close()

        exercise(1440, 1000, "desktop")
        exercise(390, 844, "mobile")
        browser.close()

    add(checks, "external runtime network requests zero", len(external_network) == 0, str(external_network))
    add(checks, "browser errors zero", len(errors) == 0, str(errors))
    status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    receipt = {
        "schema": "axm/deep-tech-governance-browser-qualification@1",
        "status": status,
        "checks_passed": sum(c["status"] == "PASS" for c in checks),
        "checks_total": len(checks),
        "checks": checks,
        "external_runtime_network_requests": external_network,
        "browser_errors": errors,
        "fixture": "fixtures/synthetic-target.json",
        "surface": "workbench.html",
        "harness": "page.set_content; workbench performs no network fetches"
    }
    if args.write:
        (root / "BROWSER_QUALIFICATION.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "checks_passed": receipt["checks_passed"], "checks_total": receipt["checks_total"], "external_network_requests": len(external_network), "browser_errors": len(errors)}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
