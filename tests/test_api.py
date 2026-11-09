"""Tests for the Wiener Linien Monitor API helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.austria_public_transport.api import (
    async_fetch_departures,
    async_fetch_traffic_info,
)


def _make_session(json_data: dict, raise_error: Exception | None = None) -> MagicMock:
    """Create a mock aiohttp session."""
    response = AsyncMock()
    response.json = AsyncMock(return_value=json_data)

    session = MagicMock(spec=aiohttp.ClientSession)
    if raise_error:
        session.get = AsyncMock(side_effect=raise_error)
    else:
        session.get = AsyncMock(return_value=response)

    return session


SAMPLE_API_RESPONSE = {
    "data": {
        "monitors": [
            {
                "locationStop": {"properties": {"title": "Karlsplatz"}},
                "lines": [
                    {
                        "name": "U1",
                        "towards": "Oberlaa",
                        "platform": "1",
                        "departures": {
                            "departure": [
                                {
                                    "departureTime": {
                                        "timePlanned": "2025-01-01T12:00:00.000+0100",
                                        "timeReal": "2025-01-01T12:01:00.000+0100",
                                        "countdown": 3,
                                    },
                                    "vehicle": {
                                        "barrierFree": True,
                                        "foldingRamp": False,
                                        "type": "U-Bahn",
                                    },
                                },
                                {
                                    "departureTime": {
                                        "timePlanned": "2025-01-01T12:05:00.000+0100",
                                        "timeReal": None,
                                        "countdown": 8,
                                    },
                                    "vehicle": {
                                        "barrierFree": True,
                                        "foldingRamp": True,
                                        "type": "U-Bahn",
                                    },
                                },
                            ]
                        },
                    },
                    {
                        "name": "U4",
                        "towards": "Hütteldorf",
                        "platform": "2",
                        "departures": {
                            "departure": [
                                {
                                    "departureTime": {
                                        "timePlanned": "2025-01-01T12:02:00.000+0100",
                                        "timeReal": "2025-01-01T12:02:30.000+0100",
                                        "countdown": 5,
                                    },
                                    "vehicle": {
                                        "barrierFree": False,
                                        "foldingRamp": False,
                                        "type": "U-Bahn",
                                    },
                                }
                            ]
                        },
                    },
                ],
            }
        ]
    },
    "message": {"serverTime": "2025-01-01T12:00:00.000+0100"},
}


@pytest.mark.asyncio
async def test_fetch_departures_success() -> None:
    """Test successful departure fetch and parsing."""
    session = _make_session(SAMPLE_API_RESPONSE)

    result = await async_fetch_departures(session, "4609")

    assert result["departures_count"] == 3
    assert result["stop_id"] == "4609"
    assert result["stop_name"] == "Karlsplatz"
    assert result["server_time"] == "2025-01-01T12:00:00.000+0100"
    assert "message" not in result

    # Should be sorted by countdown
    countdowns = [d["countdown"] for d in result["departures"]]
    assert countdowns == [3, 5, 8]


@pytest.mark.asyncio
async def test_fetch_departures_sorted_by_countdown() -> None:
    """Test that departures are sorted by countdown."""
    session = _make_session(SAMPLE_API_RESPONSE)

    result = await async_fetch_departures(session, "4609")

    departures = result["departures"]
    assert departures[0]["line"] == "U1"
    assert departures[0]["countdown"] == 3
    assert departures[1]["line"] == "U4"
    assert departures[1]["countdown"] == 5
    assert departures[2]["line"] == "U1"
    assert departures[2]["countdown"] == 8


@pytest.mark.asyncio
async def test_fetch_departures_parses_fields() -> None:
    """Test that all fields are parsed correctly."""
    session = _make_session(SAMPLE_API_RESPONSE)

    result = await async_fetch_departures(session, "4609")

    first = result["departures"][0]
    assert first["line"] == "U1"
    assert first["direction"] == "Oberlaa"
    assert first["platform"] == "1"
    assert first["time_planned"] == "2025-01-01T12:00:00.000+0100"
    assert first["time_real"] == "2025-01-01T12:01:00.000+0100"
    assert first["countdown"] == 3
    assert first["barrier_free"] is True
    assert first["folding_ramp"] is False
    assert first["type"] == "U-Bahn"


@pytest.mark.asyncio
async def test_fetch_departures_no_monitors() -> None:
    """Test response when no monitors are available."""
    data = {"data": {"monitors": []}}
    session = _make_session(data)

    result = await async_fetch_departures(session, "9999")

    assert result == {"message": "No data"}


@pytest.mark.asyncio
async def test_fetch_departures_no_data_key() -> None:
    """Test response when data key is missing."""
    session = _make_session({})

    result = await async_fetch_departures(session, "9999")

    assert result == {"message": "No data"}


@pytest.mark.asyncio
async def test_fetch_departures_client_error() -> None:
    """Test handling of aiohttp client errors."""
    session = _make_session({}, raise_error=aiohttp.ClientError("Connection failed"))

    result = await async_fetch_departures(session, "4609")

    assert result == {"message": "No data"}


@pytest.mark.asyncio
async def test_fetch_departures_timeout() -> None:
    """Test handling of timeout errors."""
    session = _make_session({}, raise_error=TimeoutError())

    result = await async_fetch_departures(session, "4609")

    assert result == {"message": "Timeout"}


@pytest.mark.asyncio
async def test_fetch_departures_empty_departures() -> None:
    """Test a monitor with no departures."""
    data = {
        "data": {
            "monitors": [
                {
                    "locationStop": {"properties": {"title": "Stephansplatz"}},
                    "lines": [
                        {
                            "name": "U3",
                            "towards": "Ottakring",
                            "platform": "1",
                            "departures": {"departure": []},
                        }
                    ],
                }
            ]
        },
        "message": {"serverTime": "2025-01-01T12:00:00.000+0100"},
    }
    session = _make_session(data)

    result = await async_fetch_departures(session, "1234")

    assert result["departures_count"] == 0
    assert result["departures"] == []
    assert result["stop_name"] == "Stephansplatz"


PLANNED_EARLY = "2024-01-01T10:03:00.000+0100"
PLANNED_LATE = "2024-01-01T10:05:00.000+0100"


@pytest.mark.asyncio
async def test_fetch_departures_null_countdown_does_not_crash() -> None:
    """A departure without a countdown must not wipe out the whole stop."""
    response = {
        "data": {
            "monitors": [
                {
                    "locationStop": {"properties": {"title": "Karlsplatz"}},
                    "lines": [
                        {
                            "name": "U1",
                            "towards": "Oberlaa",
                            "platform": "1",
                            "departures": {
                                "departure": [
                                    {
                                        "departureTime": {
                                            "timePlanned": PLANNED_LATE,
                                            "countdown": None,
                                        },
                                        "vehicle": {"type": "ptMetro"},
                                    },
                                    {
                                        "departureTime": {
                                            "timePlanned": PLANNED_EARLY,
                                            "countdown": 3,
                                        },
                                        "vehicle": {"type": "ptMetro"},
                                    },
                                ]
                            },
                        }
                    ],
                }
            ]
        },
        "message": {"serverTime": "2024-01-01T10:00:00.000+0100"},
    }
    session = _make_session(response)

    result = await async_fetch_departures(session, "247")

    assert "message" not in result
    assert result["departures_count"] == 2
    # Known countdown sorts ahead of the unknown one
    assert [d["countdown"] for d in result["departures"]] == [3, None]


SAMPLE_TRAFFIC_INFO = {
    "data": {
        "trafficInfoCategories": [
            {"id": 1, "name": "aufzugsinfo", "title": "Aufzugsstörungen"},
            {"id": 2, "name": "stoerunglang", "title": "Störung Lang"},
            {"id": 3, "name": "stoerungkurz", "title": "Störung Kurz"},
        ],
        "trafficInfos": [
            {
                "refTrafficInfoCategoryId": 1,
                "name": "ftazS_262",
                "title": "Landstraße",
                "description": "U4 Mittelbahnsteig - Ausgang Landstraßer Hauptstraße",
                "attributes": {
                    "status": "außer Betrieb",
                    "reason": "An der Instandsetzung wird bereits gearbeitet.",
                    "location": "U4 Mittelbahnsteig",
                },
                "time": {
                    "start": "2026-11-05T01:15:00.000+0100",
                    "end": "2026-11-05T05:15:00.000+0100",
                },
                "relatedLines": ["U3", "U4"],
                "relatedStops": [4904, 4913, 4904, 4913],
            },
            {
                "refTrafficInfoCategoryId": 2,
                "name": "I20260909-0007",
                "priority": "1",
                "title": "25, 26, 27: Gleisbauarbeiten",
                "description": "Linie 25: Betrieb nur zwischen Aspern und Kagran.",
                "status": "active",
                "location": "Donaufelder Straße ",
                "time": {
                    "start": "2026-09-14T04:30:00.000+0200",
                    "end": "2026-12-12T02:00:00.000+0100",
                },
                "relatedLines": ["25", "26", "27"],
            },
            {
                "refTrafficInfoCategoryId": 3,
                "name": "R119-136",
                "priority": "1",
                "title": "Züge halten in\nSchleife",
                "description": "Züge halten in\nSchleife",
                "relatedLines": ["D"],
                "relatedStops": [119],
            },
        ],
    },
    "message": {"value": "OK", "messageCode": 1},
}


@pytest.mark.asyncio
async def test_fetch_traffic_info_normalizes_all_categories() -> None:
    """Test that all three categories are read from their own field layout."""
    session = _make_session(SAMPLE_TRAFFIC_INFO)

    result = await async_fetch_traffic_info(session)

    assert result["alerts_count"] == 3
    long_term, short_term, elevator = result["alerts"]
    assert elevator["category"] == "aufzugsinfo"
    assert elevator["status"] == "außer Betrieb"
    assert elevator["reason"] == "An der Instandsetzung wird bereits gearbeitet."
    assert elevator["stops"] == [4904, 4913]
    assert long_term["status"] == "active"
    assert long_term["location"] == "Donaufelder Straße"
    assert long_term["stops"] == []
    assert short_term["title"] == "Züge halten in Schleife"
    assert short_term["start"] is None


@pytest.mark.asyncio
async def test_fetch_traffic_info_filters() -> None:
    """Test the category, line (case-insensitive) and stop filters."""
    session = _make_session(SAMPLE_TRAFFIC_INFO)

    by_category = await async_fetch_traffic_info(session, category="stoerunglang")
    by_line = await async_fetch_traffic_info(session, line="u4")
    by_stop = await async_fetch_traffic_info(session, stop_id=119)

    assert [a["id"] for a in by_category["alerts"]] == ["I20260909-0007"]
    assert [a["id"] for a in by_line["alerts"]] == ["ftazS_262"]
    assert [a["id"] for a in by_stop["alerts"]] == ["R119-136"]


@pytest.mark.asyncio
async def test_fetch_traffic_info_max_alerts() -> None:
    """Test that the result is capped in max_alerts."""
    session = _make_session(SAMPLE_TRAFFIC_INFO)

    result = await async_fetch_traffic_info(session, max_alerts=2)

    assert result["alerts_count"] == 2


@pytest.mark.asyncio
async def test_fetch_traffic_info_missing_fields_do_not_crash() -> None:
    """Test that  alert with almost no fields is still returned."""
    session = _make_session(
        {
            "data": {"trafficInfos": [{"name": "X1"}]},
            "message": {"value": "OK", "messageCode": 1},
        }
    )

    result = await async_fetch_traffic_info(session)

    assert result["alerts_count"] == 1
    assert result["alerts"][0]["category"] is None
    assert result["alerts"][0]["lines"] == []


@pytest.mark.asyncio
async def test_fetch_traffic_info_client_error() -> None:
    """Test handling of aiohttp client errors."""
    session = _make_session({}, raise_error=aiohttp.ClientError("Connection failed"))

    result = await async_fetch_traffic_info(session)

    assert result == {"message": "No data"}


@pytest.mark.asyncio
async def test_fetch_traffic_info_timeout() -> None:
    """Test handling timeout errors."""
    session = _make_session({}, raise_error=TimeoutError())

    result = await async_fetch_traffic_info(session)

    assert result == {"message": "Timeout"}
