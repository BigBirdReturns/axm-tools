from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Any

from .core import Acquisition


def _slippy_tile(latitude: float, longitude: float, zoom: int) -> tuple[int, int]:
    latitude = max(min(latitude, 85.05112878), -85.05112878)
    n = 2**zoom
    x = int((longitude + 180.0) / 360.0 * n)
    latitude_radians = math.radians(latitude)
    y = int((1.0 - math.asinh(math.tan(latitude_radians)) / math.pi) / 2.0 * n)
    return x, y


def _coverage_coordinate_count(document: Any) -> int:
    if not isinstance(document, dict):
        return 0
    geometry = document.get("geometry") if document.get("type") == "Feature" else document
    if isinstance(document.get("features"), list):
        return sum(_coverage_coordinate_count(feature) for feature in document["features"])
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None

    def count(value: Any) -> int:
        if not isinstance(value, list):
            return 0
        if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            return 1
        return sum(count(item) for item in value)

    return count(coordinates)


def acquire_kartaview(acq: Acquisition, place: dict[str, Any]) -> None:
    """Acquire KartaView coverage first, then nearby photo metadata using its documented map query."""
    latitude = float(place["center"]["latitude"])
    longitude = float(place["center"]["longitude"])
    zoom = 15
    tile_x, tile_y = _slippy_tile(latitude, longitude, zoom)
    coverage_url = f"https://api.openstreetcam.org/2.0/sequence/tiles/{tile_x}/{tile_y}/{zoom}.geojson"
    coverage_count = 0
    try:
        coverage_response = acq.request("GET", coverage_url, headers={"Accept": "application/geo+json, application/json"})
        coverage_response.raise_for_status()
        coverage_document = coverage_response.json()
        coverage_count = _coverage_coordinate_count(coverage_document)
        acq.record(
            "kartaview_coverage",
            "ok" if coverage_count else "empty",
            "GET",
            coverage_response.url,
            json.dumps(coverage_document, indent=2).encode(),
            ".geojson",
            coverage_response,
            {"tile_x": tile_x, "tile_y": tile_y, "zoom": zoom},
            media_type="application/geo+json",
        )
    except Exception as exc:  # noqa: BLE001
        acq.record(
            "kartaview_coverage",
            "failed",
            "GET",
            coverage_url,
            None,
            ".geojson",
            parameters={"tile_x": tile_x, "tile_y": tile_y, "zoom": zoom},
            error=str(exc),
        )

    photo_url = "https://api.openstreetcam.org/2.0/photo/"
    photo_params = {
        "lat": latitude,
        "lng": longitude,
        "zoomLevel": zoom,
        "join": "sequence",
        "orderBy": "id",
        "orderDirection": "desc",
    }
    try:
        photo_response = acq.request("GET", photo_url, params=photo_params, headers={"Accept": "application/json"})
        raw_payload = photo_response.content
        try:
            photo_document = photo_response.json()
            normalized_payload = json.dumps(photo_document, indent=2).encode()
        except ValueError:
            photo_document = None
            normalized_payload = raw_payload

        if photo_response.ok:
            result = photo_document.get("result") if isinstance(photo_document, dict) else None
            photos = result.get("data") if isinstance(result, dict) else None
            status = "ok" if isinstance(photos, list) and photos else "empty"
            error = None
        else:
            status = "degraded"
            error = (
                f"KartaView nearby-photo endpoint returned HTTP {photo_response.status_code}; "
                f"coverage coordinate count was {coverage_count}. The exact provider response is retained."
            )
        acq.record(
            "kartaview",
            status,
            "GET",
            photo_response.url,
            normalized_payload,
            ".json",
            photo_response,
            photo_params,
            error=error,
            media_type="application/json",
        )
    except Exception as exc:  # noqa: BLE001
        acq.record(
            "kartaview",
            "degraded",
            "GET",
            photo_url,
            None,
            ".json",
            parameters=photo_params,
            error=f"KartaView nearby-photo retrieval failed after coverage probe: {exc}",
        )


