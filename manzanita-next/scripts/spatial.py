from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlencode

from .core import Acquisition, parse_rdb


def acquire_usgs_imagery(acq: Acquisition, place: dict[str, Any]) -> None:
    bbox_text = ",".join(map(str, place["areas"]["neighborhood_bbox_wgs84"]))
    common = {"bbox": bbox_text, "bboxSR": 4326, "imageSR": 4326, "size": "1600,1200", "format": "png32", "f": "image"}
    acq.fetch_binary(
        "usgs_imagery",
        "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export",
        {**common, "transparent": "false"},
        ".png",
        required=True,
    )
    acq.fetch_binary(
        "usgs_3dep_hillshade",
        "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage",
        {**common, "renderingRule": json.dumps({"rasterFunction": "Hillshade Multidirectional"})},
        ".png",
        required=True,
    )


def acquire_usgs_water(acq: Acquisition, place: dict[str, Any]) -> None:
    bbox_text = ",".join(map(str, place["areas"]["regional_bbox_wgs84"]))
    site_url = "https://waterservices.usgs.gov/nwis/site/"
    params = {"format": "rdb", "bBox": bbox_text, "siteStatus": "active", "hasDataTypeCd": "iv", "siteOutput": "expanded"}
    try:
        response = acq.request("GET", site_url, params=params, headers={"Accept": "text/plain"})
        response.raise_for_status()
        records = parse_rdb(response.text)
        acq.record(
            "usgs_water_sites",
            "ok" if records else "empty",
            "GET",
            response.url,
            json.dumps({"sites": records[:100], "count": len(records)}, indent=2).encode(),
            ".json",
            response,
            params,
            media_type="application/json",
        )
        site_ids = [row.get("site_no") for row in records if row.get("site_no")][:12]
        if site_ids:
            acq.fetch_json(
                "usgs_water_iv",
                "https://waterservices.usgs.gov/nwis/iv/",
                {
                    "format": "json",
                    "sites": ",".join(site_ids),
                    "period": "P2D",
                    "parameterCd": "00060,00065,00045",
                    "siteStatus": "all",
                },
                required=False,
            )
    except Exception as exc:  # noqa: BLE001
        acq.record("usgs_water_sites", "failed", "GET", site_url, None, ".json", parameters=params, error=str(exc))


def acquire_osm(acq: Acquisition, place: dict[str, Any]) -> None:
    lat = place["center"]["latitude"]
    lon = place["center"]["longitude"]
    radius = place["areas"]["street_radius_m"]
    query = f"""[out:json][timeout:90];(
      way(around:{radius},{lat},{lon})[highway];
      way(around:{radius},{lat},{lon})[building];
      way(around:{radius},{lat},{lon})[landuse];
      way(around:{radius},{lat},{lon})[natural];
      way(around:{radius},{lat},{lon})[waterway];
      node(around:{radius},{lat},{lon})[natural=tree];
      relation(around:{radius},{lat},{lon})[type=multipolygon];
    );out body;>;out skel qt;"""
    encoded = urlencode({"data": query}).encode()
    body_sha256 = hashlib.sha256(encoded).hexdigest()
    endpoints = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            response = acq.request("POST", endpoint, data={"data": query}, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()
            acq.record(
                "osm_overpass",
                "ok",
                "POST",
                endpoint,
                json.dumps(data, indent=2).encode(),
                ".json",
                response,
                {"radius_m": radius, "query": query},
                media_type="application/json",
                body_sha256=body_sha256,
            )
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    acq.record(
        "osm_overpass",
        "failed",
        "POST",
        endpoints[0],
        None,
        ".json",
        parameters={"radius_m": radius, "query": query},
        body_sha256=body_sha256,
        error=str(last_error),
    )
    raise RuntimeError(f"all Overpass endpoints failed: {last_error}")
