#!/usr/bin/env python3
"""Bound the expected browser console error in the missing-image campaign."""

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


path = Path("manzanita-next/qualification/run_qualification.py")
text = path.read_text(encoding="utf-8")

old_signature = '''def assert_no_unexpected_errors(
    observed: dict[str, list[str]],
    *,
    allowed_failed_suffixes: tuple[str, ...] = (),
) -> None:
    failures = [
        url for url in observed["request_failures"]
        if not any(url.endswith(suffix) for suffix in allowed_failed_suffixes)
    ]
    require(not observed["console_errors"], f"Console errors: {observed['console_errors']}")
'''
new_signature = '''def assert_no_unexpected_errors(
    observed: dict[str, list[str]],
    *,
    allowed_failed_suffixes: tuple[str, ...] = (),
    allowed_console_substrings: tuple[str, ...] = (),
) -> None:
    failures = [
        url for url in observed["request_failures"]
        if not any(url.endswith(suffix) for suffix in allowed_failed_suffixes)
    ]
    console_errors = [
        message for message in observed["console_errors"]
        if not any(substring in message for substring in allowed_console_substrings)
    ]
    require(not console_errors, f"Console errors: {console_errors}")
'''
if old_signature in text:
    text = text.replace(old_signature, new_signature, 1)
require("allowed_console_substrings: tuple[str, ...] = ()" in text, "Bounded console allowance did not apply")
require("require(not console_errors" in text, "Filtered console assertion did not apply")

old_campaign = '''    require(page.locator("#rail-receipt").inner_text().strip() != "", "Missing imagery erased the experience receipt")
    require(page.locator("#stage-caption").inner_text().strip() != "", "Missing imagery erased the registration claim boundary")
    assert_no_unexpected_errors(observed, allowed_failed_suffixes=("/assets/base-imagery.png",))
    context.close()
    return {"id": "missing_base_image", "result": "PASS", "expected_failed_resource": "assets/base-imagery.png", "receipt_visible": True, "claim_boundary_visible": True}
'''
new_campaign = '''    require(page.locator("#rail-receipt").inner_text().strip() != "", "Missing imagery erased the experience receipt")
    require(page.locator("#stage-caption").inner_text().strip() != "", "Missing imagery erased the registration claim boundary")
    expected_console_errors = [
        message for message in observed["console_errors"]
        if "Failed to load resource" in message and "ERR_FAILED" in message
    ]
    require(
        len(expected_console_errors) == 1,
        f"Missing-image campaign expected one failed-resource console receipt, observed {observed['console_errors']}",
    )
    expected_request_failures = [
        url for url in observed["request_failures"]
        if url.endswith("/assets/base-imagery.png")
    ]
    require(
        len(expected_request_failures) == 1,
        f"Missing-image campaign expected one failed image request, observed {observed['request_failures']}",
    )
    assert_no_unexpected_errors(
        observed,
        allowed_failed_suffixes=("/assets/base-imagery.png",),
        allowed_console_substrings=("Failed to load resource: net::ERR_FAILED",),
    )
    context.close()
    return {
        "id": "missing_base_image",
        "result": "PASS",
        "expected_failed_resource": "assets/base-imagery.png",
        "expected_console_errors": expected_console_errors,
        "expected_request_failures": expected_request_failures,
        "receipt_visible": True,
        "claim_boundary_visible": True,
    }
'''
if old_campaign in text:
    text = text.replace(old_campaign, new_campaign, 1)
require("expected_console_errors = [" in text, "Expected missing-image console receipt did not apply")
require("expected_request_failures = [" in text, "Expected missing-image request receipt did not apply")
require("allowed_console_substrings=(\"Failed to load resource: net::ERR_FAILED\",)" in text, "Missing-image bounded allowance did not apply")

path.write_text(text, encoding="utf-8")
