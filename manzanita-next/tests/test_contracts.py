from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.core import Acquisition  # noqa: E402


def load_registry() -> dict:
    source_by_id: dict[str, dict] = {}
    for path in sorted((ROOT / "config").glob("source-registry*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for source in document.get("sources", []):
            source_by_id[source["id"]] = source
    return {"sources": list(source_by_id.values())}


def test_place_config() -> None:
    place = json.loads((ROOT / "config" / "place-demo.json").read_text(encoding="utf-8"))
    assert place["place_id"] == "mw-public-demo-arboretum-001"
    assert place["privacy"]["contains_private_household_data"] is False
    assert place["privacy"]["exact_private_address_allowed"] is False
    assert len(place["areas"]["regional_bbox_wgs84"]) == 4


def test_source_registry() -> None:
    registry = load_registry()
    ids = [source["id"] for source in registry["sources"]]
    assert len(ids) == len(set(ids))
    by_id = {source["id"]: source for source in registry["sources"]}
    for source in registry["sources"]:
        assert source["name"]
        assert source["attribution"]
        assert "license" in source
        assert source["cache_policy"]
        assert source["claim_scope"]
    for required in (
        "google_street_view",
        "mapillary",
        "kartaview",
        "panoramax",
        "nws_alerts",
        "calfire_incidents",
        "usgs_imagery",
        "usgs_3dep_hillshade",
        "osm_overpass",
    ):
        assert required in ids
    assert "CA_Perimeters_NIFC_FIRIS_public_view" in by_id["calfire_incidents"]["base_url"]
    assert "complete incident list" in by_id["calfire_incidents"]["claim_scope"]


def test_every_acquisition_source_id_is_registered() -> None:
    registry_ids = {source["id"] for source in load_registry()["sources"]}
    script = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts").glob("*.py"))
    used_ids = set(
        re.findall(
            r'(?:record|fetch_json|fetch_binary)\(\s*["\']([a-z0-9_]+)["\']',
            script,
            flags=re.MULTILINE,
        )
    )
    assert used_ids
    assert used_ids <= registry_ids, sorted(used_ids - registry_ids)


def test_street_provider_adapter_set() -> None:
    provider_dir = ROOT / "providers" / "street"
    required = {
        "provider_resolver.js",
        "google_street_view.js",
        "mapillary.js",
        "kartaview.js",
        "panoramax.js",
        "owned_capture.js",
        "map_only.js",
    }
    assert required <= {path.name for path in provider_dir.glob("*.js")}
    resolver = (provider_dir / "provider_resolver.js").read_text(encoding="utf-8")
    expected_order = [
        "google_street_view",
        "mapillary",
        "kartaview",
        "panoramax",
        "owned_capture",
        "map_only",
    ]
    positions = [resolver.index(f'"{provider}"') for provider in expected_order]
    assert positions == sorted(positions)


def test_secret_values_are_redacted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "super-secret-value")
    acquisition = Acquisition(tmp_path, load_registry())
    sanitized = acquisition.sanitize_url(
        "https://example.test/asset/super-secret-value?key=super-secret-value&safe=yes"
    )
    assert "super-secret-value" not in sanitized
    assert "%5BREDACTED%5D" in sanitized or "[REDACTED]" in sanitized
    parameters = acquisition.redact_value(
        {"access_token": "super-secret-value", "nested": {"value": "super-secret-value"}}
    )
    assert parameters["access_token"] == "[REDACTED]"
    assert parameters["nested"]["value"] == "[REDACTED]"


def test_no_secret_values_in_example() -> None:
    credentials = json.loads((ROOT / "config" / "credentials.example.json").read_text(encoding="utf-8"))
    assert credentials
    assert all(value == "" for value in credentials.values())
