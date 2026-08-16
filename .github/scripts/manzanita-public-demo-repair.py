#!/usr/bin/env python3
"""Apply bounded corrections to the public-safe Manzanita demonstration donor."""

from __future__ import annotations

from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


builder_path = Path("manzanita-next/public-demo/build_public_demo.py")
builder = builder_path.read_text(encoding="utf-8")

register_paths = {
    "place": (
        "M92 575 C195 496 278 431 371 376 C469 319 565 296 659 269 "
        "C753 242 843 211 927 170 C1014 128 1091 111 1153 95"
    ),
    "weather": (
        "M78 581 C168 499 247 438 342 389 C438 340 536 315 628 278 "
        "C723 240 814 208 901 166 C994 121 1082 103 1158 88"
    ),
    "water": (
        "M72 600 C164 547 254 502 341 450 C431 396 513 350 602 314 "
        "C694 276 771 233 852 190 C939 144 1025 126 1110 115"
    ),
    "fire": (
        "M66 590 C157 508 237 440 331 387 C428 332 523 300 616 258 "
        "C711 215 794 155 880 120 C970 84 1054 82 1142 66"
    ),
}

for view_id, register_path in register_paths.items():
    marker = f'    "{view_id}": {{\n        "ground": '
    start = builder.find(marker)
    require(start >= 0, f"Cannot locate {view_id} geometry")
    overlay_marker = '\n        "overlay": '
    overlay_at = builder.find(overlay_marker, start)
    require(overlay_at >= 0, f"Cannot locate {view_id} overlay")
    segment = builder[start:overlay_at]
    if '"register"' not in segment:
        builder = (
            builder[:overlay_at]
            + f'\n        "register": "{register_path}",'
            + builder[overlay_at:]
        )

old_error = """    error = receipt.get("error") if state != "ok" else None
    if isinstance(error, str) and len(error) > 240:
        error = error[:237] + "..."
"""
new_error = """    raw_error = receipt.get("error") if state != "ok" else None
    public_errors = {
        "empty": "The provider returned no qualifying item or coverage for this request.",
        "stale": "The retained source exceeds its admitted freshness window.",
        "skipped_missing_credential": "An approved provider credential is not configured; the request was not attempted.",
        "rate_limited": "The provider deferred or refused the request under a rate or quota limit.",
        "unavailable": "The provider, network, transform, or required artifact was unavailable.",
        "terms_blocked": "Provider rights or redistribution terms prohibit inclusion in this public artifact.",
        "unknown": "The retained receipt does not support a more specific public failure classification.",
    }
    error = public_errors.get(state) if state != "ok" else None
    if raw_error and state == "unknown":
        error = public_errors["unknown"]
"""
if old_error in builder:
    builder = builder.replace(old_error, new_error, 1)
require("public_errors = {" in builder, "Public error sanitization did not apply")
builder_path.write_text(builder, encoding="utf-8")

contract_path = Path("manzanita-next/public-demo/PLACE_DEMO_CONTRACT.json")
contract = contract_path.read_text(encoding="utf-8")
contract = contract.replace(
    "No coverage denial, premium setting, evacuation order, enforcement, property-risk score, or loss determination.",
    "No insurance coverage denial, premium setting, evacuation order, enforcement, property-risk score, or loss determination.",
)
require(
    "No insurance coverage denial" in contract,
    "The fire consequence boundary must name insurance explicitly",
)
contract_path.write_text(contract, encoding="utf-8")

app_path = Path("manzanita-next/public-demo/template/app.js")
app = app_path.read_text(encoding="utf-8")
app = app.replace(
    '    elements.fieldRegister.setAttribute("d", view.geometry.ground);',
    '    elements.fieldRegister.setAttribute("d", view.geometry.register);',
)
require(
    "view.geometry.register" in app,
    "Distinct registration geometry did not apply",
)
app_path.write_text(app, encoding="utf-8")

style_path = Path("manzanita-next/public-demo/template/style.css")
style = style_path.read_text(encoding="utf-8")
old_empty = """  .state-empty {
    border-color: var(--uncertain);
    background: repeating-linear-gradient(45deg, transparent 0 4px, var(--uncertain) 4px 6px);
  }
"""
new_empty = """  .state-empty {
    border-color: var(--uncertain);
    background: transparent;
  }

  .state-empty::before,
  .state-empty::after {
    content: "";
    position: absolute;
    left: 2px;
    right: 2px;
    height: 2px;
    background: var(--uncertain);
  }

  .state-empty::before {
    top: 4px;
  }

  .state-empty::after {
    bottom: 4px;
  }
"""
if old_empty in style:
    style = style.replace(old_empty, new_empty, 1)
require(
    "gradient(" not in style.lower(),
    "A gradient shortcut remains in the public-demo visual grammar",
)
style_path.write_text(style, encoding="utf-8")

browser_path = Path("manzanita-next/public-demo/tests/browser_test.py")
browser = browser_path.read_text(encoding="utf-8")
old_runtime = """    runtime = page.evaluate("window.__MANZANITA_PUBLIC_DEMO_RUNTIME__")
    data = page.evaluate("window.__MANZANITA_PUBLIC_DEMO__")
"""
new_runtime = """    runtime = page.evaluate(
        \"\"\"
        () => {
          const runtime = window.__MANZANITA_PUBLIC_DEMO_RUNTIME__;
          return {
            version: runtime.version,
            sourceRunId: runtime.sourceRunId,
            buildId: runtime.buildId,
            views: runtime.views,
            actors: runtime.actors,
            themes: runtime.themes,
            sourceStateCounts: runtime.sourceStateCounts,
            state: runtime.getState(),
          };
        }
        \"\"\"
    )
    data = page.evaluate("window.__MANZANITA_PUBLIC_DEMO__")
"""
if old_runtime in browser:
    browser = browser.replace(old_runtime, new_runtime, 1)
require(
    "state: runtime.getState()" in browser,
    "Serializable runtime inspection did not apply",
)
browser_path.write_text(browser, encoding="utf-8")

unit_path = Path("manzanita-next/public-demo/tests/test_public_demo.py")
unit = unit_path.read_text(encoding="utf-8")
unit = unit.replace(
    '        self.assertEqual(public_data["place"]["latitude"], 34.1432)',
    '        self.assertEqual(public_data["place"]["latitude"], 34.1433)',
)
anchor = """        self.assertNotIn("access_token", serialized)
        self.assertNotIn("https://public.example.invalid", serialized)
"""
replacement = """        self.assertNotIn("access_token", serialized)
        self.assertNotIn("airnow_api_key", serialized)
        self.assertNotIn("firms_map_key", serialized)
        self.assertNotIn("google_maps_api_key", serialized)
        self.assertNotIn("mapillary_access_token", serialized)
        self.assertNotIn("https://public.example.invalid", serialized)
"""
if anchor in unit:
    unit = unit.replace(anchor, replacement, 1)
require(
    'latitude"], 34.1433' in unit,
    "The public precision regression expectation did not update",
)
require(
    "airnow_api_key" in unit,
    "Credential-name regression assertions did not apply",
)
unit_path.write_text(unit, encoding="utf-8")
