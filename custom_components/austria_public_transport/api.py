"""API helpers for the Austria Public Transport integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    API_ENDPOINT,
    API_TIMEOUT,
    TRAFFIC_INFO_CATEGORY_ORDER,
    TRAFFIC_INFO_ENDPOINT,
    TRAFFIC_INFO_OK_CODE,
)

_LOGGER = logging.getLogger(__name__)


def _clean_text(text: str | None) -> str | None:
    """Change line breaks and repeated whitespace into single spaces"""
    if not text:
        return text
    return " ".join(text.split())


async def async_fetch_departures(
    session: aiohttp.ClientSession, stop_id: str
) -> dict[str, Any]:
    """Fetch and parse departure data for a stop from the Wiener Linien API.

    Returns a dict with departures_count, stop_id, stop_name, departures list,
    and server_time. Returns a dict with just 'message' on error.
    """
    try:
        url = f"{API_ENDPOINT}?stopId={stop_id}"
        async with asyncio.timeout(API_TIMEOUT):
            response = await session.get(url)
            data = await response.json()

        if not data.get("data", {}).get("monitors"):
            _LOGGER.warning("No monitor data for stop %s", stop_id)
            return {"message": "No data"}

        monitors = data["data"]["monitors"]
        departures: list[dict[str, Any]] = []
        stop_name = "Unknown"

        if monitors:
            stop_name = (
                monitors[0]
                .get("locationStop", {})
                .get("properties", {})
                .get("title", "Unknown")
            )

            for monitor in monitors:
                lines = monitor.get("lines", [])
                for line in lines:
                    line_departures = line.get("departures", {}).get("departure", [])
                    for departure in line_departures:
                        dep_time = departure.get("departureTime", {})
                        vehicle = departure.get("vehicle", {})

                        departures.append(
                            {
                                "line": line.get("name"),
                                "direction": line.get("towards"),
                                "platform": line.get("platform"),
                                "time_planned": dep_time.get("timePlanned"),
                                "time_real": dep_time.get("timeReal"),
                                "countdown": dep_time.get("countdown"),
                                "barrier_free": vehicle.get("barrierFree", False),
                                "folding_ramp": vehicle.get("foldingRamp", False),
                                "type": vehicle.get("type"),
                            }
                        )

        departures.sort(
            key=lambda x: x["countdown"] if x.get("countdown") is not None else 999
        )

        return {
            "departures_count": len(departures),
            "stop_id": stop_id,
            "stop_name": stop_name,
            "departures": departures,
            "server_time": data.get("message", {}).get("serverTime"),
        }

    except TimeoutError:
        _LOGGER.error("Timeout fetching data for stop %s", stop_id)
        return {"message": "Timeout"}
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching data for stop %s: %s", stop_id, err)
        return {"message": "No data"}
    except Exception as err:
        _LOGGER.warning("Unexpected error for stop %s: %s", stop_id, err)
        return {"message": "No data"}


async def async_fetch_traffic_info(
    session: aiohttp.ClientSession,
    category: str | None = None,
    line: str | None = None,
    stop_id: int | None = None,
    max_alerts: int = 20,
) -> dict[str, Any]:
    """Getting and normalizing Wiener Linien Traffic info(disruptions, elevators).
    Returns a dict with alerts_count and an alerts list. Returns a dict with
    """
    try:
        async with asyncio.timeout(API_TIMEOUT):
            response = await session.get(TRAFFIC_INFO_ENDPOINT)
            data = await response.json()

            message = data.get("message") or {}
        if message.get("messageCode") != TRAFFIC_INFO_OK_CODE:
            _LOGGER.warning(
                "Wiener Linien traffic info API error %s: %s",
                message.get("messageCode"),
                message.get("value"),
            )
            return {"message": message.get("value") or "No data"}
        payload = data.get("data") or {}
        categories = {
            cat.get("id"): cat.get("name")
            for cat in payload.get("trafficInfoCategories") or []
        }
        alerts: list[dict[str, Any]] = []

        for item in payload.get("trafficInfos") or []:
            attributes = item.get("attributes") or {}
            time_info = item.get("time") or {}
            item_category = categories.get(item.get("refTrafficInfoCategoryId"))
            lines = item.get("relatedLines") or []
            stops = list(dict.fromkeys(item.get("relatedStops") or []))

            if category and item_category != category:
                continue
            if line and line.upper() not in [name.upper() for name in lines]:
                continue
            if stop_id is not None and stop_id not in stops:
                continue

            alerts.append(
                {
                    "id": item.get("name"),
                    "category": item_category,
                    "title": _clean_text(item.get("title")),
                    "description": _clean_text(item.get("description")),
                    "status": item.get("status") or attributes.get("status"),
                    "location": _clean_text(
                        item.get("location") or attributes.get("location")
                    ),
                    "reason": attributes.get("reason"),
                    "priority": item.get("priority"),
                    "lines": lines,
                    "stops": stops,
                    "start": time_info.get("start"),
                    "end": time_info.get("end"),
                }
            )

        alerts.sort(
            key=lambda alert: TRAFFIC_INFO_CATEGORY_ORDER.get(
                alert["category"], len(TRAFFIC_INFO_CATEGORY_ORDER)
            )
        )
        total_count = len(alerts)
        alerts = alerts[:max_alerts]
        return {
            "alerts_count": len(alerts),
            "total_count": total_count,
            "alerts": alerts,
        }

    except TimeoutError:
        _LOGGER.error("Timeout fetching Wiener Linien traffic info")
        return {"message": "Timeout"}
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching Wiener Linien traffic info: %s", err)
        return {"message": "No data"}
    except Exception as err:
        _LOGGER.warning("Unexpected error fetching Wiener Linien traffic info: %s", err)
        return {"message": "No data"}