def acquire_panoramax(acq: Acquisition, place: dict[str, Any]) -> None:
    bbox = place["areas"]["neighborhood_bbox_wgs84"]
    url = "https://api.panoramax.xyz/api/search"
    body = {"bbox": bbox, "limit": 50}
    body_sha256 = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    try:
        response = acq.request("POST", url, json=body, headers={"Accept": "application/geo+json, application/json"})
        if response.status_code in {404, 405}:
            response = acq.request("GET", url, params={"bbox": ",".join(map(str, bbox)), "limit": 50})
        response.raise_for_status()
        data = response.json()
        acq.record(
            "panoramax",
            "ok" if data.get("features") else "empty",
            response.request.method,
            response.url,
            json.dumps(data, indent=2).encode(),
            ".json",
            response,
            {"bbox": bbox, "limit": 50, "request_body": body},
            media_type="application/json",
            body_sha256=body_sha256,
        )
        features = data.get("features") or []
        if features:
            assets = features[0].get("assets") or {}
            candidate = assets.get("thumbnail") or assets.get("visual") or assets.get("data")
            if isinstance(candidate, dict) and candidate.get("href"):
                thumbnail = acq.request("GET", candidate["href"])
                thumbnail.raise_for_status()
                if len(thumbnail.content) > 1024:
                    properties = features[0].get("properties") or {}
                    acq.record(
                        "panoramax_thumbnail",
                        "ok",
                        "GET",
                        candidate["href"],
                        thumbnail.content,
                        ".jpg",
                        thumbnail,
                        attribution_override=str(properties.get("providers") or properties.get("author") or "Panoramax item contributor"),
                        license_override=str(properties.get("license") or candidate.get("license") or "item license not supplied"),
                    )
    except Exception as exc:  # noqa: BLE001
        acq.record("panoramax", "failed", "POST", url, None, ".json", parameters={"bbox": bbox}, error=str(exc))


def acquire_keyed_sources(acq: Acquisition, place: dict[str, Any]) -> None:
    lat = place["center"]["latitude"]
    lon = place["center"]["longitude"]

    airnow_key = os.getenv("AIRNOW_API_KEY")
    if airnow_key:
        acq.fetch_json(
            "airnow",
            "https://www.airnowapi.org/aq/observation/latLong/current/",
            {"format": "application/json", "latitude": lat, "longitude": lon, "distance": 50, "API_KEY": airnow_key},
            required=False,
        )
    else:
        acq.record("airnow", "skipped_missing_credential", "GET", "https://www.airnowapi.org/aq/observation/latLong/current/", None, ".json", error="AIRNOW_API_KEY is not configured")

    firms_key = os.getenv("FIRMS_MAP_KEY")
    if firms_key:
        area = ",".join(map(str, place["areas"]["regional_bbox_wgs84"]))
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{firms_key}/VIIRS_SNPP_NRT/{area}/2"
        try:
            response = acq.request("GET", url)
            response.raise_for_status()
            acq.record("firms", "ok", "GET", response.url, response.content, ".csv", response, media_type="text/csv")
        except Exception as exc:  # noqa: BLE001
            acq.record("firms", "failed", "GET", url, None, ".csv", error=str(exc))
    else:
        acq.record("firms", "skipped_missing_credential", "GET", "https://firms.modaps.eosdis.nasa.gov/api/", None, ".csv", error="FIRMS_MAP_KEY is not configured")

    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if google_key:
        url = "https://maps.googleapis.com/maps/api/streetview/metadata"
        params = {"location": f"{lat},{lon}", "radius": 200, "source": "outdoor", "key": google_key}
        try:
            response = acq.request("GET", url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()
            provider_status = str(data.get("status", "UNKNOWN"))
            status = "ok" if provider_status == "OK" else "empty" if provider_status == "ZERO_RESULTS" else "failed"
            acq.record(
                "google_street_view",
                status,
                "GET",
                response.url,
                json.dumps(data, indent=2).encode(),
                ".json",
                response,
                params,
                error=None if status != "failed" else f"Google Street View metadata status: {provider_status}",
                media_type="application/json",
            )
        except Exception as exc:  # noqa: BLE001
            acq.record("google_street_view", "failed", "GET", url, None, ".json", parameters=params, error=str(exc))
    else:
        acq.record("google_street_view", "skipped_missing_credential", "GET", "https://maps.googleapis.com/maps/api/streetview/metadata", None, ".json", error="GOOGLE_MAPS_API_KEY is not configured")

    mapillary_token = os.getenv("MAPILLARY_ACCESS_TOKEN")
    if mapillary_token:
        url = "https://graph.mapillary.com/images"
        params = {
            "access_token": mapillary_token,
            "bbox": ",".join(map(str, place["areas"]["neighborhood_bbox_wgs84"])),
            "fields": "id,computed_geometry,captured_at,compass_angle,thumb_1024_url",
            "limit": 25,
        }
        try:
            response = acq.request("GET", url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()
            acq.record("mapillary", "ok" if data.get("data") else "empty", "GET", response.url, json.dumps(data, indent=2).encode(), ".json", response, params, media_type="application/json")
        except Exception as exc:  # noqa: BLE001
            acq.record("mapillary", "failed", "GET", url, None, ".json", parameters=params, error=str(exc))
    else:
        acq.record("mapillary", "skipped_missing_credential", "GET", "https://graph.mapillary.com/images", None, ".json", error="MAPILLARY_ACCESS_TOKEN is not configured")
