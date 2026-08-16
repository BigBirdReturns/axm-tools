from __future__ import annotations

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DESIGN_ROOT = Path(__file__).resolve().parents[1]
SPECIMEN = DESIGN_ROOT / "specimen"
CONSTITUTION = DESIGN_ROOT / "CONSTITUTION.json"
HTML = SPECIMEN / "index.html"
CSS = SPECIMEN / "style.css"
JS = SPECIMEN / "app.js"

EXPECTED_TASKS = {f"JDB99-{index:03d}" for index in range(4, 12)}
EXPECTED_PRIMITIVES = {
    "ground_contour",
    "branch_line",
    "evidence_node",
    "consequence_cut",
    "register_line",
    "source_rail",
}
EXPECTED_TYPE_ROLES = {
    "display",
    "editorial",
    "operational",
    "label",
    "data",
    "compact",
}
EXPECTED_MATERIALS = {
    "paper",
    "paper_alt",
    "ink",
    "ink_muted",
    "bark",
    "leaf",
    "water",
    "sun",
    "uncertain",
    "failure",
}
EXPECTED_SOURCE_CLASSES = {
    "observed",
    "provider_rendered",
    "captured_first_party",
    "authored",
    "modeled",
    "generated",
    "derived",
    "unavailable",
    "redacted",
}
EXPECTED_MOTION = {
    "scale_change",
    "registration",
    "source_change",
    "state_transition",
    "handoff",
}
EXPECTED_COMPONENTS = {
    "forkline_header",
    "registered_field_plate",
    "source_rail",
    "actor_action_branch",
    "evidence_ledger",
    "failure_sheet",
    "handoff_receipt",
}
EXPECTED_APERTURES = {"plant", "household", "street", "region"}
EXPECTED_OVERLAYS = {"habitat", "heat", "water", "fire"}
EXPECTED_ACTORS = {"resident", "steward", "planner"}
EXPECTED_THEMES = {"auto", "light", "dark"}


class SpecimenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.buttons: list[dict[str, str]] = []
        self.external_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheets.append(values.get("href", ""))
        if tag == "button":
            self.buttons.append(values)
        for key in ("src", "href"):
            value = values.get(key, "")
            if re.match(r"^(?:https?:)?//", value):
                self.external_urls.append(value)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def relative_luminance(value: str) -> float:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise AssertionError(f"Expected six-digit color, received {value!r}")
    channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    first_luminance = relative_luminance(first)
    second_luminance = relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


class ConstitutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.constitution = read_json(CONSTITUTION)
        cls.html = HTML.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.js = JS.read_text(encoding="utf-8")
        cls.parser = SpecimenParser()
        cls.parser.feed(cls.html)

    def test_constitution_identity_and_authority_boundary(self) -> None:
        data = self.constitution
        self.assertEqual(data["schema"], "axm-tools/manzanita-design-constitution@1")
        self.assertEqual(data["constitution_id"], "M99-DESIGN-CONSTITUTION")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["state"], "internal_candidate")
        self.assertEqual(set(data["task_references"]), EXPECTED_TASKS)
        self.assertEqual(data["object"]["accountable_actor"], "design_integrator")
        self.assertEqual(data["object"]["review_mechanism"], "M99-CONTAINED-REVIEW-BOARD")
        self.assertEqual(data["object"]["decision_authority"], "release_authority")
        self.assertEqual(data["object"]["public_effect"], "none")
        self.assertEqual(data["object"]["constitutional_count_effect"], "none")
        boundary = data["object"]["claim_boundary"].lower()
        for term in ("does not qualify", "public", "field", "external"):
            self.assertIn(term, boundary)

    def test_recognizable_form_is_complete_and_geometry_bound(self) -> None:
        language = self.constitution["form_language"]
        primitives = language["primitives"]
        self.assertEqual({row["id"] for row in primitives}, EXPECTED_PRIMITIVES)
        for row in primitives:
            self.assertGreaterEqual(len(row["meaning"]), 20)
            self.assertTrue(row["required_fields"])
            self.assertGreaterEqual(len(row["visual_law"]), 20)
        recognition = self.constitution["identity"]["recognition_test"].lower()
        for term in ("ground contour", "forked", "square evidence", "consequence", "source rail"):
            self.assertIn(term, recognition)
        registration = language["registration_law"].lower()
        for term in ("retained vertex", "station", "authored anchor", "labeled"):
            self.assertIn(term, registration)

    def test_typography_roles_and_compact_law_are_explicit(self) -> None:
        typography = self.constitution["typography"]
        roles = typography["roles"]
        self.assertEqual({row["id"] for row in roles}, EXPECTED_TYPE_ROLES)
        for row in roles:
            self.assertIn("stack", row)
            self.assertIn("size_clamp", row)
            self.assertGreater(row["line_height"], 0)
            self.assertGreaterEqual(len(row["use"]), 20)
        acceptance = " ".join(typography["optical_acceptance"]).lower()
        for term in ("320 css pixels", "200 percent zoom", "fallback", "ad hoc"):
            self.assertIn(term, acceptance)
        self.assertIn("tabular", typography["numeral_law"].lower())

    def test_light_and_dark_materials_share_semantic_roles_and_contrast(self) -> None:
        materials = self.constitution["materials"]
        tokens = {row["id"]: row for row in materials["semantic_tokens"]}
        self.assertEqual(set(tokens), EXPECTED_MATERIALS)
        for token in tokens.values():
            self.assertRegex(token["light"], r"^#[0-9a-fA-F]{6}$")
            self.assertRegex(token["dark"], r"^#[0-9a-fA-F]{6}$")
            self.assertNotEqual(token["light"].lower(), token["dark"].lower())
            self.assertGreaterEqual(len(token["meaning"]), 8)
        self.assertGreaterEqual(
            contrast_ratio(tokens["paper"]["light"], tokens["ink"]["light"]),
            7.0,
        )
        self.assertGreaterEqual(
            contrast_ratio(tokens["paper"]["dark"], tokens["ink"]["dark"]),
            7.0,
        )
        self.assertGreaterEqual(
            contrast_ratio(tokens["paper"]["light"], tokens["ink_muted"]["light"]),
            4.5,
        )
        self.assertGreaterEqual(
            contrast_ratio(tokens["paper"]["dark"], tokens["ink_muted"]["dark"]),
            4.5,
        )
        parity = materials["parity_law"].lower()
        for term in ("identical", "content hierarchy", "source visibility", "failure"):
            self.assertIn(term, parity)

    def test_source_classes_preserve_authorship_and_failure(self) -> None:
        classes = self.constitution["art_direction"]["classes"]
        self.assertEqual({row["id"] for row in classes}, EXPECTED_SOURCE_CLASSES)
        for row in classes:
            for field in (
                "required_label",
                "required_custody",
                "permitted_claim",
                "prohibited_substitution",
            ):
                self.assertGreaterEqual(len(row[field]), 10)
        generated = next(row for row in classes if row["id"] == "generated")
        generated_boundary = generated["prohibited_substitution"].lower()
        for term in ("street imagery", "geospatial", "current conditions", "work receipts"):
            self.assertIn(term, generated_boundary)
        unavailable = next(row for row in classes if row["id"] == "unavailable")
        self.assertIn("safe", unavailable["prohibited_substitution"].lower())

    def test_motion_content_and_components_are_complete(self) -> None:
        self.assertEqual(
            {row["id"] for row in self.constitution["motion"]["semantics"]},
            EXPECTED_MOTION,
        )
        for row in self.constitution["motion"]["semantics"]:
            self.assertGreaterEqual(len(row["meaning"]), 20)
            self.assertGreaterEqual(len(row["reduced_motion"]), 20)
        self.assertEqual(
            {row["id"] for row in self.constitution["components"]},
            EXPECTED_COMPONENTS,
        )
        for component in self.constitution["components"]:
            self.assertTrue(component["required_states"])
            self.assertGreaterEqual(len(component["acceptance"]), 20)
        reading_order = self.constitution["content"]["reading_order"]
        self.assertEqual(reading_order[0], "actor")
        self.assertIn("prohibited_effect", reading_order)
        self.assertEqual(self.constitution["content"]["theme_labels"], ["Auto", "Light", "Dark"])

    def test_specimen_is_self_contained_and_visibly_bounded(self) -> None:
        self.assertEqual(self.parser.scripts, ["app.js"])
        self.assertEqual(self.parser.stylesheets, ["style.css"])
        self.assertEqual(self.parser.external_urls, [])
        required_ids = {
            "specimen",
            "field-svg",
            "ground-contour",
            "overlay-area",
            "source-rail-title",
            "actor-title",
            "failure-title",
            "handoff-title",
        }
        self.assertTrue(required_ids.issubset(self.parser.ids))
        html_lower = self.html.lower()
        for phrase in (
            "authored demonstration geometry",
            "not a surveyed place",
            "no inspection",
            "internal candidate",
            "no release",
        ):
            self.assertIn(phrase, html_lower)

    def test_controls_match_constitution_and_use_ordinary_labels(self) -> None:
        theme_values = {
            row.get("data-theme-choice")
            for row in self.parser.buttons
            if row.get("data-theme-choice")
        }
        aperture_values = {
            row.get("data-aperture-choice")
            for row in self.parser.buttons
            if row.get("data-aperture-choice")
        }
        overlay_values = {
            row.get("data-overlay-choice")
            for row in self.parser.buttons
            if row.get("data-overlay-choice")
        }
        actor_values = {
            row.get("data-actor-choice")
            for row in self.parser.buttons
            if row.get("data-actor-choice")
        }
        self.assertEqual(theme_values, EXPECTED_THEMES)
        self.assertEqual(aperture_values, EXPECTED_APERTURES)
        self.assertEqual(overlay_values, EXPECTED_OVERLAYS)
        self.assertEqual(actor_values, EXPECTED_ACTORS)
        for button in self.parser.buttons:
            self.assertEqual(button.get("type"), "button")
            if any(key.startswith("data-") and key.endswith("-choice") for key in button):
                self.assertIn(button.get("aria-pressed"), {"true", "false"})
        visible_modes = re.findall(r">\s*(Auto|Light|Dark)\s*<", self.html)
        self.assertEqual(set(visible_modes), {"Auto", "Light", "Dark"})
        self.assertNotIn("signal sheet</button", self.html.lower())
        self.assertNotIn("forkline field</button", self.html.lower())

    def test_css_rejects_generic_shell_shortcuts(self) -> None:
        css_lower = self.css.lower()
        for forbidden in (
            "linear-gradient(",
            "radial-gradient(",
            "conic-gradient(",
            "backdrop-filter",
            "@import",
            "url(http",
            "border-radius: 999",
        ):
            self.assertNotIn(forbidden, css_lower)
        self.assertIn("prefers-reduced-motion: reduce", css_lower)
        self.assertIn("forced-colors: active", css_lower)
        self.assertIn("@media print", css_lower)
        self.assertIn("outline: 3px solid var(--focus)", css_lower)
        self.assertIn("min-height: 44px", css_lower)

    def test_javascript_changes_real_state_without_network_or_fixtures(self) -> None:
        js_lower = self.js.lower()
        for forbidden in (
            "fetch(",
            "xmlhttprequest",
            "websocket",
            "eventsource",
            "navigator.sendbeacon",
            "http://",
            "https://",
        ):
            self.assertNotIn(forbidden, js_lower)
        for aperture in EXPECTED_APERTURES:
            self.assertRegex(self.js, rf"\b{re.escape(aperture)}\s*:\s*\{{")
        for overlay in EXPECTED_OVERLAYS:
            self.assertRegex(self.js, rf"\b{re.escape(overlay)}\s*:\s*\{{")
        for actor in EXPECTED_ACTORS:
            self.assertRegex(self.js, rf"\b{re.escape(actor)}\s*:\s*\{{")
        for mechanism in (
            "setAttribute(\"d\"",
            "sourceGeometry.textContent",
            "actorAuthority.textContent",
            "aria-pressed",
            "manzanita:statechange",
            "m99-theme",
        ):
            self.assertIn(mechanism, self.js)
        geometry_ids = set(re.findall(r'M99-AUTH-[A-Z-]+-001', self.js))
        self.assertEqual(len(geometry_ids), 4)

    def test_specimen_contract_matches_machine_constitution(self) -> None:
        specimen = self.constitution["specimen"]
        self.assertEqual(set(specimen["apertures"]), EXPECTED_APERTURES)
        self.assertEqual(set(specimen["overlays"]), EXPECTED_OVERLAYS)
        self.assertEqual(set(specimen["actors"]), EXPECTED_ACTORS)
        self.assertEqual(set(specimen["themes"]), EXPECTED_THEMES)
        self.assertEqual(specimen["data_class"], "authored_demonstration_geometry")
        self.assertTrue(specimen["required_tests"])
        self.assertIn("no external requests", specimen["required_tests"])
        self.assertIn("zero horizontal overflow", specimen["required_tests"])


if __name__ == "__main__":
    unittest.main()
