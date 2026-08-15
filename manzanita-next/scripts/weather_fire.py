from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

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


def acquire_calfire(acq: Acquisition) -> None:
    url = "https://www.fire.ca.gov/incidents"
    try:
        response = acq.request("GET", url, headers={"Accept": "text/html"})
        response.raise_for_status()
        source_html = response.content
        acq.record("calfire_incidents", "ok", "GET", response.url, source_html, ".html", response, media_type="text/html")
        soup = BeautifulSoup(source_html, "html.parser")
        rows: list[dict[str, str | None]] = []
        for table in soup.find_all("table"):
            headers = [cell.get_text(" ", strip=True).lower() for cell in table.find_all("th")]
            if "incident" not in headers or "containment" not in headers:
                continue
            for tr in table.find_all("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in tr.find_all("td")]
                if len(cells) < 5:
                    continue
                link = tr.find("a")
                href = link.get("href") if link else None
                rows.append({
                    "incident": cells[0],
                    "counties": cells[1],
                    "started": cells[2],
                    "acres": cells[3],
                    "containment": cells[4],
                    "source_url": f"https://www.fire.ca.gov{href}" if isinstance(href, str) and href.startswith("/") else href,
                })
            if rows:
                break
        normalized = {
            "source": url,
            "retrieved_at": acq.now(),
            "disclaimer": "Reference information only. Follow local authorities for emergency instructions.",
            "active_incidents": rows,
        }
        acq.record(
            "calfire_incidents_normalized",
            "ok" if rows else "empty",
            "GET",
            response.url,
            json.dumps(normalized, indent=2).encode(),
            "-normalized.json",
            response,
            media_type="application/json",
        )
    except Exception as exc:  # noqa: BLE001
        acq.record("calfire_incidents", "failed", "GET", url, None, ".html", error=str(exc))
        raise
