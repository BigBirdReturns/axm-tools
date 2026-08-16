from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .core import Acquisition


def acquire_nws(acq: Acquisition, place: dict[str, Any]) -> None:
    lat = place["center"]["latitude"]
    lon = place["center"]["longitude"]
    points = acq.fetch_json("nws_points", f"https://api.weather.gov/points/{lat},{lon}", required=True)
    props = points["properties"]
    acq.fetch_json("nws_forecast", props["forecast"], required=True)
    acq.fetch_json("nws_forecast_hourly", props["forecastHourly"], required=False)
    acq.fetch_json("nws_alerts", "https://api.weather.gov/alerts/active", params={"point": f"{lat},{lon}"}, required=True)
    stations = acq.fetch_json("nws_stations", props["observationStations"], required=False)
    if stations and stations.get("features"):
        station_id = stations["features"][0]["properties"]["stationIdentifier"]
        acq.fetch_json("nws_observation", f"https://api.weather.gov/stations/{station_id}/observations/latest", required=False)


def _epoch_millis_to_iso(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def acquire_calfire(acq: Acquisition) -> None:
    """Acquire the official public CAL FIRE/NIFC/FIRIS active-perimeter feature view."""
    url = (
        "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
        "CA_Perimeters_NIFC_FIRIS_public_view/FeatureServer/0/query"
    )
    params = {
        "where": "displayStatus='Active'",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "orderByFields": "poly_DateCurrent DESC",
        "f": "geojson",
    }
    try:
        response = acq.request("GET", url, params=params, headers={"Accept": "application/geo+json, application/json"})
        response.raise_for_status()
        source = response.json()
        features = source.get("features") or []
        source_times: list[tuple[float, str]] = []
        normalized_features: list[dict[str, Any]] = []
        for feature in features:
            props = feature.get("properties") or {}
            for field in ("poly_DateCurrent", "EditDate", "CreationDate", "FireDiscoveryDate"):
                value = props.get(field)
                converted = _epoch_millis_to_iso(value)
                if converted and isinstance(value, (int, float)):
                    source_times.append((float(value), converted))
            normalized_features.append(
                {
                    "feature_id": props.get("GlobalID") or props.get("OBJECTID"),
                    "incident_name": props.get("incident_name") or props.get("mission"),
                    "incident_number": props.get("incident_number"),
                    "display_status": props.get("displayStatus"),
                    "source": props.get("source"),
                    "perimeter_type": props.get("type"),
                    "area_acres": props.get("area_acres") or props.get("NIFC_GISAcres"),
                    "percent_contained": props.get("Percent_Contained"),
                    "perimeter_current_at": _epoch_millis_to_iso(props.get("poly_DateCurrent")),
                    "fire_discovered_at": _epoch_millis_to_iso(props.get("FireDiscoveryDate")),
                    "edited_at": _epoch_millis_to_iso(props.get("EditDate")),
                    "geometry": feature.get("geometry"),
                    "description": props.get("description"),
                }
            )
        source_time = max(source_times, default=(0, None), key=lambda item: item[0])[1]
        source_bytes = json.dumps(source, indent=2).encode()
        acq.record(
            "calfire_incidents",
            "ok",
            "GET",
            response.url,
            source_bytes,
            ".geojson",
            response,
            params,
            source_time=source_time,
            media_type="application/geo+json",
        )
        normalized = {
            "schema": "manzanita-works/calfire-active-perimeter-index@1",
            "source": url,
            "retrieved_at": acq.now(),
            "source_time": source_time,
            "feature_count": len(normalized_features),
            "disclaimer": (
                "Active perimeter reference only. The layer is not a complete incident list, evacuation order, "
                "structure-damage finding, or parcel-level determination. Follow local authorities for emergency instructions."
            ),
            "active_perimeters": normalized_features,
        }
        acq.record(
            "calfire_incidents_normalized",
            "ok" if normalized_features else "empty",
            "GET",
            response.url,
            json.dumps(normalized, indent=2).encode(),
            "-normalized.json",
            response,
            params,
            source_time=source_time,
            media_type="application/json",
        )
    except Exception as exc:  # noqa: BLE001
        acq.record("calfire_incidents", "failed", "GET", url, None, ".geojson", parameters=params, error=str(exc))
        raise
